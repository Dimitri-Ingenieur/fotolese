"""fotolese.sort.bild – Graustufen, Wahrnehmungs-Hashes (pHash/dHash) und Analyse.

analyse_parallel verteilt analysiere() auf einen Prozess-Pool. _SLOTS/_SLOT_NR
merken je Prozess, welche Datei gerade läuft, damit nach einem Absturz der
Auslöser benannt werden kann.
"""
import multiprocessing as mp
import os
import signal
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

import numpy as np
from PIL import Image, ImageFile

from fotolese.sort.konst import DRAFT, _DREHUNG
from fotolese.sort.exif import _exif_meta


def _dct_matrix(n):
    k = np.arange(n)[:, None]
    x = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
    m[0] /= np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)


def _bits_zu_int(bits):
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


def _hashes(grau):
    """pHash (DCT 32x32 -> 8x8) und dHash (9x8), je 64 Bit, plus Kontrast (Std.-Abw.)."""
    a = np.asarray(grau.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    c = _DCT32 @ a @ _DCT32.T
    tief = c[:8, :8]
    ph = _bits_zu_int((tief > np.median(tief)).ravel())
    b = np.asarray(grau.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    dh = _bits_zu_int((b[:, 1:] > b[:, :-1]).ravel())
    return ph, dh, float(a.std())


def _grau(img):
    """Beliebigen Pillow-Modus in ein neues 8-Bit-Graustufenbild wandeln."""
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I", "F"):
        a = np.asarray(img, dtype=np.float32)
        hoch = float(a.max()) if a.size else 0.0
        if hoch > 255:
            a = a * (255.0 / hoch)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        weiss = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(weiss, rgba).convert("L")
    if img.mode == "L":
        return img.copy()
    if img.mode in ("1", "P", "RGB"):
        return img.convert("L")
    return img.convert("RGB").convert("L")  # CMYK, YCbCr, LAB, ...

def _lade_bild(pfad):
    with Image.open(pfad) as img:
        meta = _exif_meta(img)
        if img.format in ("JPEG", "MPO"):
            img.draft("L", DRAFT)
        img.load()
        return _grau(img), meta


def analysiere(pfad):
    """Liste [pHash, dHash, std, t_serie, t_exif, kamera, hinweis] oder Fehlertext (str)."""
    from fotolese.sort.nef import _lade_nef  # lokal: vermeidet Importzyklus bild <-> nef
    ext = os.path.splitext(pfad)[1].lower()
    hinweis = ""
    try:
        for versuch in (0, 1):
            ImageFile.LOAD_TRUNCATED_IMAGES = versuch == 1
            try:
                grau, meta = _lade_nef(pfad) if ext == ".nef" else _lade_bild(pfad)
                break
            except OSError as e:
                text = str(e).lower()
                if versuch == 0 and ("truncated" in text or "broken data stream" in text):
                    hinweis = "abgeschnitten"
                    continue
                raise
        drehung = _DREHUNG.get(meta["orient"])
        if drehung is not None:
            grau = grau.transpose(drehung)
        ph, dh, std = _hashes(grau)
        return [ph, dh, round(std, 3), meta["t_serie"], meta["t_exif"], meta["kamera"], hinweis]
    except Exception as e:
        return f"{type(e).__name__}: {e}"[:200]
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = False


_SLOTS = None
_SLOT_NR = 0


def _worker_init(slots=None, zaehler=None):
    global _SLOTS, _SLOT_NR
    warnings.simplefilter("ignore")
    Image.MAX_IMAGE_PIXELS = None
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if slots is not None:
        with zaehler.get_lock():
            _SLOT_NR = zaehler.value % len(slots)
            zaehler.value += 1
        _SLOTS = slots


def _job(auftrag):
    i, pfad = auftrag
    if _SLOTS is not None:
        _SLOTS[_SLOT_NR] = i          # merkt sich, welche Datei gerade läuft
    res = analysiere(pfad)
    if _SLOTS is not None:
        _SLOTS[_SLOT_NR] = -1
    return i, res


def _runde(auftraege, jobs, ablegen, fertig):
    """Ein Prozess-Pool für die Aufträge. Stürzt ein Prozess ab (z. B. LibRaw an einer
    kaputten Datei), wird nicht gewartet, sondern gemeldet, welche Dateien gerade liefen."""
    slots = mp.Array("q", [-1] * jobs, lock=False)
    zaehler = mp.Value("i", 0)
    ex = ProcessPoolExecutor(jobs, initializer=_worker_init, initargs=(slots, zaehler))
    futures = [ex.submit(_job, a) for a in auftraege]
    try:
        for f in as_completed(futures):
            i, res = f.result()
            if i not in fertig:
                ablegen(i, res)
        return False, set()
    except BrokenProcessPool:
        for f in futures:
            if f.done() and not f.cancelled() and f.exception() is None:
                i, res = f.result()
                if i not in fertig:
                    ablegen(i, res)
        return True, {v for v in slots if v >= 0} - fertig
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def analyse_parallel(auftraege, jobs, ablegen):
    fertig = set()

    def _ablegen(i, res):
        fertig.add(i)
        ablegen(i, res)

    rest, verdacht = list(auftraege), []
    while rest:
        gebrochen, laufend = _runde(rest, jobs, _ablegen, fertig)
        if gebrochen and not laufend:
            laufend = {a[0] for a in rest} - fertig
        verdacht += [a for a in rest if a[0] in laufend]
        rest = [a for a in rest if a[0] not in fertig and a[0] not in laufend]
    for a in verdacht:  # Verdächtige einzeln prüfen, um den Auslöser zu finden
        if a[0] in fertig:
            continue
        gebrochen, _ = _runde([a], 1, _ablegen, fertig)
        if gebrochen and a[0] not in fertig:
            _ablegen(a[0], "Absturz beim Lesen – Datei vermutlich defekt")
