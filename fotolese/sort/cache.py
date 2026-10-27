"""fotolese.sort.cache – Analyse-Ergebnisse und Prüfsummen in SQLite zwischenspeichern.

Merkt sich auch Bestandsbilder, damit Folgeläufe sie nicht neu analysieren müssen.
"""
import json
import os
import sqlite3

from fotolese.sort.konst import HASH_VERSION
from fotolese.sort.bericht import info


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
