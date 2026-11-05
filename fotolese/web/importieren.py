"""fotolese.web.importieren – Ordner über fotosort ins Archiv kopieren, Duplikate bereinigen, Ordnerwahl.

(Modulname nicht 'import', das ist ein Schlüsselwort.) Auftrag startet fotosort.py als
Unterprozess und liest dessen Fortschritt (#FS-Zeilen).
"""
import csv
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from fotolese.gemein import sha256 as _sha256
from fotolese.web.konst import BILD_EXT, ORDNER_MUSTER, PAPIERKORB
from fotolese.web.konfig import anzeige, bilder_text, e, groesse_text, natuerlich, url_id
from fotolese.web.html import import_frei, kopf, seite
from fotolese.web.alben import _sauber, album_anlegen, alben_liste
from fotolese.web.papierkorb import korb_pfad


FOTO_EXT = {".jpg", ".jpeg", ".png", ".nef"}
OHNE_ORDNER = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found"}


def papierkorb_inhalt(app):
    """(Dateien, Bytes) im Papierkorb Musor – weggeworfene Fotos und überzählige Duplikate – und
    (Dateien, Bytes) im alten Duplikat-Papierkorb .duplikate früherer Versionen."""
    ergebnis = []
    for wurzel in (korb_pfad(app), os.path.join(app.archiv.pfad, ".duplikate")):
        anzahl, groesse = 0, 0
        for ort, _, dateien in os.walk(wurzel):
            for d in dateien:
                if not d.endswith(".csv"):
                    try:
                        groesse += os.path.getsize(os.path.join(ort, d))
                        anzahl += 1
                    except OSError:
                        pass
        ergebnis += [anzahl, groesse]
    return ergebnis


def duplikate_bereinigen(app, auftrag=None):
    """Inhaltsgleiche Dateien (SHA-256) in den Ordnern 0001–99999 auf eine reduzieren. Die übrigen kommen in den
    Papierkorb SORTIERT/Musor/Duplikate/<Zeit>/ (mit liste.csv). Behalten wird zuerst die mit Stern (in BestOf),
    dann eine mit Ihren Labels (Namen, Jahr, Alben), dann die ohne Laufindex im Namen, dann die im kleinsten Ordner.
    Geprüft werden nur Dateien gleicher Größe; Prüfsummen merkt sich der Index."""
    st = auftrag.status if auftrag else {}
    archiv = app.archiv.pfad
    st.update(phase="Doppelte Dateien im Archiv suchen", fertig=0, gesamt=0, zusatz="")
    dateien = []
    for o in app.archiv.ordner(frisch=True):
        try:
            for d in os.scandir(os.path.join(archiv, o)):
                if (d.name.startswith(".") or os.path.splitext(d.name)[1].lower() not in FOTO_EXT
                        or not d.is_file(follow_symlinks=False)):
                    continue
                s_ = d.stat(follow_symlinks=False)
                dateien.append((o, d.name, s_.st_size, s_.st_mtime_ns))
        except OSError:
            continue
    nach_groesse = defaultdict(list)
    for d in dateien:
        nach_groesse[d[2]].append(d)
    kandidaten = [d for g in nach_groesse.values() if len(g) > 1 for d in g]
    bekannt = ({(p_, g, m): sha for p_, g, m, sha in app.index.q("SELECT pfad, groesse, mtime, sha FROM pruefsumme")}
               if app.index else {})
    shas, offen = {}, []
    for d in kandidaten:
        sha = bekannt.get((f"{d[0]}/{url_id(d[1])}", d[2], d[3]))
        if sha:
            shas[d[:2]] = sha
        else:
            offen.append(d)
    st.update(phase="Prüfsummen im Archiv", gesamt=len(offen))
    neu = []
    if offen:
        with ThreadPoolExecutor(max(1, min(app.import_jobs, 8))) as ex:
            zukunft = {ex.submit(_sha256, os.path.join(archiv, d[0], d[1])): d for d in offen}
            for k, f in enumerate(as_completed(zukunft), 1):
                d = zukunft[f]
                try:
                    shas[d[:2]] = f.result()
                    neu.append((f"{d[0]}/{url_id(d[1])}", d[2], d[3], shas[d[:2]]))
                except OSError:
                    pass
                st["fertig"] = k
    if app.index and neu:
        with app.index.lock:
            app.index.db.executemany("INSERT OR REPLACE INTO pruefsumme VALUES(?,?,?,?)", neu)
            app.index.db.commit()
    gleich = defaultdict(list)
    for d in kandidaten:
        if d[:2] in shas:
            gleich[shas[d[:2]]].append(d)
    gruppen = [g for g in gleich.values() if len(g) > 1]
    if not gruppen:
        return {"meldung": "Keine doppelten Dateien im Archiv.", "verschoben": 0}
    markiert = {(o, m) for o in {d[0] for g in gruppen for d in g} for m in app.auswahl.markiert(o)}
    gelabelt = ({r[0] for r in app.index.q("SELECT pfad FROM gesicht WHERE manuell=1 AND person IS NOT NULL "
                                           "UNION SELECT pfad FROM jahr_manuell UNION SELECT pfad FROM album_bild")}
                if app.index else set())

    def rang(d, gruppe):
        o, n = d[0], d[1]
        m = re.fullmatch(r"(.+)_\d+", os.path.splitext(n)[0])  # IMG_0001_1.JPG neben IMG_0001.JPG = Laufindex
        laufindex = bool(m) and any(os.path.splitext(x[1])[0].casefold() == m.group(1).casefold()
                                    for x in gruppe if x is not d)
        return (0 if (o, n) in markiert else 1, 0 if f"{o}/{url_id(n)}" in gelabelt else 1,
                1 if laufindex else 0, o, len(n), n)

    korb = os.path.join(korb_pfad(app), "Duplikate", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(korb, exist_ok=True)
    verschoben, weg_bytes, betroffen, fehler = 0, 0, set(), 0
    with open(os.path.join(korb, "liste.csv"), "w", newline="", encoding="utf-8", errors="surrogateescape") as f:
        w = csv.writer(f)
        w.writerow(["sha256", "behalten", "verschoben", "bytes"])
        for g in gruppen:
            g.sort(key=lambda d: rang(d, g))
            behalten = g[0]
            for d in g[1:]:
                quellordner, zielordner = os.path.join(archiv, d[0]), os.path.join(korb, d[0])
                stamm = os.path.splitext(d[1])[0]
                begleit = [n for n in (d[1] + ".xmp", d[1] + ".pp3")
                           + ((stamm + ".xmp",) if d[1].lower().endswith(".nef") else ())
                           if os.path.isfile(os.path.join(quellordner, n))]
                try:
                    os.makedirs(zielordner, exist_ok=True)
                    os.rename(os.path.join(quellordner, d[1]), os.path.join(zielordner, d[1]))  # gleiche Platte
                    for n in begleit:
                        os.rename(os.path.join(quellordner, n), os.path.join(zielordner, n))
                except OSError:
                    fehler += 1
                    continue
                w.writerow([shas[d[:2]], f"{behalten[0]}/{behalten[1]}", f"{d[0]}/{d[1]}", d[2]])
                verschoben += 1
                weg_bytes += d[2]
                betroffen.add(d[0])
                if app.index:  # von Hand gesetztes Jahr und Alben auf die behaltene Datei übertragen
                    neu_p, alt_p = f"{behalten[0]}/{url_id(behalten[1])}", f"{d[0]}/{url_id(d[1])}"
                    with app.index.lock:
                        db = app.index.db
                        db.execute("INSERT OR IGNORE INTO jahr_manuell SELECT ?, jahr FROM jahr_manuell WHERE pfad=?",
                                   (neu_p, alt_p))
                        db.execute("INSERT OR IGNORE INTO album_bild(album, pfad) SELECT album, ? FROM album_bild "
                                   "WHERE pfad=?", (neu_p, alt_p))
                        db.execute("DELETE FROM album_bild WHERE pfad=?", (alt_p,))
                        db.commit()
    for o in betroffen:
        app.auswahl.bereinigen(o)
        try:
            os.rmdir(os.path.join(archiv, o))  # nur wenn der Ordner jetzt ganz leer ist
        except OSError:
            pass
    app.archiv.ordner(frisch=True)
    text = (f"Doppelte Dateien im Archiv: {verschoben} in den Papierkorb {PAPIERKORB}/Duplikate verschoben "
            f"({groesse_text(weg_bytes)}), "
            f"von jedem Inhalt bleibt genau eine Datei." + (f" {fehler} ließen sich nicht verschieben." if fehler else ""))
    return {"meldung": text, "verschoben": verschoben, "bytes": weg_bytes}


def _bilder_im_archiv(app, pfade):
    """Absolute Pfade (fotosort-Protokoll, gemeldete Duplikate) -> „0012/<id>“ der angezeigten Bilder, ohne
    Doppelte. Zu einer NEF zählt das JPG/PNG gleichen Namens im selben Ordner; was nicht direkt in einem
    Ordner 0001–99999 liegt, fällt weg (z. B. ein Duplikat innerhalb der Quelle)."""
    archiv, je_ordner, ergebnis = os.path.abspath(app.archiv.pfad), {}, []
    for p in pfade:
        try:
            o, _, name = os.path.relpath(os.path.abspath(p), archiv).partition(os.sep)
        except ValueError:  # anderes Laufwerk (Windows)
            continue
        if not ORDNER_MUSTER.fullmatch(o) or not name or os.sep in name:
            continue
        if o not in je_ordner:
            namen = [n for n, _, _ in app.archiv.bilder(o, frisch=True)]
            je_ordner[o] = (set(namen), {os.path.splitext(n)[0].casefold(): n for n in namen})
        da, je_stamm = je_ordner[o]
        if name not in da:
            name = (je_stamm.get(os.path.splitext(name)[0].casefold())
                    if os.path.splitext(name)[1].lower() not in BILD_EXT else None)
        if name:
            ergebnis.append(f"{o}/{url_id(name)}")
    return list(dict.fromkeys(ergebnis))


def gruppen_umgebung(app, werte=None):
    """Ähnlichkeitswerte für fotosort (Import, Neu-Gruppierung, Analyse) – aus den Einstellungen oder werte."""
    w = dict(app.gruppe, **(werte or {}))
    return {"SCHWELLE": str(int(w["SCHWELLE"])), "SERIE_SEK": f"{float(w['SERIE_SEK']):g}",
            "SERIE_SCHWELLE": str(int(w["SERIE_SCHWELLE"])), "EINZELN": str(w["EINZELN"])}


def fotosort_lauf(app, argumente, umgebung, status, halter, text_zeile=None, json_zeile=None):
    """fotosort.py als Unterprozess. Fortschritt (#FS-Zeilen mit „titel“) kommt nach status, andere #FS-Zeilen
    an json_zeile, die übrige Ausgabe zeilenweise an text_zeile. halter.proc ist der Prozess (zum Abbrechen).
    Rückgabe: Exit-Code."""
    env = dict(os.environ, **umgebung, JA="1", FORTSCHRITT_JSON="1", PYTHONUNBUFFERED="1")
    halter.proc = subprocess.Popen([sys.executable, "-u", app.fotosort, *argumente], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, text=True,
                                   encoding="utf-8", errors="replace", bufsize=1)
    for zeile in halter.proc.stdout:
        zeile = zeile.rstrip("\n")
        if zeile.startswith("#FS "):
            try:
                d = json.loads(zeile[4:])
            except ValueError:
                continue
            if "titel" in d:
                status.update(phase=d.get("titel", ""), fertig=d.get("fertig", 0), gesamt=d.get("gesamt", 0),
                              zusatz=d.get("zusatz", ""))
            elif json_zeile:
                json_zeile(d)
            continue
        if text_zeile:
            text_zeile(zeile)
    return halter.proc.wait()


class Auftrag(threading.Thread):
    """Import (fotosort.py, Modus copy, mit Duplikatprüfung), Rückgängig oder Duplikatsuche – einer zur Zeit.
    Mit album kommen alle Fotos eines Imports in dieses Album, auch die schon vorhandenen gleichen Inhalts."""

    def __init__(self, app, art, ziel=None, album=None, album_rueck=None):
        super().__init__(daemon=True)
        self.app, self.art, self.ziel = app, art, ziel
        self.proc, self.abbruch = None, False
        self.album = album  # Import: Name des Albums (schon gesäubert) oder None
        self.album_zeilen = None  # nach dem Import: (Album-ID, neu eingetragene Pfade, Album neu angelegt?)
        self.album_rueck = album_rueck  # Rückgängig: album_zeilen des Imports
        self.doppelt = []  # von fotosort gemeldet: [Quelle, Datei gleichen Inhalts]
        self.status = {"art": art, "ziel": ziel, "laeuft": True, "phase": "Start", "fertig": 0, "gesamt": 0,
                       "zusatz": "", "log": [], "ergebnis": "", "fehler": "", "protokoll": None,
                       "start": time.time(), "ende": None, "album": album, "album_n": 0}

    def _zeile(self, text):
        self.status["log"] = (self.status["log"] + [text])[-400:]

    def _fotosort(self, argumente, umgebung):
        def json_zeile(d):
            if "doppelt" in d:
                self.doppelt.append(d["doppelt"])

        def text_zeile(zeile):
            if zeile.startswith("Protokoll: ") and self.art == "import":
                self.status["protokoll"] = zeile[11:].strip()
            if zeile.strip():
                self._zeile(zeile)

        return fotosort_lauf(self.app, argumente, umgebung, self.status, self, text_zeile, json_zeile)

    def run(self):
        app, st = self.app, self.status
        try:
            if self.art == "import":
                code = self._fotosort([self.ziel, app.archiv.pfad],
                                      {"MODUS": "copy", "DUPLIKATE": "1", "JOBS": str(app.import_jobs),
                                       **gruppen_umgebung(app)})
                wichtig = [z for z in st["log"] if z.startswith(("Gefunden:", "Duplikate:", "Gruppen:", "Ergänzt:",
                                                                 "JPG aus NEF:", "Fertig in", "Alle Bilder sind",
                                                                 "Keine Bilder", "Nichts zu", "Abbruch", "ABGEBROCHEN"))]
                if self.album and app.index:  # vor der Bereinigung: die gibt Alben an die behaltene Datei weiter
                    wichtig.append(self._album_zuordnen())
                if self.abbruch:
                    st["fehler"] = "Abgebrochen. Schon Kopiertes bleibt im Archiv – „Import rückgängig“ entfernt es."
                elif code:
                    st["fehler"] = (st["log"][-1] if st["log"] else "fotosort meldet einen Fehler.")
                else:
                    wichtig.append(duplikate_bereinigen(app, self)["meldung"])
                st["ergebnis"] = "\n".join(wichtig)
            elif self.art == "rueckgaengig":
                code = self._fotosort([self.ziel], {"MODUS": "undo"})
                st["ergebnis"] = "\n".join(z for z in st["log"] if z.startswith(("Fertig", "Nichts zu tun")))
                if code:
                    st["fehler"] = st["log"][-1] if st["log"] else "Rückgängig fehlgeschlagen."
                elif self.album_rueck and app.index:
                    st["ergebnis"] = "\n".join(filter(None, [st["ergebnis"], self._album_zuruecknehmen()]))
            else:
                st["ergebnis"] = duplikate_bereinigen(app, self)["meldung"]
        except Exception as fehler:
            traceback.print_exc()
            st["fehler"] = f"{type(fehler).__name__}: {fehler}"
        finally:
            st.update(laeuft=False, ende=time.time(), phase="Fehler" if st["fehler"] else "Fertig")
            app.archiv.ordner(frisch=True)
            if app.indexer:
                app.indexer.weiter.set()  # neue Bilder gleich einlesen
            art = {"import": "Import", "rueckgaengig": "Rückgängig", "duplikate": "Duplikate"}[self.art]
            print(f"{art}: {st['fehler'] or (st['ergebnis'].splitlines() or ['fertig'])[-1]}", flush=True)

    def _album_zuordnen(self):
        """Fotos dieses Imports ins gewählte Album: die neu kopierten (Protokoll: kopiert, erzeugte JPG) und die
        schon vorhandenen gleichen Inhalts, die fotosort übersprungen hat."""
        app, st = self.app, self.status
        neu = []
        if st["protokoll"] and os.path.isfile(st["protokoll"]):
            with open(st["protokoll"], newline="", encoding="utf-8", errors="surrogateescape") as f:
                neu = [z["ziel"] for z in csv.DictReader(f) if z.get("ziel") and (z.get("status") or "").split(" ")[0]
                       in ("kopiert", "erzeugt", "verschoben", "verlinkt")]
        neu = _bilder_im_archiv(app, neu)
        schon = [p for p in _bilder_im_archiv(app, [g for _, g in self.doppelt]) if p not in set(neu)]
        if not neu and not schon:
            return f"Album „{self.album}“: kein Foto aus diesem Import im Archiv."
        with app.index.lock:
            db = app.index.db
            album, name, angelegt = album_anlegen(db, self.album)
            vorher = {r[0] for r in db.execute("SELECT pfad FROM album_bild WHERE album=?", (album,))}
            dazu = [p for p in neu + schon if p not in vorher]
            db.executemany("INSERT OR IGNORE INTO album_bild(album, pfad) VALUES(?, ?)", [(album, p) for p in dazu])
            db.commit()
        self.album_zeilen = (album, dazu, angelegt)
        st.update(album=name, album_n=len(neu) + len(schon))
        return (f"Album „{name}“{' (neu angelegt)' if angelegt else ''}: {bilder_text(len(neu) + len(schon))} "
                f"zugeordnet" + (f", davon {len(schon)} schon vorher im Archiv" if schon else "") + ".")

    def _album_zuruecknehmen(self):
        """Rückgängig: die Zuordnungen des Imports wieder entfernen; ein dafür neu angelegtes Album verschwindet,
        wenn es danach leer ist."""
        album, pfade, angelegt = self.album_rueck
        with self.app.index.lock:
            db = self.app.index.db
            z = db.execute("SELECT name FROM album WHERE id=?", (album,)).fetchone()
            if not z:
                return ""
            db.executemany("DELETE FROM album_bild WHERE album=? AND pfad=?", [(album, p) for p in pfade])
            leer = angelegt and not db.execute("SELECT 1 FROM album_bild WHERE album=? LIMIT 1", (album,)).fetchone()
            if leer:
                db.execute("DELETE FROM album WHERE id=?", (album,))
            db.commit()
        return (f"Album „{z[0]}“ wieder gelöscht – es war für diesen Import angelegt." if leer
                else f"Album „{z[0]}“: {bilder_text(len(pfade))} wieder herausgenommen.")

    def abbrechen(self):
        self.abbruch = True
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)  # fotosort beendet den laufenden Ordner sauber


def _im_archiv(app, pfad):
    echt, archiv = os.path.realpath(pfad), os.path.realpath(app.archiv.pfad)
    return echt == archiv or echt.startswith(archiv + os.sep)


def ordner_liste(app, pfad):
    """Ordnerwahl im Browser: Unterordner (ohne versteckte), Brotkrumen, Schnellzugriffe."""
    heim = os.path.expanduser("~")
    pfad = os.path.abspath(os.path.expanduser(pfad or "")) if pfad else heim
    while not os.path.isdir(pfad) and os.path.dirname(pfad) != pfad:
        pfad = os.path.dirname(pfad)
    unter, fotos, lesbar = [], 0, True
    try:
        for d in os.scandir(pfad):
            if d.name.startswith(".") or d.name in OHNE_ORDNER:
                continue
            try:
                if d.is_dir():
                    unter.append(d.name)
                elif os.path.splitext(d.name)[1].lower() in FOTO_EXT and d.is_file():
                    fotos += 1
            except OSError:
                continue
    except OSError:
        lesbar = False
    unter.sort(key=natuerlich)
    teile, weg = [], pfad
    while True:
        teile.append([anzeige(os.path.basename(weg) or weg), weg])
        if os.path.dirname(weg) == weg:
            break
        weg = os.path.dirname(weg)
    teile.reverse()
    schnell = [["Persönlicher Ordner", heim]]
    for n in ("Bilder", "Pictures", "Fotos"):
        if os.path.isdir(os.path.join(heim, n)):
            schnell.append([n, os.path.join(heim, n)])
    nutzer = os.environ.get("USER") or os.path.basename(heim)
    for wurzel in (f"/media/{nutzer}", f"/run/media/{nutzer}", "/mnt", "/media"):
        try:
            for d in sorted(os.scandir(wurzel), key=lambda d: d.name):
                if d.is_dir() and not d.name.startswith(".") and d.path not in (s_[1] for s_ in schnell):
                    schnell.append([f"Laufwerk {anzeige(d.name)}", d.path])
        except OSError:
            pass
    return {"pfad": pfad, "eltern": os.path.dirname(pfad) if os.path.dirname(pfad) != pfad else None,
            "teile": teile, "ordner": [[anzeige(n), os.path.join(pfad, n)] for n in unter], "fotos": fotos,
            "lesbar": lesbar, "im_archiv": _im_archiv(app, pfad), "schnell": schnell}


def fotos_zaehlen(pfad, archiv, frist=15.0):
    """Fotos unter pfad zählen (wie fotosort: ohne versteckte Ordner und ohne das Archiv)."""
    start, archiv_real = time.time(), os.path.realpath(archiv)
    zahl = defaultdict(int)
    groesse, ordner, fertig = 0, 0, True
    for wurzel, unter, dateien in os.walk(pfad):
        unter[:] = [u for u in unter if not u.startswith(".") and u not in OHNE_ORDNER
                    and os.path.realpath(os.path.join(wurzel, u)) != archiv_real]
        ordner += 1
        for n in dateien:
            endung = os.path.splitext(n)[1].lower()
            if endung in FOTO_EXT and not n.startswith("._"):
                try:
                    groesse += os.path.getsize(os.path.join(wurzel, n))
                    zahl[endung.lstrip(".").replace("jpeg", "jpg")] += 1
                except OSError:
                    pass
        if time.time() - start > frist:
            fertig = False
            break
    return {"anzahl": sum(zahl.values()), "arten": dict(zahl), "bytes": groesse, "ordner": ordner, "fertig": fertig}


def import_api(app, pfad, daten):
    if not import_frei(app):
        return 403, {"fehler": "Import geht nur an dem Rechner, auf dem bestof.py läuft."}
    laeuft = app.auftrag is not None and app.auftrag.status["laeuft"]
    if pfad == "/api/import/abbrechen":
        if not laeuft:
            return 409, {"fehler": "Es läuft nichts."}
        app.auftrag.abbrechen()
        return 200, {"meldung": "Abbruch angefordert."}
    if laeuft:
        return 409, {"fehler": "Es läuft schon ein Auftrag – bitte warten oder abbrechen."}
    if pfad in ("/api/import/zaehlen", "/api/import/start"):
        quelle = os.path.abspath(os.path.expanduser(str(daten.get("pfad") or "")))
        if not os.path.isdir(quelle):
            return 404, {"fehler": "Ordner nicht gefunden."}
        if _im_archiv(app, quelle):
            return 400, {"fehler": "Dieser Ordner liegt im Archiv – bitte einen anderen wählen."}
        if pfad == "/api/import/zaehlen":
            return 200, fotos_zaehlen(quelle, app.archiv.pfad)
        if not os.path.isfile(app.fotosort):
            return 500, {"fehler": f"fotosort.py fehlt: {app.fotosort}"}
        album = None
        if str(daten.get("album") or "").strip():
            if not app.index:
                return 400, {"fehler": "Alben gibt es nur mit Index (INDEX = 1)."}
            album, fehler = _sauber(daten.get("album"))
            if fehler:
                return 400, {"fehler": fehler}
        app.auftrag = Auftrag(app, "import", quelle, album=album)
    elif pfad == "/api/import/rueckgaengig":
        alt = app.auftrag
        letzte = alt.status if alt else {}
        protokoll = letzte.get("protokoll") if letzte.get("art") == "import" else None
        if not protokoll or not os.path.isfile(protokoll):
            return 404, {"fehler": "Kein Import-Protokoll gefunden."}
        app.auftrag = Auftrag(app, "rueckgaengig", protokoll, album_rueck=alt.album_zeilen)
    elif pfad == "/api/duplikate" and daten.get("aktion") == "suchen":
        app.auftrag = Auftrag(app, "duplikate")
    else:  # endgültig löschen gibt es über die Weboberfläche nicht – den Papierkorb leert man im Dateimanager
        return 404, {"fehler": "Unbekannt."}
    app.auftrag.start()
    return 200, {"meldung": "Gestartet."}


def import_seite(app):
    titel = ('<div class="titel"><h1>Import</h1><div><p>Fotos aus einem Ordner samt Unterordnern nach '
             f'{e(os.path.basename(app.archiv.pfad))} kopieren</p></div></div>')
    inhalt = kopf(app, "import", titel)
    if not app.import_erlaubt:
        inhalt += '<p class="leer">Die Seite „Import“ ist ausgeschaltet (IMPORT = 0 in bestof.conf).</p>'
        return seite("Import – BestOf", inhalt)
    if not import_frei(app):
        inhalt += ('<p class="leer">Importieren geht nur an dem Rechner, auf dem bestof.py läuft – dort im Browser '
                   f'<b>http://localhost:{app.port}</b> öffnen. Die Ordnerwahl zeigt die Laufwerke dieses Rechners; '
                   'aus dem Heimnetz bleibt sie deshalb gesperrt.</p>')
        return seite("Import – BestOf", inhalt)
    if not os.path.isfile(app.fotosort):
        inhalt += (f'<p class="leer">fotosort.py fehlt: {e(app.fotosort)}. Legen Sie fotosort.py neben bestof.py '
                   'oder setzen Sie FOTOSORT in bestof.conf.</p>')
        return seite("Import – BestOf", inhalt)
    album_feld = ""
    if app.index:
        vorschlaege = "".join(f'<option value="{e(a["name"])}">' for a in alben_liste(app.index))
        album_feld = ('<label class="albumwahl">Album (optional)<input id="album" class="pname" list="albenliste" '
                      'maxlength="60" autocomplete="off" spellcheck="false" placeholder="z. B. Urlaub 2023 – vorhanden '
                      f'oder neu"></label><datalist id="albenliste">{vorschlaege}</datalist>')
    inhalt += """<main class="import">
<section><h2>1. Ordner wählen</h2>
<form class="pfadzeile" id="pfadform"><input id="pfad" class="pname" spellcheck="false" autocomplete="off"
 aria-label="Ordner"><button class="knopf">Öffnen</button></form>
<nav class="krumen" id="krumen" aria-label="Pfad"></nav>
<div class="schnell" id="schnell"></div>
<ul class="ordnerliste" id="liste"></ul></section>
<section><h2>2. Kopieren</h2>
<p id="gewaehlt" class="leise"></p>""" + album_feld + """
<div class="knopfzeile"><button class="knopf" id="zaehlen" type="button">Fotos zählen</button>
<button class="knopf haupt" id="start" type="button">In Sortiert kopieren</button></div>
<p id="zahl" class="leise"></p>
<p class="hilfe0">Die Quelle bleibt unverändert. fotosort.py sortiert ähnliche Fotos in Ordner (ergänzt passende
bestehende), legt zu NEF ein JPG an und kopiert inhaltsgleiche Dateien (gleiche SHA-256-Prüfsumme) nur einmal.
Danach bleibt im ganzen Archiv von jedem Inhalt genau eine Datei; überzählige kommen in den Papierkorb
<code>""" + e(PAPIERKORB) + """/Duplikate</code>.""" + (""" Mit Album kommen alle Fotos des Imports hinein – auch
solche, die schon im Archiv liegen; ein neuer Name legt das Album an.""" if app.index else "") + """</p></section>
<section id="lauf" hidden><h2>Fortschritt</h2>
<p id="phase"></p><progress id="balken" max="1" value="0"></progress>
<p id="ergebnis" class="ergebnis"></p>
<div class="knopfzeile"><button class="knopf" id="abbrechen" type="button">Abbrechen</button>
<button class="knopf" id="rueck" type="button" hidden>Import rückgängig</button>
<a class="knopf" id="albumlink" hidden></a></div>
<details><summary>Protokoll</summary><pre id="log"></pre></details></section>
<section><h2>Doppelte Dateien im Archiv</h2>
<p id="korb" class="leise"></p>
<div class="knopfzeile"><button class="knopf" id="dupsuchen" type="button">Jetzt prüfen</button></div>
<p class="hilfe0">Endgültig gelöscht wird hier nie. Den Papierkorb – weggeworfene Fotos und Duplikate – leeren Sie
bei Bedarf im Dateimanager: Ordner <code>""" + e(korb_pfad(app)) + """</code>.</p></section>
</main>"""
    return seite("Import – BestOf", inhalt, f"const KORB={json.dumps(PAPIERKORB)};" + JS_IMPORT)


JS_IMPORT = """
const $=id=>document.getElementById(id);let aktuell=null,laeuft=false,zeitgeber=null;
function knopf(text,ziel,klasse){const b=document.createElement('button');b.type='button';b.className=klasse||'knopf';
 b.textContent=text;b.addEventListener('click',()=>oeffnen(ziel));return b;}
async function oeffnen(p){const r=await fetch('/api/ordner?pfad='+encodeURIComponent(p||''));let j={};
 try{j=await r.json();}catch(_){}
 if(!r.ok){meldung(j.fehler||'Ordner nicht lesbar.',true);return;}
 aktuell=j;$('pfad').value=j.pfad;try{localStorage.setItem('importPfad',j.pfad);}catch(_){}
 $('krumen').replaceChildren(...j.teile.map(([n,z])=>knopf(n,z,'krume')));
 $('schnell').replaceChildren(...j.schnell.map(([n,z])=>knopf(n,z,'knopf klein')));
 const li=[];if(j.eltern){const e=document.createElement('li');e.appendChild(knopf('↑ übergeordneter Ordner',j.eltern,'ordnerknopf'));li.push(e);}
 for(const [n,z] of j.ordner){const e=document.createElement('li');e.appendChild(knopf('📁 '+n,z,'ordnerknopf'));li.push(e);}
 if(!j.ordner.length){const e=document.createElement('li');e.className='leise';e.textContent=j.lesbar?'Keine Unterordner.':'Kein Zugriff auf diesen Ordner.';li.push(e);}
 $('liste').replaceChildren(...li);$('zahl').textContent='';
 $('gewaehlt').textContent=j.im_archiv?'Dieser Ordner liegt im Archiv – bitte einen anderen wählen.':
  'Gewählt: '+j.pfad+' – '+j.fotos+(j.fotos===1?' Foto':' Fotos')+' direkt hier, Unterordner kommen mit.';
 knoepfe();}
function knoepfe(){const frei=aktuell&&!aktuell.im_archiv&&aktuell.lesbar;
 $('start').disabled=laeuft||!frei;$('zaehlen').disabled=!frei;$('dupsuchen').disabled=laeuft;}
function gb(b){return b>=1e9?(b/1e9).toFixed(1).replace('.',',')+' GB':(b/1e6).toFixed(1).replace('.',',')+' MB';}
$('pfadform').addEventListener('submit',ev=>{ev.preventDefault();oeffnen($('pfad').value);});
$('zaehlen').addEventListener('click',async()=>{$('zahl').textContent='Zähle …';
 const [ok,j]=await post('/api/import/zaehlen',{pfad:aktuell.pfad});
 if(!ok){$('zahl').textContent=j.fehler||'Zählen fehlgeschlagen.';return;}
 const arten=Object.entries(j.arten).map(([k,v])=>k.toUpperCase()+' '+v).join(' · ');
 $('zahl').textContent=(j.fertig?'':'mindestens ')+j.anzahl+' Fotos'+(arten?' ('+arten+')':'')+', '+gb(j.bytes)+
  ' in '+j.ordner+' Ordnern'+(j.fertig?'':' – Zählung nach 15 s beendet');});
$('start').addEventListener('click',async()=>{const album=$('album')?$('album').value.trim():'';
 if(!confirm('Alle Fotos aus „'+aktuell.pfad+'“ samt Unterordnern nach Sortiert kopieren'+
  (album?' und ins Album „'+album+'“ aufnehmen':'')+'?'))return;
 const [ok,j]=await post('/api/import/start',{pfad:aktuell.pfad,album});
 if(!ok){meldung(j.fehler||'Start fehlgeschlagen.',true);return;}abfragen();});
$('abbrechen').addEventListener('click',async()=>{const [ok,j]=await post('/api/import/abbrechen',{});
 meldung(ok?'Abbruch angefordert – der laufende Ordner wird noch fertig.':(j.fehler||'Nichts zu abbrechen.'),!ok);});
$('rueck').addEventListener('click',async()=>{
 if(!confirm('Alle Dateien dieses Imports wieder aus Sortiert entfernen? Die Quelle ist davon nicht betroffen.'))return;
 const [ok,j]=await post('/api/import/rueckgaengig',{});if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}abfragen();});
$('dupsuchen').addEventListener('click',async()=>{const [ok,j]=await post('/api/duplikate',{aktion:'suchen'});
 if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}abfragen();});
async function abfragen(){clearTimeout(zeitgeber);let j;
 try{const r=await fetch('/api/import/status');j=await r.json();}catch(_){zeitgeber=setTimeout(abfragen,3000);return;}
 $('korb').textContent=(j.korb[0]?'Im Papierkorb '+KORB+': '+j.korb[0]+' Dateien, '+gb(j.korb[1])+'.':'Der Papierkorb '+KORB+' ist leer.')+
  (j.korb[2]?' Dazu aus früheren Versionen im Ordner .duplikate: '+j.korb[2]+' Dateien, '+gb(j.korb[3])+'.':'');
 const a=j.auftrag;laeuft=!!(a&&a.laeuft);knoepfe();
 if(!a){$('lauf').hidden=true;return;}
 $('lauf').hidden=false;$('abbrechen').hidden=!laeuft;
 const titel={import:'Import',rueckgaengig:'Rückgängig',duplikate:'Duplikatsuche',zusammenfassen:'Zusammenfassen',gruppieren:'Neu gruppieren',umzug_rueck:'Umzug rückgängig',verschieben:'Fotos verschieben'}[a.art]||a.art;
 $('phase').textContent=titel+(a.ziel&&a.art==='import'?' von '+a.ziel:'')+
  (a.album&&a.art==='import'?' ins Album „'+a.album+'“':'')+': '+a.phase+
  (a.gesamt?' – '+a.fertig+' von '+a.gesamt:'')+(a.zusatz?' · '+a.zusatz:'');
 $('balken').max=a.gesamt||1;$('balken').value=laeuft?(a.gesamt?a.fertig:0):($('balken').max);
 if(laeuft&&!a.gesamt)$('balken').removeAttribute('value');
 $('ergebnis').textContent=a.fehler||a.ergebnis||'';$('ergebnis').classList.toggle('fehler',!!a.fehler);
 $('log').textContent=a.log.join('\\n');$('rueck').hidden=laeuft||a.art!=='import'||!a.protokoll;
 const al=$('albumlink');al.hidden=laeuft||a.art!=='import'||!a.album_n;
 if(!al.hidden){al.href='/suche?q='+encodeURIComponent('Album '+a.album);al.textContent='Album „'+a.album+'“ zeigen';}
 if(laeuft)zeitgeber=setTimeout(abfragen,1000);}
let start='';try{start=localStorage.getItem('importPfad')||'';}catch(_){}
oeffnen(start);abfragen();
"""
