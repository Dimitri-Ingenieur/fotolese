"""fotolese.web.archiv – Zugriff auf den Sortiert-Ordner: Ordner 0001–99999, Bilder, NEF-Begleiter.

Verbesserte Fassungen (ComfyUI) liegen im Unterordner „verbessert“ eines Ordners. Sie zählen als eigene Bilder
mit dem Namen „verbessert/<Datei>“ und stehen in der Liste direkt hinter ihrem Original.
"""
import os
import threading
import time

from fotolese.gemein import ordner_folge
from fotolese.web.konst import BILD_EXT, KOLORIERT, ORDNER_MUSTER, VERBESSERT
from fotolese.web.konfig import natuerlich


def _mtime(pfad):
    try:
        return os.stat(pfad).st_mtime_ns
    except OSError:
        return 0


def _lesen(pfad):
    """Bilder eines Verzeichnisses: ([(name, groesse, mtime_ns)], {Namensstamm: (NEF-Name, Größe)})."""
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
    return liste, roh


def _fassung_folge(eintrag):
    """Sortierschlüssel: die kolorierte Fassung (…_koloriert, …_koloriert_roh) direkt hinter ihrer Restaurierung."""
    stamm, endung = os.path.splitext(eintrag[0])
    for rang, zusatz in ((2, f"_{KOLORIERT}_roh"), (1, f"_{KOLORIERT}")):
        if stamm.casefold().endswith(zusatz):
            return natuerlich(stamm[:-len(zusatz)] + endung), rang
    return natuerlich(eintrag[0]), 0


def _einreihen(liste, verbessert):
    """Verbesserte Fassungen hinter ihr Original. Original ist das Bild, dessen Namensstamm der längste Anfang
    des verbesserten Namens vor einem „_“ ist: IMG_0001_1_Foto_restore gehört zu IMG_0001_1, nicht zu IMG_0001.
    Rückgabe: (Liste, {verbesserter Name: Original-Name}); Fassungen ohne Original stehen am Ende."""
    staemme = sorted(((os.path.splitext(n)[0].casefold(), n) for n, _, _ in liste), key=lambda s: -len(s[0]))
    je_original, herkunft, ohne = {}, {}, []
    for v in sorted(verbessert, key=_fassung_folge):
        stamm = os.path.splitext(v[0].split("/", 1)[1])[0].casefold()
        original = next((n for s, n in staemme if stamm.startswith(s + "_")), None)
        if original:
            je_original.setdefault(original, []).append(v)
            herkunft[v[0]] = original
        else:
            ohne.append(v)
    ergebnis = []
    for eintrag in liste:
        ergebnis.append(eintrag)
        ergebnis.extend(je_original.get(eintrag[0], []))
    return ergebnis + ohne, herkunft


class Archiv:
    def __init__(self, pfad):
        self.pfad = pfad
        self._ordner = (0.0, [])
        self._bilder = {}
        self._roh = {}
        self._herkunft = {}
        self._lock = threading.Lock()

    def ordner(self, frisch=False):
        with self._lock:
            stand, liste = self._ordner
            if not frisch and time.time() - stand < 5:
                return liste
        try:
            liste = sorted((d.name for d in os.scandir(self.pfad)
                            if ORDNER_MUSTER.fullmatch(d.name) and d.is_dir()), key=ordner_folge)
        except OSError:
            liste = []
        with self._lock:
            self._ordner = (time.time(), liste)
        return liste

    def bilder(self, ordner, frisch=False):
        """[(name, groesse, mtime_ns)] natürlich sortiert; nur JPG/JPEG/PNG, keine NEF. Dahinter jeweils die
        verbesserten Fassungen „verbessert/<Datei>“ des Bildes."""
        pfad = os.path.join(self.pfad, ordner)
        try:
            mt = (os.stat(pfad).st_mtime_ns, _mtime(os.path.join(pfad, VERBESSERT)))
        except OSError:
            return []
        with self._lock:
            alt = self._bilder.get(ordner)
            if not frisch and alt and alt[0] == mt and time.time() - alt[1] < 30:
                return alt[2]
        liste, roh = _lesen(pfad)
        herkunft = {}
        if mt[1]:
            verbessert = [(f"{VERBESSERT}/{n}", g, m) for n, g, m in _lesen(os.path.join(pfad, VERBESSERT))[0]]
            if verbessert:
                liste, herkunft = _einreihen(liste, verbessert)
        with self._lock:
            self._bilder[ordner] = (mt, time.time(), liste)
            self._roh[ordner] = roh
            self._herkunft[ordner] = herkunft
        return liste

    def roh(self, ordner):
        """{Namensstamm: (NEF-Name, Größe)} – zu welchem Bild es die RAW-Datei gibt."""
        self.bilder(ordner)
        with self._lock:
            return self._roh.get(ordner, {})

    def herkunft(self, ordner):
        """{„verbessert/<Datei>“: Name des Originals} für die verbesserten Fassungen eines Ordners."""
        self.bilder(ordner)
        with self._lock:
            return self._herkunft.get(ordner, {})

    def datei(self, ordner, name):
        """Pfad nur für Namen, die wirklich im Ordner liegen (kein Pfad-Trick möglich)."""
        for n, groesse, mt in self.bilder(ordner):
            if n == name:
                return os.path.join(self.pfad, ordner, n), groesse, mt
        return None
