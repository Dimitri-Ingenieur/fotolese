#!/usr/bin/env python3
"""
fotosort.py – Fotos rekursiv einsammeln, ähnliche Bilder gruppieren und in
nummerierte Ordner 0001–9999 verschieben (chronologisch, ein Ordner je Gruppe).

Ähnlich heißt:
  * gleiches Bild in anderer Auflösung, Kompression oder leicht bearbeitet
    (Wahrnehmungs-Hashes pHash + dHash, Abstand <= SCHWELLE)
  * Serienbilder: gleiche Kamera, höchstens SERIE_SEK Sekunden zum Nachbarbild,
    Abstand <= SERIE_SCHWELLE
  * NEF+JPG derselben Aufnahme landen dadurch automatisch im selben Ordner.
  * Zu jedem NEF ohne Kamera-JPG wird ein JPG erzeugt (eingebettete Kamera-Vorschau, verlustfrei,
    mit Datum, GPS und Kamera aus dem NEF) – auch für NEF, die schon im Bestand liegen.

Vorhandener Bestand in AUSGABE/0001…9999 bleibt unangetastet:
  * neue Bilder, die zu einem bestehenden Ordner passen, kommen in diesen Ordner
    (bei mehreren passenden Ordnern in den mit dem ähnlichsten Bild)
  * alle übrigen bekommen neue Ordner ab der höchsten vorhandenen Nummer + 1
  * gibt es den Dateinamen im Zielordner schon, erhält die neue Datei einen
    Laufindex: IMG_0001.JPG -> IMG_0001_1.JPG, IMG_0001_2.JPG …
    (Begleitdateien wie DSC_1.NEF.xmp werden passend mit umbenannt)

Aufruf (Conda):
  conda create -n fotosort -c conda-forge python=3.12 pillow numpy rawpy
  conda activate fotosort
  python fotosort.py EINGABE AUSGABE
  MODUS=test python fotosort.py EINGABE AUSGABE      # nur Plan, nichts bewegen
  MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv

Umgebungsvariablen (Standard in Klammern):
  MODUS           (move)   move | copy | link | test | undo
                           link = Vorschau mit symbolischen Links (nur Linux-Dateisysteme)
  JA              (0)      1 = ohne Rückfrage ausführen
  SCHWELLE        (20)     Bildvergleich: max. Abstand pHash+dHash (0–128)
  SERIE_SEK       (3)      Serienbilder: max. Zeitabstand zum Nachbarbild in Sekunden
  SERIE_SCHWELLE  (36)     Serienbilder: max. Abstand pHash+dHash (0–128)
  EINZELN         (ordner) ordner = jedes Einzelbild eigener Ordner, 0000 = alle in Ordner 0000
  JOBS            (Kerne)  parallele Prozesse; Quelle oder Bestand auf HDD/USB-Platte: z. B. 4
  BEGLEIT         (1)      .xmp/.pp3/.aae-Begleitdateien mitnehmen
  AUFRAEUMEN      (1)      leere Quellordner nach dem Verschieben entfernen
  NEF_JPG         (1)      0 = keine JPG aus NEF erzeugen
  DUPLIKATE       (1)      inhaltsgleiche Dateien (SHA-256) nur einmal: Bilder, die es im Bestand schon gibt
                           oder die in der Eingabe mehrfach vorkommen, werden übersprungen (bleiben liegen)
  FORTSCHRITT_JSON (0)     1 = Fortschritt als Zeilen „#FS {json}“ auf stdout (für bestof.py)
  CACHE           (~/.cache/fotosort/cache.sqlite3)  Pfad oder 0 = aus
                           merkt sich auch die Bilder im Bestand: Folgeläufe lesen sie nicht neu

Pakete: pillow numpy rawpy (rawpy optional, für NEF empfohlen; Conda: Kanal conda-forge)
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")  # 32 Prozesse x 32 BLAS-Threads vermeiden

import atexit
import csv
import errno
import hashlib
import io
import json
import re
import shutil
import signal
import sqlite3
import stat
import sys
import time
import warnings
import multiprocessing as mp
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime

import numpy as np
from PIL import Image, ImageFile

try:
    import rawpy
except ImportError:
    rawpy = None

VERSION = "1.3"
HASH_VERSION = "1"
BILD_EXT = {".jpg", ".jpeg", ".png", ".nef"}
BEGLEIT_EXT = {".xmp", ".pp3", ".aae"}
SKIP_ORDNER = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found"}
WINDOWS_FS = {"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk", "cifs", "smb3"}
KRITISCH = {errno.ENOSPC, errno.EIO, errno.EROFS, errno.ENODEV, errno.ENXIO, errno.EDQUOT}
MAX_ORDNER = 9999
FLACH_STD = 1.0          # praktisch einfarbige Bilder nicht per Hash verknüpfen
DRAFT = (256, 256)       # JPEG nur in 1/2, 1/4 oder 1/8 Auflösung dekodieren
SYNC_BYTES = 1 << 30     # nach spätestens 1 GiB Kopie: sync, dann Quellen löschen
SYNC_DATEIEN = 500


# ---------------------------------------------------------------- Hilfen
def _env(name, standard, typ=str):
    roh = os.environ.get(name, "").strip()
    if roh == "":
        return standard
    try:
        return typ(roh)
    except ValueError:
        sys.exit(f"Fehler: {name}={roh!r} ist ungültig.")


def zahl(n):
    return f"{n:,}".replace(",", ".")


def gb(b):
    if b < 1e9:
        return f"{b / 1e6:.0f} MB" if b >= 1e6 else f"{b / 1e3:.0f} kB"
    return f"{b / 1e9:.1f}".replace(".", ",") + " GB"


def dauer(s):
    s = int(s)
    if s >= 3600:
        return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d} h"
    return f"{s // 60}:{s % 60:02d} min"


def info(text=""):
    print(text, flush=True)


JSON_FORTSCHRITT = os.environ.get("FORTSCHRITT_JSON", "").strip() == "1"


class Fortschritt:
    def __init__(self, titel, gesamt, einheit="Dateien"):
        self.titel, self.gesamt, self.einheit = titel, gesamt, einheit
        self.start = self.zuletzt = time.time()
        self.tty = sys.stderr.isatty()
        self.naechste_prozent = 10

    def melden(self, fertig, zusatz="", ende=False):
        jetzt = time.time()
        if JSON_FORTSCHRITT:  # für bestof.py: eine Zeile je halbe Sekunde
            if ende or jetzt - self.zuletzt >= 0.5:
                self.zuletzt = jetzt
                print("#FS " + json.dumps({"titel": self.titel, "fertig": fertig, "gesamt": self.gesamt,
                                           "zusatz": zusatz.strip(" ·"), "ende": ende}), flush=True)
            return
        if not ende and jetzt - self.zuletzt < 1.0:
            return
        self.zuletzt = jetzt
        anteil = fertig / self.gesamt if self.gesamt else 1.0
        lauf = jetzt - self.start
        rest = lauf / anteil - lauf if anteil > 0 else 0
        zeile = (f"{self.titel}: {zahl(fertig)}/{zahl(self.gesamt)} {self.einheit} "
                 f"({anteil * 100:.0f} %){zusatz}" + ("" if ende else f" · Rest ~{dauer(rest)}"))
        if self.tty:
            sys.stderr.write("\r\033[K" + zeile + ("\n" if ende else ""))
            sys.stderr.flush()
        elif ende or anteil * 100 >= self.naechste_prozent:
            self.naechste_prozent = int(anteil * 10) * 10 + 10
            sys.stderr.write(zeile + "\n")


# ---------------------------------------------------------------- Bildanalyse
def _dct_matrix(n):
    k = np.arange(n)[:, None]
    x = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
    m[0] /= np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)
_DREHUNG = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
            4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
            6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
            8: Image.Transpose.ROTATE_90}
_EPOCHE = datetime(1970, 1, 1)


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


def _text(wert):
    if wert is None:
        return ""
    if isinstance(wert, bytes):
        wert = wert.decode("utf-8", "ignore")
    return str(wert).replace("\x00", "").strip()


def _zeit(roh, subsek=None):
    s = _text(roh)
    if len(s) < 19:
        return None
    try:
        dt = datetime.strptime(s[:10].replace("-", ":") + " " + s[11:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    if not 1900 < dt.year < 2200:
        return None
    t = (dt - _EPOCHE).total_seconds()
    ziffern = "".join(ch for ch in _text(subsek) if ch.isdigit())[:6]
    if ziffern:
        t += int(ziffern) / 10 ** len(ziffern)
    return t


def _zeit_aus_name(name):
    """Ohne EXIF: Datum im Dateinamen (IMG-20230714-WA0003.jpg, 20230714_103200.jpg, Screenshot_2023-07-14…)."""
    m = re.search(r"(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
                  r"(?:[-_. T]?([01]\d|2[0-3])[-_.:]?([0-5]\d)[-_.:]?([0-5]\d))?(?!\d)", name)
    if not m:
        return None
    return _zeit(f"{m.group(1)}:{m.group(2)}:{m.group(3)} {m.group(4) or '12'}:{m.group(5) or '00'}:{m.group(6) or '00'}")


def _leer_meta():
    return {"orient": 1, "t_serie": None, "t_exif": None, "kamera": ""}


def _exif_meta(quelle):
    meta = _leer_meta()
    try:
        ex = quelle.getexif() if hasattr(quelle, "getexif") else quelle
        try:
            sub = ex.get_ifd(0x8769)
        except Exception:
            sub = {}
        o = ex.get(0x0112, 1)
        meta["orient"] = o if isinstance(o, int) and 1 <= o <= 8 else 1
        t_orig = _zeit(sub.get(0x9003), sub.get(0x9291))
        t_digi = _zeit(sub.get(0x9004), sub.get(0x9292))
        t_datei = _zeit(ex.get(0x0132), sub.get(0x9290))
        meta["t_serie"] = t_orig if t_orig is not None else t_digi
        meta["t_exif"] = next((t for t in (t_orig, t_digi, t_datei) if t is not None), None)
        modell = _text(ex.get(0x0110))
        if modell:
            meta["kamera"] = "|".join((_text(ex.get(0x010F)), modell, _text(sub.get(0xA431))))
    except Exception:
        pass
    return meta


def _lade_bild(pfad):
    with Image.open(pfad) as img:
        meta = _exif_meta(img)
        if img.format in ("JPEG", "MPO"):
            img.draft("L", DRAFT)
        img.load()
        return _grau(img), meta


def _grau_aus_vorschau(pfad):
    """Ohne rawpy: größte eingebettete JPEG-Vorschau im NEF suchen."""
    with open(pfad, "rb") as f:
        daten = f.read()
    kandidaten = []
    pos = daten.find(b"\xff\xd8\xff")
    while pos != -1 and len(kandidaten) < 64:
        try:
            with Image.open(io.BytesIO(daten[pos:pos + (1 << 18)])) as k:
                w, h = k.size
                if k.format == "JPEG" and 64 <= min(w, h) and max(w, h) <= 20000:
                    kandidaten.append((w * h, pos))
        except Exception:
            pass
        pos = daten.find(b"\xff\xd8\xff", pos + 3)
    for _, pos in sorted(kandidaten, reverse=True):
        try:
            with Image.open(io.BytesIO(daten[pos:])) as v:
                v.draft("L", DRAFT)
                v.load()
                return _grau(v)
        except Exception:
            continue
    raise OSError("keine lesbare Vorschau im NEF gefunden")


def _lade_nef(pfad):
    meta = None
    try:
        with Image.open(pfad) as tif:
            meta = _exif_meta(tif)
    except Exception:
        pass
    if meta is None or (meta["t_exif"] is None and not meta["kamera"]):
        try:
            with open(pfad, "rb") as f:
                kopf = f.read(1 << 20)
            ex = Image.Exif()
            ex.load(kopf)
            meta = _exif_meta(ex)
        except Exception:
            meta = meta or _leer_meta()
    grau = None
    if rawpy is not None:
        try:
            with rawpy.imread(pfad) as raw:
                flip = raw.sizes.flip
                try:
                    th = raw.extract_thumb()
                    if th.format == rawpy.ThumbFormat.JPEG:
                        with Image.open(io.BytesIO(th.data)) as v:
                            v.draft("L", DRAFT)
                            v.load()
                            grau = _grau(v)
                    else:
                        grau = _grau(Image.fromarray(th.data))
                except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
                    grau = _grau(Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True)))
                if meta["orient"] == 1 and flip in (3, 5, 6):
                    meta["orient"] = {3: 3, 5: 8, 6: 6}[flip]
        except Exception:
            grau = None
    if grau is None:
        grau = _grau_aus_vorschau(pfad)
    return grau, meta


# ---------------------------------------------------------------- JPG aus NEF
_EXIF_IFD0 = (0x010F, 0x0110, 0x0112, 0x0131, 0x0132, 0x013B, 0x8298)
_EXIF_SUB = (0x829A, 0x829D, 0x8822, 0x8827, 0x8832, 0x9003, 0x9004, 0x9010, 0x9011, 0x9012, 0x9204,
             0x9207, 0x9209, 0x920A, 0x9290, 0x9291, 0x9292, 0xA402, 0xA403, 0xA405, 0xA431, 0xA432,
             0xA433, 0xA434)


def _jpeg_ende(daten, start):
    """Ende eines eingebetteten JPEG-Datenstroms (nach EOI) finden."""
    pos = start + 2
    while pos + 4 <= len(daten) and daten[pos] == 0xFF:
        marker = daten[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        laenge = int.from_bytes(daten[pos + 2:pos + 4], "big")
        pos += 2 + laenge
        if marker == 0xDA:  # Bilddaten: FF D9 kann darin nicht unmaskiert vorkommen
            ende = daten.find(b"\xff\xd9", pos)
            return len(daten) if ende == -1 else ende + 2
    return len(daten)


def _nef_jpeg_bytes(pfad):
    """Größte eingebettete Kamera-Vorschau als JPEG-Bytes + Orientierung laut LibRaw (0 = unbekannt)."""
    if rawpy is not None:
        try:
            with rawpy.imread(pfad) as raw:
                flip = {3: 3, 5: 8, 6: 6}.get(raw.sizes.flip, 0)
                th = raw.extract_thumb()
                if th.format == rawpy.ThumbFormat.JPEG:
                    return bytes(th.data), flip
                b = io.BytesIO()
                Image.fromarray(th.data).save(b, "JPEG", quality=95)
                return b.getvalue(), flip
        except Exception:
            pass
    with open(pfad, "rb") as f:
        daten = f.read()
    kandidaten = []
    pos = daten.find(b"\xff\xd8\xff")
    while pos != -1 and len(kandidaten) < 64:
        try:
            with Image.open(io.BytesIO(daten[pos:pos + (1 << 18)])) as k:
                if k.format == "JPEG" and 64 <= min(k.size) and max(k.size) <= 20000:
                    kandidaten.append((k.size[0] * k.size[1], pos))
        except Exception:
            pass
        pos = daten.find(b"\xff\xd8\xff", pos + 3)
    for _, pos in sorted(kandidaten, reverse=True):
        stueck = daten[pos:_jpeg_ende(daten, pos)]
        try:
            with Image.open(io.BytesIO(stueck)) as v:
                v.load()
            return stueck, 0
        except Exception:
            continue
    raise OSError("keine Vorschau im NEF gefunden")


def _exif_auswahl(quelle):
    """Datum, Kamera, Belichtung, Orientierung und GPS übernehmen – ohne Herstellerdaten (MakerNote)."""
    neu = Image.Exif()
    for tag in _EXIF_IFD0:
        if tag in quelle:
            neu[tag] = quelle[tag]
    for ifd_tag, erlaubt in ((0x8769, _EXIF_SUB), (0x8825, None)):
        try:
            alt = quelle.get_ifd(ifd_tag)
        except Exception:
            alt = {}
        auswahl = {tag: wert for tag, wert in alt.items() if erlaubt is None or tag in erlaubt}
        if auswahl:
            neu[ifd_tag] = auswahl  # Unter-IFD als dict: funktioniert mit Pillow 10 bis 13
    return neu


def _exif_aus_nef(pfad):
    try:
        with Image.open(pfad) as tif:
            return _exif_auswahl(tif.getexif())
    except Exception:
        pass
    try:
        with open(pfad, "rb") as f:
            kopf = f.read(1 << 20)
        ex = Image.Exif()
        ex.load(kopf)
        return _exif_auswahl(ex)
    except Exception:
        return None


def _jpeg_mit_exif(jpeg, exif_bytes):
    """EXIF als APP1 einsetzen, ohne die Bilddaten neu zu kodieren."""
    if not exif_bytes.startswith(b"Exif\x00\x00"):
        exif_bytes = b"Exif\x00\x00" + exif_bytes
    if jpeg[:2] != b"\xff\xd8" or len(exif_bytes) + 2 > 0xFFFF:
        return jpeg
    pos, app0, rest = 2, [], []
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF:
        marker = jpeg[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker in (0xDA, 0xD9):
            break
        laenge = int.from_bytes(jpeg[pos + 2:pos + 4], "big")
        segment = jpeg[pos:pos + 2 + laenge]
        if marker == 0xE0 and not rest:
            app0.append(segment)
        elif not (marker == 0xE1 and segment[4:10] == b"Exif\x00\x00"):
            rest.append(segment)
        pos += 2 + laenge
    app1 = b"\xff\xe1" + (len(exif_bytes) + 2).to_bytes(2, "big") + exif_bytes
    return b"\xff\xd8" + b"".join(app0) + app1 + b"".join(rest) + jpeg[pos:]


def nef_zu_jpg(nef, ziel):
    """JPG zum NEF anlegen: Kamera-Vorschau verlustfrei übernehmen, dazu Datum, GPS, Kamera und
    Orientierung aus dem NEF. Rückgabe: Dateigröße in Bytes."""
    daten, flip = _nef_jpeg_bytes(nef)
    exif = _exif_aus_nef(nef)
    if exif is not None:
        if flip and 0x0112 not in exif:
            exif[0x0112] = flip
        daten = _jpeg_mit_exif(daten, exif.tobytes())
    tmp = ziel + ".fotosort-tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(daten)
        st = os.stat(nef)
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.rename(tmp, ziel)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return len(daten)


def analysiere(pfad):
    """Liste [pHash, dHash, std, t_serie, t_exif, kamera, hinweis] oder Fehlertext (str)."""
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


# ---------------------------------------------------------------- Cache
class Cache:
    def __init__(self, pfad):
        self.db = None
        if not pfad or pfad == "0":
            return
        try:
            os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
            self.db = sqlite3.connect(pfad)
            self.db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
            v = self.db.execute("SELECT v FROM meta WHERE k='version'").fetchone()
            if v is None or v[0] != HASH_VERSION:
                self.db.execute("DROP TABLE IF EXISTS bilder")
                self.db.execute("INSERT OR REPLACE INTO meta VALUES('version', ?)", (HASH_VERSION,))
            self.db.execute("CREATE TABLE IF NOT EXISTS bilder(pfad BLOB PRIMARY KEY, "
                            "groesse INTEGER, mtime INTEGER, daten TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS pruefsumme(pfad BLOB PRIMARY KEY, "
                            "groesse INTEGER, mtime INTEGER, sha TEXT)")
            self.db.commit()
        except (sqlite3.Error, OSError) as e:
            info(f"Hinweis: Cache nicht nutzbar ({e}) – weiter ohne Cache.")
            self.db = None
        self.offen = 0

    def holen(self, pfad, groesse, mtime):
        if self.db is None:
            return None
        z = self.db.execute("SELECT groesse, mtime, daten FROM bilder WHERE pfad=?",
                            (os.fsencode(pfad),)).fetchone()
        if z and z[0] == groesse and z[1] == mtime:
            return json.loads(z[2])
        return None

    def ablegen(self, pfad, groesse, mtime, daten):
        if self.db is None:
            return
        try:
            self.db.execute("INSERT OR REPLACE INTO bilder VALUES(?,?,?,?)",
                            (os.fsencode(pfad), groesse, mtime, json.dumps(daten)))
            self.offen += 1
            if self.offen >= 200:
                self.db.commit()
                self.offen = 0
        except sqlite3.Error:
            pass

    def sha_holen(self, pfad, groesse, mtime):
        if self.db is None:
            return None
        z = self.db.execute("SELECT groesse, mtime, sha FROM pruefsumme WHERE pfad=?", (os.fsencode(pfad),)).fetchone()
        return z[2] if z and z[0] == groesse and z[1] == mtime else None

    def sha_ablegen(self, pfad, groesse, mtime, sha):
        if self.db is None:
            return
        try:
            self.db.execute("INSERT OR REPLACE INTO pruefsumme VALUES(?,?,?,?)",
                            (os.fsencode(pfad), groesse, mtime, sha))
        except sqlite3.Error:
            pass

    def schliessen(self):
        if self.db is not None:
            try:
                self.db.commit()
                self.db.close()
            except sqlite3.Error:
                pass
            self.db = None


# ---------------------------------------------------------------- Suche
class Datei:
    __slots__ = ("pfad", "groesse", "mtime", "dev", "res", "t_sort", "begleit", "anker")

    def __init__(self, pfad, st, anker=None):
        self.pfad, self.groesse, self.mtime, self.dev = pfad, st.st_size, st.st_mtime_ns, st.st_dev
        self.res = None
        self.t_sort = 0.0
        self.begleit = []  # [(pfad, groesse, dev)]
        self.anker = anker  # Bestand: Ordnername "NNNN", neue Bilder: None

    @property
    def ok(self):
        return isinstance(self.res, list)


def suche_bestand(ausgabe, eingabe_real):
    """Bilder, die schon in AUSGABE/NNNN liegen. Sie werden nie bewegt, sondern dienen als Anker."""
    bestand = []
    try:
        eintraege = sorted(os.scandir(ausgabe), key=lambda e: e.name)
    except OSError:
        return bestand
    for e in eintraege:
        if not (re.fullmatch(r"\d{4}", e.name) and e.is_dir(follow_symlinks=False)):
            continue
        for wurzel, ordner, dateien in os.walk(e.path):
            echt = os.path.realpath(wurzel)
            if echt == eingabe_real or echt.startswith(eingabe_real + os.sep):
                ordner[:] = []
                continue
            ordner[:] = sorted(o for o in ordner if not o.startswith(".") and o not in SKIP_ORDNER)
            for name in sorted(dateien):
                if name.startswith("._") or os.path.splitext(name)[1].lower() not in BILD_EXT:
                    continue
                pfad = os.path.join(wurzel, name)
                try:
                    st = os.lstat(pfad)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    bestand.append(Datei(pfad, st, anker=e.name))
    return bestand


def suche(eingabe, ausgabe_real):
    bilder, begleit, stat_info = [], {}, Counter()

    def fehler(e):
        stat_info["ordner_fehler"] += 1

    for wurzel, ordner, dateien in os.walk(eingabe, onerror=fehler):
        behalten = []
        for o in sorted(ordner):
            voll = os.path.join(wurzel, o)
            if o.startswith(".") or o in SKIP_ORDNER or os.path.realpath(voll) == ausgabe_real:
                stat_info["ordner_uebersprungen"] += 1
                continue
            behalten.append(o)
        ordner[:] = behalten
        for name in sorted(dateien):
            if name.startswith("._"):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in BILD_EXT and ext not in BEGLEIT_EXT:
                continue
            pfad = os.path.join(wurzel, name)
            try:
                st = os.lstat(pfad)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                stat_info["links"] += 1
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if ext in BILD_EXT:
                bilder.append(Datei(pfad, st))
            else:
                begleit.setdefault(wurzel, {})[name.casefold()] = (name, st.st_size, st.st_dev)
    return bilder, begleit, stat_info


def ordne_begleitdateien(bilder, begleit):
    """.xmp/.pp3/.aae dem passenden Bild zuordnen (NEF zuerst, z. B. DSC_1.xmp gehört zum NEF)."""
    vergeben = set()
    reihenfolge = sorted(bilder, key=lambda d: (os.path.dirname(d.pfad),
                                                os.path.splitext(os.path.basename(d.pfad))[0].casefold(),
                                                not d.pfad.lower().endswith(".nef"), d.pfad))
    anzahl = 0
    for d in reihenfolge:
        ordner, name = os.path.split(d.pfad)
        vorhanden = begleit.get(ordner)
        if not vorhanden:
            continue
        stamm = os.path.splitext(name)[0]
        for kandidat in (name + ".xmp", name + ".pp3", stamm + ".xmp", stamm + ".aae"):
            schluessel = (ordner, kandidat.casefold())
            if schluessel in vergeben or kandidat.casefold() not in vorhanden:
                continue
            echt, groesse, dev = vorhanden[kandidat.casefold()]
            vergeben.add(schluessel)
            d.begleit.append((os.path.join(ordner, echt), groesse, dev))
            anzahl += 1
    return anzahl


# ---------------------------------------------------------------- Gruppierung
if hasattr(np, "bitwise_count"):
    def _popcount(x):
        return np.bitwise_count(x)
else:  # numpy < 2.0
    _LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

    def _popcount(x):
        return _LUT[x.view(np.uint8)].reshape(x.shape + (8,)).sum(axis=-1, dtype=np.uint8)


def sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def duplikate_finden(bilder, bestand, cache, jobs):
    """Eingabebilder, deren Inhalt (SHA-256) es schon im Bestand oder weiter vorn in der Eingabe gibt.
    Geprüft werden nur Dateien gleicher Größe – alle anderen können nicht gleich sein.
    Rückgabe: {Eingabepfad: Pfad der gleichen Datei}."""
    bestand_nach_groesse = defaultdict(list)
    for d in bestand:
        bestand_nach_groesse[d.groesse].append(d)
    anzahl_ein = Counter(d.groesse for d in bilder)
    ein = [d for d in bilder if d.groesse in bestand_nach_groesse or anzahl_ein[d.groesse] > 1]
    alt = [b for g in sorted({d.groesse for d in ein}) for b in bestand_nach_groesse.get(g, [])]
    pruefen = ein + alt
    if not pruefen:
        return {}
    shas = {}
    offen = []
    for d in pruefen:
        s = cache.sha_holen(d.pfad, d.groesse, d.mtime)
        if s:
            shas[d.pfad] = s
        else:
            offen.append(d)
    fort = Fortschritt("Prüfsummen", len(offen))
    if offen:
        with ThreadPoolExecutor(max(1, min(jobs, 8))) as ex:
            zukunft = {ex.submit(sha256, d.pfad): d for d in offen}
            for k, f in enumerate(as_completed(zukunft), 1):
                d = zukunft[f]
                try:
                    shas[d.pfad] = f.result()
                    cache.sha_ablegen(d.pfad, d.groesse, d.mtime, shas[d.pfad])
                except OSError:
                    pass
                fort.melden(k)
        fort.melden(len(offen), ende=True)
    bekannt = {}
    for b in alt:
        if b.pfad in shas:
            bekannt.setdefault(shas[b.pfad], b.pfad)
    doppelt = {}
    for d in sorted(ein, key=lambda d: d.pfad):
        s = shas.get(d.pfad)
        if s is None:
            continue
        if s in bekannt:
            doppelt[d.pfad] = bekannt[s]
        else:
            bekannt[s] = d.pfad
    return doppelt


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))
        self.g = [1] * n

    def finde(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def vereinige(self, a, b):
        a, b = self.finde(a), self.finde(b)
        if a == b:
            return False
        if self.g[a] < self.g[b]:
            a, b = b, a
        self.p[b] = a
        self.g[a] += self.g[b]
        return True


def gruppiere(bilder, schwelle, serie_sek, serie_schwelle):
    n = len(bilder)
    uf = UnionFind(n)
    idx = [i for i, d in enumerate(bilder) if d.ok and d.res[2] >= FLACH_STD]
    m = len(idx)
    n_bild = n_serie = 0
    if m > 1:
        ph = np.array([bilder[i].res[0] for i in idx], dtype=np.uint64)
        dh = np.array([bilder[i].res[1] for i in idx], dtype=np.uint64)
        block = max(32, min(4096, 16_000_000 // m))
        for a in range(0, m, block):
            b = min(a + block, m)
            abstand = (_popcount(ph[a:b, None] ^ ph[None, a:]).astype(np.uint16)
                       + _popcount(dh[a:b, None] ^ dh[None, a:]))
            zi, sp = np.nonzero(abstand <= schwelle)
            zi = zi + a
            sp = sp + a
            wahl = sp > zi
            for i, j in zip(zi[wahl].tolist(), sp[wahl].tolist()):
                if uf.vereinige(idx[i], idx[j]):
                    n_bild += 1
    # Serienbilder: gleiche Kamera, zeitlich benachbart, sichtbar ähnlich
    nach_kamera = defaultdict(list)
    for i, d in enumerate(bilder):
        if d.ok and d.res[5] and d.res[3] is not None and d.res[2] >= FLACH_STD:
            nach_kamera[d.res[5]].append(i)
    for liste in nach_kamera.values():
        liste.sort(key=lambda i: (bilder[i].res[3], bilder[i].pfad))
        for k in range(1, len(liste)):
            rk = bilder[liste[k]].res
            j = k - 1
            while j >= 0 and k - j <= 60:
                rj = bilder[liste[j]].res
                if rk[3] - rj[3] > serie_sek:
                    break
                if (rk[0] ^ rj[0]).bit_count() + (rk[1] ^ rj[1]).bit_count() <= serie_schwelle:
                    if uf.vereinige(liste[k], liste[j]):
                        n_serie += 1
                j -= 1
    gruppen = defaultdict(list)
    for i, d in enumerate(bilder):
        if d.ok:
            gruppen[uf.finde(i)].append(d)
    ergebnis = []
    for g in gruppen.values():
        g.sort(key=lambda d: (d.t_sort, d.pfad))
        ergebnis.append(g)
    ergebnis.sort(key=lambda g: (g[0].t_sort, g[0].pfad))
    return ergebnis, n_bild, n_serie


def finde_anker(gruppen, bestand, schwelle, serie_sek, serie_schwelle):
    """Für jede neue Gruppe den bestehenden Ordner mit dem ähnlichsten Bild suchen
    (Bildvergleich <= SCHWELLE oder Serie: gleiche Kamera, <= SERIE_SEK, <= SERIE_SCHWELLE).
    Bestandsordner werden dabei nie verändert oder zusammengelegt.
    Rückgabe: Liste parallel zu gruppen mit Ordnername oder None."""
    anker = [None] * len(gruppen)
    alt = [d for d in bestand if d.ok and d.res[2] >= FLACH_STD]
    neu = [(gi, d) for gi, g in enumerate(gruppen) for d in g if d.res[2] >= FLACH_STD]
    if not alt or not neu:
        return anker
    bestes = {}  # Position in neu -> (abstand, ordner, pfad)

    def merken(pos, abstand, d_alt):
        kandidat = (abstand, d_alt.anker, d_alt.pfad)
        if pos not in bestes or kandidat < bestes[pos]:
            bestes[pos] = kandidat

    ph_a = np.array([d.res[0] for d in alt], dtype=np.uint64)
    dh_a = np.array([d.res[1] for d in alt], dtype=np.uint64)
    ph_n = np.array([d.res[0] for _, d in neu], dtype=np.uint64)
    dh_n = np.array([d.res[1] for _, d in neu], dtype=np.uint64)
    block = max(32, min(4096, 16_000_000 // len(alt)))
    for a in range(0, len(neu), block):
        b = min(a + block, len(neu))
        abstand = (_popcount(ph_n[a:b, None] ^ ph_a[None, :]).astype(np.uint16)
                   + _popcount(dh_n[a:b, None] ^ dh_a[None, :]))
        arg = abstand.argmin(axis=1)
        mins = abstand[np.arange(b - a), arg]
        for k in np.nonzero(mins <= schwelle)[0].tolist():
            merken(a + k, int(mins[k]), alt[int(arg[k])])
    # Serie: neues Bild wenige Sekunden vor/nach einem Bestandsbild derselben Kamera
    pro_kamera = defaultdict(list)
    for d in alt:
        if d.res[5] and d.res[3] is not None:
            pro_kamera[d.res[5]].append(d)
    zeiten = {}
    for kamera, liste in pro_kamera.items():
        liste.sort(key=lambda d: (d.res[3], d.pfad))
        zeiten[kamera] = [d.res[3] for d in liste]
    for pos, (_, d) in enumerate(neu):
        kamera, t = d.res[5], d.res[3]
        if not kamera or t is None or kamera not in pro_kamera:
            continue
        ts = zeiten[kamera]
        fenster = pro_kamera[kamera][bisect_left(ts, t - serie_sek):bisect_right(ts, t + serie_sek)]
        for d_alt in sorted(fenster, key=lambda x: abs(x.res[3] - t))[:60]:
            abstand = (d.res[0] ^ d_alt.res[0]).bit_count() + (d.res[1] ^ d_alt.res[1]).bit_count()
            if abstand <= serie_schwelle:
                merken(pos, abstand, d_alt)
    je_gruppe = {}
    for pos, kandidat in bestes.items():
        gi = neu[pos][0]
        if gi not in je_gruppe or kandidat < je_gruppe[gi]:
            je_gruppe[gi] = kandidat
    for gi, kandidat in je_gruppe.items():
        anker[gi] = kandidat[1]
    return anker


# ---------------------------------------------------------------- Zielnamen
_VERBOTEN = set('<>:"\\|?*')


def saeubern(name):
    neu = "".join("_" if (ch in _VERBOTEN or ord(ch) < 32 or 0xDC80 <= ord(ch) <= 0xDCFF) else ch
                  for ch in name)
    stamm, ext = os.path.splitext(neu)
    return (stamm.rstrip(" .") or "bild") + ext


def eindeutig(name, belegt):
    """Freien Namen im Zielordner finden: IMG.JPG, sonst IMG_1.JPG, IMG_2.JPG … (Laufindex).
    Vergleich ohne Groß/Klein, damit es auch auf exFAT/NTFS keine Kollision gibt."""
    stamm, ext = os.path.splitext(name)
    while stamm and len(os.fsencode(stamm + ext)) > 240:
        stamm = stamm[:-1]
    kandidat, n = stamm + ext, 0
    while kandidat.casefold() in belegt:
        n += 1
        kandidat = f"{stamm}_{n}{ext}"
    belegt.add(kandidat.casefold())
    return kandidat


def hoechste_nummer(ausgabe):
    hoch = 0
    try:
        for e in os.scandir(ausgabe):
            if e.is_dir(follow_symlinks=False) and re.fullmatch(r"\d{4}", e.name):
                hoch = max(hoch, int(e.name))
    except OSError:
        pass
    return hoch


def dateisystem(pfad):
    pfad = os.path.realpath(pfad)
    best = ("/", "?")
    try:
        with open("/proc/self/mounts", encoding="utf-8", errors="replace") as f:
            for zeile in f:
                teile = zeile.split()
                if len(teile) < 3:
                    continue
                mp = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), teile[1])
                if (pfad == mp or pfad.startswith(mp.rstrip("/") + "/")) and len(mp) >= len(best[0]):
                    best = (mp, teile[2])
    except OSError:
        pass
    return best


def plane(gruppen, anker, ausgabe, einzeln, start, fs_typ, nef_jpg=frozenset(), bestand_nef=None):
    """Plan [(ordnername, [(quelle, ziel, groesse, dev, art)])] in Ausführungsreihenfolge.
    art: "datei" = verschieben/kopieren, "jpg" = JPG aus dem NEF 'quelle' erzeugen.
    Rückgabe: plan, Anzahl Laufindex-Umbenennungen, Anzahl geplanter JPG (neu, Bestand)."""
    windows = fs_typ in WINDOWS_FS or fs_typ == "?"
    frei = [g for g, a in zip(gruppen, anker) if a is None]
    nummeriert = [g for g in frei if len(g) > 1 or einzeln != "0000"]
    zuteilung = defaultdict(list)
    for g, a in zip(gruppen, anker):
        if a is not None:
            zuteilung[a].extend(g)                 # ergänzt bestehenden Ordner
    for g in frei:
        if len(g) == 1 and einzeln == "0000":
            zuteilung["0000"].extend(g)
    for k, g in enumerate(nummeriert):
        zuteilung[f"{start + k:04d}"].extend(g)    # neuer Ordner
    bestand_nef = bestand_nef or {}
    plan, umbenannt, jpg_neu, jpg_bestand = [], 0, 0, 0

    def jpg_eintrag(nef_jetzt, nef_zielname, groesse, belegt, zielordner):
        """JPG nur, wenn im Zielordner noch keine JPG/JPEG mit gleichem Namensstamm liegt."""
        stamm, ext = os.path.splitext(nef_zielname)
        if f"{stamm}.jpg".casefold() in belegt or f"{stamm}.jpeg".casefold() in belegt:
            return None
        name = eindeutig(stamm + (".JPG" if ext == ".NEF" else ".jpg"), belegt)
        return (nef_jetzt, os.path.join(zielordner, name), max(groesse // 7, 1), None, "jpg")

    for ordner in sorted(set(zuteilung) | set(bestand_nef)):
        g = sorted(zuteilung.get(ordner, []), key=lambda d: (d.t_sort, d.pfad))
        zielordner = os.path.join(ausgabe, ordner)
        try:
            belegt = {n.casefold() for n in os.listdir(zielordner)}
        except OSError:
            belegt = set()
        eintraege = []
        for d in g:
            name = os.path.basename(d.pfad)
            basis = saeubern(name) if windows else name
            neu = eindeutig(basis, belegt)
            if neu != basis:
                umbenannt += 1
            eintraege.append((d.pfad, os.path.join(zielordner, neu), d.groesse, d.dev, "datei"))
            stamm, neu_stamm = os.path.splitext(name)[0], os.path.splitext(neu)[0]
            for b_pfad, b_groesse, b_dev in d.begleit:
                b_name = os.path.basename(b_pfad)
                if b_name.casefold().startswith(name.casefold()):
                    b_neu = neu + b_name[len(name):]
                else:
                    b_neu = neu_stamm + b_name[len(stamm):]
                b_neu = eindeutig(saeubern(b_neu) if windows else b_neu, belegt)
                eintraege.append((b_pfad, os.path.join(zielordner, b_neu), b_groesse, b_dev, "datei"))
        # zweiter Durchgang: alle Namen des Ordners sind jetzt bekannt
        mit_jpg = []
        for e in eintraege:
            mit_jpg.append(e)
            if e[4] == "datei" and e[0] in nef_jpg:
                neu_e = jpg_eintrag(e[1], os.path.basename(e[1]), e[2], belegt, zielordner)
                if neu_e:
                    mit_jpg.append(neu_e)
                    jpg_neu += 1
        for nef, groesse in bestand_nef.get(ordner, []):
            neu_e = jpg_eintrag(nef, os.path.basename(nef), groesse, belegt, zielordner)
            if neu_e:
                mit_jpg.append(neu_e)
                jpg_bestand += 1
        if mit_jpg:
            plan.append((ordner, mit_jpg))
    return plan, umbenannt, jpg_neu, jpg_bestand


# ---------------------------------------------------------------- Ausführung
def freier_pfad(basis):
    """basis + '.csv', bei Bedarf basis_2.csv, basis_3.csv … – nie überschreiben."""
    n = 1
    while True:
        pfad = f"{basis}.csv" if n == 1 else f"{basis}_{n}.csv"
        if not os.path.lexists(pfad):
            return pfad
        n += 1


class Protokoll:
    FELDER = ["ordner", "quelle", "ziel", "bytes", "status"]

    def __init__(self, basis):
        self.pfad = freier_pfad(basis)
        self.f = open(self.pfad, "x", newline="", encoding="utf-8", errors="surrogateescape")
        self.w = csv.writer(self.f)
        self.w.writerow(self.FELDER)

    def zeile(self, ordner, quelle, ziel, groesse, status):
        self.w.writerow([ordner, quelle, ziel, groesse, status])
        self.f.flush()

    def schliessen(self):
        self.f.close()


class Beweger:
    """Verschieben/Kopieren/Verlinken. Bei Kopie über Laufwerksgrenzen: erst sync,
    dann Größenvergleich, erst danach wird die Quelle gelöscht."""

    def __init__(self, protokoll, modus, text_ok="verschoben", nach_erfolg=None):
        self.prot, self.modus, self.text_ok = protokoll, modus, text_ok
        self.nach_erfolg = nach_erfolg  # z. B. Cache-Eintrag für den neuen Pfad
        self.wartend, self.wartend_bytes = [], 0
        self.zaehler = Counter()
        self.quellordner = set()

    def datei(self, ordner, quelle, ziel, groesse):
        if self.modus == "link":
            os.symlink(os.path.abspath(quelle), ziel)
            self._fertig(ordner, quelle, ziel, groesse, "verlinkt")
            return
        if self.modus == "move":
            try:
                os.rename(quelle, ziel)
                self._fertig(ordner, quelle, ziel, groesse, self.text_ok)
                return
            except OSError as e:
                if e.errno != errno.EXDEV:
                    raise
        tmp = ziel + ".fotosort-tmp"
        try:
            shutil.copyfile(quelle, tmp)
            try:
                shutil.copystat(quelle, tmp)
            except OSError:
                pass  # exFAT/NTFS: Rechte nicht übertragbar, Zeitstempel schon
            os.rename(tmp, ziel)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self.wartend.append((ordner, quelle, ziel, groesse))
        self.wartend_bytes += groesse
        if self.wartend_bytes >= SYNC_BYTES or len(self.wartend) >= SYNC_DATEIEN:
            self.abschliessen()

    def abschliessen(self):
        if not self.wartend:
            return
        os.sync()
        for ordner, quelle, ziel, groesse in self.wartend:
            try:
                gleich = os.path.getsize(ziel) == os.path.getsize(quelle)
            except OSError:
                gleich = False
            if not gleich:
                self._fertig(ordner, quelle, ziel, groesse, "fehler: Größe weicht ab, Quelle behalten")
                continue
            if self.modus == "move":
                try:
                    os.unlink(quelle)
                    self._fertig(ordner, quelle, ziel, groesse, self.text_ok)
                except OSError as e:
                    self._fertig(ordner, quelle, ziel, groesse, f"kopiert (Quelle nicht löschbar: {e.strerror})")
            else:
                self._fertig(ordner, quelle, ziel, groesse, "kopiert")
        self.wartend, self.wartend_bytes = [], 0

    def jpg_erzeugen(self, ordner, nef, ziel):
        groesse = nef_zu_jpg(nef, ziel)
        self.prot.zeile(ordner, nef, ziel, groesse, "erzeugt")
        self.zaehler["JPG erzeugt"] += 1

    def fehler(self, ordner, quelle, ziel, groesse, e):
        grund = getattr(e, "strerror", None) or str(e)
        self._fertig(ordner, quelle, ziel, groesse, f"fehler: {grund}")

    def _fertig(self, ordner, quelle, ziel, groesse, status):
        self.prot.zeile(ordner, quelle, ziel, groesse, status)
        self.zaehler[status.split(" ")[0].rstrip(":")] += 1
        if status == self.text_ok:
            self.quellordner.add(os.path.dirname(quelle))
        if self.nach_erfolg is not None and (status == self.text_ok or status.startswith("kopiert")):
            self.nach_erfolg(quelle, ziel)


_STOPP = {"an": False}


def _sigint(signum, frame):
    _STOPP["an"] = True
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.stderr.write("\nAbbruch angefordert – der laufende Ordner wird noch fertig. "
                     "Erneut Strg+C = sofort.\n")


def leere_ordner_entfernen(ordnerliste, grenze):
    grenze = os.path.realpath(grenze)
    entfernt = 0
    for o in sorted(ordnerliste, key=len, reverse=True):
        while os.path.realpath(o) != grenze and os.path.realpath(o).startswith(grenze + os.sep):
            try:
                os.rmdir(o)
                entfernt += 1
            except OSError:
                break
            o = os.path.dirname(o)
    return entfernt


def bestaetigen(frage):
    if os.environ.get("JA", "").strip() == "1":
        return True
    if not sys.stdin.isatty():
        sys.exit("Abbruch: keine Rückfrage möglich (kein Terminal). Mit JA=1 starten.")
    try:
        antwort = input(f"{frage} [j/N] ").strip().lower()
    except EOFError:
        antwort = ""
    return antwort in ("j", "ja", "y", "yes")


def ausfuehren(plan, modus, prot, gesamt_bytes, nach_erfolg=None):
    verb = {"move": "Verschiebe", "copy": "Kopiere", "link": "Verlinke"}[modus]
    beweger = Beweger(prot, modus, nach_erfolg=nach_erfolg if modus != "link" else None)
    anzahl = sum(len(e) for _, e in plan)
    fort = Fortschritt(verb, anzahl)
    erledigt, bytes_fertig, start = 0, 0, time.time()
    alter_handler = signal.signal(signal.SIGINT, _sigint)
    abbruch = None
    umgeleitet = {}
    try:
        for ordner, eintraege in plan:
            zielordner = os.path.dirname(eintraege[0][1])
            os.makedirs(zielordner, exist_ok=True)
            for quelle, ziel, groesse, _dev, art in eintraege:
                geplant = ziel
                if os.path.lexists(ziel):  # Sicherheitsnetz, sollte nicht vorkommen
                    belegt = {n.casefold() for n in os.listdir(zielordner)}
                    ziel = os.path.join(zielordner, eindeutig(os.path.basename(ziel), belegt))
                    umgeleitet[geplant] = ziel
                try:
                    if art == "jpg":
                        beweger.jpg_erzeugen(ordner, umgeleitet.get(quelle, quelle), ziel)
                    else:
                        beweger.datei(ordner, quelle, ziel, groesse)
                except OSError as e:
                    beweger.fehler(ordner, quelle, ziel, groesse, e)
                    if e.errno in KRITISCH:
                        abbruch = f"{e.strerror} bei {ziel}"
                        break
                except Exception as e:  # z. B. defekte Vorschau im NEF: nur diese Datei auslassen
                    beweger.fehler(ordner, quelle, ziel, groesse, e)
                erledigt += 1
                bytes_fertig += groesse
                lauf = max(time.time() - start, 1e-6)
                fort.melden(erledigt, f" · {gb(bytes_fertig)}/{gb(gesamt_bytes)} · {bytes_fertig / lauf / 1e6:.0f} MB/s")
            if abbruch or _STOPP["an"]:
                break
        beweger.abschliessen()
    finally:
        signal.signal(signal.SIGINT, alter_handler)
    fort.melden(erledigt, f" · {gb(bytes_fertig)}", ende=True)
    return beweger, abbruch or ("Strg+C" if _STOPP["an"] else None)


def rueckgaengig(logpfad):
    if not os.path.isfile(logpfad):
        sys.exit(f"Fehler: Protokoll {logpfad} nicht gefunden.")
    with open(logpfad, newline="", encoding="utf-8", errors="surrogateescape") as f:
        zeilen = list(csv.DictReader(f))
    letzte = {}
    for z in zeilen:
        if z.get("ziel"):
            letzte[z["ziel"]] = z
    zurueck = [z for z in letzte.values() if z["status"] == "verschoben"]
    entfernen = [z for z in letzte.values() if z["status"] in ("kopiert", "verlinkt", "erzeugt")
                 or z["status"].startswith("kopiert (")]
    info(f"Protokoll: {logpfad}")
    info(f"Zurückverschieben: {zahl(len(zurueck))} Dateien · Kopien, Links und erzeugte JPG entfernen: "
         f"{zahl(len(entfernen))}")
    if not zurueck and not entfernen:
        info("Nichts zu tun.")
        return 0
    if not bestaetigen("Rückgängig machen?"):
        sys.exit("Abgebrochen – nichts verändert.")
    prot = Protokoll((logpfad[:-4] if logpfad.endswith(".csv") else logpfad) + "_undo")
    undo_pfad = prot.pfad
    beweger = Beweger(prot, "move", text_ok="zurückverschoben")
    konflikte = 0
    fort = Fortschritt("Rückgängig", len(zurueck) + len(entfernen))
    erledigt = 0
    for z in reversed(zurueck):
        quelle, ziel, groesse = z["quelle"], z["ziel"], int(z["bytes"] or 0)
        erledigt += 1
        if not os.path.lexists(ziel):
            prot.zeile(z["ordner"], ziel, quelle, groesse, "fehlt im Ziel")
            continue
        if os.path.lexists(quelle):
            konflikte += 1
            prot.zeile(z["ordner"], ziel, quelle, groesse, "konflikt: Originalpfad belegt")
            continue
        try:
            os.makedirs(os.path.dirname(quelle), exist_ok=True)
            beweger.datei(z["ordner"], ziel, quelle, groesse)
        except OSError as e:
            beweger.fehler(z["ordner"], ziel, quelle, groesse, e)
            if e.errno in KRITISCH:
                break
        fort.melden(erledigt)
    beweger.abschliessen()
    entfernt = 0
    for z in entfernen:
        erledigt += 1
        quelle, ziel = z["quelle"], z["ziel"]
        try:
            if z["status"] == "erzeugt":
                if os.path.isfile(ziel) and not os.path.islink(ziel):
                    os.unlink(ziel)
                    entfernt += 1
                    prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "erzeugte JPG entfernt")
                else:
                    prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "erzeugte JPG fehlt schon")
            elif os.path.islink(ziel) and os.readlink(ziel) == os.path.abspath(quelle):
                os.unlink(ziel)
                entfernt += 1
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "link entfernt")
            elif (os.path.isfile(ziel) and not os.path.islink(ziel) and os.path.isfile(quelle)
                  and os.path.getsize(ziel) == os.path.getsize(quelle)):
                os.unlink(ziel)
                entfernt += 1
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "kopie entfernt")
            else:
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "behalten: Original fehlt oder weicht ab")
        except OSError as e:
            prot.zeile(z["ordner"], ziel, quelle, z["bytes"], f"fehler: {e.strerror}")
        fort.melden(erledigt)
    fort.melden(erledigt, ende=True)
    prot.schliessen()
    ordner = {os.path.dirname(z["ziel"]) for z in letzte.values()}
    leer = 0
    for o in ordner:
        try:
            os.rmdir(o)
            leer += 1
        except OSError:
            pass
    info(f"Fertig: {zahl(beweger.zaehler['zurückverschoben'])} zurückverschoben · "
         f"{zahl(entfernt)} Kopien/Links/JPG entfernt · {konflikte} Konflikte · {leer} leere Ordner entfernt.")
    info(f"Protokoll: {undo_pfad}")
    return 0


# ---------------------------------------------------------------- Hauptprogramm
def main():
    # Strg+C bzw. SIGINT (Abbrechen in bestof.py) immer als KeyboardInterrupt – auch wenn der startende
    # Prozess SIGINT ignoriert (z. B. Hintergrundstart aus einer Shell)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "--hilfe"):
        print(__doc__)
        return 0
    modus = _env("MODUS", "move").lower()
    if modus not in ("move", "copy", "link", "test", "undo"):
        sys.exit(f"Fehler: MODUS={modus!r} – erlaubt: move, copy, link, test, undo")
    if modus == "undo":
        if len(args) != 1:
            sys.exit("Aufruf: MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv")
        return rueckgaengig(os.path.abspath(args[0]))
    if len(args) != 2:
        sys.exit("Aufruf: python fotosort.py EINGABE AUSGABE   (Hilfe: -h)")

    schwelle = _env("SCHWELLE", 20, int)
    serie_sek = _env("SERIE_SEK", 3.0, float)
    serie_schwelle = _env("SERIE_SCHWELLE", 36, int)
    einzeln = _env("EINZELN", "ordner").lower()
    if einzeln not in ("ordner", "0000"):
        sys.exit("Fehler: EINZELN muss 'ordner' oder '0000' sein.")
    jobs = max(1, _env("JOBS", os.cpu_count() or 1, int))
    begleit_an = _env("BEGLEIT", "1") != "0"
    aufraeumen = _env("AUFRAEUMEN", "1") != "0"
    nef_jpg_an = _env("NEF_JPG", "1") != "0"
    duplikate_an = _env("DUPLIKATE", "1") != "0"
    cache_pfad = os.path.expanduser(_env("CACHE", "~/.cache/fotosort/cache.sqlite3"))

    eingabe = os.path.abspath(args[0])
    ausgabe = os.path.abspath(args[1])
    if not os.path.isdir(eingabe):
        sys.exit(f"Fehler: Eingabeordner {eingabe} existiert nicht.")
    if os.path.realpath(eingabe) == os.path.realpath(ausgabe):
        sys.exit("Fehler: Eingabe und Ausgabe sind derselbe Ordner.")
    if os.path.exists(ausgabe) and not os.path.isdir(ausgabe):
        sys.exit(f"Fehler: {ausgabe} ist kein Ordner.")
    if not os.path.isdir(ausgabe):
        if not os.path.isdir(os.path.dirname(ausgabe)):
            sys.exit(f"Fehler: {os.path.dirname(ausgabe)} existiert nicht – Laufwerk eingehängt?")
        os.mkdir(ausgabe)
    mountpunkt, fs_typ = dateisystem(ausgabe)
    if modus == "link" and fs_typ in WINDOWS_FS:
        sys.exit(f"Fehler: MODUS=link braucht ein Linux-Dateisystem, {ausgabe} liegt auf {fs_typ}.")

    info(f"fotosort {VERSION} · Modus {modus} · rawpy {'ja' if rawpy else 'nein (NEF über eingebettete Vorschau)'}")
    info(f"Eingabe:  {eingabe}")
    info(f"Ausgabe:  {ausgabe}  (Laufwerk {mountpunkt}, {fs_typ})")

    t0 = time.time()
    bilder, begleit, scan = suche(eingabe, os.path.realpath(ausgabe))
    typen = Counter(os.path.splitext(d.pfad)[1].lower().lstrip(".") for d in bilder)
    n_begleit = ordne_begleitdateien(bilder, begleit) if begleit_an else 0
    info(f"Gefunden: {zahl(len(bilder))} Bilder ("
         + " · ".join(f"{k} {zahl(v)}" for k, v in typen.most_common())
         + f"), {gb(sum(d.groesse for d in bilder))}; Begleitdateien: {zahl(n_begleit)}")
    if scan["links"] or scan["ordner_fehler"]:
        info(f"Übersprungen: {zahl(scan['links'])} symbolische Links, {zahl(scan['ordner_fehler'])} unlesbare Ordner")
    if not bilder:
        info("Keine Bilder gefunden.")
        return 0
    bestand = suche_bestand(ausgabe, os.path.realpath(eingabe))
    if bestand:
        b_ordner = sorted({d.anker for d in bestand})
        info(f"Bestand:  {zahl(len(bestand))} Bilder in {zahl(len(b_ordner))} Ordnern "
             f"({b_ordner[0]}–{b_ordner[-1]}) – bleiben, wo sie sind")

    # Analyse (mit Cache; Bestandsbilder sind nach dem ersten Lauf dort bekannt)
    cache = Cache(cache_pfad)
    atexit.register(cache.schliessen)
    doppelt = {}
    if duplikate_an:
        doppelt = duplikate_finden(bilder, bestand, cache, jobs)
        if doppelt:
            im_bestand = sum(1 for v in doppelt.values() if v.startswith(ausgabe + os.sep))
            bilder = [d for d in bilder if d.pfad not in doppelt]
            info(f"Duplikate: {zahl(len(doppelt))} Dateien mit gleichem Inhalt werden übersprungen "
                 f"({zahl(im_bestand)} schon im Archiv, {zahl(len(doppelt) - im_bestand)} mehrfach in der Quelle)")
        if not bilder:
            info("Alle Bilder sind schon im Archiv – nichts zu tun.")
            return 0
    alle_bilder = bilder + bestand
    offen = []
    for i, d in enumerate(alle_bilder):
        d.res = cache.holen(d.pfad, d.groesse, d.mtime)
        if d.res is None:
            offen.append(i)
    treffer = len(alle_bilder) - len(offen)
    fort = Fortschritt("Analyse", len(offen))
    zaehler = [0]

    def ablegen(i, res):
        d = alle_bilder[i]
        d.res = res
        if isinstance(res, list):
            cache.ablegen(d.pfad, d.groesse, d.mtime, res)
        zaehler[0] += 1
        fort.melden(zaehler[0])

    try:
        if offen:
            analyse_parallel([(i, alle_bilder[i].pfad) for i in offen], min(jobs, len(offen)), ablegen)
            fort.melden(len(offen), ende=True)
    except KeyboardInterrupt:
        cache.schliessen()
        sys.exit("\nAbgebrochen während der Analyse – nichts verschoben. Bisherige Ergebnisse sind im Cache.")
    info(f"Analyse:  {dauer(time.time() - t0)} (aus Cache: {zahl(treffer)})")

    for d in alle_bilder:
        t_exif = d.res[4] if d.ok else None
        if t_exif is None:
            t_exif = _zeit_aus_name(os.path.basename(d.pfad))
        if t_exif is None:
            try:
                t_exif = (datetime.fromtimestamp(d.mtime / 1e9) - _EPOCHE).total_seconds()
            except (OverflowError, OSError, ValueError):
                t_exif = 0.0
        d.t_sort = t_exif
    defekt = [d for d in bilder if not d.ok]
    abgeschnitten = sum(1 for d in bilder if d.ok and d.res[6])

    gruppen, n_bild, n_serie = gruppiere(bilder, schwelle, serie_sek, serie_schwelle)
    anker = finde_anker(gruppen, bestand, schwelle, serie_sek, serie_schwelle)
    start = hoechste_nummer(ausgabe) + 1
    frei_gruppen = [g for g, a in zip(gruppen, anker) if a is None]
    n_einzeln = sum(1 for g in frei_gruppen if len(g) == 1)
    n_ordner = len(frei_gruppen) - (n_einzeln if einzeln == "0000" else 0)
    if n_ordner and start + n_ordner - 1 > MAX_ORDNER:
        sys.exit(f"Abbruch vor dem Verschieben: {zahl(n_ordner)} neue Ordner nötig, ab {start:04d} frei "
                 f"sind nur {zahl(max(MAX_ORDNER - start + 1, 0))}.\n"
                 f"Möglich: EINZELN=0000 (Einzelbilder in Sammelordner) oder höhere SCHWELLE / SERIE_SCHWELLE.")
    nef_jpg, bestand_nef = set(), {}
    if nef_jpg_an:  # zu jedem NEF ein JPG – außer die Kamera hat schon eins geschrieben
        def stamm(d):
            return os.path.splitext(os.path.basename(d.pfad))[0].casefold()

        def ist(d, *endungen):
            return os.path.splitext(d.pfad)[1].lower() in endungen

        kamera_jpg = {(os.path.dirname(d.pfad), stamm(d)) for d in bilder if d.ok and ist(d, ".jpg", ".jpeg")}
        nef_jpg = {d.pfad for d in bilder
                   if d.ok and ist(d, ".nef") and (os.path.dirname(d.pfad), stamm(d)) not in kamera_jpg}
        bestand_jpg = {(d.anker, stamm(d)) for d in bestand if ist(d, ".jpg", ".jpeg")}
        for d in bestand:
            if (d.ok and ist(d, ".nef") and (d.anker, stamm(d)) not in bestand_jpg
                    and os.path.dirname(d.pfad) == os.path.join(ausgabe, d.anker)):
                bestand_nef.setdefault(d.anker, []).append((d.pfad, d.groesse))
    plan, umbenannt, jpg_neu, jpg_bestand = plane(gruppen, anker, ausgabe, einzeln, start, fs_typ,
                                                  nef_jpg, bestand_nef)

    groessen = sorted(((len(g), g) for g in frei_gruppen if len(g) > 1), key=lambda x: -x[0])
    ordner_von = {}
    for ordner, eintraege in plan:
        for quelle, *_ in eintraege:
            ordner_von[quelle] = ordner
    bereich = f"{start:04d}–{start + n_ordner - 1:04d}" if n_ordner else "–"
    info(f"Gruppen:  {zahl(n_ordner)} neue Ordner ({bereich}) · {zahl(len(groessen))} mit ≥2 Bildern · "
         f"{zahl(n_einzeln)} Einzelbilder" + (" → Ordner 0000" if einzeln == "0000" and n_einzeln else ""))
    if bestand:
        ergaenzt = [g for g, a in zip(gruppen, anker) if a is not None]
        info(f"Ergänzt:  {zahl(sum(len(g) for g in ergaenzt))} Bilder kommen in "
             f"{zahl(len({a for a in anker if a is not None}))} bestehende Ordner")
    if umbenannt:
        info(f"Laufindex: {zahl(umbenannt)} Bilder, deren Name im Zielordner schon existiert (z. B. IMG_0001_1.JPG)")
    if jpg_neu or jpg_bestand:
        info(f"JPG aus NEF: {zahl(jpg_neu + jpg_bestand)} werden erzeugt"
             + (f" (davon {zahl(jpg_bestand)} für NEF im Bestand)" if jpg_bestand else ""))
    info(f"Verknüpft: {zahl(n_bild)} × Bildvergleich (≤{schwelle}), {zahl(n_serie)} × Serie "
         f"(≤{serie_sek:g} s, ≤{serie_schwelle})")
    for anzahl, g in groessen[:5]:
        info(f"  größte: {ordner_von[g[0].pfad]} · {anzahl} Bilder · {os.path.basename(g[0].pfad)} …")
    if defekt:
        info(f"Nicht lesbar: {zahl(len(defekt))} Dateien – bleiben liegen (siehe Protokoll), z. B.:")
        for d in defekt[:5]:
            info(f"  {d.pfad}: {d.res}")
    if abgeschnitten:
        info(f"Hinweis: {zahl(abgeschnitten)} Dateien sind abgeschnitten, aber auswertbar.")

    # Platzbedarf
    ziel_dev = os.stat(ausgabe).st_dev
    sv = os.statvfs(ausgabe)
    cluster = sv.f_frsize or 4096
    frei = sv.f_bavail * sv.f_frsize
    alle = [e for _, eintraege in plan for e in eintraege]
    gesamt = sum(e[2] for e in alle)
    noetig = sum(-(-e[2] // cluster) * cluster for e in alle
                 if e[4] == "jpg" or modus == "copy" or (modus in ("move", "test") and e[3] != ziel_dev))
    if modus == "link":
        noetig = sum(-(-e[2] // cluster) * cluster for e in alle if e[4] == "jpg")
    reserve = (1 << 30) + noetig // 100
    passt = noetig + reserve <= frei
    info(f"Platz:    benötigt {gb(noetig)} (+{gb(reserve)} Reserve), frei {gb(frei)} → "
         + ("passt" if passt else "REICHT NICHT"))
    if fs_typ == "vfat" and any(e[2] >= 4 * 1024 ** 3 for e in alle):
        info("Warnung: FAT32 erlaubt keine Dateien ≥ 4 GiB.")

    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    if modus == "test":
        prot = Protokoll(os.path.join(ausgabe, f"fotosort_plan_{stempel}"))
        for ordner, eintraege in plan:
            for quelle, ziel, groesse, _dev, art in eintraege:
                prot.zeile(ordner, quelle, ziel, groesse, "geplant (JPG aus NEF)" if art == "jpg" else "geplant")
        for d in defekt:
            prot.zeile("", d.pfad, "", d.groesse, f"nicht lesbar: {d.res}")
        prot.schliessen()
        info(f"Plan:     {prot.pfad}")
        info("Probelauf – nichts verändert.")
        return 0
    if not alle:
        info("Nichts zu verschieben.")
        return 0
    if not passt:
        sys.exit("Abbruch: zu wenig Platz im Ziel – nichts verändert.")
    verb = {"move": "verschieben", "copy": "kopieren", "link": "verlinken"}[modus]
    n_dateien = sum(1 for e in alle if e[4] == "datei")
    frage = f"{zahl(n_dateien)} Dateien ({gb(sum(e[2] for e in alle if e[4] == 'datei'))}) nach {ausgabe} {verb}"
    if jpg_neu or jpg_bestand:
        frage += f" und {zahl(jpg_neu + jpg_bestand)} JPG aus NEF erzeugen"
    if not bestaetigen(frage + "?"):
        sys.exit("Abgebrochen – nichts verändert.")

    prot = Protokoll(os.path.join(ausgabe, f"fotosort_{stempel}"))
    logpfad = prot.pfad
    for d in defekt:
        prot.zeile("", d.pfad, "", d.groesse, f"nicht lesbar: {d.res}")
    for quelle, gleich in sorted(doppelt.items()):
        prot.zeile("", quelle, "", "", f"übersprungen: gleicher Inhalt wie {gleich}")
    res_von = {d.pfad: d.res for d in bilder if d.ok}

    def im_cache_merken(quelle, ziel):
        """Neuen Pfad im Cache ablegen – beim nächsten Lauf ist der Bestand dann schon bekannt."""
        res = res_von.get(quelle)
        if res is not None:
            try:
                st = os.stat(ziel)
                cache.ablegen(ziel, st.st_size, st.st_mtime_ns, res)
            except OSError:
                pass

    t1 = time.time()
    beweger, abbruch = ausfuehren(plan, modus, prot, gesamt, nach_erfolg=im_cache_merken)
    prot.schliessen()
    cache.schliessen()
    entfernt = 0
    if modus == "move" and aufraeumen:
        entfernt = leere_ordner_entfernen(beweger.quellordner, eingabe)
    z = beweger.zaehler
    info(f"Fertig in {dauer(time.time() - t1)}: " + " · ".join(f"{zahl(v)} {k}" for k, v in z.most_common())
         + (f" · {zahl(entfernt)} leere Quellordner entfernt" if entfernt else ""))
    info(f"Protokoll: {logpfad}")
    if abbruch:
        info(f"ABGEBROCHEN ({abbruch}). Erneuter Start ergänzt den Rest: passende Bilder kommen "
             f"in die schon angelegten Ordner, übrige in neue.")
    if modus in ("move", "copy", "link"):
        info(f"Rückgängig: MODUS=undo {sys.executable} {os.path.abspath(sys.argv[0])} '{logpfad}'")
    return 1 if abbruch or z["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
