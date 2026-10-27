"""fotolese.sort.bericht – Zahlen-/Größen-/Dauerformate, Fortschrittsanzeige.

Leaf-Modul ohne Abhängigkeiten zu anderen sort-Modulen, damit alle es importieren
können. JSON_FORTSCHRITT schaltet die von bestof.py gelesenen "#FS"-Zeilen frei.
"""
import json
import os
import sys
import time


def zahl(n):
    return f"{n:,}".replace(",", ".")


def gb(b):
    if b < 1e9:
        return f"{b / 1e6:.0f} MB" if b >= 1e6 else f"{b / 1e3:.0f} kB"
    return f"{b / 1e9:.1f}".replace(".", ",") + " GB"


def dauer(s):
    s = int(s)
    if s >= 3600:
        return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d} h"
    return f"{s // 60}:{s % 60:02d} min"


def info(text=""):
    print(text, flush=True)


JSON_FORTSCHRITT = os.environ.get("FORTSCHRITT_JSON", "").strip() == "1"


class Fortschritt:
    def __init__(self, titel, gesamt, einheit="Dateien"):
        self.titel, self.gesamt, self.einheit = titel, gesamt, einheit
        self.start = self.zuletzt = time.time()
        self.tty = sys.stderr.isatty()
        self.naechste_prozent = 10

    def melden(self, fertig, zusatz="", ende=False):
        jetzt = time.time()
        if JSON_FORTSCHRITT:  # für bestof.py: eine Zeile je halbe Sekunde
            if ende or jetzt - self.zuletzt >= 0.5:
                self.zuletzt = jetzt
                print("#FS " + json.dumps({"titel": self.titel, "fertig": fertig, "gesamt": self.gesamt,
                                           "zusatz": zusatz.strip(" ·"), "ende": ende}), flush=True)
            return
        if not ende and jetzt - self.zuletzt < 1.0:
            return
        self.zuletzt = jetzt
        anteil = fertig / self.gesamt if self.gesamt else 1.0
        lauf = jetzt - self.start
        rest = lauf / anteil - lauf if anteil > 0 else 0
        zeile = (f"{self.titel}: {zahl(fertig)}/{zahl(self.gesamt)} {self.einheit} "
                 f"({anteil * 100:.0f} %){zusatz}" + ("" if ende else f" · Rest ~{dauer(rest)}"))
        if self.tty:
            sys.stderr.write("\r\033[K" + zeile + ("\n" if ende else ""))
            sys.stderr.flush()
        elif ende or anteil * 100 >= self.naechste_prozent:
            self.naechste_prozent = int(anteil * 10) * 10 + 10
            sys.stderr.write(zeile + "\n")
