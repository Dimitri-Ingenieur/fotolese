"""fotolese.sort.lauf – Verschieben/Kopieren/Verlinken, Protokoll (CSV) und Rückgängig.

Beweger kopiert über Laufwerksgrenzen erst vollständig, prüft nach os.sync die Größe
und löscht die Quelle erst danach. _STOPP/_sigint erlauben sauberen Abbruch per Strg+C.
"""
import csv
import errno
import os
import shutil
import signal
import sys
import time
from collections import Counter

from fotolese.sort.konst import KRITISCH, SYNC_BYTES, SYNC_DATEIEN
from fotolese.sort.bericht import Fortschritt, gb, info, zahl
from fotolese.sort.plan import eindeutig
from fotolese.sort.nef import nef_zu_jpg


def freier_pfad(basis):
    """basis + '.csv', bei Bedarf basis_2.csv, basis_3.csv … – nie überschreiben."""
    n = 1
    while True:
        pfad = f"{basis}.csv" if n == 1 else f"{basis}_{n}.csv"
        if not os.path.lexists(pfad):
            return pfad
        n += 1


class Protokoll:
    FELDER = ["ordner", "quelle", "ziel", "bytes", "status"]

    def __init__(self, basis):
        self.pfad = freier_pfad(basis)
        self.f = open(self.pfad, "x", newline="", encoding="utf-8", errors="surrogateescape")
        self.w = csv.writer(self.f)
        self.w.writerow(self.FELDER)

    def zeile(self, ordner, quelle, ziel, groesse, status):
        self.w.writerow([ordner, quelle, ziel, groesse, status])
        self.f.flush()

    def schliessen(self):
        self.f.close()


class Beweger:
    """Verschieben/Kopieren/Verlinken. Bei Kopie über Laufwerksgrenzen: erst sync,
    dann Größenvergleich, erst danach wird die Quelle gelöscht."""

    def __init__(self, protokoll, modus, text_ok="verschoben", nach_erfolg=None):
        self.prot, self.modus, self.text_ok = protokoll, modus, text_ok
        self.nach_erfolg = nach_erfolg  # z. B. Cache-Eintrag für den neuen Pfad
        self.wartend, self.wartend_bytes = [], 0
        self.zaehler = Counter()
        self.quellordner = set()

    def datei(self, ordner, quelle, ziel, groesse):
        if self.modus == "link":
            os.symlink(os.path.abspath(quelle), ziel)
            self._fertig(ordner, quelle, ziel, groesse, "verlinkt")
            return
        if self.modus == "move":
            try:
                os.rename(quelle, ziel)
                self._fertig(ordner, quelle, ziel, groesse, self.text_ok)
                return
            except OSError as e:
                if e.errno != errno.EXDEV:
                    raise
        tmp = ziel + ".fotosort-tmp"
        try:
            shutil.copyfile(quelle, tmp)
            try:
                shutil.copystat(quelle, tmp)
            except OSError:
                pass  # exFAT/NTFS: Rechte nicht übertragbar, Zeitstempel schon
            os.rename(tmp, ziel)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self.wartend.append((ordner, quelle, ziel, groesse))
        self.wartend_bytes += groesse
        if self.wartend_bytes >= SYNC_BYTES or len(self.wartend) >= SYNC_DATEIEN:
            self.abschliessen()

    def abschliessen(self):
        if not self.wartend:
            return
        os.sync()
        for ordner, quelle, ziel, groesse in self.wartend:
            try:
                gleich = os.path.getsize(ziel) == os.path.getsize(quelle)
            except OSError:
                gleich = False
            if not gleich:
                self._fertig(ordner, quelle, ziel, groesse, "fehler: Größe weicht ab, Quelle behalten")
                continue
            if self.modus == "move":
                try:
                    os.unlink(quelle)
                    self._fertig(ordner, quelle, ziel, groesse, self.text_ok)
                except OSError as e:
                    self._fertig(ordner, quelle, ziel, groesse, f"kopiert (Quelle nicht löschbar: {e.strerror})")
            else:
                self._fertig(ordner, quelle, ziel, groesse, "kopiert")
        self.wartend, self.wartend_bytes = [], 0

    def jpg_erzeugen(self, ordner, nef, ziel):
        groesse = nef_zu_jpg(nef, ziel)
        self.prot.zeile(ordner, nef, ziel, groesse, "erzeugt")
        self.zaehler["JPG erzeugt"] += 1

    def fehler(self, ordner, quelle, ziel, groesse, e):
        grund = getattr(e, "strerror", None) or str(e)
        self._fertig(ordner, quelle, ziel, groesse, f"fehler: {grund}")

    def _fertig(self, ordner, quelle, ziel, groesse, status):
        self.prot.zeile(ordner, quelle, ziel, groesse, status)
        self.zaehler[status.split(" ")[0].rstrip(":")] += 1
        if status == self.text_ok:
            self.quellordner.add(os.path.dirname(quelle))
        if self.nach_erfolg is not None and (status == self.text_ok or status.startswith("kopiert")):
            self.nach_erfolg(quelle, ziel)


_STOPP = {"an": False}


def _sigint(signum, frame):
    _STOPP["an"] = True
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.stderr.write("\nAbbruch angefordert – der laufende Ordner wird noch fertig. "
                     "Erneut Strg+C = sofort.\n")


def leere_ordner_entfernen(ordnerliste, grenze):
    grenze = os.path.realpath(grenze)
    entfernt = 0
    for o in sorted(ordnerliste, key=len, reverse=True):
        while os.path.realpath(o) != grenze and os.path.realpath(o).startswith(grenze + os.sep):
            try:
                os.rmdir(o)
                entfernt += 1
            except OSError:
                break
            o = os.path.dirname(o)
    return entfernt


def bestaetigen(frage):
    if os.environ.get("JA", "").strip() == "1":
        return True
    if not sys.stdin.isatty():
        sys.exit("Abbruch: keine Rückfrage möglich (kein Terminal). Mit JA=1 starten.")
    try:
        antwort = input(f"{frage} [j/N] ").strip().lower()
    except EOFError:
        antwort = ""
    return antwort in ("j", "ja", "y", "yes")


def ausfuehren(plan, modus, prot, gesamt_bytes, nach_erfolg=None):
    verb = {"move": "Verschiebe", "copy": "Kopiere", "link": "Verlinke"}[modus]
    beweger = Beweger(prot, modus, nach_erfolg=nach_erfolg if modus != "link" else None)
    anzahl = sum(len(e) for _, e in plan)
    fort = Fortschritt(verb, anzahl)
    erledigt, bytes_fertig, start = 0, 0, time.time()
    alter_handler = signal.signal(signal.SIGINT, _sigint)
    abbruch = None
    umgeleitet = {}
    try:
        for ordner, eintraege in plan:
            zielordner = os.path.dirname(eintraege[0][1])
            os.makedirs(zielordner, exist_ok=True)
            for quelle, ziel, groesse, _dev, art in eintraege:
                geplant = ziel
                if os.path.lexists(ziel):  # Sicherheitsnetz, sollte nicht vorkommen
                    belegt = {n.casefold() for n in os.listdir(zielordner)}
                    ziel = os.path.join(zielordner, eindeutig(os.path.basename(ziel), belegt))
                    umgeleitet[geplant] = ziel
                try:
                    if art == "jpg":
                        beweger.jpg_erzeugen(ordner, umgeleitet.get(quelle, quelle), ziel)
                    else:
                        beweger.datei(ordner, quelle, ziel, groesse)
                except OSError as e:
                    beweger.fehler(ordner, quelle, ziel, groesse, e)
                    if e.errno in KRITISCH:
                        abbruch = f"{e.strerror} bei {ziel}"
                        break
                except Exception as e:  # z. B. defekte Vorschau im NEF: nur diese Datei auslassen
                    beweger.fehler(ordner, quelle, ziel, groesse, e)
                erledigt += 1
                bytes_fertig += groesse
                lauf = max(time.time() - start, 1e-6)
                fort.melden(erledigt, f" · {gb(bytes_fertig)}/{gb(gesamt_bytes)} · {bytes_fertig / lauf / 1e6:.0f} MB/s")
            if abbruch or _STOPP["an"]:
                break
        beweger.abschliessen()
    finally:
        signal.signal(signal.SIGINT, alter_handler)
    fort.melden(erledigt, f" · {gb(bytes_fertig)}", ende=True)
    return beweger, abbruch or ("Strg+C" if _STOPP["an"] else None)


def rueckgaengig(logpfad):
    if not os.path.isfile(logpfad):
        sys.exit(f"Fehler: Protokoll {logpfad} nicht gefunden.")
    with open(logpfad, newline="", encoding="utf-8", errors="surrogateescape") as f:
        zeilen = list(csv.DictReader(f))
    letzte = {}
    for z in zeilen:
        if z.get("ziel"):
            letzte[z["ziel"]] = z
    zurueck = [z for z in letzte.values() if z["status"] == "verschoben"]
    entfernen = [z for z in letzte.values() if z["status"] in ("kopiert", "verlinkt", "erzeugt")
                 or z["status"].startswith("kopiert (")]
    info(f"Protokoll: {logpfad}")
    info(f"Zurückverschieben: {zahl(len(zurueck))} Dateien · Kopien, Links und erzeugte JPG entfernen: "
         f"{zahl(len(entfernen))}")
    if not zurueck and not entfernen:
        info("Nichts zu tun.")
        return 0
    if not bestaetigen("Rückgängig machen?"):
        sys.exit("Abgebrochen – nichts verändert.")
    prot = Protokoll((logpfad[:-4] if logpfad.endswith(".csv") else logpfad) + "_undo")
    undo_pfad = prot.pfad
    beweger = Beweger(prot, "move", text_ok="zurückverschoben")
    konflikte = 0
    fort = Fortschritt("Rückgängig", len(zurueck) + len(entfernen))
    erledigt = 0
    for z in reversed(zurueck):
        quelle, ziel, groesse = z["quelle"], z["ziel"], int(z["bytes"] or 0)
        erledigt += 1
        if not os.path.lexists(ziel):
            prot.zeile(z["ordner"], ziel, quelle, groesse, "fehlt im Ziel")
            continue
        if os.path.lexists(quelle):
            konflikte += 1
            prot.zeile(z["ordner"], ziel, quelle, groesse, "konflikt: Originalpfad belegt")
            continue
        try:
            os.makedirs(os.path.dirname(quelle), exist_ok=True)
            beweger.datei(z["ordner"], ziel, quelle, groesse)
        except OSError as e:
            beweger.fehler(z["ordner"], ziel, quelle, groesse, e)
            if e.errno in KRITISCH:
                break
        fort.melden(erledigt)
    beweger.abschliessen()
    entfernt = 0
    for z in entfernen:
        erledigt += 1
        quelle, ziel = z["quelle"], z["ziel"]
        try:
            if z["status"] == "erzeugt":
                if os.path.isfile(ziel) and not os.path.islink(ziel):
                    os.unlink(ziel)
                    entfernt += 1
                    prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "erzeugte JPG entfernt")
                else:
                    prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "erzeugte JPG fehlt schon")
            elif os.path.islink(ziel) and os.readlink(ziel) == os.path.abspath(quelle):
                os.unlink(ziel)
                entfernt += 1
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "link entfernt")
            elif (os.path.isfile(ziel) and not os.path.islink(ziel) and os.path.isfile(quelle)
                  and os.path.getsize(ziel) == os.path.getsize(quelle)):
                os.unlink(ziel)
                entfernt += 1
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "kopie entfernt")
            else:
                prot.zeile(z["ordner"], ziel, quelle, z["bytes"], "behalten: Original fehlt oder weicht ab")
        except OSError as e:
            prot.zeile(z["ordner"], ziel, quelle, z["bytes"], f"fehler: {e.strerror}")
        fort.melden(erledigt)
    fort.melden(erledigt, ende=True)
    prot.schliessen()
    ordner = {os.path.dirname(z["ziel"]) for z in letzte.values()}
    leer = 0
    for o in ordner:
        try:
            os.rmdir(o)
            leer += 1
        except OSError:
            pass
    info(f"Fertig: {zahl(beweger.zaehler['zurückverschoben'])} zurückverschoben · "
         f"{zahl(entfernt)} Kopien/Links/JPG entfernt · {konflikte} Konflikte · {leer} leere Ordner entfernt.")
    info(f"Protokoll: {undo_pfad}")
    return 0
