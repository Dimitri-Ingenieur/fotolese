"""fotolese.web.alben – Alben: Fotos frei einordnen, ein Foto in beliebig vielen Alben.

Gespeichert im Index (Tabellen album und album_bild, pfad wie überall „0012/<id>“). Gezählt und gefiltert werden
nur Fotos, die der Index kennt. Zuordnungen verschwundener Dateien bleiben stehen: Ein kurz nicht lesbares Laufwerk
löscht so nichts, und taucht die Datei wieder auf, steht sie wieder im Album.
"""
import re
import time

from fotolese.web.konst import ORDNER_MUSTER
from fotolese.web.konfig import bilder_text, name_aus_id, url_id
from fotolese.web.suche import suche_ausfuehren

MAX_BILDER = 20000  # je Anfrage
MAX_ANTWORT = 5000  # bis zu so vielen Fotos schickt die Antwort die neuen Alben je Foto mit


def alben_liste(index):
    """[{"id", "name", "n"}] nach Namen; n = Fotos des Albums, die im Index sind."""
    return [{"id": i, "name": n, "n": c} for i, n, c in index.q(
        "SELECT a.id, a.name, COUNT(b.pfad) FROM album a LEFT JOIN album_bild ab ON ab.album = a.id "
        "LEFT JOIN bild b ON b.pfad = ab.pfad GROUP BY a.id ORDER BY a.name COLLATE NOCASE, a.id")]


def alben_von(index, pfade):
    """{pfad: [Album-IDs]} – jeder Pfad kommt vor, ohne Album mit leerer Liste."""
    ergebnis = {p: [] for p in pfade}
    ordner = sorted({p[:4] for p in pfade})
    for k in range(0, len(ordner), 500):
        teil = ordner[k:k + 500]
        for pfad, album in index.q(f"SELECT pfad, album FROM album_bild WHERE substr(pfad, 1, 4) IN "
                                   f"({','.join('?' * len(teil))}) ORDER BY album", teil):
            if pfad in ergebnis:
                ergebnis[pfad].append(album)
    return ergebnis


def _sauber(roh):
    """Albumnamen säubern. Rückgabe: (Name, Fehlertext)."""
    name = re.sub(r"\s+", " ", str(roh or "")).strip()
    if not name:
        return None, "Bitte einen Namen eingeben."
    if len(name) > 60:
        return None, "Albumnamen höchstens 60 Zeichen lang."
    if "," in name or ";" in name:
        return None, "Albumnamen ohne Komma und Semikolon – sie trennen Begriffe im Filter."
    return name, None


def _gleichnamig(db, name, ausser=None):
    """ID eines anderen Albums mit gleichem Namen (Groß-/Kleinschreibung egal, auch Umlaute) oder None."""
    k = name.casefold()
    return next((i for i, n in db.execute("SELECT id, name FROM album") if n.casefold() == k and i != ausser), None)


def _pfade(app, roh):
    """Pfade „0012/<id>“ prüfen: nur Bilder, die wirklich im Archiv liegen. Rückgabe: Liste oder None."""
    if not isinstance(roh, list) or not 1 <= len(roh) <= MAX_BILDER:
        return None
    liste, namen, pfade = set(app.archiv.ordner()), {}, []
    for p in roh:
        o, _, uid = str(p).partition("/")
        if not ORDNER_MUSTER.fullmatch(o) or o not in liste or not uid:
            return None
        if o not in namen:
            namen[o] = {url_id(n) for n, _, _ in app.archiv.bilder(o)}
        if uid not in namen[o] or url_id(name_aus_id(uid)) != uid:
            return None
        pfade.append(f"{o}/{uid}")
    return list(dict.fromkeys(pfade))


def _anzahl(db, album):
    return db.execute("SELECT COUNT(*) FROM album_bild ab JOIN bild b ON b.pfad = ab.pfad WHERE ab.album=?",
                      (album,)).fetchone()[0]


def album_api(app, pfad, daten):
    """/api/album: anlegen, umbenennen, löschen. /api/album_bild: Fotos ins Album aufnehmen oder herausnehmen."""
    with app.index.lock:
        db = app.index.db
        if pfad == "/api/album":
            code, antwort = _album_aendern(db, daten)
        else:
            code, antwort = _zuordnen(app, db, daten)
        if code == 200:
            antwort["alben"] = alben_liste(app.index)
        return code, antwort


def _album_aendern(db, daten):
    aktion = daten.get("aktion")
    if aktion == "neu":
        name, fehler = _sauber(daten.get("name"))
        if fehler:
            return 400, {"fehler": fehler}
        vorhanden = _gleichnamig(db, name)
        if vorhanden:
            name = db.execute("SELECT name FROM album WHERE id=?", (vorhanden,)).fetchone()[0]
            return 200, {"album": vorhanden, "name": name, "meldung": f"Album „{name}“ gibt es schon."}
        neu = db.execute("INSERT INTO album(name, angelegt) VALUES(?, ?)",
                         (name, time.strftime("%Y-%m-%d %H:%M:%S"))).lastrowid
        db.commit()
        return 200, {"album": neu, "name": name, "meldung": f"Album „{name}“ angelegt."}
    try:
        album = int(daten.get("id"))
    except (TypeError, ValueError):
        return 400, {"fehler": "Ungültiges Album."}
    alt = db.execute("SELECT name FROM album WHERE id=?", (album,)).fetchone()
    if not alt:
        return 404, {"fehler": "Album nicht gefunden. Seite neu laden."}
    if aktion == "umbenennen":
        name, fehler = _sauber(daten.get("name"))
        if fehler:
            return 400, {"fehler": fehler}
        anderes = _gleichnamig(db, name, album)
        if anderes:
            vorhanden = db.execute("SELECT name FROM album WHERE id=?", (anderes,)).fetchone()[0]
            return 409, {"fehler": f"Ein Album „{vorhanden}“ gibt es schon."}
        db.execute("UPDATE album SET name=? WHERE id=?", (name, album))
        db.commit()
        return 200, {"album": album, "name": name, "meldung": f"Das Album heißt jetzt „{name}“."}
    if aktion == "loeschen":
        n = _anzahl(db, album)
        db.execute("DELETE FROM album_bild WHERE album=?", (album,))
        db.execute("DELETE FROM album WHERE id=?", (album,))
        db.commit()
        return 200, {"meldung": f"Album „{alt[0]}“ gelöscht. Die {bilder_text(n)} darin bleiben im Archiv."
                     if n else f"Album „{alt[0]}“ gelöscht."}
    return 400, {"fehler": "Unbekannte Aktion."}


def _zuordnen(app, db, daten):
    """daten: {"album": ID, "an": true|false} und die Fotos als {"pfade": […]}, {"ordner": "0012"}
    oder {"suche": "2023, Leipzig"} (alle Treffer des Filters)."""
    try:
        album = int(daten.get("album"))
    except (TypeError, ValueError):
        return 400, {"fehler": "Ungültiges Album."}
    z = db.execute("SELECT name FROM album WHERE id=?", (album,)).fetchone()
    if not z:
        return 404, {"fehler": "Album nicht gefunden. Seite neu laden."}
    name, an = z[0], bool(daten.get("an"))
    if daten.get("suche") is not None:
        pfade = [f"{o}/{uid}" for o, uid, *_ in suche_ausfuehren(app, str(daten["suche"]))[0]]
        if not pfade:
            return 404, {"fehler": "Zu diesem Filter gibt es keine Fotos."}
    elif daten.get("ordner") is not None:
        ordner = str(daten["ordner"])
        if not ORDNER_MUSTER.fullmatch(ordner) or ordner not in app.archiv.ordner():
            return 404, {"fehler": "Ordner nicht gefunden."}
        pfade = [f"{ordner}/{url_id(n)}" for n, _, _ in app.archiv.bilder(ordner)]
        if not pfade:
            return 404, {"fehler": "In diesem Ordner liegen keine Bilder."}
    else:
        pfade = _pfade(app, daten.get("pfade"))
        if pfade is None:
            return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
    zeilen = [(album, p) for p in pfade]
    if an:
        n = db.executemany("INSERT OR IGNORE INTO album_bild(album, pfad) VALUES(?, ?)", zeilen).rowcount
    else:
        n = db.executemany("DELETE FROM album_bild WHERE album=? AND pfad=?", zeilen).rowcount
    db.commit()
    if len(pfade) == 1:
        text = (f"Im Album „{name}“." if an else f"Aus dem Album „{name}“ genommen.") if n else \
            (f"Steht schon im Album „{name}“." if an else f"War nicht im Album „{name}“.")
    elif an:
        schon = len(pfade) - n
        text = f"{bilder_text(n)} ins Album „{name}“ aufgenommen" + (
            f", {schon} {'stand' if schon == 1 else 'standen'} schon darin." if schon else ".")
    else:
        text = f"{bilder_text(n)} aus dem Album „{name}“ genommen."
    antwort = {"meldung": text, "geaendert": n}
    if len(pfade) <= MAX_ANTWORT:
        antwort["a"] = alben_von(app.index, pfade)
    else:
        antwort["neu_laden"] = True
    return 200, antwort
