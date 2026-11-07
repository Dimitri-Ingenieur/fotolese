"""fotolese.web.aehnlich – Seite „Ähnliche Fotos“: zu einem Foto die ähnlichsten im Archiv, nach Ähnlichkeit sortiert.

Mit KI (Standard): Der Index kennt je Foto die Merkmale des Bildmodells CLIP (siehe ki); verglichen wird hier sofort
mit allen Fotos, an jedem steht die Ähnlichkeit in Prozent. Ohne KI (KI = 0, kein Index, Modell nicht ladbar) rechnet
fotosort.py (MODUS=aehnlich) mit dem Maß vom Gruppieren – verschiedene Bits von pHash und dHash – und findet nur fast
gleiche Fotos. bestof zeigt das Ergebnis als Kontaktbogen mit allen Knöpfen; „Fotos verschieben …“ schlägt den Ordner
des Ausgangsfotos als Ziel vor.
"""
import os
from urllib.parse import urlencode

from fotolese.gemein import ist_ordner
from fotolese.web.alben import alben_liste
from fotolese.web.html import (ALBBOX, ALBUMLEISTE, JS_ALBEN, JS_BEARBEITEN, JS_BOGEN, JS_VERBESSERN, JS_VERSCHIEBEN,
                               LUPE_HTML, VERSCHIEBEN_HTML, bogen_hilfe, bogen_html, farb_daten, json_im_html, kopf,
                               seite)
from fotolese.web.index import namensliste
from fotolese.web.konfig import bilder_text, e, name_aus_id, url_id
from fotolese.web.konst import MAX_ORDNER

KI_STUFEN = ((0.95, "fast gleich"), (0.88, "sehr ähnlich"), (0.80, "ähnlich"), (-2.0, "entfernt ähnlich"))
KI_NAH = 0.88  # ab hier steht die Ähnlichkeit in Gelb


def ki_stufe(wert):
    """Ähnlichkeit der KI (Kosinus 0–1) in Worten."""
    return next(wort for grenze, wort in KI_STUFEN if wert >= grenze)


def prozent(wert):
    """0,996 -> 99: abgerundet, 100 % nur bei gleichen Merkmalen."""
    return max(0, min(100, int(wert * 100 + 1e-6)))


def stufe(abstand, schwelle):
    """Bildvergleich (ohne KI): Abstand in Worten – „sehr ähnlich“ heißt: beim Import kämen die Fotos in eine Gruppe."""
    if abstand == 0:
        return "gleich"
    if abstand <= 8:
        return "fast gleich"
    if abstand <= schwelle:
        return "sehr ähnlich"
    if abstand <= 36:
        return "ähnlich"
    return "entfernt ähnlich"


def _bezug(app, pfad):
    """„0004/<id>“ -> (Ordner, Name) eines Fotos, das bestof zeigt (auch eine Fassung), sonst None."""
    o, _, uid = str(pfad or "").partition("/")
    name = name_aus_id(uid)
    if ist_ordner(o) and o in app.archiv.ordner() and uid and url_id(name) == uid and app.archiv.datei(o, name):
        return o, name
    return None


def _zustand(app):
    """(„bereit“ | „vorbereitung“ | „aus“, Grund) der KI-Suche."""
    return app.indexer.ki_zustand() if app.indexer else ("aus", "ohne Index (INDEX = 0)")


def _familie(app, o, name):
    """Das Foto und seine Fassungen (verbessert, koloriert, bearbeitet) als Index-Pfade – die zeigt der Ordner."""
    herkunft = app.archiv.herkunft(o)
    original = herkunft.get(name, name)
    return {f"{o}/{url_id(n)}" for n in {original, *(v for v, orig in herkunft.items() if orig == original)}}


def _ki_fehler(app, rel):
    """Warum die KI das Foto nicht lesen konnte – nur solange die Datei seither unverändert ist, sonst None."""
    zeile = app.index.einer("SELECT groesse, mtime, fehler FROM ki WHERE pfad=? AND emb IS NULL", (rel,))
    o, _, uid = rel.partition("/")
    d = app.archiv.datei(o, name_aus_id(uid))
    return (zeile[2] or "nicht lesbar") if zeile and d and (zeile[0], zeile[1]) == (d[1], d[2]) else None


def aehnlich_seite(app, pfad, rid):
    bezug = _bezug(app, pfad)
    titel = '<div class="titel"><h1>Ähnliche Fotos</h1><div><p id="info"></p><p class="ziel" id="ziel"></p></div></div>'
    if not bezug:
        return seite("Ähnliche Fotos – BestOf", kopf(app, "", titel) +
                     '<p class="leer">Dieses Foto gibt es nicht (mehr). Bitte aus einem Ordner neu aufrufen.</p>')
    o, name = bezug
    pfad = f"{o}/{url_id(name)}"
    zustand, grund = _zustand(app)
    if zustand == "aus":
        return _bildvergleich(app, o, name, pfad, rid, titel, grund)
    treffer = None
    if zustand == "bereit":
        treffer = app.indexer.ki.aehnliche(pfad, app.aehnlich_anzahl, app.aehnlich_min / 100, _familie(app, o, name))
    if treffer is None:
        fehler = _ki_fehler(app, pfad) if zustand == "bereit" else None
        if fehler:
            return _ergebnis(app, o, name, pfad, [], {}, "", f"Dieses Foto kann die KI nicht lesen: {fehler}.")
        if zustand == "bereit":
            app.indexer.ki_anfordern(pfad)  # kommt im Index als Nächstes dran
        return _warten(app, o, name, pfad, titel, ki=True)
    eintraege, abzeichen = [], {}
    for rel, wert in treffer:
        to, _, uid = rel.partition("/")
        tname = name_aus_id(uid)
        d = app.archiv.datei(to, tname) if ist_ordner(to) and to in app.archiv.ordner() else None
        if not d:
            continue  # inzwischen verschoben oder im Papierkorb
        p, wort = prozent(wert), ki_stufe(wert)
        eintraege.append((to, tname, d[2], d[1]))
        abzeichen[f"{to}/{url_id(tname)}"] = (f"{p} % · {wort}", f"KI-Ähnlichkeit {p} % (Bildinhalt, CLIP) – {wort}",
                                              "nah" if wert >= KI_NAH else "")
    s = app.indexer.status
    rest = max(0, s["gesamt"] - s["fertig"]) if s["phase"] == "KI" else 0
    verglichen = max(0, len(app.indexer.ki.daten()[0]) - 1)
    zeile = (f'{bilder_text(len(eintraege))} ab {app.aehnlich_min} % Ähnlichkeit, nach Ähnlichkeit sortiert '
             f'(verglichen mit {verglichen} Fotos im Archiv). Die KI (CLIP) vergleicht den Bildinhalt – Motiv, Szene, '
             'Licht, Farben: ab 95 % fast gleich, ab 88 % sehr ähnlich, ab 80 % ähnlich, darunter entfernt ähnlich.'
             + (f' Noch ohne KI-Merkmale: {bilder_text(rest)} – „Neu suchen“ findet später mehr.' if rest else ''))
    leer = "" if eintraege else (f"Keine ähnlichen Fotos im Archiv (ab {app.aehnlich_min} % Ähnlichkeit, Einstellung "
                                 "AEHNLICH_MIN).")
    return _ergebnis(app, o, name, pfad, eintraege, abzeichen, zeile, leer)


def _bildvergleich(app, o, name, pfad, rid, titel, grund):
    """Ohne KI: fotosort.py vergleicht pHash und dHash wie beim Import – das findet nur fast gleiche Fotos."""
    r = app.rechnungen.get(rid) if rid else None
    fertig = (r is not None and r.art == "aehnlich" and r.bezug == f"{o}/{name}" and not r.status["laeuft"]
              and not r.status["fehler"] and r.status["ergebnis"])
    if not fertig:
        return _warten(app, o, name, pfad, titel, ki=False)
    erg, schwelle = r.status["ergebnis"], app.gruppe["SCHWELLE"]
    eintraege, abzeichen = [], {}
    for rel, abstand, sek in erg.get("treffer") or []:
        to, _, tname = rel.partition("/")
        treffer = app.archiv.datei(to, tname) if ist_ordner(to) and to in app.archiv.ordner() else None
        if not treffer:
            continue  # inzwischen verschoben oder eine NEF ohne JPG
        eintraege.append((to, tname, treffer[2], treffer[1]))
        wort = stufe(abstand, schwelle)
        abzeichen[f"{to}/{url_id(tname)}"] = (
            f"≈ {abstand} · {wort}",
            f"Abstand {abstand} (pHash+dHash, 0 = gleich) – {wort}"
            + (f"; gleiche Kamera, {sek:g} s auseinander" if sek is not None else "")
            + (f"; bis {schwelle} (SCHWELLE) legt fotosort Fotos beim Import zusammen" if abstand <= schwelle else ""),
            "nah" if abstand <= schwelle else "")
    gruppe = sum(1 for rel, a, _ in erg.get("treffer") or [] if a <= schwelle)
    zeile = (f'KI-Suche aus: {e(grund)}. Ohne KI findet „Ähnliche Fotos“ nur fast gleiche Fotos – per Bildvergleich '
             f'wie beim Import. {bilder_text(len(eintraege))} mit Abstand bis {erg.get("bis", 24)}, nach Ähnlichkeit '
             f'sortiert (verglichen mit {erg.get("bilder", 0)} Fotos im Archiv). Abstand = verschiedene Bits von pHash '
             f'und dHash: 0 = gleich, um 60 = ganz verschieden; bis {schwelle} (Einstellung „Bildvergleich“) legt '
             f'fotosort Fotos beim Import in eine Gruppe' + (f' – das wären hier {gruppe}' if gruppe else '') + '.')
    if erg.get("grund"):
        leer = f"Das Foto ist {erg['grund']}."
    elif not eintraege:
        leer = (f"Keine fast gleichen Fotos im Archiv (Abstand bis {erg.get('bis', 24)}): gleiche Aufnahme in anderer "
                "Größe, Serienbilder, nachbearbeitete Kopien.")
    else:
        leer = ""
    return _ergebnis(app, o, name, pfad, eintraege, abzeichen, zeile, leer, neu=True, zeile_html=True)


def _ergebnis(app, o, name, pfad, treffer, abzeichen, zeile, leer, neu=False, zeile_html=False):
    """Kontaktbogen: vorn das Ausgangsfoto, dahinter die Treffer (Ordner, Name, mtime, Größe) mit ihrem Abzeichen."""
    _, groesse, mt = app.archiv.datei(o, name)
    eintraege = [(o, name, mt, groesse)] + list(treffer)
    abzeichen = dict(abzeichen, **{pfad: ("Ausgangsfoto", "Zu diesem Foto werden ähnliche gesucht", "bezug")})
    felder, daten = bogen_html(app, eintraege, einordner=False, abzeichen=abzeichen)
    n = len(treffer)
    knoepfe = ('<nav class="weg" aria-label="Aktionen">'
               f'<a class="knopf" href="/o/{o}">Ordner {o}</a>'
               f'<a class="knopf" href="/aehnlich?{urlencode(dict(pfad=pfad, **({"neu": 1} if neu else {})))}" '
               'title="Noch einmal suchen – mit den Fotos, die jetzt im Archiv sind">Neu suchen</a>'
               + ('<button class="knopf" id="verschieben" type="button" aria-pressed="false" title="Ähnliche Fotos '
                  'auswählen und in den Ordner des Ausgangsfotos oder einen anderen verschieben">Fotos verschieben …'
                  '</button>' if n else "") + '</nav>')
    titel = (f'<div class="titel"><h1>Ähnliche Fotos</h1><div><p id="info">{e(os.path.basename(name))} · '
             f'Ordner {o}</p><p class="ziel" id="ziel"></p></div></div>{knoepfe}')
    inhalt = kopf(app, "", titel) + (f'<p class="leer">{e(leer)}</p>' if leer else "")
    hoch = max(int(x) for x in app.archiv.ordner())
    naechster = f"{hoch + 1:04d}" if hoch < MAX_ORDNER else None
    inhalt += ((f'<div class="filter aehnzeile"><p class="leise">{zeile if zeile_html else e(zeile)}</p></div>'
                if zeile else "") + (ALBUMLEISTE if app.index else "")
               + f'<main class="bogen">{felder}</main>' + bogen_hilfe(app)
               + VERSCHIEBEN_HTML.replace("{naechster}", naechster or "–") + LUPE_HTML + (ALBBOX if app.index else ""))
    ordner_menge = sorted({x for x, *_ in eintraege})
    js = {"einordner": False, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {x: [url_id(m) for m in app.auswahl.markiert(x)] for x in ordner_menge},
          "ziele": {x: {url_id(m): z for m, z in app.auswahl.ziele(x).items()} for x in ordner_menge},
          "alben": alben_liste(app.index) if app.index else None, "suche": None, "treffer": len(daten),
          "aehnlich": {"pfad": pfad, "ordner": o}, "naechster": naechster,
          "verbessern": app.verbesserer.fuer_seite() if app.verbesserer else [], "kolorieren": farb_daten(app),
          "vorwahl": app.verbesserer.vorwahl if app.verbesserer else ""}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"Ähnlich zu {os.path.basename(name)} – BestOf", inhalt,
                 JS_BOGEN + JS_ALBEN + JS_VERBESSERN + JS_BEARBEITEN + JS_VERSCHIEBEN)


def _warten(app, o, name, pfad, titel, ki):
    """Solange gerechnet wird: das Ausgangsfoto, der Stand, danach Weiterleitung auf das Ergebnis."""
    _, _, mt = app.archiv.datei(o, name)
    if ki:
        stand = "Die KI bereitet die Suche vor …"
        hilfe = ("Verglichen wird der Bildinhalt mit dem KI-Modell CLIP. Dafür berechnet der Index einmal für jedes "
                 "Foto KI-Merkmale – beim ersten Mal dauert das je nach Rechner etwa 15 bis 60 Minuten je 50.000 Fotos, "
                 "danach kommt jedes Ergebnis sofort. Dieses Foto ist als Nächstes dran.")
    else:
        stand = "fotosort vergleicht das Foto mit dem Archiv …"
        hilfe = ("Ohne KI wird verglichen wie beim Gruppieren: Wahrnehmungs-Fingerabdrücke (pHash und dHash), das findet "
                 "nur fast gleiche Fotos. Beim ersten Mal liest fotosort Fotos, die es noch nicht kennt – das kann "
                 "dauern; danach geht es schnell.")
    inhalt = kopf(app, "", titel) + (
        f'<main class="import aehnwarten"><section><img class="aehnbild" src="/t/{o}/{url_id(name)}?v={mt}" alt="">'
        f'<p><b>{e(os.path.basename(name))}</b> · <a href="/o/{o}">Ordner {o}</a></p>'
        f'<p id="stand" class="leise">{e(stand)}</p><progress id="balken" max="1"></progress>'
        f'<p class="hilfe0">{e(hilfe)}</p></section></main>')
    return seite(f"Ähnlich zu {os.path.basename(name)} – BestOf", inhalt,
                 f"const P={json_im_html({'pfad': pfad})};" + (JS_WARTEN_KI if ki else JS_WARTEN))


def aehnlich_api(app, pfad):
    """GET /api/aehnlich?pfad=…: Ist die KI-Suche für dieses Foto bereit? Für die Warteseite. Rückgabe: (Code, Antwort)."""
    bezug = _bezug(app, pfad)
    if not bezug:
        return 404, {"fehler": "Dieses Foto gibt es nicht (mehr) – bitte aus einem Ordner neu aufrufen."}
    rel = f"{bezug[0]}/{url_id(bezug[1])}"
    zustand, grund = _zustand(app)
    if zustand == "aus":
        return 200, {"aus": True, "text": grund}
    if zustand == "bereit":
        if app.indexer.ki.hat(rel) or _ki_fehler(app, rel):
            return 200, {"bereit": True}
        app.indexer.ki_anfordern(rel)
    s = app.indexer.status
    phase, fertig, gesamt = s["phase"], s["fertig"], s["gesamt"]
    if phase == "KI" and gesamt:
        text = f"Die KI liest das Archiv: {fertig} von {gesamt} Fotos – dieses Foto kommt als Nächstes dran …"
    elif phase == "Index" and gesamt:
        text = f"Der Index liest neue Fotos: {fertig} von {gesamt} – danach rechnet die KI …"
    elif phase.startswith("Lade KI-Modell"):
        text, fertig, gesamt = f"Das KI-Modell wird geladen (einmalig): {phase[len('Lade KI-Modell'):].strip(' ()')} …", 0, 0
    elif phase == "Prüfe KI-Modell":
        text, fertig, gesamt = "Das KI-Modell wird geprüft …", 0, 0
    else:
        text, fertig, gesamt = f"Index: {phase} …", 0, 0
    return 200, {"bereit": False, "text": text, "fertig": fertig, "gesamt": gesamt}


JS_WARTEN_KI = """
const $=id=>document.getElementById(id);
async function abfragen(){let j;
 try{j=await (await fetch('/api/aehnlich?'+new URLSearchParams({pfad:P.pfad}))).json();}
 catch(_){setTimeout(abfragen,2000);return;}
 if(j.bereit||j.aus){location.replace('/aehnlich?'+new URLSearchParams({pfad:P.pfad}));return;}
 if(j.fehler){$('stand').textContent=j.fehler;$('balken').hidden=true;return;}
 $('stand').textContent=j.text||'…';
 if(j.gesamt){$('balken').max=j.gesamt;$('balken').value=j.fertig;}else $('balken').removeAttribute('value');
 setTimeout(abfragen,1000);}
abfragen();
"""

JS_WARTEN = """
const $=id=>document.getElementById(id);
function zahl(n){return String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g,'.');}
async function abfragen(id){let r;try{r=(await (await fetch('/api/gruppieren?id='+encodeURIComponent(id))).json()).rechnungen[id];}
 catch(_){setTimeout(()=>abfragen(id),2000);return;}
 if(!r){suchen();return;}
 if(r.laeuft){$('stand').textContent='fotosort vergleicht: '+(r.phase||'Start')+(r.gesamt?' – '+zahl(r.fertig)+' von '+zahl(r.gesamt):'')+' …';
  $('balken').max=r.gesamt||1;if(r.gesamt)$('balken').value=r.fertig;else $('balken').removeAttribute('value');
  setTimeout(()=>abfragen(id),600);return;}
 if(r.fehler){$('stand').textContent='Die Suche ging schief: '+r.fehler;$('balken').hidden=true;return;}
 location.replace('/aehnlich?'+new URLSearchParams({pfad:P.pfad,id}));}
let neu=new URLSearchParams(location.search).has('neu');  // „Neu suchen“: kein früheres Ergebnis nehmen
async function suchen(){const [ok,j]=await post('/api/gruppieren',{aktion:'aehnlich',pfad:P.pfad,neu});
 if(!ok){$('stand').textContent=j.fehler||'Die Suche lässt sich nicht starten.';$('balken').hidden=true;return;}
 if(neu){neu=false;history.replaceState(null,'','/aehnlich?'+new URLSearchParams({pfad:P.pfad}));}  // Neuladen: dieselbe Suche
 abfragen(j.id);}
suchen();
"""
