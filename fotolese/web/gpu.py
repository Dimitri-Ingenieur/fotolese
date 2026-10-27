"""fotolese.web.gpu – Gesichtsmodelle (YuNet, SFace) auf der GPU rechnen, wenn eine nutzbar ist.

waehlen() prüft beim Start in einem eigenen Prozess die Rechenwerke in KANDIDATEN der Reihe nach: ONNX Runtime
(CUDA, ROCm, DirectML, CoreML, OpenVINO) und OpenCV (CUDA, OpenCL). Genommen wird das erste, das wie die CPU
rechnet und schneller ist; sonst bleibt alles auf der CPU wie bisher.
Erkenner rechnet auf der CPU mit cv2.FaceDetectorYN/FaceRecognizerSF, auf der GPU mit derselben Vor- und
Nachverarbeitung, hier in numpy nachgebaut (OpenCV objdetect: face_detect.cpp, face_recognize.cpp) – gleiche
Gesichter, Punkte und Merkmale. Scheitert die GPU unterwegs (z. B. Speicher voll), rechnet er auf der CPU weiter.
"""
import contextlib
import ctypes
import io
import multiprocessing as mp
import os
import re
import sys
import tempfile
import time
from importlib.util import find_spec

import numpy as np

NMS, TOP_K = 0.3, 5000
STRIDES = (8, 16, 32)
AUSGAENGE = [f"{art}_{s}" for art in ("cls", "obj", "bbox", "kps") for s in STRIDES]
# Kennung (Wert für GPU=…), Anzeige, Art, ONNX-Runtime-Provider bzw. OpenCV-Backend, Provider-Optionen.
# Nicht dabei: TensorRT und MIGraphX – sie übersetzen das Netz für jede neue Bildgröße neu.
# CUDA: keine Algorithmensuche je Bildgröße (HEURISTIC), volle Genauigkeit wie die CPU (kein TF32).
KANDIDATEN = [
    ("cuda", "CUDA (ONNX Runtime)", "ort", "CUDAExecutionProvider",
     {"device_id": "0", "cudnn_conv_algo_search": "HEURISTIC", "arena_extend_strategy": "kSameAsRequested",
      "use_tf32": "0"}),
    ("rocm", "ROCm (ONNX Runtime)", "ort", "ROCMExecutionProvider", {"device_id": "0"}),
    ("directml", "DirectML (ONNX Runtime)", "ort", "DmlExecutionProvider", {"device_id": "0"}),
    ("coreml", "CoreML (ONNX Runtime)", "ort", "CoreMLExecutionProvider",
     {"ModelFormat": "MLProgram", "MLComputeUnits": "CPUAndGPU"}),
    ("openvino", "OpenVINO (ONNX Runtime)", "ort", "OpenVINOExecutionProvider", {"device_type": "GPU", "precision": "FP32"}),
    ("opencv-cuda", "CUDA (OpenCV)", "cv", "cuda", None),
    ("opencl", "OpenCL (OpenCV)", "cv", "opencl", None),
]
NVIDIA_HINWEIS = 'python -m pip install "onnxruntime-gpu[cuda,cudnn]" (siehe README, GPU)'


# ---- ONNX-Modell anpassen, ohne das onnx-Paket: Protobuf-Felder direkt lesen und schreiben ----
def _varint_lesen(b, i):
    wert = schiebe = 0
    while True:
        x = b[i]
        i += 1
        wert |= (x & 0x7F) << schiebe
        if x < 0x80:
            return wert, i
        schiebe += 7


def _varint(wert):
    aus = bytearray()
    while True:
        x, wert = wert & 0x7F, wert >> 7
        aus.append(x | 0x80 if wert else x)
        if not wert:
            return bytes(aus)


def _felder(b):
    """Protobuf-Nachricht -> [(Feldnummer, Drahttyp, Wert)]; Wert = Inhalt (Typ 2) oder die Rohbytes."""
    b = memoryview(b)
    i, felder = 0, []
    while i < len(b):
        schluessel, i = _varint_lesen(b, i)
        nr, typ = schluessel >> 3, schluessel & 7
        if typ == 0:
            _, j = _varint_lesen(b, i)
        elif typ == 1:
            j = i + 8
        elif typ == 2:
            laenge, i = _varint_lesen(b, i)
            j = i + laenge
        elif typ == 5:
            j = i + 4
        else:
            raise ValueError(f"Protobuf-Drahttyp {typ} nicht unterstützt")
        felder.append((nr, typ, b[i:j]))
        i = j
    return felder


def _bytes(felder):
    return b"".join(b"".join((_varint(nr << 3 | typ), _varint(len(w)) if typ == 2 else b"", w))
                    for nr, typ, w in felder)


def _text(b, nr):
    return next((bytes(w).decode("utf-8", "replace") for n, t, w in _felder(b) if n == nr and t == 2), "")


def _masse(value_info, variabel):
    """ValueInfoProto (-> type -> tensor_type -> shape): Maße an den Positionen in variabel (Index -> Name) frei."""
    def tiefer(b, pfad):
        if not pfad:
            felder, k = [], 0
            for nr, t, w in _felder(b):
                if nr == 1:  # TensorShapeProto.dim
                    if k in variabel:
                        w = _bytes([(2, 2, variabel[k].encode())])  # Dimension.dim_param statt dim_value
                    k += 1
                felder.append((nr, t, w))
            return _bytes(felder)
        return _bytes([(nr, t, tiefer(w, pfad[1:]) if nr == pfad[0] and t == 2 else w) for nr, t, w in _felder(b)])
    return tiefer(value_info, (2, 1, 2))


def modell_anpassen(modell, eingang=None, ausgang=None):
    """Für ONNX Runtime: Gewichte aus den Graph-Eingängen nehmen (sonst keine Optimierung), value_info weglassen
    (feste Zwischenmaße) und die Maße von Ein- und Ausgängen frei machen – YuNet ist auf 640x640 festgelegt."""
    def graph(b):
        felder = _felder(b)
        gewichte = {_text(w, 8) for nr, t, w in felder if nr == 5}  # initializer -> TensorProto.name
        aus = []
        for nr, t, w in felder:
            if nr == 13:  # value_info
                continue
            if nr == 11:  # input
                if _text(w, 1) in gewichte:
                    continue
                if eingang:
                    w = _masse(w, eingang)
            if nr == 12 and ausgang:  # output
                w = _masse(w, ausgang)
            aus.append((nr, t, w))
        return _bytes(aus)
    return _bytes([(nr, t, graph(w) if nr == 7 and t == 2 else w) for nr, t, w in _felder(modell)])


# ---- Vor- und Nachverarbeitung wie in OpenCV ----
def yunet_blob(cv2, bgr):
    """Rechts und unten mit Schwarz auf Vielfache von 32 auffüllen (FaceDetectorYN::padWithDivisor)."""
    h, w = bgr.shape[:2]
    ph, pw = (h - 1) // 32 * 32 + 32, (w - 1) // 32 * 32 + 32
    pad = cv2.copyMakeBorder(bgr, 0, ph - h, 0, pw - w, cv2.BORDER_CONSTANT, value=0)
    return cv2.dnn.blobFromImage(pad), pw, ph


def yunet_dekodieren(cv2, ausgaben, pw, ph, score):
    """Wie FaceDetectorYN::postProcess: Gesichter (x, y, w, h, 5 Punkte, Score) als (n, 15) float32 oder None."""
    teile = []
    for k, s in enumerate(STRIDES):
        cls, obj = ausgaben[k].reshape(-1), ausgaben[3 + k].reshape(-1)
        bbox, kps = ausgaben[6 + k].reshape(-1, 4), ausgaben[9 + k].reshape(-1, 10)
        sc = np.sqrt(np.clip(cls, 0, 1) * np.clip(obj, 0, 1))
        idx = np.nonzero(sc >= np.float32(score))[0]
        if not idx.size:
            continue
        r, c = np.divmod(idx, pw // s)
        r, c, st = r.astype(np.float32), c.astype(np.float32), np.float32(s)
        b, p = bbox[idx], kps[idx]
        f = np.empty((idx.size, 15), np.float32)
        w, h = np.exp(b[:, 2]) * st, np.exp(b[:, 3]) * st
        f[:, 0] = (c + b[:, 0]) * st - w / np.float32(2)
        f[:, 1] = (r + b[:, 1]) * st - h / np.float32(2)
        f[:, 2], f[:, 3] = w, h
        f[:, 4:14:2] = (p[:, 0::2] + c[:, None]) * st
        f[:, 5:14:2] = (p[:, 1::2] + r[:, None]) * st
        f[:, 14] = sc[idx]
        teile.append(f)
    if not teile:
        return None
    f = np.concatenate(teile)
    if len(f) > 1:
        kaesten = [tuple(int(v) for v in z[:4]) for z in f]  # wie Rect2i: Nachkommastellen abschneiden
        f = f[np.asarray(cv2.dnn.NMSBoxes(kaesten, f[:, 14].tolist(), score, NMS, 1.0, TOP_K), int).reshape(-1)]
    return f if len(f) else None


_ZIEL = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655],
                  [70.7299, 92.2041]], np.float32)
_ZIEL_MITTE = np.array([56.0262, 71.9008], np.float32)


def _summe5(a):
    return float(a[0]) + float(a[1]) + float(a[2]) + float(a[3]) + float(a[4])


def ausrichtung(gesicht):
    """Wie FaceRecognizerSF::getSimilarityTransformMatrix: Augen, Nase, Mundwinkel auf feste Punkte (Umeyama)."""
    src = np.asarray(gesicht, np.float32).reshape(-1)[4:14].reshape(5, 2)
    mitte = np.array([(src[0, j] + src[1, j] + src[2, j] + src[3, j] + src[4, j]) / np.float32(5) for j in (0, 1)],
                     np.float32)
    s_d, d_d = src - mitte, _ZIEL - _ZIEL_MITTE
    A = np.array([[_summe5(d_d[:, 0] * s_d[:, 0]) / 5, _summe5(d_d[:, 0] * s_d[:, 1]) / 5],
                  [_summe5(d_d[:, 1] * s_d[:, 0]) / 5, _summe5(d_d[:, 1] * s_d[:, 1]) / 5]])
    d = np.array([1.0, -1.0 if A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0] < 0 else 1.0])
    u, s, vt = np.linalg.svd(A)
    tol = max(s) * 2 * np.finfo(np.float32).tiny
    if int(s[0] > tol) + int(s[1] > tol) == 1:
        T = u @ vt if np.linalg.det(u) * np.linalg.det(vt) > 0 else u @ np.diag([d[0], -1.0]) @ vt
    else:
        T = u @ np.diag(d) @ vt
    skala = (s[0] * d[0] + s[1] * d[1]) / (_summe5(s_d[:, 0] * s_d[:, 0]) / 5 + _summe5(s_d[:, 1] * s_d[:, 1]) / 5)
    return np.hstack([T * skala, (_ZIEL_MITTE.astype(np.float64) - skala * (T @ mitte.astype(np.float64)))[:, None]])


def ausrichten(cv2, bgr, gesicht):
    """Wie FaceRecognizerSF.alignCrop: 112x112 Pixel, Gesicht aufrecht in der Mitte."""
    return cv2.warpAffine(bgr, ausrichtung(gesicht), (112, 112), flags=cv2.INTER_LINEAR)


def sface_blob(cv2, ausgerichtet):
    return cv2.dnn.blobFromImage(ausgerichtet, 1, (112, 112), (0, 0, 0), True, False)


# ---- Netze ----
class _OrtNetz:
    def __init__(self, modell, provider, optionen, **anpassen):
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        if provider == "CUDAExecutionProvider" and hasattr(ort, "preload_dlls"):
            with contextlib.redirect_stdout(io.StringIO()):
                ort.preload_dlls()  # CUDA/cuDNN aus den pip-Paketen nvidia-* laden
        o = ort.SessionOptions()
        o.intra_op_num_threads = o.inter_op_num_threads = 1
        if provider == "DmlExecutionProvider":
            o.enable_mem_pattern = False
            o.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        with open(modell, "rb") as f:
            daten = modell_anpassen(f.read(), **anpassen)
        self.sitzung = ort.InferenceSession(daten, o, providers=[(provider, optionen), "CPUExecutionProvider"])
        if self.sitzung.get_providers()[0] != provider:  # ONNX Runtime fällt sonst still auf die CPU zurück
            raise RuntimeError(f"{provider} nicht aktiv")
        self.eingang = self.sitzung.get_inputs()[0].name

    def rechnen(self, blob, namen=None):
        return self.sitzung.run(namen, {self.eingang: blob})


class _CvNetz:
    def __init__(self, cv2, modell, backend, ziel):
        # die neue Engine von OpenCV 5 rechnet nur auf der CPU – für GPU-Ziele die klassische nehmen
        engine = (cv2.dnn.ENGINE_CLASSIC,) if hasattr(cv2.dnn, "ENGINE_CLASSIC") else ()
        self.netz = cv2.dnn.readNet(modell, "", "", *engine)
        self.netz.setPreferableBackend(backend)
        self.netz.setPreferableTarget(ziel)

    def rechnen(self, blob, namen=None):
        self.netz.setInput(blob)
        return list(self.netz.forward(namen)) if namen else [self.netz.forward()]


def _kandidat(kennung):
    return next(k for k in KANDIDATEN if k[0] == kennung)


def _netze(cv2, modelle, kennung):
    _, _, art, ziel, optionen = _kandidat(kennung)
    if art == "ort":
        return (_OrtNetz(modelle[0], ziel, optionen, eingang={2: "hoehe", 3: "breite"}, ausgang={1: "anzahl"}),
                _OrtNetz(modelle[1], ziel, optionen))
    backend, target = ((cv2.dnn.DNN_BACKEND_CUDA, cv2.dnn.DNN_TARGET_CUDA) if ziel == "cuda"
                       else (cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_OPENCL))
    return _CvNetz(cv2, modelle[0], backend, target), _CvNetz(cv2, modelle[1], backend, target)


class Erkenner:
    """Gesichter finden (YuNet) und Merkmale berechnen (SFace) – auf der gewählten GPU oder der CPU.
    wahl: Ergebnis von waehlen() oder None (CPU). gpu sagt, ob gerade die GPU rechnet; rueckfall, warum nicht mehr."""

    def __init__(self, modelle, score=0.5, wahl=None):
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        import cv2
        self.cv2, self.modelle, self.score = cv2, modelle, score
        self.netze = self.anzeige = self.rueckfall = self.fehler = None
        self._det = self._rec = None
        self.klein_cpu = False
        if wahl and wahl.get("kennung"):
            self.anzeige = wahl.get("anzeige") or wahl["kennung"]
            try:
                self.netze = _netze(cv2, modelle, wahl["kennung"])
            except Exception as fehler:
                self._aufgeben(fehler)
            # OpenCV richtet seine GPU-Kernel für jede neue Bildgröße neu ein – kleine Ausschnitte (Gegenprobe,
            # jedes Mal eine andere Größe) rechnet die CPU schneller
            self.klein_cpu = _kandidat(wahl["kennung"])[2] == "cv"

    @property
    def gpu(self):
        return self.netze is not None

    def _aufgeben(self, fehler):
        self.fehler, self.rueckfall = fehler, f"{self.anzeige}: {_grund('', fehler)}"
        self.netze = None

    def erkennen(self, bgr):
        """Wie FaceDetectorYN.detect (Score-Schwelle score, NMS 0,3): (n, 15) float32 oder None."""
        if self.netze and not (self.klein_cpu and max(bgr.shape[:2]) <= 320):
            try:
                blob, pw, ph = yunet_blob(self.cv2, bgr)
                return yunet_dekodieren(self.cv2, self.netze[0].rechnen(blob, AUSGAENGE), pw, ph, self.score)
            except Exception as fehler:
                self._aufgeben(fehler)
        if self._det is None:
            self._det = self.cv2.FaceDetectorYN.create(self.modelle[0], "", (320, 320), self.score, NMS, TOP_K)
        self._det.setInputSize((bgr.shape[1], bgr.shape[0]))
        return self._det.detect(bgr)[1]

    def merkmal(self, bgr, gesicht):
        """Wie FaceRecognizerSF.feature(alignCrop(bgr, gesicht)): 128 Werte, float32."""
        if self.netze:
            try:
                ausgerichtet = ausrichten(self.cv2, bgr, gesicht)
                return np.asarray(self.netze[1].rechnen(sface_blob(self.cv2, ausgerichtet))[0], np.float32).ravel()
            except Exception as fehler:
                self._aufgeben(fehler)
        if self._rec is None:
            self._rec = self.cv2.FaceRecognizerSF.create(self.modelle[1], "")
        return self._rec.feature(self._rec.alignCrop(bgr, gesicht)).astype(np.float32).ravel()


# ---- Auswahl ----
def _nvidia_name():
    """Name der ersten NVIDIA-GPU über NVML (kommt mit dem Treiber), sonst ''."""
    for datei in ("libnvidia-ml.so.1", "nvml.dll"):
        try:
            nvml = ctypes.CDLL(datei)
        except OSError:
            continue
        try:
            griff, name = ctypes.c_void_p(), ctypes.create_string_buffer(96)
            if (nvml.nvmlInit_v2() == 0 and nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(griff)) == 0
                    and nvml.nvmlDeviceGetName(griff, name, 96) == 0):
                return name.value.decode("utf-8", "replace")
        except (AttributeError, OSError):
            pass
        finally:
            with contextlib.suppress(AttributeError, OSError):
                nvml.nvmlShutdown()
    return ""


def _geraet(cv2, ziel):
    if ziel in ("CUDAExecutionProvider", "cuda"):
        return _nvidia_name()
    if ziel == "opencl":
        return cv2.ocl.Device.getDefault().name().strip()
    return ""


def _fehlt(cv2, art, ziel, erzwungen):
    """None = nutzbar; True = nicht vorhanden (kein Grund nötig); Text = vorhanden, aber nicht nutzbar."""
    if art == "ort":
        if find_spec("onnxruntime") is None:
            return "ONNX Runtime nicht installiert" if erzwungen else True
        import onnxruntime as ort
        if ziel not in ort.get_available_providers():
            return f"{ziel} fehlt in dieser ONNX Runtime" if erzwungen else True
        return None
    if ziel == "cuda":
        try:
            ok = cv2.cuda.getCudaEnabledDeviceCount() > 0 and len(cv2.dnn.getAvailableTargets(cv2.dnn.DNN_BACKEND_CUDA))
        except (AttributeError, cv2.error):
            ok = False
        return None if ok else ("OpenCV ohne CUDA gebaut" if erzwungen else True)
    if not cv2.ocl.haveOpenCL() or not cv2.ocl.Device.getDefault().name():
        return "kein OpenCL-Gerät" if erzwungen else True
    if cv2.ocl.Device.getDefault().type() != cv2.ocl.Device_TYPE_GPU and not erzwungen:
        return True  # OpenCL auf der CPU bringt nichts
    return None


@contextlib.contextmanager
def _mitschneiden(text):
    """Ausgaben der GPU-Bibliotheken (C++ auf fd 1/2) auffangen – darin steht, woran es scheitert."""
    sys.stdout.flush()
    sys.stderr.flush()
    with tempfile.TemporaryFile() as f:
        alt = os.dup(1), os.dup(2)
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(alt[0], 1)
            os.dup2(alt[1], 2)
            os.close(alt[0])
            os.close(alt[1])
            f.seek(0)
            text.append(f.read().decode("utf-8", "replace"))


class _Grund(Exception):
    """Selbst formulierte Ursache – wird so angezeigt."""


def _grund(text, fehler=None):
    """Kurze Fehlerursache aus Bibliotheksausgabe und Ausnahme, z. B. 'libcudnn.so.9 fehlt'."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    alles = f"{text}\n{fehler or ''}"
    m = re.search(r"([\w.+-]+\.(?:so[\w.]*|dll|dylib)):\s*cannot open shared object", alles)
    if m:
        return f"{m.group(1)} fehlt"
    unten = alles.lower()
    if "insufficient" in unten and "driver" in unten:
        return "Grafiktreiber zu alt für diese CUDA-Version"
    if "out of memory" in unten:
        return "GPU-Speicher voll"
    if isinstance(fehler, _Grund):
        return str(fehler)
    zeilen = [z.strip() for z in text.splitlines() if re.search(r"error|fail", z, re.I)]
    kurz = zeilen[-1] if zeilen else (f"{type(fehler).__name__}: {fehler}" if fehler else "unbekannter Fehler")
    return re.sub(r"^\[[^\]]*\]\s*", "", kurz)[-200:]


def _cuda_hinweis(grund):
    """Was bei CUDA hilft: den Treiber gibt es nur von NVIDIA, CUDA und cuDNN bringen die pip-Extras mit."""
    if grund.startswith(("libcuda.so", "nvcuda.dll")):
        return f"NVIDIA-Grafiktreiber fehlt ({grund.split()[0]})"
    if grund.startswith("Grafiktreiber zu alt"):
        return f'{grund} – Treiber aktualisieren oder für CUDA 12: "onnxruntime-gpu[cuda,cudnn]<1.27"'
    if grund.endswith(" fehlt"):
        return f"{grund} – {NVIDIA_HINWEIS}"
    return grund


def _ms(f, aufwaermen=1, n=3):
    for _ in range(aufwaermen):
        f()
    zeiten = []
    for _ in range(n):
        t = time.perf_counter()
        f()
        zeiten.append((time.perf_counter() - t) * 1000)
    return sorted(zeiten)[n // 2]


def pruefen(modelle, wunsch="auto"):
    """Rechenwerk wählen (läuft in einem eigenen Prozess, siehe waehlen). Jeder Kandidat muss auf Testdaten wie
    die CPU rechnen (Ausgaben bis 1 % Abweichung, Merkmal-Kosinus ab 0,999) und YuNet bei 1280x960 Pixeln
    schneller schaffen; bei GPU = <Kennung> zählt nur, dass er richtig rechnet."""
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    import cv2
    cv2.setNumThreads(1)  # wie in den Index-Prozessen
    wunsch = (wunsch or "auto").strip().lower()
    if wunsch in ("0", "aus", "nein", "cpu"):
        return {"kennung": None, "grund": "GPU = 0 gesetzt"}
    if wunsch != "auto" and wunsch not in {k[0] for k in KANDIDATEN}:
        return {"kennung": None, "grund": f"GPU = {wunsch} unbekannt (erlaubt: auto, 0, "
                                          f"{', '.join(k[0] for k in KANDIDATEN)})"}
    zufall = np.random.default_rng(1)
    probe = zufall.random((1, 3, 224, 320), dtype=np.float32) * 255
    gesicht = (zufall.random((112, 112, 3)) * 255).astype(np.uint8)
    bild = (zufall.random((960, 1280, 3)) * 255).astype(np.uint8)
    cpu_det = _CvNetz(cv2, modelle[0], cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU)
    soll_det = cpu_det.rechnen(probe, AUSGAENGE)
    soll_rec = _CvNetz(cv2, modelle[1], cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU).rechnen(
        sface_blob(cv2, gesicht))[0].ravel()
    cpu = Erkenner(modelle)
    ms_cpu = _ms(lambda: cpu.erkennen(bild))
    gruende = []
    for kennung, anzeige, art, ziel, _ in KANDIDATEN:
        if wunsch not in ("auto", kennung):
            continue
        fehlt = _fehlt(cv2, art, ziel, wunsch != "auto")
        if fehlt:
            if fehlt is not True:
                gruende.append(f"{anzeige}: {fehlt}")
            continue
        text = []
        try:
            with _mitschneiden(text):
                erk = Erkenner(modelle, 0.5, {"kennung": kennung, "anzeige": anzeige})
                if not erk.gpu:
                    raise erk.fehler
                ist_det = erk.netze[0].rechnen(probe, AUSGAENGE)
                ist_rec = np.asarray(erk.netze[1].rechnen(sface_blob(cv2, gesicht))[0], np.float32).ravel()
                abw = max(float(np.abs(a - b).max()) / (float(np.abs(a).max()) + 1e-6) for a, b in zip(soll_det, ist_det))
                cos = float(soll_rec @ ist_rec) / (float(np.linalg.norm(soll_rec) * np.linalg.norm(ist_rec)) or 1.0)
                if abw > 0.01 or cos < 0.999:
                    raise _Grund(f"rechnet ungenau (Abweichung {abw:.1%}, Merkmal {cos:.4f})")
                ms_gpu = _ms(lambda: erk.erkennen(bild), aufwaermen=2)
                if not erk.gpu:
                    raise erk.fehler
        except Exception as fehler:
            grund = _grund("".join(text), fehler)
            gruende.append(f"{anzeige}: {_cuda_hinweis(grund) if kennung == 'cuda' else grund}")
            continue
        if wunsch == "auto" and ms_gpu >= 0.8 * ms_cpu:
            gruende.append(f"{anzeige}: nicht schneller als die CPU ({ms_gpu:.0f} statt {ms_cpu:.0f} ms)")
            continue
        return {"kennung": kennung, "anzeige": anzeige, "geraet": _geraet(cv2, ziel), "ms_gpu": ms_gpu, "ms_cpu": ms_cpu}
    if not gruende:
        nvidia = _nvidia_name()
        gruende.append(f"{nvidia} gefunden, aber ohne GPU-Unterstützung für Python – {NVIDIA_HINWEIS}" if nvidia
                       else "keine GPU gefunden")
    return {"kennung": None, "grund": "; ".join(gruende), "ms_cpu": ms_cpu}


def _kind(modelle, wunsch, rueck):
    try:
        ergebnis = pruefen(modelle, wunsch)
    except Exception as fehler:
        ergebnis = {"kennung": None, "grund": f"Prüfung gescheitert: {type(fehler).__name__}: {fehler}"[:300]}
    rueck.send(ergebnis)


def waehlen(modelle, wunsch="auto", frist=600):
    """pruefen() in einem eigenen Prozess: ein abstürzender Treiber trifft nicht bestof, und der GPU-Speicher
    der Probe wird danach wieder frei. Gibt immer ein Ergebnis zurück (bei Problemen: CPU mit Grund)."""
    if str(wunsch).strip().lower() in ("0", "aus", "nein", "cpu"):
        return {"kennung": None, "grund": "GPU = 0 gesetzt"}
    ctx = mp.get_context("spawn")
    empfang, senden = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_kind, args=(modelle, wunsch, senden), daemon=True)
    p.start()
    senden.close()
    try:
        if empfang.poll(frist):
            return empfang.recv()
        return {"kennung": None, "grund": f"GPU-Prüfung nach {frist} s abgebrochen"}
    except EOFError:
        p.join(5)
        return {"kennung": None, "grund": f"GPU-Prüfung abgestürzt (Code {p.exitcode})"}
    finally:
        if p.is_alive():
            p.terminate()
        p.join(5)
        empfang.close()
