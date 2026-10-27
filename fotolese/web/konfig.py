"""fotolese.web.konfig – bestof.conf lesen/schreiben, Einstellungen (_env) und Textformate.

KONFIG und QUELLE sind Modul-Globals: cli.main setzt konfig.KONFIG, _env liest sie
beim Aufruf. QUELLE vermerkt je Einstellung die Herkunft (Umgebung/bestof.conf/Standard).
"""
import html
import math
import os
import re
import threading
from collections import OrderedDict
from urllib.parse import quote, unquote_to_bytes

from PIL import Image

from fotolese import gemein
from fotolese.web.konst import MONATE


KONFIG_VORLAGE = """\
# bestof.conf – Einstellungen für bestof.py. Liegt im selben Ordner wie bestof.py.
# Format: NAME = Wert. Text nach " #" ist Kommentar; Werte mit # in Anführungszeichen setzen.
# Umgebungsvariablen haben Vorrang (z. B. PORT=9000 python bestof.py …). Änderungen gelten nach dem Neustart.

# ---- Personen: bestof.py lernt aus Ihren Korrekturen und Bestätigungen ----
# Die beiden Werte stellt bestof.py selbst nach, sobald LERNEN_AB Fehlzuordnungen korrigiert wurden.
PERSON_SCHWELLE = 0.40   # ab dieser Ähnlichkeit kommt ein Gesicht automatisch zu einer Person
ABSTAND = 0.00           # so viel ähnlicher als jede andere benannte Person muss es sein, sonst neue Gruppe
# Gelernt: noch nicht
LERNEN = 1               # 1 = die Werte oben automatisch anpassen, 0 = nie
LERNEN_AB = 5            # neu lernen nach so vielen korrigierten Fehlzuordnungen
# NACHZIEHEN = 0.50      # beim Korrigieren wandern sehr ähnliche Gesichter derselben Gruppe mit; 1 = aus

# ---- Gesichtssuche – eine Änderung durchsucht alle Bilder neu (Namen bleiben) ----
# GESICHTER = 1          # 0 = keine Gesichtserkennung
# ERKENN_PX = 1920
# MIN_GESICHT = 48       # Pixel im Originalbild
# GESICHT_SCORE = 0.50
# GEGENPROBE = 0.80

# ---- Import ----
# IMPORT = 1             # 0 = Seite „Import“ aus
# IMPORT_JOBS = 4        # parallele Prozesse für fotosort; Standard: Hälfte der Kerne
# FOTOSORT = /pfad/zu/fotosort.py   # Standard: neben bestof.py

# ---- Server und Anzeige ----
# PORT = 8765
# HOST = 127.0.0.1       # 0.0.0.0 = auch im Heimnetz, dann PASSWORT setzen
# PASSWORT =
# BROWSER = 1
# MAX_BEST = 3
# BESTOF = BestOf
# GROSS = 2048
# PRO_SEITE = 120
# INDEX = 1
# INDEX_JOBS = 4         # Standard: Hälfte der Kerne
# ORT_MIN_EW = 10000
# NAEHE_KM = 15
# AKTUALISIEREN = 300
# DATEN = ~/.cache/fotosort
"""

LERN_SCHLUESSEL = ("PERSON_SCHWELLE", "ABSTAND")


class Konfig:
    """bestof.conf: NAME = Wert, # Kommentare. bestof.py schreibt nur gelernte Werte zurück und lässt
    Kommentare und eigene Zeilen stehen."""

    def __init__(self, pfad):
        self.pfad = pfad
        self.werte = {}
        self.lock = threading.Lock()
        self.schreibbar = True
        if not os.path.exists(pfad):
            try:
                self._schreiben(KONFIG_VORLAGE.splitlines())
                print(f"Einstellungen: {pfad} angelegt.")
            except OSError as fehler:
                self.schreibbar = False
                print(f"Hinweis: {pfad} lässt sich nicht anlegen ({fehler}) – es gelten Standardwerte.")
        self.laden()

    @staticmethod
    def zerlegen(zeile):
        """'NAME = Wert   # Kommentar' -> (NAME, Wert); Kommentar- und Leerzeilen -> None."""
        z = zeile.strip()
        if not z or z.startswith("#") or "=" not in z:
            return None
        name, wert = z.split("=", 1)
        name, wert = name.strip().upper(), wert.strip()
        if wert.startswith('"'):
            ende = wert.find('"', 1)
            wert = wert[1:ende] if ende > 0 else wert[1:]
        else:
            wert = re.split(r"\s+#", wert, maxsplit=1)[0].strip()
        return (name, wert) if re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) else None

    def laden(self):
        try:
            with open(self.pfad, encoding="utf-8") as f:
                self.werte = dict(p for p in map(self.zerlegen, f.read().splitlines()) if p)
        except OSError:
            self.werte = {}

    def _schreiben(self, zeilen):
        tmp = self.pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen) + "\n")
        os.replace(tmp, self.pfad)

    def setzen(self, neu, notiz=None):
        """Werte ändern (aktive Zeile, sonst auskommentierte, sonst anhängen) und „# Gelernt:“ erneuern."""
        if not self.schreibbar:
            return False
        with self.lock:
            try:
                with open(self.pfad, encoding="utf-8") as f:
                    zeilen = f.read().splitlines()
            except OSError:
                zeilen = KONFIG_VORLAGE.splitlines()
            for name, wert in neu.items():
                aktiv = [i for i, z in enumerate(zeilen) if (self.zerlegen(z) or ("",))[0] == name]
                aus = [i for i, z in enumerate(zeilen) if re.match(rf"\s*#\s*{name}\s*=", z)]
                i = aktiv[0] if aktiv else (aus[0] if aus else None)
                text = f"{name} = {wert}"
                if i is None:
                    zeilen.append(text)
                    continue
                kommentar = re.search(r"\s+(#.*)$", zeilen[i].split("=", 1)[1])
                zeilen[i] = f"{text:<24} {kommentar.group(1)}" if kommentar else text
            if notiz is not None:
                i = next((i for i, z in enumerate(zeilen) if z.startswith("# Gelernt:")), None)
                if i is None:
                    letzte = [i for i, z in enumerate(zeilen) if (self.zerlegen(z) or ("",))[0] in LERN_SCHLUESSEL]
                    i = (letzte[-1] + 1) if letzte else len(zeilen)
                    zeilen.insert(i, "")
                zeilen[i] = f"# Gelernt: {notiz}"
            try:
                self._schreiben(zeilen)
            except OSError as fehler:
                print(f"Hinweis: {self.pfad} lässt sich nicht schreiben ({fehler}).")
                return False
            self.werte.update({k: str(v) for k, v in neu.items()})
            return True


KONFIG = None   # wird in main() geladen
QUELLE = {}     # Name -> „Umgebung“ | „bestof.conf“ | „Standard“


def _env(name, standard, typ=str):
    """Einstellung: Umgebungsvariable vor bestof.conf vor Standardwert (siehe fotolese.gemein)."""
    return gemein._env(name, standard, typ,
                       konfig=(KONFIG.werte if KONFIG is not None else None), quelle=QUELLE)


def natuerlich(name):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name.casefold())]


def bilder_text(n):
    return "1 Bild" if n == 1 else f"{n} Bilder"


def url_id(name):
    return quote(os.fsencode(name), safe="")


def name_aus_id(teil):
    return os.fsdecode(unquote_to_bytes(teil))


def anzeige(name):
    return name.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def e(text):
    return html.escape(anzeige(str(text)), quote=True)


def zeit_text(zeit, kurz=False):
    if not zeit:
        return ""
    jahr, monat, tag = int(zeit[:4]), int(zeit[5:7]), int(zeit[8:10])
    if kurz:
        return f"{MONATE[monat]} {jahr}"
    return f"{tag}. {MONATE[monat]} {jahr}, {zeit[11:16]} Uhr"


def datum_kurz(sortzeit):
    """„März 2021“; bei von Hand gesetztem Jahr nur „1990“ (der Monat aus der Datei gilt dann nicht)."""
    if not sortzeit:
        return ""
    return sortzeit if len(sortzeit) == 4 else zeit_text(sortzeit, kurz=True)


def groesse_text(n):
    if n is None:
        return ""
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB".replace(".", ",")
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB".replace(".", ",")
    return f"{max(1, round(n / 1e3))} kB"


_MASSE, _MASSE_LOCK = OrderedDict(), threading.Lock()


def bildmasse(pfad, groesse, mt):
    """(Breite, Höhe) wie angezeigt (EXIF-Drehung beachtet); liest nur den Dateikopf. Für Bilder,
    die der Index noch nicht kennt."""
    schluessel = (pfad, groesse, mt)
    with _MASSE_LOCK:
        if schluessel in _MASSE:
            return _MASSE[schluessel]
    try:
        with Image.open(pfad) as img:
            w, h = img.size
            if img.getexif().get(0x0112, 1) in (5, 6, 7, 8):
                w, h = h, w
    except Exception:
        w = h = None
    with _MASSE_LOCK:
        _MASSE[schluessel] = (w, h)
        while len(_MASSE) > 20000:
            _MASSE.popitem(last=False)
    return w, h


def ort_text(ort, km, kurz=True):
    if not ort:
        return ""
    if km is None or km < 1.5:
        return ort
    return f"bei {ort}" if kurz else f"bei {ort} ({km:.0f} km)"


def km_zwischen(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742.0 * math.asin(min(1.0, math.sqrt(a)))
