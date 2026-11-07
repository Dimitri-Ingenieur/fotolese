"""fotolese.web.html – Seiten und Bausteine der Oberfläche (CSS, JS, HTML-Erzeugung)."""
import hashlib
import json
import os
import random
from urllib.parse import quote, urlencode

import numpy as np

from fotolese.web.konst import KOLORIERT, MAX_ORDNER, MONATE, PAPIERKORB, VERBESSERT
from fotolese.web.konfig import (anzeige, bilder_text, bildmasse, datum_kurz, e, groesse_text,
                                 name_aus_id, ort_text, url_id, zeit_text)
from fotolese.web.suche import ALLE_FOTOS, OHNE_ALBUM, suche_ausfuehren
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
.knopf[aria-pressed=true]{border-color:var(--stift);color:var(--stift)}
.waehlen .raster .kachel{cursor:pointer}.waehlen .raster .kachel .bild{opacity:.7}
.kachel.markiert .bild{opacity:1!important;outline:3px solid var(--stift);outline-offset:-3px;position:relative}
.kachel.markiert .bild::after{content:"✓";position:absolute;top:6px;right:8px;background:var(--stift);color:var(--umfeld);
 border-radius:999px;width:24px;height:24px;display:grid;place-items:center;font-weight:700}
.wahlleiste{position:sticky;bottom:0;z-index:8;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;
 background:var(--lupe);border-top:1px solid var(--linie)}.wahlleiste span{flex:1 1 14em;min-width:0}
.zdialog{position:fixed;inset:0;z-index:30;background:rgba(0,0,0,.6);display:grid;place-items:center;padding:16px}
.zbox{background:var(--umfeld);border:1px solid var(--linie);width:min(680px,100%);max-height:100%;overflow:auto;padding:16px 18px}
.zbox h2{margin:0 0 8px;font-size:20px}.zbox h3{font-size:15px;margin:14px 0 4px}.zliste{font-family:var(--zahl);margin:4px 0}
.zziel{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.zziel select{padding:4px 8px;background:var(--flaeche);
 border:1px solid var(--linie);color:var(--text);font:inherit}
.vorschlaege{padding-left:18px;margin:6px 0}.vorschlaege li{margin:6px 0}.vorschlaege .leise{margin:2px 0}
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
.knopf.korb{flex:none;display:inline-flex;align-items:center;justify-content:center;padding:6px 8px;color:var(--leise)}
.korb svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.knopf.korb:hover{color:var(--fehler);border-color:var(--fehler)}
.knopf.holen{display:none;flex:none;font-size:13px;padding:5px 9px}
/* weggeworfen: Kachel bleibt stehen (nichts rutscht unter den Mauszeiger), „Zurückholen“ an derselben Stelle */
.feld.weg .holen{display:inline-block}
.feld.weg .stern,.feld.weg .korb,.feld.weg .ordnernr{display:none}
.feld.weg .technik,.feld.weg .meta,.feld.weg .alben{visibility:hidden}
.feld.weg .rahmen{cursor:default}.feld.weg .rahmen img{opacity:.12}
.feld.weg .zelle::after{content:"Im Papierkorb";position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;color:var(--leise);pointer-events:none}
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
.lupe .text{flex:1 1 auto;width:12em;min-width:0;display:flex;flex-direction:column;overflow:hidden}  /* feste Grundbreite: langer Name zieht die Leiste nicht auf */
.lupe .wer,.lupe .info{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lupe .wer{color:var(--leise)}
.lupe .info{font-size:13px}
.lupe .knopf.jsetz{font-size:15px;padding:4px 9px}
.gesichter-an .knopf.gz{border-color:var(--text)}
.meldung{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--text);color:var(--umfeld);
  padding:9px 14px;border-radius:2px;max-width:min(92vw,60ch);z-index:20}
.meldung.fehler{background:var(--fehler);color:#1f1f1f}
.meldung[hidden]{display:none}
.meldung .mknopf{margin-left:12px;color:inherit;font-weight:600;font-size:inherit}
.lupe:not([hidden]) ~ .meldung{bottom:96px}
/* Verbessern (ComfyUI) und Vorher/Nachher */
.lupe .flaeche .nachher{position:absolute;max-width:none;max-height:none;object-fit:contain;pointer-events:none;
  outline:none}
/* Bearbeiten: eigene Leiste statt der normalen, Vorschau per CSS am Lupenbild */
.lupe .bearbeitung{display:flex;align-items:center;gap:10px 14px;padding:10px 16px 14px;flex-wrap:wrap;
  border-top:1px solid var(--linie)}
.bearbeitung .btitel{font-weight:600}
.bearbeitung .knopf.dreh{font-size:18px;line-height:1;padding:5px 10px}
.bearbeitung label{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--leise)}
.bearbeitung input[type=range]{width:7.5em;accent-color:var(--stift)}
.bearbeitung output{min-width:2.4em;font-variant-numeric:tabular-nums;color:var(--text)}
.bearbeitung .speichern{border-color:var(--stift);color:var(--stift)}.bearbeitung .speichern:disabled{opacity:.45}
.lupe.bearbeiten .flaeche img{outline:none}
.trenner{position:absolute;width:2px;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.45);pointer-events:none}
.trenner::after{content:"⇆";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:30px;height:30px;
  border-radius:50%;background:#fff;color:#222;display:flex;align-items:center;justify-content:center;font-size:16px;
  box-shadow:0 1px 6px rgba(0,0,0,.5)}
.vlabel{position:absolute;padding:1px 8px;font-size:13px;background:rgba(30,30,30,.82);border-radius:2px;text-decoration:none}
.vlabel:hover{text-decoration:underline}
.lupe .farbhinweis{width:11em;padding:5px 8px;background:var(--flaeche);border:1px solid var(--linie);border-radius:2px}
.vergleich-an .flaeche{cursor:ew-resize;touch-action:none}
.vstatus{position:absolute;right:12px;top:10px;margin:0;padding:5px 12px;font-size:13px;background:rgba(30,30,30,.88);
  border-radius:2px;z-index:2;pointer-events:none;max-width:70%}
.lupe .vregler{width:8em;accent-color:var(--stift)}
.lupe .knopf.vgl[aria-pressed=true]{border-color:var(--stift);color:var(--stift)}
.abadge{position:absolute;right:8px;bottom:8px;max-width:calc(100% - 16px);overflow:hidden;text-overflow:ellipsis;
 white-space:nowrap;font-size:12px;padding:2px 7px;border-radius:999px;background:rgba(0,0,0,.72);color:var(--text)}
.abadge.nah{color:var(--stift)}.abadge.bezug{background:var(--stift);color:var(--umfeld);font-weight:700}
.aehnbild{display:block;max-width:min(420px,100%);max-height:50vh;margin:0 0 10px}.aehnzeile p{margin:0;max-width:110ch}
.vbadge{position:absolute;left:8px;bottom:8px;max-width:calc(100% - 16px);overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-size:12px;padding:1px 7px;border-radius:2px;background:rgba(40,40,40,.86);color:var(--stift);
  pointer-events:none}
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
.albumwahl{display:grid;gap:4px;max-width:28em;margin:10px 0 4px;font-size:13px;color:var(--leise)}
.albumwahl .pname{font-size:15px;width:100%}
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
.hilfe0 code{overflow-wrap:anywhere}
.import progress{width:100%;height:10px;accent-color:var(--stift)}
.ergebnis{white-space:pre-line}.ergebnis.fehler{color:var(--fehler)}
.import pre{max-height:40vh;overflow:auto;font-size:12px;background:var(--lupe);padding:10px;white-space:pre-wrap}
.einst{max-width:900px}.einst>section{min-width:0}.einst code,.titel .pfad{overflow-wrap:anywhere}.ezeile{display:grid;grid-template-columns:minmax(12em,17em) 1fr;gap:2px 14px;padding:8px 0;
 border-bottom:1px solid var(--flaeche)}.ezeile label{padding-top:6px}.ezeile .hilfe0{grid-column:2;margin:2px 0 0}
.eingabe{display:flex;gap:6px;align-items:center;min-width:0}.eingabe .wert{min-width:0}
.eingabe input[type=text],.eingabe select,.eingabe textarea{padding:5px 8px;background:var(--flaeche);color:var(--text);
 border:1px solid var(--linie);border-radius:2px;font:inherit;font-size:15px}
.eingabe input[inputmode=decimal]{width:7em;font-family:var(--zahl)}.eingabe input[type=text]:not([inputmode]){flex:1}
.eingabe select{max-width:100%}.eingabe textarea{flex:1;resize:vertical}.eingabe .wert:disabled{opacity:.6}
.schalter{display:inline-flex;gap:6px;align-items:center;padding-top:4px}
.equelle{white-space:nowrap;border:1px solid var(--linie);border-radius:999px;padding:0 7px;margin-left:4px;font-size:12px}
.ehinweis:not(:empty){display:block;color:var(--stift)}.warn{color:var(--stift)}
.wfliste ul{list-style:none;padding:0;margin:6px 0;font-size:14px}.wfliste li{padding:3px 0}
.wfliste li.fehler{color:var(--fehler)}.planliste{font-size:14px;margin:6px 0;padding-left:18px}
@media (max-width:640px){.ezeile{grid-template-columns:1fr}.ezeile .hilfe0{grid-column:1}.ezeile label{padding-top:0}}
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
.feld.eingeordnet .rahmen img{opacity:.35}
.vs-an .feld .rahmen{cursor:pointer}.feld.markiert .rahmen{outline:3px solid var(--stift);outline-offset:-3px;position:relative}
.feld.markiert .rahmen::after{content:"✓";position:absolute;top:8px;left:8px;background:var(--stift);color:var(--umfeld);
 border-radius:999px;width:24px;height:24px;display:grid;place-items:center;font-weight:700}
.vsin{display:flex;gap:6px}.vsin .pname{font-size:15px;width:5.5em}
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
  .suche{flex-basis:100%;max-width:none;flex-wrap:wrap}.suche input{flex:1 1 100%;width:auto}
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
function meldung(text,fehler,aktion){meldungEl.textContent=text;meldungEl.classList.toggle('fehler',!!fehler);
 const aktionen=aktion?(Array.isArray(aktion[0])?aktion:[aktion]):[];  // [Text, Funktion] oder Liste davon
 for(const [t,fn] of aktionen){const k=document.createElement('button');k.type='button';k.className='link mknopf';
  k.textContent=t;k.addEventListener('click',()=>{meldungEl.hidden=true;fn();});meldungEl.append(k);}
 meldungEl.hidden=false;clearTimeout(meldungTimer);
 meldungTimer=setTimeout(()=>meldungEl.hidden=true,aktion?10000:fehler?6000:2600);}
async function post(url,daten){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify(daten||{})});let j={};try{j=await r.json();}catch(_){j={fehler:'Server antwortet nicht.'};}
 return [r.ok,j];}
// Umzug (Ordner zusammengefasst): Meldung nach dem Seitenwechsel, mit „Rückgängig“
async function auftragWarten(){for(;;){await new Promise(r=>setTimeout(r,400));let j;
 try{j=await (await fetch('/api/gruppieren')).json();}catch(_){continue;}if(j.auftrag&&!j.auftrag.laeuft)return j.auftrag;}}
async function umzugZurueck(nachher){const [ok,j]=await post('/api/gruppieren',{aktion:'rueckgaengig'});
 if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}meldung('Wird zurückgenommen …');const a=await auftragWarten();
 try{sessionStorage.setItem('bestofMeldung',JSON.stringify({text:a.fehler||a.ergebnis,fehler:!!a.fehler}));}catch(_){}
 location.href=nachher||'/';}
if(!document.querySelector('.aehnwarten'))try{  // Warteseite „Ähnliche“ leitet gleich weiter: Meldung dort zeigen
 const m=JSON.parse(sessionStorage.getItem('bestofMeldung')||'null');sessionStorage.removeItem('bestofMeldung');
 if(m){const akt=[];if(m.rueck)akt.push(['Rückgängig',()=>umzugZurueck(m.nachher)]);
  if(m.ziel&&location.pathname!=='/o/'+m.ziel)akt.push(['Ordner '+m.ziel+' öffnen',()=>{location.href='/o/'+m.ziel;}]);
  setTimeout(()=>meldung(m.text,!!m.fehler,akt.length?akt:null),50);}}catch(_){}
const statusEl=document.querySelector('.status');
async function statusHolen(){try{const r=await fetch('/api/status');const j=await r.json();
 statusEl.textContent=j.text;if(j.laeuft)setTimeout(statusHolen,3000);}catch(_){}}
if(statusEl&&statusEl.dataset.laeuft==='1')setTimeout(statusHolen,2000);
"""

JS_UEBERSICHT = """
const $=id=>document.getElementById(id);
function zahl(n){return String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g,'.');}
function bilderText(n){return n===1?'1 Bild':zahl(n)+' Bilder';}
// Ordner zusammenfassen: Ordner anklicken (Umschalt = Bereich), Vorschau, Analyse mit fotosort, Ausführen
const zk=$('zusammen'),wl=$('wahlleiste'),zd=$('zdialog'),kacheln=[...document.querySelectorAll('.raster .kachel')];
let wahl=false,letzte=-1,anaId=null,anaTimer=null;const gew=new Set();
const NAMEN={SCHWELLE:'Bildvergleich',SERIE_SEK:'Serie: Zeitabstand',SERIE_SCHWELLE:'Serie: Abstand'};
function liste(){return [...gew].sort((a,b)=>a-b);}  // nach Nummer: 9999 vor 10000
function waehlen(an){wahl=an&&!!kacheln.length;document.body.classList.toggle('waehlen',wahl);wl.hidden=!wahl;
 zk.setAttribute('aria-pressed',wahl);if(!wahl){gew.clear();letzte=-1;}zeigen();}
function zeigen(){kacheln.forEach(k=>k.classList.toggle('markiert',gew.has(k.dataset.o)));const l=liste();
 $('wahltext').textContent=l.length?l.length+' Ordner gewählt: '+l.join(', '):'Ordner anklicken, die zusammengehören (Umschalt = Bereich).';
 $('zstart').disabled=l.length<2;}
if(zk)zk.addEventListener('click',()=>waehlen(!wahl));
if(wl){$('zende').addEventListener('click',()=>waehlen(false));$('zstart').addEventListener('click',dialogAuf);
 $('zziel').addEventListener('change',vorschauHolen);$('zab').addEventListener('click',dialogZu);$('zok').addEventListener('click',zusammenfassen);
 zd.addEventListener('click',ev=>{if(ev.target===zd)dialogZu();});}
document.addEventListener('keydown',ev=>{if(ev.key!=='Escape')return;if(zd&&!zd.hidden)dialogZu();else if(wahl)waehlen(false);});
kacheln.forEach((k,i)=>k.addEventListener('click',ev=>{if(!wahl)return;ev.preventDefault();const o=k.dataset.o;
 if(o==='0000'){meldung('Den Sammelordner 0000 bitte nicht zusammenfassen – er gehört den Einzelbildern.',true);return;}
 if(ev.shiftKey&&letzte>=0){const an=!gew.has(o);for(let x=Math.min(letzte,i);x<=Math.max(letzte,i);x++){
   const ox=kacheln[x].dataset.o;if(ox!=='0000'){if(an)gew.add(ox);else gew.delete(ox);}}}
 else if(gew.has(o))gew.delete(o);else gew.add(o);letzte=i;zeigen();}));
function dialogAuf(){const l=liste();if(l.length<2)return;zd.hidden=false;$('zok').disabled=false;
 $('zziel').replaceChildren(...l.map(o=>new Option(o,o)));$('zziel').value=l[0];$('zliste').textContent=l.join(' · ');
 $('zinfo').textContent='';vorschauHolen();analyseStarten(l);$('zziel').focus();}
function dialogZu(){zd.hidden=true;clearTimeout(anaTimer);if(anaId)post('/api/gruppieren',{aktion:'abbrechen',id:anaId});anaId=null;}
async function vorschauHolen(){const [ok,j]=await post('/api/gruppieren',{aktion:'vorschau',ordner:liste(),ziel:$('zziel').value});
 if(!ok){$('zinfo').textContent=j.fehler||'';return;}
 $('zliste').textContent=j.ordner.map(x=>x.ordner+' ('+bilderText(x.bilder)+(x.sterne?', '+x.sterne+' ★':'')+')').join(' · ');
 let t=bilderText(j.bilder)+(j.bilder===1?' kommt':' kommen')+' nach '+j.ziel+' (dort schon '+bilderText(j.ziel_bilder)+'), die anderen Ordner verschwinden. '+
  'Verbesserte Fassungen, Begleitdateien, Sterne, Alben, Jahr und Gesichter wandern mit.';
 if(j.umbenannt)t+=' '+j.umbenannt+(j.umbenannt===1?' Aufnahme bekommt':' Aufnahmen bekommen')+' einen Laufindex, weil der Name im Ziel schon vorkommt (z. B. IMG_0001_1.JPG).';
 if(j.sterne_weg)t+=' Höchstens '+j.max_best+' Sterne je Ordner: '+j.sterne_weg+' entfallen.';
 $('zinfo').textContent=t;}
async function analyseStarten(l){clearTimeout(anaTimer);const box=$('zanalyse');box.replaceChildren(absatz('fotosort vergleicht die Fotos …','leise'));
 const [ok,j]=await post('/api/gruppieren',{aktion:'analyse',ordner:l});
 if(!ok){box.replaceChildren(absatz(j.fehler||'Analyse nicht möglich.','leise'));return;}anaId=j.id;analyseAbfragen();}
async function analyseAbfragen(){const id=anaId;if(!id)return;let r;
 try{r=(await (await fetch('/api/gruppieren?id='+encodeURIComponent(id))).json()).rechnungen[id];}catch(_){}
 if(id!==anaId)return;
 if(!r||r.laeuft){if(r)$('zanalyse').replaceChildren(absatz('fotosort vergleicht die Fotos: '+r.phase+
   (r.gesamt?' – '+zahl(r.fertig)+' von '+zahl(r.gesamt):'')+' …','leise'));anaTimer=setTimeout(analyseAbfragen,600);return;}
 anaId=null;if(r.fehler){$('zanalyse').replaceChildren(absatz('Analyse: '+r.fehler,'leise'));return;}analyseZeigen(r.ergebnis);}
function absatz(text,klasse){const p=document.createElement('p');p.textContent=text;if(klasse)p.className=klasse;return p;}
function wertText(n,w){return n==='SERIE_SEK'?String(w).replace('.',',')+' s':String(w);}
function analyseZeigen(a){const box=$('zanalyse'),teile=[];
 if(a.vergleichbar<2)teile.push(absatz('Zu wenig vergleichbare Fotos für eine Aussage.'));
 else if(a.teile===1)teile.push(absatz('Mit den jetzigen Werten wären sie schon eine Gruppe. fotosort legt beim Import aber '+
  'bestehende Ordner nie zusammen – sie kamen wohl in verschiedenen Importen. Zusammenfassen erledigt das.'));
 else{teile.push(absatz('Mit den jetzigen Werten hätte fotosort sie in '+a.teile+' Gruppen aufgeteilt. Eine dieser Änderungen hätte genügt:'));
  const ul=document.createElement('ul');ul.className='vorschlaege';
  for(const v of a.vorschlaege){const li=document.createElement('li'),kopf=document.createElement('b');
   kopf.textContent=NAMEN[v.name]+' ('+v.name+'): ';li.append(kopf);
   if(v.wert===null){li.append('nicht möglich – '+v.grund+'.');ul.append(li);continue;}
   li.append(wertText(v.name,v.wert)+' statt '+wertText(v.name,a.jetzt[v.name])+' ');
   const b=document.createElement('button');b.type='button';b.className='knopf klein';b.textContent='Übernehmen';
   b.title='In den Einstellungen speichern – gilt für künftige Importe und „Neu gruppieren“';
   b.addEventListener('click',async()=>{const [ok,j]=await post('/api/einstellungen',{werte:{[v.name]:v.wert}});
    meldung(ok?j.meldung+' Gilt für künftige Importe.':(j.fehler||'Speichern fehlgeschlagen.'),!ok);if(ok)b.disabled=true;});
   li.append(b);
   li.append(absatz('Engste Stelle: '+v.paar[0]+' ↔ '+v.paar[1]+' (Abstand '+v.abstand+(v.sekunden!=null?', '+String(v.sekunden).replace('.',',')+' s':'')+').','leise'));
   const f=v.folgen||{};let ft='';
   if(f.zu_hoch)ft='So hoch, dass auch viele unähnliche Fotos zusammenkämen – eher nicht übernehmen.';
   else if(v.folgen){const t=[];if(f.n_mit)t.push('käme mit dazu: '+f.mit.slice(0,6).join(', ')+(f.n_mit>6?' …':''));
    t.push(f.zusammen?(f.zusammen===1?'1 weitere Zusammenlegung':zahl(f.zusammen)+' weitere Zusammenlegungen')+' im Archiv'+
     (f.beispiele.length?' (z. B. '+f.beispiele.slice(0,3).map(b=>b.slice(0,4).join(' + ')+(b.length>4?' …':'')).join('; ')+')':''):
     'sonst ändert sich im Archiv nichts');ft='Folgen bei „Neu gruppieren“: '+t.join(', ')+'.';}
   if(ft)li.append(absatz(ft,'leise'));ul.append(li);}
  teile.push(ul);}
 if(a.n_nicht)teile.push(absatz(a.n_nicht+(a.n_nicht===1?' Foto ist':' Fotos sind')+' einfarbig oder nicht lesbar – die ordnet fotosort nie automatisch zu.','leise'));
 box.replaceChildren(...teile);}
async function zusammenfassen(){const l=liste(),ziel=$('zziel').value;$('zok').disabled=true;
 const [ok,j]=await post('/api/gruppieren',{aktion:'zusammenfassen',ordner:l,ziel});
 if(!ok){meldung(j.fehler||'Zusammenfassen nicht möglich.',true);$('zok').disabled=false;return;}
 meldung('Wird zusammengefasst …');const a=await auftragWarten();
 try{sessionStorage.setItem('bestofMeldung',JSON.stringify({text:a.fehler||a.ergebnis,fehler:!!a.fehler,rueck:!a.fehler}));}catch(_){}
 location.href='/o/'+ziel;}
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
 lupeAehnl=lupe.querySelector('.aehnl'),
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
  const n=D.bilder.filter(b=>!b.weg).length;
  info.textContent=n+(n===1?' Bild, ':' Bilder, ')+l.length+' von '+D.max+' mit Stern';
  zielEl.textContent=l.length?'BestOf: '+l.map(id=>D.ziele[D.ordner][id]).join(', '):'Noch kein Stern (☆ = Kopie in BestOf)';}
 if(aktiv>=0)lupeZeichne();}
async function umschalten(i){
 if(laeuft)return;const b=D.bilder[i],l=D.auswahl[b.ordner]||[];
 if(!l.includes(b.id)&&l.length>=D.max){meldung('Ordner '+b.ordner+' hat schon '+STERNE(D.max)+'. Nehmen Sie erst einem Bild den Stern.',true);return;}
 laeuft=true;const [ok,j]=await post('/api/auswahl',{ordner:b.ordner,datei:b.id});laeuft=false;
 if(!ok){meldung(j.fehler||'Stern setzen fehlgeschlagen.',true);return;}
 D.auswahl[b.ordner]=j.auswahl;D.ziele[b.ordner]=j.ziele;zeichne();meldung(j.meldung);}
// Papierkorb: Foto wandert nach SORTIERT/Musor, die Kachel bleibt als „Im Papierkorb“ stehen; „Rückgängig“ holt es zurück
async function wegwerfen(i){const b=D.bilder[i];if(!b||b.weg)return;
 if((D.auswahl[b.ordner]||[]).includes(b.id)){
  meldung('Das Bild hat einen Stern – erst den Stern entfernen, dann in den Papierkorb.',true);return;}
 b.weg=true;const [ok,j]=await post('/api/papierkorb',{pfad:b.ordner+'/'+b.id});  // weg=true: kein Doppelklick
 if(!ok){b.weg=false;meldung(j.fehler||'Verschieben fehlgeschlagen.',true);return;}
 b.rueck=j.rueck;wegZeigen(i,true);meldung(j.meldung,false,['Rückgängig',()=>zurueckholen(i)]);}
async function zurueckholen(i){const b=D.bilder[i];if(!b.weg||!b.rueck)return;
 const [ok,j]=await post('/api/papierkorb',{rueck:b.rueck});
 if(!ok){meldung(j.fehler||'Zurückholen fehlgeschlagen.',true);return;}b.rueck=null;wegZeigen(i,false);meldung(j.meldung);}
function wegZeigen(i,an){D.bilder[i].weg=an;felder[i].classList.toggle('weg',an);
 if(an&&aktiv===i){const k=sichtbar(i,1);if(k<0)schliesse();else oeffne(k);}
 zeichne();if(typeof albLeiste==='function')albLeiste();}
function sichtbar(i,schritt){const n=D.bilder.length;  // nächstes nicht weggeworfenes Bild ab i
 for(let k=0;k<n;k++){const j=((i+k*schritt)%n+n)%n;if(!D.bilder[j].weg)return j;}return -1;}
felder.forEach((f,i)=>{f.querySelector('.stern').addEventListener('click',()=>umschalten(i));
 f.querySelector('.korb').addEventListener('click',()=>wegwerfen(i));
 f.querySelector('.holen').addEventListener('click',()=>zurueckholen(i));
 f.querySelector('.rahmen').addEventListener('click',ev=>{if(D.bilder[i].weg)return;
  if(window.feldKlick&&window.feldKlick(i,ev))return;oeffne(i);});  // feldKlick: Fotos verschieben (Auswahl)
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
 const pfade=D.bilder.slice(von,bis+1).filter(b=>b.j!==jahr&&!b.weg).map(b=>b.ordner+'/'+b.id);
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
 lupeWer.textContent=(D.einordner?'':'Ordner '+b.ordner+', ')+b.name+(b.wf?' (verbessert: '+b.wf+')':'')+' · '+b.t+
  (an?' – BestOf '+D.ziele[b.ordner][b.id]:'');
 lupeInfo.textContent=[b.jm?'':b.z,b.ol,namenVon(b,true).join(', ')].filter(Boolean).join(', ');
 if(lupeJahr&&document.activeElement!==lupeJahr)jahrFeld(lupeJahr,b);jsetzZeichne(lupeJsetz,b);
 lupeKarte.hidden=!b.k;if(b.k)lupeKarte.href=b.k;
 gzKnopf.hidden=!D.gesichter;gzKnopf.textContent='Gesichter'+(b.f.length?' ('+b.f.length+')':'');
 sternKnopf(lupeKnopf,b,an,voll);lupeKnopf.title+=' (Leertaste oder S)';kaesten();albenLupe();verbLupe();}
function oeffne(i,schritt){bearbeitenAus();const j=sichtbar(i,schritt||1);if(j<0){schliesse();return;}
 vergleichZu(false);nbox.hidden=true;nGesicht=null;aktiv=j;const b=D.bilder[aktiv];
 lupeImg.src=b.g;lupeImg.alt=b.name;lupeOrig.href=b.o;lupeAehnl.href='/aehnlich?pfad='+encodeURIComponent(b.ordner+'/'+b.id);lupe.hidden=false;lupeZeichne();if(gesichterAn)gesichterHolen(aktiv);
 vorladen(aktiv+1);vorladen(aktiv-1);lupe.querySelector('.zu').focus({preventScroll:true});}
function schliesse(){if(aktiv<0)return;vergleichZu(false);nbox.hidden=true;nGesicht=null;const f=felder[aktiv];aktiv=-1;
 bearbeitenAus();lupe.hidden=true;
 lupeImg.removeAttribute('src');
 kaesten();f.querySelector('.rahmen').focus({preventScroll:true});f.scrollIntoView({block:'nearest'});}
lupeImg.addEventListener('load',kaesten);window.addEventListener('resize',kaesten);
lupe.querySelector('.zurueck').addEventListener('click',()=>oeffne(aktiv-1,-1));
lupe.querySelector('.vor').addEventListener('click',()=>oeffne(aktiv+1));
lupe.querySelector('.zu').addEventListener('click',schliesse);
function gesichterUmschalten(){vergleichZu(true);gesichterAn=!gesichterAn;if(!gesichterAn)nbox.hidden=true;
 else gesichterHolen(aktiv);kaesten();}
gzKnopf.addEventListener('click',gesichterUmschalten);
lupeKnopf.addEventListener('click',()=>umschalten(aktiv));
lupe.querySelector('.korb').addEventListener('click',()=>wegwerfen(aktiv));
let wischX=null;lupe.addEventListener('touchstart',ev=>{wischX=ev.touches[0].clientX;},{passive:true});
// im Vergleich ist Ziehen der Schieber, beim Bearbeiten wird nicht geblättert
lupe.addEventListener('touchend',ev=>{if(wischX===null||vergleich||bearbeitet){wischX=null;return;}
 const dx=ev.changedTouches[0].clientX-wischX;wischX=null;
 if(Math.abs(dx)>60)oeffne(aktiv+(dx<0?1:-1),dx<0?1:-1);});
document.addEventListener('keydown',ev=>{
 if(bearbeitet&&ev.key==='Escape'){bTaste(ev);return;}  // auch aus einem Regler heraus
 if(ev.altKey||ev.ctrlKey||ev.metaKey||ev.target.matches('input,select'))return;
 if(albenOffen()){if(ev.key==='Escape'){albenZu();ev.preventDefault();}return;}
 if(aktiv>=0){
  if(bearbeitet){bTaste(ev);return;}
  if(!nbox.hidden&&ev.key==='Escape'){nennenZu();ev.preventDefault();}
  else if(ev.key==='ArrowRight'){oeffne(aktiv+1);ev.preventDefault();}
  else if(ev.key==='ArrowLeft'){oeffne(aktiv-1,-1);ev.preventDefault();}
  else if(ev.key===' '||ev.key==='s'||ev.key==='S'||ev.key==='b'){umschalten(aktiv);ev.preventDefault();}
  else if(ev.key==='Delete'){wegwerfen(aktiv);ev.preventDefault();}
  else if(ev.key==='g'||ev.key==='G')gesichterUmschalten();
  else if(ev.key==='v'||ev.key==='V'){vergleichAn(!vergleich);ev.preventDefault();}
  else if((ev.key==='j'||ev.key==='J')&&lupeJahr){lupeJahr.focus();lupeJahr.select();ev.preventDefault();}
  else if(ev.key==='a'||ev.key==='A'){albumTaste();ev.preventDefault();}
  else if(ev.key==='e'||ev.key==='E'){bearbeitenAn();ev.preventDefault();}
  else if(ev.key==='Escape'){schliesse();}
 }else if(D.einordner){
  if(ev.key==='ArrowRight'&&D.weiter)location.href=D.weiter;
  else if(ev.key==='ArrowLeft'&&D.zurueck)location.href=D.zurueck;
  else if(ev.key==='n'||ev.key==='N')location.href=D.offen;
  else if(ev.key==='Escape'){if(window.vsAus&&window.vsAus())return;location.href=D.uebersicht;}
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
function albAlleZeichnen(){D.bilder.forEach((_,i)=>feldAlben(i));albLeiste();albOhne();if(aktiv>=0)albenLupe();
 if(albenOffen())albenListe();}
function albOhne(){const el=document.getElementById('ohnealbum');if(!D.ohne_album||!el)return;  // Filter „Ohne Album“
 const da=D.bilder.filter(b=>!b.weg),rest=da.filter(b=>!(b.a||[]).length).length;
 D.bilder.forEach((b,i)=>{if(felder[i])felder[i].classList.toggle('eingeordnet',!!(b.a||[]).length);});
 el.textContent=rest===da.length?'Album oben wählen, dann ＋ unter den Fotos – eingeordnete werden blass, nach dem Neuladen '+
  'bleiben nur die übrigen.':(rest?'Noch '+rest+' von '+da.length+' hier ohne Album – nach dem Neuladen bleiben nur sie.':
  'Alle '+da.length+' hier eingeordnet – neu laden für die nächsten.');}
function albUebernehmen(j){if(j.alben)ALB.splice(0,ALB.length,...j.alben);
 if(j.a)D.bilder.forEach(b=>{const p=albPfad(b);if(p in j.a)b.a=j.a[p];});
 if(j.neu_laden)setTimeout(()=>location.reload(),1500);
 albAuswahl();if(aktAlbum!==null&&!ALB.some(a=>a.id===aktAlbum))albAktiv(null);else albAlleZeichnen();}
async function albSetzen(daten){const [ok,j]=await post('/api/album_bild',daten);
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);return false;}albUebernehmen(j);meldung(j.meldung);return true;}
function albumKlick(i,bereich){if(aktAlbum===null||i<0)return;const an=!(D.bilder[i].a||[]).includes(aktAlbum);let von=i,bis=i;
 if(bereich&&albLetzte>=0){von=Math.min(albLetzte,i);bis=Math.max(albLetzte,i);}albLetzte=i;
 const pfade=[];for(let k=von;k<=bis;k++)if(!D.bilder[k].weg)pfade.push(albPfad(D.bilder[k]));
 if(pfade.length)albSetzen({album:aktAlbum,an,pfade});}
function albAuswahl(){if(!aktSel)return;
 aktSel.replaceChildren(new Option(ALB.length?'Fotos markieren für Album …':'Noch kein Album',''),
  ...ALB.map(a=>new Option(a.name+' ('+a.n+')',String(a.id))));aktSel.value=aktAlbum===null?'':String(aktAlbum);}
function albAktiv(id){aktAlbum=id!==null&&(ALB||[]).some(a=>a.id===id)?id:null;albLetzte=-1;
 try{if(aktAlbum===null)localStorage.removeItem('bestofAlbum');else localStorage.setItem('bestofAlbum',String(aktAlbum));}catch(_){}
 if(aktSel)aktSel.value=aktAlbum===null?'':String(aktAlbum);if(albLeisteEl)albLeisteEl.classList.toggle('aktiv',aktAlbum!==null);
 albAlleZeichnen();}
function albLeiste(){if(!albLeisteEl)return;const an=aktAlbum!==null;albAlle.hidden=albRaus.hidden=!an;
 if(!an){albInfo.textContent=ALB.length?'Album wählen, dann Fotos mit ＋ hinzufügen.':'Neues Album anlegen, dann Fotos mit ＋ hinzufügen.';return;}
 const da=D.bilder.filter(b=>!b.weg),n=da.filter(b=>(b.a||[]).includes(aktAlbum)).length,
  alle=D.suche?D.treffer:da.length,mehr=alle>da.length;
 albInfo.textContent=n+' von '+da.length+' hier im Album. ＋ unter dem Foto oder Taste A in der Lupe, Umschalt = Bereich.';
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
 const alleSetzen=an=>{const wo=D.suche?{suche:D.suche}:D.ordner?{ordner:D.ordner}:
   {pfade:D.bilder.filter(b=>!b.weg).map(b=>b.ordner+'/'+b.id)},n=D.suche?D.treffer:D.bilder.length,name=albName(aktAlbum);
  if(an?n>50&&!confirm(n+' Fotos ins Album „'+name+'“ aufnehmen?'):!confirm('Alle '+n+' Fotos '+
   (D.suche?'dieses Filters':D.ordner?'dieses Ordners':'dieser Seite')+' aus dem Album „'+name+'“ nehmen? Die Fotos selbst bleiben.'))return;
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

JS_VERSCHIEBEN = """
// Fotos verschieben: anklicken (Umschalt = Bereich), dann in eine neue Gruppe oder einen anderen Ordner
const vsKnopf=document.getElementById('verschieben'),vsLeiste=document.getElementById('vsleiste');
let vsAn=false,vsLetzte=-1;const vsGew=new Set();
function vsModus(an){vsAn=an&&!!vsLeiste;document.body.classList.toggle('vs-an',vsAn);if(vsLeiste)vsLeiste.hidden=!vsAn;
 if(vsKnopf)vsKnopf.setAttribute('aria-pressed',vsAn);if(!vsAn){vsGew.clear();vsLetzte=-1;}vsZeigen();}
function vsListe(){return [...vsGew].filter(i=>!D.bilder[i].weg).sort((a,b)=>a-b);}
function vsZeigen(){felder.forEach((f,i)=>f.classList.toggle('markiert',vsGew.has(i)));if(!vsLeiste)return;const l=vsListe();
 document.getElementById('vstext').textContent=l.length?(l.length===1?'1 Foto':l.length+' Fotos')+' gewählt: '+
  l.map(i=>D.bilder[i].name).join(', '):D.aehnlich?'Fotos anklicken, die zum Ausgangsfoto gehören (Umschalt = Bereich).':
  'Fotos anklicken, die nicht in diese Gruppe gehören (Umschalt = Bereich).';
 const zu=document.getElementById('vszu');if(zu&&D.aehnlich){zu.hidden=false;zu.disabled=!l.length;
  zu.textContent='Zu '+D.aehnlich.ordner+' (Ausgangsfoto)';}
 document.getElementById('vsneu').disabled=!l.length||!D.naechster;document.getElementById('vsin').disabled=!l.length;}
window.feldKlick=(i,ev)=>{if(!vsAn)return false;
 if(ev.shiftKey&&vsLetzte>=0){const an=!vsGew.has(i);for(let k=Math.min(vsLetzte,i);k<=Math.max(vsLetzte,i);k++){
   if(D.bilder[k].weg)continue;if(an)vsGew.add(k);else vsGew.delete(k);}}
 else if(vsGew.has(i))vsGew.delete(i);else vsGew.add(i);vsLetzte=i;vsZeigen();return true;};
window.vsAus=()=>{if(!vsAn)return false;vsModus(false);return true;};
async function vsStarten(ziel){const l=vsListe().filter(i=>D.bilder[i].ordner!==ziel);  // schon im Ziel: bleibt
 if(!l.length){if(vsListe().length)meldung('Die gewählten Fotos liegen schon in Ordner '+ziel+'.',true);return;}
 const was=l.length===1?'1 Foto':l.length+' Fotos';
 if(!confirm(was+(ziel==='neu'?' in eine neue Gruppe (Ordner '+D.naechster+')':' nach Ordner '+ziel)+' verschieben? '+
  'NEF, Begleitdateien, verbesserte Fassungen, Sterne, Alben, Jahr und Gesichter kommen mit; „Rückgängig“ ist möglich.'))return;
 const [ok,j]=await post('/api/gruppieren',{aktion:'verschieben',pfade:l.map(i=>D.bilder[i].ordner+'/'+D.bilder[i].id),ziel});
 if(!ok){meldung(j.fehler||'Verschieben nicht möglich.',true);return;}
 meldung('Wird verschoben …');const a=await auftragWarten(),leer=!!D.ordner&&(a.entfernt||[]).includes(D.ordner);
 const hier=D.aehnlich?'/aehnlich?pfad='+encodeURIComponent(D.aehnlich.pfad):'/o/'+D.ordner;  // Ähnliche: neu suchen
 try{sessionStorage.setItem('bestofMeldung',JSON.stringify({text:a.fehler||a.ergebnis,fehler:!!a.fehler,rueck:!a.fehler,
  nachher:hier,ziel:a.fehler?null:a.zielordner}));}catch(_){}
 location.href=leer&&!a.fehler?'/o/'+a.zielordner:D.aehnlich?hier:location.pathname;}
if(vsKnopf&&vsLeiste){vsKnopf.addEventListener('click',()=>vsModus(!vsAn));
 document.getElementById('vsende').addEventListener('click',()=>vsModus(false));
 document.getElementById('vsneu').addEventListener('click',()=>vsStarten('neu'));
 const zu=document.getElementById('vszu');if(zu&&D.aehnlich)zu.addEventListener('click',()=>vsStarten(D.aehnlich.ordner));
 document.getElementById('vsform').addEventListener('submit',ev=>{ev.preventDefault();
  const z=document.getElementById('vsziel').value.replace(/\\D/g,'');
  if(!z){meldung('Bitte die Nummer des Zielordners eingeben, z. B. 0012.',true);return;}
  const ziel=String(+z).padStart(4,'0');if(ziel===D.ordner){meldung('Die Fotos liegen schon in Ordner '+ziel+'.',true);return;}
  vsStarten(ziel);});
 vsZeigen();}
"""

JS_VERBESSERN = """
// Verbessern und Kolorieren mit ComfyUI (je ein Auftrag im Hintergrund) und Vorher/Nachher-Schieber in der Lupe
const VW=D.verbessern||[],FARBE=D.kolorieren,farbKnopf=lupe.querySelector('.farb'),
 farbHinweis=lupe.querySelector('.farbhinweis'),wfWahl=lupe.querySelector('.wfwahl'),verbKnopf=lupe.querySelector('.verb'),
 vglKnopf=lupe.querySelector('.vgl'),vRegler=lupe.querySelector('.vregler'),nachherImg=lupe.querySelector('.nachher'),
 trenner=lupe.querySelector('.trenner'),vLabels=[...lupe.querySelectorAll('.vlabel')],vStatus=lupe.querySelector('.vstatus');
let vergleich=false,vAnteil=50,vZiehen=false,vTimer=null;const vJobs={};  // Auftrag -> {i, t0, s}
wfWahl.replaceChildren(...VW.map(w=>new Option(w.name,w.datei)));
if(D.vorwahl&&VW.some(w=>w.datei===D.vorwahl))wfWahl.value=D.vorwahl;  // Einstellungen: fester Workflow
else try{const m=localStorage.getItem('bestofWorkflow');if(m&&VW.some(w=>w.datei===m))wfWahl.value=m;}catch(_){}
wfWahl.addEventListener('change',()=>{try{localStorage.setItem('bestofWorkflow',wfWahl.value);}catch(_){}verbLupe();});
function wfAktuell(){return VW.find(x=>x.datei===wfWahl.value)||VW[0];}
function farbWf(){return FARBE?(FARBE.workflow||(VW.length&&wfAktuell().farbe?wfAktuell().name:null)):null;}  // wer koloriert
function vPaar(b){return b.paar||(b.ng?[b.g,b.ng]:b.vg?[b.vg,b.g]:null);}  // [vorher, nachher]
function origVon(g){return g.replace('/g/','/orig/').replace(/[?]v=.*$/,'');}
function vJob(i){return Object.values(vJobs).find(j=>j.i===i&&j.s.laeuft);}
function verbLupe(){if(aktiv<0)return;const b=D.bilder[aktiv],job=vJob(aktiv),fw=farbWf(),
  vp=VW.length&&wfAktuell().prompt;  // vp: beim Verbessern kommen die Farbhinweise in den Prompt des Workflows
 verbKnopf.hidden=!VW.length;wfWahl.hidden=VW.length<2;verbKnopf.disabled=farbKnopf.disabled=!!job;
 farbKnopf.hidden=!fw;farbHinweis.hidden=!fw&&!vp;farbKnopf.title='Dieses Foto kolorieren'+(fw?' mit „'+fw+'“':'')+
  ' – Original oder verbesserte Fassung; das Ergebnis kommt in den Unterordner verbessert';
 farbHinweis.title='Kommt ans Ende des Prompts – '+(fw&&vp?'beim Verbessern und beim Kolorieren':fw?'beim Kolorieren':
  'beim Verbessern')+', z. B. „the dress is dark blue“; Enter = '+(fw?'Kolorieren':'Verbessern');
 verbKnopf.textContent=job&&job.s.art!=='kolorieren'?'Wird verbessert …':'✦ Verbessern';
 farbKnopf.textContent=job&&job.s.art==='kolorieren'?'Wird koloriert …':'◐ Kolorieren';
 vglKnopf.hidden=!vPaar(b);vglKnopf.setAttribute('aria-pressed',vergleich);vStatus.hidden=!job;
 if(job){const s=job.s,sek=Math.round((Date.now()-job.t0)/1000);
  vStatus.textContent=(s.art==='kolorieren'?'Kolorieren mit „':'Verbessern mit „')+s.workflow+'“: '+(s.platz?
   s.phase.replace('Warteschlange','wartet, Platz '+s.platz):s.phase)+' · '+Math.floor(sek/60)+':'+String(sek%60).padStart(2,'0');}}
async function verbessern(art){if(aktiv<0||!VW.length&&art==='verbessern'||vJob(aktiv))return;
 const i=aktiv,b=D.bilder[i],w=VW.length?wfAktuell():null;
 const [ok,j]=await post('/api/verbessern',{pfad:b.ordner+'/'+b.id,workflow:w?w.datei:'',art,
  farbhinweise:farbHinweis.hidden?'':farbHinweis.value.trim()});
 if(!ok){meldung(j.fehler||(art==='kolorieren'?'Kolorieren':'Verbessern')+' ließ sich nicht starten.',true);return;}
 vJobs[j.auftrag]={i,t0:Date.now(),s:{laeuft:true,phase:'Hochladen',workflow:j.workflow||(w&&w.name)||'',art}};
 meldung(j.meldung);verbLupe();vAbfragen();}
async function vAbfragen(){clearTimeout(vTimer);const ids=Object.keys(vJobs).filter(k=>vJobs[k].s.laeuft);if(!ids.length)return;
 try{const r=await fetch('/api/verbessern?'+ids.map(k=>'id='+encodeURIComponent(k)).join('&'));const j=await r.json();
  for(const k of ids){const s=(j.auftraege||{})[k]||{laeuft:false,fehler:'bestof kennt den Auftrag nicht mehr (neu gestartet?).'};
   vJobs[k].s=Object.assign({workflow:vJobs[k].s.workflow,art:vJobs[k].s.art},s);if(!s.laeuft)vFertig(k);}}catch(_){}
 verbLupe();vTimer=setTimeout(vAbfragen,1500);}
function vFertig(k){const {i,s}=vJobs[k],b=D.bilder[i],farb=s.art==='kolorieren';
 if(s.fehler){meldung((farb?'Kolorieren':'Verbessern')+' fehlgeschlagen: '+s.fehler,true);return;}
 b.ng=s.ergebnis.g;b.paar=[b.g,s.ergebnis.g];  // Vergleich: dieses Foto <-> Ergebnis
 meldung((farb?'Koloriert: ':'Verbessert: ')+s.ergebnis.name+' – im Ordner direkt hinter dem Foto.',false,
  ['Ordner neu laden',()=>location.reload()]);
 if(aktiv===i&&!bearbeitet)vergleichAn(true);}
function vergleichAn(an){const b=aktiv>=0?D.bilder[aktiv]:null,p=an&&b?vPaar(b):null;
 if(!p){vergleichZu(true);return;}
 vergleich=true;gesichterAn=false;nbox.hidden=true;lupe.classList.add('vergleich-an');
 if(lupeImg.getAttribute('src')!==p[0])lupeImg.src=p[0];nachherImg.src=p[1];
 vLabels[0].href=origVon(p[0]);vLabels[1].href=origVon(p[1]);  // Schilder öffnen die Dateien (Herunterladen)
 vRegler.hidden=false;[nachherImg,trenner,...vLabels].forEach(x=>x.hidden=false);kaesten();vLagen();verbLupe();}
function vergleichZu(bildZurueck){if(!vergleich)return;vergleich=false;lupe.classList.remove('vergleich-an');
 vRegler.hidden=true;[nachherImg,trenner,...vLabels].forEach(x=>x.hidden=true);nachherImg.removeAttribute('src');
 const b=aktiv>=0?D.bilder[aktiv]:null;if(bildZurueck&&b&&lupeImg.getAttribute('src')!==b.g)lupeImg.src=b.g;verbLupe();}
function vLagen(){if(!vergleich||!lupeImg.complete||!lupeImg.naturalWidth)return;
 const r=lupeImg.getBoundingClientRect(),fr=flaeche.getBoundingClientRect(),x=r.left-fr.left,y=r.top-fr.top;
 Object.assign(nachherImg.style,{left:x+'px',top:y+'px',width:r.width+'px',height:r.height+'px',
  clipPath:'inset(0 0 0 '+vAnteil+'%)'});
 Object.assign(trenner.style,{left:(x+r.width*vAnteil/100-1)+'px',top:y+'px',height:r.height+'px'});
 vLabels[0].style.left=(x+8)+'px';vLabels[1].style.left=(x+r.width-8-vLabels[1].offsetWidth)+'px';
 vLabels.forEach(l=>{l.style.top=(y+8)+'px';});}
function vSetzen(ev){const r=lupeImg.getBoundingClientRect();if(!r.width)return;
 vAnteil=Math.max(0,Math.min(100,(ev.clientX-r.left)/r.width*100));vRegler.value=vAnteil;vLagen();}
flaeche.addEventListener('pointerdown',ev=>{if(!vergleich||ev.target.closest('a,button,input,.nennbox'))return;vZiehen=true;
 try{flaeche.setPointerCapture(ev.pointerId);}catch(_){}vSetzen(ev);ev.preventDefault();});
flaeche.addEventListener('pointermove',ev=>{if(vergleich&&vZiehen)vSetzen(ev);});
['pointerup','pointercancel'].forEach(t=>flaeche.addEventListener(t,()=>{vZiehen=false;}));
vRegler.addEventListener('input',()=>{vAnteil=+vRegler.value;vLagen();});
nachherImg.addEventListener('load',vLagen);lupeImg.addEventListener('load',vLagen);window.addEventListener('resize',vLagen);
verbKnopf.addEventListener('click',()=>verbessern('verbessern'));farbKnopf.addEventListener('click',()=>verbessern('kolorieren'));
farbHinweis.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();
 verbessern(farbWf()?'kolorieren':'verbessern');}});
vglKnopf.addEventListener('click',()=>vergleichAn(!vergleich));
"""

JS_BEARBEITEN = """
// Bearbeiten: drehen, spiegeln, Helligkeit, Kontrast, Sättigung – Vorschau per CSS, Speichern legt eine neue Fassung an
// im Modus {i, drehung, spiegeln, helligkeit, kontrast, saettigung}; var, weil andere Teile schon früher fragen
var bearbeitet=null;
const bLeiste=lupe.querySelector('.bearbeitung'),bSpeichern=bLeiste.querySelector('.speichern'),
 bRegler=[...bLeiste.querySelectorAll('input[type=range]')],REGLER=['helligkeit','kontrast','saettigung'],
 FILTER=['brightness','contrast','saturate'];  // dieselben Formeln rechnet bearbeiten.py
function bGeaendert(){const z=bearbeitet;return !!z&&(z.drehung!==0||z.spiegeln||REGLER.some(k=>z[k]!==0));}
function bVorschau(){const z=bearbeitet;if(!z)return;
 const w=lupeImg.offsetWidth,h=lupeImg.offsetHeight,quer=z.drehung%180!==0;  // 90°/270°: gedreht einpassen
 const s=quer&&w&&h?Math.min((flaeche.clientWidth-24)/h,(flaeche.clientHeight-24)/w):1;
 lupeImg.style.transform='scale('+s+')'+(z.spiegeln?' scaleX(-1)':'')+' rotate('+z.drehung+'deg)';
 lupeImg.style.filter=REGLER.map((k,n)=>FILTER[n]+'('+(1+z[k]/100)+')').join(' ');
 bRegler.forEach(e=>{const v=z[e.dataset.regler];e.value=v;e.nextElementSibling.textContent=(v>0?'+':'')+v;});
 bSpeichern.disabled=!bGeaendert();}
function bearbeitenAn(){if(aktiv<0||bearbeitet)return;vergleichZu(true);nennenZu();if(gesichterAn)gesichterUmschalten();
 bearbeitet={i:aktiv,drehung:0,spiegeln:false,helligkeit:0,kontrast:0,saettigung:0};
 lupe.classList.add('bearbeiten');lupe.querySelector('.leiste').hidden=true;bLeiste.hidden=false;bVorschau();}
function bearbeitenAus(){if(!bearbeitet)return;bearbeitet=null;lupe.classList.remove('bearbeiten');
 lupeImg.style.transform=lupeImg.style.filter='';bLeiste.hidden=true;lupe.querySelector('.leiste').hidden=false;
 if(aktiv>=0)lupeZeichne();}
function bSchritt(art){const z=bearbeitet;if(!z)return;
 if(art==='spiegeln')z.spiegeln=!z.spiegeln;  // gespiegelt dreht „rechts“ andersherum – so, wie man es sieht
 else z.drehung=(z.drehung+((art==='rechts')!==z.spiegeln?90:270))%360;
 bVorschau();}
function bTaste(ev){const k=ev.key;
 if(k==='Escape'){if(!bGeaendert()||confirm('Änderungen verwerfen?'))bearbeitenAus();}
 else if(k==='r'||k==='R')bSchritt(ev.shiftKey?'links':'rechts');
 else if(k==='h'||k==='H')bSchritt('spiegeln');
 else if(k!==' ')return;  // Leertaste (sonst Stern) löst keinen Knopf aus, der gerade den Fokus hat
 ev.preventDefault();}
async function bSpeichernKlick(){const z=bearbeitet;if(!z||!bGeaendert())return;const i=z.i,b=D.bilder[i];
 bSpeichern.disabled=true;bSpeichern.textContent='Speichern …';
 const daten={pfad:b.ordner+'/'+b.id,drehung:z.drehung,spiegeln:z.spiegeln};REGLER.forEach(k=>{daten[k]=z[k];});
 const [ok,j]=await post('/api/bearbeiten',daten);bSpeichern.textContent='Speichern';
 if(!ok){bSpeichern.disabled=false;meldung(j.fehler||'Speichern fehlgeschlagen.',true);return;}
 bearbeitenAus();b.ng=j.ergebnis.g;b.paar=[b.g,j.ergebnis.g];  // Vergleich wie nach dem Verbessern
 meldung(j.meldung,false,['Ordner neu laden',()=>location.reload()]);
 if(aktiv===i&&z.drehung%180===0)vergleichAn(true);}  // um 90° gedreht: anderes Seitenverhältnis, kein Schieber
lupe.querySelector('.bearb').addEventListener('click',bearbeitenAn);
bLeiste.querySelectorAll('.dreh').forEach(k=>k.addEventListener('click',()=>bSchritt(k.dataset.schritt)));
bRegler.forEach(e=>{
 e.addEventListener('input',()=>{if(bearbeitet){bearbeitet[e.dataset.regler]=+e.value;bVorschau();}});
 e.addEventListener('dblclick',()=>{if(bearbeitet){bearbeitet[e.dataset.regler]=0;bVorschau();}});});
bLeiste.querySelector('.zuruecksetzen').addEventListener('click',()=>{if(!bearbeitet)return;
 Object.assign(bearbeitet,{drehung:0,spiegeln:false,helligkeit:0,kontrast:0,saettigung:0});bVorschau();});
bLeiste.querySelector('.abbrechen').addEventListener('click',bearbeitenAus);
bSpeichern.addEventListener('click',bSpeichernKlick);
window.addEventListener('resize',bVorschau);lupeImg.addEventListener('load',bVorschau);
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


def korb_knopf(taste=""):
    return (f'<button class="knopf korb" type="button" aria-label="In den Papierkorb" title="In den Papierkorb '
            f'(Ordner {PAPIERKORB}){taste}"><svg viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="M4 7h16M10 7V4.5h4V7M6.2 7l1 13h9.6l1-13M10 11v6M14 11v6"/></svg></button>')


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


def import_frei(app):
    """Import und Ordnerwahl nur für Anfragen von dem Rechner, auf dem bestof.py läuft (Handler._lokal):
    Die Ordnerwahl zeigt dessen Laufwerke – das soll niemand aus dem Heimnetz sehen."""
    return app.import_erlaubt and getattr(getattr(app, "anfrage", None), "lokal", False)


def kopf(app, aktiv="", inhalt_titel="", suchtext=""):
    text, laeuft = status_text(app)
    navi = [("ordner", "/", "Ordner")]
    if import_frei(app):
        navi.append(("import", "/import", "Import"))
    if app.index:
        navi.append(("alben", "/alben", "Alben"))
        navi.append(("personen", "/personen", "Personen"))
    navi.append(("einstellungen", "/einstellungen", "Einstellungen"))
    links = "".join(f'<a href="{url}"{" aria-current=page" if k == aktiv else ""}>{t}</a>' for k, url, t in navi)
    suche = ""
    if app.index:
        suche = (f'<form class="suche" action="/suche" role="search"><input name="q" value="{e(suchtext)}" '
                 f'placeholder="Filter, z. B. 2023, Leipzig, Anna" aria-label="Filter" title="Begriffe mit Komma trennen. '
                 f'Alben mit + verknüpft zeigen Fotos, die in allen sind: Reisen + Paris">'
                 f'<button class="knopf">Filtern</button>'
                 f'<a class="knopf" href="/suche?{urlencode({"q": ALLE_FOTOS})}" title="Alle Fotos nach Datum – '
                 f'zum Einordnen in Alben und Jahre">{ALLE_FOTOS}</a>'
                 f'<a class="knopf" href="/suche?{urlencode({"q": OHNE_ALBUM})}" title="Fotos, die noch in keinem '
                 f'Album sind – zum Einordnen">{OHNE_ALBUM}</a></form>')
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


def farb_daten(app):
    """Für die Lupe: Kolorieren möglich (ffmpeg da)? Dann {"workflow": Name von FARBE_WORKFLOW oder None – dann
    kolorieren die Workflows mit Prompt-Text}, sonst None."""
    v = app.verbesserer
    if not (v and v.farbe):
        return None
    fw = v.farb_wf()
    return {"workflow": fw["name"] if fw else None}


def fassung_name(name, original):
    """„verbessert/IMG_0001_Foto_restore_2.png“ -> „Foto restore 2“: was hinter dem Namen des Originals steht."""
    stamm = os.path.splitext(name.split("/", 1)[1])[0]
    if original:
        stamm = stamm[len(os.path.splitext(original)[0]) + 1:]
    return stamm.replace("_", " ").strip() or "verbessert"


def bogen_html(app, eintraege, einordner, abzeichen=None):
    """eintraege: [(ordner, name, mtime, groesse)] -> (HTML der Felder, Bilddaten für JS). abzeichen: {„0004/<id>“:
    (Text, Titel, Klasse)} – ein Schild unten rechts im Foto, z. B. der Abstand auf der Seite „Ähnliche Fotos“."""
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
    felder, daten, fassungen = [], [], {}
    for i, (o, name, mt, groesse) in enumerate(eintraege):
        uid = url_id(name)
        rel = f"{o}/{uid}"
        if o not in fassungen:  # verbesserte Fassungen: Original <-> neueste Fassung, für Abzeichen und Vergleich
            herkunft, mts = app.archiv.herkunft(o), {n: m for n, _, m in app.archiv.bilder(o)}
            neueste = {}
            for v, original in herkunft.items():
                if original in mts and v in mts and mts[v] >= mts.get(neueste.get(original), 0):
                    neueste[original] = v
            fassungen[o] = (herkunft, mts, neueste)
        herkunft, mts, neueste = fassungen[o]
        vg = ng = wf = None
        if name.startswith(VERBESSERT + "/"):
            original = herkunft.get(name)
            wf = fassung_name(name, original)
            vg = f"/g/{o}/{url_id(original)}?v={mts[original]}" if original in mts else None
            stamm, endung = os.path.splitext(name)
            basis = stamm[:-len(KOLORIERT) - 1] + endung if stamm.endswith(f"_{KOLORIERT}") else None
            farbig = f"{stamm}_{KOLORIERT}.png"
            if basis in mts:  # kolorierte Fassung: vorher = ihre Restaurierung
                vg = f"/g/{o}/{url_id(basis)}?v={mts[basis]}"
            if farbig in mts:  # Restaurierung: nachher = ihre kolorierte Fassung
                ng = f"/g/{o}/{url_id(farbig)}?v={mts[farbig]}"
        elif name in neueste:
            ng = f"/g/{o}/{url_id(neueste[name])}?v={mts[neueste[name]]}"
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
            f'<span class="buchstabe" aria-hidden="true"></span>{nr}'
            + (f'<span class="vbadge" title="Fassung im Unterordner verbessert">✦ {e(wf)}</span>' if wf else "")
            + (f'<span class="abadge {ab[2]}" title="{e(ab[1])}">{e(ab[0])}</span>'
               if (ab := (abzeichen or {}).get(rel)) else "")
            + '</div>'
            f'<figcaption><span class="lfd">{i + 1}</span><span class="dateiname" title="{e(name)}">'
            f'{e(os.path.basename(name))}</span>'
            f'{STERN_KNOPF}{korb_knopf()}<button class="knopf holen" type="button" title="Aus dem Papierkorb '
            f'zurück in den Ordner">Zurückholen</button>'
            f'<span class="technik{" spitze" if oben else ""}"'
            + (' title="Höchste Auflösung in diesem Ordner"' if oben else "") + f'>{e(technik)}</span>'
            f'<span class="meta">{jahr_html}<span class="mtext">{meta_html}</span></span>'
            + ('<span class="alben"></span>' if app.index else "") + '</figcaption></figure>')
        karte = (f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=14/{lat:.5f}/{lon:.5f}"
                 if lat is not None else "")
        daten.append({"id": uid, "ordner": o, "name": anzeige(os.path.basename(name)), "g": f"/g/{o}/{uid}?v={mt}",
                      "o": f"/orig/{o}/{uid}", "z": zeit_text(zeit), "zm": monat, "ol": ort_text(ort, km, kurz=False),
                      "ok": ort_text(ort, km), "j": jahr, "jm": jm is not None, "k": karte, "f": f, "fs": such_stand,
                      "t": technik, "a": alben.get(rel, []),
                      **{k: v for k, v in (("vg", vg), ("ng", ng), ("wf", wf)) if v}})
    return "".join(felder), daten


BEARBEITUNG_HTML = (
    '<div class="bearbeitung" hidden><span class="btitel">Bearbeiten</span>'
    '<button class="knopf dreh" type="button" data-schritt="links" aria-label="90° nach links drehen" '
    'title="90° nach links drehen (Umschalt+R)">↺</button>'
    '<button class="knopf dreh" type="button" data-schritt="rechts" aria-label="90° nach rechts drehen" '
    'title="90° nach rechts drehen (Taste R)">↻</button>'
    '<button class="knopf dreh" type="button" data-schritt="spiegeln" aria-label="Waagerecht spiegeln" '
    'title="Waagerecht spiegeln (Taste H)">⇋</button>'
    + "".join(f'<label>{text}<input type="range" min="-100" max="100" step="1" value="0" data-regler="{k}" '
              f'title="Doppelklick = zurück auf 0"><output>0</output></label>'
              for k, text in (("helligkeit", "Helligkeit"), ("kontrast", "Kontrast"), ("saettigung", "Sättigung")))
    + '<button class="knopf zuruecksetzen" type="button">Zurücksetzen</button>'
    '<button class="knopf abbrechen" type="button" title="Ohne Speichern zurück (Esc)">Abbrechen</button>'
    '<button class="knopf speichern" type="button" title="Neue Fassung …_bearbeitet.png im Unterordner verbessert '
    'anlegen – das Foto bleibt unverändert">Speichern</button></div>')

LUPE_HTML = ('<div class="lupe" hidden role="dialog" aria-label="Lupe"><div class="flaeche"><img alt="">'
             '<img class="nachher" alt="" hidden><div class="trenner" hidden></div>'
             '<a class="vlabel" target="_blank" rel="noopener" hidden title="Datei öffnen">Vorher ↗</a>'
             '<a class="vlabel" target="_blank" rel="noopener" hidden title="Datei öffnen">Nachher ↗</a>'
             '<p class="vstatus" hidden role="status"></p>'
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
             + STERN_KNOPF + korb_knopf(" – Taste Entf") +
             '<button class="knopf bearb" type="button" title="Drehen, spiegeln, Helligkeit, Kontrast, Sättigung – '
             'gespeichert wird eine neue Fassung, das Foto bleibt (Taste E)">✎ Bearbeiten</button>'
             '<select class="wfwahl" aria-label="Workflow zum Verbessern" hidden></select>'
             '<button class="knopf verb" type="button" hidden title="Dieses Foto mit dem gewählten Workflow verbessern – '
             'das Ergebnis kommt in den Unterordner verbessert, das Foto bleibt">✦ Verbessern</button>'
             '<input class="farbhinweis" maxlength="300" autocomplete="off" '
             'aria-label="Farbhinweise für den Prompt beim Verbessern und Kolorieren" hidden '
             'placeholder="Farbhinweise (optional)">'
             '<button class="knopf farb" type="button" hidden title="Dieses Foto kolorieren – Original oder verbesserte '
             'Fassung; das Ergebnis kommt in den Unterordner verbessert">◐ Kolorieren</button>'
             '<button class="knopf vgl" type="button" aria-pressed="false" hidden title="Vorher/Nachher vergleichen '
             '(Taste V)">Vergleich</button>'
             '<input class="vregler" type="range" min="0" max="100" step="0.5" value="50" aria-label="Vorher/Nachher" hidden>'
             '<button class="knopf almark" type="button" aria-pressed="false" title="Taste A" hidden></button>'
             '<button class="knopf alb" type="button" title="Alben zuordnen (Taste A)">Alben</button>'
             '<button class="knopf gz" type="button" title="Taste G">Gesichter</button>'
             '<a class="knopf karte" target="_blank" rel="noopener noreferrer">Karte</a>'
             '<a class="knopf aehnl" title="Ähnliche Fotos im Archiv suchen – nach Ähnlichkeit sortiert">≈ Ähnliche</a>'
             '<a class="knopf orig" target="_blank" rel="noopener">Original</a>'
             '<button class="knopf zu" type="button">Schließen</button></div>' + BEARBEITUNG_HTML + '</div>')

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


VERSCHIEBEN_HILFE = (' Gehören Fotos nicht in diesen Ordner: „Fotos verschieben …“, Fotos anklicken (Umschalt = Bereich), '
                     'dann „In neue Gruppe“ oder die Nummer eines anderen Ordners – mit NEF, Fassungen, Sternen und '
                     'Alben, „Rückgängig“ inklusive.')


def bogen_hilfe(app, einordner=False):
    """Hilfezeile unter dem Kontaktbogen (Ordner und Filter)."""
    text = (f'Bild anklicken zum Vergrößern. ☆ unter dem Bild = Stern: kopiert es nach BestOf (je Ordner höchstens '
            f'{app.auswahl.max_best}). Der Eimer daneben schiebt das Foto in den Papierkorb (Ordner {PAPIERKORB}, '
            f'mit „Rückgängig“; endgültig löschen geht nur im Dateimanager). In der Lupe: <kbd>←</kbd> <kbd>→</kbd> '
            f'blättern, <kbd>Leertaste</kbd> oder <kbd>S</kbd> Stern, <kbd>Entf</kbd> Papierkorb, <kbd>V</kbd> '
            f'Vorher/Nachher, ')
    verbessern = ' „≈ Ähnliche“ in der Lupe sucht die ähnlichsten Fotos im ganzen Archiv.' + (
        ' „✦ Verbessern“ in der Lupe schickt das Foto an ComfyUI; die neue Fassung kommt in den Unterordner '
        f'„{VERBESSERT}“ und steht nach dem Neuladen als eigene Kachel hinter dem Original.' if app.verbesserer else '')
    if farb_daten(app):
        verbessern += (' „◐ Kolorieren“ färbt das gezeigte Foto ein – das Original direkt oder eine verbesserte Fassung '
                       '(…_koloriert.png); Helligkeit und Details bleiben die des Fotos.')
    if not app.index:
        return f'<p class="hilfe">{text}<kbd>Esc</kbd> schließen.{verbessern}{VERSCHIEBEN_HILFE * einordner}</p>'
    return (f'<p class="hilfe">{text}<kbd>G</kbd> Gesichter (Namensschild anklicken = benennen, fehlt eins: ins '
            f'Gesicht klicken), <kbd>J</kbd> Jahr ändern, <kbd>A</kbd> Album, <kbd>Esc</kbd> schließen.{verbessern} '
            'Jahr korrigieren: ins Jahresfeld tippen, Enter; leeren = Jahr aus der Datei. Für viele Fotos: oben bei '
            '„Jahr per Klick“ das Jahr eintippen, dann → Jahr unter den Fotos anklicken (Umschalt = Bereich). '
            'Alben: oben ein Album wählen, dann ＋ unter den Fotos (Umschalt = Bereich); ein Album unter einem Foto '
            'anklicken zeigt alle Fotos darin. „Alle Fotos“ oben zeigt das ganze Archiv nach Datum, „Ohne Album“ '
            'die Fotos, die noch in keinem Album sind.' + VERSCHIEBEN_HILFE * einordner + '</p>')


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


VERSCHIEBEN_HTML = """<div class="wahlleiste" id="vsleiste" hidden><span id="vstext"></span>
<button class="knopf haupt" id="vszu" type="button" hidden disabled></button>
<button class="knopf haupt" id="vsneu" type="button" disabled>In neue Gruppe ({naechster})</button>
<form class="vsin" id="vsform"><input id="vsziel" class="pname" inputmode="numeric" maxlength="5" placeholder="Ordner"
 aria-label="Nummer des Zielordners" autocomplete="off"><button class="knopf" id="vsin" disabled>In diesen Ordner</button></form>
<button class="knopf" id="vsende" type="button">Fertig</button></div>"""


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
    if bilder:
        weg.append('<button class="knopf" id="verschieben" type="button" aria-pressed="false" title="Fotos auswählen, '
                   'die nicht in diese Gruppe gehören, und in eine neue Gruppe oder einen anderen Ordner verschieben">'
                   'Fotos verschieben …</button>')
    hoch = max(int(o) for o in liste)
    naechster = f"{hoch + 1:04d}" if hoch < MAX_ORDNER else None
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
        inhalt += ((ALBUMLEISTE if app.index else "") + f'<main class="bogen">{felder}</main>'
                   + bogen_hilfe(app, einordner=True) + VERSCHIEBEN_HTML.replace("{naechster}", naechster or "–"))
    inhalt += LUPE_HTML + (ALBBOX if app.index else "")
    markiert = app.auswahl.markiert(ordner)
    js = {"einordner": True, "ordner": ordner, "max": app.auswahl.max_best, "bilder": daten, "jahr": bool(app.index),
          "namen": namensliste(app.index), "gesichter": bool(app.indexer and app.indexer.gesichter_aktiv),
          "auswahl": {ordner: [url_id(m) for m in markiert]},
          "ziele": {ordner: {url_id(m): z for m, z in app.auswahl.ziele(ordner).items()}},
          "zurueck": f"/o/{zurueck}" if zurueck else None, "weiter": f"/o/{weiter}" if weiter else None,
          "offen": f"/weiter/{ordner}", "uebersicht": f"/?seite={seite_nr}", "naechster": naechster,
          "alben": alben_liste(app.index) if app.index else None,
          "verbessern": app.verbesserer.fuer_seite() if app.verbesserer else [], "kolorieren": farb_daten(app),
          "vorwahl": app.verbesserer.vorwahl if app.verbesserer else ""}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{ordner} – BestOf", inhalt, JS_BOGEN + JS_ALBEN + JS_VERBESSERN + JS_BEARBEITEN + JS_VERSCHIEBEN)


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
    ohne_album = "ohne Album" in erklaerung  # Einordnen: Fotos, die ein Album bekommen, werden hier blass
    titel = (f'<div class="titel"><div><p id="info">{stand}</p><p class="ziel" id="ziel"></p>'
             + ('<p class="leise" id="ohnealbum"></p>' if ohne_album and eintraege else "") + '</div></div>')
    inhalt = kopf(app, "", titel, text)
    if erklaerung:
        inhalt += f'<div class="filter" aria-label="Erkannter Filter">{chips}</div>'
    if not text.strip():
        inhalt += ('<p class="leer">Geben Sie Begriffe mit Komma getrennt ein, z. B. 2023, Leipzig, Anna – '
                   'oder „Alle Fotos“ für das ganze Archiv. Reisen + Paris zeigt die Fotos, die in beiden Alben '
                   'sind.</p>')
    elif not eintraege and ohne_album and len(erklaerung) == 1:
        inhalt += '<p class="leer">Jedes Foto ist in mindestens einem Album.</p>'
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
          "alben": alben_liste(app.index) if app.index else None, "suche": text.strip() or None, "treffer": gesamt,
          "ohne_album": ohne_album,
          "verbessern": app.verbesserer.fuer_seite() if app.verbesserer else [], "kolorieren": farb_daten(app),
          "vorwahl": app.verbesserer.vorwahl if app.verbesserer else ""}
    inhalt += f'<script type="application/json" id="daten">{json_im_html(js)}</script>'
    return seite(f"{text} – BestOf", inhalt, JS_BOGEN + JS_ALBEN + JS_VERBESSERN + JS_BEARBEITEN)


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
            "ORDER BY b.sortzeit IS NULL, b.sortzeit, length(b.ordner), b.pfad"):
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
        f'<figure class="gesicht wahl" data-id="{gid}" title="{e(name_aus_id(gp.split("/", 1)[1]))} (Ordner {gp.split("/", 1)[0]})">'
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


ZUSAMMEN_HTML = """<div class="wahlleiste" id="wahlleiste" hidden><span id="wahltext"></span>
<button class="knopf haupt" id="zstart" type="button" disabled>Zusammenfassen …</button>
<button class="knopf" id="zende" type="button">Fertig</button></div>
<div class="zdialog" id="zdialog" hidden role="dialog" aria-modal="true" aria-labelledby="ztitel"><div class="zbox">
<h2 id="ztitel">Ordner zusammenfassen</h2><p id="zliste" class="zliste"></p>
<label class="zziel">Alle Fotos kommen nach <select id="zziel"></select></label><p id="zinfo" class="leise"></p>
<section class="zanalyse"><h3>Welche Ähnlichkeit hätte gereicht?</h3><div id="zanalyse"></div></section>
<div class="knopfzeile"><button class="knopf haupt" id="zok" type="button">Zusammenfassen</button>
<button class="knopf" id="zab" type="button">Abbrechen</button></div></div></div>"""


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
        kacheln.append(f'<a class="kachel{" gewaehlt" if markiert else ""}" href="/o/{o}" data-o="{o}">'
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
                 f'maxlength="5" placeholder="Ordner" aria-label="Ordnernummer"><button class="knopf">Öffnen</button></form>'
                 f'<button class="knopf rechts" id="zusammen" type="button" aria-pressed="false" title="Ordner mit '
                 f'ähnlichen Fotos auswählen und zu einem zusammenfassen">Ordner zusammenfassen</button>'
                 f'<button class="knopf" id="neuaufbau" type="button">BestOf neu aufbauen</button></div>')
    if not alle:
        hauptteil = (f'<p class="leer">Keine Ordner 0001–99999 gefunden in {e(app.archiv.pfad)}. '
                     f'Prüfen Sie den Pfad beim Start.</p>')
    elif not liste:
        hauptteil = '<p class="leer">Jeder Ordner hat ein Bild mit Stern.</p>' if filt == "ohne" else \
            '<p class="leer">Noch keine Sterne. Öffnen Sie einen Ordner und markieren Sie bis zu ' \
            f'{bilder_text(app.auswahl.max_best)} mit ☆ – sie landen in BestOf.</p>'
    else:
        hauptteil = f'<main class="raster">{"".join(kacheln)}</main>' + ZUSAMMEN_HTML
    nav = seiten_nav(seite_nr, seiten, lambda n: f"/?filter={filt}&seite={n}")
    quelle = ('<p class="quelle">Ortsnamen: GeoNames (CC BY 4.0). Gesichtserkennung lokal mit YuNet und SFace '
              '(OpenCV Zoo).</p>' if app.index else "")
    return seite("BestOf – " + os.path.basename(app.archiv.pfad),
                 kopf(app, "ordner", titel) + werkzeuge + hauptteil + nav + quelle, JS_UEBERSICHT)
