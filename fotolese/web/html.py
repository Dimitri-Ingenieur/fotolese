"""fotolese.web.html – Seiten und Bausteine der Oberfläche (CSS, JS, HTML-Erzeugung)."""
import hashlib
import json
import os
import random
from urllib.parse import quote, urlencode

import numpy as np

from fotolese.web.konst import MONATE
from fotolese.web.konfig import (anzeige, bilder_text, bildmasse, datum_kurz, e, groesse_text,
                                 name_aus_id, ort_text, url_id, zeit_text)
from fotolese.web.suche import ALLE_FOTOS, suche_ausfuehren
from fotolese.web.alben import alben_liste, alben_von
from fotolese.web.index import namensliste, personen_namen
from fotolese.web.lernen import lern_zeile


CSS = """
:root{
  --umfeld:#333;--flaeche:#3b3b3b;--linie:#4f4f4f;--text:#ececec;--leise:#a9a9a9;
  --stift:#f2c14e;--fehler:#e8735a;--lupe:#2a2a2a;--album:#8ecae6;
  --zahl:"Ubuntu Condensed","DejaVu Sans Condensed","Roboto Condensed","Arial Narrow",sans-serif;
  --schrift:system-ui,Ubuntu,"Noto Sans","DejaVu Sans",sans-serif;
  color-scheme:dark;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;background:var(--umfeld);color:var(--text);font:15px/1.45 var(--schrift)}
a{color:inherit}
:focus-visible{outline:2px solid var(--stift);outline-offset:2px}
button,input{font:inherit;color:inherit}
.kopf{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px 22px;padding:18px 16px 14px;border-bottom:1px solid var(--linie)}
.archiv{font-family:var(--zahl);font-weight:700;font-size:26px;text-decoration:none;letter-spacing:.01em}
.stand,.status{color:var(--leise);margin:0}
.status{font-size:13px;width:100%}
.status:empty{display:none}
.navi{display:flex;gap:2px;flex-wrap:wrap}
.navi a,.knopf{display:inline-block;padding:6px 12px;border:1px solid var(--linie);background:none;
  text-decoration:none;cursor:pointer;border-radius:2px}
.navi a[aria-current]{background:var(--text);color:var(--umfeld);border-color:var(--text)}
.knopf:hover,.navi a:hover{border-color:var(--leise)}
.knopf[disabled]{opacity:.45;cursor:default}
.suche{display:flex;gap:6px;flex:1 1 22em;max-width:36em}
.suche input,.springen input,.pname{padding:6px 9px;background:var(--flaeche);border:1px solid var(--linie);border-radius:2px}
.suche input{flex:1;min-width:0;width:0}
.suche .knopf{white-space:nowrap}
.springen{display:flex;gap:6px}
.springen input{width:6.5em;font-family:var(--zahl);font-variant-numeric:tabular-nums}
.rechts{margin-left:auto}
.raster{display:grid;gap:18px 14px;padding:18px 16px 28px;grid-template-columns:repeat(auto-fill,minmax(168px,1fr))}
.kachel{text-decoration:none;display:block}
.kachel .bild{aspect-ratio:1;background:var(--flaeche);overflow:hidden}
.kachel img{width:100%;height:100%;object-fit:cover;display:block}
.kachel .zeile{display:flex;align-items:baseline;gap:8px;padding-top:6px}
.nr{font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:.02em}
.kachel .nr{font-size:20px}
.leise{color:var(--leise);font-size:13px}
.kachel .wann{display:block;min-height:1.2em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kachel:not(.gewaehlt) .bild{opacity:.82}
.kachel:hover .bild{opacity:1}
.sterne{flex:none;margin-left:auto;fill:var(--stift)}
.seiten{display:flex;flex-wrap:wrap;gap:4px;padding:0 16px 32px}
.seiten a,.seiten span{min-width:2.4em;text-align:center;padding:4px 8px;border:1px solid var(--linie);
  text-decoration:none;font-family:var(--zahl);font-variant-numeric:tabular-nums}
.seiten span[aria-current]{background:var(--text);color:var(--umfeld);border-color:var(--text)}
.leer{padding:40px 16px;color:var(--leise);max-width:60ch}
.filter{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:14px 16px 0}
.filter .chip{border:1px solid var(--linie);padding:3px 10px;border-radius:999px;font-size:13px}
/* Kontaktbogen */
.titel{display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap}
.titel h1{margin:0;font-family:var(--zahl);font-weight:700;font-size:64px;line-height:.9;font-variant-numeric:tabular-nums;letter-spacing:.02em}
.titel p{margin:0}
.ziel{color:var(--stift)}
.weg{display:flex;gap:6px;flex-wrap:wrap}
.bogen{display:grid;gap:22px 16px;padding:22px 16px 40px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.feld{margin:0}
.zelle{position:relative}
.feld .rahmen{aspect-ratio:1;background:var(--flaeche);padding:10px;display:block;width:100%;border:0;cursor:zoom-in}
.feld .rahmen img{width:100%;height:100%;object-fit:contain;display:block}
.fettstift{position:absolute;left:-7px;top:-7px;width:calc(100% + 14px);height:calc(100% + 14px);pointer-events:none;
  fill:none;stroke:var(--stift);stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round;
  stroke-dasharray:100;stroke-dashoffset:100;transition:stroke-dashoffset .38s ease-out;overflow:visible}
.gewaehlt .fettstift{stroke-dashoffset:0}
.buchstabe{position:absolute;left:-10px;top:-20px;font-family:var(--zahl);font-weight:700;font-style:italic;
  font-size:34px;line-height:1;color:var(--stift);transform:rotate(-9deg);text-shadow:0 0 4px rgba(0,0,0,.55);pointer-events:none}
.ordnernr{position:absolute;right:8px;top:8px;font-family:var(--zahl);font-weight:700;font-size:15px;
  background:rgba(40,40,40,.82);padding:1px 6px;border-radius:2px;text-decoration:none}
.feld figcaption{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;padding-top:8px}
.lfd{font-family:var(--zahl);font-weight:700;color:var(--leise);font-variant-numeric:tabular-nums;min-width:1.6em}
.dateiname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;font-size:13px;color:var(--leise)}
.gewaehlt .dateiname{color:var(--text)}
.knopf.stern{flex:none;display:inline-flex;align-items:center;justify-content:center;padding:5px 9px;color:var(--leise)}
.stern svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linejoin:round}
.knopf.stern:hover{color:var(--stift)}
.gewaehlt .stern{border-color:var(--stift);color:var(--stift)}.gewaehlt .stern svg{fill:currentColor}
.voll .stern{opacity:.45}
.technik{width:100%;font-size:12px;color:var(--leise);font-variant-numeric:tabular-nums;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.technik.spitze{color:var(--stift)}
.meta{width:100%;font-size:13px;color:var(--leise);display:flex;align-items:center;gap:7px;min-height:1.2em}
.mtext{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.meta b{font-weight:600;color:var(--text)}
.jahr{width:4.3em;flex:none;padding:0 5px;text-align:center;font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;
  background:none;border:1px solid var(--linie);border-radius:999px;color:var(--text)}
.jahr:hover{border-color:var(--leise)}
.jahr:placeholder-shown{border-style:dashed;font-weight:400}
.jahr::placeholder{color:var(--leise)}
.jahr.manuell,.jahr.an{border-color:var(--stift);color:var(--stift)}
.jahr.falsch{border-color:var(--fehler);color:var(--fehler)}
.ordnerjahr{display:flex;gap:6px;align-items:center}
.ordnerjahr .jahr,.jahrwerk .jahr{font-size:15px;padding:5px 6px;width:4.8em}
.knopf.jsetz{flex:none;padding:0 8px;border-radius:999px;font-family:var(--zahl);font-weight:700;font-size:13px;
  font-variant-numeric:tabular-nums;white-space:nowrap}
.knopf.jsetz.an{border-color:var(--stift);color:var(--stift)}
.jahrwerk{display:flex;align-items:center;gap:6px;margin-left:auto}
.hilfe{padding:0 16px 32px;color:var(--leise);font-size:13px}
kbd{font-family:var(--zahl);border:1px solid var(--linie);padding:0 5px;border-radius:2px}
/* Lupe */
.lupe{position:fixed;inset:0;background:var(--lupe);display:grid;grid-template-rows:1fr auto;z-index:10}
.lupe[hidden]{display:none}
.lupe .flaeche{display:flex;align-items:center;justify-content:center;min-height:0;padding:12px;position:relative;overflow:hidden}
.lupe img{max-width:100%;max-height:100%;object-fit:contain}
.lupe.gewaehlt .flaeche img{outline:5px solid var(--stift);outline-offset:6px}
.kasten{position:absolute;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.6);pointer-events:none}
.kasten button{position:absolute;left:-2px;top:100%;margin-top:3px;white-space:nowrap;font-size:13px;background:#fff;color:#222;
  padding:0 6px;border:0;border-radius:2px;cursor:pointer;pointer-events:auto}
.kasten button:hover{background:var(--stift)}
.kasten.aktiv{border-color:var(--stift)}.kasten.aktiv button{background:var(--stift)}
.ghinweis{position:absolute;left:50%;top:10px;transform:translateX(-50%);margin:0;padding:4px 10px;max-width:92%;
  font-size:13px;text-align:center;background:rgba(30,30,30,.86);border-radius:2px;z-index:2;pointer-events:none}
.gesichter-an .flaeche img{cursor:crosshair}
.nennbox{position:absolute;left:50%;bottom:14px;transform:translateX(-50%);z-index:3;width:min(92vw,27em);
  display:grid;gap:10px;padding:12px 14px;background:var(--flaeche);border:1px solid var(--linie);border-radius:3px;
  box-shadow:0 8px 28px rgba(0,0,0,.5)}
.nennbox.oben{top:14px;bottom:auto}
.nennbox label{display:grid;gap:4px;font-size:13px;color:var(--leise)}
.nennbox input{padding:6px 9px;font-size:17px;background:var(--umfeld);border:1px solid var(--linie);border-radius:2px}
.nknoepfe{display:flex;flex-wrap:wrap;gap:6px}
.nknoepfe .haupt{border-color:var(--stift);color:var(--stift)}
.nfuss{display:flex;justify-content:space-between;gap:10px}
.link{background:none;border:0;padding:0;color:var(--leise);text-decoration:underline;cursor:pointer;font-size:13px}
.link:hover{color:var(--text)}
.lupe .leiste{display:flex;align-items:center;gap:10px;padding:10px 16px 14px;flex-wrap:wrap;border-top:1px solid var(--linie)}
.lupe .wo{font-family:var(--zahl);font-weight:700;font-variant-numeric:tabular-nums;font-size:18px}
.lupe .jahr{font-size:17px;width:4.6em;padding:3px 6px}
.lupe .text{flex:1;min-width:12em;display:flex;flex-direction:column;overflow:hidden}
.lupe .wer,.lupe .info{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lupe .wer{color:var(--leise)}
.lupe .info{font-size:13px}
.lupe .knopf.jsetz{font-size:15px;padding:4px 9px}
.gesichter-an .knopf.gz{border-color:var(--text)}
.meldung{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--text);color:var(--umfeld);
  padding:9px 14px;border-radius:2px;max-width:min(92vw,60ch);z-index:20}
.meldung.fehler{background:var(--fehler);color:#1f1f1f}
.meldung[hidden]{display:none}
.lupe:not([hidden]) ~ .meldung{bottom:96px}
/* Personen */
.personen{padding:10px 16px 40px;display:grid;gap:26px}
.person{border-top:1px solid var(--linie);padding-top:14px}
.pkopf{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:10px}
.pname{font-family:var(--zahl);font-weight:700;font-size:20px;width:13em}
.pname:placeholder-shown{color:var(--leise)}
.gesichter{display:flex;flex-wrap:wrap;gap:8px}
.gesicht{position:relative;margin:0;width:88px}
.gesicht img{width:88px;height:88px;object-fit:cover;display:block;background:var(--flaeche)}
.gesicht a{display:block}
.gesicht button{position:absolute;top:2px;width:24px;height:24px;padding:0;border:0;border-radius:2px;
  background:rgba(40,40,40,.85);cursor:pointer;line-height:24px}
.gesicht .weg{right:2px}.gesicht .nennen{left:2px}
.gesicht .weg:hover{background:var(--fehler);color:#1f1f1f}.gesicht .nennen:hover{background:var(--stift);color:#1f1f1f}
.gruppe{margin-top:10px}
.gruppe .gkopf{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:13px;color:var(--leise)}
.hinweis{font-size:13px;color:var(--stift)}
.import{padding:6px 16px 40px;display:grid;gap:22px;max-width:1100px}
.import h2{font-size:17px;margin:0 0 10px}
.import section{border-top:1px solid var(--linie);padding-top:14px}
.pfadzeile{display:flex;gap:6px}.pfadzeile .pname{flex:1;font-size:15px;width:auto;min-width:0}
.krumen{display:flex;flex-wrap:wrap;gap:2px;margin:10px 0 6px}
.krume{background:none;border:0;color:var(--leise);cursor:pointer;padding:2px 4px;font-size:13px}
.krume:hover{color:var(--text)}.krume:not(:last-child):not(:first-child)::after{content:" /";color:var(--linie)}
.schnell{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}.knopf.klein{font-size:13px;padding:3px 9px}
.ordnerliste{list-style:none;margin:0;padding:0;max-height:46vh;overflow:auto;border:1px solid var(--linie)}
.ordnerliste li{border-bottom:1px solid var(--flaeche)}.ordnerliste li.leise{padding:8px 10px}
.ordnerknopf{display:block;width:100%;text-align:left;background:none;border:0;padding:7px 10px;cursor:pointer}
.ordnerknopf:hover{background:var(--flaeche)}
.knopfzeile{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.knopf.haupt{border-color:var(--stift);color:var(--stift)}
.hilfe0{font-size:13px;color:var(--leise);max-width:80ch}
.import progress{width:100%;height:10px;accent-color:var(--stift)}
.ergebnis{white-space:pre-line}.ergebnis.fehler{color:var(--fehler)}
.import pre{max-height:40vh;overflow:auto;font-size:12px;background:var(--lupe);padding:10px;white-space:pre-wrap}
.lernstand{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:12px 16px 0;font-size:13px;
  color:var(--leise)}
.pruefleiste{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;
  background:var(--umfeld);border-bottom:1px solid var(--linie)}
.pruefleiste .pname{font-size:15px;width:14em}
.wahl{cursor:pointer}
.wahl img{transition:opacity .12s}
.wahl.an img{outline:3px solid var(--stift);outline-offset:-3px}
.wahl .haken{position:absolute;top:3px;left:3px;width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;
  background:var(--stift);color:#1f1f1f;font-weight:700;display:none}
.wahl.an .haken{display:block}
.quelle{padding:0 16px 24px;color:var(--leise);font-size:12px}
/* Alben */
select{font:inherit;color:inherit;padding:5px 8px;background:var(--flaeche);border:1px solid var(--linie);border-radius:2px}
.alben{width:100%;display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;min-height:1.3em}
.achip{font-size:12px;padding:0 8px;border:1px solid var(--album);border-radius:999px;color:var(--album);
  text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.achip:hover{background:var(--album);color:#1f1f1f}
.aplus{font-size:12px}
.knopf.amark{font-size:13px;padding:2px 9px}
.knopf.amark.an,.lupe .knopf.almark.an{border-color:var(--album);color:var(--album)}
.imalbum .rahmen{outline:3px solid var(--album);outline-offset:-3px}
.albumleiste{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;
  padding:10px 16px;background:var(--umfeld);border-bottom:1px solid var(--linie)}
.albumleiste.aktiv{border-bottom-color:var(--album)}
.albumleiste.aktiv select{border-color:var(--album)}
.albbox{position:fixed;left:50%;bottom:150px;transform:translateX(-50%);z-index:12;width:min(92vw,26em);display:grid;
  gap:10px;padding:12px 14px;background:var(--flaeche);border:1px solid var(--linie);border-radius:3px;
  box-shadow:0 8px 28px rgba(0,0,0,.5)}
.albbox .atitel{margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.aliste{display:grid;gap:5px;max-height:40vh;overflow:auto}
.aliste label{display:flex;align-items:center;gap:7px;cursor:pointer}
.aliste input{accent-color:var(--album);width:17px;height:17px}
.alneu{display:flex;gap:6px}
.alneu input{flex:1;min-width:0;padding:6px 9px;background:var(--umfeld);border:1px solid var(--linie);border-radius:2px}
.lupe .lalben{display:flex;flex-wrap:wrap;gap:4px;padding-top:2px}
.albumneu{gap:8px}.albumneu .pname{font-size:15px;width:min(22em,100%)}
.albumkachel .bild{display:block}.albumkachel .zeile{flex-wrap:wrap}.albumkachel .pname{font-size:17px;width:100%}
@media (max-width:560px){
  .titel h1{font-size:48px}.raster{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .bogen{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
  .suche{flex-basis:100%;max-width:none}
  .jahrwerk{margin-left:0}
  .albumleiste{position:static}
}
@media (prefers-reduced-motion:reduce){.fettstift{transition:none}}
"""

FAVICON = ("data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#333"/>'
    '<path d="M6 7 L26 5 L27 25 L7 27 L5 9 L12 6" fill="none" stroke="#f2c14e" stroke-width="3.2" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>', safe=""))

JS_GEMEINSAM = """
const meldungEl=document.querySelector('.meldung');let meldungTimer;
function meldung(text,fehler){meldungEl.textContent=text;meldungEl.classList.toggle('fehler',!!fehler);
 meldungEl.hidden=false;clearTimeout(meldungTimer);meldungTimer=setTimeout(()=>meldungEl.hidden=true,fehler?6000:2600);}
async function post(url,daten){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify(daten||{})});let j={};try{j=await r.json();}catch(_){j={fehler:'Server antwortet nicht.'};}
 return [r.ok,j];}
const statusEl=document.querySelector('.status');
async function statusHolen(){try{const r=await fetch('/api/status');const j=await r.json();
 statusEl.textContent=j.text;if(j.laeuft)setTimeout(statusHolen,3000);}catch(_){}}
if(statusEl&&statusEl.dataset.laeuft==='1')setTimeout(statusHolen,2000);
"""

JS_UEBERSICHT = """
const nb=document.getElementById('neuaufbau');
if(nb)nb.addEventListener('click',async()=>{
 if(!confirm('BestOf aus den gespeicherten Sternen neu aufbauen? Fehlende Kopien werden ergänzt, veraltete entfernt.'))return;
 nb.disabled=true;const [ok,j]=await post('/api/neuaufbau');nb.disabled=false;
 meldung(ok?j.meldung:(j.fehler||'Neuaufbau fehlgeschlagen.'),!ok);if(ok)setTimeout(()=>location.reload(),1600);});
"""

JS_BOGEN = """
const D=JSON.parse(document.getElementById('daten').textContent);
let laeuft=false,aktiv=-1,gesichterAn=false,setzJahr=null,jahrLetzte=-1;
const felder=[...document.querySelectorAll('.feld')],info=document.getElementById('info'),zielEl=document.getElementById('ziel');
const lupe=document.querySelector('.lupe'),lupeImg=lupe.querySelector('img'),flaeche=lupe.querySelector('.flaeche'),
 lupeWo=lupe.querySelector('.wo'),lupeWer=lupe.querySelector('.wer'),lupeInfo=lupe.querySelector('.info'),
 lupeKnopf=lupe.querySelector('.stern'),lupeOrig=lupe.querySelector('.orig'),lupeKarte=lupe.querySelector('.karte'),
 gzKnopf=lupe.querySelector('.gz'),lupeJahr=D.jahr?lupe.querySelector('.jahr'):null,lupeJsetz=lupe.querySelector('.jsetz'),
 zusammenEl=document.getElementById('zusammen');
if(!D.jahr)lupe.querySelector('.jahr').hidden=true;
const ABC='abcdefghijklmnopqrstuvwxyz',STERNE=n=>n===1?'einen Stern':n+' Sterne';
function sternKnopf(k,b,an,voll){k.setAttribute('aria-pressed',an);
 k.title=an?'Stern entfernen – nimmt '+(D.ziele[b.ordner]||{})[b.id]+' aus BestOf':
  voll?'Ordner '+b.ordner+' hat schon '+STERNE(D.max):'Mit Stern markieren – kopiert das Bild nach BestOf';}
function zeichne(){
 felder.forEach((f,i)=>{const b=D.bilder[i],l=D.auswahl[b.ordner]||[],k=l.indexOf(b.id),an=k>=0,voll=!an&&l.length>=D.max;
  f.classList.toggle('gewaehlt',an);f.classList.toggle('voll',voll);
  f.querySelector('.buchstabe').textContent=an&&l.length>1?ABC[k]:'';sternKnopf(f.querySelector('.stern'),b,an,voll);});
 if(D.einordner){const l=D.auswahl[D.ordner]||[];
  info.textContent=D.bilder.length+(D.bilder.length===1?' Bild, ':' Bilder, ')+l.length+' von '+D.max+' mit Stern';
  zielEl.textContent=l.length?'BestOf: '+l.map(id=>D.ziele[D.ordner][id]).join(', '):'Noch kein Stern (☆ = Kopie in BestOf)';}
 if(aktiv>=0)lupeZeichne();}
async function umschalten(i){
 if(laeuft)return;const b=D.bilder[i],l=D.auswahl[b.ordner]||[];
 if(!l.includes(b.id)&&l.length>=D.max){meldung('Ordner '+b.ordner+' hat schon '+STERNE(D.max)+'. Nehmen Sie erst einem Bild den Stern.',true);return;}
 laeuft=true;const [ok,j]=await post('/api/auswahl',{ordner:b.ordner,datei:b.id});laeuft=false;
 if(!ok){meldung(j.fehler||'Stern setzen fehlgeschlagen.',true);return;}
 D.auswahl[b.ordner]=j.auswahl;D.ziele[b.ordner]=j.ziele;zeichne();meldung(j.meldung);}
felder.forEach((f,i)=>{f.querySelector('.stern').addEventListener('click',()=>umschalten(i));
 f.querySelector('.rahmen').addEventListener('click',()=>oeffne(i));
 const k=f.querySelector('.jsetz');if(k)k.addEventListener('click',ev=>jahrKlick(i,ev.shiftKey));});
function vorladen(i){if(i>=0&&i<D.bilder.length){const b=new Image();b.src=D.bilder[i].g;}}
function hinweisText(b){const n=b.f.length,klick=' Ins Gesicht klicken, um es zu markieren.';
 if(b.fs==='fehler')return 'Die Datei ist nicht lesbar.';
 if(b.fs==='offen'&&!n)return 'Noch nicht nach Gesichtern durchsucht – der Index läuft.'+klick;
 return n?n+(n===1?' Gesicht.':' Gesichter.')+' Fehlt eines?'+klick:'Kein Gesicht erkannt.'+klick;}
function kaesten(){flaeche.querySelectorAll('.kasten').forEach(k=>k.remove());
 lupe.classList.toggle('gesichter-an',gesichterAn);ghinweis.hidden=!gesichterAn||aktiv<0||!nbox.hidden;
 if(aktiv>=0)ghinweis.textContent=hinweisText(D.bilder[aktiv]);
 if(!gesichterAn||aktiv<0||!lupeImg.complete)return;
 const r=lupeImg.getBoundingClientRect(),fr=flaeche.getBoundingClientRect();
 for(const g of D.bilder[aktiv].f){const [x,y,w,h]=g;const k=document.createElement('div');
  k.className='kasten'+(g===nGesicht?' aktiv':'');
  k.style.left=(r.left-fr.left+x*r.width)+'px';k.style.top=(r.top-fr.top+y*r.height)+'px';
  k.style.width=(w*r.width)+'px';k.style.height=(h*r.height)+'px';
  const a=document.createElement('button');a.type='button';a.textContent=g[5];a.title='Wer ist das? Namen ändern';
  a.addEventListener('click',()=>gesichtBenennen(g));k.appendChild(a);flaeche.appendChild(k);}}
const nbox=lupe.querySelector('.nennbox'),nname=nbox.querySelector('.nname'),nhaupt=nbox.querySelector('.haupt'),
 nneben=nbox.querySelector('.neben'),nkein=nbox.querySelector('.kein'),namenListe=document.getElementById('namenliste'),
 ghinweis=lupe.querySelector('.ghinweis');let nGesicht=null,sucht=false;
(D.namen||[]).forEach(namenErgaenzen);
function namenErgaenzen(n){if(!n||[...namenListe.options].some(o=>o.value===n))return;
 const o=document.createElement('option');o.value=n;namenListe.appendChild(o);}
function nennenZu(){if(nbox.hidden)return;nbox.hidden=true;nGesicht=null;kaesten();}
function gesichtBenennen(g){nGesicht=g;nkein.hidden=!!g.neu;
 if(g.neu){nname.value='';nhaupt.textContent='Stelle markieren';nhaupt.dataset.art='neu';nneben.hidden=true;
  nbox.classList.toggle('oben',g.y>0.55);nbox.hidden=false;kaesten();nname.focus();return;}
 const unbenannt=g[5].startsWith('Person '),n=g[7]||1;
 nname.value=unbenannt?'':g[5];
 const gruppe=n>1?'Alle '+n+' Gesichter '+(unbenannt?'dieser Gruppe':'von '+g[5]):'',einzeln=n>1?'Nur dieses Gesicht':'Speichern';
 const gruppeZuerst=unbenannt&&n>1;  // „Person N“ benennen = ganze Gruppe; benannte Gruppe = Korrektur dieses Gesichts
 nhaupt.textContent=gruppeZuerst?gruppe:einzeln;nhaupt.dataset.art=gruppeZuerst?'gruppe':'einzeln';
 nneben.hidden=!gruppe;nneben.textContent=gruppeZuerst?einzeln:gruppe;nneben.dataset.art=gruppeZuerst?'einzeln':'gruppe';
 nbox.classList.toggle('oben',g[1]+g[3]/2>0.55);  // Gesicht unten im Bild: Feld oben zeigen
 nbox.hidden=false;kaesten();nname.focus();nname.select();}
async function gesichterHolen(i){if(!D.gesichter||i<0)return;const b=D.bilder[i];
 try{const r=await fetch('/api/gesichter?pfad='+encodeURIComponent(b.ordner+'/'+b.id));if(!r.ok)return;const j=await r.json();
  if(!nbox.hidden&&aktiv===i)return;  // während des Benennens nichts austauschen
  b.f=j.f;b.fs=j.fs;feldMeta(i);if(aktiv===i)lupeZeichne();}catch(_){}}
function gesichterAendern(passt,tun){D.bilder.forEach((b,i)=>{let neu=false;
 b.f.forEach(f=>{if(passt(f)){tun(f);neu=true;}});if(neu)feldMeta(i);});}
async function nennenAusfuehren(art){const g=nGesicht;if(!g||aktiv<0)return;const name=nname.value.trim(),i=aktiv,b=D.bilder[i];
 if(art!=='weg'&&!name){meldung('Bitte einen Namen eingeben.',true);nname.focus();return;}
 if(art==='neu'){nbox.hidden=true;nGesicht=null;kaesten();gesichtSuchen(g.x,g.y,name);return;}
 const ziel={id:g[6],pfad:b.ordner+'/'+b.id,kasten:g.slice(0,4)};  // Lage hilft, falls die ID veraltet ist
 const [ok,j]=await post(art==='gruppe'?'/api/person':'/api/gesicht',
  art==='gruppe'?{ids:[g[4]],name}:art==='weg'?ziel:Object.assign({name},ziel));
 if(!ok){if(j.veraltet){nbox.hidden=true;nGesicht=null;gesichterHolen(i);}meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}
 if(j.id)g[6]=j.id;
 if(art==='gruppe')gesichterAendern(f=>f[4]===g[4],f=>{f[5]=j.name;});
 else if(art==='weg')D.bilder.forEach((b,i)=>{const n=b.f.length;b.f=b.f.filter(f=>f[6]!==g[6]);if(b.f.length!==n)feldMeta(i);});
 else{const neu=new Map((j.bewegt||[]).map(x=>[x[0],x]));gesichterAendern(f=>neu.has(f[6]),f=>{const x=neu.get(f[6]);f[4]=x[1];f[5]=x[2];});}
 if(j.anzahl)gesichterAendern(f=>j.anzahl[f[4]]!==undefined,f=>{f[7]=j.anzahl[f[4]];});
 namenErgaenzen(j.name);nbox.hidden=true;nGesicht=null;if(aktiv>=0)lupeZeichne();meldung(j.meldung);gesichterHolen(i);}
nhaupt.addEventListener('click',()=>nennenAusfuehren(nhaupt.dataset.art));
nneben.addEventListener('click',()=>nennenAusfuehren(nneben.dataset.art));
nkein.addEventListener('click',()=>nennenAusfuehren('weg'));
lupeImg.addEventListener('click',ev=>{if(!gesichterAn||aktiv<0)return;if(!nbox.hidden){nennenZu();return;}
 const r=lupeImg.getBoundingClientRect(),x=(ev.clientX-r.left)/r.width,y=(ev.clientY-r.top)/r.height;
 if(x>=0&&x<=1&&y>=0&&y<=1)gesichtSuchen(x,y);});
async function gesichtSuchen(x,y,name){if(sucht)return;const i=aktiv,b=D.bilder[i];sucht=true;
 if(!name)meldung('Suche Gesicht …');
 const [ok,j]=await post('/api/gesicht_neu',name?{ordner:b.ordner,datei:b.id,x,y,name,erzwingen:true}:{ordner:b.ordner,datei:b.id,x,y});
 sucht=false;
 if(!ok){if(j.markieren&&aktiv===i){meldung(j.fehler+' Mit einem Namen markieren Sie die Stelle trotzdem.',true);
   gesichtBenennen({neu:true,x,y});}else meldung(j.fehler||'Suche fehlgeschlagen.',true);return;}
 let g=b.f.find(f=>f[6]===j.gesicht[6]);if(!g){g=j.gesicht;b.f.push(g);feldMeta(i);}
 namenErgaenzen(j.name);meldung(j.meldung);if(aktiv===i){lupeZeichne();if(!name)gesichtBenennen(g);}}
nbox.querySelector('.abbr').addEventListener('click',nennenZu);
nname.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();nennenAusfuehren(nhaupt.dataset.art);}
 else if(ev.key==='Escape'){ev.preventDefault();nennenZu();}});
function namenVon(b,alle){return [...new Set(b.f.map(g=>g[5]).filter(n=>alle||!n.startsWith('Person ')))]
 .sort((a,c)=>a.localeCompare(c,'de'));}
function jahrTitel(b){return b.jm?'Jahr von Hand gesetzt'+(b.z?' (Datei: '+b.z+')':' (Datei ohne Datum)')+
 '. Feld leeren und Enter = wieder Jahr aus der Datei.':b.j?'Jahr aus der Datei (EXIF oder Dateiname). Korrigieren: Jahr eintippen, Enter.':
 'Kein Datum in der Datei. Jahr eintippen, Enter.';}
function jahrFeld(inp,b){if(!inp)return;inp.value=b.j||'';inp.dataset.alt=inp.value;inp.classList.toggle('manuell',!!b.jm);
 inp.title=jahrTitel(b);}
function feldMeta(i){const b=D.bilder[i],n=namenVon(b,false),f=felder[i],m=f.querySelector('.mtext');
 jahrFeld(f.querySelector('.jahr'),b);jsetzZeichne(f.querySelector('.jsetz'),b);
 m.textContent=[b.jm?'':b.zm,b.ok].filter(Boolean).join(', ');
 if(n.length){if(m.textContent)m.append(' – ');const s=document.createElement('b');s.textContent=n.join(', ');m.append(s);}}
function jahreUebernehmen(j){D.bilder.forEach((b,i)=>{const n=j.jahre[b.ordner+'/'+b.id];if(n){b.j=n[0];b.jm=n[1];feldMeta(i);}});
 if(zusammenEl&&j.zusammen!==undefined)zusammenEl.textContent=j.zusammen;if(aktiv>=0)lupeZeichne();}
async function jahrAendern(inp,i){const b=D.bilder[i],wert=inp.value.trim();if(wert===inp.dataset.alt)return;
 if(wert&&!/^[0-9]{4}$/.test(wert)){meldung('Bitte das Jahr mit vier Ziffern eingeben, z. B. 1994.',true);inp.value=inp.dataset.alt;return;}
 const [ok,j]=await post('/api/jahr',{pfade:[b.ordner+'/'+b.id],jahr:wert});
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);inp.value=inp.dataset.alt;return;}
 jahreUebernehmen(j);meldung(j.meldung);}
function jahrTasten(inp){inp.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}
 else if(ev.key==='Escape'){ev.preventDefault();inp.value=inp.dataset.alt||'';inp.blur();}});}
// Jahr per Klick: Jahr oben in der Leiste eintippen, dann „→ Jahr“ unter den Fotos (Umschalt = Bereich)
const sjEl=document.getElementById('setzjahr'),sjAus=document.getElementById('setzjahraus'),
 sjInfo=document.getElementById('jahrinfo'),HEUTE=new Date().getFullYear();
function jsetzZeichne(k,b){if(!k)return;k.hidden=setzJahr===null;if(k.hidden)return;const gleich=b.j===setzJahr;
 k.textContent=(gleich?'✓ ':'→ ')+setzJahr;k.classList.toggle('an',gleich);k.setAttribute('aria-pressed',gleich);
 k.title=(gleich?'Hat schon das Jahr '+setzJahr:'Jahr '+setzJahr+' setzen')+' – mit Umschalt alle Fotos bis zum zuletzt angeklickten';}
async function jahrKlick(i,bereich){if(setzJahr===null||i<0)return;const jahr=setzJahr;let von=i,bis=i;
 if(bereich&&jahrLetzte>=0){von=Math.min(jahrLetzte,i);bis=Math.max(jahrLetzte,i);}jahrLetzte=i;
 const pfade=D.bilder.slice(von,bis+1).filter(b=>b.j!==jahr).map(b=>b.ordner+'/'+b.id);
 if(!pfade.length){meldung((von===bis?'Hat':'Alle haben')+' schon das Jahr '+jahr+'.');return;}
 let j={},n=0;
 for(let k=0;k<pfade.length;k+=1000){let ok;[ok,j]=await post('/api/jahr',{pfade:pfade.slice(k,k+1000),jahr:String(jahr)});
  if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}jahreUebernehmen(j);n+=Object.keys(j.jahre).length;}
 meldung(pfade.length>1000?'Jahr '+jahr+' für '+n+' Bilder gesetzt.':j.meldung);}
function jahrWerkzeug(wert){if(wert===setzJahr)return;setzJahr=wert;jahrLetzte=-1;
 try{if(wert===null)sessionStorage.removeItem('bestofJahr');else sessionStorage.setItem('bestofJahr',String(wert));}catch(_){}
 sjAus.hidden=sjInfo.hidden=wert===null;sjEl.classList.toggle('an',wert!==null);
 felder.forEach((f,i)=>jsetzZeichne(f.querySelector('.jsetz'),D.bilder[i]));if(aktiv>=0)lupeZeichne();}
function jahrEingabe(){const w=sjEl.value.trim(),n=+w,gut=/^[0-9]{4}$/.test(w)&&n>=1900&&n<=HEUTE;
 sjEl.classList.toggle('falsch',w.length===4&&!gut);jahrWerkzeug(gut?n:null);}
if(sjEl){sjEl.addEventListener('input',jahrEingabe);
 sjEl.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();
   if(sjEl.classList.contains('falsch'))meldung('Bitte ein Jahr von 1900 bis '+HEUTE+' eingeben.',true);else sjEl.blur();}
  else if(ev.key==='Escape'){ev.preventDefault();sjEl.value='';jahrEingabe();sjEl.blur();}});
 sjAus.addEventListener('click',()=>{sjEl.value='';jahrEingabe();sjEl.focus();});
 let gemerkt=null;try{gemerkt=sessionStorage.getItem('bestofJahr');}catch(_){}
 if(gemerkt){sjEl.value=gemerkt;jahrEingabe();}}
if(lupeJsetz)lupeJsetz.addEventListener('click',ev=>jahrKlick(aktiv,ev.shiftKey));
function lupeZeichne(){const b=D.bilder[aktiv],l=D.auswahl[b.ordner]||[],an=l.includes(b.id),voll=!an&&l.length>=D.max;
 lupe.classList.toggle('gewaehlt',an);lupe.classList.toggle('voll',voll);lupeWo.textContent=(aktiv+1)+' / '+D.bilder.length;
 lupeWer.textContent=(D.einordner?'':'Ordner '+b.ordner+', ')+b.name+' · '+b.t+(an?' – BestOf '+D.ziele[b.ordner][b.id]:'');
 lupeInfo.textContent=[b.jm?'':b.z,b.ol,namenVon(b,true).join(', ')].filter(Boolean).join(', ');
 if(lupeJahr&&document.activeElement!==lupeJahr)jahrFeld(lupeJahr,b);jsetzZeichne(lupeJsetz,b);
 lupeKarte.hidden=!b.k;if(b.k)lupeKarte.href=b.k;
 gzKnopf.hidden=!D.gesichter;gzKnopf.textContent='Gesichter'+(b.f.length?' ('+b.f.length+')':'');
 sternKnopf(lupeKnopf,b,an,voll);lupeKnopf.title+=' (Leertaste oder S)';kaesten();albenLupe();}
function oeffne(i){nbox.hidden=true;nGesicht=null;aktiv=(i+D.bilder.length)%D.bilder.length;const b=D.bilder[aktiv];
 lupeImg.src=b.g;lupeImg.alt=b.name;lupeOrig.href=b.o;lupe.hidden=false;lupeZeichne();if(gesichterAn)gesichterHolen(aktiv);
 vorladen(aktiv+1);vorladen(aktiv-1);lupe.querySelector('.zu').focus({preventScroll:true});}
function schliesse(){if(aktiv<0)return;nbox.hidden=true;nGesicht=null;const f=felder[aktiv];aktiv=-1;lupe.hidden=true;
 lupeImg.removeAttribute('src');
 kaesten();f.querySelector('.rahmen').focus({preventScroll:true});f.scrollIntoView({block:'nearest'});}
lupeImg.addEventListener('load',kaesten);window.addEventListener('resize',kaesten);
lupe.querySelector('.zurueck').addEventListener('click',()=>oeffne(aktiv-1));
lupe.querySelector('.vor').addEventListener('click',()=>oeffne(aktiv+1));
lupe.querySelector('.zu').addEventListener('click',schliesse);
gzKnopf.addEventListener('click',()=>{gesichterAn=!gesichterAn;if(!gesichterAn)nbox.hidden=true;else gesichterHolen(aktiv);kaesten();});
lupeKnopf.addEventListener('click',()=>umschalten(aktiv));
let wischX=null;lupe.addEventListener('touchstart',ev=>{wischX=ev.touches[0].clientX;},{passive:true});
lupe.addEventListener('touchend',ev=>{if(wischX===null)return;const dx=ev.changedTouches[0].clientX-wischX;wischX=null;
 if(Math.abs(dx)>60)oeffne(aktiv+(dx<0?1:-1));});
document.addEventListener('keydown',ev=>{
 if(ev.altKey||ev.ctrlKey||ev.metaKey||ev.target.matches('input,select'))return;
 if(albenOffen()){if(ev.key==='Escape'){albenZu();ev.preventDefault();}return;}
 if(aktiv>=0){
  if(!nbox.hidden&&ev.key==='Escape'){nennenZu();ev.preventDefault();}
  else if(ev.key==='ArrowRight'){oeffne(aktiv+1);ev.preventDefault();}
  else if(ev.key==='ArrowLeft'){oeffne(aktiv-1);ev.preventDefault();}
  else if(ev.key===' '||ev.key==='s'||ev.key==='S'||ev.key==='b'){umschalten(aktiv);ev.preventDefault();}
  else if(ev.key==='g'||ev.key==='G'){gesichterAn=!gesichterAn;if(!gesichterAn)nbox.hidden=true;else gesichterHolen(aktiv);kaesten();}
  else if((ev.key==='j'||ev.key==='J')&&lupeJahr){lupeJahr.focus();lupeJahr.select();ev.preventDefault();}
  else if(ev.key==='a'||ev.key==='A'){albumTaste();ev.preventDefault();}
  else if(ev.key==='Escape'){schliesse();}
 }else if(D.einordner){
  if(ev.key==='ArrowRight'&&D.weiter)location.href=D.weiter;
  else if(ev.key==='ArrowLeft'&&D.zurueck)location.href=D.zurueck;
  else if(ev.key==='n'||ev.key==='N')location.href=D.offen;
  else if(ev.key==='Escape')location.href=D.uebersicht;
 }});
felder.forEach((f,i)=>{const inp=f.querySelector('.jahr');feldMeta(i);if(!inp)return;
 jahrTasten(inp);inp.addEventListener('change',()=>jahrAendern(inp,i));});
if(lupeJahr){jahrTasten(lupeJahr);lupeJahr.addEventListener('change',()=>{if(aktiv>=0)jahrAendern(lupeJahr,aktiv);});}
const oj=document.getElementById('ordnerjahr');
if(oj)oj.addEventListener('submit',async ev=>{ev.preventDefault();const inp=oj.querySelector('.jahr'),wert=inp.value.trim();
 if(wert&&!/^[0-9]{4}$/.test(wert)){meldung('Bitte das Jahr mit vier Ziffern eingeben, z. B. 1994.',true);return;}
 if(!wert&&!confirm('Alle von Hand gesetzten Jahre in diesem Ordner entfernen? Dann gilt wieder das Jahr aus den Dateien.'))return;
 const [ok,j]=await post('/api/jahr',{ordner:D.ordner,jahr:wert});
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}inp.value='';jahreUebernehmen(j);meldung(j.meldung);});
zeichne();
"""

JS_PRUEFEN = """
const wahl=new Set(),zahl=document.getElementById('zahl'),wahlEls=[...document.querySelectorAll('.wahl')];let letzte=-1;
function zeigen(){zahl.textContent=wahl.size?wahl.size+' ausgewählt':'Gesichter anklicken (Umschalt = Bereich)';
 document.querySelectorAll('.aktion').forEach(b=>b.disabled=!wahl.size);}
function setzen(f,an){const id=+f.dataset.id;if(an)wahl.add(id);else wahl.delete(id);f.classList.toggle('an',an);}
wahlEls.forEach((f,i)=>f.addEventListener('click',ev=>{const an=!wahl.has(+f.dataset.id);
 if(ev.shiftKey&&letzte>=0){const [a,b]=[Math.min(letzte,i),Math.max(letzte,i)];for(let k=a;k<=b;k++)setzen(wahlEls[k],an);}
 else setzen(f,an);letzte=i;zeigen();}));
document.getElementById('alle').addEventListener('click',()=>{wahlEls.forEach(f=>setzen(f,true));zeigen();});
document.getElementById('keine').addEventListener('click',()=>{wahlEls.forEach(f=>setzen(f,false));zeigen();});
async function ausfuehren(daten){document.querySelectorAll('.aktion').forEach(b=>b.disabled=true);
 const [ok,j]=await post('/api/gesichter_nennen',Object.assign({ids:[...wahl]},daten));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);zeigen();return;}meldung(j.meldung);setTimeout(()=>location.reload(),1200);}
document.getElementById('nennen').addEventListener('click',()=>{const n=document.getElementById('wname').value.trim();
 if(!n){meldung('Bitte einen Namen eingeben.',true);return;}ausfuehren({name:n});});
document.getElementById('wname').addEventListener('keydown',ev=>{if(ev.key==='Enter'&&wahl.size){ev.preventDefault();
 document.getElementById('nennen').click();}});
document.getElementById('bestaetigen').addEventListener('click',()=>ausfuehren({bestaetigen:true}));
document.getElementById('entfernen').addEventListener('click',()=>{
 if(confirm(wahl.size+' Gesichter entfernen? Sie werden keiner Person mehr zugeordnet.'))ausfuehren({});});
zeigen();
"""

JS_PERSONEN = """
const lk=document.getElementById('lernen');
if(lk)lk.addEventListener('click',async()=>{lk.disabled=true;const [ok,j]=await post('/api/lernen',{});lk.disabled=false;
 meldung(ok?j.meldung:(j.fehler||'Lernen fehlgeschlagen.'),!ok);if(ok)setTimeout(()=>location.reload(),4000);});
const ids=el=>el.dataset.ids.split(',').map(Number);
document.querySelectorAll('.pname').forEach(inp=>{
 const speichern=async()=>{if(inp.value===inp.dataset.alt)return;
  const [ok,j]=await post('/api/person',{ids:ids(inp),name:inp.value});
  if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);inp.value=inp.dataset.alt;return;}
  inp.dataset.alt=inp.value;meldung(j.meldung);if(j.neu_laden)setTimeout(()=>location.reload(),1200);};
 inp.addEventListener('change',speichern);
 inp.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}});});
document.querySelectorAll('.ignorieren').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/person',{ids:ids(k),ignorieren:k.dataset.an!=='1'});
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),800);}));
document.querySelectorAll('.loesen').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/person',{ids:[+k.dataset.id],name:''});
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),800);}));
const gesichtZiel=k=>({id:+k.dataset.id,pfad:k.dataset.pfad,kasten:k.dataset.kasten.split(',').map(Number)});
document.querySelectorAll('.gesicht .weg').forEach(k=>k.addEventListener('click',async()=>{
 const [ok,j]=await post('/api/gesicht',gesichtZiel(k));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}k.closest('.gesicht').remove();meldung(j.meldung);}));
document.querySelectorAll('.gesicht .nennen').forEach(k=>k.addEventListener('click',async()=>{
 const neu=prompt('Wer ist das? Gleicher Name = gleiche Person, auch auf Fotos aus anderen Lebensaltern.','');
 if(neu===null||!neu.trim())return;
 const [ok,j]=await post('/api/gesicht',Object.assign({name:neu.trim()},gesichtZiel(k)));
 if(!ok){meldung(j.fehler||'Fehlgeschlagen.',true);return;}meldung(j.meldung);setTimeout(()=>location.reload(),1200);}));
"""

JS_ALBEN = """
const ALB=D.alben||null,albLeisteEl=document.getElementById('albumleiste'),aktSel=document.getElementById('aktalbum'),
 albInfo=document.getElementById('albuminfo'),albAlle=document.getElementById('albumalle'),albRaus=document.getElementById('albumraus'),
 albbox=document.querySelector('.albbox'),lalben=lupe.querySelector('.lalben'),lalbKnopf=lupe.querySelector('.alb'),
 lmarkKnopf=lupe.querySelector('.almark');
let aktAlbum=null,albLetzte=-1,albBild=-1;
function albPfad(b){return b.ordner+'/'+b.id;}
function albName(id){const a=(ALB||[]).find(x=>x.id===id);return a?a.name:'';}
function albSortiert(ids){return (ALB||[]).filter(a=>ids.includes(a.id));}  // ALB kommt nach Namen sortiert
function albLink(a){const l=document.createElement('a');l.className='achip';l.textContent=a.name;
 l.href='/suche?q='+encodeURIComponent('Album '+a.name);l.title='Alle Fotos im Album „'+a.name+'“';return l;}
function feldAlben(i){const b=D.bilder[i],f=felder[i],s=f&&f.querySelector('.alben');if(!ALB||!s)return;
 const ids=b.a||[],an=aktAlbum!==null&&ids.includes(aktAlbum),k=document.createElement('button');
 f.classList.toggle('imalbum',an);k.type='button';
 if(aktAlbum!==null){k.className='knopf amark'+(an?' an':'');k.textContent=(an?'✓ ':'＋ ')+albName(aktAlbum);
  k.setAttribute('aria-pressed',an);k.title=(an?'Aus dem Album nehmen':'Ins Album aufnehmen')+
   ' – mit Umschalt alle Fotos bis zum zuletzt angeklickten';k.addEventListener('click',ev=>albumKlick(i,ev.shiftKey));}
 else{k.className='link aplus';k.textContent=ids.length?'＋':'＋ Album';k.title='Alben zuordnen';
  k.addEventListener('click',()=>albenOeffnen(i));}
 s.replaceChildren(...albSortiert(ids.filter(id=>id!==aktAlbum)).map(albLink),k);}  // aktives Album zeigt der Knopf
function albAlleZeichnen(){D.bilder.forEach((_,i)=>feldAlben(i));albLeiste();if(aktiv>=0)albenLupe();if(albenOffen())albenListe();}
function albUebernehmen(j){if(j.alben)ALB.splice(0,ALB.length,...j.alben);
 if(j.a)D.bilder.forEach(b=>{const p=albPfad(b);if(p in j.a)b.a=j.a[p];});
 if(j.neu_laden)setTimeout(()=>location.reload(),1500);
 albAuswahl();if(aktAlbum!==null&&!ALB.some(a=>a.id===aktAlbum))albAktiv(null);else albAlleZeichnen();}
async function albSetzen(daten){const [ok,j]=await post('/api/album_bild',daten);
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);return false;}albUebernehmen(j);meldung(j.meldung);return true;}
function albumKlick(i,bereich){if(aktAlbum===null||i<0)return;const an=!(D.bilder[i].a||[]).includes(aktAlbum);let von=i,bis=i;
 if(bereich&&albLetzte>=0){von=Math.min(albLetzte,i);bis=Math.max(albLetzte,i);}albLetzte=i;
 const pfade=[];for(let k=von;k<=bis;k++)pfade.push(albPfad(D.bilder[k]));albSetzen({album:aktAlbum,an,pfade});}
function albAuswahl(){if(!aktSel)return;
 aktSel.replaceChildren(new Option(ALB.length?'Fotos markieren für Album …':'Noch kein Album',''),
  ...ALB.map(a=>new Option(a.name+' ('+a.n+')',String(a.id))));aktSel.value=aktAlbum===null?'':String(aktAlbum);}
function albAktiv(id){aktAlbum=id!==null&&(ALB||[]).some(a=>a.id===id)?id:null;albLetzte=-1;
 try{if(aktAlbum===null)localStorage.removeItem('bestofAlbum');else localStorage.setItem('bestofAlbum',String(aktAlbum));}catch(_){}
 if(aktSel)aktSel.value=aktAlbum===null?'':String(aktAlbum);if(albLeisteEl)albLeisteEl.classList.toggle('aktiv',aktAlbum!==null);
 albAlleZeichnen();}
function albLeiste(){if(!albLeisteEl)return;const an=aktAlbum!==null;albAlle.hidden=albRaus.hidden=!an;
 if(!an){albInfo.textContent=ALB.length?'Album wählen, dann Fotos mit ＋ hinzufügen.':'Neues Album anlegen, dann Fotos mit ＋ hinzufügen.';return;}
 const n=D.bilder.filter(b=>(b.a||[]).includes(aktAlbum)).length,alle=D.suche?D.treffer:D.bilder.length,mehr=alle>D.bilder.length;
 albInfo.textContent=n+' von '+D.bilder.length+' hier im Album. ＋ unter dem Foto oder Taste A in der Lupe, Umschalt = Bereich.';
 albAlle.textContent=mehr?'Alle '+alle+' Treffer hinzufügen':'Alle '+alle+' hinzufügen';
 albRaus.textContent=mehr?'Alle Treffer entfernen':'Alle entfernen';}
function albenLupe(){if(!ALB||aktiv<0)return;const ids=D.bilder[aktiv].a||[],an=aktAlbum!==null&&ids.includes(aktAlbum);
 lalben.replaceChildren(...albSortiert(ids).map(albLink));lalben.hidden=!ids.length;
 lalbKnopf.textContent='Alben'+(ids.length?' ('+ids.length+')':'');lmarkKnopf.hidden=aktAlbum===null;
 if(aktAlbum!==null){lmarkKnopf.textContent=(an?'✓ ':'＋ ')+albName(aktAlbum);lmarkKnopf.classList.toggle('an',an);
  lmarkKnopf.setAttribute('aria-pressed',an);}}
function albumTaste(){if(!ALB||aktiv<0)return;if(aktAlbum!==null)albumKlick(aktiv,false);else albenOeffnen(aktiv);}
function albenOffen(){return !!albbox&&!albbox.hidden;}
function albenOeffnen(i){if(!ALB||!albbox||i<0)return;albBild=i;albenListe();albbox.hidden=false;
 (albbox.querySelector('.aliste input')||albbox.querySelector('.aname')).focus();}
function albenZu(){if(!albenOffen())return;albbox.hidden=true;const i=albBild;albBild=-1;
 const k=aktiv>=0?lalbKnopf:(felder[i]&&felder[i].querySelector('.alben button'));if(k)k.focus({preventScroll:true});}
function albenListe(){const b=D.bilder[albBild];if(!b)return;const ids=b.a||[],liste=albbox.querySelector('.aliste');
 albbox.querySelector('.atitel').textContent='Alben für „'+b.name+'“';
 if(!ALB.length){const p=document.createElement('p');p.className='leise';p.textContent='Noch kein Album – unten eins anlegen.';
  liste.replaceChildren(p);return;}
 liste.replaceChildren(...ALB.map(a=>{const l=document.createElement('label'),c=document.createElement('input'),
  n=document.createElement('span');c.type='checkbox';c.checked=ids.includes(a.id);
  c.addEventListener('change',()=>albBildSetzen(a.id,c.checked,c));n.className='leise';n.textContent=a.n;
  l.append(c,a.name,n);return l;}));}
async function albBildSetzen(id,an,c){const b=D.bilder[albBild];if(!b)return;
 if(!await albSetzen({album:id,an,pfade:[albPfad(b)]})&&c)c.checked=!an;}
if(albbox){albbox.querySelector('.alneu').addEventListener('submit',async ev=>{ev.preventDefault();
  const inp=albbox.querySelector('.aname'),name=inp.value.trim();if(!name)return;
  const [ok,j]=await post('/api/album',{aktion:'neu',name});if(!ok){meldung(j.fehler||'Anlegen fehlgeschlagen.',true);return;}
  inp.value='';albUebernehmen(j);await albBildSetzen(j.album,true);});
 albbox.querySelector('.azu').addEventListener('click',albenZu);
 albbox.addEventListener('keydown',ev=>{if(ev.key==='Escape'){ev.preventDefault();ev.stopPropagation();albenZu();}});}
if(albLeisteEl){aktSel.addEventListener('change',()=>albAktiv(aktSel.value?+aktSel.value:null));
 document.getElementById('albumneu').addEventListener('click',async()=>{
  const name=prompt('Name des neuen Albums, z. B. Urlaub 2023:','');if(name===null||!name.trim())return;
  const [ok,j]=await post('/api/album',{aktion:'neu',name});if(!ok){meldung(j.fehler||'Anlegen fehlgeschlagen.',true);return;}
  albUebernehmen(j);albAktiv(j.album);meldung(j.meldung+' Jetzt Fotos mit ＋ hinzufügen.');});
 const alleSetzen=an=>{const wo=D.suche?{suche:D.suche}:{ordner:D.ordner},n=D.suche?D.treffer:D.bilder.length,name=albName(aktAlbum);
  if(an?n>50&&!confirm(n+' Fotos ins Album „'+name+'“ aufnehmen?'):!confirm('Alle '+n+' Fotos '+
   (D.suche?'dieses Filters':'dieses Ordners')+' aus dem Album „'+name+'“ nehmen? Die Fotos selbst bleiben.'))return;
  albSetzen(Object.assign({album:aktAlbum,an},wo));};
 albAlle.addEventListener('click',()=>alleSetzen(true));albRaus.addEventListener('click',()=>alleSetzen(false));}
lalbKnopf.addEventListener('click',()=>albenOeffnen(aktiv));lmarkKnopf.addEventListener('click',()=>albumKlick(aktiv,false));
if(ALB){let gemerkt=null;try{gemerkt=localStorage.getItem('bestofAlbum');}catch(_){}
 albAuswahl();albAktiv(gemerkt?+gemerkt:null);}
else{lalbKnopf.hidden=lmarkKnopf.hidden=lalben.hidden=true;}
"""

JS_ALBENSEITE = """
const neuForm=document.getElementById('neualbum');
neuForm.addEventListener('submit',async ev=>{ev.preventDefault();const inp=neuForm.querySelector('input'),name=inp.value.trim();
 if(!name){meldung('Bitte einen Namen eingeben.',true);return;}
 const [ok,j]=await post('/api/album',{aktion:'neu',name});if(!ok){meldung(j.fehler||'Anlegen fehlgeschlagen.',true);return;}
 try{localStorage.setItem('bestofAlbum',String(j.album));}catch(_){}
 meldung(j.meldung+' Es ist zum Markieren gewählt: Ordner öffnen und Fotos mit ＋ hinzufügen.');setTimeout(()=>location.reload(),2200);});
document.querySelectorAll('.aname').forEach(inp=>{
 const speichern=async()=>{const name=inp.value.trim();if(name===inp.dataset.alt)return;
  const [ok,j]=await post('/api/album',{aktion:'umbenennen',id:+inp.dataset.id,name});
  if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);inp.value=inp.dataset.alt;return;}
  inp.value=inp.dataset.alt=j.name;meldung(j.meldung);setTimeout(()=>location.reload(),1200);};
 inp.addEventListener('change',speichern);
 inp.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}
  else if(ev.key==='Escape'){inp.value=inp.dataset.alt;inp.blur();}});});
document.querySelectorAll('.amarkieren').forEach(k=>k.addEventListener('click',()=>{
 try{localStorage.setItem('bestofAlbum',k.dataset.id);}catch(_){}location.href='/';}));
document.querySelectorAll('.aloeschen').forEach(k=>k.addEventListener('click',async()=>{
 if(!confirm('Album „'+k.dataset.name+'“ löschen? Die Fotos bleiben im Archiv, nur diese Zuordnung verschwindet.'))return;
 const [ok,j]=await post('/api/album',{aktion:'loeschen',id:+k.dataset.id});
 if(!ok){meldung(j.fehler||'Löschen fehlgeschlagen.',true);return;}
 try{if(localStorage.getItem('bestofAlbum')===k.dataset.id)localStorage.removeItem('bestofAlbum');}catch(_){}
 meldung(j.meldung);setTimeout(()=>location.reload(),1200);}));
"""


def json_im_html(daten):
    return json.dumps(daten, ensure_ascii=True).replace("</", "<\\/")


def stift_pfad(saat):
    """Leicht unregelmäßiger, von Hand gezogener Rahmen (Fettstift auf dem Kontaktbogen)."""
    r = random.Random(hashlib.sha1(saat.encode("utf-8", "surrogateescape")).digest())

    def j(v):
        return v + r.uniform(-1.8, 1.8)

    punkte = [(j(4), j(5)), (j(50), j(3)), (j(96), j(4.5)), (j(97.5), j(50)), (j(96), j(96)),
              (j(50), j(97.5)), (j(3.5), j(96)), (j(2.5), j(50)), (j(5), j(7)), (j(22), j(3.5))]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in punkte)


STERN_WEG = "M12 2.8 14.5 9.6 21.7 9.9 16 14.3 18 21.2 12 17.2 6 21.2 8 14.3 2.3 9.9 9.5 9.6z"
STERN_KNOPF = (f'<button class="knopf stern" type="button" aria-pressed="false" aria-label="Stern">'
               f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{STERN_WEG}"/></svg></button>')


def sterne_svg(n):
    """Auf der Ordnerkachel: ein kleiner Stern je Bild mit Stern (höchstens drei gezeichnet)."""
    if not n:
        return ""
    k = min(n, 3)
    wege = "".join(f'<path transform="translate({24 * i} 0)" d="{STERN_WEG}"/>' for i in range(k))
    return (f'<svg class="sterne" width="{14 * k}" height="14" viewBox="0 0 {24 * k} 24" role="img" '
            f'aria-label="{n} mit Stern">{wege}</svg>')


def status_text(app):
    if not app.indexer:
        return "", False
    s = app.indexer.status
    rechenwerk = app.indexer.rechenwerk()  # GPU oder CPU – leer, solange die Gesichtserkennung aus ist oder lädt
    if s["phase"] == "Index" and s["gesamt"]:
        return (f"Index: {s['fertig']} von {s['gesamt']} Bildern gelesen – Filter noch unvollständig."
                + (f" {rechenwerk}." if rechenwerk else "")), True
    if s["phase"] not in ("fertig", "Index"):
        return f"Index: {s['phase']} …", True
    zahlen = app.index.einer("SELECT (SELECT COUNT(*) FROM bild), (SELECT COUNT(*) FROM gesicht)")
    text = f"Index: {zahlen[0]} Bilder"
    if app.indexer.gesichter_aktiv:
        text += f", {zahlen[1]} Gesichter, {len(personen_gruppen(app.index, 2, False))} Personen"
    letzte = s["meldungen"][-1] if s["meldungen"] else ""
    if "aus" in letzte and not letzte.startswith(("Gesichtserkennung auf der", "GPU-Fehler")):
        text += f". {letzte}"
    if rechenwerk:
        text += f". {rechenwerk}"
    return text, False


def kopf(app, aktiv="", inhalt_titel="", suchtext=""):
    text, laeuft = status_text(app)
    navi = [("ordner", "/", "Ordner")]
    if app.import_erlaubt:
        navi.append(("import", "/import", "Import"))
    if app.index:
        navi.append(("alben", "/alben", "Alben"))
        navi.append(("personen", "/personen", "Personen"))
    links = "".join(f'<a href="{url}"{" aria-current=page" if k == aktiv else ""}>{t}</a>' for k, url, t in navi)
    suche = ""
    if app.index:
        suche = (f'<form class="suche" action="/suche" role="search"><input name="q" value="{e(suchtext)}" '
                 f'placeholder="Filter, z. B. 2023, Leipzig, Anna" aria-label="Filter"><button class="knopf">Filtern</button>'
                 f'<a class="knopf" href="/suche?{urlencode({"q": ALLE_FOTOS})}" title="Alle Fotos nach Datum – '
                 f'zum Einordnen in Alben und Jahre">{ALLE_FOTOS}</a></form>')
    return (f'<header class="kopf"><a class="archiv" href="/">{e(os.path.basename(app.archiv.pfad))}</a>'
            f'{inhalt_titel}<nav class="navi" aria-label="Bereiche">{links}</nav>{suche}'
            f'<p class="status" data-laeuft="{1 if laeuft else 0}">{e(text)}</p></header>')


def seite(titel, inhalt, skript=""):
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(titel)}</title><link rel="icon" href="{FAVICON}"><style>{CSS}</style></head>'
            f'<body>{inhalt}<div class="meldung" role="status" aria-live="polite" hidden></div>'
            f'<script>{JS_GEMEINSAM}{skript}</script></body></html>').encode("utf-8", "surrogateescape")


def bild_daten(app, ordner, bilder):
    """Metadaten und Gesichter aus dem Index für die Bilder eines oder mehrerer Ordner."""
    meta, gesichter = {}, {}
    if not app.index or not bilder:
        return meta, gesichter
    ordner_menge = sorted({o for o, _ in bilder})
    platz = ",".join("?" * len(ordner_menge))
    for z in app.index.q(f"SELECT pfad, zeit, ort, ort_km, lat, lon, jahr, jahr_man, gesichter, fehler, breite, hoehe "
                         f"FROM bild_eff WHERE ordner IN ({platz})", ordner_menge):
        meta[z[0]] = z[1:]
    namen = personen_namen(app.index)
    for gid, pfad, x, y, w, h, person in app.index.q(
            f"SELECT id, pfad, x, y, w, h, person FROM gesicht WHERE ordner IN ({platz}) ORDER BY x", ordner_menge):
        if person is None or person not in namen or namen[person][1]:
            continue
        gesichter.setdefault(pfad, []).append([round(x, 4), round(y, 4), round(w, 4), round(h, 4), person,
                                               namen[person][0], gid, namen[person][2]])
    return meta, gesichter


def bogen_html(app, eintraege, einordner):
    """eintraege: [(ordner, name, mtime, groesse)] -> (HTML der Felder, Bilddaten für JS)."""
    meta, gesichter = bild_daten(app, None, [(o, n) for o, n, *_ in eintraege])
    alben = alben_von(app.index, [f"{o}/{url_id(n)}" for o, n, *_ in eintraege]) if app.index else {}
    masse = []
    for o, name, mt, groesse in eintraege:  # Auflösung: aus dem Index, sonst Dateikopf lesen
        m = meta.get(f"{o}/{url_id(name)}")
        w, h = (m[9], m[10]) if m and m[9] else bildmasse(os.path.join(app.archiv.pfad, o, name), groesse, mt)
        masse.append((w, h))
    pixel = [w * h for w, h in masse if w]
    # höchste Auflösung hervorheben – nur wenn sich die Bilder des Ordners darin unterscheiden
    spitze = max(pixel) if einordner and len(pixel) > 1 and min(pixel) < max(pixel) else 0
    felder, daten = [], []
    for i, (o, name, mt, groesse) in enumerate(eintraege):
        uid = url_id(name)
        rel = f"{o}/{uid}"
        m = meta.get(rel)
        zeit, ort, km, lat, lon, ja, jm, n_ges, fehler, _, _ = m if m else (None,) * 11
        w, h = masse[i]
        roh = app.archiv.roh(o).get(os.path.splitext(name)[0].casefold())
        px = f"{w} × {h}" if w else "Auflösung unbekannt"
        technik = " · ".join(t for t in (px, groesse_text(groesse), f"NEF {groesse_text(roh[1])}" if roh else "") if t)
        oben = spitze and w and w * h == spitze
        such_stand = "fehler" if fehler else ("offen" if n_ges is None else "ok")
        jahr = jm if jm is not None else ja
        f = gesichter.get(rel, [])
        benannt = sorted({g[5] for g in f if not g[5].startswith("Person ")})
        monat = MONATE[int(zeit[5:7])] if zeit else ""
        kurz = ", ".join(t for t in ("" if jm is not None else monat, ort_text(ort, km)) if t)
        meta_html = e(kurz) + (f'{" – " if kurz else ""}<b>{e(", ".join(benannt))}</b>' if benannt else "")
        jahr_html = (f'<input class="jahr{" manuell" if jm is not None else ""}" value="{jahr or ""}" inputmode="numeric" '
                     f'maxlength="4" placeholder="Jahr" aria-label="Jahr"><button class="knopf jsetz" type="button" '
                     f'hidden></button>' if app.index else "")
        nr = "" if einordner else f'<a class="ordnernr" href="/o/{o}" title="Ordner öffnen">{o}</a>'
        felder.append(
            f'<figure class="feld" data-id="{uid}"><div class="zelle">'
            f'<button class="rahmen" type="button" aria-label="{e(name)} groß ansehen">'
            f'<img loading="lazy" decoding="async" src="/t/{o}/{uid}?v={mt}" alt=""></button>'
            f'<svg class="fettstift" viewBox="0 0 100 100" aria-hidden="true">'
            f'<path pathLength="100" d="{stift_pfad(f"{o}{name}")}"/></svg>'
            f'<span class="buchstabe" aria-hidden="true"></span>{nr}</div>'
            f'<figcaption><span class="lfd">{i + 1}</span><span class="dateiname" title="{e(name)}">{e(name)}</span>'
            f'{STERN_KNOPF}'
            f'<span class="technik{" spitze" if oben else ""}"'
            + (' title="Höchste Auflösung in diesem Ordner"' if oben else "") + f'>{e(technik)}</span>'
            f'<span class="meta">{jahr_html}<span class="mtext">{meta_html}</span></span>'
            + ('<span class="alben"></span>' if app.index else "") + '</figcaption></figure>')
        karte = (f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=14/{lat:.5f}/{lon:.5f}"
                 if lat is not None else "")
        daten.append({"id": uid, "ordner": o, "name": anzeige(name), "g": f"/g/{o}/{uid}?v={mt}",
                      "o": f"/orig/{o}/{uid}", "z": zeit_text(zeit), "zm": monat, "ol": ort_text(ort, km, kurz=False),
                      "ok": ort_text(ort, km), "j": jahr, "jm": jm is not None, "k": karte, "f": f, "fs": such_stand,
                      "t": technik, "a": alben.get(rel, [])})
    return "".join(felder), daten


LUPE_HTML = ('<div class="lupe" hidden role="dialog" aria-label="Lupe"><div class="flaeche"><img alt="">'
             '<p class="ghinweis" hidden></p>'
             '<div class="nennbox" hidden role="dialog" aria-label="Gesicht benennen">'
             '<label>Wer ist das?<input class="nname" list="namenliste" maxlength="60" autocomplete="off" '
             'spellcheck="false"></label><div class="nknoepfe"><button class="knopf haupt" type="button"></button>'
             '<button class="knopf neben" type="button"></button></div><div class="nfuss">'
             '<button class="link kein" type="button" title="Falsch erkannt, z. B. Muster oder Foto im Foto">Kein Gesicht'
             '</button><button class="link abbr" type="button">Abbrechen</button></div></div>'
             '<datalist id="namenliste"></datalist></div>'
             '<div class="leiste"><span class="wo"></span>'
             '<input class="jahr" inputmode="numeric" maxlength="4" placeholder="Jahr" aria-label="Jahr (Taste J)">'
             '<button class="knopf jsetz" type="button" hidden></button>'
             '<span class="text"><span class="wer"></span>'
             '<span class="info"></span><span class="lalben" hidden></span></span>'
             '<button class="knopf zurueck" type="button" aria-label="Voriges Bild">‹</button>'
             '<button class="knopf vor" type="button" aria-label="Nächstes Bild">›</button>'
             + STERN_KNOPF +
             '<button class="knopf almark" type="button" aria-pressed="false" title="Taste A" hidden></button>'
             '<button class="knopf alb" type="button" title="Alben zuordnen (Taste A)">Alben</button>'
             '<button class="knopf gz" type="button" title="Taste G">Gesichter</button>'
             '<a class="knopf karte" target="_blank" rel="noopener noreferrer">Karte</a>'
             '<a class="knopf orig" target="_blank" rel="noopener">Original</a>'
             '<button class="knopf zu" type="button">Schließen</button></div></div>')

# Leiste über dem Bogen: Fotos für ein Album markieren und Jahr per Klick setzen
ALBUMLEISTE = ('<div class="albumleiste" id="albumleiste"><select id="aktalbum" aria-label="Album zum Markieren"></select>'
               '<button class="knopf" id="albumneu" type="button">Neues Album</button>'
               '<span class="leise" id="albuminfo"></span>'
               '<button class="knopf" id="albumalle" type="button" hidden></button>'
               '<button class="knopf" id="albumraus" type="button" hidden></button>'
               '<span class="jahrwerk"><label class="leise" for="setzjahr">Jahr per Klick</label>'
               '<input class="jahr" id="setzjahr" inputmode="numeric" maxlength="4" placeholder="Jahr" autocomplete="off" '
               'title="Jahr eintippen, dann unter den Fotos auf → Jahr klicken (Umschalt = alle bis zum zuletzt '
               'angeklickten). Esc = beenden.">'
               '<button class="link" id="setzjahraus" type="button" hidden title="Jahr per Klick beenden" '
               'aria-label="Jahr per Klick beenden">✕</button>'
               '<span class="leise" id="jahrinfo" hidden>→ unter den Fotos, Umschalt = Bereich</span></span></div>')

ALBBOX = ('<div class="albbox" hidden role="dialog" aria-label="Alben zuordnen"><p class="atitel"></p>'
          '<div class="aliste"></div><form class="alneu"><input class="aname" maxlength="60" autocomplete="off" '
          'placeholder="Neues Album" aria-label="Neues Album anlegen und zuordnen"><button class="knopf">Anlegen</button>'
          '</form><div class="nfuss"><a class="link" href="/alben">Alben verwalten</a>'
          '<button class="link azu" type="button">Fertig</button></div></div>')


def bogen_hilfe(app):
    """Hilfezeile unter dem Kontaktbogen (Ordner und Filter)."""
    text = (f'Bild anklicken zum Vergrößern. ☆ unter dem Bild = Stern: kopiert es nach BestOf (je Ordner höchstens '
            f'{app.auswahl.max_best}). In der Lupe: <kbd>←</kbd> <kbd>→</kbd> blättern, <kbd>Leertaste</kbd> oder '
            f'<kbd>S</kbd> Stern, ')
    if not app.index:
        return f'<p class="hilfe">{text}<kbd>Esc</kbd> schließen.</p>'
    return (f'<p class="hilfe">{text}<kbd>G</kbd> Gesichter (Namensschild anklicken = benennen, fehlt eins: ins '
            'Gesicht klicken), <kbd>J</kbd> Jahr ändern, <kbd>A</kbd> Album, <kbd>Esc</kbd> schließen. '
            'Jahr korrigieren: ins Jahresfeld tippen, Enter; leeren = Jahr aus der Datei. Für viele Fotos: oben bei '
            '„Jahr per Klick“ das Jahr eintippen, dann → Jahr unter den Fotos anklicken (Umschalt = Bereich). '
            'Alben: oben ein Album wählen, dann ＋ unter den Fotos (Umschalt = Bereich); ein Album unter einem Foto '
            'anklicken zeigt alle Fotos darin. „Alle Fotos“ oben zeigt das ganze Archiv nach Datum.</p>')


def seiten_nav(seite_nr, seiten, link):
    """Seitenleiste 1 … 4 5 [6] 7 8 … 20; link(n) liefert die Adresse von Seite n."""
    if seiten <= 1:
        return ""
    nummern = sorted({1, seiten, *range(max(1, seite_nr - 3), min(seiten, seite_nr + 3) + 1)})
    teile, letzte = [], 0
    for n in nummern:
        if n - letzte > 1:
            teile.append("<span aria-hidden='true'>…</span>")
        teile.append(f"<span aria-current='page'>{n}</span>" if n == seite_nr else f'<a href="{e(link(n))}">{n}</a>')
        letzte = n
    return f'<nav class="seiten" aria-label="Seiten">{"".join(teile)}</nav>'


def ordner_zusammen(app, ordner):
    """Frühestes (wirksames) Datum und häufigster Ort eines Ordners, z. B. „März 2021, Leipzig“."""
    if not app.index:
        return ""
    z = app.index.einer("SELECT MIN(sortzeit), (SELECT ort FROM bild WHERE ordner=? AND ort IS NOT NULL "
                        "GROUP BY ort ORDER BY COUNT(*) DESC LIMIT 1) FROM bild_eff WHERE ordner=?", (ordner, ordner))
    return ", ".join(t for t in (datum_kurz(z[0]), z[1] or "") if t) if z else ""


def ordner_seite(app, ordner):
    app.auswahl.bereinigen(ordner)
    liste = app.archiv.ordner()
    bilder = app.archiv.bilder(ordner)
    pos = liste.index(ordner)
    zurueck = liste[pos - 1] if pos > 0 else None
    weiter = liste[pos + 1] if pos + 1 < len(liste) else None
    seite_nr = pos // app.pro_seite + 1
    felder, daten = bogen_html(app, [(ordner, n, mt, g) for n, g, mt in bilder], einordner=True)
    zusammen = ordner_zusammen(app, ordner)
    weg = []
    if zurueck:
        weg.append(f'<a class="knopf" href="/o/{zurueck}" title="Taste ←">Ordner {zurueck}</a>')
    if weiter:
        weg.append(f'<a class="knopf" href="/o/{weiter}" title="Taste →">Ordner {weiter}</a>')
    weg.append(f'<a class="knopf" href="/weiter/{ordner}" title="Taste N">Nächster ohne Stern</a>')
    ordnerjahr = ('<form class="ordnerjahr" id="ordnerjahr"><input class="jahr" inputmode="numeric" maxlength="4" '
                  'placeholder="Jahr" aria-label="Jahr für alle Bilder dieses Ordners" title="Jahr für alle Bilder dieses '
                  'Ordners setzen. Leer lassen = alle Korrekturen im Ordner entfernen.">'
                  '<button class="knopf">für alle Bilder</button></form>' if app.index and bilder else "")
    titel = (f'<div class="titel"><h1>{ordner}</h1><div><p id="info"></p><p class="ziel" id="ziel"></p>'
             f'<p class="leise" id="zusammen">{e(zusammen)}</p></div></div>'
             f'<nav class="weg" aria-label="Ordner wechseln">{"".join(weg)}</nav>{ordnerjahr}')
    inhalt = kopf(app, "ordner", titel)
    if not bilder:
        inhalt += '<p class="leer">In diesem Ordner liegen keine JPG- oder PNG-Bilder.</p>'
    else:
        inhalt += (ALBUMLEISTE if app.index else "") + f'<main class="bogen">{felder}</main>' + bogen_hilfe(app)
    inhalt += LUPE_HTML + (ALBBOX if app.index else "")
    markiert = app.auswahl.markiert(ordner)
    js = {"einordner": True, "ordner": ordner, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {ordner: [url_id(m) for m in markiert]},
          "ziele": {ordner: {url_id(m): z for m, z in app.auswahl.ziele(ordner).items()}},
          "zurueck": f"/o/{zurueck}" if zurueck else None, "weiter": f"/o/{weiter}" if weiter else None,
          "offen": f"/weiter/{ordner}", "uebersicht": f"/?seite={seite_nr}",
          "alben": alben_liste(app.index) if app.index else None}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{ordner} – BestOf", inhalt, JS_BOGEN + JS_ALBEN)


def such_seite(app, text, seite_nr):
    zeilen, erklaerung = suche_ausfuehren(app, text) if text.strip() else ([], [])
    gesamt = len(zeilen)
    pro = 240
    seiten = max(1, -(-gesamt // pro))
    seite_nr = min(max(1, seite_nr), seiten)
    teil = zeilen[(seite_nr - 1) * pro: seite_nr * pro]
    eintraege = []
    for o, uid, *_ in teil:
        treffer = app.archiv.datei(o, name_aus_id(uid))
        if treffer:
            eintraege.append((o, name_aus_id(uid), treffer[2], treffer[1]))
    felder, daten = bogen_html(app, eintraege, einordner=False)
    chips = "".join(f'<span class="chip">{e(t)}</span>' for t in erklaerung)
    stand = bilder_text(gesamt) + (f", Seite {seite_nr} von {seiten}" if seiten > 1 else "")
    titel = f'<div class="titel"><div><p id="info">{stand}</p><p class="ziel" id="ziel"></p></div></div>'
    inhalt = kopf(app, "", titel, text)
    if erklaerung:
        inhalt += f'<div class="filter" aria-label="Erkannter Filter">{chips}</div>'
    if not text.strip():
        inhalt += ('<p class="leer">Geben Sie Begriffe mit Komma getrennt ein, z. B. 2023, Leipzig, Anna – '
                   'oder „Alle Fotos“ für das ganze Archiv.</p>')
    elif not eintraege:
        inhalt += '<p class="leer">Keine Fotos passen zu allen Begriffen. Entfernen Sie einen Begriff oder prüfen Sie die Schreibweise.</p>'
    else:
        inhalt += ((ALBUMLEISTE if app.index else "") + f'<main class="bogen">{felder}</main>'
                   + seiten_nav(seite_nr, seiten, lambda n: "/suche?" + urlencode({"q": text, "seite": n}))
                   + bogen_hilfe(app))
    inhalt += LUPE_HTML + (ALBBOX if app.index else "")
    ordner_menge = sorted({o for o, *_ in eintraege})
    js = {"einordner": False, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {o: [url_id(m) for m in app.auswahl.markiert(o)] for o in ordner_menge},
          "ziele": {o: {url_id(m): z for m, z in app.auswahl.ziele(o).items()} for o in ordner_menge},
          "alben": alben_liste(app.index) if app.index else None, "suche": text.strip() or None, "treffer": gesamt}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{text} – BestOf", inhalt, JS_BOGEN + JS_ALBEN)


def personen_gruppen(index, mindest, ignorierte):
    """Gruppen mit gleichem Namen gehören zu einer Person (z. B. Kinder- und Erwachsenenfotos).
    Rückgabe: [(name oder None, [(id, anzahl), …])], benannte zuerst, dann nach Größe."""
    gruppen = {}
    for pid, name, anzahl in index.q("SELECT id, name, anzahl FROM person WHERE ignoriert = ? AND anzahl > 0",
                                     (1 if ignorierte else 0,)):
        schluessel = name.casefold() if name else f"#{pid}"
        eintrag = gruppen.setdefault(schluessel, [name, []])
        eintrag[1].append((pid, anzahl))
    liste = [(name, sorted(m, key=lambda x: -x[1])) for name, m in gruppen.values()
             if sum(a for _, a in m) >= mindest]
    liste.sort(key=lambda g: (g[0] is None, (g[0] or "").casefold(), -sum(a for _, a in g[1])))
    return liste


def personen_seite(app, alle, ignorierte):
    inhalt = kopf(app, "personen", '<div class="titel"><h1>Personen</h1></div>')
    if not app.indexer or not app.indexer.gesichter_aktiv:
        meldungen = " ".join(app.indexer.status["meldungen"][-2:]) if app.indexer else ""
        inhalt += f'<p class="leer">Die Gesichtserkennung ist aus. {e(meldungen)}</p>'
        return seite("Personen – BestOf", inhalt)
    personen = personen_gruppen(app.index, 1 if alle else 2, ignorierte)
    schalter = [f'<a class="knopf" href="/personen{"" if alle else "?alle=1"}">'
                f'{"Nur Personen mit mehreren Gesichtern" if alle else "Auch einzelne Gesichter zeigen"}</a>',
                f'<a class="knopf" href="/personen{"" if ignorierte else "?ignorierte=1"}">'
                f'{"Zurück zu den Personen" if ignorierte else "Ignorierte Personen"}</a>']
    inhalt += f'<div class="filter">{"".join(schalter)}</div>'
    inhalt += (f'<p class="lernstand"><span>{e(lern_zeile(app))}</span>'
               f'<button class="knopf" id="lernen" type="button" title="Schwelle und Abstand aus Ihren Korrekturen '
               f'und Bestätigungen neu einstellen, eindeutige Fälle umsortieren">Jetzt lernen</button></p>')
    if app.indexer.rechenwerk():
        inhalt += f'<p class="lernstand"><span>{e(app.indexer.rechenwerk(lang=True))}</span></p>'
    if not personen:
        inhalt += ('<p class="leer">Noch keine Personen. Der Index sucht im Hintergrund nach Gesichtern; '
                   'diese Seite füllt sich, sobald er Fotos gelesen hat.</p>')
    teile = []
    for name, mitglieder in personen:
        ids = [pid for pid, _ in mitglieder]
        platz = ",".join("?" * len(ids))
        fotos = app.index.einer(f"SELECT COUNT(DISTINCT pfad) FROM gesicht WHERE person IN ({platz})", ids)[0]
        such = urlencode({"q": name or f"Person {ids[0]}"})
        id_text = ",".join(map(str, ids))
        mehrere = len(mitglieder) > 1
        zeilen = []
        for k, (pid, anzahl) in enumerate(mitglieder, 1):
            beispiele = app.index.q("SELECT g.id, b.mtime || '.' || CAST(g.x * 10000 AS INT) || '.' || CAST(g.y * 10000 AS INT) "
                                    "|| '.' || CAST(g.w * 10000 AS INT), g.pfad, g.x, g.y, g.w, g.h FROM gesicht g "
                                    "JOIN bild b ON b.pfad=g.pfad WHERE g.person=? ORDER BY g.pixel DESC LIMIT ?",
                                    (pid, 10 if mehrere else 14))
            gesichter = "".join(
                f'<figure class="gesicht"><a href="/suche?{such}"><img loading="lazy" src="/f/{gid}?v={mt}" alt=""></a>'
                f'<button class="nennen" type="button" data-id="{gid}" data-pfad="{e(gp)}" data-kasten="{gx},{gy},{gw},{gh}" '
                f'title="Dieses Gesicht ist jemand anderes" aria-label="Gesicht benennen">✎</button>'
                f'<button class="weg" type="button" data-id="{gid}" data-pfad="{e(gp)}" data-kasten="{gx},{gy},{gw},{gh}" '
                f'title="Kein Gesicht oder unbekannt – entfernen" aria-label="Gesicht entfernen">✕</button></figure>'
                for gid, mt, gp, gx, gy, gw, gh in beispiele)
            kopfzeile = (f'<div class="gkopf"><span>Gruppe {k}, {anzahl} {"Gesicht" if anzahl == 1 else "Gesichter"}</span>'
                         f'<a class="knopf" href="/personen?gruppe={pid}" title="Alle Gesichter dieser Gruppe, untypische zuerst">'
                         f'Alle prüfen</a><button class="knopf loesen" type="button" data-id="{pid}" '
                         f'title="Name entfernen – die Gruppe wird wieder eine eigene Person">Gruppe lösen</button></div>'
                         if mehrere else "")
            zeilen.append(f'<div class="gruppe" id="p{pid}">{kopfzeile}<div class="gesichter">{gesichter}</div></div>')
        hinweis = (f'<span class="hinweis">{len(mitglieder)} Gruppen, z. B. Fotos aus verschiedenen Jahren</span>'
                   if mehrere else "")
        teile.append(f'<section class="person"><div class="pkopf">'
                     f'<input class="pname" data-ids="{id_text}" data-alt="{e(name or "")}" value="{e(name or "")}" '
                     f'placeholder="Person {ids[0]}" aria-label="Name für Person {ids[0]}">'
                     f'<span class="leise">{bilder_text(fotos)}</span>{hinweis}'
                     f'<a class="knopf" href="/suche?{such}">Fotos zeigen</a>'
                     + ("" if mehrere else f'<a class="knopf" href="/personen?gruppe={ids[0]}" '
                                           f'title="Alle Gesichter, untypische zuerst – dort stecken meist Verwechslungen">'
                                           f'Alle {mitglieder[0][1]} prüfen</a>') +
                     f'<button class="knopf ignorieren" type="button" data-ids="{id_text}" data-an="{1 if ignorierte else 0}">'
                     f'{"Wieder zeigen" if ignorierte else "Ignorieren"}</button></div>{"".join(zeilen)}</section>')
    inhalt += (f'<main class="personen">{"".join(teile)}</main>'
               '<p class="hilfe">Namen eintippen und Enter drücken. Gleicher Name bei mehreren Gruppen = dieselbe Person, '
               'z. B. Kinder- und Erwachsenenfotos; die Gruppen bleiben getrennt und lassen sich mit „Gruppe lösen“ wieder '
               'trennen. ✎ ordnet ein einzelnes Gesicht jemand anderem zu – sehr ähnliche Gesichter derselben Gruppe '
               'wandern mit. ✕ entfernt es.</p>')
    return seite("Personen – BestOf", inhalt, JS_PERSONEN)


def alben_seite(app):
    """Alben anlegen, umbenennen, löschen; je Album Titelbild (frühestes Foto), Anzahl und Weg zu den Fotos."""
    alben = alben_liste(app.index)
    titelbilder = {}
    for album, ordner, datei, mt in app.index.q(
            "SELECT ab.album, b.ordner, b.datei, b.mtime FROM album_bild ab JOIN bild_eff b ON b.pfad = ab.pfad "
            "ORDER BY b.sortzeit IS NULL, b.sortzeit, b.pfad"):
        titelbilder.setdefault(album, (ordner, datei, mt))
    ohne = app.index.einer("SELECT COUNT(*) FROM bild WHERE pfad NOT IN (SELECT pfad FROM album_bild)")[0]
    titel = (f'<div class="titel"><h1>Alben</h1><div><p>{len(alben)} {"Album" if len(alben) == 1 else "Alben"}</p>'
             f'<p><a href="/suche?{urlencode({"q": "ohne Album"})}">{bilder_text(ohne)} ohne Album</a></p></div></div>')
    inhalt = kopf(app, "alben", titel)
    inhalt += ('<form class="filter albumneu" id="neualbum"><input class="pname" maxlength="60" autocomplete="off" '
               'placeholder="Neues Album, z. B. Urlaub 2023" aria-label="Name des neuen Albums">'
               '<button class="knopf haupt">Album anlegen</button></form>')
    kacheln = []
    for a in alben:
        such = urlencode({"q": f"Album {a['name']}"})
        tb = titelbilder.get(a["id"])
        bild = f'<img loading="lazy" decoding="async" src="/t/{tb[0]}/{tb[1]}?v={tb[2]}" alt="">' if tb else ""
        kacheln.append(
            f'<div class="kachel albumkachel"><a class="bild" href="/suche?{such}" aria-label="Fotos im Album '
            f'{e(a["name"])}">{bild}</a><div class="zeile"><input class="pname aname" data-id="{a["id"]}" '
            f'data-alt="{e(a["name"])}" value="{e(a["name"])}" maxlength="60" aria-label="Name des Albums" '
            f'title="Umbenennen: Namen ändern, Enter"></div><div class="zeile"><span class="leise">'
            f'{bilder_text(a["n"])}</span></div><div class="zeile"><a class="knopf" href="/suche?{such}">Fotos zeigen</a>'
            f'<button class="knopf amarkieren" type="button" data-id="{a["id"]}" title="Dieses Album zum Markieren '
            f'wählen und zu den Ordnern gehen">Markieren</button><button class="knopf aloeschen" type="button" '
            f'data-id="{a["id"]}" data-name="{e(a["name"])}">Löschen</button></div></div>')
    if kacheln:
        inhalt += f'<main class="raster">{"".join(kacheln)}</main>'
    else:
        inhalt += '<p class="leer">Noch keine Alben. Legen Sie oben eins an und markieren Sie dann Fotos dafür.</p>'
    inhalt += ('<p class="hilfe">Ein Foto kann in beliebig vielen Alben stehen. Fotos markieren: einen Ordner oder ein '
               'Filterergebnis öffnen, oben „Fotos markieren für Album …“ wählen, dann ＋ unter den Fotos anklicken '
               '(mit <kbd>Umschalt</kbd> alle bis zum zuletzt angeklickten) oder in der Lupe <kbd>A</kbd> drücken; „Alle '
               'hinzufügen“ nimmt den ganzen Ordner bzw. alle Treffer. Ohne gewähltes Album öffnet ＋ unter einem Foto '
               'die Liste aller Alben zum Ankreuzen. Im Filter: <i>Album Urlaub</i> oder nur <i>Urlaub</i>, '
               '<i>ohne Album</i>. Löschen entfernt nur das Album, nicht die Fotos.</p>')
    return seite("Alben – BestOf", inhalt, JS_ALBENSEITE)


def gruppe_pruefen_seite(app, pid):
    """Alle Gesichter einer Gruppe, untypische zuerst (geringste Ähnlichkeit zum Gruppenmittel) –
    so findet man Verwechslungen, z. B. Kinder in der Gruppe eines Elternteils, und benennt sie gesammelt."""
    z = app.index.einer("SELECT name, summe, anzahl FROM person WHERE id=?", (pid,))
    if not z:
        return None
    name = z[0] or f"Person {pid}"
    mitte = np.frombuffer(z[1], np.float32)
    laenge = float(np.linalg.norm(mitte))
    zeilen = app.index.q("SELECT g.id, g.emb, g.pfad, g.x, g.y, g.w, g.h, b.mtime FROM gesicht g "
                         "LEFT JOIN bild b ON b.pfad = g.pfad WHERE g.person=?", (pid,))
    zeilen.sort(key=lambda r: float(np.frombuffer(r[1], np.float32) @ mitte) / laenge if r[1] and laenge > 0 else 2.0)
    gesamt, zeilen = len(zeilen), zeilen[:600]
    gesichter = "".join(
        f'<figure class="gesicht wahl" data-id="{gid}" title="{e(name_aus_id(gp.split("/", 1)[1]))} (Ordner {gp[:4]})">'
        f'<img loading="lazy" src="/f/{gid}?v={mt}.{int(gx * 1e4)}.{int(gy * 1e4)}.{int(gw * 1e4)}" alt="">'
        f'<span class="haken" aria-hidden="true">✓</span></figure>'
        for gid, _, gp, gx, gy, gw, gh, mt in zeilen)
    titel = f'<div class="titel"><h1>Prüfen</h1><div><p>{e(name)}: {gesamt} Gesichter, untypische zuerst{" (die ersten 600)" if gesamt > 600 else ""}</p></div></div>'
    inhalt = kopf(app, "personen", titel)
    namen = "".join(f'<option value="{e(n)}">' for n in namensliste(app.index))
    inhalt += ('<div class="pruefleiste"><span id="zahl" class="leise"></span>'
               '<button class="knopf" id="alle" type="button">Alle</button>'
               '<button class="knopf" id="keine" type="button">Keine</button>'
               '<input id="wname" class="pname" list="namenliste" maxlength="60" autocomplete="off" '
               'placeholder="Name, z. B. Anna" aria-label="Name für die ausgewählten Gesichter">'
               '<button class="knopf aktion" id="nennen" type="button">Ausgewählte so nennen</button>'
               '<button class="knopf aktion" id="bestaetigen" type="button" title="Stimmt so – bestof.py lernt '
               'daraus">Ausgewählte bestätigen</button>'
               '<button class="knopf aktion" id="entfernen" type="button">Ausgewählte entfernen</button>'
               f'<a class="knopf rechts" href="/personen">Zurück zu den Personen</a></div>'
               f'<datalist id="namenliste">{namen}</datalist>'
               f'<main class="personen"><div class="gesichter">{gesichter}</div></main>'
               '<p class="hilfe">Gesichter anklicken, Namen eintippen, „Ausgewählte so nennen“. Jedes Gesicht kommt zur '
               'ähnlichsten Gruppe dieses Namens oder bildet eine neue. Oben stehen die Gesichter, die am wenigsten zum '
               'Rest der Gruppe passen. Danach „Alle“ und „Ausgewählte bestätigen“: Bestätigte und korrigierte Gesichter '
               'sind die Labels, aus denen bestof.py lernt.</p>')
    return seite(f"{name} prüfen – BestOf", inhalt, JS_PRUEFEN)


def uebersicht(app, filt, seite_nr):
    alle = app.archiv.ordner()
    gewaehlt = app.auswahl.mit_auswahl()
    if filt == "ohne":
        liste = [o for o in alle if o not in gewaehlt]
    elif filt == "mit":
        liste = [o for o in alle if o in gewaehlt]
    else:
        filt, liste = "alle", alle
    seiten = max(1, -(-len(liste) // app.pro_seite))
    seite_nr = min(max(1, seite_nr), seiten)
    teil = liste[(seite_nr - 1) * app.pro_seite: seite_nr * app.pro_seite]
    zusammen = {}
    if app.index and teil:
        platz = ",".join("?" * len(teil))
        for o, zeit in app.index.q(f"SELECT ordner, MIN(sortzeit) FROM bild_eff WHERE ordner IN ({platz}) "
                                   f"GROUP BY ordner", teil):
            zusammen[o] = [datum_kurz(zeit)]
        for o, ort, _ in app.index.q(f"SELECT ordner, ort, COUNT(*) c FROM bild WHERE ordner IN ({platz}) "
                                     f"AND ort IS NOT NULL GROUP BY ordner, ort ORDER BY c DESC", teil):
            if len(zusammen.setdefault(o, [""])) == 1:
                zusammen[o].append(ort)
    kacheln = []
    for o in teil:
        bilder = app.archiv.bilder(o)
        markiert = app.auswahl.markiert(o)
        titelbild = next((b for b in bilder if b[0] in markiert), bilder[0] if bilder else None)
        bild = (f'<img loading="lazy" decoding="async" src="/t/{o}/{url_id(titelbild[0])}?v={titelbild[2]}" alt="">'
                if titelbild else "")
        wann = ", ".join(t for t in zusammen.get(o, []) if t)
        kacheln.append(f'<a class="kachel{" gewaehlt" if markiert else ""}" href="/o/{o}">'
                       f'<div class="bild">{bild}</div><div class="zeile"><span class="nr">{o}</span>'
                       f'<span class="leise">{bilder_text(len(bilder))}</span>{sterne_svg(len(markiert))}</div>'
                       f'<span class="leise wann">{e(wann)}</span></a>')
    n_mit = len(gewaehlt & set(alle))

    def filterlink(schluessel, text, n):
        aktuell = ' aria-current="page"' if schluessel == filt else ""
        return f'<a href="/?filter={schluessel}"{aktuell}>{text} ({n})</a>'

    titel = (f'<p class="stand">{len(alle)} Ordner, {n_mit} mit Stern, '
             f'{bilder_text(app.auswahl.anzahl_bilder())} in BestOf</p>')
    werkzeuge = (f'<div class="filter"><nav class="navi" aria-label="Ordnerfilter">{filterlink("alle", "Alle", len(alle))}'
                 f'{filterlink("ohne", "Ohne Stern", len(alle) - n_mit)}{filterlink("mit", "Mit Stern", n_mit)}</nav>'
                 f'<form class="springen" action="/springen"><input name="o" inputmode="numeric" pattern="[0-9]*" '
                 f'maxlength="4" placeholder="Ordner" aria-label="Ordnernummer"><button class="knopf">Öffnen</button></form>'
                 f'<button class="knopf rechts" id="neuaufbau" type="button">BestOf neu aufbauen</button></div>')
    if not alle:
        hauptteil = (f'<p class="leer">Keine Ordner 0001–9999 gefunden in {e(app.archiv.pfad)}. '
                     f'Prüfen Sie den Pfad beim Start.</p>')
    elif not liste:
        hauptteil = '<p class="leer">Jeder Ordner hat ein Bild mit Stern.</p>' if filt == "ohne" else \
            '<p class="leer">Noch keine Sterne. Öffnen Sie einen Ordner und markieren Sie bis zu ' \
            f'{bilder_text(app.auswahl.max_best)} mit ☆ – sie landen in BestOf.</p>'
    else:
        hauptteil = f'<main class="raster">{"".join(kacheln)}</main>'
    nav = seiten_nav(seite_nr, seiten, lambda n: f"/?filter={filt}&seite={n}")
    quelle = ('<p class="quelle">Ortsnamen: GeoNames (CC BY 4.0). Gesichtserkennung lokal mit YuNet und SFace '
              '(OpenCV Zoo).</p>' if app.index else "")
    return seite("BestOf – " + os.path.basename(app.archiv.pfad),
                 kopf(app, "ordner", titel) + werkzeuge + hauptteil + nav + quelle, JS_UEBERSICHT)
