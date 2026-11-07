"""fotolese.web.drehen – ein Foto um 90° drehen oder waagerecht spiegeln, verlustfrei und in der Datei selbst.

JPEG: Nur die Ausrichtung im EXIF (und, falls vorhanden, im XMP) ändert sich, die Bilddaten bleiben Byte für Byte –
jedes Programm zeigt das Foto danach richtig herum. PNG: Die Pixel werden gedreht und verlustfrei neu geschrieben;
Texte (etwa der ComfyUI-Workflow), Farbprofil, EXIF und die übrigen Zusatzangaben bleiben.

Danach zieht bestof alles nach: Gesichtskästen im Index drehen mit (Namen bleiben), Breite und Höhe tauschen, die
Gesichter im gedrehten Bild neu suchen lassen (ein Scan, der auf der Seite lag, hatte oft keine), die BestOf-Kopie
auffrischen. Weil sich der Dateiinhalt ändert, vermerkt SORTIERT/.bestof-gedreht.json die Prüfsumme von vorher –
so erkennt fotosort die ungedrehte Datei beim nächsten Import derselben Quelle weiter als „schon im Archiv“.
"""
import hashlib
import io
import json
import os
import re
import shutil
import threading
import traceback

from PIL import Image, ImageOps, PngImagePlugin

from fotolese.gemein import GEDREHT
from fotolese.web.html import bogen_html
from fotolese.web.konfig import anzeige, name_aus_id, url_id
from fotolese.web.konst import ORDNER_MUSTER
from fotolese.web.papierkorb import umzug_laeuft

T = Image.Transpose
SCHRITTE = {"rechts": T.ROTATE_270, "links": T.ROTATE_90, "spiegeln": T.FLIP_LEFT_RIGHT}  # PIL dreht links herum
MELDUNG = {"rechts": "Um 90° nach rechts gedreht", "links": "Um 90° nach links gedreht",
           "spiegeln": "Waagerecht gespiegelt"}
_LAGE = {2: T.FLIP_LEFT_RIGHT, 3: T.ROTATE_180, 4: T.FLIP_TOP_BOTTOM, 5: T.TRANSPOSE, 6: T.ROTATE_270,
         7: T.TRANSVERSE, 8: T.ROTATE_90}  # EXIF-Ausrichtung -> Anzeige, wie ImageOps.exif_transpose
_XMP = b"http://ns.adobe.com/xap/1.0/\x00"
_SPERRE = threading.Lock()


class DrehFehler(Exception):
    """Fehler beim Drehen mit einem Text für die Oberfläche; die Datei ist dann unverändert."""


def _folge():
    """{(EXIF-Ausrichtung, Schritt): neue Ausrichtung} – an einem kleinen, in jeder Lage anderen Muster ausgerechnet,
    also genau so, wie PIL (und damit bestof) die Ausrichtung beim Anzeigen anwendet."""
    muster = Image.frombytes("L", (3, 2), bytes(range(6)))
    zeigen = {o: muster.transpose(_LAGE[o]) if o in _LAGE else muster for o in range(1, 9)}
    nach_bild = {(im.size, im.tobytes()): o for o, im in zeigen.items()}
    folge = {}
    for o, im in zeigen.items():
        for schritt, t in SCHRITTE.items():
            danach = im.transpose(t)
            folge[(o, schritt)] = nach_bild[(danach.size, danach.tobytes())]
    return folge


FOLGE = _folge()


def kasten_drehen(kasten, schritt):
    """Gesichtskasten (x, y, w, h als Anteile des angezeigten Bildes) nach dem Schritt."""
    x, y, w, h = kasten
    if schritt == "rechts":
        return 1 - y - h, x, h, w
    if schritt == "links":
        return y, 1 - x - w, h, w
    return 1 - x - w, y, w, h


# -- JPEG: Ausrichtung im EXIF setzen, Bilddaten unverändert

def _tiff_ausrichtung(tiff, neu):
    """TIFF-Daten eines EXIF-Blocks mit neuer Ausrichtung. Gibt es den Eintrag in IFD0, ändern sich nur seine Bytes;
    sonst kommt IFD0 samt neuem Eintrag ans Ende – alle anderen Daten und Verweise bleiben, wo sie sind."""
    if tiff[:4] not in (b"II*\x00", b"MM\x00*"):
        raise DrehFehler("EXIF-Daten nicht lesbar – das Foto bleibt unverändert.")
    bo = "little" if tiff[:2] == b"II" else "big"
    ifd = int.from_bytes(tiff[4:8], bo)
    n = int.from_bytes(tiff[ifd:ifd + 2], bo) if 8 <= ifd <= len(tiff) - 2 else -1
    ende = ifd + 2 + 12 * n
    if n < 0 or ende + 4 > len(tiff):
        raise DrehFehler("EXIF-Daten nicht lesbar – das Foto bleibt unverändert.")
    eintraege = [tiff[ifd + 2 + 12 * k:ifd + 14 + 12 * k] for k in range(n)]
    for k, e in enumerate(eintraege):
        if int.from_bytes(e[:2], bo) == 0x0112:
            typ, anzahl = int.from_bytes(e[2:4], bo), int.from_bytes(e[4:8], bo)
            if anzahl == 1 and typ in (3, 4):  # SHORT oder LONG: der Wert steht im Eintrag selbst
                p = ifd + 2 + 12 * k + 8
                return tiff[:p] + neu.to_bytes(2 if typ == 3 else 4, bo).ljust(4, b"\x00") + tiff[p + 4:]
            del eintraege[k]  # ungewöhnlich gespeichert: durch einen richtigen Eintrag ersetzen
            break
    eintraege.append((0x0112).to_bytes(2, bo) + (3).to_bytes(2, bo) + (1).to_bytes(4, bo)
                     + neu.to_bytes(2, bo) + b"\x00\x00")
    eintraege.sort(key=lambda e: int.from_bytes(e[:2], bo))  # TIFF verlangt aufsteigende Nummern
    start = len(tiff) + (len(tiff) & 1)  # IFDs beginnen an gerader Stelle
    neues_ifd = len(eintraege).to_bytes(2, bo) + b"".join(eintraege) + tiff[ende:ende + 4]  # Verweis auf IFD1 bleibt
    return tiff[:4] + start.to_bytes(4, bo) + tiff[8:] + b"\x00" * (start - len(tiff)) + neues_ifd


def _app1(inhalt):
    if len(inhalt) + 2 > 0xFFFF:
        raise DrehFehler("EXIF-Block zu groß – das Foto bleibt unverändert.")
    return b"\xff\xe1" + (len(inhalt) + 2).to_bytes(2, "big") + inhalt


def _jpeg_ausrichtung(roh, neu):
    """JPEG mit neuer EXIF-Ausrichtung; ohne EXIF entsteht ein kleiner EXIF-Block hinter SOI bzw. JFIF. Steht die
    Ausrichtung auch im XMP, bekommt sie dort denselben Wert (eine Ziffer, nichts verschiebt sich)."""
    teile, pos, exif_da, vorn = [], 2, False, 0  # vorn: JFIF/JFXX direkt hinter SOI – ein neuer EXIF-Block folgt
    while True:
        if pos + 4 > len(roh) or roh[pos] != 0xFF:
            raise DrehFehler("JPEG-Aufbau nicht lesbar – das Foto bleibt unverändert.")
        marke = roh[pos + 1]
        if marke == 0xFF:  # Füllbyte
            pos += 1
            continue
        if marke in (0xDA, 0xD9):  # ab hier die Bilddaten: bleiben, wie sie sind
            break
        if marke == 0x01 or 0xD0 <= marke <= 0xD8:  # Marken ohne Länge
            teile.append(roh[pos:pos + 2])
            pos += 2
            continue
        laenge = int.from_bytes(roh[pos + 2:pos + 4], "big")
        inhalt = roh[pos + 4:pos + 2 + laenge]
        if marke == 0xE1 and inhalt.startswith(b"Exif\x00\x00") and not exif_da:
            exif_da = True
            teile.append(_app1(b"Exif\x00\x00" + _tiff_ausrichtung(inhalt[6:], neu)))
        elif marke == 0xE1 and inhalt.startswith(_XMP):
            teile.append(roh[pos:pos + 4] + re.sub(rb'(tiff:Orientation\s*=\s*["\']|<tiff:Orientation>\s*)[1-8]',
                                                   lambda m: m.group(1) + str(neu).encode(), inhalt))
        else:
            if marke == 0xE0 and vorn == len(teile):
                vorn += 1
            teile.append(roh[pos:pos + 2 + laenge])
        pos += 2 + laenge
    if not exif_da:
        tiff = b"MM\x00*\x00\x00\x00\x08\x00\x01\x01\x12\x00\x03\x00\x00\x00\x01" + neu.to_bytes(2, "big") + bytes(6)
        teile.insert(vorn, _app1(b"Exif\x00\x00" + tiff))
    return roh[:2] + b"".join(teile) + roh[pos:]


# -- PNG: Pixel drehen, verlustfrei neu schreiben, Zusatzangaben behalten

_PNG_ZUSATZ = {b"cHRM", b"cICP", b"gAMA", b"sBIT", b"sRGB", b"tIME", b"bKGD", b"hIST", b"sPLT",
               b"tEXt", b"zTXt", b"iTXt"}  # schreibt PIL aus pnginfo; iCCP, tRNS, pHYs, eXIf kommen eigens
_DREHUNG_IM_TEXT = ("XML:com.adobe.xmp", "Raw profile type exif")  # Texte, die eine Ausrichtung tragen können


def _png_chunks(roh):
    pos = 8
    while pos + 12 <= len(roh):
        laenge = int.from_bytes(roh[pos:pos + 4], "big")
        typ = roh[pos + 4:pos + 8]
        yield typ, roh[pos + 8:pos + 8 + laenge]
        if typ == b"IEND":
            break
        pos += 12 + laenge


def _png_drehen(roh, schritt):
    chunks = list(_png_chunks(roh))
    ihdr = next((d for t, d in chunks if t == b"IHDR"), b"")
    if len(ihdr) < 13:
        raise DrehFehler("PNG-Aufbau nicht lesbar – das Foto bleibt unverändert.")
    if ihdr[8] == 16 and ihdr[9] in (2, 4, 6):  # 16 Bit je Farbkanal: PIL läse nur 8 Bit – das wäre ein Verlust
        raise DrehFehler("PNG mit 16 Bit je Farbkanal lässt sich hier nicht verlustfrei drehen.")
    if any(t == b"acTL" for t, _ in chunks):
        raise DrehFehler("Animierte PNG lassen sich nicht drehen.")
    with Image.open(io.BytesIO(roh)) as im:
        im.load()
        lage = im.getexif().get(0x0112, 1)
        bild = ImageOps.exif_transpose(im).transpose(SCHRITTE[schritt])
        dpi = im.info.get("dpi")
    ersetzen = _DREHUNG_IM_TEXT if lage != 1 else ()  # aus diesen Texten hat exif_transpose die Ausrichtung entfernt
    zusatz, nach_idat = PngImagePlugin.PngInfo(), False
    for typ, daten in chunks:
        nach_idat = nach_idat or typ == b"IDAT"
        if typ in (b"tEXt", b"zTXt", b"iTXt") and daten.split(b"\x00", 1)[0].decode("latin-1") in ersetzen:
            continue
        if typ in _PNG_ZUSATZ or typ[1:2].islower():  # dazu private Chunks (zweiter Buchstabe klein)
            zusatz.add(typ, daten, after_idat=nach_idat)
    for schluessel in ersetzen:
        wert = bild.info.get(schluessel)
        if isinstance(wert, bytes):
            wert = wert.decode("utf-8", "replace")
        if isinstance(wert, str):
            (zusatz.add_itxt if schluessel.startswith("XML") else zusatz.add_text)(schluessel, wert)
    optionen = {"pnginfo": zusatz}
    if dpi:
        optionen["dpi"] = dpi if schritt == "spiegeln" else dpi[::-1]
    if bild.info.get("exif"):
        optionen["exif"] = bild.info["exif"]
    puffer = io.BytesIO()
    bild.save(puffer, "PNG", **optionen)
    return puffer.getvalue()


def neuer_inhalt(roh, schritt):
    """Dateiinhalt nach dem Schritt (rechts, links, spiegeln) – für JPEG und PNG, sonst DrehFehler."""
    try:
        if roh[:2] == b"\xff\xd8":
            with Image.open(io.BytesIO(roh)) as im:
                lage = im.getexif().get(0x0112, 1)  # wie PIL sie anzeigt: EXIF, sonst XMP
            return _jpeg_ausrichtung(roh, FOLGE[(lage if lage in range(1, 9) else 1, schritt)])
        if roh[:8] == b"\x89PNG\r\n\x1a\n":
            return _png_drehen(roh, schritt)
    except DrehFehler:
        raise
    except Exception as fehler:  # PIL: beschädigte oder ungewöhnliche Datei
        print(f"Hinweis: Drehen nicht möglich – {type(fehler).__name__}: {fehler}", flush=True)
        raise DrehFehler("Die Bilddatei ist nicht lesbar – das Foto bleibt unverändert.") from None
    raise DrehFehler("Nur JPEG und PNG lassen sich drehen.")


# -- Datei ersetzen und alles nachführen

def _schreiben(pfad, daten):
    """Neuen Inhalt daneben schreiben und an die Stelle der Datei setzen. Rechte bleiben, die Änderungszeit ist
    jetzt – daran erkennen Vorschaubilder, Index und Browser die neue Fassung."""
    tmp = os.path.join(os.path.dirname(pfad), f".{os.path.basename(pfad)}.drehen.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(daten)
            f.flush()
            os.fsync(f.fileno())
        try:
            shutil.copymode(pfad, tmp)
        except OSError:
            pass  # exFAT/NTFS: keine Rechte
        os.replace(tmp, pfad)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _vermerke(app):
    """{SHA-256 jetzt: {vorher, vorher_groesse, groesse}} aus SORTIERT/.bestof-gedreht.json."""
    try:
        with open(os.path.join(app.archiv.pfad, GEDREHT), encoding="utf-8") as f:
            daten = json.load(f).get("gedreht")
        return daten if isinstance(daten, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _vermerken(app, dazu=None, weg=None):
    """Vermerk ergänzen (dazu) oder einen überholten entfernen (weg); fotosort liest die Datei beim Import."""
    vermerke = _vermerke(app)
    vermerke.update(dazu or {})
    vermerke.pop(weg, None)
    pfad = os.path.join(app.archiv.pfad, GEDREHT)
    with open(pfad + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"version": 1, "gedreht": vermerke}, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(pfad + ".tmp", pfad)


def _index_nachfuehren(app, rel, schritt, groesse, mtime):
    """Gesichtskästen mitdrehen, Breite/Höhe tauschen, Größe und Zeit der neuen Datei eintragen – so bleiben Namen
    und von Hand markierte Gesichter. Mit Gesichtserkennung sucht der Index danach im gedrehten Bild neu."""
    db = app.index.db
    for gid, *kasten in db.execute("SELECT id, x, y, w, h FROM gesicht WHERE pfad=?", (rel,)).fetchall():
        db.execute("UPDATE gesicht SET x=?, y=?, w=?, h=? WHERE id=?", (*kasten_drehen(kasten, schritt), gid))
    neu_suchen = bool(app.indexer and app.indexer.gesichter_aktiv)
    db.execute("UPDATE bild SET groesse=?, mtime=?" + (", breite=hoehe, hoehe=breite" if schritt != "spiegeln" else "")
               + (", gesichter=NULL" if neu_suchen else "") + " WHERE pfad=?", (groesse, mtime, rel))
    db.commit()


def drehen(app, ordner, name, schritt):
    """Foto drehen oder spiegeln. Rückgabe: (Größe, mtime_ns) der neuen Datei. DrehFehler/OSError: Datei unverändert."""
    pfad = os.path.join(app.archiv.pfad, ordner, name)
    with _SPERRE:
        with open(pfad, "rb") as f:
            roh = f.read()
        neu = neuer_inhalt(roh, schritt)
        sha_alt, sha_neu = hashlib.sha256(roh).hexdigest(), hashlib.sha256(neu).hexdigest()
        alt = _vermerke(app).get(sha_alt)  # schon einmal gedreht: der Inhalt von ganz vorher zählt
        alt = alt if isinstance(alt, dict) and isinstance(alt.get("vorher"), str) else None
        vorher = (alt or {}).get("vorher", sha_alt), (alt or {}).get("vorher_groesse", len(roh))
        if vorher[0] != sha_neu:  # vor dem Ersetzen, damit der Vermerk nie fehlt
            _vermerken(app, {sha_neu: {"vorher": vorher[0], "vorher_groesse": vorher[1], "groesse": len(neu)}})
        if app.index:
            with app.index.lock:  # Datei und Index zusammen: der Indexer sieht nie das eine ohne das andere
                _schreiben(pfad, neu)
                st = os.stat(pfad)
                try:
                    _index_nachfuehren(app, f"{ordner}/{url_id(name)}", schritt, st.st_size, st.st_mtime_ns)
                except Exception:
                    traceback.print_exc()
        else:
            _schreiben(pfad, neu)
            st = os.stat(pfad)
        if alt:
            try:
                _vermerken(app, weg=sha_alt)  # diesen Inhalt gibt es nicht mehr
            except OSError as fehler:
                print(f"Hinweis: {GEDREHT} nicht aufgeräumt ({fehler}).", flush=True)
    app.archiv.bilder(ordner, frisch=True)
    app.auswahl.auffrischen(ordner, name)
    if app.indexer:
        app.indexer.weiter.set()  # Gesichter im gedrehten Bild suchen
    print(f"{MELDUNG[schritt]}: {ordner}/{anzeige(name)}", flush=True)
    return st.st_size, st.st_mtime_ns


def drehen_api(app, daten):
    """POST /api/drehen {pfad: "0001/<id>", art: rechts | links | spiegeln} -> neue Bilddaten für die Seite."""
    if umzug_laeuft(app):
        return 409, {"fehler": "Gerade werden Ordner umsortiert – bitte einen Moment warten."}
    schritt = str(daten.get("art") or "")
    if schritt not in SCHRITTE:
        return 400, {"fehler": "Unbekannte Drehung."}
    o, _, uid = str(daten.get("pfad") or "").partition("/")
    name = name_aus_id(uid)
    if not (ORDNER_MUSTER.fullmatch(o) and o in app.archiv.ordner() and uid and url_id(name) == uid
            and app.archiv.datei(o, name)):
        return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
    try:
        groesse, mt = drehen(app, o, name, schritt)
    except DrehFehler as fehler:
        return 400, {"fehler": str(fehler)}
    except OSError as fehler:
        return 500, {"fehler": f"Drehen fehlgeschlagen ({fehler.strerror or fehler}) – das Foto ist unverändert."}
    _, eintrag = bogen_html(app, [(o, name, mt, groesse)], True)
    return 200, {"bild": eintrag[0], "klein": f"/t/{o}/{uid}?v={mt}", "meldung": MELDUNG[schritt] + "."}
