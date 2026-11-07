"""fotolese.web.auswahl – Sterne (BestOf-Auswahl) je Ordner lesen/schreiben und Kopien in BestOf abgleichen."""
import json
import os
import shutil
import sys
import threading

from fotolese.web.konst import BESTOF_MUSTER, BUCHSTABEN
from fotolese.web.konfig import anzeige, bilder_text, url_id


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

    def auffrischen(self, ordner, name):
        """Kopie in BestOf erneuern, wenn das Bild einen Stern hat – etwa nachdem es gedreht wurde."""
        with self.lock:
            markiert = self.markiert(ordner)
            if name not in markiert:
                return
            try:
                self._abgleichen(ordner, markiert)
                self._speichern()
            except OSError as fehler:
                print(f"Hinweis: BestOf-Kopie von {ordner}/{anzeige(name)} nicht erneuert ({fehler}).", flush=True)

    def umziehen(self, paare):
        """Sterne mitnehmen, wenn Bilder den Ordner wechseln: paare = [(alter Ordner, alter Name, neuer Ordner,
        neuer Name)]. Im Zielordner kommen sie hinter die vorhandenen Sterne; über MAX_BEST hinaus fallen sie weg.
        Rückgabe: Zahl der weggefallenen Sterne."""
        with self.lock:
            neu = {}
            for alt_o, alt_n, neu_o, neu_n in paare:
                for o in (alt_o, neu_o):
                    if o not in neu:
                        neu[o] = self.markiert(o)
                if alt_n in neu[alt_o]:
                    neu[alt_o].remove(alt_n)
                    neu[neu_o].append(neu_n)
            return self._uebernehmen(neu)

    def setzen(self, stand):
        """Sterne je Ordner auf einen früheren Stand {Ordner: [Namen]} zurücksetzen (Umzug rückgängig)."""
        with self.lock:
            return self._uebernehmen({o: list(namen) for o, namen in stand.items()})

    def _uebernehmen(self, neu):
        weg = 0
        for o, liste in neu.items():
            self.archiv.bilder(o, frisch=True)  # Dateien gerade verschoben: Ordner neu lesen
            if liste == self.markiert(o) and not liste:
                continue
            try:
                weg += len(liste) - len(self._abgleichen(o, liste))
            except OSError:
                pass
        try:
            self._speichern()
        except OSError:
            pass
        return weg

    def umschalten(self, ordner, name):
        with self.lock:
            alt = self.markiert(ordner)
            if name in alt:
                neu = [m for m in alt if m != name]
            elif len(alt) >= self.max_best:
                sterne = "einen Stern" if self.max_best == 1 else f"{self.max_best} Sterne"
                return 409, {"fehler": f"Ordner {ordner} hat schon {sterne}. Nehmen Sie erst einem Bild den Stern."}
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
                return 500, {"fehler": f"Kopieren nach BestOf fehlgeschlagen: {grund}. Sterne unverändert."}
            ziele = self.ziele(ordner, markiert)
            if name in markiert:
                meldung = f"Stern gesetzt – als {ziele[name]} in BestOf kopiert."
            elif markiert:
                meldung = "Stern entfernt. In BestOf: " + ", ".join(ziele[m] for m in markiert) + "."
            else:
                meldung = "Stern entfernt. Aus diesem Ordner liegt nichts mehr in BestOf."
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
