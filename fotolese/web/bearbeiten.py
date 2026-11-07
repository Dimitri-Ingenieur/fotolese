"""fotolese.web.bearbeiten – ein Foto in der Lupe bearbeiten und als neue Fassung speichern.

Im Bearbeitungsmodus der Lupe lässt sich das Foto um 90° drehen und waagerecht spiegeln, dazu Helligkeit, Kontrast
und Sättigung einstellen. Die Lupe zeigt das vorab mit CSS (transform, filter); „Speichern“ wendet dasselbe mit
denselben Formeln auf das Foto in voller Größe an und legt es wie beim Verbessern als
SORTIERT/<Ordner>/verbessert/<Name>_bearbeitet.png ab (weitere als …_bearbeitet_2.png). Das Foto selbst bleibt.
"""
import os
import re

from PIL import Image, ImageOps

from fotolese.web.bild import _rgb
from fotolese.web.konfig import anzeige, name_aus_id, url_id
from fotolese.web.konst import ORDNER_MUSTER
from fotolese.web.papierkorb import umzug_laeuft
from fotolese.web.verbessern import Fehler, speichern

T = Image.Transpose
DREHUNG = {90: T.ROTATE_270, 180: T.ROTATE_180, 270: T.ROTATE_90}  # im Uhrzeigersinn; PIL dreht links herum
REGLER = ("helligkeit", "kontrast", "saettigung")  # je -100 … +100, 0 = unverändert


def _hell_kontrast(bild, b, c):
    """Jeden Kanal wie CSS brightness(b) contrast(c): erst · b, dann um die Mitte strecken – je begrenzt auf 0–255,
    gerundet erst am Ende (eine Tabelle, wie der Browser ohne Zwischenrundung)."""
    tabelle = [min(255, max(0, round(min(255.0, v * b) * c + 127.5 * (1 - c)))) for v in range(256)]
    return bild.point(tabelle * len(bild.getbands()))


def bearbeitet(im, drehung=0, spiegeln=False, helligkeit=0, kontrast=0, saettigung=0):
    """Das Foto wie in der Vorschau: aufrecht, im Uhrzeigersinn drehen, dann spiegeln, dann Helligkeit, Kontrast und
    Sättigung mit den Formeln von CSS brightness(), contrast() und saturate(). Graue Fotos bleiben grau (kleiner)."""
    im = ImageOps.exif_transpose(im)
    if drehung in DREHUNG:
        im = im.transpose(DREHUNG[drehung])
    if spiegeln:
        im = im.transpose(T.FLIP_LEFT_RIGHT)
    grau = im.mode in ("1", "L", "LA", "I", "I;16", "I;16B", "I;16L", "F")
    bild = _rgb(im)
    b, c, s = (1 + helligkeit / 100), (1 + kontrast / 100), (1 + saettigung / 100)
    if b != 1 or c != 1:
        bild = _hell_kontrast(bild, b, c)
    if s != 1 and not grau:
        bild = bild.convert("RGB", (0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s, 0,
                                    0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s, 0,
                                    0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s, 0))
    if grau:
        bild = bild.convert("L")
    profil = im.mode not in ("CMYK", "YCbCr", "LAB", "HSV")  # dessen Farbprofil passte nicht mehr zum RGB-Ergebnis
    bild.info = {k: v for k, v in im.info.items() if isinstance(v, str) or (k == "icc_profile" and profil)}
    return bild


def bearbeiten_api(app, daten):
    """POST /api/bearbeiten {pfad, drehung, spiegeln, helligkeit, kontrast, saettigung} -> neue Fassung."""
    if umzug_laeuft(app):
        return 409, {"fehler": "Gerade werden Ordner umsortiert – bitte einen Moment warten."}
    o, _, uid = str(daten.get("pfad") or "").partition("/")
    name = name_aus_id(uid)
    if not (ORDNER_MUSTER.fullmatch(o) and o in app.archiv.ordner() and uid and url_id(name) == uid
            and app.archiv.datei(o, name)):
        return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
    try:
        drehung = int(daten.get("drehung") or 0) % 360
        werte = {k: max(-100, min(100, int(daten.get(k) or 0))) for k in REGLER}
    except (TypeError, ValueError):
        return 400, {"fehler": "Ungültige Werte."}
    spiegeln = bool(daten.get("spiegeln"))
    if drehung not in (0, 90, 180, 270):
        return 400, {"fehler": "Drehen geht nur in Schritten von 90°."}
    if not (drehung or spiegeln or any(werte.values())):
        return 400, {"fehler": "Nichts geändert – erst drehen, spiegeln oder einen Regler bewegen."}
    stamm = re.sub(r"_bearbeitet(_\d+)?$", "", os.path.splitext(os.path.basename(name))[0]) + "_bearbeitet"
    try:
        with Image.open(os.path.join(app.archiv.pfad, o, name)) as im:
            im.load()
            bild = bearbeitet(im, drehung, spiegeln, **werte)
        neu = speichern(app, o, name, bild, None, stamm=stamm,
                        notiz={"bearbeitet": {"drehung": drehung, "spiegeln": spiegeln, **werte}})
    except Fehler as fehler:
        return 500, {"fehler": str(fehler)}
    except OSError as fehler:
        return 500, {"fehler": f"Speichern fehlgeschlagen ({fehler.strerror or fehler})."}
    app.archiv.bilder(o, frisch=True)
    _, _, mt = app.archiv.datei(o, neu) or (None, 0, 0)
    if app.indexer:
        app.indexer.weiter.set()  # die neue Fassung gleich einlesen
    print(f"Bearbeitet: {o}/{anzeige(name)} – gespeichert als {anzeige(neu)}", flush=True)
    nid = url_id(neu)
    return 200, {"ergebnis": {"name": anzeige(neu), "id": nid, "g": f"/g/{o}/{nid}?v={mt}", "o": f"/orig/{o}/{nid}"},
                 "meldung": f"Gespeichert als {anzeige(neu)} – im Ordner direkt hinter dem Foto."}
