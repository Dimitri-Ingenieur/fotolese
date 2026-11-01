"""fotolese.web.einstellungen – Seite „Einstellungen“: Werte ansehen und ändern, Workflows, Neu gruppieren.

Geändert wird bestof.conf (Kommentare und eigene Zeilen bleiben); die Werte gelten sofort. Was eine
Umgebungsvariable setzt, hat Vorrang und lässt sich hier nicht ändern. Die ComfyUI-Adresse und das Hochladen von
Workflows gehen nur an diesem Rechner – beides bestimmt, was ComfyUI ausführt.
"""
import json
import os
import re

from fotolese.web import konfig
from fotolese.web.konfig import e
from fotolese.web.html import json_im_html, kopf, seite
from fotolese.web.kolorieren import OHNE_PROMPT, STANDARD_PROMPT
from fotolese.web.verbessern import Comfy, Workflows, workflow_namen

MAX_WORKFLOW = 2 * 1024 * 1024  # Bytes: größere Workflow-Dateien nimmt die Seite nicht an


class Feld:
    """Eine Einstellung: Name in bestof.conf, Anzeige, Art (int, float, bool, wahl, text, textlang, workflow,
    farbworkflow), Standard, Grenzen bzw. Wahlmöglichkeiten; lokal = nur an diesem Rechner änderbar."""

    def __init__(self, name, titel, art, standard, hilfe="", grenzen=None, wahl=None, lokal=False):
        self.name, self.titel, self.art, self.standard, self.hilfe = name, titel, art, standard, hilfe
        self.grenzen, self.wahl, self.lokal = grenzen, wahl, lokal


GRUPPEN = [
    ("gruppierung", "Ähnlichkeit beim Import",
     "So legt fotosort ähnliche Fotos in einen Ordner – beim Import und bei „Neu gruppieren“ unten. Der Abstand "
     "zweier Fotos zählt die verschiedenen Bits zweier Bild-Fingerabdrücke (pHash und dHash, 0–128): 0 = gleich, "
     "um 60 = ganz verschieden.", [
         Feld("SCHWELLE", "Bildvergleich", "int", 20, "Höchster Abstand für dasselbe Motiv – in anderer Größe, "
              "Kompression oder leicht bearbeitet. Höher = mehr kommt zusammen.", (0, 128)),
         Feld("SERIE_SEK", "Serie: Zeitabstand (Sekunden)", "float", 3.0, "Serienbilder derselben Kamera: höchstens "
              "so viele Sekunden bis zum Nachbarbild …", (0, 86400)),
         Feld("SERIE_SCHWELLE", "Serie: Abstand", "int", 36, "… und höchstens dieser Abstand.", (0, 128)),
         Feld("EINZELN", "Einzelbilder", "wahl", "ordner", "Fotos, zu denen nichts passt.", None,
              [("ordner", "je ein eigener Ordner"), ("0000", "alle in Ordner 0000")]),
     ]),
    ("verbessern", "Verbessern mit ComfyUI",
     "Workflows sind in ComfyUI mit „Export (API)“ gespeicherte JSON-Dateien im Ordner workflows.", [
         Feld("COMFYUI", "ComfyUI-Adresse", "text", "http://127.0.0.1:8188", "0 = Verbessern aus (gilt nach dem "
              "Neustart). Nur an diesem Rechner änderbar.", lokal=True),
         Feld("VERBESSERN_WORKFLOW", "Workflow für „Verbessern“", "workflow", "", "In der Lupe vorgewählt; leer = der "
              "zuletzt dort gewählte."),
         Feld("FARBE_WORKFLOW", "Workflow für die Kolorierung", "farbworkflow", "", "Zweiter Lauf auf der "
              "restaurierten Fassung; leer = derselbe Workflow wie beim Verbessern. Braucht einen Prompt-Text."),
     ]),
    ("kolorierung", "Kolorierung",
     "Zweiter Lauf nach der Restaurierung, braucht ffmpeg. Ergebnis <Name>_<Workflow>_koloriert.png.", [
         Feld("COLORIZE_DEFAULT", "Vorwahl in der Lupe", "wahl", "off", "", None,
              [("off", "aus"), ("on", "an"), ("auto", "nur Schwarzweiß und Sepia")]),
         Feld("COLORIZE_RESTORE_LORA", "Restore-LoRA im zweiten Lauf", "float", 0.0, "0 = aus; 0,3–0,5 hilft bei "
              "Farbsäumen.", (0, 1)),
         Feld("COLORIZE_LUMA_LOCK", "Luma-Lock", "bool", True, "Helligkeit und Details aus der Restaurierung, nur die "
              "Farbe aus dem zweiten Lauf."),
         Feld("COLORIZE_CHROMA_BLUR", "Farbe weichzeichnen (Sigma)", "float", 0.0, "Gegen Farbsäume; 0 = aus.",
              (0, 20)),
         Feld("COLORIZE_MONO_THRESHOLD", "Schwelle für „nur Schwarzweiß“", "float", 10.0, "Farbstreuung darunter gilt "
              "als monochrom.", (0, 255)),
         Feld("COLORIZE_PROMPT", "Kolorier-Anweisung", "textlang", "", "Leer = eingebaute Anweisung (englisch)."),
         Feld("COLORIZE_KEEP_RAW", "Bild des zweiten Laufs behalten", "bool", False, "Zusätzlich als "
              "…_koloriert_roh.png."),
     ]),
    ("anzeige", "Anzeige", "", [
        Feld("MAX_BEST", "Sterne je Ordner", "int", 3, "So viele Bilder je Ordner kommen höchstens nach BestOf.",
             (1, 26)),
        Feld("PRO_SEITE", "Ordner je Übersichtsseite", "int", 120, "", (12, 2000)),
        Feld("NAEHE_KM", "Umkreis für Ortsfilter (km)", "float", 15.0, "", (0.5, 500)),
    ]),
    ("personen", "Personen",
     "bestof.py lernt Schwelle und Abstand aus Ihren Korrekturen nach (siehe Seite „Personen“).", [
         Feld("PERSON_SCHWELLE", "Ähnlichkeit für dieselbe Person", "float", 0.40, "Höher = strenger.", (0.1, 0.95)),
         Feld("ABSTAND", "Vorsprung vor anderen Personen", "float", 0.0, "So viel ähnlicher als jede andere benannte "
              "Person, sonst neue Gruppe.", (0, 0.3)),
         Feld("LERNEN", "Aus Korrekturen lernen", "bool", True, "Die beiden Werte oben automatisch anpassen."),
         Feld("LERNEN_AB", "Neu lernen nach … Korrekturen", "int", 5, "", (1, 100)),
         Feld("NACHZIEHEN", "Ähnliche Gesichter mitnehmen ab", "float", 0.50, "Beim Korrigieren wandern sehr ähnliche "
              "Gesichter derselben Gruppe mit; 1 = aus.", (0.3, 1)),
     ]),
    ("import", "Import", "", [
        Feld("IMPORT_JOBS", "Parallele Prozesse für fotosort", "int", None, "Quelle oder Archiv auf HDD/USB: 2–4. "
             "Standard: so viele wie für den Index.", (1, 64)),
    ]),
]
FELD = {f.name: f for _, _, _, felder in GRUPPEN for f in felder}


def _farbe(app):
    return app.verbesserer.farbe if app.verbesserer else None


def _farb_attr(attr, umrechnen=lambda w: w):
    def holen(app):
        f = _farbe(app)
        return getattr(f, attr) if f else None

    def setzen(app, w):
        f = _farbe(app)
        if f:
            setattr(f, attr, umrechnen(w))
    return holen, setzen


def _app_attr(attr):
    return (lambda app: getattr(app, attr)), (lambda app, w: setattr(app, attr, w))


def _gruppe(name):
    return (lambda app: app.gruppe[name]), (lambda app, w: app.gruppe.__setitem__(name, w))


def _comfy_setzen(app, w):
    if app.verbesserer and w != "0":
        app.verbesserer.comfy = Comfy(w)


def _verb_attr(attr):
    def holen(app):
        return getattr(app.verbesserer, attr) if app.verbesserer else None

    def setzen(app, w):
        if app.verbesserer:
            setattr(app.verbesserer, attr, w)
    return holen, setzen


ZUGRIFF = {  # Name -> (aktueller Wert oder None = aus bestof.conf lesen, sofort anwenden)
    **{n: _gruppe(n) for n in ("SCHWELLE", "SERIE_SEK", "SERIE_SCHWELLE", "EINZELN")},
    "COMFYUI": ((lambda app: app.verbesserer.comfy.basis if app.verbesserer else None), _comfy_setzen),
    "VERBESSERN_WORKFLOW": _verb_attr("vorwahl"),
    "FARBE_WORKFLOW": _verb_attr("farb_workflow"),
    "COLORIZE_DEFAULT": _farb_attr("standard"),
    "COLORIZE_RESTORE_LORA": _farb_attr("restore_lora"),
    "COLORIZE_LUMA_LOCK": _farb_attr("luma"),
    "COLORIZE_CHROMA_BLUR": _farb_attr("chroma_blur"),
    "COLORIZE_MONO_THRESHOLD": _farb_attr("schwelle"),
    "COLORIZE_PROMPT": ((lambda app: None), _farb_attr("prompt", lambda w: w.strip() or STANDARD_PROMPT)[1]),
    "COLORIZE_KEEP_RAW": _farb_attr("roh_behalten"),
    "MAX_BEST": ((lambda app: app.auswahl.max_best), (lambda app, w: setattr(app.auswahl, "max_best", w))),
    "PRO_SEITE": _app_attr("pro_seite"),
    "NAEHE_KM": _app_attr("naehe_km"),
    "PERSON_SCHWELLE": _app_attr("person_schwelle"),
    "ABSTAND": _app_attr("abstand"),
    "LERNEN": _app_attr("lernen"),
    "LERNEN_AB": _app_attr("lernen_ab"),
    "NACHZIEHEN": _app_attr("nachziehen"),
    "IMPORT_JOBS": _app_attr("import_jobs"),
}


def standard(app, feld):
    return app.index_jobs if feld.name == "IMPORT_JOBS" else feld.standard


def pruefen(app, feld, roh):
    """Eingabe -> Wert in der richtigen Art; ValueError mit Text für die Oberfläche."""
    if feld.art == "bool":
        if isinstance(roh, bool):
            return roh
        if str(roh).strip().lower() in ("1", "an", "ja", "true"):
            return True
        if str(roh).strip().lower() in ("0", "aus", "nein", "false"):
            return False
        raise ValueError(f"{feld.titel}: an oder aus.")
    text = str(roh).strip()
    if feld.art in ("int", "float"):
        try:
            wert = int(text) if feld.art == "int" else float(text.replace(",", "."))
        except ValueError:
            raise ValueError(f"{feld.titel}: bitte eine {'ganze ' if feld.art == 'int' else ''}Zahl eingeben.") from None
        unten, oben = feld.grenzen
        if not unten <= wert <= oben:
            raise ValueError(f"{feld.titel}: erlaubt sind {_zahl(unten)} bis {_zahl(oben)}.")
        return wert
    if feld.art == "wahl":
        if text not in [k for k, _ in feld.wahl]:
            raise ValueError(f"{feld.titel}: ungültige Wahl.")
        return text
    if feld.art in ("workflow", "farbworkflow"):
        if not text:
            return ""
        w = next((w for w in _workflows(app).brauchbar() if w["datei"] == text), None)
        if not w:
            raise ValueError(f"{feld.titel}: Workflow {text} gibt es nicht (oder er ist nicht brauchbar).")
        if feld.art == "farbworkflow" and not w["farbe"]:
            raise ValueError(f"{feld.titel}: „{w['name']}“ – {OHNE_PROMPT}")
        return text
    if "\n" in text or "\r" in text or '"' in text or len(text) > 2000:
        raise ValueError(f"{feld.titel}: eine Zeile, ohne Anführungszeichen, höchstens 2000 Zeichen.")
    if feld.name == "COMFYUI" and text != "0" and not re.fullmatch(r"https?://[^\s/]+(:\d+)?/?", text):
        raise ValueError("ComfyUI-Adresse: z. B. http://127.0.0.1:8188 (oder 0 = aus).")
    return text


def _zahl(w):
    return f"{w:g}".replace(".", ",") if isinstance(w, float) else str(w)


def conf_text(feld, wert):
    """Wert, wie er in bestof.conf steht – Text mit # oder Rand-Leerzeichen in Anführungszeichen."""
    if feld.art == "bool":
        return "1" if wert else "0"
    if feld.art == "float":
        return f"{wert:g}"
    text = str(wert)
    return f'"{text}"' if ("#" in text or text != text.strip()) else text


def anzeige(feld, wert):
    """Wert, wie ihn das Eingabefeld zeigt (Zahlen mit Komma)."""
    if feld.art == "bool":
        return "1" if wert else "0"
    if feld.art == "float":
        return _zahl(float(wert))
    return "" if wert is None else str(wert)


def wert(app, feld):
    """Der Wert, der gerade gilt: aus dem laufenden Programm, sonst wie in Umgebung/bestof.conf/Standard."""
    holen = ZUGRIFF[feld.name][0]
    aktuell = holen(app)
    if aktuell is not None and feld.name != "COMFYUI":
        return aktuell
    roh = os.environ.get(feld.name, "").strip() or (konfig.KONFIG.werte.get(feld.name, "").strip()
                                                    if konfig.KONFIG else "")
    if not roh:
        return standard(app, feld)
    try:
        return pruefen(app, feld, roh) if feld.art not in ("workflow", "farbworkflow") else roh
    except ValueError:
        return standard(app, feld)


def quelle(feld):
    if os.environ.get(feld.name, "").strip():
        return "Umgebung"
    if konfig.KONFIG and konfig.KONFIG.werte.get(feld.name, "").strip():
        return "bestof.conf"
    return "Standard"


def _lokal(app):
    return bool(getattr(getattr(app, "anfrage", None), "lokal", False))


def _workflows(app):
    return app.verbesserer.workflows if app.verbesserer else Workflows(app.workflow_ordner)


def feld_daten(app, feld):
    w = wert(app, feld)
    q = quelle(feld)
    d = {"wert": anzeige(feld, w), "quelle": q, "standard": anzeige(feld, standard(app, feld)),
         "gesperrt": "Umgebung" if q == "Umgebung" else ("lokal" if feld.lokal and not _lokal(app) else "")}
    if feld.name == "COMFYUI" and app.verbesserer and str(w).rstrip("/") != app.verbesserer.comfy.basis:
        d["hinweis"] = f"Läuft noch mit {app.verbesserer.comfy.basis} – gilt nach dem Neustart."
    elif feld.name == "COMFYUI" and not app.verbesserer and w != "0":
        d["hinweis"] = "Verbessern ist aus – gilt nach dem Neustart."
    return d


def einstellungen_api(app, daten):
    """POST /api/einstellungen {werte: {NAME: Wert oder None = Standard}} – prüfen, in bestof.conf schreiben,
    sofort anwenden. Rückgabe: (Code, Antwort mit den neuen Felddaten)."""
    werte = daten.get("werte")
    if not isinstance(werte, dict) or not werte or len(werte) > len(FELD):
        return 400, {"fehler": "Ungültige Anfrage."}
    neu = {}
    for name, roh in werte.items():
        feld = FELD.get(name)
        if not feld:
            return 400, {"fehler": f"Unbekannte Einstellung {name}."}
        if os.environ.get(name, "").strip():
            return 409, {"fehler": f"{feld.titel}: über die Umgebungsvariable {name} gesetzt – die hat Vorrang und "
                                   "lässt sich hier nicht ändern."}
        if feld.lokal and not _lokal(app):
            return 403, {"fehler": f"{feld.titel}: nur an dem Rechner änderbar, auf dem bestof.py läuft."}
        try:
            neu[name] = None if roh is None else pruefen(app, feld, roh)
        except ValueError as fehler:
            return 400, {"fehler": str(fehler), "feld": name}
    if not konfig.KONFIG or not konfig.KONFIG.setzen({n: None if w is None else conf_text(FELD[n], w)
                                                       for n, w in neu.items()}):
        return 500, {"fehler": "bestof.conf lässt sich nicht schreiben – Werte unverändert."}
    texte = []
    for name, w in neu.items():
        feld = FELD[name]
        gilt = standard(app, feld) if w is None else w
        konfig.QUELLE[name] = "Standard" if w is None else "bestof.conf"
        ZUGRIFF[name][1](app, gilt)
        texte.append(f"{feld.titel} = {anzeige(feld, gilt) or '–'}" + (" (Standard)" if w is None else ""))
    return 200, {"meldung": "Gespeichert: " + "; ".join(texte) + ".",
                 "felder": {n: feld_daten(app, FELD[n]) for n in neu}}


def workflow_hochladen(app, daten):
    """POST /api/workflow {name, daten, ersetzen}: Workflow im API-Format in den Ordner workflows legen."""
    if not _lokal(app):
        return 403, {"fehler": "Workflows hochladen geht nur an dem Rechner, auf dem bestof.py läuft."}
    name = os.path.basename(str(daten.get("name") or "").replace("\\", "/")).strip()
    stamm = re.sub(r"\.json$", "", name, flags=re.IGNORECASE)
    stamm = re.sub(r"[^\w .()-]+", "_", stamm).strip(" ._")[:80]
    if not stamm:
        return 400, {"fehler": "Bitte eine JSON-Datei wählen."}
    inhalt = daten.get("daten")
    if not isinstance(inhalt, dict) or not inhalt:
        return 400, {"fehler": "Die Datei ist kein JSON-Workflow."}
    if "nodes" in inhalt and "links" in inhalt:
        return 400, {"fehler": "Das ist das normale Workflow-Format. Bitte in ComfyUI mit „Export (API)“ speichern."}
    knoten = [v for v in inhalt.values() if isinstance(v, dict) and isinstance(v.get("inputs"), dict)
              and v.get("class_type")]
    if not knoten:
        return 400, {"fehler": "Keine ComfyUI-Knoten gefunden – ist das ein Workflow im API-Format?"}
    ordner = app.workflow_ordner
    datei = stamm + ".json"
    ziel = os.path.join(ordner, datei)
    if os.path.exists(ziel) and not daten.get("ersetzen"):
        return 409, {"fehler": f"{datei} gibt es schon.", "ersetzen": True}
    try:
        os.makedirs(ordner, exist_ok=True)
        tmp = os.path.join(ordner, f".{datei}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(inhalt, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ziel)
    except OSError as fehler:
        return 500, {"fehler": f"Speichern fehlgeschlagen: {fehler.strerror or fehler}"}
    w = next((w for w in _workflows(app).liste() if w["datei"] == datei), None)
    if w and w["fehler"]:
        return 200, {"meldung": f"{datei} gespeichert, aber nicht brauchbar: {w['fehler']}.", "workflows":
                     workflow_liste(app)}
    farbe = " – kann auch kolorieren" if w and w["farbe"] else ""
    return 200, {"meldung": f"Workflow „{workflow_namen(datei)[0]}“ gespeichert{farbe}.", "workflows": workflow_liste(app)}


def workflow_liste(app):
    return [{"datei": w["datei"], "name": w["name"], "fehler": w["fehler"], "farbe": bool(w["farbe"])}
            for w in _workflows(app).liste()]


def _eingabe(app, feld, d):
    """HTML des Eingabefelds."""
    aus = " disabled" if d["gesperrt"] else ""
    attr = f'id="f_{feld.name}" class="wert" data-wert="{e(d["wert"])}"{aus}'
    if feld.art == "bool":
        return f'<label class="schalter"><input type="checkbox" {attr}{" checked" if d["wert"] == "1" else ""}> an</label>'
    if feld.art in ("wahl", "workflow", "farbworkflow"):
        if feld.art == "wahl":
            optionen = list(feld.wahl)
        else:
            leer = "– zuletzt gewählter –" if feld.art == "workflow" else "– wie beim Verbessern –"
            optionen = [("", leer)] + [(w["datei"], w["name"] + ("" if w["farbe"] or feld.art == "workflow"
                                                                  else " (kein Prompt gefunden)"))
                                       for w in _workflows(app).brauchbar()]
            if d["wert"] and d["wert"] not in [k for k, _ in optionen]:
                optionen.append((d["wert"], f"{d['wert']} (fehlt)"))
        return f'<select {attr}>' + "".join(
            f'<option value="{e(k)}"{" selected" if k == d["wert"] else ""}>{e(t)}</option>' for k, t in optionen) + \
            "</select>"
    if feld.art == "textlang":
        platzhalter = e(STANDARD_PROMPT) if feld.name == "COLORIZE_PROMPT" else ""
        return f'<textarea {attr} rows="3" placeholder="{platzhalter}">{e(d["wert"])}</textarea>'
    modus = ' inputmode="decimal"' if feld.art in ("int", "float") else ""
    return f'<input type="text" {attr}{modus} value="{e(d["wert"])}" spellcheck="false" autocomplete="off">'


def _zeile(app, feld):
    d = feld_daten(app, feld)
    sperre = {"Umgebung": f"gesetzt über die Umgebungsvariable {feld.name}",
              "lokal": "nur an diesem Rechner änderbar"}.get(d["gesperrt"], "")
    std = "" if d["gesperrt"] else (f'<button type="button" class="knopf klein std" title="Standard: '
                                    f'{e(d["standard"] or "leer")}">Standard</button>')
    return (f'<div class="ezeile" data-name="{feld.name}" data-art="{feld.art}"><label for="f_{feld.name}">'
            f'{e(feld.titel)}</label><div class="eingabe">{_eingabe(app, feld, d)}{std}</div>'
            f'<p class="hilfe0">{e(feld.hilfe)} <span class="equelle">{e(d["quelle"])}</span>'
            f'{" " + e(sperre) + "." if sperre else ""}<span class="ehinweis">{e(d.get("hinweis", ""))}</span></p></div>')


def einstellungen_seite(app):
    pfad = konfig.KONFIG.pfad if konfig.KONFIG and _lokal(app) else "bestof.conf"  # Pfade nur an diesem Rechner
    titel = ('<div class="titel"><h1>Einstellungen</h1><div><p class="pfad">gespeichert in '
             f'{e(pfad)}</p></div></div>')
    abschnitte = []
    for schluessel, ueberschrift, text, felder in GRUPPEN:
        zusatz = ""
        if schluessel == "kolorierung" and not _farbe(app):
            zusatz = ('<p class="hilfe0 warn">' + ("Verbessern ist aus (COMFYUI = 0) – die Werte gelten nach dem "
                                                     "Neustart." if not app.verbesserer else
                                                     "ffmpeg fehlt – ohne ffmpeg gibt es keine Kolorierung.") + "</p>")
        if schluessel == "verbessern":
            zusatz = _workflow_html(app)
        abschnitte.append(
            f'<section class="egruppe" id="{schluessel}"><h2>{e(ueberschrift)}</h2>'
            + (f'<p class="hilfe0">{e(text)}</p>' if text else "") + zusatz
            + "".join(_zeile(app, f) for f in felder)
            + '<div class="knopfzeile"><button class="knopf haupt speichern" type="button" disabled>Speichern'
              '</button></div></section>')
        if schluessel == "gruppierung":
            abschnitte.append(NEU_HTML)
    inhalt = kopf(app, "einstellungen", titel) + '<main class="import einst">' + "".join(abschnitte) + "</main>"
    daten = {"lokal": _lokal(app), "workflows": workflow_liste(app), "max_workflow": MAX_WORKFLOW}
    return seite("Einstellungen – BestOf", inhalt, f"const E={json_im_html(daten)};" + JS_EINSTELLUNGEN)


def _workflow_html(app):
    hochladen = ('<div class="knopfzeile"><label class="knopf" for="wfdatei">Workflow hochladen …</label>'
                 '<input type="file" id="wfdatei" accept=".json,application/json" hidden></div>'
                 if _lokal(app) else '<p class="hilfe0">Workflows hochladen geht nur an dem Rechner, auf dem bestof.py '
                                     'läuft.</p>')
    ordner = (f'<p class="leise">Ordner: <code>{e(app.workflow_ordner)}</code></p>' if _lokal(app) else "")
    return f'<div class="wfliste">{ordner}<ul id="wfliste"></ul>{hochladen}</div>'


NEU_HTML = """<section class="egruppe" id="neugruppieren"><h2>Neu gruppieren</h2>
<p class="hilfe0">Gruppiert alle Fotos im Archiv mit den Werten oben neu – als kämen sie alle in einem Import. Jede Gruppe
behält den Ordner, in dem schon die meisten ihrer Fotos liegen; Fotos mit gleichem Namen (JPG und NEF) bleiben beisammen,
verbesserte Fassungen, Begleitdateien, Sterne, Alben, Jahr und Gesichter wandern mit. Erst kommt eine Vorschau, verschoben
wird erst nach Ihrer Bestätigung – und „Rückgängig“ stellt alles wieder her.</p>
<div class="knopfzeile"><button class="knopf" id="planen" type="button">Vorschau berechnen</button>
<button class="knopf" id="planstopp" type="button" hidden>Abbrechen</button></div>
<div id="planlauf" hidden><p id="planphase" class="leise"></p><progress id="planbalken" max="1" value="0"></progress></div>
<div id="plan" hidden><p id="plantext" class="ergebnis"></p><ul id="planliste" class="planliste"></ul>
<div class="knopfzeile"><button class="knopf haupt" id="ausfuehren" type="button">Jetzt neu gruppieren</button></div></div>
<p id="umzugtext" class="ergebnis"></p>
<div class="knopfzeile"><button class="knopf" id="umzugrueck" type="button" hidden>Letzten Umzug rückgängig</button></div>
</section>"""

JS_EINSTELLUNGEN = """
const $=id=>document.getElementById(id);
function feldWert(z){const i=z.querySelector('.wert');return i.type==='checkbox'?(i.checked?'1':'0'):i.value.trim();}
function feldSetzen(z,d){const i=z.querySelector('.wert');if(i.type==='checkbox')i.checked=d.wert==='1';else i.value=d.wert;
 i.dataset.wert=d.wert;z.querySelector('.equelle').textContent=d.quelle;z.querySelector('.ehinweis').textContent=d.hinweis||'';}
function geaendert(s){return [...s.querySelectorAll('.ezeile')].filter(z=>{const i=z.querySelector('.wert');
 return !i.disabled&&feldWert(z)!==i.dataset.wert;});}
function knopfStand(s){const k=s.querySelector('.speichern');if(k)k.disabled=!geaendert(s).length;}
async function speichern(werte,s){const [ok,j]=await post('/api/einstellungen',{werte});
 if(!ok){meldung(j.fehler||'Speichern fehlgeschlagen.',true);if(j.feld){const i=$('f_'+j.feld);if(i)i.focus();}return false;}
 for(const [n,d] of Object.entries(j.felder||{})){const z=document.querySelector('.ezeile[data-name="'+n+'"]');if(z)feldSetzen(z,d);}
 meldung(j.meldung);document.querySelectorAll('.egruppe').forEach(knopfStand);return true;}
document.querySelectorAll('.egruppe').forEach(s=>{
 s.addEventListener('input',()=>knopfStand(s));s.addEventListener('change',()=>knopfStand(s));
 const k=s.querySelector('.speichern');
 if(k)k.addEventListener('click',()=>{const w={};for(const z of geaendert(s))w[z.dataset.name]=feldWert(z);speichern(w,s);});
 s.querySelectorAll('.std').forEach(b=>b.addEventListener('click',()=>{const z=b.closest('.ezeile');
  speichern({[z.dataset.name]:null},s);}));
 s.addEventListener('keydown',ev=>{if(ev.key==='Enter'&&ev.target.matches('input.wert')){ev.preventDefault();
  const w={};for(const z of geaendert(s))w[z.dataset.name]=feldWert(z);if(Object.keys(w).length)speichern(w,s);}});});
// Workflows
function wfZeigen(liste){const ul=$('wfliste');if(!ul)return;
 ul.replaceChildren(...(liste.length?liste:[null]).map(w=>{const li=document.createElement('li');
  if(!w){li.className='leise';li.textContent='Noch keine Workflows.';return li;}
  li.textContent=(w.fehler?'✗ ':'✓ ')+w.name+' ('+w.datei+')'+(w.fehler?' – '+w.fehler:w.farbe?' – kann kolorieren':'');
  if(w.fehler)li.className='fehler';return li;}));}
wfZeigen(E.workflows);
const wfd=$('wfdatei');
if(wfd)wfd.addEventListener('change',async()=>{const f=wfd.files[0];wfd.value='';if(!f)return;
 if(f.size>E.max_workflow){meldung('Die Datei ist zu groß für einen Workflow.',true);return;}
 let daten;try{daten=JSON.parse(await f.text());}catch(_){meldung('Die Datei ist kein gültiges JSON.',true);return;}
 let [ok,j]=await post('/api/workflow',{name:f.name,daten});
 if(!ok&&j.ersetzen&&confirm(j.fehler+' Ersetzen?'))[ok,j]=await post('/api/workflow',{name:f.name,daten,ersetzen:true});
 if(!ok){if(!j.ersetzen)meldung(j.fehler||'Hochladen fehlgeschlagen.',true);return;}
 meldung(j.meldung);wfZeigen(j.workflows);setTimeout(()=>location.reload(),1500);});
// Neu gruppieren: Vorschau (fotosort rechnet), Ausführen, Rückgängig
let planId=null,planZeit=null,umzugLief=false;
function gruppenWerte(){const w={};for(const n of ['SCHWELLE','SERIE_SEK','SERIE_SCHWELLE','EINZELN']){
 const i=$('f_'+n);if(i)w[n]=i.value.trim();}return w;}
function zahl(n){return String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g,'.');}
function bilderText(n){return n===1?'1 Bild':zahl(n)+' Bilder';}
$('planen').addEventListener('click',async()=>{const [ok,j]=await post('/api/gruppieren',{aktion:'plan',werte:gruppenWerte()});
 if(!ok){meldung(j.fehler||'Vorschau ließ sich nicht starten.',true);return;}
 planId=j.id;$('plan').hidden=true;$('planlauf').hidden=false;$('planstopp').hidden=false;$('planen').disabled=true;planAbfragen();});
$('planstopp').addEventListener('click',()=>post('/api/gruppieren',{aktion:'abbrechen',id:planId}));
async function planAbfragen(){let j;try{const r=await fetch('/api/gruppieren?id='+encodeURIComponent(planId));j=await r.json();}
 catch(_){setTimeout(planAbfragen,2000);return;}
 const r=j.rechnungen[planId];if(!r){$('planlauf').hidden=true;$('planen').disabled=false;return;}
 $('planphase').textContent=(r.phase||'Start')+(r.gesamt?' – '+zahl(r.fertig)+' von '+zahl(r.gesamt):'');
 $('planbalken').max=r.gesamt||1;if(r.gesamt)$('planbalken').value=r.fertig;else $('planbalken').removeAttribute('value');
 if(r.laeuft){setTimeout(planAbfragen,700);return;}
 $('planlauf').hidden=true;$('planstopp').hidden=true;$('planen').disabled=false;
 if(r.fehler){meldung('Vorschau: '+r.fehler,true);return;}
 planZeigen(r.ergebnis,r.werte);}
function planZeigen(p,w){const par=p.parameter,gespeichert=['SCHWELLE','SERIE_SEK','SERIE_SCHWELLE','EINZELN'].every(n=>{
  const i=$('f_'+n);return !i||i.value.trim()===i.dataset.wert;});
 let t='Mit Bildvergleich '+par.SCHWELLE+', Serie '+String(par.SERIE_SEK).replace('.',',')+' s / '+par.SERIE_SCHWELLE+
  ', Einzelbilder '+(par.EINZELN==='0000'?'in Ordner 0000':'je eigener Ordner')+(gespeichert?'':' (noch nicht gespeichert)')+':\\n'+
  bilderText(p.bilder)+' in '+zahl(p.ordner_vorher)+' Ordnern → danach '+zahl(p.ordner_nachher)+' Ordner, '+
  zahl(p.gruppen)+' Gruppen mit mehreren Bildern, '+zahl(p.einzeln)+' Einzelbilder.';
 if(!p.bewegt)t+='\\nNichts zu tun – das Archiv ist schon so gruppiert.';
 else t+='\\n'+bilderText(p.bewegt)+(p.bewegt===1?' wandert: ':' wandern: ')+
  (p.n_zusammen===1?'1 Gruppe':zahl(p.n_zusammen)+' Gruppen')+' aus mehreren Ordnern, '+zahl(p.n_geteilt)+
  (p.n_geteilt===1?' Ordner wird':' Ordner werden')+' geteilt'+(p.neue_ordner.length?', '+(p.neue_ordner.length===1?'1 neuer Ordner':
  p.neue_ordner.length+' neue Ordner')+' ab '+p.neue_ordner[0]:'')+
  (p.aus_sammel?', '+(p.aus_sammel===1?'1 Bild aus Ordner 0000 bekommt':p.aus_sammel+' Bilder aus Ordner 0000 bekommen')+' eine Gruppe':'')+'.';
 if(p.fest)t+='\\n'+bilderText(p.fest)+(p.fest===1?' ist einfarbig oder unlesbar und bleibt, wo es ist.':
  ' sind einfarbig oder unlesbar und bleiben, wo sie sind.');
 if(!gespeichert)t+='\\nKünftige Importe nutzen die gespeicherten Werte – oben „Speichern“, damit sie zu diesem Stand passen.';
 $('plantext').textContent=t;
 const li=[...p.zusammen.slice(0,8).map(z=>'zusammen: '+z.aus.join(' + ')+' → '+z.ziel+' ('+bilderText(z.bilder)+')'),
  ...p.geteilt.slice(0,8).map(g=>'geteilt: '+g.ordner+' → '+g.nach.join(', '))];
 if(p.n_zusammen>8||p.n_geteilt>8)li.push('…');
 $('planliste').replaceChildren(...li.map(x=>{const e=document.createElement('li');e.textContent=x;return e;}));
 $('ausfuehren').hidden=!p.bewegt;$('plan').hidden=false;planZeit=Date.now();}
$('ausfuehren').addEventListener('click',async()=>{
 if(!confirm('Archiv jetzt neu gruppieren? Die Dateien werden verschoben; „Rückgängig“ stellt den alten Stand wieder her.'))return;
 const [ok,j]=await post('/api/gruppieren',{aktion:'ausfuehren',id:planId});
 if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}$('plan').hidden=true;umzugLief=true;umzugAbfragen();});
$('umzugrueck').addEventListener('click',async()=>{
 if(!confirm('Den letzten Umzug zurücknehmen? Die Dateien kommen in ihre alten Ordner zurück.'))return;
 const [ok,j]=await post('/api/gruppieren',{aktion:'rueckgaengig'});
 if(!ok){meldung(j.fehler||'Nicht möglich.',true);return;}umzugLief=true;umzugAbfragen();});
const ARTEN={zusammenfassen:'Zusammenfassen',gruppieren:'Neu gruppieren',umzug_rueck:'Umzug rückgängig'};
async function umzugAbfragen(){let j;try{const r=await fetch('/api/gruppieren');j=await r.json();}catch(_){setTimeout(umzugAbfragen,2000);return;}
 const a=j.auftrag,l=j.letzter,lauf=a&&a.laeuft;
 if(lauf&&ARTEN[a.art])$('umzugtext').textContent=ARTEN[a.art]+': '+a.phase+(a.gesamt?' – '+zahl(a.fertig)+' von '+zahl(a.gesamt):'');
 else if(lauf)$('umzugtext').textContent='Gerade läuft ein Import – Neu gruppieren geht danach.';
 else if(umzugLief&&a&&ARTEN[a.art]){$('umzugtext').textContent=a.fehler||a.ergebnis;$('umzugtext').classList.toggle('fehler',!!a.fehler);
  meldung(a.fehler||a.ergebnis,!!a.fehler);umzugLief=false;}
 else if(l)$('umzugtext').textContent='Letzter Umzug ('+l.zeit.slice(6,8)+'.'+l.zeit.slice(4,6)+'.'+l.zeit.slice(0,4)+' '+
  l.zeit.slice(9,11)+':'+l.zeit.slice(11,13)+'): '+(l.text||ARTEN[l.art]||'')+(l.rueckgaengig?' – zurückgenommen.':'');
 $('umzugrueck').hidden=lauf||!l||!!l.rueckgaengig;$('ausfuehren').disabled=!!lauf;$('planen').disabled=!!lauf||!$('planlauf').hidden;
 if(lauf)setTimeout(umzugAbfragen,700);}
umzugAbfragen();
"""
