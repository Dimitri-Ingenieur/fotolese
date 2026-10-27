"""fotolese.web.archiv – Zugriff auf den Sortiert-Ordner: Ordner 0001–9999, Bilder, NEF-Begleiter."""
import os
import threading
import time

from fotolese.web.konst import BILD_EXT, ORDNER_MUSTER
from fotolese.web.konfig import natuerlich


class Archiv:
    def __init__(self, pfad):
        self.pfad = pfad
        self._ordner = (0.0, [])
        self._bilder = {}
        self._roh = {}
        self._lock = threading.Lock()

    def ordner(self, frisch=False):
        with self._lock:
            stand, liste = self._ordner
            if not frisch and time.time() - stand < 5:
                return liste
        try:
            liste = sorted(d.name for d in os.scandir(self.pfad)
                           if ORDNER_MUSTER.fullmatch(d.name) and d.is_dir())
        except OSError:
            liste = []
        with self._lock:
            self._ordner = (time.time(), liste)
        return liste

    def bilder(self, ordner, frisch=False):
        """[(name, groesse, mtime_ns)] natürlich sortiert; nur JPG/JPEG/PNG, keine NEF."""
        pfad = os.path.join(self.pfad, ordner)
        try:
            mt = os.stat(pfad).st_mtime_ns
        except OSError:
            return []
        with self._lock:
            alt = self._bilder.get(ordner)
            if not frisch and alt and alt[0] == mt and time.time() - alt[1] < 30:
                return alt[2]
        liste, roh = [], {}
        try:
            for d in os.scandir(pfad):
                endung = os.path.splitext(d.name)[1].lower()
                if endung == ".nef" and not d.name.startswith("."):
                    try:
                        roh[os.path.splitext(d.name)[0].casefold()] = (d.name, d.stat().st_size)
                    except OSError:
                        pass
                    continue
                if d.name.startswith((".", "._")) or endung not in BILD_EXT:
                    continue
                try:
                    if d.is_file():
                        st = d.stat()
                        liste.append((d.name, st.st_size, st.st_mtime_ns))
                except OSError:
                    continue
        except OSError:
            pass
        liste.sort(key=lambda x: natuerlich(x[0]))
        with self._lock:
            self._bilder[ordner] = (mt, time.time(), liste)
            self._roh[ordner] = roh
        return liste

    def roh(self, ordner):
        """{Namensstamm: (NEF-Name, Größe)} – zu welchem Bild es die RAW-Datei gibt."""
        self.bilder(ordner)
        with self._lock:
            return self._roh.get(ordner, {})

    def datei(self, ordner, name):
        """Pfad nur für Namen, die wirklich im Ordner liegen (kein Pfad-Trick möglich)."""
        for n, groesse, mt in self.bilder(ordner):
            if n == name:
                return os.path.join(self.pfad, ordner, n), groesse, mt
        return None
