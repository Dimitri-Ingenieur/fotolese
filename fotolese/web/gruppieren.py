"""fotolese.web.gruppieren – Ordner zusammenfassen, Fotos in eine neue Gruppe verschieben, das Archiv neu
gruppieren – mit Rückgängig.

fotosort.py rechnet (MODUS=analyse: mit welchen Ähnlichkeitswerten wären diese Ordner automatisch zusammengekommen,
MODUS=gruppen: Plan für das ganze Archiv), bestof führt aus. Verschoben wird je Aufnahme alles, was dazugehört:
JPG/PNG, NEF, Begleitdateien (.xmp, .pp3, .aae) und die verbesserten Fassungen im Unterordner „verbessert“. Gibt es
den Namen im Ziel schon, bekommt die Aufnahme einen Laufindex (IMG_0001_1.JPG, ihre Fassungen
IMG_0001_1_<Workflow>.png). Sterne (BestOf), Alben, von Hand gesetzte Jahre, Gesichter und Prüfsummen im Index
wandern mit, leere Ordner verschwinden. Jeder Umzug steht in SORTIERT/.bestof-umzug/umzug-<Zeit>.json;
„Rückgängig“ stellt den letzten wieder her.
"""
import json
import os
import re
import secrets
import signal
import threading
import time
import traceback

from fotolese.gemein import ordner_folge
from fotolese.web.konst import BILD_EXT, MAX_ORDNER, ORDNER_MUSTER, VERBESSERT
from fotolese.web.konfig import bilder_text, name_aus_id, natuerlich, url_id
from fotolese.web.importieren import fotosort_lauf, gruppen_umgebung

UMZUG = ".bestof-umzug"  # Unterordner von SORTIERT: Protokolle und Pläne
FOTO_EXT = {".jpg", ".jpeg", ".png", ".nef"}
BEGLEIT_EXT = {".xmp", ".pp3", ".aae"}
SAMMEL = "0000"
ARTEN = {"zusammenfassen": "Zusammenfassen", "gruppieren": "Neu gruppieren", "umzug_rueck": "Umzug rückgängig",
         "verschieben": "Fotos verschieben"}
MAX_RECHNUNGEN = 20
GRENZEN = {"SCHWELLE": (0, 128, int), "SERIE_SEK": (0.0, 86400.0, float), "SERIE_SCHWELLE": (0, 128, int)}


class UmzugFehler(Exception):
    """Fehler mit einem Text für die Oberfläche."""


def stamm_von(name):
    """Namensstamm, zu dem eine Datei gehört: IMG_1.JPG, IMG_1.NEF, IMG_1.xmp, IMG_1.NEF.xmp und ._IMG_1.JPG gehören
    zu IMG_1. Rückgabe: (Vorsatz „._“ oder „“, Stamm, Rest) mit Vorsatz + Stamm + Rest = name."""
    vorsatz = "._" if name.startswith("._") else ""
    kern = name[len(vorsatz):]
    stamm, endung = os.path.splitext(kern)
    if endung.lower() in BEGLEIT_EXT:
        s2, e2 = os.path.splitext(stamm)
        if e2.lower() in FOTO_EXT:
            stamm = s2
    return vorsatz, stamm, kern[len(stamm):]


def index_id(rel):
    """„0005/IMG_1.JPG“ oder „0005/verbessert/x.png“ -> Pfad im Index; None für Dateien, die bestof nicht zeigt."""
    ordner, _, name = rel.partition("/")
    datei = name[len(VERBESSERT) + 1:] if name.startswith(VERBESSERT + "/") else name
    if "/" in datei or datei.startswith(".") or os.path.splitext(datei)[1].lower() not in BILD_EXT:
        return None
    return f"{ordner}/{url_id(name)}"


class Einheit:
    """Eine Aufnahme: Dateien direkt im Ordner und ihre verbesserten Fassungen."""
    __slots__ = ("stamm", "dateien", "fassungen", "bild")

    def __init__(self, stamm):
        self.stamm, self.dateien, self.fassungen, self.bild = stamm, [], [], False


class Stand:
    """Inhalt eines Ordners, nach Aufnahmen gebündelt, und welche Namen belegt sind (ohne Groß/Klein) – wird bei
    jedem Umzug nachgeführt, damit neue Namen auch nach vorigen Umzügen desselben Laufs frei sind."""

    def __init__(self, archiv, ordner):
        self.ordner, self.pfad = ordner, os.path.join(archiv, ordner)
        self.da = os.path.isdir(self.pfad)
        self.namen, self.staemme, self.bild_staemme, self.fassungen = set(), set(), set(), set()
        self.einheiten, self.lose, self.lose_fassungen, self.unterordner = {}, [], [], []
        fassungen = []
        try:
            eintraege = sorted(os.scandir(self.pfad), key=lambda e: e.name)
        except OSError:
            eintraege = []
        for e in eintraege:
            try:
                ist_ordner = e.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if ist_ordner:
                if e.name == VERBESSERT:
                    fassungen = self._fassungen_lesen(e.path)
                else:
                    self.unterordner.append(e.name)
                continue
            self.namen.add(e.name.casefold())
            vorsatz, stamm, _ = stamm_von(e.name)
            if (e.name.startswith(".") and not vorsatz) or not stamm:
                self.lose.append(e.name)  # z. B. .DS_Store
                continue
            schluessel = stamm.casefold()
            self.staemme.add(schluessel)
            einheit = self.einheiten.setdefault(schluessel, Einheit(stamm))
            einheit.dateien.append(e.name)
            if not vorsatz and os.path.splitext(e.name)[1].lower() in BILD_EXT:
                self.bild_staemme.add(schluessel)
                if not einheit.bild:
                    einheit.stamm, einheit.bild = stamm, True
        laengste = sorted(self.bild_staemme, key=len, reverse=True)
        for v in fassungen:  # Zuordnung wie in archiv._einreihen: längster Namensstamm vor einem „_“
            self.fassungen.add(v.casefold())
            if v.startswith("."):
                continue  # z. B. eine Fassung, die gerade gespeichert wird
            vs = os.path.splitext(v)[0].casefold()
            original = next((s for s in laengste if vs.startswith(s + "_")), None)
            if original:
                self.einheiten[original].fassungen.append(v)
            else:
                self.lose_fassungen.append(v)

    @staticmethod
    def _fassungen_lesen(pfad):
        try:
            return sorted(e.name for e in os.scandir(pfad) if not e.is_dir(follow_symlinks=False))
        except OSError:
            return []

    def bilder(self):
        """Zahl der Bilder, die bestof zeigt (JPG/PNG direkt im Ordner und Fassungen)."""
        return sum(1 for e in self.einheiten.values() for n in e.dateien
                   if not n.startswith(".") and os.path.splitext(n)[1].lower() in BILD_EXT) + \
            sum(len(e.fassungen) for e in self.einheiten.values()) + len(self.lose_fassungen)


def _neue_namen(einheit, stamm):
    """[(alt, neu)] für die Dateien und die Fassungen einer Aufnahme mit neuem Namensstamm."""
    if stamm == einheit.stamm:
        return [(n, n) for n in einheit.dateien], [(v, v) for v in einheit.fassungen]
    dateien = []
    for n in einheit.dateien:
        vorsatz, _, rest = stamm_von(n)
        dateien.append((n, vorsatz + stamm + rest))
    k, alt = len(einheit.stamm), einheit.stamm.casefold()
    fassungen = [(v, stamm + v[k:] if v[:k].casefold() == alt else v) for v in einheit.fassungen]
    return dateien, fassungen


def _frei(ziel, einheit, stamm):
    """Namen im Ziel für die Aufnahme mit diesem Stamm, oder None, wenn etwas kollidiert – auch wenn eine Fassung
    danach einem anderen Original zugeordnet würde oder eine verwaiste Fassung im Ziel dieser Aufnahme."""
    sc = stamm.casefold()
    if sc in ziel.staemme or any(f.startswith(sc + "_") for f in ziel.fassungen):
        return None
    dateien, fassungen = _neue_namen(einheit, stamm)
    if any(neu.casefold() in ziel.namen for _, neu in dateien) or \
            any(neu.casefold() in ziel.fassungen for _, neu in fassungen):
        return None
    for _, neu in fassungen:
        vs = os.path.splitext(neu)[0].casefold()
        if any(len(s) > len(sc) and vs.startswith(s + "_") for s in ziel.bild_staemme):
            return None
    return dateien, fassungen


def _umbenennen(schritte):
    """Dateien verschieben, nie überschreiben; geht etwas schief, alles zurück. schritte: [(von, nach)]."""
    erledigt = []
    try:
        for von, nach in schritte:
            if os.path.lexists(nach):
                raise FileExistsError(17, "Datei existiert schon", nach)
            os.makedirs(os.path.dirname(nach), exist_ok=True)
            os.rename(von, nach)
            erledigt.append((von, nach))
    except OSError:
        for von, nach in reversed(erledigt):
            try:
                os.rename(nach, von)
            except OSError:
                pass
        raise


def einheit_bewegen(quelle, ziel, einheit, umbenennen=True):
    """Alle Dateien einer Aufnahme von quelle nach ziel (Stand-Objekte). Ohne umbenennen nur unter dem eigenen
    Namen. Rückgabe: ([(alt_rel, neu_rel)], umbenannt?) oder None, wenn kein Name frei ist. OSError: nichts bewegt."""
    for n in range(0, 10000 if umbenennen else 1):
        stamm = einheit.stamm if n == 0 else f"{einheit.stamm}_{n}"
        namen = _frei(ziel, einheit, stamm)
        if namen:
            break
    else:
        return None
    dateien, fassungen = namen
    schritte = [(os.path.join(quelle.pfad, a), os.path.join(ziel.pfad, b), f"{quelle.ordner}/{a}",
                 f"{ziel.ordner}/{b}") for a, b in dateien]
    schritte += [(os.path.join(quelle.pfad, VERBESSERT, a), os.path.join(ziel.pfad, VERBESSERT, b),
                  f"{quelle.ordner}/{VERBESSERT}/{a}", f"{ziel.ordner}/{VERBESSERT}/{b}") for a, b in fassungen]
    _umbenennen([(s[0], s[1]) for s in schritte])
    alt = einheit.stamm.casefold()
    for a, b in dateien:
        quelle.namen.discard(a.casefold())
        ziel.namen.add(b.casefold())
    for a, b in fassungen:
        quelle.fassungen.discard(a.casefold())
        ziel.fassungen.add(b.casefold())
    quelle.staemme.discard(alt)
    quelle.bild_staemme.discard(alt)
    quelle.einheiten.pop(alt, None)
    ziel.staemme.add(stamm.casefold())
    if einheit.bild:
        ziel.bild_staemme.add(stamm.casefold())
    ziel.da = True
    return [(s[2], s[3]) for s in schritte], stamm != einheit.stamm


def lose_bewegen(quelle, ziel):
    """Beim Zusammenfassen auch den Rest: versteckte Dateien (nur, wenn der Name frei ist) und Fassungen ohne
    Original (mit Laufindex, aber nicht, wenn sie im Ziel einem Original zugeordnet würden).
    Rückgabe: ([(alt_rel, neu_rel)], Zahl der Dateien, die bleiben)."""
    paare, bleibt = [], 0
    for n in list(quelle.lose):
        if n.casefold() in ziel.namen:
            bleibt += 1
            continue
        try:
            _umbenennen([(os.path.join(quelle.pfad, n), os.path.join(ziel.pfad, n))])
        except OSError:
            bleibt += 1
            continue
        quelle.lose.remove(n)
        quelle.namen.discard(n.casefold())
        ziel.namen.add(n.casefold())
        paare.append((f"{quelle.ordner}/{n}", f"{ziel.ordner}/{n}"))
    for v in list(quelle.lose_fassungen):
        stamm, endung = os.path.splitext(v)
        if any(stamm.casefold().startswith(s + "_") for s in ziel.bild_staemme):
            bleibt += 1
            continue
        neu = next((f"{stamm}{f'_{k}' if k else ''}{endung}" for k in range(10000)
                    if f"{stamm}{f'_{k}' if k else ''}{endung}".casefold() not in ziel.fassungen), None)
        try:
            if neu is None:
                raise FileExistsError(v)
            _umbenennen([(os.path.join(quelle.pfad, VERBESSERT, v), os.path.join(ziel.pfad, VERBESSERT, neu))])
        except OSError:
            bleibt += 1
            continue
        quelle.lose_fassungen.remove(v)
        quelle.fassungen.discard(v.casefold())
        ziel.fassungen.add(neu.casefold())
        paare.append((f"{quelle.ordner}/{VERBESSERT}/{v}", f"{ziel.ordner}/{VERBESSERT}/{neu}"))
    return paare, bleibt + len(quelle.unterordner)


def index_umziehen(app, paare):
    """Index nachführen: paare = [(alter Pfad, neuer Pfad)] wie im Index („0005/IMG_1.JPG“). Am neuen Pfad lag keine
    Datei – was der Index dort noch kennt, ist veraltet und fällt weg (Gesichter samt Personensummen)."""
    if not app.index or not paare:
        return
    with app.index.lock:
        db = app.index.db
        for alt, neu in paare:
            if alt == neu:
                continue
            veraltet = db.execute("SELECT id, person, emb FROM gesicht WHERE pfad=?", (neu,)).fetchall()
            if veraltet and app.indexer:
                app.indexer._personen_abziehen(db, veraltet)
            for tabelle in ("gesicht", "bild", "jahr_manuell", "album_bild", "pruefsumme"):
                db.execute(f"DELETE FROM {tabelle} WHERE pfad=?", (neu,))
            ordner, uid = neu.split("/", 1)
            db.execute("UPDATE bild SET pfad=?, ordner=?, datei=? WHERE pfad=?", (neu, ordner, uid, alt))
            db.execute("UPDATE gesicht SET pfad=?, ordner=? WHERE pfad=?", (neu, ordner, alt))
            for tabelle in ("jahr_manuell", "album_bild", "pruefsumme"):
                db.execute(f"UPDATE {tabelle} SET pfad=? WHERE pfad=?", (neu, alt))
        db.commit()


def _stern_name(rel):
    """„0005/verbessert/x.png“ -> („0005“, „verbessert/x.png“) – so heißen die Bilder in der Auswahl."""
    ordner, _, name = rel.partition("/")
    return ordner, name


def umzug_ordner(app):
    return os.path.join(app.archiv.pfad, UMZUG)


def letzter_umzug(app):
    """(Pfad, Protokoll) des neuesten Umzugs oder (None, None)."""
    try:
        namen = sorted((n for n in os.listdir(umzug_ordner(app)) if re.fullmatch(r"umzug-\d{8}-\d{6}-\d{3}\.json", n)),
                       reverse=True)
    except OSError:
        return None, None
    for n in namen:
        pfad = os.path.join(umzug_ordner(app), n)
        try:
            with open(pfad, encoding="utf-8") as f:
                return pfad, json.load(f)
        except (OSError, ValueError):
            continue
    return None, None


def _entfernt_text(prot):
    n = len(prot["entfernt"])
    return "" if not n else (", 1 leerer Ordner entfernt" if n == 1 else f", {n} leere Ordner entfernt")


def _leer_entfernen(ordner):
    """Leeren Unterordner „verbessert“ und dann den Ordner selbst entfernen, wenn nichts mehr darin liegt.
    Rückgabe: Ordner entfernt?"""
    for pfad in (os.path.join(ordner, VERBESSERT), ordner):
        try:
            os.rmdir(pfad)  # nur, wenn leer
        except OSError:
            if pfad == ordner:
                return False
    return True


def _schreiben(pfad, daten):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=0)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pfad)


class Umzug(threading.Thread):
    """Exklusiver Auftrag wie der Import (app.auftrag): Ordner zusammenfassen, Fotos verschieben, einen Plan von
    fotosort ausführen oder den letzten Umzug zurücknehmen."""

    def __init__(self, app, art, ordner=None, ziel=None, plan=None, auswahl=None):
        super().__init__(daemon=True)
        self.app, self.art, self.ordner, self.ziel, self.plan = app, art, ordner, ziel, plan
        self.auswahl = auswahl or []  # Fotos verschieben: [(Ordner, Name wie in bestof)]
        self.abbruch, self.proc = False, None
        self.status = {"art": art, "ziel": None, "laeuft": True, "phase": "Start", "fertig": 0, "gesamt": 0,
                       "zusatz": "", "log": [], "ergebnis": "", "fehler": "", "protokoll": None, "start": time.time(),
                       "ende": None, "album": None, "album_n": 0, "ordner": ordner, "zielordner": ziel,
                       "umzug": None, "bewegt": 0, "entfernt": []}

    def abbrechen(self):
        self.abbruch = True

    def run(self):
        app, st = self.app, self.status
        try:
            with app.umzug_sperre:
                if self.art == "zusammenfassen":
                    self._zusammenfassen()
                elif self.art == "verschieben":
                    self._verschieben()
                elif self.art == "gruppieren":
                    self._plan_ausfuehren()
                else:
                    self._zuruecknehmen()
        except UmzugFehler as fehler:
            st["fehler"] = str(fehler)
        except Exception as fehler:
            traceback.print_exc()
            st["fehler"] = f"{type(fehler).__name__}: {fehler}"
        finally:
            st.update(laeuft=False, ende=time.time(), phase="Fehler" if st["fehler"] else "Fertig")
            app.archiv.ordner(frisch=True)
            if app.indexer:
                app.indexer.weiter.set()
            print(f"{ARTEN[self.art]}: {st['fehler'] or st['ergebnis']}", flush=True)

    # -- Ausführen
    def _umziehen(self, liste, staende, lose=()):
        """liste: [(Quelle, Schlüssel der Aufnahme, Ziel)] als Stand-Objekte; lose: Quellordner, deren Rest
        (versteckte Dateien, verwaiste Fassungen) mitkommt. Zwei Runden: erst unter dem eigenen Namen, dann der
        Rest mit Laufindex – Namen, die im Ziel erst durch einen Wegzug frei werden, bleiben so meist erhalten."""
        app, st = self.app, self.status
        betroffen = sorted(staende, key=ordner_folge)
        zeit = time.strftime("%Y%m%d-%H%M%S")
        for k in range(1000):  # feste Breite: der Name sortiert zeitlich, auch mehrere Umzüge je Sekunde
            stempel = f"{zeit}-{k:03d}"
            pfad = os.path.join(umzug_ordner(app), f"umzug-{stempel}.json")
            if not os.path.exists(pfad):
                break
        prot = {"version": 1, "art": self.art, "zeit": stempel, "ordner": self.ordner, "ziel": self.ziel,
                "sterne_vorher": {o: app.auswahl.markiert(o) for o in betroffen if app.auswahl.markiert(o)},
                "neue_ordner": [o for o in betroffen if not staende[o].da], "entfernt": [], "umzuege": [],
                "fertig": False, "rueckgaengig": None, "text": ""}
        st.update(phase="Verschieben", fertig=0, gesamt=len(liste), umzug=pfad)
        _schreiben(pfad, prot)
        index_paare, stern_paare, fehler, umbenannt, einheiten = [], [], [], 0, 0

        def merken(paare):
            prot["umzuege"] += [list(p) for p in paare]
            for a, b in paare:
                ia, ib = index_id(a), index_id(b)
                if ia and ib:
                    index_paare.append((ia, ib))
                    stern_paare.append((*_stern_name(a), *_stern_name(b)))
            if len(index_paare) >= 200:
                index_umziehen(app, index_paare)
                index_paare.clear()
                _schreiben(pfad, prot)

        offen = liste
        for runde in (0, 1):
            rest = []
            for quelle, schluessel, ziel in offen:
                if self.abbruch:
                    break
                einheit = quelle.einheiten.get(schluessel)
                if einheit is None:
                    continue
                try:
                    erg = einheit_bewegen(quelle, ziel, einheit, umbenennen=runde == 1)
                except OSError as f:
                    fehler.append(f"{quelle.ordner}/{einheit.stamm}: {f.strerror or f}")
                    st["fertig"] += 1
                    continue
                if erg is None:
                    if runde == 0:
                        rest.append((quelle, schluessel, ziel))
                    else:
                        fehler.append(f"{quelle.ordner}/{einheit.stamm}: kein freier Name in {ziel.ordner}")
                    continue
                paare, neu_benannt = erg
                umbenannt += neu_benannt
                einheiten += 1
                st["fertig"] += 1
                st["bewegt"] = einheiten
                merken(paare)
            offen = rest
        bleibt = 0
        if not self.abbruch:
            for o in lose:
                paare, n = lose_bewegen(staende[o], staende[self.ziel])
                bleibt += n
                merken(paare)
        index_umziehen(app, index_paare)
        st["phase"] = "Sterne und Ordner"
        weg = app.auswahl.umziehen(stern_paare) if stern_paare else 0
        for o in betroffen:
            if _leer_entfernen(os.path.join(app.archiv.pfad, o)):
                prot["entfernt"].append(o)
        bilder = sum(1 for a, _ in prot["umzuege"] if index_id(a))
        prot.update(fertig=True, bilder=bilder, umbenannt=umbenannt, sterne_weg=weg, fehler=fehler[:50],
                    abgebrochen=self.abbruch)
        return prot, pfad, bleibt

    def _abschluss(self, prot, pfad, text):
        prot["text"] = text
        self.status["entfernt"] = list(prot["entfernt"])
        _schreiben(pfad, prot)
        if prot["umzuege"]:
            self.status["ergebnis"] = text
        else:  # nichts bewegt: kein Protokoll, das man zurücknehmen könnte
            os.unlink(pfad)
            self.status.update(ergebnis=text, umzug=None)

    def _zusatz(self, prot):
        teile = []
        if prot["umbenannt"]:
            teile.append(f"{prot['umbenannt']} mit Laufindex umbenannt (gleicher Name im Ziel)")
        if prot["sterne_weg"]:
            teile.append(f"{prot['sterne_weg']} Stern{'' if prot['sterne_weg'] == 1 else 'e'} entfallen "
                         f"(höchstens {self.app.auswahl.max_best} je Ordner)")
        if prot["fehler"]:
            teile.append(f"{len(prot['fehler'])} nicht verschoben: {prot['fehler'][0]}")
        if prot["abgebrochen"]:
            teile.append("abgebrochen – Rückgängig nimmt das Verschobene zurück")
        return (" " + "; ".join(teile) + ".") if teile else ""

    def _zusammenfassen(self):
        app = self.app
        quellen = [o for o in self.ordner if o != self.ziel]
        staende = {o: Stand(app.archiv.pfad, o) for o in [self.ziel] + quellen}
        liste = [(staende[o], k, staende[self.ziel]) for o in quellen
                 for k in sorted(staende[o].einheiten, key=lambda k: natuerlich(staende[o].einheiten[k].stamm))]
        prot, pfad, bleibt = self._umziehen(liste, staende, lose=quellen)
        text = (f"{len(quellen) + 1} Ordner zu {self.ziel} zusammengefasst: {bilder_text(prot['bilder'])} verschoben"
                + _entfernt_text(prot) + "." + self._zusatz(prot)
                + (f" {bleibt} Dateien oder Unterordner blieben, wo sie waren." if bleibt else ""))
        self._abschluss(prot, pfad, text)

    def _verschieben(self):
        """Ausgewählte Fotos – je Aufnahme mit allem, was dazugehört – in eine neue Gruppe (nächste freie Nummer)
        oder einen vorhandenen Ordner. Eine gewählte Fassung nimmt ihr Original und dessen Fassungen mit."""
        app = self.app
        neu = self.ziel is None
        if neu:
            hoch = max([int(o) for o in app.archiv.ordner(frisch=True)] + [0])
            if hoch >= MAX_ORDNER:
                raise UmzugFehler("Es ist keine Ordnernummer mehr frei.")
            self.ziel = f"{hoch + 1:04d}"
        self.status["zielordner"] = self.ziel
        staende, liste, gesehen, fehlt = {}, [], set(), 0

        def stand(o):
            if o not in staende:
                staende[o] = Stand(app.archiv.pfad, o)
            return staende[o]

        for o, name in self.auswahl:
            if o == self.ziel:
                continue
            quelle = stand(o)
            if name.startswith(VERBESSERT + "/"):
                v = name.split("/", 1)[1]
                schluessel = next((k for k, e in quelle.einheiten.items() if v in e.fassungen), None)
            else:
                schluessel = stamm_von(name)[1].casefold() if name.casefold() in quelle.namen else None
            if schluessel is None or schluessel not in quelle.einheiten:
                fehlt += 1  # inzwischen weg oder eine Fassung ohne Original
                continue
            if (o, schluessel) not in gesehen:
                gesehen.add((o, schluessel))
                liste.append((quelle, schluessel, stand(self.ziel)))
        if not liste:
            raise UmzugFehler("Diese Fotos gibt es dort nicht mehr – bitte die Seite neu laden.")
        prot, pfad, _ = self._umziehen(liste, staende)
        n = self.status["bewegt"]
        f = sum(1 for a, _ in prot["umzuege"] if f"/{VERBESSERT}/" in a and index_id(a))
        was = ("1 Foto" if n == 1 else f"{n} Fotos") + (
            f" (mit {f} verbesserten Fassung{'' if f == 1 else 'en'})" if f else "")
        text = ((f"{was} in die neue Gruppe {self.ziel} verschoben" if neu else f"{was} nach {self.ziel} verschoben")
                + _entfernt_text(prot) + "." + self._zusatz(prot)
                + (f" {fehlt} gab es nicht mehr." if fehlt else ""))
        self._abschluss(prot, pfad, text)

    def _plan_ausfuehren(self):
        app, st = self.app, self.status
        try:
            with open(self.plan, encoding="utf-8") as f:
                plan = json.load(f)
        except (OSError, ValueError) as fehler:
            raise UmzugFehler(f"Plan nicht lesbar ({fehler}). Bitte die Vorschau neu berechnen.") from None
        if plan.get("version") != 1 or os.path.realpath(str(plan.get("ausgabe", ""))) != \
                os.path.realpath(app.archiv.pfad):
            raise UmzugFehler("Der Plan gehört nicht zu diesem Archiv. Bitte die Vorschau neu berechnen.")
        vorhanden = set(app.archiv.ordner(frisch=True))
        neue = [o for o in plan.get("neue_ordner", []) if ORDNER_MUSTER.fullmatch(str(o))]
        abbild = {}
        if any(o in vorhanden for o in neue):  # inzwischen angelegt (z. B. Import): neue Nummern dahinter
            hoch = max([int(o) for o in vorhanden] + [0])
            abbild = {o: f"{hoch + 1 + k:04d}" for k, o in enumerate(neue)}
            if neue and hoch + len(neue) > MAX_ORDNER:
                raise UmzugFehler("Für die neuen Gruppen sind keine Ordnernummern mehr frei.")
        staende, liste, gesehen, fehlt, widerspruch = {}, [], {}, 0, 0

        def stand(o):
            if o not in staende:
                staende[o] = Stand(app.archiv.pfad, o)
            return staende[o]

        st.update(phase="Plan prüfen")
        for eintrag in plan.get("umzuege", []):
            try:
                rel, ziel = str(eintrag[0]), str(eintrag[1])
            except (TypeError, IndexError):
                continue
            o, _, name = rel.partition("/")
            ziel = abbild.get(ziel, ziel)
            if not (ORDNER_MUSTER.fullmatch(o) and ORDNER_MUSTER.fullmatch(ziel) and name and "/" not in name
                    and o != ziel and o in vorhanden):
                fehlt += 1
                continue
            quelle = stand(o)
            schluessel = stamm_von(name)[1].casefold()
            if name.casefold() not in quelle.namen or schluessel not in quelle.einheiten:
                fehlt += 1  # inzwischen weg (Papierkorb, anderer Umzug)
                continue
            if (o, schluessel) in gesehen:
                widerspruch += gesehen[(o, schluessel)] != ziel
                continue
            gesehen[(o, schluessel)] = ziel
            liste.append((quelle, schluessel, stand(ziel)))
        prot, pfad, _ = self._umziehen(liste, staende)
        prot["parameter"] = plan.get("parameter")
        neu = [o for o in prot["neue_ordner"] if staende[o].da]
        p = plan.get("parameter") or {}
        text = (f"Neu gruppiert (SCHWELLE {p.get('SCHWELLE')}, SERIE_SEK {p.get('SERIE_SEK')}, SERIE_SCHWELLE "
                f"{p.get('SERIE_SCHWELLE')}): {bilder_text(prot['bilder'])} verschoben"
                + ((", 1 neuer Ordner" if len(neu) == 1 else f", {len(neu)} neue Ordner") if neu else "")
                + _entfernt_text(prot) + "."
                + self._zusatz(prot)
                + (f" {fehlt} Bilder aus dem Plan gibt es nicht mehr." if fehlt else "")
                + (f" {widerspruch} widersprüchliche Einträge übersprungen." if widerspruch else ""))
        self._abschluss(prot, pfad, text)

    def _zuruecknehmen(self):
        app, st = self.app, self.status
        pfad, prot = letzter_umzug(app)
        if not prot or prot.get("rueckgaengig"):
            raise UmzugFehler("Es gibt keinen Umzug, der sich zurücknehmen lässt.")
        umzuege = prot.get("umzuege") or []
        st.update(phase="Zurücklegen", fertig=0, gesamt=len(umzuege), umzug=pfad)
        index_paare, fehlt, zurueck = [], 0, 0
        betroffen = set(prot.get("sterne_vorher") or {})
        for alt, neu in reversed(umzuege):
            von, nach = os.path.join(app.archiv.pfad, neu), os.path.join(app.archiv.pfad, alt)
            betroffen |= {alt.split("/", 1)[0], neu.split("/", 1)[0]}
            try:
                if not os.path.lexists(von) or os.path.lexists(nach):
                    raise FileNotFoundError(von)
                _umbenennen([(von, nach)])
            except OSError:
                fehlt += 1
                continue
            zurueck += 1
            st["fertig"] = zurueck
            ia, ib = index_id(neu), index_id(alt)
            if ia and ib:
                index_paare.append((ia, ib))
            if len(index_paare) >= 200:
                index_umziehen(app, index_paare)
                index_paare.clear()
        index_umziehen(app, index_paare)
        st["phase"] = "Sterne und Ordner"
        vorher = prot.get("sterne_vorher") or {}
        app.auswahl.setzen({o: vorher.get(o, []) for o in betroffen})
        for o in sorted(betroffen, key=ordner_folge):
            _leer_entfernen(os.path.join(app.archiv.pfad, o))
        prot["rueckgaengig"] = time.strftime("%Y%m%d-%H%M%S")
        _schreiben(pfad, prot)
        st["ergebnis"] = (f"Rückgängig: {zurueck} {'Datei' if zurueck == 1 else 'Dateien'} zurückgelegt, Sterne wie vorher."
                          + (f" {fehlt} ließen sich nicht zurücklegen (inzwischen verschoben, umbenannt oder "
                             "der alte Name ist wieder belegt)." if fehlt else ""))


class Rechnung(threading.Thread):
    """fotosort rechnet, ohne etwas zu verschieben: MODUS=analyse (Werte für eine Auswahl) oder MODUS=gruppen (Plan
    für das ganze Archiv). Läuft neben anderem; das Ergebnis holt die Seite über die ID."""

    def __init__(self, app, art, ordner=None, werte=None):
        super().__init__(daemon=True)
        self.app, self.art, self.ordner, self.werte = app, art, ordner or [], werte or {}
        self.id = secrets.token_urlsafe(9)
        self.proc, self.plan = None, None
        self.status = {"id": self.id, "art": art, "laeuft": True, "phase": "Start", "fertig": 0, "gesamt": 0,
                       "zusatz": "", "fehler": "", "ergebnis": None, "text": [], "ordner": self.ordner,
                       "werte": dict(app.gruppe, **self.werte), "start": time.time()}

    def run(self):
        app, st = self.app, self.status
        erg = {}
        try:
            umgebung = {"MODUS": "analyse" if self.art == "analyse" else "gruppen", "JOBS": str(app.import_jobs),
                        **gruppen_umgebung(app, self.werte)}
            if self.art == "plan":
                os.makedirs(umzug_ordner(app), exist_ok=True)
                self.plan = os.path.join(umzug_ordner(app), f"plan-{time.strftime('%Y%m%d-%H%M%S')}-{self.id}.json")
                umgebung["PLAN"] = self.plan
                _alte_plaene(app)

            def text_zeile(z):
                if z.strip():
                    st["text"] = (st["text"] + [z])[-60:]

            code = fotosort_lauf(app, [app.archiv.pfad, *self.ordner], umgebung, st, self, text_zeile, erg.update)
            if code:
                st["fehler"] = ("Abgebrochen." if code < 0 or code == 130 else
                                (st["text"][-1] if st["text"] else f"fotosort meldet Fehler {code}."))
            elif self.art == "analyse":
                st["ergebnis"] = erg.get("analyse")
            else:
                with open(self.plan, encoding="utf-8") as f:
                    plan = json.load(f)
                plan.pop("umzuege", None)
                st["ergebnis"] = plan
            if not code and not st["ergebnis"]:
                st["fehler"] = "fotosort lieferte kein Ergebnis."
        except Exception as fehler:
            traceback.print_exc()
            st["fehler"] = f"{type(fehler).__name__}: {fehler}"
        finally:
            st.update(laeuft=False, phase="Fehler" if st["fehler"] else "Fertig")

    def abbrechen(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)


def _alte_plaene(app, behalten=5):
    try:
        plaene = sorted(n for n in os.listdir(umzug_ordner(app)) if n.startswith("plan-") and n.endswith(".json"))
    except OSError:
        return
    for n in plaene[:-behalten] if len(plaene) > behalten else []:
        try:
            os.unlink(os.path.join(umzug_ordner(app), n))
        except OSError:
            pass


def _werte_pruefen(roh):
    """Ähnlichkeitswerte aus einer Anfrage (Vorschau mit noch nicht gespeicherten Werten)."""
    werte = {}
    for name, (unten, oben, typ) in GRENZEN.items():
        if roh.get(name) in (None, ""):
            continue
        try:
            wert = typ(str(roh[name]).replace(",", "."))
        except ValueError:
            raise UmzugFehler(f"{name}: ungültiger Wert.") from None
        if not unten <= wert <= oben:
            raise UmzugFehler(f"{name}: erlaubt sind {unten:g} bis {oben:g}.")
        werte[name] = wert
    if roh.get("EINZELN") not in (None, ""):
        if roh["EINZELN"] not in ("ordner", SAMMEL):
            raise UmzugFehler("EINZELN: ordner oder 0000.")
        werte["EINZELN"] = roh["EINZELN"]
    return werte


def _ordner_pruefen(app, roh, mindest=2):
    if not isinstance(roh, list) or not mindest <= len(roh) <= 500:
        raise UmzugFehler(f"Bitte mindestens {mindest} Ordner wählen.")
    vorhanden = set(app.archiv.ordner(frisch=True))
    ordner = sorted({str(o) for o in roh}, key=ordner_folge)  # ordner[0] = kleinste Nummer, vorgewähltes Ziel
    for o in ordner:
        if not ORDNER_MUSTER.fullmatch(o) or o not in vorhanden:
            raise UmzugFehler(f"Ordner {o} gibt es nicht. Seite neu laden.")
        if o == SAMMEL:
            raise UmzugFehler("Den Sammelordner 0000 bitte nicht zusammenfassen – er gehört den Einzelbildern.")
    if len(ordner) < mindest:
        raise UmzugFehler(f"Bitte mindestens {mindest} Ordner wählen.")
    return ordner


def _pfade_pruefen(app, roh):
    """[„0008/<id>“, …] aus einer Anfrage -> [(Ordner, Name)] – nur Bilder, die bestof dort wirklich zeigt."""
    if not isinstance(roh, list) or not 1 <= len(roh) <= 5000:
        raise UmzugFehler("Bitte mindestens ein Foto wählen.")
    vorhanden, auswahl = set(app.archiv.ordner(frisch=True)), []
    for p in roh:
        o, _, uid = str(p).partition("/")
        name = name_aus_id(uid)
        if not (ORDNER_MUSTER.fullmatch(o) and o in vorhanden and uid and url_id(name) == uid
                and app.archiv.datei(o, name)):
            raise UmzugFehler("Ein Foto gibt es nicht mehr – bitte die Seite neu laden.")
        auswahl.append((o, name))
    return list(dict.fromkeys(auswahl))


def vorschau(app, ordner, ziel):
    """Vor dem Zusammenfassen: Bilder und Sterne je Ordner, wie viele Aufnahmen einen Laufindex bekämen und wie
    viele Sterne über MAX_BEST hinaus wegfielen. Liest nur."""
    staende = {o: Stand(app.archiv.pfad, o) for o in ordner}
    z = staende[ziel]
    belegt = Stand(app.archiv.pfad, ziel)  # Kopie zum Durchspielen
    umbenannt = 0
    for o in ordner:
        if o == ziel:
            continue
        for k, einheit in staende[o].einheiten.items():
            if _frei(belegt, einheit, einheit.stamm) is None:
                umbenannt += 1
            for n in einheit.dateien:  # nur grob nachführen: Stamm belegt
                belegt.namen.add(n.casefold())
            belegt.staemme.add(k)
    sterne = {o: len(app.auswahl.markiert(o)) for o in ordner}
    gesamt = sum(sterne.values())
    return {"ordner": [{"ordner": o, "bilder": staende[o].bilder(), "sterne": sterne[o]} for o in ordner],
            "ziel": ziel, "bilder": sum(s.bilder() for o, s in staende.items() if o != ziel),
            "umbenannt": umbenannt, "sterne": min(gesamt, app.auswahl.max_best),
            "sterne_weg": max(0, gesamt - app.auswahl.max_best), "max_best": app.auswahl.max_best,
            "ziel_bilder": z.bilder()}


def _belegt(app):
    a = app.auftrag
    if a is not None and a.status["laeuft"]:
        return ("Es läuft schon ein Auftrag (" + (ARTEN.get(a.status["art"]) or "Import") +
                ") – bitte warten, bis er fertig ist.")
    if app.verbesserer and app.verbesserer.beschaeftigt():
        return "Gerade wird ein Foto verbessert – bitte warten, bis es fertig ist."
    return None


def gruppieren_api(app, daten):
    """POST /api/gruppieren: aktion = analyse | plan | abbrechen | vorschau | zusammenfassen | ausfuehren |
    rueckgaengig. Rückgabe: (Code, Antwort)."""
    aktion = daten.get("aktion")
    try:
        if aktion in ("analyse", "plan"):
            if not os.path.isfile(app.fotosort):
                return 500, {"fehler": f"fotosort.py fehlt: {app.fotosort}"}
            laufend = [r for r in app.rechnungen.values() if r.status["laeuft"]]
            if len(laufend) >= 2:
                return 409, {"fehler": "Es laufen schon zwei Berechnungen – bitte warten."}
            if aktion == "analyse":
                r = Rechnung(app, "analyse", ordner=_ordner_pruefen(app, daten.get("ordner")))
            else:
                r = Rechnung(app, "plan", werte=_werte_pruefen(daten.get("werte") or {}))
            with app.rechnungen_lock:
                app.rechnungen[r.id] = r
                while len(app.rechnungen) > MAX_RECHNUNGEN:
                    app.rechnungen.popitem(last=False)
            r.start()
            return 200, {"id": r.id}
        if aktion == "abbrechen":
            r = app.rechnungen.get(str(daten.get("id") or ""))
            if r:
                r.abbrechen()
                return 200, {"meldung": "Abbruch angefordert."}
            a = app.auftrag
            if daten.get("id") == "auftrag" and a is not None and a.status["laeuft"] and a.status["art"] in ARTEN:
                a.abbrechen()
                return 200, {"meldung": "Abbruch angefordert – der Umzug hält nach der laufenden Aufnahme an."}
            return 404, {"fehler": "Es läuft nichts."}
        if aktion == "vorschau":
            ordner = _ordner_pruefen(app, daten.get("ordner"))
            ziel = str(daten.get("ziel") or ordner[0])
            if ziel not in ordner:
                return 400, {"fehler": "Das Ziel muss einer der gewählten Ordner sein."}
            return 200, vorschau(app, ordner, ziel)
        if aktion in ("zusammenfassen", "ausfuehren", "rueckgaengig", "verschieben"):
            grund = _belegt(app)
            if grund:
                return 409, {"fehler": grund}
            if aktion == "verschieben":
                auswahl = _pfade_pruefen(app, daten.get("pfade"))
                ziel = str(daten.get("ziel") or "neu")
                if ziel != "neu":
                    if not ORDNER_MUSTER.fullmatch(ziel) or ziel not in app.archiv.ordner(frisch=True):
                        return 404, {"fehler": f"Ordner {ziel} gibt es nicht."}
                    if all(o == ziel for o, _ in auswahl):
                        return 400, {"fehler": f"Die Fotos liegen schon in Ordner {ziel}."}
                app.auftrag = Umzug(app, "verschieben", ordner=sorted({o for o, _ in auswahl}, key=ordner_folge),
                                    ziel=None if ziel == "neu" else ziel, auswahl=auswahl)
            elif aktion == "zusammenfassen":
                ordner = _ordner_pruefen(app, daten.get("ordner"))
                ziel = str(daten.get("ziel") or ordner[0])
                if ziel not in ordner:
                    return 400, {"fehler": "Das Ziel muss einer der gewählten Ordner sein."}
                app.auftrag = Umzug(app, "zusammenfassen", ordner=ordner, ziel=ziel)
            elif aktion == "ausfuehren":
                r = app.rechnungen.get(str(daten.get("id") or ""))
                if not r or r.art != "plan" or r.status["laeuft"] or r.status["fehler"] or not r.plan:
                    return 404, {"fehler": "Keine fertige Vorschau gefunden – bitte neu berechnen."}
                if time.time() - r.status["start"] > 6 * 3600:
                    return 409, {"fehler": "Die Vorschau ist älter als 6 Stunden – bitte neu berechnen."}
                app.auftrag = Umzug(app, "gruppieren", plan=r.plan)
            else:
                pfad, prot = letzter_umzug(app)
                if not prot or prot.get("rueckgaengig"):
                    return 404, {"fehler": "Es gibt keinen Umzug, der sich zurücknehmen lässt."}
                app.auftrag = Umzug(app, "umzug_rueck")
            app.auftrag.start()
            return 200, {"meldung": "Gestartet."}
    except UmzugFehler as fehler:
        return 400, {"fehler": str(fehler)}
    return 400, {"fehler": "Unbekannte Aktion."}


def gruppieren_stand(app, ids):
    """GET /api/gruppieren: Berechnungen (über ihre IDs), der laufende oder letzte exklusive Auftrag – vom Import
    nur Art und Zustand, die Pfade darin sind Sache dieses Rechners – und der letzte Umzug (zurücknehmbar?)."""
    rechnungen = {i: dict(r.status) for i in ids if (r := app.rechnungen.get(i))}
    a = app.auftrag
    auftrag = None
    if a is not None:
        s = a.status
        auftrag = ({k: s.get(k) for k in ("art", "laeuft", "phase", "fertig", "gesamt", "zusatz", "ergebnis", "fehler",
                                          "ordner", "zielordner", "bewegt", "entfernt", "start", "ende")}
                   if s["art"] in ARTEN else {"art": s["art"], "laeuft": s["laeuft"]})
    _, prot = letzter_umzug(app)
    letzter = None
    if prot:
        letzter = {"zeit": prot.get("zeit"), "art": prot.get("art"), "text": prot.get("text"),
                   "rueckgaengig": prot.get("rueckgaengig"), "fertig": prot.get("fertig")}
    return {"rechnungen": rechnungen, "auftrag": auftrag, "letzter": letzter}
