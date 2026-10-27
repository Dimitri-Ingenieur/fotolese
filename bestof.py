#!/usr/bin/env python3
"""
bestof.py – Weboberfläche: Fotos durchsehen, filtern, je Ordner bis zu 3 beste Bilder auswählen.

Auswahl -> sofort Kopie in SORTIERT/BestOf:
  1 Bild ausgewählt    -> 0001.jpg
  2–3 Bilder           -> 0001a.jpg, 0001b.jpg, 0001c.jpg  (a = zuerst ausgewählt)
NEF-Dateien werden nicht angezeigt – fotosort.py legt zu jedem NEF ein JPG an.

Im Hintergrund entsteht ein Index (SORTIERT/.bestof-index.sqlite3):
  * Datum aus den EXIF-Daten (sonst aus dem Dateinamen), GPS -> nächster größerer Ort (GeoNames, offline)
  * Gesichter -> Personen (Person 1, Person 2 …), auf der Seite „Personen“ benennbar
Jahr:
  Jedes Bild hat ein Jahresfeld, vorausgefüllt aus EXIF oder Dateiname. Falsch (Scan, Kamerauhr,
  WhatsApp)? Jahr eintippen, Enter. Gelb = von Hand gesetzt; leeren + Enter = wieder Jahr aus der Datei.
  „für alle Bilder“ auf der Ordnerseite setzt das Jahr für den ganzen Ordner. Ein von Hand gesetztes Jahr
  ersetzt auch den Monat (gilt dann als unbekannt). Gespeichert im Index, die Bilddateien bleiben unverändert.
Gesichter:
  Suche in zwei Stufen (GESICHT_SCORE, GEGENPROBE), kleine Gesichter mit Merkmalen aus dem Originalbild.
  Fehlt trotzdem eins (sehr klein, Profil, verdeckt)? In der Lupe Gesichter einblenden (G) und ins Gesicht
  klicken – dort wird genauer gesucht. Findet die Suche nichts, lässt sich die Stelle mit Namen markieren.
  Der Knopf „Gesichter (N)“ ist immer da; die Zeile oben im Bild sagt, ob das Bild schon durchsucht ist.
Personen:
  Gleicher Name = dieselbe Person. Kinder- und Erwachsenenfotos landen oft in getrennten Gruppen;
  beide „Anna“ nennen genügt. Die Gruppen bleiben getrennt (je eigener Mittelwert), der Filter
  „Anna“ findet beide. „Gruppe lösen“ nimmt den Namen wieder weg.
  In der Lupe (G) das Namensschild anklicken: Name eintippen, dann
    „Alle N Gesichter dieser Gruppe“  – die ganze Gruppe heißt so (Standard bei „Person N“), oder
    „Nur dieses Gesicht“              – Korrektur: das Gesicht wechselt zur ähnlichsten Gruppe dieses
                                        Namens oder bildet eine neue; sehr ähnliche Gesichter derselben
                                        alten Gruppe (z. B. Serienbilder) wandern mit (NACHZIEHEN).
  Auf „Personen“: Namensfeld = ganze Gruppe, ✎ = nur dieses Gesicht (mit Nachziehen), ✕ = kein Gesicht.
  „Alle prüfen“ zeigt alle Gesichter einer Gruppe, untypische zuerst – dort stecken Verwechslungen
  (z. B. Kind in der Gruppe eines Elternteils). Anklicken (Umschalt = Bereich), Namen eintippen, fertig.
Import (Seite „Import“, braucht fotosort.py neben bestof.py):
  Ordner im Browser wählen, „In Sortiert kopieren“. fotosort.py kopiert alle Fotos samt Unterordnern (Quelle
  bleibt unverändert), sortiert ähnliche in Ordner, ergänzt passende bestehende, legt zu NEF ein JPG an.
  Inhaltsgleiche Dateien (SHA-256) kommen nur einmal ins Archiv; danach behält das Archiv von jedem Inhalt
  genau eine Datei (bevorzugt: in BestOf ausgewählt, mit Labels, ohne Laufindex). Überzählige wandern in den
  Papierkorb SORTIERT/.duplikate/<Zeit>/ (mit liste.csv), „Papierkorb leeren“ löscht sie.
  „Abbrechen“ stoppt nach dem laufenden Ordner, „Import rückgängig“ entfernt die Kopien des letzten Imports.
Ordneransicht: unter jedem Foto Auflösung, Dateigröße und – falls vorhanden – Größe der NEF-Datei;
  die höchste Auflösung im Ordner ist gelb markiert.
Einstellungen und Lernen (bestof.conf neben bestof.py, wird beim ersten Start angelegt):
  NAME = Wert je Zeile; Umgebungsvariablen haben Vorrang. Jede Korrektur einer automatischen Zuordnung
  (Gesicht „Thomas“ ist in Wahrheit „Paul“) und jede Bestätigung (Schild anklicken + Enter, „Ausgewählte
  bestätigen“) ist ein Label. Nach LERNEN_AB Korrekturen stellt bestof.py PERSON_SCHWELLE und ABSTAND so ein,
  dass diese Fehler nicht wieder passieren, ohne bestätigte Gesichter zu verlieren, schreibt sie in bestof.conf
  und verschiebt automatisch zugeordnete Gesichter, die eindeutig zu einer anderen benannten Person passen.
  Ihre eigenen Zuordnungen bleiben unangetastet. Auf „Personen“ steht der Lernstand, „Jetzt lernen“ startet es sofort.
Filter im Suchfeld, Begriffe mit Komma trennen:
  2023, Leipzig, Anna    -> Fotos aus 2023, höchstens NAEHE_KM von Leipzig, auf denen Anna ist
  Juli 2023 | 2023-07 | 0012 (Ordner) | Person 7 | ohne Jahr | Jahr korrigiert | Teil eines Dateinamens

Aufruf (Conda-Umgebung von fotosort.py):
  python -m pip install opencv-python-headless   # nur für die Gesichtserkennung nötig
  python bestof.py /media/$USER/EXTERN/Sortiert

Tasten im Ordner:  ← / →  voriger / nächster Ordner,  N  nächster Ordner ohne Auswahl
Tasten in der Lupe: ← / →  Bild,  Leertaste  aus- / abwählen,  G  Gesichter zeigen,  J  Jahr ändern,  Esc  schließen
                    (Namensschild anklicken = benennen: ganze Gruppe oder nur dieses Gesicht;
                     Gesicht fehlt = bei eingeblendeten Gesichtern ins Gesicht klicken)

Umgebungsvariablen (Standard in Klammern):
  PORT       (8765)
  HOST       (127.0.0.1)   0.0.0.0 = auch von Tablet/Handy im Heimnetz (dann PASSWORT setzen)
  PASSWORT   ()            Passwortschutz, Benutzername beliebig
  MAX_BEST   (3)           höchstens so viele Bilder je Ordner
  BESTOF     (BestOf)      Zielordner, relativ zu SORTIERT oder absolut
  VORSCHAU   (SORTIERT/.vorschau)  Ordner für Vorschaubilder, 0 = nur Arbeitsspeicher
  GROSS      (2048)        Kantenlänge der Lupe in Pixel, 0 = Originaldatei
  PRO_SEITE  (120)         Ordner je Übersichtsseite
  BROWSER    (1)           Browser beim Start öffnen
  INDEX      (1)           0 = kein Index (keine Metadaten, Orte, Personen, Filter)
  GESICHTER  (1)           0 = keine Gesichtserkennung
  INDEX_JOBS (Kerne/2)     parallele Prozesse für den Index
  ORT_MIN_EW (10000)       „größerer Ort“ = mindestens so viele Einwohner
  NAEHE_KM   (15)          Umkreis für Ortsfilter
  PERSON_SCHWELLE (0.40)   Ähnlichkeit für dieselbe Person (höher = strenger) – wird gelernt
  ABSTAND    (0.00)        so viel ähnlicher als jede andere benannte Person, sonst neue Gruppe – wird gelernt
  LERNEN     (1)           0 = Schwelle und Abstand nie automatisch ändern
  LERNEN_AB  (5)           neu lernen nach so vielen korrigierten Fehlzuordnungen
  BESTOF_CONF (bestof.conf neben dem Skript)  andere Einstellungsdatei
  IMPORT     (1)           0 = Seite „Import“ aus (ohne PASSWORT ohnehin nur bei HOST=127.0.0.1)
  IMPORT_JOBS (Kerne/2)    parallele Prozesse für fotosort beim Import (HDD/USB: z. B. 2–4)
  FOTOSORT   (fotosort.py neben bestof.py)
  NACHZIEHEN (0.50)        beim Korrigieren eines Gesichts wandern Gesichter derselben Gruppe mit, die ihm
                           mindestens so ähnlich sind und ihm ähnlicher als dem Rest der Gruppe; 1 = aus
  ERKENN_PX  (1920)        Bildgröße für die Gesichtssuche (größer = findet kleinere Gesichter, langsamer);
                           die Merkmale kleiner Gesichter kommen aus dem Originalbild
  MIN_GESICHT (48)         kleinere Gesichter ignorieren (Pixel im Originalbild)
  GESICHT_SCORE (0.50)     Mindestsicherheit der Gesichtssuche, 1. Stufe (kleiner = mehr Kandidaten)
  GEGENPROBE (0.80)        2. Stufe: Kandidat muss im vergrößerten Ausschnitt erneut gefunden werden –
                           filtert Muster (Buchstaben, Fell, Stoff) heraus; 0 = aus
                           Ändert sich einer dieser Werte, durchsucht der Index alle Bilder neu nach Gesichtern;
                           Namen und Korrekturen bleiben erhalten (Gesicht an gleicher Stelle im Bild).
  AKTUALISIEREN (300)      Sekunden bis zur nächsten Suche nach neuen Bildern
  DATEN      (~/.cache/fotosort)   Ablage für Gesichtsmodelle und Ortsdaten

Daten, die beim ersten Start einmalig geladen werden:
  GeoNames cities1000 (CC BY 4.0)        https://download.geonames.org/export/dump/cities1000.zip
  YuNet Gesichtserkennung (MIT), SFace Gesichtsmerkmale (Apache 2.0) aus github.com/opencv/opencv_zoo
Alles Weitere läuft lokal; keine Fotos verlassen den Rechner.
"""
import base64
import csv
import hashlib
import hmac
import html
import io
import json
import math
import multiprocessing as mp
import os
import random
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import warnings
import webbrowser
import zipfile
from collections import OrderedDict, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import find_spec
from urllib.parse import parse_qs, quote, unquote_to_bytes, urlencode, urlsplit

import numpy as np
from PIL import Image, ImageFile, ImageOps

VERSION = "2.7.1"
BILD_EXT = {".jpg", ".jpeg", ".png"}
ORDNER_MUSTER = re.compile(r"\d{4}")
BESTOF_MUSTER = re.compile(r"(\d{4})([a-z]?)\.(jpg|png)")
BUCHSTABEN = "abcdefghijklmnopqrstuvwxyz"
THUMB = 480
MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]
MONAT_NR = {m.casefold(): i for i, m in enumerate(MONATE) if m}
MONAT_NR.update({"maerz": 3, "jänner": 1, "jan": 1, "feb": 2, "mär": 3, "apr": 4, "jun": 6, "jul": 7,
                 "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12})
GEONAMES_URL = "https://download.geonames.org/export/dump/cities1000.zip"
MODELLE = {
    "yunet": ("face_detection_yunet_2023mar.onnx",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
              "face_detection_yunet_2023mar.onnx",
              "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "sface": ("face_recognition_sface_2021dec.onnx",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/"
              "face_recognition_sface_2021dec.onnx",
              "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True  # abgeschnittene Dateien so weit wie möglich zeigen


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
    """Einstellung: Umgebungsvariable vor bestof.conf vor Standardwert."""
    roh, quelle = os.environ.get(name, "").strip(), "Umgebung"
    if roh == "" and KONFIG is not None:
        roh, quelle = KONFIG.werte.get(name, "").strip(), "bestof.conf"
    if roh == "":
        QUELLE[name] = "Standard"
        return standard
    try:
        wert = typ(roh)
    except ValueError:
        if quelle == "Umgebung":
            sys.exit(f"Fehler: {name}={roh!r} ist ungültig.")
        print(f"Hinweis: {name} = {roh!r} in bestof.conf ist ungültig – es gilt {standard}.")
        QUELLE[name] = "Standard"
        return standard
    QUELLE[name] = quelle
    return wert


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


# ---------------------------------------------------------------- Archiv
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


# ---------------------------------------------------------------- Bilder
def _draft_groesse(w, h, kante):
    if w >= h:
        return kante, max(1, kante * h // max(w, 1))
    return max(1, kante * w // max(h, 1)), kante


def _rgb(img):
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N"):
        img = img.convert("I")
    if img.mode in ("I", "F"):
        hoch = img.getextrema()[1] or 1
        if hoch > 255:
            img = img.point(lambda v: v * (255.0 / hoch))
        img = img.convert("L")
    if img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        weiss = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(weiss, rgba)
    return img.convert("RGB")


def oeffne(pfad, kante):
    """Bild aufrecht als RGB laden; JPEG nur so groß dekodieren wie nötig (kante 0 = voll)."""
    with Image.open(pfad) as img:
        if kante and img.format in ("JPEG", "MPO"):
            img.draft("RGB", _draft_groesse(img.width, img.height, kante))
        img.load()
        img = ImageOps.exif_transpose(img)
        return _rgb(img)


def als_jpeg(img, kante, qualitaet):
    if kante and max(img.size) > kante:
        img.thumbnail((kante, kante), Image.Resampling.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=qualitaet)
    return b.getvalue()


def thumb_schluessel(pfad, groesse, mt):
    return hashlib.sha1(f"{pfad}|{groesse}|{mt}|{THUMB}".encode("utf-8", "surrogateescape")).hexdigest()


def atomar_schreiben(datei, daten):
    os.makedirs(os.path.dirname(datei), exist_ok=True)
    tmp = f"{datei}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "wb") as f:
        f.write(daten)
    os.replace(tmp, datei)


PLATZHALTER = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><rect width="120" height="90" '
               b'fill="#444"/><text x="60" y="50" fill="#bbb" font-size="11" text-anchor="middle" '
               b'font-family="sans-serif">nicht lesbar</text></svg>')


class Vorschau:
    """Vorschaubilder auf Platte (Standard: SORTIERT/.vorschau), Lupenbilder im Arbeitsspeicher."""

    def __init__(self, ordner, gross):
        self.ordner = ordner
        self.gross = gross
        self._ram = OrderedDict()
        self._ram_bytes = 0
        self._lock = threading.Lock()

    def _ram_holen(self, key):
        with self._lock:
            if key in self._ram:
                self._ram.move_to_end(key)
                return self._ram[key]
        return None

    def _ram_ablegen(self, key, daten):
        with self._lock:
            if key in self._ram:
                return
            self._ram[key] = daten
            self._ram_bytes += len(daten[1])
            while self._ram_bytes > 256 * 1024 * 1024 and self._ram:
                _, alt = self._ram.popitem(last=False)
                self._ram_bytes -= len(alt[1])

    def _platte(self, key, erzeugen):
        if self.ordner:
            datei = os.path.join(self.ordner, key[:2], key + ".jpg")
            try:
                with open(datei, "rb") as f:
                    return "image/jpeg", f.read()
            except OSError:
                pass
        treffer = self._ram_holen(key)
        if treffer:
            return treffer
        daten = ("image/jpeg", erzeugen())
        if self.ordner:
            try:
                atomar_schreiben(datei, daten[1])
                return daten
            except OSError:
                pass
        self._ram_ablegen(key, daten)
        return daten

    def klein(self, pfad, groesse, mt):
        return self._platte(thumb_schluessel(pfad, groesse, mt),
                            lambda: als_jpeg(oeffne(pfad, THUMB), THUMB, 80))

    def gesicht(self, gid, pfad, mt, box):
        x, y, w, h = box

        def erzeugen():
            seite = max(w, h)
            with Image.open(pfad) as img:
                lang = max(img.size)
                if img.format in ("JPEG", "MPO"):
                    ziel = min(lang, int(320 / max(seite, 0.01)))
                    img.draft("RGB", _draft_groesse(img.width, img.height, ziel))
                img.load()
                bild = _rgb(ImageOps.exif_transpose(img))
            bw, bh = bild.size
            cx, cy, s = (x + w / 2) * bw, (y + h / 2) * bh, max(w * bw, h * bh) * 0.8
            ausschnitt = bild.crop((int(cx - s), int(cy - s), int(cx + s), int(cy + s)))
            return als_jpeg(ausschnitt.resize((176, 176), Image.Resampling.LANCZOS), 0, 85)

        schluessel = f"gesicht|{gid}|{pfad}|{mt}|{x:.4f}|{y:.4f}|{w:.4f}|{h:.4f}"  # Kasten gehört dazu: IDs können neu vergeben werden
        return self._platte(hashlib.sha1(schluessel.encode("utf-8", "surrogateescape")).hexdigest(), erzeugen)

    def gross_bild(self, pfad, groesse, mt):
        ext = os.path.splitext(pfad)[1].lower()
        if self.gross == 0:
            with open(pfad, "rb") as f:
                return ("image/png" if ext == ".png" else "image/jpeg"), f.read()
        key = f"{pfad}|{groesse}|{mt}|{self.gross}"
        treffer = self._ram_holen(key)
        if treffer:
            return treffer
        daten = ("image/jpeg", als_jpeg(oeffne(pfad, self.gross), self.gross, 88))
        self._ram_ablegen(key, daten)
        return daten


# ---------------------------------------------------------------- Auswahl und BestOf
class Auswahl:
    def __init__(self, archiv, bestof, max_best):
        self.archiv, self.bestof, self.max_best = archiv, bestof, max_best
        self.pfad = os.path.join(archiv.pfad, ".bestof-auswahl.json")
        self.lock = threading.Lock()
        self.daten = {"version": 1, "ordner": {}}
        try:
            with open(self.pfad, encoding="utf-8") as f:
                geladen = json.load(f)
            if isinstance(geladen.get("ordner"), dict):
                self.daten = geladen
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as fehler:
            sys.exit(f"Fehler: {self.pfad} ist nicht lesbar ({fehler}). Datei prüfen oder umbenennen.")

    def markiert(self, ordner):
        return list(self.daten["ordner"].get(ordner, {}).get("markiert", []))

    def anzahl_bilder(self):
        return sum(len(v.get("markiert", [])) for v in self.daten["ordner"].values())

    def mit_auswahl(self):
        return {o for o, v in self.daten["ordner"].items() if v.get("markiert")}

    def ziele(self, ordner, markiert=None):
        markiert = self.markiert(ordner) if markiert is None else markiert
        return {m: f"{ordner}{'' if len(markiert) == 1 else BUCHSTABEN[k]}{self._endung(m)}"
                for k, m in enumerate(markiert)}

    @staticmethod
    def _endung(name):
        ext = os.path.splitext(name)[1].lower()
        return ".jpg" if ext == ".jpeg" else ext

    def _speichern(self):
        tmp = self.pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.daten, f, ensure_ascii=True, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.pfad)

    @staticmethod
    def _kopiere(quelle, ziel):
        tmp = ziel + ".tmp-bestof"
        try:
            shutil.copyfile(quelle, tmp)
            try:
                shutil.copystat(quelle, tmp)
            except OSError:
                pass  # exFAT/NTFS: Rechte nicht übertragbar
            os.replace(tmp, ziel)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _abgleichen(self, ordner, markiert, alles_neu=False):
        """BestOf für einen Ordner auf den Stand von 'markiert' bringen. Erst kopieren, dann aufräumen."""
        vorhanden = {n for n, *_ in self.archiv.bilder(ordner)}
        markiert = [m for m in markiert if m in vorhanden][:self.max_best]
        soll = {ziel: m for m, ziel in self.ziele(ordner, markiert).items()}
        alt = {} if alles_neu else self.daten["ordner"].get(ordner, {}).get("kopien", {})
        kopien = {}
        if soll:
            os.makedirs(self.bestof, exist_ok=True)
        for ziel, quelle in soll.items():
            qp = os.path.join(self.archiv.pfad, ordner, quelle)
            st = os.stat(qp)
            merk = [quelle, st.st_size, st.st_mtime_ns]
            zp = os.path.join(self.bestof, ziel)
            if alt.get(ziel) != merk or not os.path.exists(zp):
                self._kopiere(qp, zp)
            kopien[ziel] = merk
        if os.path.isdir(self.bestof):
            for d in os.scandir(self.bestof):
                m = BESTOF_MUSTER.fullmatch(d.name)
                if m and m.group(1) == ordner and d.name not in soll:
                    os.unlink(d.path)
        if markiert:
            self.daten["ordner"][ordner] = {"markiert": markiert, "kopien": kopien}
        else:
            self.daten["ordner"].pop(ordner, None)
        return markiert

    def bereinigen(self, ordner):
        """Markierungen von Dateien entfernen, die nicht mehr im Ordner liegen."""
        with self.lock:
            alt = self.markiert(ordner)
            if not alt:
                return
            vorhanden = {n for n, *_ in self.archiv.bilder(ordner)}
            if all(m in vorhanden for m in alt):
                return
            try:
                self._abgleichen(ordner, alt)
                self._speichern()
            except OSError:
                pass

    def umschalten(self, ordner, name):
        with self.lock:
            alt = self.markiert(ordner)
            if name in alt:
                neu = [m for m in alt if m != name]
            elif len(alt) >= self.max_best:
                return 409, {"fehler": f"Schon {self.max_best} Bilder aus Ordner {ordner} ausgewählt. "
                                       f"Wählen Sie erst eines ab."}
            else:
                neu = alt + [name]
            try:
                markiert = self._abgleichen(ordner, neu)
                self._speichern()
            except OSError as fehler:
                try:
                    self._abgleichen(ordner, alt)
                except OSError:
                    pass
                grund = fehler.strerror or str(fehler)
                return 500, {"fehler": f"Kopieren nach BestOf fehlgeschlagen: {grund}. Auswahl unverändert."}
            ziele = self.ziele(ordner, markiert)
            if name in markiert:
                meldung = f"Als {ziele[name]} in BestOf kopiert."
            elif markiert:
                meldung = "Abgewählt. In BestOf: " + ", ".join(ziele[m] for m in markiert) + "."
            else:
                meldung = "Abgewählt. Aus diesem Ordner liegt nichts mehr in BestOf."
            return 200, {"auswahl": [url_id(m) for m in markiert],
                         "ziele": {url_id(m): z for m, z in ziele.items()}, "meldung": meldung}

    def neu_aufbauen(self):
        with self.lock:
            fehler = 0
            for ordner in list(self.daten["ordner"]):
                try:
                    self._abgleichen(ordner, self.markiert(ordner), alles_neu=True)
                except OSError:
                    fehler += 1
            gueltig = set(self.daten["ordner"])
            entfernt = 0
            if os.path.isdir(self.bestof):
                for d in os.scandir(self.bestof):
                    m = BESTOF_MUSTER.fullmatch(d.name)
                    if m and m.group(1) not in gueltig:
                        os.unlink(d.path)
                        entfernt += 1
            self._speichern()
            n = len(gueltig)
            return {"meldung": f"BestOf neu aufgebaut: {bilder_text(self.anzahl_bilder())} aus "
                               f"{n} Ordner{'' if n == 1 else 'n'}, {entfernt} veraltete Dateien entfernt"
                               + (f", {fehler} Ordner mit Fehlern." if fehler else ".")}


# ---------------------------------------------------------------- Orte (GeoNames, offline)
class Orte:
    AUSGESCHLOSSEN = {"PPLX", "PPLH", "PPLQ", "PPLW", "PPLCH"}  # Ortsteile, historische Orte

    def __init__(self, zip_pfad, min_ew):
        self.zip_pfad, self.min_ew = zip_pfad, min_ew
        self.bereit = False
        self._namen, self._lat, self._lon, self._such = [], None, None, {}

    def laden(self):
        namen, lat, lon, such = [], [], [], {}
        with zipfile.ZipFile(self.zip_pfad) as z:
            txt = next(n for n in z.namelist() if n.endswith(".txt"))
            with z.open(txt) as roh:
                for zeile in io.TextIOWrapper(roh, encoding="utf-8"):
                    t = zeile.rstrip("\n").split("\t")
                    if len(t) < 15:
                        continue
                    try:
                        breite, laenge, ew = float(t[4]), float(t[5]), int(t[14] or 0)
                    except ValueError:
                        continue
                    eintrag = (ew, t[1], breite, laenge, t[8])
                    schluessel = {t[1].casefold(), t[2].casefold()}
                    if ew >= 500000:
                        schluessel.update(a.casefold() for a in t[3].split(",") if a)
                    for k in schluessel:
                        if k and (k not in such or such[k][0] < ew):
                            such[k] = eintrag
                    if ew >= self.min_ew and t[7] not in self.AUSGESCHLOSSEN:
                        namen.append(t[1])
                        lat.append(breite)
                        lon.append(laenge)
        self._namen = namen
        self._lat, self._lon = np.radians(np.array(lat)), np.radians(np.array(lon))
        self._such = such
        self.bereit = True
        return len(namen), len(such)

    def naechster(self, lat, lon):
        if not self.bereit or not self._namen:
            return None, None
        p, la = math.radians(lat), math.radians(lon)
        a = (np.sin((self._lat - p) / 2) ** 2
             + math.cos(p) * np.cos(self._lat) * np.sin((self._lon - la) / 2) ** 2)
        i = int(np.argmin(a))
        return self._namen[i], round(12742.0 * math.asin(min(1.0, math.sqrt(float(a[i])))), 1)

    def suchen(self, text):
        treffer = self._such.get(text.casefold()) if self.bereit else None
        return None if treffer is None else {"name": treffer[1], "lat": treffer[2], "lon": treffer[3]}


# ---------------------------------------------------------------- Index (SQLite)
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


def _ueberlappung(a, b):
    """Überlappung zweier Kästen (x, y, w, h) als Schnitt/Vereinigung (IoU), 0–1."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    schnitt = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    vereinigt = a[2] * a[3] + b[2] * b[3] - schnitt
    return schnitt / vereinigt if vereinigt > 0 else 0.0


def _ueberdeckung(a, b):
    """Anteil des kleineren Kastens, der im anderen liegt (1 = ganz darin) – erkennt doppelte Kästen
    um dasselbe Gesicht, z. B. einmal mit und einmal ohne Mütze."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    kleiner = min(a[2] * a[3], b[2] * b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1) / kleiner if kleiner > 0 else 0.0


def personen_namen(index):
    return {pid: (name or f"Person {pid}", ign, anzahl)
            for pid, name, ign, anzahl in index.q("SELECT id, name, ignoriert, anzahl FROM person")}


def namensliste(index):
    """Vergebene Namen für die Eingabehilfe (gleiche Schreibweise = gleiche Person)."""
    namen = {}
    for (n,) in index.q("SELECT name FROM person WHERE name IS NOT NULL AND ignoriert=0 AND anzahl>0") if index else []:
        namen.setdefault(n.casefold(), n)
    return sorted(namen.values(), key=str.casefold)


# ---------------------------------------------------------------- Index-Prozesse (Gesichter, EXIF)
_IW = {}


def _iw_init(yunet, sface, erkenn_px, min_px, vorschau, score=0.5, gegenprobe=0.8):
    warnings.simplefilter("ignore")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _IW.update(erkenn_px=erkenn_px, min_px=min_px, vorschau=vorschau, gegenprobe=gegenprobe, det=None, rec=None)
    if yunet and sface:
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        import cv2
        cv2.setNumThreads(1)
        _IW["cv2"] = cv2
        _IW["det"] = cv2.FaceDetectorYN.create(yunet, "", (320, 320), score, 0.3, 5000)
        _IW["rec"] = cv2.FaceRecognizerSF.create(sface, "")


def _gegenprobe(cv2, det, src, f, faktor):
    """Gesicht im vergrößerten Ausschnitt noch einmal suchen. Echte Gesichter werden in beiden Maßstäben
    sicher gefunden (Test: 0,77–0,95), Muster wie Buchstaben oder Fell nicht (meist 0). Rückgabe: Sicherheit."""
    x, y, w, h = (float(v) * faktor for v in f[:4])
    seite, cx, cy = 2.2 * max(w, h), x + w / 2, y + h / 2
    hoehe, breite = src.shape[:2]
    x0, y0 = int(max(0, cx - seite / 2)), int(max(0, cy - seite / 2))
    x1, y1 = int(min(breite, cx + seite / 2)), int(min(hoehe, cy + seite / 2))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    stueck = src[y0:y1, x0:x1]
    k = 320 / max(stueck.shape[:2])
    klein = cv2.resize(stueck, (max(1, round(stueck.shape[1] * k)), max(1, round(stueck.shape[0] * k))),
                       interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    det.setInputSize((klein.shape[1], klein.shape[0]))
    _, treffer = det.detect(klein)
    beste = 0.0
    for q in (treffer if treffer is not None else []):
        if _ueberlappung((x, y, w, h), (x0 + q[0] / k, y0 + q[1] / k, q[2] / k, q[3] / k)) > 0.3:
            beste = max(beste, float(q[14]))
    return beste


def _exif_zeit(ex, sub):
    for roh in (sub.get(0x9003), sub.get(0x9004), ex.get(0x0132)):
        s = (roh.decode("ascii", "ignore") if isinstance(roh, bytes) else str(roh or "")).replace("\x00", "").strip()
        m = re.match(r"((?:19|20)\d\d)[:\-](\d\d)[:\-](\d\d)[ T](\d\d):(\d\d):(\d\d)", s)
        if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return None


def _datum_aus_name(name):
    """Fallback ohne EXIF: Datum im Dateinamen, z. B. IMG-20230714-WA0003.jpg, 20230714_103200.jpg,
    Screenshot_2023-07-14-10-32-00.png."""
    m = re.search(r"(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
                  r"(?:[-_. T]?([01]\d|2[0-3])[-_.:]?([0-5]\d)[-_.:]?([0-5]\d))?(?!\d)", name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4) or '12'}:{m.group(5) or '00'}:{m.group(6) or '00'}"


def _exif_gps(ex):
    try:
        g = ex.get_ifd(0x8825)
    except Exception:
        return None
    if not g:
        return None

    def grad(werte, ref):
        try:
            d, m, s = (float(x) for x in werte)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        v = d + m / 60 + s / 3600
        if math.isnan(v):
            return None
        ref = ref.decode("ascii", "ignore") if isinstance(ref, bytes) else str(ref or "")
        return -v if ref.strip().upper()[:1] in ("S", "W") else v

    lat, lon = grad(g.get(2), g.get(1)), grad(g.get(4), g.get(3))
    if lat is None or lon is None or (abs(lat) < 1e-6 and abs(lon) < 1e-6):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 6), round(lon, 6)


def _iw_job(auftrag):
    rel, pfad, groesse, mt, gesichter_an = auftrag
    erg = {"rel": rel, "groesse": groesse, "mtime": mt, "breite": None, "hoehe": None, "zeit": None,
           "gps": None, "kamera": None, "gesichter": None, "fehler": None}
    try:
        with Image.open(pfad) as img:
            ex = img.getexif()
            try:
                sub = ex.get_ifd(0x8769)
            except Exception:
                sub = {}
            erg["zeit"] = _exif_zeit(ex, sub) or _datum_aus_name(os.path.basename(pfad))
            erg["gps"] = _exif_gps(ex)
            modell = ex.get(0x0110)
            erg["kamera"] = str(modell).replace("\x00", "").strip() or None if modell else None
            o = ex.get(0x0112, 1)
            w, h = img.size
            erg["breite"], erg["hoehe"] = (h, w) if o in (5, 6, 7, 8) else (w, h)
            if not (gesichter_an and _IW.get("det")):
                return erg
            if img.format in ("JPEG", "MPO"):
                img.draft("RGB", _draft_groesse(img.width, img.height, _IW["erkenn_px"]))
            img.load()
            bild = _rgb(ImageOps.exif_transpose(img))
        if _IW["vorschau"]:  # Vorschaubild gleich mit anlegen – spart später einen Lesevorgang
            datei = os.path.join(_IW["vorschau"], *(lambda k: (k[:2], k + ".jpg"))(thumb_schluessel(pfad, groesse, mt)))
            if not os.path.exists(datei):
                try:
                    atomar_schreiben(datei, als_jpeg(bild.copy(), THUMB, 80))
                except OSError:
                    pass
        erkenn = bild
        if max(bild.size) > _IW["erkenn_px"]:
            erkenn = bild.copy()
            erkenn.thumbnail((_IW["erkenn_px"], _IW["erkenn_px"]), Image.Resampling.LANCZOS)
        cv2, det, rec = _IW["cv2"], _IW["det"], _IW["rec"]
        a = cv2.cvtColor(np.asarray(erkenn), cv2.COLOR_RGB2BGR)
        bh, bw = a.shape[:2]
        det.setInputSize((bw, bh))
        _, treffer = det.detect(a)
        s_d = bild.width / bw                                   # dekodiertes Bild : Suchbild
        s_o = max(s_d, (erg["breite"] or bild.width) / bw)      # Original : Suchbild
        quellen = {"erkenn": a}

        def quelle(art):  # Bild für die Merkmale, je Bild höchstens einmal erzeugt
            if art not in quellen:
                if art == "bild":
                    quellen[art] = cv2.cvtColor(np.asarray(bild), cv2.COLOR_RGB2BGR)
                else:
                    with Image.open(pfad) as voll:
                        voll.load()
                        quellen[art] = cv2.cvtColor(np.asarray(_rgb(ImageOps.exif_transpose(voll))), cv2.COLOR_RGB2BGR)
            return quellen[art]

        gefunden = []
        for f in (treffer if treffer is not None else []):
            x, y, fw, fh, score = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[14])
            groesse = min(fw, fh) * s_o  # Gesichtsgröße im Original
            if groesse < _IW["min_px"]:
                continue
            # Merkmale aus möglichst hoher Auflösung – kleine Gesichter (Gruppenfotos) aus dem Original
            if min(fw, fh) * s_d >= 96 or s_o <= s_d * 1.01:
                art, faktor = ("erkenn", 1.0) if s_d <= 1.001 else ("bild", s_d)
            else:
                art, faktor = "voll", s_o
            if _IW["gegenprobe"] > 0 and _gegenprobe(cv2, det, quelle(art), f, faktor) < _IW["gegenprobe"]:
                continue  # nur in einem Maßstab gefunden: wahrscheinlich Muster, kein Gesicht
            g = f.copy()
            g[:14] *= faktor
            merkmal = rec.feature(rec.alignCrop(quelle(art), g)).astype(np.float32).flatten()
            norm = float(np.linalg.norm(merkmal))
            if norm <= 0:
                continue
            gefunden.append((max(x, 0) / bw, max(y, 0) / bh, fw / bw, fh / bh, score, round(groesse),
                             (merkmal / norm).tobytes()))
        def doppelt(k, b):  # zwei Kästen um dasselbe Gesicht (z. B. Stirn+Augen und Augen+Kinn)
            u = _ueberdeckung(k[:4], b[:4])
            return u >= 0.5 or (u >= 0.2 and float(np.frombuffer(k[6], np.float32) @ np.frombuffer(b[6], np.float32)) >= 0.6)

        behalten = []  # den sichereren Kasten behalten
        for kandidat in sorted(gefunden, key=lambda k: -k[4]):
            if not any(doppelt(kandidat, k) for k in behalten):
                behalten.append(kandidat)
        erg["gesichter"] = behalten
    except Exception as fehler:
        erg["fehler"] = f"{type(fehler).__name__}: {fehler}"[:200]
    return erg


class GesichtsSucher:
    """Sucht ein Gesicht an einer angeklickten Stelle – für Gesichter, die der Index übersehen hat.
    Kleines Fenster zuerst (das Gesicht unter dem Klick), großzügige Schwelle, Merkmale aus voller Auflösung."""

    def __init__(self, modelle):
        self.modelle = modelle
        self.lock = threading.Lock()
        self.cv2 = self.det = self.rec = None

    def suchen(self, pfad, x, y):
        with self.lock:
            if self.det is None:
                os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
                import cv2
                self.cv2 = cv2
                self.det = cv2.FaceDetectorYN.create(self.modelle[0], "", (320, 320), 0.5, 0.3, 5000)
                self.rec = cv2.FaceRecognizerSF.create(self.modelle[1], "")
            cv2 = self.cv2
            with Image.open(pfad) as img:
                img.load()
                bild = _rgb(ImageOps.exif_transpose(img))
            W, H = bild.size
            cx, cy = x * W, y * H
            for anteil in (0.12, 0.35, 1.0):
                seite = max(48, round(min(W, H) * anteil))
                x0 = int(min(max(cx - seite / 2, 0), max(W - seite, 0)))
                y0 = int(min(max(cy - seite / 2, 0), max(H - seite, 0)))
                stueck = bild.crop((x0, y0, min(W, x0 + seite), min(H, y0 + seite)))
                f = 640 / max(stueck.size)
                klein = stueck.resize((max(1, round(stueck.width * f)), max(1, round(stueck.height * f))),
                                      Image.Resampling.LANCZOS)
                a = cv2.cvtColor(np.asarray(klein), cv2.COLOR_RGB2BGR)
                self.det.setInputSize((a.shape[1], a.shape[0]))
                _, treffer = self.det.detect(a)
                bester = None
                for t in (treffer if treffer is not None else []):
                    fx, fy, fw, fh = x0 + t[0] / f, y0 + t[1] / f, t[2] / f, t[3] / f
                    if (fx - 0.15 * fw <= cx <= fx + 1.15 * fw and fy - 0.15 * fh <= cy <= fy + 1.15 * fh
                            and (bester is None or t[14] > bester[14])):
                        bester = t
                if bester is None:
                    continue
                g = bester.copy()
                g[:14] /= f  # Koordinaten im Ausschnitt, volle Auflösung
                merkmal = self.rec.feature(self.rec.alignCrop(cv2.cvtColor(np.asarray(stueck), cv2.COLOR_RGB2BGR), g))
                merkmal = merkmal.astype(np.float32).flatten()
                norm = float(np.linalg.norm(merkmal))
                fx, fy, fw, fh = x0 + float(g[0]), y0 + float(g[1]), float(g[2]), float(g[3])
                return {"kasten": (max(fx, 0) / W, max(fy, 0) / H, fw / W, fh / H), "score": float(bester[14]),
                        "pixel": round(min(fw, fh)), "emb": (merkmal / norm).tobytes() if norm > 0 else None,
                        "groesse": (W, H)}
            return {"kasten": None, "groesse": (W, H)}


class Indexer(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.index = app.index
        self.status = {"phase": "Start", "fertig": 0, "gesamt": 0, "meldungen": []}
        self.gesichter_aktiv = False
        self.modelle = (None, None)
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

    def _verarbeiten(self, todo):
        ctx = mp.get_context("spawn")
        args = (*self.modelle, self.app.erkenn_px, self.app.min_gesicht, self.app.vorschau.ordner,
                self.app.gesicht_score, self.app.gegenprobe)
        rest, verdacht = list(todo), []
        while rest and not self._stopp:
            fertig, puffer = set(), []
            self._ex = ProcessPoolExecutor(min(self.app.index_jobs, len(rest)), mp_context=ctx,
                                           initializer=_iw_init, initargs=args)
            try:
                futures = [self._ex.submit(_iw_job, a) for a in rest]
                for f in as_completed(futures):
                    r = f.result()
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
        for a in verdacht:
            if self._stopp:
                return
            with ProcessPoolExecutor(1, mp_context=ctx, initializer=_iw_init, initargs=args) as einzel:
                try:
                    r = einzel.submit(_iw_job, a).result()
                except BrokenProcessPool:
                    r = {"rel": a[0], "groesse": a[2], "mtime": a[3], "breite": None, "hoehe": None, "zeit": None,
                         "gps": None, "kamera": None, "gesichter": [], "fehler": "Absturz beim Lesen"}
            self._schreiben([r])
            self.status["fertig"] += 1


# ---------------------------------------------------------------- Suche
def suche_ausfuehren(app, text):
    """Begriffe mit Komma trennen. Gleiche Art = ODER (2022, 2023; Leipzig, Dresden),
    verschiedene Arten = UND (2023, Juli, Leipzig), Personen immer UND (Anna, Ben = beide drauf)."""
    jahre, monate, jahr_monat, ordner, orte, personen, texte, erklaerung = set(), set(), set(), set(), [], [], [], []
    namen, anzeige_name, sonder = {}, {}, set()
    if app.index:
        for pid, name in app.index.q("SELECT id, name FROM person"):
            if name:
                namen.setdefault(name.casefold(), set()).add(pid)
                anzeige_name[name.casefold()] = name

    def deuten(t, nur_pruefen=False):
        k = re.sub(r"\s+", " ", t.casefold())
        if k in ("ohne jahr", "kein jahr", "jahr fehlt"):
            if not nur_pruefen:
                sonder.add("ohne_jahr")
                erklaerung.append("ohne Jahr")
            return True
        if k in ("jahr korrigiert", "jahr manuell", "jahr von hand"):
            if not nur_pruefen:
                sonder.add("korrigiert")
                erklaerung.append("Jahr von Hand gesetzt")
            return True
        m = re.fullmatch(r"((?:19|20)\d\d)-(\d{1,2})", k)
        if re.fullmatch(r"(19|20)\d\d", k):
            if not nur_pruefen:
                jahre.add(int(k))
                erklaerung.append(f"Jahr {k}")
            return True
        if m and 1 <= int(m.group(2)) <= 12:
            if not nur_pruefen:
                jahr_monat.add((int(m.group(1)), int(m.group(2))))
                erklaerung.append(f"{MONATE[int(m.group(2))]} {m.group(1)}")
            return True
        if k in MONAT_NR:
            if not nur_pruefen:
                monate.add(MONAT_NR[k])
                erklaerung.append(f"Monat {MONATE[MONAT_NR[k]]}")
            return True
        if re.fullmatch(r"\d{4}", k):
            if not nur_pruefen:
                ordner.add(k)
                erklaerung.append(f"Ordner {k}")
            return True
        m = re.fullmatch(r"person\s*(\d+)", k)
        if k in namen or m:
            if not nur_pruefen:
                personen.append((namen.get(k) or {int(m.group(1))}, t))
                erklaerung.append(f"Person {anzeige_name[k]}" if k in namen else f"Person {m.group(1)}")
            return True
        if app.indexer and app.indexer.orte.bereit:
            ort = app.indexer.orte.suchen(t)
            if ort:
                if not nur_pruefen:
                    orte.append(ort)
                    erklaerung.append(f"bei {t[:1].upper() + t[1:]} (bis {app.naehe_km:g} km)")
                return True
        if app.index and app.index.einer("SELECT 1 FROM bild WHERE ort = ? COLLATE NOCASE LIMIT 1", (t,)):
            if not nur_pruefen:
                orte.append({"name": t, "lat": None, "lon": None})
                erklaerung.append(f"Ort {t}")
            return True
        return False

    for term in (t.strip() for t in re.split(r"[,;]", text)):
        if not term:
            continue
        if deuten(term):
            continue
        teile = term.split()
        if len(teile) > 1 and all(deuten(t, nur_pruefen=True) for t in teile):
            for t in teile:
                deuten(t)
            continue
        texte.append(term.casefold())
        erklaerung.append(f"Dateiname enthält „{term}“")

    if not app.index:
        return [], erklaerung
    # bild_eff: von Hand gesetztes Jahr vor EXIF/Dateiname; der Monat gilt dann als unbekannt
    sql, args = ["SELECT ordner, datei, zeit, ort, ort_km, lat, lon FROM bild_eff WHERE 1=1"], []
    if jahre:  # gleiche Art ODER, verschiedene Arten UND: „2023, Juli“ = Juli 2023
        sql.append(f"AND jahr_eff IN ({','.join('?' * len(jahre))})")
        args += sorted(jahre)
    if monate:
        sql.append(f"AND monat_eff IN ({','.join('?' * len(monate))})")
        args += sorted(monate)
    if "ohne_jahr" in sonder:
        sql.append("AND jahr_eff IS NULL")
    if "korrigiert" in sonder:
        sql.append("AND jahr_man IS NOT NULL")
    if jahr_monat:
        sql.append("AND (" + " OR ".join("(jahr_eff=? AND monat_eff=?)" for _ in jahr_monat) + ")")
        for j, m in sorted(jahr_monat):
            args += [j, m]
    if ordner:
        sql.append(f"AND ordner IN ({','.join('?' * len(ordner))})")
        args += sorted(ordner)
    for ids, _ in personen:
        sql.append(f"AND pfad IN (SELECT pfad FROM gesicht WHERE person IN ({','.join('?' * len(ids))}))")
        args += sorted(ids)
    sql.append("ORDER BY sortzeit IS NULL, sortzeit, ordner, datei")
    zeilen = app.index.q(" ".join(sql), args)
    if orte:
        def nahe(z):
            for o in orte:
                if o["lat"] is None:
                    if (z[3] or "").casefold() == o["name"].casefold():
                        return True
                elif z[5] is not None and km_zwischen(z[5], z[6], o["lat"], o["lon"]) <= app.naehe_km:
                    return True
            return False
        zeilen = [z for z in zeilen if nahe(z)]
    for t in texte:
        zeilen = [z for z in zeilen if t in name_aus_id(z[1]).casefold()]
    return zeilen, erklaerung


# ---------------------------------------------------------------- Oberfläche
CSS = """
:root{
  --umfeld:#333;--flaeche:#3b3b3b;--linie:#4f4f4f;--text:#ececec;--leise:#a9a9a9;
  --stift:#f2c14e;--fehler:#e8735a;--lupe:#2a2a2a;
  --zahl:"Ubuntu Condensed","DejaVu Sans Condensed","Roboto Condensed","Arial Narrow",sans-serif;
  --schrift:system-ui,Ubuntu,"Noto Sans","DejaVu Sans",sans-serif;
  color-scheme:dark;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;background:var(--umfeld);color:var(--text);font:15px/1.45 var(--schrift)}
a{color:inherit}
:focus-visible{outline:2px solid var(--stift);outline-offset:2px}
button,input{font:inherit;color:inherit}
.kopf{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px 22px;padding:18px 16px 14px;border-bottom:1px solid var(--linie)}
.archiv{font-family:var(--zahl);font-weight:700;font-size:26px;text-decoration:none;letter-spacing:.01em}
.stand,.status{color:var(--leise);margin:0}
.status{font-size:13px;width:100%}
.status:empty{display:none}
.navi{display:flex;gap:2px;flex-wrap:wrap}
.navi a,.knopf{display:inline-block;padding:6px 12px;border:1px solid var(--linie);background:none;
  text-decoration:none;cursor:pointer;border-radius:2px}
.navi a[aria-current]{background:var(--text);color:var(--umfeld);border-color:var(--text)}
.knopf:hover,.navi a:hover{border-color:var(--leise)}
.knopf[disabled]{opacity:.45;cursor:default}
.suche{display:flex;gap:6px;flex:1 1 22em;max-width:36em}
.suche input,.springen input,.pname{padding:6px 9px;background:var(--flaeche);border:1px solid var(--linie);border-radius:2px}
.suche input{flex:1;min-width:0}
.springen{display:flex;gap:6px}
.springen input{width:6.5em;font-family:var(--zahl);font-variant-numeric:tabular-nums}
.rechts{margin-left:auto}
.raster{display:grid;gap:18px 14px;padding:18px 16px 28px;grid-template-columns:repeat(auto-fill,minmax(168px,1fr))}
.kachel{text-decoration:none;display:block}
.kachel .bild{aspect-ratio:1;background:var(--flaeche);overflow:hidden}
.kachel img{width:100%;height:100%;object-fit:cover;display:block}
.kachel .zeile{display:flex;align-items:baseline;gap:8px;padding-top:6px}
.nr{font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:.02em}
.kachel .nr{font-size:20px}
.leise{color:var(--leise);font-size:13px}
.kachel .wann{display:block;min-height:1.2em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kachel:not(.gewaehlt) .bild{opacity:.82}
.kachel:hover .bild{opacity:1}
.striche{width:30px;height:16px;margin-left:auto;stroke:var(--stift);stroke-width:2.6;stroke-linecap:round;fill:none}
.seiten{display:flex;flex-wrap:wrap;gap:4px;padding:0 16px 32px}
.seiten a,.seiten span{min-width:2.4em;text-align:center;padding:4px 8px;border:1px solid var(--linie);
  text-decoration:none;font-family:var(--zahl);font-variant-numeric:tabular-nums}
.seiten span[aria-current]{background:var(--text);color:var(--umfeld);border-color:var(--text)}
.leer{padding:40px 16px;color:var(--leise);max-width:60ch}
.filter{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:14px 16px 0}
.filter .chip{border:1px solid var(--linie);padding:3px 10px;border-radius:999px;font-size:13px}
/* Kontaktbogen */
.titel{display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap}
.titel h1{margin:0;font-family:var(--zahl);font-weight:700;font-size:64px;line-height:.9;font-variant-numeric:tabular-nums;letter-spacing:.02em}
.titel p{margin:0}
.ziel{color:var(--stift)}
.weg{display:flex;gap:6px;flex-wrap:wrap}
.bogen{display:grid;gap:22px 16px;padding:22px 16px 40px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.feld{margin:0}
.zelle{position:relative}
.feld .rahmen{aspect-ratio:1;background:var(--flaeche);padding:10px;display:block;width:100%;border:0;cursor:zoom-in}
.feld .rahmen img{width:100%;height:100%;object-fit:contain;display:block}
.fettstift{position:absolute;left:-7px;top:-7px;width:calc(100% + 14px);height:calc(100% + 14px);pointer-events:none;
  fill:none;stroke:var(--stift);stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round;
  stroke-dasharray:100;stroke-dashoffset:100;transition:stroke-dashoffset .38s ease-out;overflow:visible}
.gewaehlt .fettstift{stroke-dashoffset:0}
.buchstabe{position:absolute;left:-10px;top:-20px;font-family:var(--zahl);font-weight:700;font-style:italic;
  font-size:34px;line-height:1;color:var(--stift);transform:rotate(-9deg);text-shadow:0 0 4px rgba(0,0,0,.55);pointer-events:none}
.ordnernr{position:absolute;right:8px;top:8px;font-family:var(--zahl);font-weight:700;font-size:15px;
  background:rgba(40,40,40,.82);padding:1px 6px;border-radius:2px;text-decoration:none}
.feld figcaption{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;padding-top:8px}
.lfd{font-family:var(--zahl);font-weight:700;color:var(--leise);font-variant-numeric:tabular-nums;min-width:1.6em}
.dateiname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;font-size:13px;color:var(--leise)}
.gewaehlt .dateiname{color:var(--text)}
.waehlen{flex:none}
.gewaehlt .waehlen{border-color:var(--stift);color:var(--stift)}
.feld.voll .waehlen{opacity:.45}
.technik{width:100%;font-size:12px;color:var(--leise);font-variant-numeric:tabular-nums;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.technik.spitze{color:var(--stift)}
.meta{width:100%;font-size:13px;color:var(--leise);display:flex;align-items:center;gap:7px;min-height:1.2em}
.mtext{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.meta b{font-weight:600;color:var(--text)}
.jahr{width:4.3em;flex:none;padding:0 5px;text-align:center;font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;
  background:none;border:1px solid var(--linie);border-radius:999px;color:var(--text)}
.jahr:hover{border-color:var(--leise)}
.jahr:placeholder-shown{border-style:dashed;font-weight:400}
.jahr::placeholder{color:var(--leise)}
.jahr.manuell{border-color:var(--stift);color:var(--stift)}
.ordnerjahr{display:flex;gap:6px;align-items:center}
.ordnerjahr .jahr{font-size:15px;padding:5px 6px;width:4.8em}
.hilfe{padding:0 16px 32px;color:var(--leise);font-size:13px}
kbd{font-family:var(--zahl);border:1px solid var(--linie);padding:0 5px;border-radius:2px}
/* Lupe */
.lupe{position:fixed;inset:0;background:var(--lupe);display:grid;grid-template-rows:1fr auto;z-index:10}
.lupe[hidden]{display:none}
.lupe .flaeche{display:flex;align-items:center;justify-content:center;min-height:0;padding:12px;position:relative;overflow:hidden}
.lupe img{max-width:100%;max-height:100%;object-fit:contain}
.lupe.gewaehlt .flaeche img{outline:5px solid var(--stift);outline-offset:6px}
.kasten{position:absolute;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.6);pointer-events:none}
.kasten button{position:absolute;left:-2px;top:100%;margin-top:3px;white-space:nowrap;font-size:13px;background:#fff;color:#222;
  padding:0 6px;border:0;border-radius:2px;cursor:pointer;pointer-events:auto}
.kasten button:hover{background:var(--stift)}
.kasten.aktiv{border-color:var(--stift)}.kasten.aktiv button{background:var(--stift)}
.ghinweis{position:absolute;left:50%;top:10px;transform:translateX(-50%);margin:0;padding:4px 10px;max-width:92%;
  font-size:13px;text-align:center;background:rgba(30,30,30,.86);border-radius:2px;z-index:2;pointer-events:none}
.gesichter-an .flaeche img{cursor:crosshair}
.nennbox{position:absolute;left:50%;bottom:14px;transform:translateX(-50%);z-index:3;width:min(92vw,27em);
  display:grid;gap:10px;padding:12px 14px;background:var(--flaeche);border:1px solid var(--linie);border-radius:3px;
  box-shadow:0 8px 28px rgba(0,0,0,.5)}
.nennbox.oben{top:14px;bottom:auto}
.nennbox label{display:grid;gap:4px;font-size:13px;color:var(--leise)}
.nennbox input{padding:6px 9px;font-size:17px;background:var(--umfeld);border:1px solid var(--linie);border-radius:2px}
.nknoepfe{display:flex;flex-wrap:wrap;gap:6px}
.nknoepfe .haupt{border-color:var(--stift);color:var(--stift)}
.nfuss{display:flex;justify-content:space-between;gap:10px}
.link{background:none;border:0;padding:0;color:var(--leise);text-decoration:underline;cursor:pointer;font-size:13px}
.link:hover{color:var(--text)}
.lupe .leiste{display:flex;align-items:center;gap:10px;padding:10px 16px 14px;flex-wrap:wrap;border-top:1px solid var(--linie)}
.lupe .wo{font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;font-size:18px}
.lupe .jahr{font-size:17px;width:4.6em;padding:3px 6px}
.lupe .text{flex:1;min-width:12em;display:flex;flex-direction:column;overflow:hidden}
.lupe .wer,.lupe .info{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lupe .wer{color:var(--leise)}
.lupe .info{font-size:13px}
.lupe.gewaehlt .waehlen{border-color:var(--stift);color:var(--stift)}
.gesichter-an .knopf.gz{border-color:var(--text)}
.meldung{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--text);color:var(--umfeld);
  padding:9px 14px;border-radius:2px;max-width:min(92vw,60ch);z-index:20}
.meldung.fehler{background:var(--fehler);color:#1f1f1f}
.meldung[hidden]{display:none}
.lupe:not([hidden]) ~ .meldung{bottom:96px}
/* Personen */
.personen{padding:10px 16px 40px;display:grid;gap:26px}
.person{border-top:1px solid var(--linie);padding-top:14px}
.pkopf{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:10px}
.pname{font-family:var(--zahl);font-weight:700;font-size:20px;width:13em}
.pname:placeholder-shown{color:var(--leise)}
.gesichter{display:flex;flex-wrap:wrap;gap:8px}
.gesicht{position:relative;margin:0;width:88px}
.gesicht img{width:88px;height:88px;object-fit:cover;display:block;background:var(--flaeche)}
.gesicht a{display:block}
.gesicht button{position:absolute;top:2px;width:24px;height:24px;padding:0;border:0;border-radius:2px;
  background:rgba(40,40,40,.85);cursor:pointer;line-height:24px}
.gesicht .weg{right:2px}.gesicht .nennen{left:2px}
.gesicht .weg:hover{background:var(--fehler);color:#1f1f1f}.gesicht .nennen:hover{background:var(--stift);color:#1f1f1f}
.gruppe{margin-top:10px}
.gruppe .gkopf{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:13px;color:var(--leise)}
.hinweis{font-size:13px;color:var(--stift)}
.import{padding:6px 16px 40px;display:grid;gap:22px;max-width:1100px}
.import h2{font-size:17px;margin:0 0 10px}
.import section{border-top:1px solid var(--linie);padding-top:14px}
.pfadzeile{display:flex;gap:6px}.pfadzeile .pname{flex:1;font-size:15px;width:auto;min-width:0}
.krumen{display:flex;flex-wrap:wrap;gap:2px;margin:10px 0 6px}
.krume{background:none;border:0;color:var(--leise);cursor:pointer;padding:2px 4px;font-size:13px}
.krume:hover{color:var(--text)}.krume:not(:last-child):not(:first-child)::after{content:" /";color:var(--linie)}
.schnell{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}.knopf.klein{font-size:13px;padding:3px 9px}
.ordnerliste{list-style:none;margin:0;padding:0;max-height:46vh;overflow:auto;border:1px solid var(--linie)}
.ordnerliste li{border-bottom:1px solid var(--flaeche)}.ordnerliste li.leise{padding:8px 10px}
.ordnerknopf{display:block;width:100%;text-align:left;background:none;border:0;padding:7px 10px;cursor:pointer}
.ordnerknopf:hover{background:var(--flaeche)}
.knopfzeile{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.knopf.haupt{border-color:var(--stift);color:var(--stift)}
.hilfe0{font-size:13px;color:var(--leise);max-width:80ch}
.import progress{width:100%;height:10px;accent-color:var(--stift)}
.ergebnis{white-space:pre-line}.ergebnis.fehler{color:var(--fehler)}
.import pre{max-height:40vh;overflow:auto;font-size:12px;background:var(--lupe);padding:10px;white-space:pre-wrap}
.lernstand{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:12px 16px 0;font-size:13px;
  color:var(--leise)}
.pruefleiste{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;
  background:var(--umfeld);border-bottom:1px solid var(--linie)}
.pruefleiste .pname{font-size:15px;width:14em}
.wahl{cursor:pointer}
.wahl img{transition:opacity .12s}
.wahl.an img{outline:3px solid var(--stift);outline-offset:-3px}
.wahl .haken{position:absolute;top:3px;left:3px;width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;
  background:var(--stift);color:#1f1f1f;font-weight:700;display:none}
.wahl.an .haken{display:block}
.quelle{padding:0 16px 24px;color:var(--leise);font-size:12px}
@media (max-width:560px){
  .titel h1{font-size:48px}.raster{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .bogen{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
  .feld .waehlen{width:100%}
  .suche{flex-basis:100%;max-width:none}
}
@media (prefers-reduced-motion:reduce){.fettstift{transition:none}}
"""

FAVICON = ("data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#333"/>'
    '<path d="M6 7 L26 5 L27 25 L7 27 L5 9 L12 6" fill="none" stroke="#f2c14e" stroke-width="3.2" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>', safe=""))

JS_GEMEINSAM = """
const meldungEl=document.querySelector('.meldung');let meldungTimer;
function meldung(text,fehler){meldungEl.textContent=text;meldungEl.classList.toggle('fehler',!!fehler);
 meldungEl.hidden=false;clearTimeout(meldungTimer);meldungTimer=setTimeout(()=>meldungEl.hidden=true,fehler?6000:2600);}
async function post(url,daten){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify(daten||{})});let j={};try{j=await r.json();}catch(_){j={fehler:'Server antwortet nicht.'};}
 return [r.ok,j];}
const statusEl=document.querySelector('.status');
async function statusHolen(){try{const r=await fetch('/api/status');const j=await r.json();
 statusEl.textContent=j.text;if(j.laeuft)setTimeout(statusHolen,3000);}catch(_){}}
if(statusEl&&statusEl.dataset.laeuft==='1')setTimeout(statusHolen,2000);
"""

JS_UEBERSICHT = """
const nb=document.getElementById('neuaufbau');
if(nb)nb.addEventListener('click',async()=>{
 if(!confirm('BestOf aus den gespeicherten Auswahlen neu aufbauen? Fehlende Kopien werden ergänzt, veraltete entfernt.'))return;
 nb.disabled=true;const [ok,j]=await post('/api/neuaufbau');nb.disabled=false;
 meldung(ok?j.meldung:(j.fehler||'Neuaufbau fehlgeschlagen.'),!ok);if(ok)setTimeout(()=>location.reload(),1600);});
"""

JS_BOGEN = """
const D=JSON.parse(document.getElementById('daten').textContent);
let laeuft=false,aktiv=-1,gesichterAn=false;
const felder=[...document.querySelectorAll('.feld')],info=document.getElementById('info'),zielEl=document.getElementById('ziel');
const lupe=document.querySelector('.lupe'),lupeImg=lupe.querySelector('img'),flaeche=lupe.querySelector('.flaeche'),
 lupeWo=lupe.querySelector('.wo'),lupeWer=lupe.querySelector('.wer'),lupeInfo=lupe.querySelector('.info'),
 lupeKnopf=lupe.querySelector('.waehlen'),lupeOrig=lupe.querySelector('.orig'),lupeKarte=lupe.querySelector('.karte'),
 gzKnopf=lupe.querySelector('.gz'),lupeJahr=D.jahr?lupe.querySelector('.jahr'):null,zusammenEl=document.getElementById('zusammen');
if(!D.jahr)lupe.querySelector('.jahr').hidden=true;
const ABC='abcdefghijklmnopqrstuvwxyz';
function zeichne(){
 felder.forEach((f,i)=>{const b=D.bilder[i],l=D.auswahl[b.ordner]||[],k=l.indexOf(b.id),an=k>=0;
  f.classList.toggle('gewaehlt',an);f.classList.toggle('voll',!an&&l.length>=D.max);
  f.querySelector('.buchstabe').textContent=an&&l.length>1?ABC[k]:'';
  const w=f.querySelector('.waehlen');w.textContent=an?'Abwählen':'Auswählen';w.setAttribute('aria-pressed',an);
  w.title=an?'Aus BestOf entfernen ('+(D.ziele[b.ordner]||{})[b.id]+')':'In BestOf kopieren';});
 if(D.einordner){const l=D.auswahl[D.ordner]||[];
  info.textContent=D.bilder.length+(D.bilder.length===1?' Bild, ':' Bilder, ')+l.length+' von '+D.max+' ausgewählt';
  zielEl.textContent=l.length?'BestOf: '+l.map(id=>D.ziele[D.ordner][id]).join(', '):'Noch keine Auswahl';}
 if(aktiv>=0)lupeZeichne();}
async function umschalten(i){
 if(laeuft)return;const b=D.bilder[i],l=D.auswahl[b.ordner]||[];
 if(!l.includes(b.id)&&l.length>=D.max){meldung('Schon '+D.max+' Bilder aus Ordner '+b.ordner+' ausgewählt. Wählen Sie erst eines ab.',true);return;}
 laeuft=true;const [ok,j]=await post('/api/auswahl',{ordner:b.ordner,datei:b.id});laeuft=false;
 if(!ok){meldung(j.fehler||'Auswahl fehlgeschlagen.',true);return;}
 D.auswahl[b.ordner]=j.auswahl;D.ziele[b.ordner]=j.ziele;zeichne();meldung(j.meldung);}
felder.forEach((f,i)=>{f.querySelector('.waehlen').addEventListener('click',()=>umschalten(i));
 f.querySelector('.rahmen').addEventListener('click',()=>oeffne(i));});
function vorladen(i){if(i>=0&&i<D.bilder.length){const b=new Image();b.src=D.bilder[i].g;}}
function hinweisText(b){const n=b.f.length,klick=' Ins Gesicht klicken, um es zu markieren.';
 if(b.fs==='fehler')return 'Die Datei ist nicht lesbar.';
 if(b.fs==='offen'&&!n)return 'Noch nicht nach Gesichtern durchsucht – der Index läuft.'+klick;
 return n?n+(n===1?' Gesicht.':' Gesichter.')+' Fehlt eines?'+klick:'Kein Gesicht erkannt.'+klick;}
function kaesten(){flaeche.querySelectorAll('.kasten').forEach(k=>k.remove());
 lupe.classList.toggle('gesichter-an',gesichterAn);ghinweis.hidden=!gesichterAn||aktiv<0||!nbox.hidden;
 if(aktiv>=0)ghinweis.textContent=hinweisText(D.bilder[aktiv]);
 if(!gesichterAn||aktiv<0||!lupeImg.complete)return;
 const r=lupeImg.getBoundingClientRect(),fr=flaeche.getBoundingClientRect();
 for(const g of D.bilder[aktiv].f){const [x,y,w,h]=g;const k=document.createElement('div');
  k.className='kasten'+(g===nGesicht?' aktiv':'');
  k.style.left=(r.left-fr.left+x*r.width)+'px';k.style.top=(r.top-fr.top+y*r.height)+'px';
  k.style.width=(w*r.width)+'px';k.style.height=(h*r.height)+'px';
  const a=document.createElement('button');a.type='button';a.textContent=g[5];a.title='Wer ist das? Namen ändern';
  a.addEventListener('click',()=>gesichtBenennen(g));k.appendChild(a);flaeche.appendChild(k);}}
const nbox=lupe.querySelector('.nennbox'),nname=nbox.querySelector('.nname'),nhaupt=nbox.querySelector('.haupt'),
 nneben=nbox.querySelector('.neben'),nkein=nbox.querySelector('.kein'),namenListe=document.getElementById('namenliste'),
 ghinweis=lupe.querySelector('.ghinweis');let nGesicht=null,sucht=false;
(D.namen||[]).forEach(namenErgaenzen);
function namenErgaenzen(n){if(!n||[...namenListe.options].some(o=>o.value===n))return;
 const o=document.createElement('option');o.value=n;namenListe.appendChild(o);}
function nennenZu(){if(nbox.hidden)return;nbox.hidden=true;nGesicht=null;kaesten();}
function gesichtBenennen(g){nGesicht=g;nkein.hidden=!!g.neu;
 if(g.neu){nname.value='';nhaupt.textContent='Stelle markieren';nhaupt.dataset.art='neu';nneben.hidden=true;
  nbox.classList.toggle('oben',g.y>0.55);nbox.hidden=false;kaesten();nname.focus();return;}
 const unbenannt=g[5].startsWith('Person '),n=g[7]||1;
 nname.value=unbenannt?'':g[5];
 const gruppe=n>1?'Alle '+n+' Gesichter '+(unbenannt?'dieser Gruppe':'von '+g[5]):'',einzeln=n>1?'Nur dieses Gesicht':'Speichern';
 const gruppeZuerst=unbenannt&&n>1;  // „Person N“ benennen = ganze Gruppe; benannte Gruppe = Korrektur dieses Gesichts
 nhaupt.textContent=gruppeZuerst?gruppe:einzeln;nhaupt.dataset.art=gruppeZuerst?'gruppe':'einzeln';
 nneben.hidden=!gruppe;nneben.textContent=gruppeZuerst?einzeln:gruppe;nneben.dataset.art=gruppeZuerst?'einzeln':'gruppe';
 nbox.classList.toggle('oben',g[1]+g[3]/2>0.55);  // Gesicht unten im Bild: Feld oben zeigen
 nbox.hidden=false;kaesten();nname.focus();nname.select();}
async function gesichterHolen(i){if(!D.gesichter||i<0)return;const b=D.bilder[i];
 try{const r=await fetch('/api/gesichter?pfad='+encodeURIComponent(b.ordner+'/'+b.id));if(!r.ok)return;const j=await r.json();
  if(!nbox.hidden&&aktiv===i)return;  // während des Benennens nichts austauschen
  b.f=j.f;b.fs=j.fs;feldMeta(i);if(aktiv===i)lupeZeichne();}catch(_){}}
function gesichterAendern(passt,tun){D.bilder.forEach((b,i)=>{let neu=false;
 b.f.forEach(f=>{if(passt(f)){tun(f);neu=true;}});if(neu)feldMeta(i);});}
async function nennenAusfuehren(art){const g=nGesicht;if(!g||aktiv<0)return;const name=nname.value.trim(),i=aktiv,b=D.bilder[i];
 if(art!=='weg'&&!name){meldung('Bitte einen Namen eingeben.',true);nname.focus();return;}
 if(art==='neu'){nbox.hidden=true;nGesicht=null;kaesten();gesichtSuchen(g.x,g.y,name);return;}
 const ziel={id:g[6],pfad:b.ordner+'/'+b.id,kasten:g.slice(0,4)};  // Lage hilft, falls die ID veraltet ist
 const [ok,j]=await post(art==='gruppe'?'/api/person':'/api/gesicht',
  art==='gruppe'?{ids:[g[4]],name}:art==='weg'?ziel:Object.assign({name},ziel));
 if(!ok){if(j.veraltet){nbox.hidden=true;nGesicht=null;gesichterHolen(i);}meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}
 if(j.id)g[6]=j.id;
 if(art==='gruppe')gesichterAendern(f=>f[4]===g[4],f=>{f[5]=j.name;});
 else if(art==='weg')D.bilder.forEach((b,i)=>{const n=b.f.length;b.f=b.f.filter(f=>f[6]!==g[6]);if(b.f.length!==n)feldMeta(i);});
 else{const neu=new Map((j.bewegt||[]).map(x=>[x[0],x]));gesichterAendern(f=>neu.has(f[6]),f=>{const x=neu.get(f[6]);f[4]=x[1];f[5]=x[2];});}
 if(j.anzahl)gesichterAendern(f=>j.anzahl[f[4]]!==undefined,f=>{f[7]=j.anzahl[f[4]];});
 namenErgaenzen(j.name);nbox.hidden=true;nGesicht=null;if(aktiv>=0)lupeZeichne();meldung(j.meldung);gesichterHolen(i);}
nhaupt.addEventListener('click',()=>nennenAusfuehren(nhaupt.dataset.art));
nneben.addEventListener('click',()=>nennenAusfuehren(nneben.dataset.art));
nkein.addEventListener('click',()=>nennenAusfuehren('weg'));
lupeImg.addEventListener('click',ev=>{if(!gesichterAn||aktiv<0)return;if(!nbox.hidden){nennenZu();return;}
 const r=lupeImg.getBoundingClientRect(),x=(ev.clientX-r.left)/r.width,y=(ev.clientY-r.top)/r.height;
 if(x>=0&&x<=1&&y>=0&&y<=1)gesichtSuchen(x,y);});
async function gesichtSuchen(x,y,name){if(sucht)return;const i=aktiv,b=D.bilder[i];sucht=true;
 if(!name)meldung('Suche Gesicht …');
 const [ok,j]=await post('/api/gesicht_neu',name?{ordner:b.ordner,datei:b.id,x,y,name,erzwingen:true}:{ordner:b.ordner,datei:b.id,x,y});
 sucht=false;
 if(!ok){if(j.markieren&&aktiv===i){meldung(j.fehler+' Mit einem Namen markieren Sie die Stelle trotzdem.',true);
   gesichtBenennen({neu:true,x,y});}else meldung(j.fehler||'Suche fehlgeschlagen.',true);return;}
 let g=b.f.find(f=>f[6]===j.gesicht[6]);if(!g){g=j.gesicht;b.f.push(g);feldMeta(i);}
 namenErgaenzen(j.name);meldung(j.meldung);if(aktiv===i){lupeZeichne();if(!name)gesichtBenennen(g);}}
nbox.querySelector('.abbr').addEventListener('click',nennenZu);
nname.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();nennenAusfuehren(nhaupt.dataset.art);}
 else if(ev.key==='Escape'){ev.preventDefault();nennenZu();}});
function namenVon(b,alle){return [...new Set(b.f.map(g=>g[5]).filter(n=>alle||!n.startsWith('Person ')))]
 .sort((a,c)=>a.localeCompare(c,'de'));}
function jahrTitel(b){return b.jm?'Jahr von Hand gesetzt'+(b.z?' (Datei: '+b.z+')':' (Datei ohne Datum)')+
 '. Feld leeren und Enter = wieder Jahr aus der Datei.':b.j?'Jahr aus der Datei (EXIF oder Dateiname). Korrigieren: Jahr eintippen, Enter.':
 'Kein Datum in der Datei. Jahr eintippen, Enter.';}
function jahrFeld(inp,b){if(!inp)return;inp.value=b.j||'';inp.dataset.alt=inp.value;inp.classList.toggle('manuell',!!b.jm);
 inp.title=jahrTitel(b);}
function feldMeta(i){const b=D.bilder[i],n=namenVon(b,false),f=felder[i],m=f.querySelector('.mtext');
 jahrFeld(f.querySelector('.jahr'),b);m.textContent=[b.jm?'':b.zm,b.ok].filter(Boolean).join(', ');
 if(n.length){if(m.textContent)m.append(' – ');const s=document.createElement('b');s.textContent=n.join(', ');m.append(s);}}
function jahreUebernehmen(j){D.bilder.forEach((b,i)=>{const n=j.jahre[b.ordner+'/'+b.id];if(n){b.j=n[0];b.jm=n[1];feldMeta(i);}});
 if(zusammenEl&&j.zusammen!==undefined)zusammenEl.textContent=j.zusammen;if(aktiv>=0)lupeZeichne();}
async function jahrAendern(inp,i){const b=D.bilder[i],wert=inp.value.trim();if(wert===inp.dataset.alt)return;
 if(wert&&!/^[0-9]{4}$/.test(wert)){meldung('Bitte das Jahr mit vier Ziffern eingeben, z. B. 1994.',true);inp.value=inp.dataset.alt;return;}
 const [ok,j]=await post('/api/jahr',{pfade:[b.ordner+'/'+b.id],jahr:wert});
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);inp.value=inp.dataset.alt;return;}
 jahreUebernehmen(j);meldung(j.meldung);}
function jahrTasten(inp){inp.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}
 else if(ev.key==='Escape'){ev.preventDefault();inp.value=inp.dataset.alt||'';inp.blur();}});}
function lupeZeichne(){const b=D.bilder[aktiv],l=D.auswahl[b.ordner]||[],an=l.includes(b.id);
 lupe.classList.toggle('gewaehlt',an);lupeWo.textContent=(aktiv+1)+' / '+D.bilder.length;
 lupeWer.textContent=(D.einordner?'':'Ordner '+b.ordner+', ')+b.name+' · '+b.t+(an?' – BestOf '+D.ziele[b.ordner][b.id]:'');
 lupeInfo.textContent=[b.jm?'':b.z,b.ol,namenVon(b,true).join(', ')].filter(Boolean).join(', ');
 if(lupeJahr&&document.activeElement!==lupeJahr)jahrFeld(lupeJahr,b);lupeKarte.hidden=!b.k;if(b.k)lupeKarte.href=b.k;
 gzKnopf.hidden=!D.gesichter;gzKnopf.textContent='Gesichter'+(b.f.length?' ('+b.f.length+')':'');
 lupeKnopf.textContent=an?'Abwählen':'Auswählen';lupeKnopf.setAttribute('aria-pressed',an);kaesten();}
function oeffne(i){nbox.hidden=true;nGesicht=null;aktiv=(i+D.bilder.length)%D.bilder.length;const b=D.bilder[aktiv];
 lupeImg.src=b.g;lupeImg.alt=b.name;lupeOrig.href=b.o;lupe.hidden=false;lupeZeichne();if(gesichterAn)gesichterHolen(aktiv);
 vorladen(aktiv+1);vorladen(aktiv-1);lupe.querySelector('.zu').focus({preventScroll:true});}
function schliesse(){if(aktiv<0)return;nbox.hidden=true;nGesicht=null;const f=felder[aktiv];aktiv=-1;lupe.hidden=true;
 lupeImg.removeAttribute('src');
 kaesten();f.querySelector('.rahmen').focus({preventScroll:true});f.scrollIntoView({block:'nearest'});}
lupeImg.addEventListener('load',kaesten);window.addEventListener('resize',kaesten);
lupe.querySelector('.zurueck').addEventListener('click',()=>oeffne(aktiv-1));
lupe.querySelector('.vor').addEventListener('click',()=>oeffne(aktiv+1));
lupe.querySelector('.zu').addEventListener('click',schliesse);
gzKnopf.addEventListener('click',()=>{gesichterAn=!gesichterAn;if(!gesichterAn)nbox.hidden=true;else gesichterHolen(aktiv);kaesten();});
lupeKnopf.addEventListener('click',()=>umschalten(aktiv));
let wischX=null;lupe.addEventListener('touchstart',ev=>{wischX=ev.touches[0].clientX;},{passive:true});
lupe.addEventListener('touchend',ev=>{if(wischX===null)return;const dx=ev.changedTouches[0].clientX-wischX;wischX=null;
 if(Math.abs(dx)>60)oeffne(aktiv+(dx<0?1:-1));});
document.addEventListener('keydown',ev=>{
 if(ev.altKey||ev.ctrlKey||ev.metaKey||ev.target.matches('input'))return;
 if(aktiv>=0){
  if(!nbox.hidden&&ev.key==='Escape'){nennenZu();ev.preventDefault();}
  else if(ev.key==='ArrowRight'){oeffne(aktiv+1);ev.preventDefault();}
  else if(ev.key==='ArrowLeft'){oeffne(aktiv-1);ev.preventDefault();}
  else if(ev.key===' '||ev.key==='b'){umschalten(aktiv);ev.preventDefault();}
  else if(ev.key==='g'||ev.key==='G'){gesichterAn=!gesichterAn;if(!gesichterAn)nbox.hidden=true;else gesichterHolen(aktiv);kaesten();}
  else if((ev.key==='j'||ev.key==='J')&&lupeJahr){lupeJahr.focus();lupeJahr.select();ev.preventDefault();}
  else if(ev.key==='Escape'){schliesse();}
 }else if(D.einordner){
  if(ev.key==='ArrowRight'&&D.weiter)location.href=D.weiter;
  else if(ev.key==='ArrowLeft'&&D.zurueck)location.href=D.zurueck;
  else if(ev.key==='n'||ev.key==='N')location.href=D.offen;
  else if(ev.key==='Escape')location.href=D.uebersicht;
 }});
felder.forEach((f,i)=>{const inp=f.querySelector('.jahr');feldMeta(i);if(!inp)return;
 jahrTasten(inp);inp.addEventListener('change',()=>jahrAendern(inp,i));});
if(lupeJahr){jahrTasten(lupeJahr);lupeJahr.addEventListener('change',()=>{if(aktiv>=0)jahrAendern(lupeJahr,aktiv);});}
const oj=document.getElementById('ordnerjahr');
if(oj)oj.addEventListener('submit',async ev=>{ev.preventDefault();const inp=oj.querySelector('.jahr'),wert=inp.value.trim();
 if(wert&&!/^[0-9]{4}$/.test(wert)){meldung('Bitte das Jahr mit vier Ziffern eingeben, z. B. 1994.',true);return;}
 if(!wert&&!confirm('Alle von Hand gesetzten Jahre in diesem Ordner entfernen? Dann gilt wieder das Jahr aus den Dateien.'))return;
 const [ok,j]=await post('/api/jahr',{ordner:D.ordner,jahr:wert});
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}inp.value='';jahreUebernehmen(j);meldung(j.meldung);});
zeichne();
"""

JS_PRUEFEN = """
const wahl=new Set(),zahl=document.getElementById('zahl'),wahlEls=[...document.querySelectorAll('.wahl')];let letzte=-1;
function zeigen(){zahl.textContent=wahl.size?wahl.size+' ausgewählt':'Gesichter anklicken (Umschalt = Bereich)';
 document.querySelectorAll('.aktion').forEach(b=>b.disabled=!wahl.size);}
function setzen(f,an){const id=+f.dataset.id;if(an)wahl.add(id);else wahl.delete(id);f.classList.toggle('an',an);}
wahlEls.forEach((f,i)=>f.addEventListener('click',ev=>{const an=!wahl.has(+f.dataset.id);
 if(ev.shiftKey&&letzte>=0){const [a,b]=[Math.min(letzte,i),Math.max(letzte,i)];for(let k=a;k<=b;k++)setzen(wahlEls[k],an);}
 else setzen(f,an);letzte=i;zeigen();}));
document.getElementById('alle').addEventListener('click',()=>{wahlEls.forEach(f=>setzen(f,true));zeigen();});
document.getElementById('keine').addEventListener('click',()=>{wahlEls.forEach(f=>setzen(f,false));zeigen();});
async function ausfuehren(daten){document.querySelectorAll('.aktion').forEach(b=>b.disabled=true);
 const [ok,j]=await post('/api/gesichter_nennen',Object.assign({ids:[...wahl]},daten));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);zeigen();return;}meldung(j.meldung);setTimeout(()=>location.reload(),1200);}
document.getElementById('nennen').addEventListener('click',()=>{const n=document.getElementById('wname').value.trim();
 if(!n){meldung('Bitte einen Namen eingeben.',true);return;}ausfuehren({name:n});});
document.getElementById('wname').addEventListener('keydown',ev=>{if(ev.key==='Enter'&&wahl.size){ev.preventDefault();
 document.getElementById('nennen').click();}});
document.getElementById('bestaetigen').addEventListener('click',()=>ausfuehren({bestaetigen:true}));
document.getElementById('entfernen').addEventListener('click',()=>{
 if(confirm(wahl.size+' Gesichter entfernen? Sie werden keiner Person mehr zugeordnet.'))ausfuehren({});});
zeigen();
"""

JS_PERSONEN = """
const lk=document.getElementById('lernen');
if(lk)lk.addEventListener('click',async()=>{lk.disabled=true;const [ok,j]=await post('/api/lernen',{});lk.disabled=false;
 meldung(ok?j.meldung:(j.fehler||'Lernen fehlgeschlagen.'),!ok);if(ok)setTimeout(()=>location.reload(),4000);});
const ids=el=>el.dataset.ids.split(',').map(Number);
document.querySelectorAll('.pname').forEach(inp=>{
 const speichern=async()=>{if(inp.value===inp.dataset.alt)return;
  const [ok,j]=await post('/api/person',{ids:ids(inp),name:inp.value});
  if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);inp.value=inp.dataset.alt;return;}
  inp.dataset.alt=inp.value;meldung(j.meldung);if(j.neu_laden)setTimeout(()=>location.reload(),1200);};
 inp.addEventListener('change',speichern);
 inp.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}});});
document.querySelectorAll('.ignorieren').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/person',{ids:ids(k),ignorieren:k.dataset.an!=='1'});
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),800);}));
document.querySelectorAll('.loesen').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/person',{ids:[+k.dataset.id],name:''});
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),800);}));
const gesichtZiel=k=>({id:+k.dataset.id,pfad:k.dataset.pfad,kasten:k.dataset.kasten.split(',').map(Number)});
document.querySelectorAll('.gesicht .weg').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/gesicht',gesichtZiel(k));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}k.closest('.gesicht').remove();meldung(j.meldung);}));
document.querySelectorAll('.gesicht .nennen').forEach(k=>k.addEventListener('click',async()=>{
 const neu=prompt('Wer ist das? Gleicher Name = gleiche Person, auch auf Fotos aus anderen Lebensaltern.','');
 if(neu===null||!neu.trim())return;
 const [ok,j]=await post('/api/gesicht',Object.assign({name:neu.trim()},gesichtZiel(k)));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),1200);}));
"""


def json_im_html(daten):
    return json.dumps(daten, ensure_ascii=True).replace("</", "<\\/")


def stift_pfad(saat):
    """Leicht unregelmäßiger, von Hand gezogener Rahmen (Fettstift auf dem Kontaktbogen)."""
    r = random.Random(hashlib.sha1(saat.encode("utf-8", "surrogateescape")).digest())

    def j(v):
        return v + r.uniform(-1.8, 1.8)

    punkte = [(j(4), j(5)), (j(50), j(3)), (j(96), j(4.5)), (j(97.5), j(50)), (j(96), j(96)),
              (j(50), j(97.5)), (j(3.5), j(96)), (j(2.5), j(50)), (j(5), j(7)), (j(22), j(3.5))]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in punkte)


def striche_svg(n):
    if not n:
        return ""
    wege = " ".join(f"M{3 + 8 * k} 14 L{8 + 8 * k} 2" for k in range(min(n, 3)))
    return (f'<svg class="striche" viewBox="0 0 30 16" role="img" aria-label="{n} ausgewählt">'
            f'<path d="{wege}"/></svg>')


def status_text(app):
    if not app.indexer:
        return "", False
    s = app.indexer.status
    if s["phase"] == "Index" and s["gesamt"]:
        return f"Index: {s['fertig']} von {s['gesamt']} Bildern gelesen – Filter noch unvollständig.", True
    if s["phase"] not in ("fertig", "Index"):
        return f"Index: {s['phase']} …", True
    zahlen = app.index.einer("SELECT (SELECT COUNT(*) FROM bild), (SELECT COUNT(*) FROM gesicht)")
    text = f"Index: {zahlen[0]} Bilder"
    if app.indexer.gesichter_aktiv:
        text += f", {zahlen[1]} Gesichter, {len(personen_gruppen(app.index, 2, False))} Personen"
    if s["meldungen"] and ("aus" in s["meldungen"][-1]):
        text += f". {s['meldungen'][-1]}"
    return text, False


def kopf(app, aktiv="", inhalt_titel="", suchtext=""):
    text, laeuft = status_text(app)
    navi = [("ordner", "/", "Ordner")]
    if app.import_erlaubt:
        navi.append(("import", "/import", "Import"))
    if app.index:
        navi.append(("personen", "/personen", "Personen"))
    links = "".join(f'<a href="{url}"{" aria-current=page" if k == aktiv else ""}>{t}</a>' for k, url, t in navi)
    suche = ""
    if app.index:
        suche = (f'<form class="suche" action="/suche" role="search"><input name="q" value="{e(suchtext)}" '
                 f'placeholder="Filter, z. B. 2023, Leipzig, Anna" aria-label="Filter"><button class="knopf">Filtern</button></form>')
    return (f'<header class="kopf"><a class="archiv" href="/">{e(os.path.basename(app.archiv.pfad))}</a>'
            f'{inhalt_titel}<nav class="navi" aria-label="Bereiche">{links}</nav>{suche}'
            f'<p class="status" data-laeuft="{1 if laeuft else 0}">{e(text)}</p></header>')


def seite(titel, inhalt, skript=""):
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(titel)}</title><link rel="icon" href="{FAVICON}"><style>{CSS}</style></head>'
            f'<body>{inhalt}<div class="meldung" role="status" aria-live="polite" hidden></div>'
            f'<script>{JS_GEMEINSAM}{skript}</script></body></html>').encode("utf-8", "surrogateescape")


def bild_daten(app, ordner, bilder):
    """Metadaten und Gesichter aus dem Index für die Bilder eines oder mehrerer Ordner."""
    meta, gesichter = {}, {}
    if not app.index or not bilder:
        return meta, gesichter
    ordner_menge = sorted({o for o, _ in bilder})
    platz = ",".join("?" * len(ordner_menge))
    for z in app.index.q(f"SELECT pfad, zeit, ort, ort_km, lat, lon, jahr, jahr_man, gesichter, fehler, breite, hoehe "
                         f"FROM bild_eff WHERE ordner IN ({platz})", ordner_menge):
        meta[z[0]] = z[1:]
    namen = personen_namen(app.index)
    for gid, pfad, x, y, w, h, person in app.index.q(
            f"SELECT id, pfad, x, y, w, h, person FROM gesicht WHERE ordner IN ({platz}) ORDER BY x", ordner_menge):
        if person is None or person not in namen or namen[person][1]:
            continue
        gesichter.setdefault(pfad, []).append([round(x, 4), round(y, 4), round(w, 4), round(h, 4), person,
                                               namen[person][0], gid, namen[person][2]])
    return meta, gesichter


def bogen_html(app, eintraege, einordner):
    """eintraege: [(ordner, name, mtime, groesse)] -> (HTML der Felder, Bilddaten für JS)."""
    meta, gesichter = bild_daten(app, None, [(o, n) for o, n, *_ in eintraege])
    masse = []
    for o, name, mt, groesse in eintraege:  # Auflösung: aus dem Index, sonst Dateikopf lesen
        m = meta.get(f"{o}/{url_id(name)}")
        w, h = (m[9], m[10]) if m and m[9] else bildmasse(os.path.join(app.archiv.pfad, o, name), groesse, mt)
        masse.append((w, h))
    pixel = [w * h for w, h in masse if w]
    # höchste Auflösung hervorheben – nur wenn sich die Bilder des Ordners darin unterscheiden
    spitze = max(pixel) if einordner and len(pixel) > 1 and min(pixel) < max(pixel) else 0
    felder, daten = [], []
    for i, (o, name, mt, groesse) in enumerate(eintraege):
        uid = url_id(name)
        rel = f"{o}/{uid}"
        m = meta.get(rel)
        zeit, ort, km, lat, lon, ja, jm, n_ges, fehler, _, _ = m if m else (None,) * 11
        w, h = masse[i]
        roh = app.archiv.roh(o).get(os.path.splitext(name)[0].casefold())
        px = f"{w} × {h}" if w else "Auflösung unbekannt"
        technik = " · ".join(t for t in (px, groesse_text(groesse), f"NEF {groesse_text(roh[1])}" if roh else "") if t)
        oben = spitze and w and w * h == spitze
        such_stand = "fehler" if fehler else ("offen" if n_ges is None else "ok")
        jahr = jm if jm is not None else ja
        f = gesichter.get(rel, [])
        benannt = sorted({g[5] for g in f if not g[5].startswith("Person ")})
        monat = MONATE[int(zeit[5:7])] if zeit else ""
        kurz = ", ".join(t for t in ("" if jm is not None else monat, ort_text(ort, km)) if t)
        meta_html = e(kurz) + (f'{" – " if kurz else ""}<b>{e(", ".join(benannt))}</b>' if benannt else "")
        jahr_html = (f'<input class="jahr{" manuell" if jm is not None else ""}" value="{jahr or ""}" inputmode="numeric" '
                     f'maxlength="4" placeholder="Jahr" aria-label="Jahr">' if app.index else "")
        nr = "" if einordner else f'<a class="ordnernr" href="/o/{o}" title="Ordner öffnen">{o}</a>'
        felder.append(
            f'<figure class="feld" data-id="{uid}"><div class="zelle">'
            f'<button class="rahmen" type="button" aria-label="{e(name)} groß ansehen">'
            f'<img loading="lazy" decoding="async" src="/t/{o}/{uid}?v={mt}" alt=""></button>'
            f'<svg class="fettstift" viewBox="0 0 100 100" aria-hidden="true">'
            f'<path pathLength="100" d="{stift_pfad(f"{o}{name}")}"/></svg>'
            f'<span class="buchstabe" aria-hidden="true"></span>{nr}</div>'
            f'<figcaption><span class="lfd">{i + 1}</span><span class="dateiname" title="{e(name)}">{e(name)}</span>'
            f'<button class="knopf waehlen" type="button" aria-pressed="false">Auswählen</button>'
            f'<span class="technik{" spitze" if oben else ""}"'
            + (' title="Höchste Auflösung in diesem Ordner"' if oben else "") + f'>{e(technik)}</span>'
            f'<span class="meta">{jahr_html}<span class="mtext">{meta_html}</span></span></figcaption></figure>')
        karte = (f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=14/{lat:.5f}/{lon:.5f}"
                 if lat is not None else "")
        daten.append({"id": uid, "ordner": o, "name": anzeige(name), "g": f"/g/{o}/{uid}?v={mt}",
                      "o": f"/orig/{o}/{uid}", "z": zeit_text(zeit), "zm": monat, "ol": ort_text(ort, km, kurz=False),
                      "ok": ort_text(ort, km), "j": jahr, "jm": jm is not None, "k": karte, "f": f, "fs": such_stand,
                      "t": technik})
    return "".join(felder), daten


LUPE_HTML = ('<div class="lupe" hidden role="dialog" aria-label="Lupe"><div class="flaeche"><img alt="">'
             '<p class="ghinweis" hidden></p>'
             '<div class="nennbox" hidden role="dialog" aria-label="Gesicht benennen">'
             '<label>Wer ist das?<input class="nname" list="namenliste" maxlength="60" autocomplete="off" '
             'spellcheck="false"></label><div class="nknoepfe"><button class="knopf haupt" type="button"></button>'
             '<button class="knopf neben" type="button"></button></div><div class="nfuss">'
             '<button class="link kein" type="button" title="Falsch erkannt, z. B. Muster oder Foto im Foto">Kein Gesicht'
             '</button><button class="link abbr" type="button">Abbrechen</button></div></div>'
             '<datalist id="namenliste"></datalist></div>'
             '<div class="leiste"><span class="wo"></span>'
             '<input class="jahr" inputmode="numeric" maxlength="4" placeholder="Jahr" aria-label="Jahr (Taste J)">'
             '<span class="text"><span class="wer"></span>'
             '<span class="info"></span></span>'
             '<button class="knopf zurueck" type="button" aria-label="Voriges Bild">‹</button>'
             '<button class="knopf vor" type="button" aria-label="Nächstes Bild">›</button>'
             '<button class="knopf waehlen" type="button" aria-pressed="false">Auswählen</button>'
             '<button class="knopf gz" type="button" title="Taste G">Gesichter</button>'
             '<a class="knopf karte" target="_blank" rel="noopener noreferrer">Karte</a>'
             '<a class="knopf orig" target="_blank" rel="noopener">Original</a>'
             '<button class="knopf zu" type="button">Schließen</button></div></div>')


def ordner_zusammen(app, ordner):
    """Frühestes (wirksames) Datum und häufigster Ort eines Ordners, z. B. „März 2021, Leipzig“."""
    if not app.index:
        return ""
    z = app.index.einer("SELECT MIN(sortzeit), (SELECT ort FROM bild WHERE ordner=? AND ort IS NOT NULL "
                        "GROUP BY ort ORDER BY COUNT(*) DESC LIMIT 1) FROM bild_eff WHERE ordner=?", (ordner, ordner))
    return ", ".join(t for t in (datum_kurz(z[0]), z[1] or "") if t) if z else ""


def ordner_seite(app, ordner):
    app.auswahl.bereinigen(ordner)
    liste = app.archiv.ordner()
    bilder = app.archiv.bilder(ordner)
    pos = liste.index(ordner)
    zurueck = liste[pos - 1] if pos > 0 else None
    weiter = liste[pos + 1] if pos + 1 < len(liste) else None
    seite_nr = pos // app.pro_seite + 1
    felder, daten = bogen_html(app, [(ordner, n, mt, g) for n, g, mt in bilder], einordner=True)
    zusammen = ordner_zusammen(app, ordner)
    weg = []
    if zurueck:
        weg.append(f'<a class="knopf" href="/o/{zurueck}" title="Taste ←">Ordner {zurueck}</a>')
    if weiter:
        weg.append(f'<a class="knopf" href="/o/{weiter}" title="Taste →">Ordner {weiter}</a>')
    weg.append(f'<a class="knopf" href="/weiter/{ordner}" title="Taste N">Nächster ohne Auswahl</a>')
    ordnerjahr = ('<form class="ordnerjahr" id="ordnerjahr"><input class="jahr" inputmode="numeric" maxlength="4" '
                  'placeholder="Jahr" aria-label="Jahr für alle Bilder dieses Ordners" title="Jahr für alle Bilder dieses '
                  'Ordners setzen. Leer lassen = alle Korrekturen im Ordner entfernen.">'
                  '<button class="knopf">für alle Bilder</button></form>' if app.index and bilder else "")
    titel = (f'<div class="titel"><h1>{ordner}</h1><div><p id="info"></p><p class="ziel" id="ziel"></p>'
             f'<p class="leise" id="zusammen">{e(zusammen)}</p></div></div>'
             f'<nav class="weg" aria-label="Ordner wechseln">{"".join(weg)}</nav>{ordnerjahr}')
    inhalt = kopf(app, "ordner", titel)
    if not bilder:
        inhalt += '<p class="leer">In diesem Ordner liegen keine JPG- oder PNG-Bilder.</p>'
    else:
        inhalt += (f'<main class="bogen">{felder}</main>'
                   '<p class="hilfe">Bild anklicken zum Vergrößern. In der Lupe: <kbd>←</kbd> <kbd>→</kbd> blättern, '
                   '<kbd>Leertaste</kbd> aus- oder abwählen, <kbd>G</kbd> Gesichter (Namensschild anklicken = benennen, fehlt eins: ins Gesicht klicken), <kbd>J</kbd> Jahr ändern, '
                   '<kbd>Esc</kbd> schließen. Jahr korrigieren: ins Jahresfeld tippen, Enter; leeren = Jahr aus der Datei.</p>')
    inhalt += LUPE_HTML
    markiert = app.auswahl.markiert(ordner)
    js = {"einordner": True, "ordner": ordner, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {ordner: [url_id(m) for m in markiert]},
          "ziele": {ordner: {url_id(m): z for m, z in app.auswahl.ziele(ordner).items()}},
          "zurueck": f"/o/{zurueck}" if zurueck else None, "weiter": f"/o/{weiter}" if weiter else None,
          "offen": f"/weiter/{ordner}", "uebersicht": f"/?seite={seite_nr}"}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{ordner} – BestOf", inhalt, JS_BOGEN)


def such_seite(app, text, seite_nr):
    zeilen, erklaerung = suche_ausfuehren(app, text) if text.strip() else ([], [])
    gesamt = len(zeilen)
    pro = 240
    seiten = max(1, -(-gesamt // pro))
    seite_nr = min(max(1, seite_nr), seiten)
    teil = zeilen[(seite_nr - 1) * pro: seite_nr * pro]
    eintraege = []
    for o, uid, *_ in teil:
        treffer = app.archiv.datei(o, name_aus_id(uid))
        if treffer:
            eintraege.append((o, name_aus_id(uid), treffer[2], treffer[1]))
    felder, daten = bogen_html(app, eintraege, einordner=False)
    chips = "".join(f'<span class="chip">{e(t)}</span>' for t in erklaerung)
    titel = f'<div class="titel"><div><p id="info">{bilder_text(gesamt)}</p><p class="ziel" id="ziel"></p></div></div>'
    inhalt = kopf(app, "", titel, text)
    if erklaerung:
        inhalt += f'<div class="filter" aria-label="Erkannter Filter">{chips}</div>'
    if not text.strip():
        inhalt += '<p class="leer">Geben Sie Begriffe mit Komma getrennt ein, z. B. 2023, Leipzig, Anna.</p>'
    elif not eintraege:
        inhalt += '<p class="leer">Keine Fotos passen zu allen Begriffen. Entfernen Sie einen Begriff oder prüfen Sie die Schreibweise.</p>'
    else:
        inhalt += f'<main class="bogen">{felder}</main>'
        if seiten > 1:
            teile = [f"<span aria-current='page'>{n}</span>" if n == seite_nr else
                     f'<a href="/suche?{urlencode({"q": text, "seite": n})}">{n}</a>' for n in range(1, seiten + 1)]
            inhalt += f'<nav class="seiten" aria-label="Seiten">{"".join(teile)}</nav>'
    inhalt += LUPE_HTML
    ordner_menge = sorted({o for o, *_ in eintraege})
    js = {"einordner": False, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {o: [url_id(m) for m in app.auswahl.markiert(o)] for o in ordner_menge},
          "ziele": {o: {url_id(m): z for m, z in app.auswahl.ziele(o).items()} for o in ordner_menge}}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{text} – BestOf", inhalt, JS_BOGEN)


def personen_gruppen(index, mindest, ignorierte):
    """Gruppen mit gleichem Namen gehören zu einer Person (z. B. Kinder- und Erwachsenenfotos).
    Rückgabe: [(name oder None, [(id, anzahl), …])], benannte zuerst, dann nach Größe."""
    gruppen = {}
    for pid, name, anzahl in index.q("SELECT id, name, anzahl FROM person WHERE ignoriert = ? AND anzahl > 0",
                                     (1 if ignorierte else 0,)):
        schluessel = name.casefold() if name else f"#{pid}"
        eintrag = gruppen.setdefault(schluessel, [name, []])
        eintrag[1].append((pid, anzahl))
    liste = [(name, sorted(m, key=lambda x: -x[1])) for name, m in gruppen.values()
             if sum(a for _, a in m) >= mindest]
    liste.sort(key=lambda g: (g[0] is None, (g[0] or "").casefold(), -sum(a for _, a in g[1])))
    return liste


def personen_seite(app, alle, ignorierte):
    inhalt = kopf(app, "personen", '<div class="titel"><h1>Personen</h1></div>')
    if not app.indexer or not app.indexer.gesichter_aktiv:
        meldungen = " ".join(app.indexer.status["meldungen"][-2:]) if app.indexer else ""
        inhalt += f'<p class="leer">Die Gesichtserkennung ist aus. {e(meldungen)}</p>'
        return seite("Personen – BestOf", inhalt)
    personen = personen_gruppen(app.index, 1 if alle else 2, ignorierte)
    schalter = [f'<a class="knopf" href="/personen{"" if alle else "?alle=1"}">'
                f'{"Nur Personen mit mehreren Gesichtern" if alle else "Auch einzelne Gesichter zeigen"}</a>',
                f'<a class="knopf" href="/personen{"" if ignorierte else "?ignorierte=1"}">'
                f'{"Zurück zu den Personen" if ignorierte else "Ignorierte Personen"}</a>']
    inhalt += f'<div class="filter">{"".join(schalter)}</div>'
    inhalt += (f'<p class="lernstand"><span>{e(lern_zeile(app))}</span>'
               f'<button class="knopf" id="lernen" type="button" title="Schwelle und Abstand aus Ihren Korrekturen '
               f'und Bestätigungen neu einstellen, eindeutige Fälle umsortieren">Jetzt lernen</button></p>')
    if not personen:
        inhalt += ('<p class="leer">Noch keine Personen. Der Index sucht im Hintergrund nach Gesichtern; '
                   'diese Seite füllt sich, sobald er Fotos gelesen hat.</p>')
    teile = []
    for name, mitglieder in personen:
        ids = [pid for pid, _ in mitglieder]
        platz = ",".join("?" * len(ids))
        fotos = app.index.einer(f"SELECT COUNT(DISTINCT pfad) FROM gesicht WHERE person IN ({platz})", ids)[0]
        such = urlencode({"q": name or f"Person {ids[0]}"})
        id_text = ",".join(map(str, ids))
        mehrere = len(mitglieder) > 1
        zeilen = []
        for k, (pid, anzahl) in enumerate(mitglieder, 1):
            beispiele = app.index.q("SELECT g.id, b.mtime || '.' || CAST(g.x * 10000 AS INT) || '.' || CAST(g.y * 10000 AS INT) "
                                    "|| '.' || CAST(g.w * 10000 AS INT), g.pfad, g.x, g.y, g.w, g.h FROM gesicht g "
                                    "JOIN bild b ON b.pfad=g.pfad WHERE g.person=? ORDER BY g.pixel DESC LIMIT ?",
                                    (pid, 10 if mehrere else 14))
            gesichter = "".join(
                f'<figure class="gesicht"><a href="/suche?{such}"><img loading="lazy" src="/f/{gid}?v={mt}" alt=""></a>'
                f'<button class="nennen" type="button" data-id="{gid}" data-pfad="{e(gp)}" data-kasten="{gx},{gy},{gw},{gh}" '
                f'title="Dieses Gesicht ist jemand anderes" aria-label="Gesicht benennen">✎</button>'
                f'<button class="weg" type="button" data-id="{gid}" data-pfad="{e(gp)}" data-kasten="{gx},{gy},{gw},{gh}" '
                f'title="Kein Gesicht oder unbekannt – entfernen" aria-label="Gesicht entfernen">✕</button></figure>'
                for gid, mt, gp, gx, gy, gw, gh in beispiele)
            kopfzeile = (f'<div class="gkopf"><span>Gruppe {k}, {anzahl} {"Gesicht" if anzahl == 1 else "Gesichter"}</span>'
                         f'<a class="knopf" href="/personen?gruppe={pid}" title="Alle Gesichter dieser Gruppe, untypische zuerst">'
                         f'Alle prüfen</a><button class="knopf loesen" type="button" data-id="{pid}" '
                         f'title="Name entfernen – die Gruppe wird wieder eine eigene Person">Gruppe lösen</button></div>'
                         if mehrere else "")
            zeilen.append(f'<div class="gruppe" id="p{pid}">{kopfzeile}<div class="gesichter">{gesichter}</div></div>')
        hinweis = (f'<span class="hinweis">{len(mitglieder)} Gruppen, z. B. Fotos aus verschiedenen Jahren</span>'
                   if mehrere else "")
        teile.append(f'<section class="person"><div class="pkopf">'
                     f'<input class="pname" data-ids="{id_text}" data-alt="{e(name or "")}" value="{e(name or "")}" '
                     f'placeholder="Person {ids[0]}" aria-label="Name für Person {ids[0]}">'
                     f'<span class="leise">{bilder_text(fotos)}</span>{hinweis}'
                     f'<a class="knopf" href="/suche?{such}">Fotos zeigen</a>'
                     + ("" if mehrere else f'<a class="knopf" href="/personen?gruppe={ids[0]}" '
                                           f'title="Alle Gesichter, untypische zuerst – dort stecken meist Verwechslungen">'
                                           f'Alle {mitglieder[0][1]} prüfen</a>') +
                     f'<button class="knopf ignorieren" type="button" data-ids="{id_text}" data-an="{1 if ignorierte else 0}">'
                     f'{"Wieder zeigen" if ignorierte else "Ignorieren"}</button></div>{"".join(zeilen)}</section>')
    inhalt += (f'<main class="personen">{"".join(teile)}</main>'
               '<p class="hilfe">Namen eintippen und Enter drücken. Gleicher Name bei mehreren Gruppen = dieselbe Person, '
               'z. B. Kinder- und Erwachsenenfotos; die Gruppen bleiben getrennt und lassen sich mit „Gruppe lösen“ wieder '
               'trennen. ✎ ordnet ein einzelnes Gesicht jemand anderem zu – sehr ähnliche Gesichter derselben Gruppe '
               'wandern mit. ✕ entfernt es.</p>')
    return seite("Personen – BestOf", inhalt, JS_PERSONEN)


def gruppe_pruefen_seite(app, pid):
    """Alle Gesichter einer Gruppe, untypische zuerst (geringste Ähnlichkeit zum Gruppenmittel) –
    so findet man Verwechslungen, z. B. Kinder in der Gruppe eines Elternteils, und benennt sie gesammelt."""
    z = app.index.einer("SELECT name, summe, anzahl FROM person WHERE id=?", (pid,))
    if not z:
        return None
    name = z[0] or f"Person {pid}"
    mitte = np.frombuffer(z[1], np.float32)
    laenge = float(np.linalg.norm(mitte))
    zeilen = app.index.q("SELECT g.id, g.emb, g.pfad, g.x, g.y, g.w, g.h, b.mtime FROM gesicht g "
                         "LEFT JOIN bild b ON b.pfad = g.pfad WHERE g.person=?", (pid,))
    zeilen.sort(key=lambda r: float(np.frombuffer(r[1], np.float32) @ mitte) / laenge if r[1] and laenge > 0 else 2.0)
    gesamt, zeilen = len(zeilen), zeilen[:600]
    gesichter = "".join(
        f'<figure class="gesicht wahl" data-id="{gid}" title="{e(name_aus_id(gp.split("/", 1)[1]))} (Ordner {gp[:4]})">'
        f'<img loading="lazy" src="/f/{gid}?v={mt}.{int(gx * 1e4)}.{int(gy * 1e4)}.{int(gw * 1e4)}" alt="">'
        f'<span class="haken" aria-hidden="true">✓</span></figure>'
        for gid, _, gp, gx, gy, gw, gh, mt in zeilen)
    titel = f'<div class="titel"><h1>Prüfen</h1><div><p>{e(name)}: {gesamt} Gesichter, untypische zuerst{" (die ersten 600)" if gesamt > 600 else ""}</p></div></div>'
    inhalt = kopf(app, "personen", titel)
    namen = "".join(f'<option value="{e(n)}">' for n in namensliste(app.index))
    inhalt += ('<div class="pruefleiste"><span id="zahl" class="leise"></span>'
               '<button class="knopf" id="alle" type="button">Alle</button>'
               '<button class="knopf" id="keine" type="button">Keine</button>'
               '<input id="wname" class="pname" list="namenliste" maxlength="60" autocomplete="off" '
               'placeholder="Name, z. B. Anna" aria-label="Name für die ausgewählten Gesichter">'
               '<button class="knopf aktion" id="nennen" type="button">Ausgewählte so nennen</button>'
               '<button class="knopf aktion" id="bestaetigen" type="button" title="Stimmt so – bestof.py lernt '
               'daraus">Ausgewählte bestätigen</button>'
               '<button class="knopf aktion" id="entfernen" type="button">Ausgewählte entfernen</button>'
               f'<a class="knopf rechts" href="/personen">Zurück zu den Personen</a></div>'
               f'<datalist id="namenliste">{namen}</datalist>'
               f'<main class="personen"><div class="gesichter">{gesichter}</div></main>'
               '<p class="hilfe">Gesichter anklicken, Namen eintippen, „Ausgewählte so nennen“. Jedes Gesicht kommt zur '
               'ähnlichsten Gruppe dieses Namens oder bildet eine neue. Oben stehen die Gesichter, die am wenigsten zum '
               'Rest der Gruppe passen. Danach „Alle“ und „Ausgewählte bestätigen“: Bestätigte und korrigierte Gesichter '
               'sind die Labels, aus denen bestof.py lernt.</p>')
    return seite(f"{name} prüfen – BestOf", inhalt, JS_PRUEFEN)


def uebersicht(app, filt, seite_nr):
    alle = app.archiv.ordner()
    gewaehlt = app.auswahl.mit_auswahl()
    if filt == "ohne":
        liste = [o for o in alle if o not in gewaehlt]
    elif filt == "mit":
        liste = [o for o in alle if o in gewaehlt]
    else:
        filt, liste = "alle", alle
    seiten = max(1, -(-len(liste) // app.pro_seite))
    seite_nr = min(max(1, seite_nr), seiten)
    teil = liste[(seite_nr - 1) * app.pro_seite: seite_nr * app.pro_seite]
    zusammen = {}
    if app.index and teil:
        platz = ",".join("?" * len(teil))
        for o, zeit in app.index.q(f"SELECT ordner, MIN(sortzeit) FROM bild_eff WHERE ordner IN ({platz}) "
                                   f"GROUP BY ordner", teil):
            zusammen[o] = [datum_kurz(zeit)]
        for o, ort, _ in app.index.q(f"SELECT ordner, ort, COUNT(*) c FROM bild WHERE ordner IN ({platz}) "
                                     f"AND ort IS NOT NULL GROUP BY ordner, ort ORDER BY c DESC", teil):
            if len(zusammen.setdefault(o, [""])) == 1:
                zusammen[o].append(ort)
    kacheln = []
    for o in teil:
        bilder = app.archiv.bilder(o)
        markiert = app.auswahl.markiert(o)
        titelbild = next((b for b in bilder if b[0] in markiert), bilder[0] if bilder else None)
        bild = (f'<img loading="lazy" decoding="async" src="/t/{o}/{url_id(titelbild[0])}?v={titelbild[2]}" alt="">'
                if titelbild else "")
        wann = ", ".join(t for t in zusammen.get(o, []) if t)
        kacheln.append(f'<a class="kachel{" gewaehlt" if markiert else ""}" href="/o/{o}">'
                       f'<div class="bild">{bild}</div><div class="zeile"><span class="nr">{o}</span>'
                       f'<span class="leise">{bilder_text(len(bilder))}</span>{striche_svg(len(markiert))}</div>'
                       f'<span class="leise wann">{e(wann)}</span></a>')
    n_mit = len(gewaehlt & set(alle))

    def filterlink(schluessel, text, n):
        aktuell = ' aria-current="page"' if schluessel == filt else ""
        return f'<a href="/?filter={schluessel}"{aktuell}>{text} ({n})</a>'

    titel = (f'<p class="stand">{len(alle)} Ordner, {n_mit} mit Auswahl, '
             f'{bilder_text(app.auswahl.anzahl_bilder())} in BestOf</p>')
    werkzeuge = (f'<div class="filter"><nav class="navi" aria-label="Ordnerfilter">{filterlink("alle", "Alle", len(alle))}'
                 f'{filterlink("ohne", "Ohne Auswahl", len(alle) - n_mit)}{filterlink("mit", "Mit Auswahl", n_mit)}</nav>'
                 f'<form class="springen" action="/springen"><input name="o" inputmode="numeric" pattern="[0-9]*" '
                 f'maxlength="4" placeholder="Ordner" aria-label="Ordnernummer"><button class="knopf">Öffnen</button></form>'
                 f'<button class="knopf rechts" id="neuaufbau" type="button">BestOf neu aufbauen</button></div>')
    if not alle:
        hauptteil = (f'<p class="leer">Keine Ordner 0001–9999 gefunden in {e(app.archiv.pfad)}. '
                     f'Prüfen Sie den Pfad beim Start.</p>')
    elif not liste:
        hauptteil = '<p class="leer">Alle Ordner haben eine Auswahl.</p>' if filt == "ohne" else \
            '<p class="leer">Noch keine Auswahl. Öffnen Sie einen Ordner und wählen Sie bis zu ' \
            f'{app.auswahl.max_best} Bilder aus.</p>'
    else:
        hauptteil = f'<main class="raster">{"".join(kacheln)}</main>'
    nav = ""
    if seiten > 1:
        nummern = sorted({1, seiten, *range(max(1, seite_nr - 3), min(seiten, seite_nr + 3) + 1)})
        teile, letzte = [], 0
        for n in nummern:
            if n - letzte > 1:
                teile.append("<span aria-hidden='true'>…</span>")
            teile.append(f"<span aria-current='page'>{n}</span>" if n == seite_nr
                         else f'<a href="/?filter={filt}&seite={n}">{n}</a>')
            letzte = n
        nav = f'<nav class="seiten" aria-label="Seiten">{"".join(teile)}</nav>'
    quelle = ('<p class="quelle">Ortsnamen: GeoNames (CC BY 4.0). Gesichtserkennung lokal mit YuNet und SFace '
              '(OpenCV Zoo).</p>' if app.index else "")
    return seite("BestOf – " + os.path.basename(app.archiv.pfad),
                 kopf(app, "ordner", titel) + werkzeuge + hauptteil + nav + quelle, JS_UEBERSICHT)


# ---------------------------------------------------------------- Server
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


def _lernlog(db, art, gid, von=None, zu=None, aehnlich=None, abstand=None):
    """Protokoll Ihrer Labels: korrektur (automatisch falsch zugeordnet), label, bestaetigt, entfernt, umsortiert."""
    db.execute("INSERT INTO lernlog VALUES(?,?,?,?,?,?,?)",
               (time.strftime("%Y-%m-%d %H:%M:%S"), art, gid, von, zu, aehnlich, abstand))


def _fehler_aehnlichkeit(db, pid, v, name):
    """Wie ähnlich war ein falsch zugeordnetes Gesicht seiner Gruppe (ohne sich selbst) – und um wie viel
    ähnlicher als der nächsten anderen benannten Person? Beides braucht das Lernen."""
    z = db.execute("SELECT summe, anzahl FROM person WHERE id=?", (pid,)).fetchone()
    if not z or z[1] < 2:
        return None, None
    rest = np.frombuffer(z[0], np.float32) - v
    laenge = float(np.linalg.norm(rest))
    if laenge <= 1e-6:
        return None, None
    falsch = float(rest @ v) / laenge
    andere = []
    for summe, n in db.execute("SELECT summe, name FROM person WHERE name IS NOT NULL AND anzahl > 0 "
                               "AND ignoriert = 0").fetchall():
        s_vec = np.frombuffer(summe, np.float32)
        l2 = float(np.linalg.norm(s_vec))
        if n.casefold() != name.casefold() and l2 > 0:
            andere.append(float(s_vec @ v) / l2)
    return falsch, (falsch - max(andere)) if andere else None


def offene_korrekturen(app):
    if not app.index:
        return 0
    z = app.index.einer("SELECT COUNT(*) FROM lernlog WHERE art='korrektur' AND zeit > "
                        "COALESCE((SELECT v FROM meta WHERE k='lernen_zeit'), '')")
    return z[0] if z else 0


def _kosten(T, M, neg_a, neg_d, pos_a, pos_o):
    """Bewertet Schwelle T und Abstand M an Ihren Labels: Fehlzuordnungen zählen dreifach, verpasste einfach.
    neg: korrigierte Fehlzuordnungen (Ähnlichkeit zur falschen Gruppe, Vorsprung vor der nächsten Person),
    pos: bestätigte Gesichter (Ähnlichkeit zur eigenen Person, beste andere Person)."""
    falsch = int(np.sum((neg_a >= T) & (neg_d >= M)))
    richtig = (pos_a >= T) & (pos_a - pos_o >= M)
    daneben = (pos_o >= T) & (pos_o - pos_a >= M)
    falsch += int(np.sum(daneben))
    verpasst = int(np.sum(~richtig & ~daneben))
    return 3 * falsch + verpasst, falsch, verpasst


def _zahl(x):
    return f"{x:.2f}".replace(".", ",")


def lern_text(st):
    if st.get("kalibriert"):
        if (st["T"], st["M"]) != (st["T_vorher"], st["M_vorher"]):
            teil = (f"Schwelle {_zahl(st['T_vorher'])} → {_zahl(st['T'])}, "
                    f"Abstand {_zahl(st['M_vorher'])} → {_zahl(st['M'])}")
        else:
            teil = f"Schwelle {_zahl(st['T'])} und Abstand {_zahl(st['M'])} passen"
        teil += (f" (aus {st['korrekturen']} Korrekturen und {st['labels']} bestätigten Gesichtern; "
                 f"Fehlzuordnungen darin {st['fehler_vorher']} → {st['fehler_nachher']}, "
                 f"verpasst {st['verpasst_vorher']} → {st['verpasst_nachher']})")
    else:
        teil = (f"Schwelle bleibt {_zahl(st['T'])} – zum Einstellen braucht es mindestens 3 Korrekturen und "
                f"10 bestätigte Gesichter (jetzt {st['korrekturen']} und {st['labels']})")
    return f"Gelernt: {teil}; {st['umsortiert']} Gesichter umsortiert."


def lernen(app, anlass="automatisch"):
    """Lernen aus Ihren Labels.
    1. Schwelle und Abstand so wählen, dass Ihre korrigierten Fehlzuordnungen möglichst nicht wieder passieren,
       ohne bestätigte Gesichter zu verlieren (Gitter, Schritt je Runde begrenzt) -> bestof.conf.
    2. Automatisch zugeordnete Gesichter, die eindeutig besser zu einer anderen benannten Person passen,
       dorthin verschieben. Vorbild jeder Gruppe sind Ihre bestätigten Gesichter (ab 3), sonst alle.
    Von Ihnen gesetzte Zuordnungen bleiben unangetastet."""
    if not (app.index and app.indexer):
        return {"meldung": "Ohne Index gibt es nichts zu lernen."}
    T0, M0 = app.person_schwelle, app.abstand
    with app.index.lock:
        db = app.index.db
        personen = {pid: (name, ign) for pid, name, ign in db.execute("SELECT id, name, ignoriert FROM person")}
        zeilen = [z for z in db.execute("SELECT id, person, emb, manuell FROM gesicht WHERE person IS NOT NULL "
                                        "AND emb IS NOT NULL").fetchall() if z[1] in personen]
        neg = np.array(db.execute("SELECT aehnlich, COALESCE(abstand, 9) FROM lernlog WHERE art='korrektur' "
                                  "AND aehnlich IS NOT NULL ORDER BY zeit DESC LIMIT 2000").fetchall(),
                       dtype=float).reshape(-1, 2)
        if not zeilen:
            return {"meldung": "Noch keine Gesichter im Index."}
        gruppen = sorted({z[1] for z in zeilen})
        nummer = {p: i for i, p in enumerate(gruppen)}
        g = np.array([nummer[z[1]] for z in zeilen])
        E = np.stack([np.frombuffer(z[2], np.float32) for z in zeilen]).astype(np.float64)
        von_hand = np.array([bool(z[3]) for z in zeilen])
        k = len(gruppen)
        alle = np.zeros((k, E.shape[1]))
        np.add.at(alle, g, E)
        labels = np.zeros_like(alle)
        np.add.at(labels, g[von_hand], E[von_hand])
        mit_labels = np.bincount(g[von_hand], minlength=k) >= 3
        P = np.where(mit_labels[:, None], labels, alle)
        drin = np.where(mit_labels[g], von_hand, True)  # steckt das Gesicht im Vorbild seiner Gruppe?
        schl = [(personen[p][0] or "").casefold() for p in gruppen]
        spalten = np.array([i for i in range(k) if schl[i] and not personen[gruppen[i]][1]], dtype=int)
        namen_u = sorted({schl[i] for i in spalten})
        if len(namen_u) < 2:
            return {"meldung": "Zum Lernen braucht es mindestens zwei benannte Personen."}
        Pn = P[spalten]
        laenge = np.linalg.norm(Pn, axis=1)
        roh = E @ Pn.T
        S = np.where(laenge[None, :] > 0, roh / np.where(laenge > 0, laenge, 1)[None, :], -1.0)
        spalte_von = np.full(k, -1)
        spalte_von[spalten] = np.arange(len(spalten))
        z_i = np.where((spalte_von[g] >= 0) & drin)[0]
        c = spalte_von[g[z_i]]
        nenner = np.sqrt(np.maximum(laenge[c] ** 2 - 2 * roh[z_i, c] + 1, 0))
        S[z_i, c] = np.where(nenner > 1e-6, (roh[z_i, c] - 1) / np.maximum(nenner, 1e-6), -1.0)
        name_von_spalte = np.array([namen_u.index(schl[i]) for i in spalten])
        Mx = np.stack([S[:, name_von_spalte == u].max(axis=1) for u in range(len(namen_u))], axis=1)
        eigen_u = np.array([namen_u.index(schl[i]) if schl[i] in namen_u else -1 for i in g])
        # 1. Schwelle und Abstand
        pos = np.where(von_hand & (eigen_u >= 0))[0]
        pos_a = Mx[pos, eigen_u[pos]]
        andere = Mx[pos].copy()
        andere[np.arange(len(pos)), eigen_u[pos]] = -1.0
        pos_o = andere.max(axis=1) if len(pos) else np.zeros(0)
        neg_a, neg_d = neg[:, 0], neg[:, 1]
        kalibriert = len(neg) >= 3 and len(pos) >= 10
        T1, M1 = T0, M0
        vorher = _kosten(T0, M0, neg_a, neg_d, pos_a, pos_o)
        if kalibriert:
            beste = min((_kosten(T, M, neg_a, neg_d, pos_a, pos_o)[0], abs(T - T0) + abs(M - M0), T, M)
                        for T in np.round(np.arange(0.30, 0.7001, 0.01), 2)
                        for M in np.round(np.arange(0.0, 0.2001, 0.01), 2))
            T1 = round(float(np.clip(T0 + np.clip(beste[2] - T0, -0.08, 0.08), 0.30, 0.70)), 2)
            M1 = round(float(np.clip(M0 + np.clip(beste[3] - M0, -0.05, 0.05), 0.0, 0.20)), 2)
        nachher = _kosten(T1, M1, neg_a, neg_d, pos_a, pos_o)
        # 2. umsortieren
        M_um = max(M1, 0.05)
        auto = np.where(~von_hand)[0]
        bewegen = []
        if len(auto):
            ziel_u = Mx[auto].argmax(axis=1)
            s_b = Mx[auto, ziel_u]
            zweit = Mx[auto].copy()
            zweit[np.arange(len(auto)), ziel_u] = -1.0
            s_2 = zweit.max(axis=1)
            eigen = P[g[auto]]
            weg = np.where(drin[auto][:, None], E[auto], 0.0)
            l_e = np.linalg.norm(eigen - weg, axis=1)
            s_cur = np.where(l_e > 1e-6, (np.einsum("ij,ij->i", eigen, E[auto]) - np.where(drin[auto], 1.0, 0.0))
                             / np.maximum(l_e, 1e-6), -1.0)
            for j, r in enumerate(auto):
                if eigen_u[r] == ziel_u[j] or not (s_b[j] >= T1 and s_b[j] - s_2[j] >= M_um
                                                    and s_b[j] - s_cur[j] >= M_um):
                    continue
                kandidaten = np.where(name_von_spalte == ziel_u[j])[0]
                beste_spalte = kandidaten[int(np.argmax(S[r, kandidaten]))]
                bewegen.append((float(s_b[j] - max(s_2[j], s_cur[j])), int(r), gruppen[spalten[beste_spalte]]))
        bewegen.sort(reverse=True)
        plus, minus, umsortiert = [], [], 0
        for _, r, ziel in bewegen[:max(20, len(auto) // 4)]:
            gid, alt, emb = zeilen[r][0], zeilen[r][1], zeilen[r][2]
            if db.execute("UPDATE gesicht SET person=? WHERE id=? AND manuell=0 AND person=?",
                          (ziel, gid, alt)).rowcount:
                plus.append((ziel, emb))
                minus.append((alt, emb))
                umsortiert += 1
                _lernlog(db, "umsortiert", gid, personen[alt][0], personen[ziel][0])
        if plus:
            app.indexer._personen_aendern(db, plus=plus, minus=minus)
        jetzt = time.strftime("%Y-%m-%d %H:%M:%S")
        stand = {"zeit": jetzt, "anlass": anlass, "T_vorher": T0, "M_vorher": M0, "T": T1, "M": M1,
                 "korrekturen": int(len(neg)), "labels": int(len(pos)), "fehler_vorher": vorher[1],
                 "verpasst_vorher": vorher[2], "fehler_nachher": nachher[1], "verpasst_nachher": nachher[2],
                 "umsortiert": umsortiert, "kalibriert": bool(kalibriert)}
        db.execute("INSERT OR REPLACE INTO meta VALUES('lernen_zeit', ?)", (jetzt,))
        db.execute("INSERT OR REPLACE INTO meta VALUES('lernen_stand', ?)", (json.dumps(stand),))
        db.commit()
    if QUELLE.get("PERSON_SCHWELLE") != "Umgebung":
        app.person_schwelle = T1
    if QUELLE.get("ABSTAND") != "Umgebung":
        app.abstand = M1
    stand["meldung"] = lern_text(stand)
    if KONFIG is not None:
        notiz = f"{jetzt[:16]} – {stand['meldung'][9:]}"
        KONFIG.setzen({"PERSON_SCHWELLE": f"{T1:.2f}", "ABSTAND": f"{M1:.2f}"} if kalibriert else {}, notiz)
    return stand


def lern_zeile(app):
    """Kurzfassung für die Seite „Personen“."""
    if not app.lernen:
        return "Automatisches Lernen ist aus (LERNEN = 0 in bestof.conf)."
    offen = offene_korrekturen(app)
    z = app.index.einer("SELECT v FROM meta WHERE k='lernen_stand'")
    text = f"Lernen: Schwelle {_zahl(app.person_schwelle)}, Abstand {_zahl(app.abstand)}."
    if z:
        st = json.loads(z[0])
        text += f" Zuletzt am {st['zeit'][8:10]}.{st['zeit'][5:7]}. um {st['zeit'][11:16]}: {st['umsortiert']} umsortiert."
    return text + (f" Seitdem {offen} {'Korrektur' if offen == 1 else 'Korrekturen'} – neu gelernt wird ab "
                   f"{app.lernen_ab}.")


class Lerner(threading.Thread):
    """Lernt im Hintergrund, sobald LERNEN_AB Fehlzuordnungen korrigiert sind."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.ereignis = threading.Event()

    def anstossen(self):
        self.ereignis.set()

    def run(self):
        while True:
            self.ereignis.wait()
            time.sleep(5)  # weitere Korrekturen abwarten, dann einmal lernen
            self.ereignis.clear()
            try:
                if self.app.lernen and offene_korrekturen(self.app) >= self.app.lernen_ab:
                    print(f"Personen: {lernen(self.app, 'automatisch')['meldung']}", flush=True)
            except Exception:
                traceback.print_exc()


# ---------------------------------------------------------------- Import (fotosort) und Duplikate
FOTO_EXT = {".jpg", ".jpeg", ".png", ".nef"}
OHNE_ORDNER = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found"}


def _sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def papierkorb(app):
    return os.path.join(app.archiv.pfad, ".duplikate")


def papierkorb_inhalt(app):
    anzahl, groesse = 0, 0
    for wurzel, _, dateien in os.walk(papierkorb(app)):
        for d in dateien:
            if not d.endswith(".csv"):
                try:
                    groesse += os.path.getsize(os.path.join(wurzel, d))
                    anzahl += 1
                except OSError:
                    pass
    return anzahl, groesse


def duplikate_bereinigen(app, auftrag=None):
    """Inhaltsgleiche Dateien (SHA-256) in den Ordnern 0001–9999 auf eine reduzieren. Die übrigen kommen nach
    SORTIERT/.duplikate/<Zeit>/ (Papierkorb mit liste.csv). Behalten wird zuerst die in BestOf ausgewählte,
    dann eine mit Ihren Labels, dann die ohne Laufindex im Namen, dann die im kleinsten Ordner.
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
                                           "UNION SELECT pfad FROM jahr_manuell")} if app.index else set())

    def rang(d, gruppe):
        o, n = d[0], d[1]
        m = re.fullmatch(r"(.+)_\d+", os.path.splitext(n)[0])  # IMG_0001_1.JPG neben IMG_0001.JPG = Laufindex
        laufindex = bool(m) and any(os.path.splitext(x[1])[0].casefold() == m.group(1).casefold()
                                    for x in gruppe if x is not d)
        return (0 if (o, n) in markiert else 1, 0 if f"{o}/{url_id(n)}" in gelabelt else 1,
                1 if laufindex else 0, o, len(n), n)

    korb = os.path.join(papierkorb(app), time.strftime("%Y%m%d-%H%M%S"))
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
                if app.index:  # von Hand gesetztes Jahr auf die behaltene Datei übertragen
                    with app.index.lock:
                        app.index.db.execute("INSERT OR IGNORE INTO jahr_manuell SELECT ?, jahr FROM jahr_manuell "
                                             "WHERE pfad=?", (f"{behalten[0]}/{url_id(behalten[1])}",
                                                              f"{d[0]}/{url_id(d[1])}"))
                        app.index.db.commit()
    for o in betroffen:
        app.auswahl.bereinigen(o)
        try:
            os.rmdir(os.path.join(archiv, o))  # nur wenn der Ordner jetzt ganz leer ist
        except OSError:
            pass
    app.archiv.ordner(frisch=True)
    text = (f"Doppelte Dateien im Archiv: {verschoben} nach .duplikate verschoben ({groesse_text(weg_bytes)}), "
            f"von jedem Inhalt bleibt genau eine Datei." + (f" {fehler} ließen sich nicht verschieben." if fehler else ""))
    return {"meldung": text, "verschoben": verschoben, "bytes": weg_bytes}


class Auftrag(threading.Thread):
    """Import (fotosort.py, Modus copy, mit Duplikatprüfung), Rückgängig oder Duplikatsuche – einer zur Zeit."""

    def __init__(self, app, art, ziel=None):
        super().__init__(daemon=True)
        self.app, self.art, self.ziel = app, art, ziel
        self.proc, self.abbruch = None, False
        self.status = {"art": art, "ziel": ziel, "laeuft": True, "phase": "Start", "fertig": 0, "gesamt": 0,
                       "zusatz": "", "log": [], "ergebnis": "", "fehler": "", "protokoll": None,
                       "start": time.time(), "ende": None}

    def _zeile(self, text):
        self.status["log"] = (self.status["log"] + [text])[-400:]

    def _fotosort(self, argumente, umgebung):
        env = dict(os.environ, **umgebung, JA="1", FORTSCHRITT_JSON="1", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen([sys.executable, "-u", self.app.fotosort, *argumente], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, text=True,
                                     encoding="utf-8", errors="replace", bufsize=1)
        for zeile in self.proc.stdout:
            zeile = zeile.rstrip("\n")
            if zeile.startswith("#FS "):
                try:
                    d = json.loads(zeile[4:])
                except ValueError:
                    continue
                self.status.update(phase=d.get("titel", ""), fertig=d.get("fertig", 0), gesamt=d.get("gesamt", 0),
                                   zusatz=d.get("zusatz", ""))
                continue
            if zeile.startswith("Protokoll: ") and self.art == "import":
                self.status["protokoll"] = zeile[11:].strip()
            if zeile.strip():
                self._zeile(zeile)
        return self.proc.wait()

    def run(self):
        app, st = self.app, self.status
        try:
            if self.art == "import":
                code = self._fotosort([self.ziel, app.archiv.pfad],
                                      {"MODUS": "copy", "DUPLIKATE": "1", "JOBS": str(app.import_jobs)})
                wichtig = [z for z in st["log"] if z.startswith(("Gefunden:", "Duplikate:", "Gruppen:", "Ergänzt:",
                                                                 "JPG aus NEF:", "Fertig in", "Alle Bilder sind",
                                                                 "Keine Bilder", "Nichts zu", "Abbruch", "ABGEBROCHEN"))]
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
    if not app.import_erlaubt:
        return 403, {"fehler": "Import ist hier nicht freigegeben."}
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
        app.auftrag = Auftrag(app, "import", quelle)
    elif pfad == "/api/import/rueckgaengig":
        letzte = app.auftrag.status if app.auftrag else {}
        protokoll = letzte.get("protokoll") if letzte.get("art") == "import" else None
        if not protokoll or not os.path.isfile(protokoll):
            return 404, {"fehler": "Kein Import-Protokoll gefunden."}
        app.auftrag = Auftrag(app, "rueckgaengig", protokoll)
    elif pfad == "/api/duplikate" and daten.get("aktion") == "suchen":
        app.auftrag = Auftrag(app, "duplikate")
    elif pfad == "/api/duplikate" and daten.get("aktion") == "leeren":
        anzahl, groesse = papierkorb_inhalt(app)
        shutil.rmtree(papierkorb(app), ignore_errors=True)
        return 200, {"meldung": f"Papierkorb geleert: {anzahl} Dateien, {groesse_text(groesse)} frei."}
    else:
        return 404, {"fehler": "Unbekannt."}
    app.auftrag.start()
    return 200, {"meldung": "Gestartet."}


def import_seite(app):
    titel = ('<div class="titel"><h1>Import</h1><div><p>Fotos aus einem Ordner samt Unterordnern nach '
             f'{e(os.path.basename(app.archiv.pfad))} kopieren</p></div></div>')
    inhalt = kopf(app, "import", titel)
    if not app.import_erlaubt:
        inhalt += ('<p class="leer">Import ist nur am eigenen Rechner (HOST=127.0.0.1) oder mit PASSWORT möglich '
                   '(IMPORT = 1 in bestof.conf).</p>')
        return seite("Import – BestOf", inhalt)
    if not os.path.isfile(app.fotosort):
        inhalt += (f'<p class="leer">fotosort.py fehlt: {e(app.fotosort)}. Legen Sie fotosort.py neben bestof.py '
                   'oder setzen Sie FOTOSORT in bestof.conf.</p>')
        return seite("Import – BestOf", inhalt)
    inhalt += """<main class="import">
<section><h2>1. Ordner wählen</h2>
<form class="pfadzeile" id="pfadform"><input id="pfad" class="pname" spellcheck="false" autocomplete="off"
 aria-label="Ordner"><button class="knopf">Öffnen</button></form>
<nav class="krumen" id="krumen" aria-label="Pfad"></nav>
<div class="schnell" id="schnell"></div>
<ul class="ordnerliste" id="liste"></ul></section>
<section><h2>2. Kopieren</h2>
<p id="gewaehlt" class="leise"></p>
<div class="knopfzeile"><button class="knopf" id="zaehlen" type="button">Fotos zählen</button>
<button class="knopf haupt" id="start" type="button">In Sortiert kopieren</button></div>
<p id="zahl" class="leise"></p>
<p class="hilfe0">Die Quelle bleibt unverändert. fotosort.py sortiert ähnliche Fotos in Ordner (ergänzt passende
bestehende), legt zu NEF ein JPG an und kopiert inhaltsgleiche Dateien (gleiche SHA-256-Prüfsumme) nur einmal.
Danach bleibt im ganzen Archiv von jedem Inhalt genau eine Datei; überzählige kommen in den Papierkorb
<code>.duplikate</code>.</p></section>
<section id="lauf" hidden><h2>Fortschritt</h2>
<p id="phase"></p><progress id="balken" max="1" value="0"></progress>
<p id="ergebnis" class="ergebnis"></p>
<div class="knopfzeile"><button class="knopf" id="abbrechen" type="button">Abbrechen</button>
<button class="knopf" id="rueck" type="button" hidden>Import rückgängig</button></div>
<details><summary>Protokoll</summary><pre id="log"></pre></details></section>
<section><h2>Doppelte Dateien im Archiv</h2>
<p id="korb" class="leise"></p>
<div class="knopfzeile"><button class="knopf" id="dupsuchen" type="button">Jetzt prüfen</button>
<button class="knopf" id="leeren" type="button">Papierkorb leeren</button></div></section>
</main>"""
    return seite("Import – BestOf", inhalt, JS_IMPORT)


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
 $('start').disabled=laeuft||!frei;$('zaehlen').disabled=!frei;$('dupsuchen').disabled=laeuft;$('leeren').disabled=laeuft;}
function gb(b){return b>=1e9?(b/1e9).toFixed(1).replace('.',',')+' GB':(b/1e6).toFixed(1).replace('.',',')+' MB';}
$('pfadform').addEventListener('submit',ev=>{ev.preventDefault();oeffnen($('pfad').value);});
$('zaehlen').addEventListener('click',async()=>{$('zahl').textContent='Zähle …';
 const [ok,j]=await post('/api/import/zaehlen',{pfad:aktuell.pfad});
 if(!ok){$('zahl').textContent=j.fehler||'Zählen fehlgeschlagen.';return;}
 const arten=Object.entries(j.arten).map(([k,v])=>k.toUpperCase()+' '+v).join(' · ');
 $('zahl').textContent=(j.fertig?'':'mindestens ')+j.anzahl+' Fotos'+(arten?' ('+arten+')':'')+', '+gb(j.bytes)+
  ' in '+j.ordner+' Ordnern'+(j.fertig?'':' – Zählung nach 15 s beendet');});
$('start').addEventListener('click',async()=>{
 if(!confirm('Alle Fotos aus „'+aktuell.pfad+'“ samt Unterordnern nach Sortiert kopieren?'))return;
 const [ok,j]=await post('/api/import/start',{pfad:aktuell.pfad});
 if(!ok){meldung(j.fehler||'Start fehlgeschlagen.',true);return;}abfragen();});
$('abbrechen').addEventListener('click',async()=>{const [ok,j]=await post('/api/import/abbrechen',{});
 meldung(ok?'Abbruch angefordert – der laufende Ordner wird noch fertig.':(j.fehler||'Nichts zu abbrechen.'),!ok);});
$('rueck').addEventListener('click',async()=>{
 if(!confirm('Alle Dateien dieses Imports wieder aus Sortiert entfernen? Die Quelle ist davon nicht betroffen.'))return;
 const [ok,j]=await post('/api/import/rueckgaengig',{});if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}abfragen();});
$('dupsuchen').addEventListener('click',async()=>{const [ok,j]=await post('/api/duplikate',{aktion:'suchen'});
 if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}abfragen();});
$('leeren').addEventListener('click',async()=>{if(!confirm('Papierkorb .duplikate endgültig löschen?'))return;
 const [ok,j]=await post('/api/duplikate',{aktion:'leeren'});meldung(ok?j.meldung:(j.fehler||'Nicht möglich.'),!ok);abfragen();});
async function abfragen(){clearTimeout(zeitgeber);let j;
 try{const r=await fetch('/api/import/status');j=await r.json();}catch(_){zeitgeber=setTimeout(abfragen,3000);return;}
 $('korb').textContent=j.korb[0]?'Im Papierkorb .duplikate: '+j.korb[0]+' Dateien, '+gb(j.korb[1])+'.':'Papierkorb .duplikate ist leer.';
 const a=j.auftrag;laeuft=!!(a&&a.laeuft);knoepfe();
 if(!a){$('lauf').hidden=true;return;}
 $('lauf').hidden=false;$('abbrechen').hidden=!laeuft;
 const titel={import:'Import',rueckgaengig:'Rückgängig',duplikate:'Duplikatsuche'}[a.art];
 $('phase').textContent=titel+(a.ziel&&a.art==='import'?' von '+a.ziel:'')+': '+a.phase+
  (a.gesamt?' – '+a.fertig+' von '+a.gesamt:'')+(a.zusatz?' · '+a.zusatz:'');
 $('balken').max=a.gesamt||1;$('balken').value=laeuft?(a.gesamt?a.fertig:0):($('balken').max);
 if(laeuft&&!a.gesamt)$('balken').removeAttribute('value');
 $('ergebnis').textContent=a.fehler||a.ergebnis||'';$('ergebnis').classList.toggle('fehler',!!a.fehler);
 $('log').textContent=a.log.join('\\n');$('rueck').hidden=laeuft||a.art!=='import'||!a.protokoll;
 if(laeuft)zeitgeber=setTimeout(abfragen,1000);}
let start='';try{start=localStorage.getItem('importPfad')||'';}catch(_){}
oeffnen(start);abfragen();
"""


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Abgebrochene Verbindungen (Tab zu, Browser beendet) sind normal – keinen Traceback ins Terminal."""
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def lokale_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "IP-des-Rechners"


def main():
    args = sys.argv[1:]
    if len(args) != 1 or args[0] in ("-h", "--help", "--hilfe"):
        print(__doc__)
        return 0 if args else 2
    archiv_pfad = os.path.abspath(args[0])
    if not os.path.isdir(archiv_pfad):
        sys.exit(f"Fehler: {archiv_pfad} existiert nicht – Laufwerk eingehängt?")
    global KONFIG
    KONFIG = Konfig(os.path.abspath(os.path.expanduser(os.environ.get("BESTOF_CONF", "").strip()
                                                       or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                       "bestof.conf"))))
    port = _env("PORT", 8765, int)
    host = _env("HOST", "127.0.0.1")
    bestof = _env("BESTOF", "BestOf")
    bestof = bestof if os.path.isabs(bestof) else os.path.join(archiv_pfad, bestof)
    vorschau_ordner = _env("VORSCHAU", os.path.join(archiv_pfad, ".vorschau"))
    if vorschau_ordner == "0":
        vorschau_ordner = None
    else:
        vorschau_ordner = os.path.abspath(os.path.expanduser(vorschau_ordner))
        try:
            os.makedirs(vorschau_ordner, exist_ok=True)
            probe = os.path.join(vorschau_ordner, ".schreibtest")
            with open(probe, "w") as f:
                f.write("ok")
            os.unlink(probe)
        except OSError as fehler:
            print(f"Hinweis: {vorschau_ordner} nicht beschreibbar ({fehler.strerror}) – Vorschaubilder nur im Arbeitsspeicher.")
            vorschau_ordner = None

    app = App()
    app.archiv = Archiv(archiv_pfad)
    app.auswahl = Auswahl(app.archiv, bestof, max(1, min(26, _env("MAX_BEST", 3, int))))
    app.vorschau = Vorschau(vorschau_ordner, max(0, _env("GROSS", 2048, int)))
    app.pro_seite = max(12, _env("PRO_SEITE", 120, int))
    app.passwort = _env("PASSWORT", "")
    app.gesichter = _env("GESICHTER", "1") != "0"
    app.index_jobs = max(1, _env("INDEX_JOBS", max(1, (os.cpu_count() or 2) // 2), int))
    app.ort_min_ew = _env("ORT_MIN_EW", 10000, int)
    app.naehe_km = _env("NAEHE_KM", 15.0, float)
    app.person_schwelle = _env("PERSON_SCHWELLE", 0.40, float)
    app.nachziehen = _env("NACHZIEHEN", 0.50, float)
    app.abstand = min(0.3, max(0.0, _env("ABSTAND", 0.0, float)))
    app.lernen = _env("LERNEN", "1") != "0"
    app.lernen_ab = max(1, _env("LERNEN_AB", 5, int))
    app.lerner = None
    app.fotosort = os.path.abspath(os.path.expanduser(_env("FOTOSORT", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fotosort.py"))))
    app.import_jobs = max(1, _env("IMPORT_JOBS", app.index_jobs, int))
    app.auftrag = None
    app.erkenn_px = max(320, _env("ERKENN_PX", 1920, int))
    app.min_gesicht = max(8, _env("MIN_GESICHT", 48, int))
    app.gesicht_score = min(0.99, max(0.3, _env("GESICHT_SCORE", 0.50, float)))
    app.gegenprobe = min(0.99, max(0.0, _env("GEGENPROBE", 0.80, float)))
    app.sucher = None
    app.aktualisieren = max(30, _env("AKTUALISIEREN", 300, int))
    app.daten = os.path.abspath(os.path.expanduser(_env("DATEN", "~/.cache/fotosort")))
    app.index, app.indexer = None, None
    if _env("INDEX", "1") != "0":
        try:
            app.index = Index(os.path.join(archiv_pfad, ".bestof-index.sqlite3"))
            app.indexer = Indexer(app)
            app.lerner = Lerner(app)
        except sqlite3.Error as fehler:
            print(f"Hinweis: Index nicht nutzbar ({fehler}) – ohne Metadaten und Filter.")
            app.index = None
    Handler.app = app

    try:
        server = Server((host, port), Handler)
    except OSError as fehler:
        sys.exit(f"Fehler: Port {port} auf {host} nicht nutzbar ({fehler.strerror}). Anderen PORT wählen.")
    server.daemon_threads = True
    lokal = host in ("127.0.0.1", "localhost", "::1")
    app.import_erlaubt = _env("IMPORT", "1") != "0" and (lokal or bool(app.passwort))
    adresse = f"http://{'127.0.0.1' if lokal or host == '0.0.0.0' else host}:{port}"
    print(f"bestof {VERSION}")
    print(f"Archiv:   {archiv_pfad}  ({len(app.archiv.ordner())} Ordner, "
          f"{bilder_text(app.auswahl.anzahl_bilder())} ausgewählt)")
    print(f"BestOf:   {bestof}")
    print(f"Vorschau: {vorschau_ordner or 'nur Arbeitsspeicher'}")
    print(f"Index:    {'aus' if not app.index else app.index.pfad + f' ({app.index_jobs} Prozesse)'}")
    print(f"Einstellungen: {KONFIG.pfad} – Personen: Schwelle {app.person_schwelle:.2f} "
          f"({QUELLE.get('PERSON_SCHWELLE')}), Abstand {app.abstand:.2f} ({QUELLE.get('ABSTAND')}), "
          f"Lernen {'an, ab ' + str(app.lernen_ab) + ' Korrekturen' if app.lernen else 'aus'}")
    print(f"Adresse:  {adresse}" + (f"  ·  im Heimnetz: http://{lokale_ip()}:{port}" if host == "0.0.0.0" else ""))
    if not lokal and not app.passwort:
        print("Warnung: ohne PASSWORT kann jeder im Netz die Fotos sehen und die Auswahl ändern.")
    print("Strg+C beendet.", flush=True)
    if app.indexer:
        app.indexer.start()
    if app.lerner:
        app.lerner.start()
        app.lerner.anstossen()  # Korrekturen aus der letzten Sitzung?
    if _env("BROWSER", "1") != "0":
        threading.Timer(0.8, lambda: webbrowser.open(adresse)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        if app.indexer:
            app.indexer.stoppen()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
