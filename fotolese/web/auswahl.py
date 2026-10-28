"""fotolese.web.auswahl – Sterne (BestOf-Auswahl) je Ordner lesen/schreiben und Kopien in BestOf abgleichen."""
import json
import os
import shutil
import sys
import threading

from fotolese.web.konst import BESTOF_MUSTER, BUCHSTABEN
from fotolese.web.konfig import bilder_text, url_id


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
