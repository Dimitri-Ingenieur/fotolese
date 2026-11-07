"""fotolese.web.aehnlich – Seite „Ähnliche Fotos“: zu einem Foto die ähnlichsten im Archiv, nach Ähnlichkeit sortiert.

fotosort.py rechnet (MODUS=aehnlich) mit demselben Maß wie beim Gruppieren: der Zahl verschiedener Bits von pHash
und dHash (0 = gleich, um 60 = ganz verschieden). bestof zeigt das Ergebnis als Kontaktbogen mit allen Knöpfen;
jedes Foto trägt seinen Abstand. „Fotos verschieben …“ schlägt den Ordner des Ausgangsfotos als Ziel vor.
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


def stufe(abstand, schwelle):
    """Abstand in Worten – „sehr ähnlich“ heißt: beim Import kämen die Fotos in eine Gruppe (SCHWELLE)."""
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


def aehnlich_seite(app, pfad, rid):
    bezug = _bezug(app, pfad)
    titel = '<div class="titel"><h1>Ähnliche Fotos</h1><div><p id="info"></p><p class="ziel" id="ziel"></p></div></div>'
    if not bezug:
        return seite("Ähnliche Fotos – BestOf", kopf(app, "", titel) +
                     '<p class="leer">Dieses Foto gibt es nicht (mehr). Bitte aus einem Ordner neu aufrufen.</p>')
    o, name = bezug
    pfad = f"{o}/{url_id(name)}"
    r = app.rechnungen.get(rid) if rid else None
    fertig = (r is not None and r.art == "aehnlich" and r.bezug == f"{o}/{name}" and not r.status["laeuft"]
              and not r.status["fehler"] and r.status["ergebnis"])
    if not fertig:
        return _warten(app, o, name, pfad, titel)
    erg, schwelle = r.status["ergebnis"], app.gruppe["SCHWELLE"]
    _, groesse, mt = app.archiv.datei(o, name)
    eintraege = [(o, name, mt, groesse)]
    abzeichen = {pfad: ("Ausgangsfoto", "Zu diesem Foto werden ähnliche gesucht", "bezug")}
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
    felder, daten = bogen_html(app, eintraege, einordner=False, abzeichen=abzeichen)
    n = len(eintraege) - 1
    gruppe = sum(1 for rel, a, _ in erg.get("treffer") or [] if a <= schwelle)
    zeile = (f'<p class="leise">{bilder_text(n)} mit Abstand bis {erg.get("bis", 48)}, nach Ähnlichkeit sortiert '
             f'(verglichen mit {erg.get("bilder", 0)} Fotos im Archiv). Abstand = verschiedene Bits von pHash und dHash: '
             f'0 = gleich, um 60 = ganz verschieden; bis {schwelle} (Einstellung „Bildvergleich“) legt fotosort Fotos '
             f'beim Import in eine Gruppe' + (f' – das wären hier {gruppe}' if gruppe else '') + '.</p>')
    knoepfe = ('<nav class="weg" aria-label="Aktionen">'
               f'<a class="knopf" href="/o/{o}">Ordner {o}</a>'
               f'<a class="knopf" href="/aehnlich?{urlencode({"pfad": pfad, "neu": 1})}" title="Noch einmal suchen – '
               'mit den Fotos, die jetzt im Archiv sind">Neu suchen</a>'
               + ('<button class="knopf" id="verschieben" type="button" aria-pressed="false" title="Ähnliche Fotos '
                  'auswählen und in den Ordner des Ausgangsfotos oder einen anderen verschieben">Fotos verschieben …'
                  '</button>' if n else "") + '</nav>')
    titel = (f'<div class="titel"><h1>Ähnliche Fotos</h1><div><p id="info">{e(os.path.basename(name))} · '
             f'Ordner {o}</p><p class="ziel" id="ziel"></p></div></div>{knoepfe}')
    inhalt = kopf(app, "", titel)
    if erg.get("grund"):
        inhalt += f'<p class="leer">Das Foto ist {e(erg["grund"])}.</p>'
    elif not n:
        inhalt += (f'<p class="leer">Keine ähnlichen Fotos im Archiv (Abstand bis {erg.get("bis", 48)}). '
                   'Ähnlich heißt hier: dasselbe Motiv – gleiche Aufnahme in anderer Größe, Serienbilder, '
                   'nachbearbeitete Kopien.</p>')
    hoch = max(int(x) for x in app.archiv.ordner())
    naechster = f"{hoch + 1:04d}" if hoch < MAX_ORDNER else None
    inhalt += (f'<div class="filter aehnzeile">{zeile}</div>' + (ALBUMLEISTE if app.index else "")
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


def _warten(app, o, name, pfad, titel):
    """Solange fotosort rechnet: das Ausgangsfoto, der Stand, danach Weiterleitung auf das Ergebnis."""
    _, _, mt = app.archiv.datei(o, name)
    inhalt = kopf(app, "", titel) + (
        f'<main class="import aehnwarten"><section><img class="aehnbild" src="/t/{o}/{url_id(name)}?v={mt}" alt="">'
        f'<p><b>{e(os.path.basename(name))}</b> · <a href="/o/{o}">Ordner {o}</a></p>'
        '<p id="stand" class="leise">fotosort vergleicht das Foto mit dem Archiv …</p>'
        '<progress id="balken" max="1"></progress>'
        '<p class="hilfe0">Verglichen wird wie beim Gruppieren: Wahrnehmungs-Fingerabdrücke (pHash und dHash). Beim '
        'ersten Mal liest fotosort Fotos, die es noch nicht kennt – das kann dauern; danach geht es schnell.</p>'
        '</section></main>')
    daten = {"pfad": pfad}
    return seite(f"Ähnlich zu {os.path.basename(name)} – BestOf", inhalt,
                 f"const P={json_im_html(daten)};" + JS_WARTEN)


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
