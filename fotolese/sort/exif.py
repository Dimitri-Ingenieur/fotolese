"""fotolese.sort.exif – Zeit, Orientierung und Kamera aus EXIF (oder Dateiname) lesen."""
from datetime import datetime

from fotolese import gemein
from fotolese.sort.konst import _EPOCHE


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
    teile = gemein.datum_teile_aus_name(name)
    if teile is None:
        return None
    return _zeit("{}:{}:{} {}:{}:{}".format(*teile))


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
