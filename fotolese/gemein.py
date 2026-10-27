"""fotolese.gemein – Helfer, die fotosort (sort) und bestof (web) gemeinsam nutzen.

Vereinheitlicht den zuvor in beiden Skripten doppelt vorhandenen Code:
Einstellungen (_env), SHA-256 und das Datum aus dem Dateinamen.
"""
import hashlib
import os
import re
import sys


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
