"""fotolese.web.ki – KI-Bildmerkmale für „Ähnliche Fotos“: der Bildteil von CLIP ViT-B/32 als ONNX-Modell.

Der Indexer berechnet je Foto einmal einen Merkmalsvektor (512 Zahlen, Tabelle ki im Index). Er beschreibt den
Bildinhalt statt der Pixel: Ein Kind mit Mütze am Hafen ähnelt anderen Hafen- und Kinderfotos, auch mit anderem
Ausschnitt, Licht oder Format. Gerechnet wird auf der CPU in einem eigenen Prozess – mit ONNX Runtime oder, wenn das
fehlt, mit OpenCV ab Version 5. Die Ähnlichkeit zweier Fotos ist der Kosinus ihrer Vektoren (1 = gleich).
"""
import math
import os
import signal
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec

import numpy as np
from PIL import Image, ImageOps

from fotolese.web.bild import _rgb

KENNUNG = "clip-vit-b32-xenova/1"  # Modell und Vorverarbeitung; ändert sich das, rechnet der Index alles neu
GROESSE = 224
MITTEL = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)  # Normierung wie beim Training von CLIP
STREUUNG = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
MASSE = 512
STAPEL = 16  # Fotos je Auftrag an den KI-Prozess


def laufzeiten():
    """Womit sich das Modell rechnen lässt, in dieser Reihenfolge: ([„onnxruntime“, „opencv“], „“) – oder ([], Grund)."""
    arten = ["onnxruntime"] if find_spec("onnxruntime") is not None else []
    if find_spec("cv2") is None:
        return arten, "" if arten else "weder ONNX Runtime noch OpenCV installiert (python -m pip install opencv-python-headless)"
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    import cv2
    if hasattr(cv2.dnn, "ENGINE_NEW"):  # erst die neue Engine von OpenCV 5 kann CLIP
        arten.append("opencv")
    return arten, "" if arten else (f"OpenCV {cv2.__version__} kann das Modell nicht rechnen, nötig ist OpenCV ab 5 "
                                    "oder ONNX Runtime (python -m pip install -U opencv-python-headless)")


def vorbereiten(pfad):
    """Foto -> (3, 224, 224) float32 wie bei CLIP: kurze Seite bikubisch auf 224, Mitte ausschneiden, normieren.
    Ein JPEG wird gleich verkleinert dekodiert (draft) – schnell auch bei großen Fotos."""
    with Image.open(pfad) as img:
        if img.format in ("JPEG", "MPO"):
            w, h = img.size
            k = GROESSE / max(1, min(w, h))
            img.draft("RGB", (max(1, math.ceil(w * k)), max(1, math.ceil(h * k))))
        img.load()
        bild = _rgb(ImageOps.exif_transpose(img))
    w, h = bild.size
    k = GROESSE / max(1, min(w, h))
    neu = (max(GROESSE, round(w * k)), max(GROESSE, round(h * k)))
    bild = bild.resize(neu, Image.Resampling.BICUBIC)
    links, oben = (neu[0] - GROESSE) // 2, (neu[1] - GROESSE) // 2
    a = np.asarray(bild.crop((links, oben, links + GROESSE, oben + GROESSE)), np.float32) / 255.0
    return ((a - MITTEL) / STREUUNG).transpose(2, 0, 1)


# ---- KI-Prozess: ein Prozess mit mehreren Threads (das Modell liegt so nur einmal im Speicher) ----
_KW = {}


def _kw_init(modell, art, threads):
    warnings.simplefilter("ignore")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    threads = max(1, int(threads))
    if art == "onnxruntime":
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        o = ort.SessionOptions()
        o.intra_op_num_threads, o.inter_op_num_threads = threads, 1
        sitzung = ort.InferenceSession(modell, o, providers=["CPUExecutionProvider"])
        eingang = sitzung.get_inputs()[0].name
        _KW["rechnen"] = lambda x: sitzung.run(None, {eingang: x})[0]
    else:
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        import cv2
        cv2.setNumThreads(threads)
        netz = cv2.dnn.readNet(modell, "", "", cv2.dnn.ENGINE_NEW)

        def rechnen(x):
            netz.setInput(x)
            return netz.forward()
        _KW["rechnen"] = rechnen
    _KW["lesen"] = ThreadPoolExecutor(threads)


def _merkmale(stapel):
    aus = np.asarray(_KW["rechnen"](stapel), np.float32).reshape(len(stapel), -1)
    if aus.shape[1] != MASSE:
        raise ValueError(f"Modell liefert {aus.shape[1]} statt {MASSE} Werte")
    norm = np.linalg.norm(aus, axis=1, keepdims=True)
    return aus / np.where(norm > 0, norm, 1)


def _probe(modell, art):
    """Modell laden und einmal mit einem grauen Bild rechnen: Laufzeit und Modell passen zusammen (512 Werte).
    Als gewöhnliche Aufgabe, nicht als Initializer – so landet ein Fehler still beim Aufrufer statt im Terminal."""
    _kw_init(modell, art, 1)
    return _merkmale(np.zeros((1, 3, GROESSE, GROESSE), np.float32)).shape


def _quelle(a):
    """Vorschaubild statt Original, wenn es eins gibt und es groß genug ist – liest 50 statt 4000 KB, das zählt bei
    einer externen Festplatte. a: (rel, pfad, groesse, mtime[, Vorschaubild])."""
    if len(a) > 4 and a[4]:
        try:
            with Image.open(a[4]) as t:
                if min(t.size) >= GROESSE:
                    return a[4]
        except OSError:
            pass
    return a[1]


def _kw_job(auftraege):
    """[(rel, pfad, groesse, mtime[, Vorschaubild])] -> [(rel, groesse, mtime, Merkmal als float16-Bytes oder None,
    Fehler oder None)]."""
    def lesen(a):
        quelle = _quelle(a)
        try:
            return vorbereiten(quelle), None
        except Exception as fehler:
            if quelle != a[1]:  # Vorschaubild kaputt: das Original versuchen
                try:
                    return vorbereiten(a[1]), None
                except Exception as f:
                    fehler = f
            return None, f"{type(fehler).__name__}: {fehler}"[:200]

    gelesen = list(_KW["lesen"].map(lesen, auftraege))
    fehler = {i: f for i, (_, f) in enumerate(gelesen) if f}
    ok = [i for i, (x, _) in enumerate(gelesen) if x is not None]
    merkmal = {}
    if ok:
        stapel = np.stack([gelesen[i][0] for i in ok])
        try:
            werte = _merkmale(stapel)
        except Exception:  # ganzer Stapel geht nicht: einzeln, damit nur das schuldige Foto fehlt
            werte = []
            for k in range(len(ok)):
                try:
                    werte.append(_merkmale(stapel[k:k + 1])[0])
                except Exception as f:
                    werte.append(None)
                    fehler[ok[k]] = f"{type(f).__name__}: {f}"[:200]
        for k, i in enumerate(ok):
            if werte[k] is not None:
                merkmal[i] = np.asarray(werte[k], np.float32).astype(np.float16).tobytes()
    return [(a[0], a[2], a[3], merkmal.get(i), fehler.get(i)) for i, a in enumerate(auftraege)]


# ---- Suche ----
class KiSuche:
    """Die Merkmale aller Fotos im Speicher (float16, 1 KB je Foto) und die Suche nach den ähnlichsten.
    stand zählt der Indexer nach jedem Schreiben hoch; dann liest die nächste Suche die Merkmale neu."""

    def __init__(self, index):
        self.index = index
        self.stand = 0
        self._lock = threading.Lock()
        self._daten = None  # (stand, [pfad], Matrix, {pfad: Zeile})

    def daten(self):
        with self._lock:
            if self._daten is None or self._daten[0] != self.stand:
                stand = self.stand
                zeilen = [z for z in self.index.q("SELECT pfad, emb FROM ki WHERE emb IS NOT NULL")
                          if len(z[1]) == 2 * MASSE]
                matrix = (np.frombuffer(b"".join(z[1] for z in zeilen), np.float16).reshape(len(zeilen), MASSE)
                          if zeilen else np.zeros((0, MASSE), np.float16))
                pfade = [z[0] for z in zeilen]
                self._daten = (stand, pfade, matrix, {p: i for i, p in enumerate(pfade)})
            return self._daten[1:]

    def hat(self, rel):
        return rel in self.daten()[2]

    def aehnliche(self, rel, anzahl=150, minimum=0.72, ohne=()):
        """Die Fotos, die rel am ähnlichsten sind: [(pfad, Ähnlichkeit 0–1)] absteigend, nur ab minimum, ohne rel
        selbst und ohne die Pfade in ohne. None, wenn rel noch kein Merkmal hat."""
        pfade, matrix, pos = self.daten()
        i = pos.get(rel)
        if i is None:
            return None
        v = matrix[i].astype(np.float32)
        werte = np.empty(len(pfade), np.float32)
        for a in range(0, len(pfade), 16384):  # stückweise in float32, so bleibt der Speicher klein
            werte[a:a + 16384] = matrix[a:a + 16384].astype(np.float32) @ v
        werte[i] = -2.0
        for p in ohne:
            if p in pos:
                werte[pos[p]] = -2.0
        k = min(len(werte), max(1, anzahl))
        beste = np.argpartition(-werte, k - 1)[:k]
        beste = beste[np.argsort(-werte[beste], kind="stable")]
        return [(pfade[j], float(min(1.0, werte[j]))) for j in beste.tolist() if werte[j] >= minimum]
