"""fotolese.sort.nef – NEF/RAW lesen (Graustufen-Vorschau) und verlustfrei ein JPG erzeugen."""
import io
import os

from PIL import Image

from fotolese.sort.konst import DRAFT, rawpy
from fotolese.sort.bild import _grau
from fotolese.sort.exif import _exif_meta, _leer_meta


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
