"""fotolese.web.index – SQLite-Index (Bilder, Gesichter, Personen) und der Indexer-Thread.

Der Indexer lädt Orts- und Gesichtsmodelle, wählt das Rechenwerk (GPU, sonst CPU – siehe gpu),
liest neue Bilder in einem Prozess-Pool (gesichter._iw_job) und ordnet Gesichter Personen zu.
"""
import hashlib
import os
import shutil
import sqlite3
import threading
import traceback
import urllib.request
import multiprocessing as mp
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from importlib.util import find_spec

import numpy as np

from fotolese.web import gpu
from fotolese.web.konst import GEONAMES_URL, MODELLE
from fotolese.web.konfig import bilder_text, url_id
from fotolese.web.orte import Orte
from fotolese.web.gesichter import _iw_init, _iw_job, _ueberlappung


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS bild(pfad TEXT PRIMARY KEY, ordner TEXT, datei TEXT, groesse INTEGER, mtime INTEGER,
  breite INTEGER, hoehe INTEGER, zeit TEXT, jahr INTEGER, monat INTEGER, lat REAL, lon REAL, ort TEXT,
  ort_km REAL, kamera TEXT, gesichter INTEGER, fehler TEXT);
CREATE INDEX IF NOT EXISTS bild_ordner ON bild(ordner);
CREATE INDEX IF NOT EXISTS bild_jahr ON bild(jahr);
CREATE TABLE IF NOT EXISTS gesicht(id INTEGER PRIMARY KEY, pfad TEXT, ordner TEXT, x REAL, y REAL, w REAL, h REAL,
  score REAL, pixel REAL, emb BLOB, person INTEGER, manuell INTEGER DEFAULT 0, hand INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS gesicht_pfad ON gesicht(pfad);
CREATE INDEX IF NOT EXISTS gesicht_person ON gesicht(person);
CREATE INDEX IF NOT EXISTS gesicht_ordner ON gesicht(ordner);
CREATE TABLE IF NOT EXISTS person(id INTEGER PRIMARY KEY, name TEXT, summe BLOB, anzahl INTEGER,
  ignoriert INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS jahr_manuell(pfad TEXT PRIMARY KEY, jahr INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pruefsumme(pfad TEXT PRIMARY KEY, groesse INTEGER, mtime INTEGER, sha TEXT);
CREATE TABLE IF NOT EXISTS lernlog(zeit TEXT, art TEXT, gid INTEGER, von TEXT, zu TEXT, aehnlich REAL, abstand REAL);
CREATE TABLE IF NOT EXISTS album(id INTEGER PRIMARY KEY, name TEXT NOT NULL, angelegt TEXT);
CREATE TABLE IF NOT EXISTS album_bild(album INTEGER NOT NULL, pfad TEXT NOT NULL, PRIMARY KEY(album, pfad));
CREATE INDEX IF NOT EXISTS album_bild_pfad ON album_bild(pfad);
DROP VIEW IF EXISTS bild_eff;
CREATE VIEW bild_eff AS SELECT b.*,
  COALESCE(k.jahr, b.jahr) AS jahr_eff,
  CASE WHEN k.jahr IS NULL OR k.jahr = b.jahr THEN b.monat END AS monat_eff,
  CASE WHEN k.jahr <> b.jahr OR b.jahr IS NULL THEN k.jahr END AS jahr_man,
  CASE WHEN k.jahr IS NULL OR k.jahr = b.jahr THEN b.zeit ELSE CAST(k.jahr AS TEXT) END AS sortzeit
  FROM bild b LEFT JOIN jahr_manuell k ON k.pfad = b.pfad;
"""


class Index:
    def __init__(self, pfad):
        self.pfad = pfad
        self.lock = threading.RLock()
        self.db = sqlite3.connect(pfad, check_same_thread=False, timeout=30)
        self.db.executescript(SCHEMA)
        if "hand" not in {z[1] for z in self.db.execute("PRAGMA table_info(gesicht)")}:  # Index aus Version < 2.4
            self.db.execute("ALTER TABLE gesicht ADD COLUMN hand INTEGER DEFAULT 0")
        self.db.commit()

    def q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def einer(self, sql, args=()):
        zeilen = self.q(sql, args)
        return zeilen[0] if zeilen else None


def personen_namen(index):
    return {pid: (name or f"Person {pid}", ign, anzahl)
            for pid, name, ign, anzahl in index.q("SELECT id, name, ignoriert, anzahl FROM person")}


def namensliste(index):
    """Vergebene Namen für die Eingabehilfe (gleiche Schreibweise = gleiche Person)."""
    namen = {}
    for (n,) in index.q("SELECT name FROM person WHERE name IS NOT NULL AND ignoriert=0 AND anzahl>0") if index else []:
        namen.setdefault(n.casefold(), n)
    return sorted(namen.values(), key=str.casefold)


class Indexer(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.index = app.index
        self.status = {"phase": "Start", "fertig": 0, "gesamt": 0, "meldungen": []}
        self.gesichter_aktiv = False
        self.modelle = (None, None)
        self.gpu = None  # Ergebnis von gpu.waehlen(): GPU-Kennung oder CPU mit Grund
        self.prozesse = self.gpu_prozesse = 0  # im laufenden Durchgang: Index-Prozesse, davon auf der GPU
        self.rechner = Counter()  # Bilder dieser Sitzung je Rechenwerk (gpu/cpu)
        self.rueckfall = None  # letzter GPU-Fehler, nach dem ein Prozess auf die CPU gewechselt ist
        self.orte = Orte(os.path.join(app.daten, "geonames", "cities1000.zip"), app.ort_min_ew)
        self.weiter = threading.Event()
        self._stopp = False
        self._ex = None

    def meldung(self, text):
        print(f"Index: {text}", flush=True)
        self.status["meldungen"] = (self.status["meldungen"] + [text])[-5:]

    def stoppen(self):
        self._stopp = True
        self.weiter.set()
        if self._ex is not None:
            self._ex.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _laden(url, ziel, sha256=None):
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        tmp = ziel + ".laden"
        with urllib.request.urlopen(url, timeout=60) as antwort, open(tmp, "wb") as f:
            shutil.copyfileobj(antwort, f, 1 << 20)
        if sha256:
            with open(tmp, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != sha256:
                    os.unlink(tmp)
                    raise ValueError("Prüfsumme stimmt nicht")
        os.replace(tmp, ziel)

    def vorbereiten(self):
        self.status["phase"] = "Lade Ortsdaten"
        zip_pfad = self.orte.zip_pfad
        try:
            if not os.path.exists(zip_pfad):
                self.meldung("lade Ortsdaten von GeoNames (einmalig, etwa 10 MB) …")
                self._laden(GEONAMES_URL, zip_pfad)
            orte, namen = self.orte.laden()
            self.meldung(f"{orte} Orte ab {self.app.ort_min_ew} Einwohnern bereit.")
        except Exception as fehler:
            self.meldung(f"Ortsnamen aus: {fehler}. Datei von {GEONAMES_URL} nach {zip_pfad} legen.")
        if not self.app.gesichter:
            self.meldung("Gesichtserkennung aus (GESICHTER=0).")
            return
        if find_spec("cv2") is None:
            self.meldung("Gesichtserkennung aus: OpenCV fehlt (python -m pip install opencv-python-headless).")
            return
        self.status["phase"] = "Lade Gesichtsmodelle"
        pfade = []
        try:
            for datei, url, sha in MODELLE.values():
                ziel = os.path.join(self.app.daten, "modelle", datei)
                if not os.path.exists(ziel):
                    self.meldung(f"lade {datei} (einmalig) …")
                    self._laden(url, ziel, sha)
                pfade.append(ziel)
            self.modelle = tuple(pfade)
            self.gesichter_aktiv = True
        except Exception as fehler:
            self.meldung(f"Gesichtserkennung aus: Modelle nicht ladbar ({fehler}).")
            return
        a = self.app
        param = f"3|{a.erkenn_px}|{a.min_gesicht}|{a.gesicht_score:g}|{a.gegenprobe:g}"
        with self.index.lock:
            db = self.index.db
            alt = db.execute("SELECT v FROM meta WHERE k='gesicht_param'").fetchone()
            if alt is None or alt[0] != param:  # neue Version oder andere Einstellungen: Gesichter neu suchen
                n = db.execute("UPDATE bild SET gesichter=NULL WHERE fehler IS NULL").rowcount
                db.execute("INSERT OR REPLACE INTO meta VALUES('gesicht_param', ?)", (param,))
                db.commit()
                if n:
                    self.meldung(f"Gesichtssuche geändert – {bilder_text(n)} werden neu durchsucht. "
                                 f"Namen und Korrekturen bleiben erhalten.")
        self.status["phase"] = "Prüfe GPU"
        self.gpu = gpu.waehlen(self.modelle, a.gpu) if a.gpu_jobs else {"kennung": None, "grund": "GPU_JOBS = 0 gesetzt"}
        self.meldung(self.rechenwerk(lang=True))

    def rechenwerk(self, lang=False):
        """Worauf die Gesichtserkennung rechnet – kurz für die Kopfzeile, lang für Terminal und Seite „Personen“."""
        w = self.gpu
        if not (self.gesichter_aktiv and w):
            return ""
        if not w.get("kennung"):
            return f"Gesichtserkennung auf der CPU – {w.get('grund') or 'keine GPU'}"
        text = f"Gesichtserkennung auf der GPU – {w['anzeige']}" + (f", {w['geraet']}" if w.get("geraet") else "")
        if self.status["phase"] == "Index" and self.gpu_prozesse < self.prozesse:
            text += f" ({self.gpu_prozesse} von {self.prozesse} Index-Prozessen, übrige CPU)"
        if self.rueckfall:
            text += f"; GPU-Fehler, ein Prozess rechnet jetzt auf der CPU: {self.rueckfall}"
        if lang and w.get("ms_cpu"):
            text += f". Probe 1280×960: {w['ms_gpu']:.0f} ms statt {w['ms_cpu']:.0f} ms auf der CPU"
        if lang and self.rechner:
            text += f". Diese Sitzung: {bilder_text(self.rechner['gpu'])} auf der GPU, {self.rechner['cpu']} auf der CPU"
        return text

    def run(self):
        try:
            self.vorbereiten()
            while not self._stopp:
                self.durchlauf()
                self.status["phase"] = "fertig"
                self.weiter.wait(self.app.aktualisieren)
                self.weiter.clear()
        except Exception:
            traceback.print_exc()
            self.status["phase"] = "Fehler – siehe Terminal"

    # -- Datenbankpflege
    def _personen_abziehen(self, db, zeilen):
        """Gesichter (id, person, emb) aus den Personensummen herausnehmen."""
        self._personen_aendern(db, minus=[(person, emb) for _, person, emb in zeilen])

    def _personen_aendern(self, db, plus=(), minus=()):
        """Personensummen anpassen: plus/minus = [(person, emb)]. Gesichter ohne Merkmale (von Hand markiert)
        zählen mit, ändern aber den Mittelwert nicht. Leere Gruppen ohne Namen verschwinden."""
        je = {}
        for vz, liste in ((1, plus), (-1, minus)):
            for person, emb in liste:
                if person is None:
                    continue
                s, n = je.get(person, (np.zeros(128, np.float32), 0))
                je[person] = (s + vz * np.frombuffer(emb, np.float32) if emb else s, n + vz)
        for person, (s, n) in je.items():
            z = db.execute("SELECT summe, anzahl, name FROM person WHERE id=?", (person,)).fetchone()
            if not z:
                continue
            rest = z[1] + n
            if rest <= 0 and (not z[2] or any(
                    pid != person and (name or "").casefold() == z[2].casefold()
                    for pid, name in db.execute("SELECT id, name FROM person WHERE name IS NOT NULL").fetchall())):
                db.execute("DELETE FROM person WHERE id=?", (person,))
            else:
                neu = np.frombuffer(z[0], np.float32) + s if rest > 0 else np.zeros(128, np.float32)
                db.execute("UPDATE person SET summe=?, anzahl=? WHERE id=?", (neu.astype(np.float32).tobytes(),
                                                                              max(rest, 0), person))

    def _schreiben(self, ergebnisse):
        with self.index.lock:
            db = self.index.db
            for r in ergebnisse:
                rel = r["rel"]
                ordner, datei = rel.split("/", 1)
                alte = db.execute("SELECT id, person, emb, x, y, w, h, manuell, hand FROM gesicht WHERE pfad=?",
                                  (rel,)).fetchall()
                neue, erbe = r["gesichter"], {}
                vorher = db.execute("SELECT groesse, mtime FROM bild WHERE pfad=?", (rel,)).fetchone()
                unveraendert = vorher is not None and tuple(vorher) == (r["groesse"], r["mtime"])
                if neue is not None:
                    # Gesicht an gleicher Stelle erbt die Zuordnung: Namen, Korrekturen, „kein Gesicht“
                    paare = sorted(((_ueberlappung(a[3:7], n[:4]), i, j) for i, a in enumerate(alte)
                                    for j, n in enumerate(neue)), reverse=True)
                    frei_a, frei_n = set(range(len(alte))), set(range(len(neue)))
                    for wert, i, j in paare:
                        if wert < 0.4:
                            break
                        if i in frei_a and j in frei_n:
                            erbe[j] = alte[i]
                            frei_a.discard(i)
                            frei_n.discard(j)
                    # bleiben stehen: von Hand markierte; bei unveränderter Datei auch von Ihnen benannte
                    weg = [alte[i] for i in frei_a if not alte[i][8]
                           and not (unveraendert and alte[i][7] and alte[i][1] is not None)]
                    self._personen_aendern(db, plus=[(e[1], neue[j][6]) for j, e in erbe.items()],
                                           minus=[(a[1], a[2]) for a in weg] + [(e[1], e[2]) for e in erbe.values()])
                    db.executemany("DELETE FROM gesicht WHERE id=?", [(a[0],) for a in weg])
                lat, lon = r["gps"] or (None, None)
                ort, km = self.orte.naechster(lat, lon) if lat is not None else (None, None)
                zeit = r["zeit"]
                n_ges = len(neue) if neue is not None else (None if not alte else len(alte))
                db.execute("INSERT OR REPLACE INTO bild VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (rel, ordner, datei, r["groesse"], r["mtime"], r["breite"], r["hoehe"], zeit,
                            int(zeit[:4]) if zeit else None, int(zeit[5:7]) if zeit else None, lat, lon, ort, km,
                            r["kamera"], n_ges, r["fehler"]))
                for j, (x, y, w, h, score, pixel, emb) in enumerate(neue or []):
                    e = erbe.get(j)
                    if e:  # gleiches Gesicht: Zeile und ID bleiben – offene Seiten arbeiten weiter damit
                        db.execute("UPDATE gesicht SET x=?, y=?, w=?, h=?, score=?, pixel=?, emb=?, hand=0 WHERE id=?",
                                   (x, y, w, h, score, pixel, emb, e[0]))
                    else:
                        db.execute("INSERT INTO gesicht(pfad, ordner, x, y, w, h, score, pixel, emb) "
                                   "VALUES(?,?,?,?,?,?,?,?,?)", (rel, ordner, x, y, w, h, score, pixel, emb))
            db.commit()

    def personen_zuordnen(self):
        """Neue Gesichter der ähnlichsten Person zuordnen (Mittelwert der Merkmale), sonst neue Person.
        Bestehende Zuordnungen bleiben stabil – Namen gehen nie verloren."""
        schwelle, abstand = self.app.person_schwelle, self.app.abstand
        with self.index.lock:
            db = self.index.db
            neu = db.execute("SELECT id, emb FROM gesicht WHERE person IS NULL AND manuell=0 AND emb IS NOT NULL "
                             "ORDER BY pixel DESC").fetchall()
            if not neu:
                return
            personen = db.execute("SELECT id, summe, anzahl, name FROM person").fetchall()
            ids = [p[0] for p in personen]
            namen = [(p[3] or "").casefold() for p in personen]
            summen = np.zeros((max(len(ids), 16) * 2, 128), np.float32)
            anzahl = [p[2] for p in personen]
            for k, p in enumerate(personen):
                summen[k] = np.frombuffer(p[1], np.float32)
            norm = np.linalg.norm(summen, axis=1, keepdims=True)
            zentren = np.divide(summen, norm, out=np.zeros_like(summen), where=norm > 0)
            geaendert = set()
            for gid, emb in neu:
                v = np.frombuffer(emb, np.float32)
                k = len(ids)
                if k:
                    s = zentren[:k] @ v
                    j = int(np.argmax(s))
                    eindeutig = True
                    if s[j] >= schwelle and abstand > 0 and namen[j]:
                        # gelernter Abstand: ähnelt das Gesicht einer anderen benannten Person fast genauso,
                        # lieber neue Gruppe als falscher Name
                        n_arr = np.array(namen, dtype=object)
                        andere = s[(n_arr != namen[j]) & (n_arr != "")]
                        eindeutig = not andere.size or s[j] - float(andere.max()) >= abstand
                    if s[j] >= schwelle and eindeutig:
                        summen[j] += v
                        zentren[j] = summen[j] / (np.linalg.norm(summen[j]) or 1)
                        anzahl[j] += 1
                        geaendert.add(j)
                        db.execute("UPDATE gesicht SET person=? WHERE id=?", (ids[j], gid))
                        continue
                cur = db.execute("INSERT INTO person(name, summe, anzahl) VALUES(NULL, ?, 1)", (v.tobytes(),))
                if k >= len(summen):
                    summen = np.vstack([summen, np.zeros_like(summen)])
                    zentren = np.vstack([zentren, np.zeros_like(zentren)])
                summen[k], zentren[k] = v, v
                ids.append(cur.lastrowid)
                namen.append("")
                anzahl.append(1)
                db.execute("UPDATE gesicht SET person=? WHERE id=?", (cur.lastrowid, gid))
            for j in geaendert:
                db.execute("UPDATE person SET summe=?, anzahl=? WHERE id=?", (summen[j].tobytes(), anzahl[j], ids[j]))
            db.commit()

    def durchlauf(self):
        app = self.app
        self.status["phase"] = "Suche neue Bilder"
        auf_platte = {}
        for o in app.archiv.ordner(frisch=True):
            for name, groesse, mt in app.archiv.bilder(o, frisch=True):
                auf_platte[f"{o}/{url_id(name)}"] = (o, name, groesse, mt)
        im_index = {r[0]: r[1:] for r in self.index.q("SELECT pfad, groesse, mtime, gesichter, fehler FROM bild")}
        if not auf_platte and im_index:  # Festplatte abgezogen oder Ordner unlesbar: nichts löschen
            if not getattr(self, "_archiv_weg", False):
                self.meldung("Archiv nicht erreichbar – Index bleibt unverändert.")
            self._archiv_weg = True
            return
        self._archiv_weg = False
        weg = [p for p in im_index if p not in auf_platte]
        if weg:
            with self.index.lock:
                db = self.index.db
                for p in weg:
                    self._personen_abziehen(db, db.execute("SELECT id, person, emb FROM gesicht WHERE pfad=?",
                                                           (p,)).fetchall())
                    db.execute("DELETE FROM gesicht WHERE pfad=?", (p,))
                    db.execute("DELETE FROM bild WHERE pfad=?", (p,))
                db.commit()
        todo = []
        for rel, (o, name, groesse, mt) in auf_platte.items():
            alt = im_index.get(rel)
            neu_lesen = alt is None or (alt[0], alt[1]) != (groesse, mt)
            gesichter_fehlen = self.gesichter_aktiv and alt is not None and alt[2] is None and not alt[3]
            if neu_lesen or gesichter_fehlen:
                todo.append((rel, os.path.join(app.archiv.pfad, o, name), groesse, mt, self.gesichter_aktiv))
        if self.orte.bereit:  # Orte nachtragen, falls die Ortsdaten erst später da waren
            with self.index.lock:
                offen = self.index.db.execute("SELECT pfad, lat, lon FROM bild WHERE lat IS NOT NULL AND ort IS NULL")
                for p, lat, lon in offen.fetchall():
                    self.index.db.execute("UPDATE bild SET ort=?, ort_km=? WHERE pfad=?", (*self.orte.naechster(lat, lon), p))
                self.index.db.commit()
        if not todo:
            self.personen_zuordnen()
            return
        todo.sort(key=lambda a: a[0])
        self.status.update(phase="Index", fertig=0, gesamt=len(todo))
        self._verarbeiten(todo)
        self.personen_zuordnen()

    def _rechner_merken(self, r):
        if r.get("rechner"):
            self.rechner[r["rechner"]] += 1
        if r.get("rueckfall") and r["rueckfall"] != self.rueckfall:
            self.rueckfall = r["rueckfall"]
            self.meldung(f"GPU-Fehler, ein Prozess rechnet jetzt auf der CPU: {self.rueckfall}")

    def _verarbeiten(self, todo):
        ctx = mp.get_context("spawn")
        app = self.app
        args = (*self.modelle, app.erkenn_px, app.min_gesicht, app.vorschau.ordner, app.gesicht_score, app.gegenprobe)
        wahl = self.gpu if self.gpu and self.gpu.get("kennung") else None
        rest, verdacht = list(todo), []
        while rest and not self._stopp:
            fertig, puffer = set(), []
            self.prozesse = min(app.index_jobs, len(rest))
            self.gpu_prozesse = min(app.gpu_jobs, self.prozesse) if wahl else 0
            self._ex = ProcessPoolExecutor(self.prozesse, mp_context=ctx, initializer=_iw_init,
                                           initargs=(*args, wahl, app.gpu_jobs, ctx.Value("i", 0)))
            try:
                futures = [self._ex.submit(_iw_job, a) for a in rest]
                for f in as_completed(futures):
                    r = f.result()
                    self._rechner_merken(r)
                    puffer.append(r)
                    fertig.add(r["rel"])
                    self.status["fertig"] += 1
                    if len(puffer) >= 48:
                        self._schreiben(puffer)
                        self.personen_zuordnen()
                        puffer = []
                rest = []
            except BrokenProcessPool:  # ein Bild hat einen Prozess abgeschossen: Rest einzeln prüfen
                verdacht = [a for a in rest if a[0] not in fertig]
                rest = []
            except Exception:
                if self._stopp:
                    return
                raise
            finally:
                self._ex.shutdown(wait=False, cancel_futures=True)
                self._ex = None
                if puffer:
                    self._schreiben(puffer)
        if verdacht:
            self.prozesse, self.gpu_prozesse = 1, 0
        for a in verdacht:  # einzeln und auf der CPU: vielleicht hat die GPU den Prozess abstürzen lassen
            if self._stopp:
                return
            with ProcessPoolExecutor(1, mp_context=ctx, initializer=_iw_init, initargs=args) as einzel:
                try:
                    r = einzel.submit(_iw_job, a).result()
                except BrokenProcessPool:
                    r = {"rel": a[0], "groesse": a[2], "mtime": a[3], "breite": None, "hoehe": None, "zeit": None,
                         "gps": None, "kamera": None, "gesichter": [], "fehler": "Absturz beim Lesen"}
            self._rechner_merken(r)
            self._schreiben([r])
            self.status["fertig"] += 1
