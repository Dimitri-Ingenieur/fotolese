"""fotolese.web.gesichter – Gesichter erkennen (YuNet/SFace) und Merkmale (Embeddings) berechnen.

_IW hält je Worker-Prozess den Erkenner (GPU oder CPU, siehe gpu). _ueberlappung/_ueberdeckung sind
hier zuhause, damit index diese Geometrie-Helfer nutzen kann, ohne einen Importzyklus.
"""
import math
import os
import re
import signal
import threading
import warnings

import numpy as np
from PIL import Image, ImageOps

from fotolese import gemein
from fotolese.web.konst import THUMB
from fotolese.web.bild import _draft_groesse, _rgb, als_jpeg, atomar_schreiben, thumb_schluessel
from fotolese.web.gpu import Erkenner


def _ueberlappung(a, b):
    """Überlappung zweier Kästen (x, y, w, h) als Schnitt/Vereinigung (IoU), 0–1."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    schnitt = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    vereinigt = a[2] * a[3] + b[2] * b[3] - schnitt
    return schnitt / vereinigt if vereinigt > 0 else 0.0


def _ueberdeckung(a, b):
    """Anteil des kleineren Kastens, der im anderen liegt (1 = ganz darin) – erkennt doppelte Kästen
    um dasselbe Gesicht, z. B. einmal mit und einmal ohne Mütze."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    kleiner = min(a[2] * a[3], b[2] * b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1) / kleiner if kleiner > 0 else 0.0


_IW = {}


def _iw_init(yunet, sface, erkenn_px, min_px, vorschau, score=0.5, gegenprobe=0.8, wahl=None, gpu_jobs=0,
             zaehler=None):
    warnings.simplefilter("ignore")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _IW.update(erkenn_px=erkenn_px, min_px=min_px, vorschau=vorschau, gegenprobe=gegenprobe, erk=None)
    if yunet and sface:
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        import cv2
        cv2.setNumThreads(1)
        _IW["cv2"] = cv2
        if wahl and zaehler is not None:  # nur die ersten gpu_jobs Prozesse rechnen auf der GPU (GPU-Speicher)
            with zaehler.get_lock():
                nr, zaehler.value = zaehler.value, zaehler.value + 1
            wahl = wahl if nr < gpu_jobs else None
        _IW["erk"] = Erkenner((yunet, sface), score, wahl)


def _gegenprobe(cv2, erk, src, f, faktor):
    """Gesicht im vergrößerten Ausschnitt noch einmal suchen. Echte Gesichter werden in beiden Maßstäben
    sicher gefunden (Test: 0,77–0,95), Muster wie Buchstaben oder Fell nicht (meist 0). Rückgabe: Sicherheit."""
    x, y, w, h = (float(v) * faktor for v in f[:4])
    seite, cx, cy = 2.2 * max(w, h), x + w / 2, y + h / 2
    hoehe, breite = src.shape[:2]
    x0, y0 = int(max(0, cx - seite / 2)), int(max(0, cy - seite / 2))
    x1, y1 = int(min(breite, cx + seite / 2)), int(min(hoehe, cy + seite / 2))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    stueck = src[y0:y1, x0:x1]
    k = 320 / max(stueck.shape[:2])
    klein = cv2.resize(stueck, (max(1, round(stueck.shape[1] * k)), max(1, round(stueck.shape[0] * k))),
                       interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    treffer = erk.erkennen(klein)
    beste = 0.0
    for q in (treffer if treffer is not None else []):
        if _ueberlappung((x, y, w, h), (x0 + q[0] / k, y0 + q[1] / k, q[2] / k, q[3] / k)) > 0.3:
            beste = max(beste, float(q[14]))
    return beste


def _exif_zeit(ex, sub):
    for roh in (sub.get(0x9003), sub.get(0x9004), ex.get(0x0132)):
        s = (roh.decode("ascii", "ignore") if isinstance(roh, bytes) else str(roh or "")).replace("\x00", "").strip()
        m = re.match(r"((?:19|20)\d\d)[:\-](\d\d)[:\-](\d\d)[ T](\d\d):(\d\d):(\d\d)", s)
        if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return None

def _datum_aus_name(name):
    """Fallback ohne EXIF: Datum im Dateinamen (siehe fotolese.gemein) als 'JJJJ-MM-TT hh:mm:ss'."""
    teile = gemein.datum_teile_aus_name(name)
    return None if teile is None else "{}-{}-{} {}:{}:{}".format(*teile)


def _exif_gps(ex):
    try:
        g = ex.get_ifd(0x8825)
    except Exception:
        return None
    if not g:
        return None

    def grad(werte, ref):
        try:
            d, m, s = (float(x) for x in werte)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        v = d + m / 60 + s / 3600
        if math.isnan(v):
            return None
        ref = ref.decode("ascii", "ignore") if isinstance(ref, bytes) else str(ref or "")
        return -v if ref.strip().upper()[:1] in ("S", "W") else v

    lat, lon = grad(g.get(2), g.get(1)), grad(g.get(4), g.get(3))
    if lat is None or lon is None or (abs(lat) < 1e-6 and abs(lon) < 1e-6):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 6), round(lon, 6)


def _iw_job(auftrag):
    rel, pfad, groesse, mt, gesichter_an = auftrag
    erg = {"rel": rel, "groesse": groesse, "mtime": mt, "breite": None, "hoehe": None, "zeit": None,
           "gps": None, "kamera": None, "gesichter": None, "fehler": None, "rechner": None, "rueckfall": None}
    try:
        with Image.open(pfad) as img:
            ex = img.getexif()
            try:
                sub = ex.get_ifd(0x8769)
            except Exception:
                sub = {}
            erg["zeit"] = _exif_zeit(ex, sub) or _datum_aus_name(os.path.basename(pfad))
            erg["gps"] = _exif_gps(ex)
            modell = ex.get(0x0110)
            erg["kamera"] = str(modell).replace("\x00", "").strip() or None if modell else None
            o = ex.get(0x0112, 1)
            w, h = img.size
            erg["breite"], erg["hoehe"] = (h, w) if o in (5, 6, 7, 8) else (w, h)
            if not (gesichter_an and _IW.get("erk")):
                return erg
            if img.format in ("JPEG", "MPO"):
                img.draft("RGB", _draft_groesse(img.width, img.height, _IW["erkenn_px"]))
            img.load()
            bild = _rgb(ImageOps.exif_transpose(img))
        if _IW["vorschau"]:  # Vorschaubild gleich mit anlegen – spart später einen Lesevorgang
            datei = os.path.join(_IW["vorschau"], *(lambda k: (k[:2], k + ".jpg"))(thumb_schluessel(pfad, groesse, mt)))
            if not os.path.exists(datei):
                try:
                    atomar_schreiben(datei, als_jpeg(bild.copy(), THUMB, 80))
                except OSError:
                    pass
        erkenn = bild
        if max(bild.size) > _IW["erkenn_px"]:
            erkenn = bild.copy()
            erkenn.thumbnail((_IW["erkenn_px"], _IW["erkenn_px"]), Image.Resampling.LANCZOS)
        cv2, erk = _IW["cv2"], _IW["erk"]
        a = cv2.cvtColor(np.asarray(erkenn), cv2.COLOR_RGB2BGR)
        bh, bw = a.shape[:2]
        treffer = erk.erkennen(a)
        s_d = bild.width / bw                                   # dekodiertes Bild : Suchbild
        s_o = max(s_d, (erg["breite"] or bild.width) / bw)      # Original : Suchbild
        quellen = {"erkenn": a}

        def quelle(art):  # Bild für die Merkmale, je Bild höchstens einmal erzeugt
            if art not in quellen:
                if art == "bild":
                    quellen[art] = cv2.cvtColor(np.asarray(bild), cv2.COLOR_RGB2BGR)
                else:
                    with Image.open(pfad) as voll:
                        voll.load()
                        quellen[art] = cv2.cvtColor(np.asarray(_rgb(ImageOps.exif_transpose(voll))), cv2.COLOR_RGB2BGR)
            return quellen[art]

        gefunden = []
        for f in (treffer if treffer is not None else []):
            x, y, fw, fh, score = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[14])
            groesse = min(fw, fh) * s_o  # Gesichtsgröße im Original
            if groesse < _IW["min_px"]:
                continue
            # Merkmale aus möglichst hoher Auflösung – kleine Gesichter (Gruppenfotos) aus dem Original
            if min(fw, fh) * s_d >= 96 or s_o <= s_d * 1.01:
                art, faktor = ("erkenn", 1.0) if s_d <= 1.001 else ("bild", s_d)
            else:
                art, faktor = "voll", s_o
            if _IW["gegenprobe"] > 0 and _gegenprobe(cv2, erk, quelle(art), f, faktor) < _IW["gegenprobe"]:
                continue  # nur in einem Maßstab gefunden: wahrscheinlich Muster, kein Gesicht
            g = f.copy()
            g[:14] *= faktor
            merkmal = erk.merkmal(quelle(art), g)
            norm = float(np.linalg.norm(merkmal))
            if norm <= 0:
                continue
            gefunden.append((max(x, 0) / bw, max(y, 0) / bh, fw / bw, fh / bh, score, round(groesse),
                             (merkmal / norm).tobytes()))
        def doppelt(k, b):  # zwei Kästen um dasselbe Gesicht (z. B. Stirn+Augen und Augen+Kinn)
            u = _ueberdeckung(k[:4], b[:4])
            return u >= 0.5 or (u >= 0.2 and float(np.frombuffer(k[6], np.float32) @ np.frombuffer(b[6], np.float32)) >= 0.6)

        behalten = []  # den sichereren Kasten behalten
        for kandidat in sorted(gefunden, key=lambda k: -k[4]):
            if not any(doppelt(kandidat, k) for k in behalten):
                behalten.append(kandidat)
        erg["gesichter"] = behalten
        erg["rechner"], erg["rueckfall"] = ("gpu" if erk.gpu else "cpu"), erk.rueckfall
    except Exception as fehler:
        erg["fehler"] = f"{type(fehler).__name__}: {fehler}"[:200]
    return erg


class GesichtsSucher:
    """Sucht ein Gesicht an einer angeklickten Stelle – für Gesichter, die der Index übersehen hat.
    Kleines Fenster zuerst (das Gesicht unter dem Klick), großzügige Schwelle, Merkmale aus voller Auflösung."""

    def __init__(self, modelle, wahl=lambda: None):
        self.modelle = modelle
        self.wahl = wahl  # liefert die aktuelle GPU-Wahl des Indexers (None = CPU)
        self.lock = threading.Lock()
        self.erk = self._fuer = None

    def suchen(self, pfad, x, y):
        with self.lock:
            wahl = self.wahl()
            if self.erk is None or wahl is not self._fuer:  # erst CPU, nach der GPU-Prüfung die gewählte GPU
                self.erk, self._fuer = Erkenner(self.modelle, 0.5, wahl), wahl
            cv2 = self.erk.cv2
            with Image.open(pfad) as img:
                img.load()
                bild = _rgb(ImageOps.exif_transpose(img))
            W, H = bild.size
            cx, cy = x * W, y * H
            for anteil in (0.12, 0.35, 1.0):
                seite = max(48, round(min(W, H) * anteil))
                x0 = int(min(max(cx - seite / 2, 0), max(W - seite, 0)))
                y0 = int(min(max(cy - seite / 2, 0), max(H - seite, 0)))
                stueck = bild.crop((x0, y0, min(W, x0 + seite), min(H, y0 + seite)))
                f = 640 / max(stueck.size)
                klein = stueck.resize((max(1, round(stueck.width * f)), max(1, round(stueck.height * f))),
                                      Image.Resampling.LANCZOS)
                a = cv2.cvtColor(np.asarray(klein), cv2.COLOR_RGB2BGR)
                treffer = self.erk.erkennen(a)
                bester = None
                for t in (treffer if treffer is not None else []):
                    fx, fy, fw, fh = x0 + t[0] / f, y0 + t[1] / f, t[2] / f, t[3] / f
                    if (fx - 0.15 * fw <= cx <= fx + 1.15 * fw and fy - 0.15 * fh <= cy <= fy + 1.15 * fh
                            and (bester is None or t[14] > bester[14])):
                        bester = t
                if bester is None:
                    continue
                g = bester.copy()
                g[:14] /= f  # Koordinaten im Ausschnitt, volle Auflösung
                merkmal = self.erk.merkmal(cv2.cvtColor(np.asarray(stueck), cv2.COLOR_RGB2BGR), g)
                norm = float(np.linalg.norm(merkmal))
                fx, fy, fw, fh = x0 + float(g[0]), y0 + float(g[1]), float(g[2]), float(g[3])
                return {"kasten": (max(fx, 0) / W, max(fy, 0) / H, fw / W, fh / H), "score": float(bester[14]),
                        "pixel": round(min(fw, fh)), "emb": (merkmal / norm).tobytes() if norm > 0 else None,
                        "groesse": (W, H)}
            return {"kasten": None, "groesse": (W, H)}
