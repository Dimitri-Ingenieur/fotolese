"""fotolese.web.papierkorb – Fotos in den Papierkorb SORTIERT/Musor schieben und wieder zurückholen.

Endgültig gelöscht wird über die Weboberfläche nie: Der Papierkorb ist ein gewöhnlicher Ordner, den man bei
Bedarf im Dateimanager leert. Ein Foto wandert samt NEF und Begleitdateien (.xmp, .pp3) nach
Musor/<Ordner>/ (eine verbesserte Fassung nach Musor/<Ordner>/verbessert/); Musor/liste.csv vermerkt,
woher es kam. Fotos mit Stern lassen sich nicht wegwerfen –
erst den Stern entfernen. Die Einträge im Index räumt der Indexer beim nächsten Durchlauf auf; bis dahin
bleiben Namen, Jahr und Alben stehen, so dass „Rückgängig“ alles zurückbringt.
"""
import csv
import errno
import os
import secrets
import shutil
import threading
import time
from collections import OrderedDict

from fotolese.web.konst import ORDNER_MUSTER, PAPIERKORB
from fotolese.web.konfig import anzeige, name_aus_id, url_id

_LOCK = threading.Lock()
_ZULETZT = OrderedDict()  # Rückgängig-Schlüssel -> (Ordner, [(Name im Ordner, Name im Papierkorb)])
MAX_MERKEN = 500


def korb_pfad(app):
    return os.path.join(app.archiv.pfad, PAPIERKORB)


def _mitwandern(app, ordner, name):
    """Dateinamen, die mit dem Foto wandern: das Foto selbst, die NEF gleichen Namens und Begleitdateien
    (.xmp/.pp3, Groß-/Kleinschreibung egal). NEF und NAME.xmp bleiben, wenn ein anderes Bild denselben
    Namensstamm hat (z. B. IMG_1.JPG und IMG_1.PNG) – es braucht sie noch."""
    stamm = os.path.splitext(name)[0].casefold()
    geteilt = any(n != name and os.path.splitext(n)[0].casefold() == stamm for n, _, _ in app.archiv.bilder(ordner))
    roh = None if geteilt else app.archiv.roh(ordner).get(stamm)
    haupt = [name] + ([roh[0]] if roh else [])
    gesucht = {h.casefold() + endung for h in haupt for endung in (".xmp", ".pp3")}
    if not geteilt:
        gesucht.add(stamm + ".xmp")
    try:
        begleit = sorted(d.name for d in os.scandir(os.path.join(app.archiv.pfad, ordner))
                         if d.name.casefold() in gesucht and d.is_file(follow_symlinks=False))
    except OSError:
        begleit = []
    return haupt + begleit


def _rest(name, stamm):
    """Was nach dem Namensstamm kommt: „IMG_1.NEF“ -> „.NEF“, „img_1.JPG.xmp“ -> „.JPG.xmp“."""
    k = next((i for i in range(len(name) + 1) if name[:i].casefold() == stamm.casefold()), 0)
    return name[k:]


def _freie_namen(ziel, namen, stamm):
    """Im Papierkorb nichts überschreiben: belegt -> alle Dateien der Gruppe mit „ (2)“, „ (3)“ … am Namensstamm."""
    for k in range(1, 10000):
        neu = namen if k == 1 else [f"{stamm} ({k})" + _rest(n, stamm) for n in namen]
        if not any(os.path.lexists(os.path.join(ziel, n)) for n in neu):
            return list(zip(namen, neu))
    raise OSError(errno.EEXIST, "kein freier Name im Papierkorb")


def _bewegen(quelle, ziel):
    if os.path.lexists(ziel):  # os.rename würde unter Linux stillschweigend überschreiben
        raise OSError(errno.EEXIST, "Ziel existiert schon", ziel)
    os.makedirs(os.path.dirname(ziel), exist_ok=True)  # verbesserte Fassungen: …/verbessert/<Datei>
    try:
        os.rename(quelle, ziel)
    except OSError as fehler:
        if fehler.errno != errno.EXDEV:
            raise
        shutil.move(quelle, ziel)  # anderes Laufwerk (eingehängter Ordner): kopieren, dann Quelle entfernen


def _alle_bewegen(paare, von, nach):
    """Alle oder keine: misslingt eine Datei, wandern die schon verschobenen zurück."""
    erledigt = []
    try:
        for a, b in paare:
            _bewegen(os.path.join(von, a), os.path.join(nach, b))
            erledigt.append((a, b))
    except OSError:
        for a, b in reversed(erledigt):
            try:
                _bewegen(os.path.join(nach, b), os.path.join(von, a))
            except OSError:
                pass
        raise


def _protokoll(app, aktion, ordner, paare):
    pfad = os.path.join(korb_pfad(app), "liste.csv")
    try:
        neu = not os.path.exists(pfad)
        with open(pfad, "a", newline="", encoding="utf-8", errors="surrogateescape") as f:
            w = csv.writer(f)
            if neu:
                w.writerow(["zeit", "aktion", "archiv", "papierkorb"])
            for a, b in paare:
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), aktion, f"{ordner}/{a}", f"{PAPIERKORB}/{ordner}/{b}"])
    except OSError:
        pass  # Protokoll ist Komfort – das Verschieben selbst ist gelungen


def wegwerfen(app, pfad):
    o, _, uid = str(pfad or "").partition("/")
    name = name_aus_id(uid)
    if not (ORDNER_MUSTER.fullmatch(o) and o in app.archiv.ordner() and uid and url_id(name) == uid):
        return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
    if name in app.auswahl.markiert(o):
        return 409, {"fehler": "Das Bild hat einen Stern – erst den Stern entfernen, dann in den Papierkorb."}
    ordner_pfad, ziel = os.path.join(app.archiv.pfad, o), os.path.join(korb_pfad(app), o)
    with _LOCK:
        if not app.archiv.datei(o, name) or not os.path.isfile(os.path.join(ordner_pfad, name)):
            return 404, {"fehler": "Bild nicht gefunden – liegt es schon im Papierkorb? Seite neu laden."}
        try:
            os.makedirs(ziel, exist_ok=True)
            paare = _freie_namen(ziel, _mitwandern(app, o, name), os.path.splitext(name)[0])
            _alle_bewegen(paare, ordner_pfad, ziel)
        except OSError as fehler:
            return 500, {"fehler": f"Verschieben in den Papierkorb fehlgeschlagen: {fehler.strerror or fehler}. "
                                   f"Das Foto bleibt, wo es war."}
        _protokoll(app, "Papierkorb", o, paare)
        schluessel = secrets.token_urlsafe(12)
        _ZULETZT[schluessel] = (o, paare)
        while len(_ZULETZT) > MAX_MERKEN:
            _ZULETZT.popitem(last=False)
    app.archiv.bilder(o, frisch=True)
    app.auswahl.bereinigen(o)  # falls gerade jemand einen Stern gesetzt hat: Kopie in BestOf abgleichen
    mit = [anzeige(a) for a, _ in paare[1:]]
    return 200, {"meldung": f"{anzeige(name)}{' (mit ' + ', '.join(mit) + ')' if mit else ''} liegt jetzt im "
                            f"Papierkorb {PAPIERKORB}/{o}.", "rueck": schluessel}


def zurueckholen(app, schluessel):
    schluessel = str(schluessel or "")
    with _LOCK:
        eintrag = _ZULETZT.get(schluessel)
        if not eintrag:
            return 404, {"fehler": f"Zurückholen geht nicht mehr – das Foto liegt im Ordner {PAPIERKORB}."}
        o, paare = eintrag
        korb, ordner_pfad = os.path.join(korb_pfad(app), o), os.path.join(app.archiv.pfad, o)
        if any(os.path.lexists(os.path.join(ordner_pfad, a)) for a, _ in paare):
            return 409, {"fehler": f"Im Ordner {o} liegt inzwischen eine Datei gleichen Namens – bitte von Hand aus "
                                   f"{PAPIERKORB}/{o} holen."}
        try:
            os.makedirs(ordner_pfad, exist_ok=True)
            _alle_bewegen([(b, a) for a, b in paare], korb, ordner_pfad)
        except OSError as fehler:
            return 500, {"fehler": f"Zurückholen fehlgeschlagen: {fehler.strerror or fehler}."}
        del _ZULETZT[schluessel]
        _protokoll(app, "zurück", o, paare)
    app.archiv.ordner(frisch=True)
    app.archiv.bilder(o, frisch=True)
    return 200, {"meldung": f"{anzeige(paare[0][0])} ist zurück in Ordner {o}."}


def umzug_laeuft(app):
    """Werden gerade Ordner zusammengefasst oder neu gruppiert? Dann warten Papierkorb und Verbessern."""
    a = getattr(app, "auftrag", None)
    return a is not None and a.status.get("laeuft") and a.status.get("art") in ("zusammenfassen", "gruppieren",
                                                                                  "umzug_rueck", "verschieben")


def papierkorb_api(app, daten):
    if umzug_laeuft(app):
        return 409, {"fehler": "Gerade werden Ordner umsortiert – bitte einen Moment warten."}
    if daten.get("rueck") is not None:
        return zurueckholen(app, daten["rueck"])
    return wegwerfen(app, daten.get("pfad"))
