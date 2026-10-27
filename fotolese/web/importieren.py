"""fotolese.web.importieren – Ordner über fotosort ins Archiv kopieren, Duplikate bereinigen, Ordnerwahl.

(Modulname nicht 'import', das ist ein Schlüsselwort.) Auftrag startet fotosort.py als
Unterprozess und liest dessen Fortschritt (#FS-Zeilen).
"""
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from fotolese.gemein import sha256 as _sha256
from fotolese.web.konfig import anzeige, e, groesse_text, natuerlich, url_id
from fotolese.web.html import kopf, seite


FOTO_EXT = {".jpg", ".jpeg", ".png", ".nef"}
OHNE_ORDNER = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found"}


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
