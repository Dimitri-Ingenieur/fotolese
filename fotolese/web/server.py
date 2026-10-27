"""fotolese.web.server – HTTP-Handler (GET/POST) und die Aktionen hinter den /api-Aufrufen.

Die Aktionen (Jahr setzen, Personen/Gesichter ändern, Gesicht nachsuchen) geben jeweils
(Code, Antwort-dict) zurück; der Handler verpackt das als JSON.
"""
import base64
import hmac
import json
import os
import re
import shutil
import time
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

import numpy as np

from fotolese.web.konst import ORDNER_MUSTER
from fotolese.web.konfig import bilder_text, name_aus_id, url_id
from fotolese.web.bild import PLATZHALTER
from fotolese.web.gesichter import GesichtsSucher, _ueberdeckung, _ueberlappung
from fotolese.web.lernen import _fehler_aehnlichkeit, _lernlog, lernen
from fotolese.web.html import (bild_daten, gruppe_pruefen_seite, ordner_seite, ordner_zusammen, personen_seite,
                               status_text, such_seite, uebersicht)
from fotolese.web.importieren import import_api, import_seite, ordner_liste, papierkorb_inhalt


class App:
    pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "bestof"
    app = None

    def log_message(self, fmt, *args):
        pass

    def _senden(self, code, typ, daten, cache="no-store", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if typ.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                             "style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(daten)

    def _json(self, code, daten):
        self._senden(code, "application/json; charset=utf-8", json.dumps(daten).encode())

    def _weiterleiten(self, ziel):
        self._senden(303, "text/plain; charset=utf-8", b"", extra={"Location": ziel})

    def _nicht_gefunden(self, text="Nicht gefunden."):
        self._senden(404, "text/plain; charset=utf-8", text.encode())

    def _erlaubt(self):
        pw = self.app.passwort
        if not pw:
            return True
        kopf_wert = self.headers.get("Authorization", "")
        if kopf_wert.startswith("Basic "):
            try:
                _, _, gesendet = base64.b64decode(kopf_wert[6:]).decode("utf-8").partition(":")
                if hmac.compare_digest(gesendet.encode(), pw.encode()):
                    return True
            except (ValueError, UnicodeDecodeError):
                pass
        self._senden(401, "text/plain; charset=utf-8", b"Passwort erforderlich.",
                     extra={"WWW-Authenticate": 'Basic realm="BestOf", charset="UTF-8"'})
        return False

    def _sicher(self, fn):
        try:
            if self._erlaubt():
                fn()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as fehler:
            traceback.print_exc()
            try:
                self._senden(500, "text/plain; charset=utf-8", f"Fehler: {fehler}".encode("utf-8", "replace"))
            except Exception:
                pass

    def do_GET(self):
        self._sicher(self._get)

    def do_HEAD(self):
        self._sicher(self._get)

    def do_POST(self):
        self._sicher(self._post)

    def _ordner_ok(self, o):
        return ORDNER_MUSTER.fullmatch(o) is not None and o in self.app.archiv.ordner()

    def _get(self):
        teile = urlsplit(self.path)
        q = parse_qs(teile.query)
        weg = teile.path.split("/")[1:]
        app = self.app

        def zahl_param(name):
            try:
                return int(q.get(name, ["1"])[0])
            except ValueError:
                return 1

        html_typ = "text/html; charset=utf-8"
        if teile.path == "/":
            return self._senden(200, html_typ, uebersicht(app, q.get("filter", ["alle"])[0], zahl_param("seite")))
        if teile.path == "/suche":
            return self._senden(200, html_typ, such_seite(app, q.get("q", [""])[0][:300], zahl_param("seite")))
        if teile.path == "/personen" and "gruppe" in q and app.index:
            try:
                inhalt = gruppe_pruefen_seite(app, int(q["gruppe"][0]))
            except ValueError:
                inhalt = None
            return self._senden(200, html_typ, inhalt) if inhalt else self._weiterleiten("/personen")
        if teile.path == "/personen":
            return self._senden(200, html_typ, personen_seite(app, "alle" in q, "ignorierte" in q))
        if teile.path == "/import":
            return self._senden(200, html_typ, import_seite(app))
        if teile.path == "/api/ordner":
            if not app.import_erlaubt:
                return self._json(403, {"fehler": "Import ist hier nicht freigegeben."})
            return self._json(200, ordner_liste(app, q.get("pfad", [""])[0]))
        if teile.path == "/api/import/status":
            a = app.auftrag
            return self._json(200, {"auftrag": a.status if a else None, "korb": papierkorb_inhalt(app)})
        if teile.path == "/api/gesichter" and app.index:
            o, _, uid = q.get("pfad", [""])[0].partition("/")
            datei_name = name_aus_id(uid)
            if not (ORDNER_MUSTER.fullmatch(o) and o in app.archiv.ordner() and uid and url_id(datei_name) == uid
                    and app.archiv.datei(o, datei_name)):
                return self._json(404, {"fehler": "Bild nicht gefunden."})
            meta, gesichter = bild_daten(app, None, [(o, datei_name)])
            m = meta.get(f"{o}/{uid}")
            stand = "fehler" if m and m[8] else ("offen" if not m or m[7] is None else "ok")
            return self._json(200, {"f": gesichter.get(f"{o}/{uid}", []), "fs": stand})
        if teile.path == "/api/status":
            text, laeuft = status_text(app)
            return self._json(200, {"text": text, "laeuft": laeuft})
        if teile.path == "/favicon.ico":
            return self._senden(204, "image/x-icon", b"")
        if teile.path == "/springen":
            ziffern = re.sub(r"\D", "", q.get("o", [""])[0])[:4]
            liste = app.archiv.ordner()
            if ziffern and liste:
                gesucht = f"{int(ziffern):04d}"
                treffer = next((o for o in liste if o >= gesucht), liste[-1])
                return self._weiterleiten(f"/o/{treffer}")
            return self._weiterleiten("/")
        if len(weg) == 2 and weg[0] == "o" and self._ordner_ok(weg[1]):
            return self._senden(200, html_typ, ordner_seite(app, weg[1]))
        if len(weg) == 2 and weg[0] == "weiter" and self._ordner_ok(weg[1]):
            liste, gewaehlt = app.archiv.ordner(), app.auswahl.mit_auswahl()
            pos = liste.index(weg[1])
            naechster = next((o for o in liste[pos + 1:] + liste[:pos] if o not in gewaehlt), None)
            return self._weiterleiten(f"/o/{naechster}" if naechster else "/?filter=ohne")
        if len(weg) == 2 and weg[0] == "f" and app.index and weg[1].isdigit():
            z = app.index.einer("SELECT g.ordner, b.datei, g.x, g.y, g.w, g.h FROM gesicht g JOIN bild b "
                                "ON b.pfad=g.pfad WHERE g.id=?", (int(weg[1]),))
            treffer = app.archiv.datei(z[0], name_aus_id(z[1])) if z else None
            if not treffer:
                return self._nicht_gefunden()
            try:
                typ, daten = app.vorschau.gesicht(int(weg[1]), treffer[0], treffer[2], z[2:6])
            except Exception:
                return self._senden(200, "image/svg+xml", PLATZHALTER)
            return self._senden(200, typ, daten, cache="public, max-age=31536000, immutable")
        if len(weg) == 3 and weg[0] in ("t", "g", "orig") and self._ordner_ok(weg[1]):
            treffer = app.archiv.datei(weg[1], name_aus_id(weg[2]))
            if not treffer:
                return self._nicht_gefunden()
            pfad, groesse, mt = treffer
            if weg[0] == "orig":
                return self._original(pfad, groesse)
            try:
                typ, daten = (app.vorschau.klein if weg[0] == "t" else app.vorschau.gross_bild)(pfad, groesse, mt)
            except Exception:
                return self._senden(200, "image/svg+xml", PLATZHALTER)
            return self._senden(200, typ, daten, cache="public, max-age=31536000, immutable")
        return self._nicht_gefunden()

    def _original(self, pfad, groesse):
        typ = "image/png" if pfad.lower().endswith(".png") else "image/jpeg"
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(groesse))
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{url_id(os.path.basename(pfad))}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            with open(pfad, "rb") as f:
                shutil.copyfileobj(f, self.wfile, 1 << 20)

    def _post(self):
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(415, {"fehler": "Nur JSON."})  # verhindert Formular-Angriffe fremder Seiten
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge > 65536:
            self.close_connection = True
            return self._json(413, {"fehler": "Anfrage zu groß."})
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
        except ValueError:
            return self._json(400, {"fehler": "Ungültige Anfrage."})
        pfad = urlsplit(self.path).path
        app = self.app
        if pfad == "/api/auswahl":
            ordner, uid = str(daten.get("ordner", "")), str(daten.get("datei", ""))
            if not self._ordner_ok(ordner):
                return self._json(404, {"fehler": "Ordner nicht gefunden."})
            name = name_aus_id(uid)
            if not app.archiv.datei(ordner, name):
                return self._json(404, {"fehler": "Bild nicht gefunden. Seite neu laden."})
            code, antwort = app.auswahl.umschalten(ordner, name)
            return self._json(code, antwort)
        if pfad == "/api/neuaufbau":
            return self._json(200, app.auswahl.neu_aufbauen())
        if pfad == "/api/person" and app.index:
            return self._json(*person_aendern(app, daten))
        if pfad == "/api/gesicht" and app.index:
            return self._json(*gesicht_aendern(app, daten))
        if pfad == "/api/jahr" and app.index:
            return self._json(*jahr_aendern(app, daten))
        if pfad.startswith(("/api/import/", "/api/duplikate")):
            return self._json(*import_api(app, pfad, daten))
        if pfad == "/api/lernen" and app.index:
            return self._json(200, lernen(app, "von Hand"))
        if pfad == "/api/gesichter_nennen" and app.index:
            return self._json(*gesichter_nennen(app, daten))
        if pfad == "/api/gesicht_neu" and app.index:
            return self._json(*gesicht_neu(app, daten))
        return self._json(404, {"fehler": "Unbekannt."})


def jahr_aendern(app, daten):
    """Jahr von Hand setzen (gilt vor EXIF und Dateiname) oder mit leerem Wert zurück zum Jahr aus der Datei.
    daten: {"pfade": ["0012/<id>", …]} oder {"ordner": "0012"}, dazu {"jahr": "1994" | ""}."""
    heute = time.localtime().tm_year
    roh = str(daten.get("jahr") or "").strip()
    jahr = None
    if roh:
        if not re.fullmatch(r"\d{4}", roh) or not 1900 <= int(roh) <= heute:
            return 400, {"fehler": f"Bitte ein Jahr von 1900 bis {heute} eingeben."}
        jahr = int(roh)
    liste = app.archiv.ordner()
    if daten.get("ordner") is not None:
        ordner = str(daten.get("ordner"))
        if not ORDNER_MUSTER.fullmatch(ordner) or ordner not in liste:
            return 404, {"fehler": "Ordner nicht gefunden."}
        pfade = [f"{ordner}/{url_id(n)}" for n, _, _ in app.archiv.bilder(ordner)]
        if not pfade:
            return 404, {"fehler": "In diesem Ordner liegen keine Bilder."}
    else:
        roh_pfade = daten.get("pfade")
        if not isinstance(roh_pfade, list) or not 1 <= len(roh_pfade) <= 1000:
            return 400, {"fehler": "Ungültige Anfrage."}
        pfade = []
        for p in roh_pfade:
            o, _, uid = str(p).partition("/")
            name = name_aus_id(uid)
            if (not ORDNER_MUSTER.fullmatch(o) or o not in liste or not uid or url_id(name) != uid
                    or not app.archiv.datei(o, name)):
                return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
            pfade.append(f"{o}/{uid}")
        pfade = list(dict.fromkeys(pfade))
    with app.index.lock:
        db = app.index.db
        auto = {}
        for k in range(0, len(pfade), 500):
            teil = pfade[k:k + 500]
            auto.update(db.execute(f"SELECT pfad, jahr FROM bild WHERE pfad IN ({','.join('?' * len(teil))})",
                                   teil).fetchall())
        ergebnis = {}
        for p in pfade:
            if jahr is None or auto.get(p) == jahr:  # gleich wie in der Datei: keine Korrektur speichern
                db.execute("DELETE FROM jahr_manuell WHERE pfad=?", (p,))
                ergebnis[p] = [auto.get(p) if jahr is None else jahr, False]
            else:
                db.execute("INSERT OR REPLACE INTO jahr_manuell(pfad, jahr) VALUES(?, ?)", (p, jahr))
                ergebnis[p] = [jahr, True]
        db.commit()
    n = len(pfade)
    if jahr is None:
        if n > 1:
            text = f"Von Hand gesetzte Jahre entfernt ({bilder_text(n)}). Es gilt wieder das Jahr aus den Dateien."
        else:
            text = f"Jahr aus der Datei: {auto[pfade[0]]}." if auto.get(pfade[0]) else "Die Datei enthält kein Datum."
    elif n > 1:
        text = f"Jahr {jahr} für {bilder_text(n)} gesetzt."
    else:
        text = f"Jahr {jahr} gespeichert." if ergebnis[pfade[0]][1] else f"Jahr {jahr} stimmt mit der Datei überein."
    antwort = {"meldung": text, "jahre": ergebnis}
    ordner_menge = {p.split("/", 1)[0] for p in pfade}
    if len(ordner_menge) == 1:
        antwort["zusammen"] = ordner_zusammen(app, ordner_menge.pop())
    return 200, antwort


def _name_pruefen(db, name, ausser=()):
    """Name säubern, prüfen und die Schreibweise einer schon vorhandenen Person übernehmen."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if "," in name or ";" in name:
        return None, "Namen ohne Komma und Semikolon – sie trennen Begriffe im Filter."
    if name and re.fullmatch(r"(19|20)\d\d|\d{4}|person\s*\d+", name.casefold()):
        return None, "Dieser Name sieht aus wie ein Jahr, ein Ordner oder „Person N“. Bitte anders wählen."
    for pid, vorhanden in db.execute("SELECT id, name FROM person WHERE name IS NOT NULL").fetchall():
        if pid not in ausser and vorhanden.casefold() == name.casefold():
            return vorhanden, None
    return name, None


def person_aendern(app, daten):
    try:
        ids = sorted({int(x) for x in (daten.get("ids") or [daten.get("id")])})
    except (TypeError, ValueError):
        return 400, {"fehler": "Ungültige Person."}
    platz = ",".join("?" * len(ids))
    with app.index.lock:
        db = app.index.db
        if not ids or db.execute(f"SELECT COUNT(*) FROM person WHERE id IN ({platz})", ids).fetchone()[0] != len(ids):
            return 404, {"fehler": "Person nicht gefunden. Seite neu laden."}
        if "ignorieren" in daten:
            an = bool(daten["ignorieren"])
            db.execute(f"UPDATE person SET ignoriert=? WHERE id IN ({platz})", (int(an), *ids))
            db.commit()
            return 200, {"meldung": "Ignoriert – erscheint nicht mehr in Listen und Lupe." if an else "Wieder sichtbar."}
        name, fehler = _name_pruefen(db, daten.get("name"), ausser=set(ids))
        if fehler:
            return 400, {"fehler": fehler}
        db.execute(f"UPDATE person SET name=? WHERE id IN ({platz})", (name or None, *ids))
        if not name:
            db.commit()
            return 200, {"meldung": "Name entfernt – die Gruppe ist wieder eine eigene Person.", "neu_laden": True,
                         "name": f"Person {ids[0]}"}
        gleiche = [(pid, ig, n) for pid, vorhanden, ig, n in db.execute(
            "SELECT id, name, ignoriert, anzahl FROM person WHERE name IS NOT NULL").fetchall()
            if vorhanden.casefold() == name.casefold()]
        andere = [ig for pid, ig, _ in gleiche if pid not in ids]
        if andere:  # verknüpft: Sichtbarkeit der schon vorhandenen Person übernehmen
            db.execute(f"UPDATE person SET ignoriert=? WHERE id IN ({platz})", (int(any(andere)), *ids))
        db.commit()
        gruppen = sum(1 for _, _, n in gleiche if n > 0)
    zusatz = f" {name} umfasst jetzt {gruppen} Gruppen." if gruppen > 1 else ""
    return 200, {"meldung": f"Gespeichert: {name}.{zusatz}", "neu_laden": gruppen > 1, "name": name}


def _gesicht_finden(db, daten):
    """Gesicht über seine ID; kennt der Index die ID nicht mehr (Seite älter als der Index, z. B. während
    der Index ein Bild neu durchsucht), über Bild und Lage des Kastens."""
    try:
        gid = int(daten.get("id"))
    except (TypeError, ValueError):
        gid = None
    if gid is not None and db.execute("SELECT 1 FROM gesicht WHERE id=?", (gid,)).fetchone():
        return gid
    pfad, kasten = daten.get("pfad"), daten.get("kasten")
    try:
        kasten = [float(v) for v in kasten[:4]] if isinstance(kasten, list) and len(kasten) >= 4 else None
    except (TypeError, ValueError):
        kasten = None
    if not isinstance(pfad, str) or not kasten:
        return None
    beste = None
    for kid, x, y, w, h in db.execute("SELECT id, x, y, w, h FROM gesicht WHERE pfad=?", (pfad,)).fetchall():
        wert = max(_ueberlappung(kasten, (x, y, w, h)), 0.8 * _ueberdeckung(kasten, (x, y, w, h)))
        if wert >= 0.4 and (beste is None or wert > beste[0]):
            beste = (wert, kid)
    return beste[1] if beste else None


def gesicht_aendern(app, daten):
    """Ohne Name: Gesicht entfernen. Mit Name: Gesicht dieser Person zuordnen – zur ähnlichsten ihrer
    Gruppen, sonst als neue Gruppe (so bekommt z. B. das Kindergesicht eine eigene Gruppe)."""
    with app.index.lock:
        db = app.index.db
        gid = _gesicht_finden(db, daten)
        if gid is None:
            return 404, {"fehler": "Die Gesichter dieses Fotos wurden gerade neu erkannt. Bitte noch einmal anklicken.",
                         "veraltet": True}
        zeile = db.execute("SELECT g.person, g.emb, p.name, g.manuell FROM gesicht g LEFT JOIN person p "
                           "ON p.id = g.person WHERE g.id=?", (gid,)).fetchone()
        if not str(daten.get("name") or "").strip():
            app.indexer._personen_abziehen(db, [(gid, zeile[0], zeile[1])])
            db.execute("UPDATE gesicht SET person=NULL, manuell=1 WHERE id=?", (gid,))
            _lernlog(db, "entfernt", gid, zeile[2])
            db.commit()
            return 200, {"meldung": "Gesicht entfernt. Es wird keiner Person mehr zugeordnet.", "id": gid}
        name, fehler = _name_pruefen(db, daten.get("name"))
        if fehler:
            return 400, {"fehler": fehler}
        if zeile[2] and zeile[2].casefold() == name.casefold():  # gleicher Name = Bestätigung (Label)
            if not zeile[3]:
                db.execute("UPDATE gesicht SET manuell=1 WHERE id=?", (gid,))
                _lernlog(db, "bestaetigt", gid, None, zeile[2])
                db.commit()
            return 200, {"meldung": f"Bestätigt: {zeile[2]}. bestof.py lernt daraus.", "person": zeile[0],
                         "name": zeile[2], "id": gid}
        if not zeile[1]:  # von Hand markierte Stelle ohne Merkmale: zur größten Gruppe dieses Namens
            app.indexer._personen_aendern(db, minus=[(zeile[0], None)])
            gleich = [(n, pid, ig) for pid, vorhanden, n, ig in db.execute(
                "SELECT id, name, anzahl, ignoriert FROM person WHERE name IS NOT NULL AND anzahl > 0").fetchall()
                if vorhanden.casefold() == name.casefold()]
            if gleich:
                pid = max(gleich)[1]
                app.indexer._personen_aendern(db, plus=[(pid, None)])
            else:
                pid = db.execute("INSERT INTO person(name, summe, anzahl) VALUES(?, ?, 1)",
                                 (name, np.zeros(128, np.float32).tobytes())).lastrowid
            db.execute("UPDATE gesicht SET person=?, manuell=1 WHERE id=?", (pid, gid))
            _lernlog(db, "label", gid, zeile[2], name)
            anzahl = dict(db.execute("SELECT id, anzahl FROM person WHERE id IN (?, ?)",
                                     (pid, zeile[0] if zeile[0] is not None else -1)).fetchall())
            db.commit()
            return 200, {"meldung": f"Stelle ist jetzt {name}.", "person": pid, "name": name,
                         "bewegt": [[gid, pid, name]], "anzahl": anzahl, "id": gid}
        v = np.frombuffer(zeile[1], np.float32)
        # automatisch falsch zugeordnet? Ähnlichkeit festhalten – daraus lernt bestof.py Schwelle und Abstand
        korrektur = bool(zeile[2] and not zeile[3])
        falsch, abst = _fehler_aehnlichkeit(db, zeile[0], v, zeile[2]) if korrektur else (None, None)
        app.indexer._personen_abziehen(db, [(gid, zeile[0], zeile[1])])
        bester, ignoriert, bekannt = None, False, False
        for pid, vorhanden, summe, anzahl, ig in db.execute(
                "SELECT id, name, summe, anzahl, ignoriert FROM person WHERE name IS NOT NULL").fetchall():
            if vorhanden.casefold() != name.casefold():
                continue
            ignoriert = ignoriert or bool(ig)
            if anzahl <= 0:
                continue
            bekannt = True
            s_vec = np.frombuffer(summe, np.float32)
            aehnlich = float(s_vec @ v / (np.linalg.norm(s_vec) or 1))
            if aehnlich >= app.person_schwelle and (bester is None or aehnlich > bester[1]):
                bester = (pid, aehnlich, s_vec, anzahl)
        if bester:
            pid = bester[0]
            db.execute("UPDATE person SET summe=?, anzahl=? WHERE id=?",
                       ((bester[2] + v).astype(np.float32).tobytes(), bester[3] + 1, pid))
            text = f"Gesicht ist jetzt {name}."
        else:
            pid = db.execute("INSERT INTO person(name, summe, anzahl, ignoriert) VALUES(?, ?, 1, ?)",
                             (name, v.tobytes(), int(ignoriert))).lastrowid
            text = (f"Gesicht ist jetzt {name} – als eigene Gruppe, weil es den übrigen Fotos von {name} wenig ähnelt."
                    if bekannt else f"Gesicht ist jetzt {name} (neue Person).")
        db.execute("UPDATE gesicht SET person=?, manuell=1 WHERE id=?", (pid, gid))
        bewegt, alt = [[gid, pid, name]], zeile[0]
        mit = _nachziehen(app, db, alt, pid, v) if alt is not None and daten.get("nachziehen", True) else []
        if mit:
            app.indexer._personen_abziehen(db, [(kid, alt, kemb) for kid, kemb in mit])
            summe, anzahl = db.execute("SELECT summe, anzahl FROM person WHERE id=?", (pid,)).fetchone()
            neu = np.frombuffer(summe, np.float32) + np.sum([np.frombuffer(m[1], np.float32) for m in mit], axis=0)
            db.execute("UPDATE person SET summe=?, anzahl=? WHERE id=?",
                       (neu.astype(np.float32).tobytes(), anzahl + len(mit), pid))
            db.executemany("UPDATE gesicht SET person=? WHERE id=?", [(pid, kid) for kid, _ in mit])
            bewegt += [[kid, pid, name] for kid, _ in mit]
            text += (" 1 sehr ähnliches Gesicht derselben Gruppe ist mitgewandert." if len(mit) == 1 else
                     f" {len(mit)} sehr ähnliche Gesichter derselben Gruppe sind mitgewandert.")
        anzahl = dict(db.execute("SELECT id, anzahl FROM person WHERE id IN (?, ?)",
                                 (pid, alt if alt is not None else -1)).fetchall())
        _lernlog(db, "korrektur" if korrektur else "label", gid, zeile[2], name, falsch, abst)
        db.commit()
    if korrektur and app.lerner:
        app.lerner.anstossen()
    return 200, {"meldung": text, "person": pid, "name": name, "bewegt": bewegt, "anzahl": anzahl, "id": gid}


def gesicht_daten(db, gid):
    """[x, y, w, h, person, name, id, anzahl] wie in den Bilddaten der Seite."""
    x, y, w, h, pid, name, anzahl = db.execute(
        "SELECT g.x, g.y, g.w, g.h, g.person, p.name, p.anzahl FROM gesicht g LEFT JOIN person p ON p.id = g.person "
        "WHERE g.id=?", (gid,)).fetchone()
    return [round(x, 4), round(y, 4), round(w, 4), round(h, 4), pid, name or f"Person {pid}", gid, anzahl or 0]


def gesicht_neu(app, daten):
    """Übersehenes Gesicht: an der angeklickten Stelle suchen und eintragen. Findet die Suche keins,
    lässt sich die Stelle mit Namen trotzdem markieren (erzwingen) – z. B. Profil oder Hinterkopf."""
    if not (app.indexer and app.indexer.gesichter_aktiv):
        return 503, {"fehler": "Die Gesichtserkennung ist aus oder lädt noch."}
    ordner, uid = str(daten.get("ordner", "")), str(daten.get("datei", ""))
    datei_name = name_aus_id(uid)
    treffer = (app.archiv.datei(ordner, datei_name) if ORDNER_MUSTER.fullmatch(ordner) and url_id(datei_name) == uid
               and ordner in app.archiv.ordner() else None)
    if not treffer:
        return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
    try:
        x, y = float(daten.get("x")), float(daten.get("y"))
    except (TypeError, ValueError):
        return 400, {"fehler": "Ungültige Stelle."}
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return 400, {"fehler": "Ungültige Stelle."}
    rel = f"{ordner}/{uid}"
    name = ""
    if str(daten.get("name") or "").strip():
        with app.index.lock:
            name, fehler = _name_pruefen(app.index.db, daten.get("name"))
        if fehler:
            return 400, {"fehler": fehler}
    for gid, gx, gy, gw, gh in app.index.q("SELECT id, x, y, w, h FROM gesicht WHERE pfad=? AND "
                                           "NOT (person IS NULL AND manuell=1)", (rel,)):
        if gx - 0.1 * gw <= x <= gx + 1.1 * gw and gy - 0.1 * gh <= y <= gy + 1.1 * gh:
            with app.index.lock:
                return 200, {"gesicht": gesicht_daten(app.index.db, gid), "vorhanden": True,
                             "meldung": "Dieses Gesicht ist schon markiert."}
    try:
        if app.sucher is None:
            app.sucher = GesichtsSucher(app.indexer.modelle)
        fund = app.sucher.suchen(treffer[0], x, y)
    except Exception as fehler:
        return 500, {"fehler": f"Suche fehlgeschlagen: {type(fehler).__name__}: {fehler}"[:200]}
    if fund["kasten"] is None:
        if not daten.get("erzwingen"):
            return 404, {"fehler": "Hier habe ich kein Gesicht gefunden.", "markieren": True}
        if not name:
            return 400, {"fehler": "Bitte einen Namen eingeben."}
        W, H = fund["groesse"]
        seite = 0.08 * min(W, H)
        fund.update(kasten=(max(0.0, x - seite / 2 / W), max(0.0, y - seite / 2 / H), seite / W, seite / H),
                    score=0.0, pixel=round(seite), emb=None)
    with app.index.lock:
        db = app.index.db
        for gid, gx, gy, gw, gh, person, manuell in db.execute(
                "SELECT id, x, y, w, h, person, manuell FROM gesicht WHERE pfad=?", (rel,)).fetchall():
            if (_ueberlappung(fund["kasten"], (gx, gy, gw, gh)) >= 0.4
                    or _ueberdeckung(fund["kasten"], (gx, gy, gw, gh)) >= 0.6):
                if person is None and manuell:  # früher als „kein Gesicht“ entfernt: wieder aufnehmen
                    db.execute("DELETE FROM gesicht WHERE id=?", (gid,))
                else:
                    return 200, {"gesicht": gesicht_daten(db, gid), "vorhanden": True,
                                 "meldung": "Dieses Gesicht ist schon markiert."}
        gid = db.execute("INSERT INTO gesicht(pfad, ordner, x, y, w, h, score, pixel, emb, person, manuell, hand) "
                         "VALUES(?,?,?,?,?,?,?,?,?,NULL,1,1)",
                         (rel, ordner, *fund["kasten"], fund["score"], fund["pixel"], fund["emb"])).lastrowid
        if not name:  # zuordnen wie beim Einlesen: ähnlichste sichtbare Gruppe oder neue Gruppe
            v = np.frombuffer(fund["emb"], np.float32)
            werte = []
            for pid, summe, pname in db.execute("SELECT id, summe, name FROM person WHERE anzahl > 0 "
                                                "AND ignoriert = 0").fetchall():
                s_vec = np.frombuffer(summe, np.float32)
                laenge = float(np.linalg.norm(s_vec))
                werte.append((float(s_vec @ v) / laenge if laenge > 0 else -1.0, pid, (pname or "").casefold()))
            werte.sort(reverse=True)
            bester = werte[0] if werte and werte[0][0] >= app.person_schwelle else None
            if bester and bester[2] and app.abstand > 0:
                andere = [w for w, _, n in werte if n and n != bester[2]]
                if andere and bester[0] - andere[0] < app.abstand:
                    bester = None  # zu nah an einer anderen Person: lieber neue Gruppe
            if bester:
                pid = bester[1]
                app.indexer._personen_aendern(db, plus=[(pid, fund["emb"])])
            else:
                pid = db.execute("INSERT INTO person(name, summe, anzahl) VALUES(NULL, ?, 1)", (v.tobytes(),)).lastrowid
            db.execute("UPDATE gesicht SET person=? WHERE id=?", (pid, gid))
        db.commit()
    if name:
        code, antwort = gesicht_aendern(app, {"id": gid, "name": name, "nachziehen": False})
        if code != 200:
            return code, antwort
    with app.index.lock:
        g = gesicht_daten(app.index.db, gid)
    text = (f"Stelle als {g[5]} markiert (kein Gesicht erkennbar, zählt nur für die Suche nach Namen)."
            if fund["emb"] is None else f"Gesicht gefunden: {g[5]}.")
    return 200, {"gesicht": g, "name": g[5], "meldung": text}


def gesichter_nennen(app, daten):
    """Ausgewählte Gesichter (Seite „Prüfen“) gesammelt benennen oder entfernen."""
    roh = daten.get("ids")
    try:
        ids = list(dict.fromkeys(int(x) for x in roh)) if isinstance(roh, list) else []
    except (TypeError, ValueError):
        ids = []
    if not 1 <= len(ids) <= 1000:
        return 400, {"fehler": "Bitte Gesichter auswählen."}
    if daten.get("bestaetigen"):  # „stimmt so“ – wird zum Label, aus dem bestof.py lernt
        erledigt = 0
        with app.index.lock:
            db = app.index.db
            for gid in ids:
                z = db.execute("SELECT g.person, p.name FROM gesicht g JOIN person p ON p.id = g.person "
                               "WHERE g.id=?", (gid,)).fetchone()
                if z:
                    db.execute("UPDATE gesicht SET manuell=1 WHERE id=?", (gid,))
                    _lernlog(db, "bestaetigt", gid, None, z[1] or f"Person {z[0]}")
                    erledigt += 1
            db.commit()
        if not erledigt:
            return 404, {"fehler": "Diese Gesichter gibt es nicht mehr. Seite neu laden."}
        return 200, {"meldung": f"{erledigt} {'Gesicht' if erledigt == 1 else 'Gesichter'} bestätigt – "
                                f"bestof.py lernt daraus.", "anzahl": erledigt}
    name = ""
    if str(daten.get("name") or "").strip():
        with app.index.lock:
            name, fehler = _name_pruefen(app.index.db, daten.get("name"))
        if fehler:
            return 400, {"fehler": fehler}
    erledigt, endname = 0, name
    for gid in ids:
        code, antwort = gesicht_aendern(app, {"id": gid, "name": name, "nachziehen": False} if name else {"id": gid})
        if code == 200:
            erledigt += 1
            endname = antwort.get("name") or endname
    if not erledigt:
        return 404, {"fehler": "Diese Gesichter gibt es nicht mehr. Seite neu laden."}
    text = (f"{erledigt} {'Gesicht heißt' if erledigt == 1 else 'Gesichter heißen'} jetzt {endname}." if name else
            f"{erledigt} {'Gesicht' if erledigt == 1 else 'Gesichter'} entfernt.")
    return 200, {"meldung": text, "anzahl": erledigt}


def _nachziehen(app, db, alt, neu_pid, v):
    """Gesichter der alten Gruppe, die dem korrigierten Gesicht v sehr ähnlich sind (≥ NACHZIEHEN) und ihm
    ähnlicher als dem Rest ihrer Gruppe – typisch Serienbilder. Von Hand zugeordnete bleiben."""
    if alt == neu_pid or app.nachziehen >= 1:
        return []
    zeile = db.execute("SELECT summe FROM person WHERE id=?", (alt,)).fetchone()
    if not zeile:
        return []
    rest = np.frombuffer(zeile[0], np.float32)
    mit = []
    for kid, kemb in db.execute("SELECT id, emb FROM gesicht WHERE person=? AND manuell=0 AND emb IS NOT NULL",
                                (alt,)).fetchall():
        k = np.frombuffer(kemb, np.float32)
        zum_neuen = float(k @ v)
        if zum_neuen < app.nachziehen:
            continue
        ohne = rest - k  # Rest der Gruppe ohne dieses Gesicht
        laenge = float(np.linalg.norm(ohne))
        zum_rest = float(k @ ohne) / laenge if laenge > 1e-6 else -1.0
        if zum_neuen > zum_rest:
            mit.append((kid, kemb))
    return mit
