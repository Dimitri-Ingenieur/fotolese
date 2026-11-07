"""fotolese.gemein – Helfer, die fotosort (sort) und bestof (web) gemeinsam nutzen.

Vereinheitlicht den zuvor in beiden Skripten doppelt vorhandenen Code:
Einstellungen (_env), SHA-256, das Datum aus dem Dateinamen, die Namen der Ordner im Archiv und die Liste der in
bestof gedrehten Fotos.
"""
import hashlib
import json
import os
import re
import sys

# Ordner im Archiv: 0000 (Sammelordner), 0001–9999 vierstellig, ab 10000 fünfstellig bis 99999 – so, wie
# f"{n:04d}" sie schreibt. Jede Nummer hat genau einen Namen: 01234 ist kein Ordner (sonst gäbe es 1234 doppelt).
MAX_ORDNER = 99999
ORDNER_RE = r"(?:\d{4}|[1-9]\d{4})"
ORDNER_MUSTER = re.compile(ORDNER_RE)


def ist_ordner(name):
    """Name eines Ordners 0000–99999?"""
    return ORDNER_MUSTER.fullmatch(name) is not None


def ordner_folge(name):
    """Sortierschlüssel nach Nummer: 9999 vor 10000 – als Text stünde 10000 vor 2000. Verträgt jeden Namen."""
    return len(name), name


def _env(name, standard, typ=str, konfig=None, quelle=None):
    """Einstellung lesen: Umgebungsvariable vor Konfig-Datei vor Standardwert.

    konfig: dict NAME->Wert (z. B. aus bestof.conf) oder None (nur Umgebung, fotosort).
    quelle: dict, in dem die Herkunft je NAME vermerkt wird, oder None.
    Ungültige Umgebungswerte beenden das Programm; ungültige Konfig-Werte lösen
    nur einen Hinweis aus und der Standardwert gilt.
    """
    roh, woher = os.environ.get(name, "").strip(), "Umgebung"
    if roh == "" and konfig is not None:
        roh, woher = konfig.get(name, "").strip(), "bestof.conf"
    if roh == "":
        if quelle is not None:
            quelle[name] = "Standard"
        return standard
    try:
        wert = typ(roh)
    except ValueError:
        if woher == "Umgebung" or konfig is None:
            sys.exit(f"Fehler: {name}={roh!r} ist ungültig.")
        print(f"Hinweis: {name} = {roh!r} in bestof.conf ist ungültig – es gilt {standard}.")
        if quelle is not None:
            quelle[name] = "Standard"
        return standard
    if quelle is not None:
        quelle[name] = woher
    return wert


# In bestof gedrehte oder gespiegelte Fotos: SORTIERT/.bestof-gedreht.json, Prüfsumme jetzt -> Inhalt von vorher
GEDREHT = ".bestof-gedreht.json"


def gedrehte_laden(archiv):
    """{SHA-256 jetzt: (SHA-256 vorher, Größe vorher, Größe jetzt)} der in bestof gedrehten Fotos. Für die Duplikat-
    suche beim Import: Der Inhalt von vor dem Drehen gilt als vorhanden, solange das gedrehte Foto im Archiv liegt."""
    try:
        with open(os.path.join(archiv, GEDREHT), encoding="utf-8") as f:
            daten = json.load(f)["gedreht"]
        return {jetzt: (v["vorher"], int(v["vorher_groesse"]), int(v["groesse"])) for jetzt, v in daten.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def sha256(pfad):
    """SHA-256 einer Datei, in 1-MiB-Blöcken gelesen."""
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


DATUM_IM_NAMEN = re.compile(
    r"(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
    r"(?:[-_. T]?([01]\d|2[0-3])[-_.:]?([0-5]\d)[-_.:]?([0-5]\d))?(?!\d)")


def datum_teile_aus_name(name):
    """Datum im Dateinamen finden (IMG-20230714-WA0003.jpg, 20230714_103200.jpg,
    Screenshot_2023-07-14-10-32-00.png). Rückgabe: (JJJJ, MM, TT, hh, mm, ss) oder None.
    Fehlende Uhrzeit wird zu 12:00:00 ergänzt (Mittag, wie bisher in beiden Skripten)."""
    m = DATUM_IM_NAMEN.search(name)
    if not m:
        return None
    return (m.group(1), m.group(2), m.group(3),
            m.group(4) or "12", m.group(5) or "00", m.group(6) or "00")
