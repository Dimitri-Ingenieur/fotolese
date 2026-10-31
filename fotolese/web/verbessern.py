"""fotolese.web.verbessern – Fotos mit ComfyUI verbessern und als eigene Fassung neben dem Original ablegen.

Ein Workflow ist eine in ComfyUI mit „Export (API)“ gespeicherte JSON-Datei im Ordner WORKFLOWS (Standard:
workflows/ neben bestof.py); jede Datei ist eine Wahl neben „Verbessern“. bestof lädt das Foto hoch, setzt es in
den Bild-Eingang (LoadImage oder ein anderer Knoten mit dem Text-Eingang „image“; gibt es mehrere, den mit
„fotolese“ im Titel), würfelt die Seeds neu und holt das Bild des Speicher-Knotens ab. Gespeichert wird verlustfrei
als PNG in SORTIERT/<Ordner>/verbessert/<Name>_<Workflow>.png – mit dem EXIF des Originals (Datum, Ort; die Drehung
steckt dann schon im Bild) und der Workflow-Beschreibung, die ComfyUI ins PNG schreibt. Von Hand gesetztes Jahr
und Alben übernimmt die neue Fassung vom Original.

Wahlweise folgt eine Kolorierung (kolorieren.py): zweiter Lauf desselben Workflows auf der restaurierten Fassung,
Ergebnis nach dem Luma-Lock als …_koloriert.png. Scheitert sie, bleibt die Restaurierung trotzdem gültig.
"""
import copy
import errno
import io
import json
import os
import random
import re
import secrets
import shutil
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import OrderedDict
from urllib.parse import urlencode

from PIL import Image, ImageOps, PngImagePlugin

from fotolese.web.konst import KOLORIERT, ORDNER_MUSTER, VERBESSERT
from fotolese.web.konfig import anzeige, name_aus_id, url_id
from fotolese.web.kolorieren import MAX_HINWEIS, MODI, FarbFehler, farb_ziele, lora_setzen

FRIST = 3600  # so lange wartet ein Auftrag höchstens auf das Ergebnis (Sekunden)
MAX_AUFTRAEGE = 200
_SPEICHERN = threading.Lock()


class Fehler(Exception):
    """Fehler mit einem Text für die Oberfläche."""


def workflow_namen(datei):
    """„Foto_restore_API.json“ -> („Foto restore“, „Foto_restore“): Anzeige und Teil des Dateinamens."""
    stamm = re.sub(r"(?:[\s_-]+api|\s*\(api\))$", "", os.path.splitext(datei)[0], flags=re.IGNORECASE)
    kurz = re.sub(r"[^\w-]+", "_", stamm).strip("_") or "Workflow"
    return stamm.replace("_", " ").strip() or kurz, kurz


class Workflows:
    """Die Workflow-Dateien eines Ordners; liest neu, sobald eine Datei dazukommt oder sich ändert."""

    def __init__(self, ordner):
        self.ordner = ordner
        self._stand, self._liste = None, []
        self._lock = threading.Lock()

    def liste(self):
        """[{"datei", "name", "kurz", "daten", "eingang", "fehler"}] nach Dateinamen; brauchbar sind die mit daten."""
        try:
            dateien = sorted((d.name, d.stat().st_mtime_ns) for d in os.scandir(self.ordner)
                             if d.name.lower().endswith(".json") and not d.name.startswith(".") and d.is_file())
        except OSError:
            dateien = []
        with self._lock:
            if dateien != self._stand:
                self._stand, self._liste = dateien, [self._laden(n) for n, _ in dateien]
            return self._liste

    def brauchbar(self):
        return [w for w in self.liste() if w["daten"]]

    def _laden(self, datei):
        name, kurz = workflow_namen(datei)
        w = {"datei": datei, "name": name, "kurz": kurz, "daten": None, "eingang": None, "fehler": None, "farbe": None}
        try:
            with open(os.path.join(self.ordner, datei), encoding="utf-8") as f:
                daten = json.load(f)
        except (OSError, ValueError) as fehler:
            w["fehler"] = f"nicht lesbar ({fehler})"
            return w
        if isinstance(daten, dict) and "nodes" in daten and "links" in daten:
            w["fehler"] = "kein API-Format – in ComfyUI mit „Export (API)“ speichern"
            return w
        knoten = ({k: v for k, v in daten.items() if isinstance(v, dict) and isinstance(v.get("inputs"), dict)
                   and v.get("class_type")} if isinstance(daten, dict) else {})
        eingaenge = [k for k, v in knoten.items() if isinstance(v["inputs"].get("image"), str)]
        markiert = [k for k in eingaenge if "fotolese" in str((knoten[k].get("_meta") or {}).get("title", "")).lower()]
        if not knoten:
            w["fehler"] = "keine Knoten – ist das ein ComfyUI-Workflow im API-Format?"
        elif len(markiert) == 1 or len(eingaenge) == 1:
            w["daten"], w["eingang"] = daten, (markiert or eingaenge)[0]
            w["farbe"] = farb_ziele(knoten)  # wo die Kolorierung eingreift, None = nicht möglich
        else:
            w["fehler"] = ("kein Bild-Eingang (z. B. LoadImage)" if not eingaenge
                           else "mehrere Bild-Eingänge – den richtigen Knoten im Titel mit „fotolese“ kennzeichnen")
        return w


def _comfy_fehler(code, text):
    """Fehlerantwort von ComfyUI in einen Satz fassen (z. B. fehlender Knoten, fehlendes Modell)."""
    try:
        j = json.loads(text)
    except ValueError:
        return f"ComfyUI antwortet mit Fehler {code}: {text[:200]}"
    teile = []
    fehler = j.get("error") if isinstance(j, dict) else None
    if isinstance(fehler, dict):
        teile.append(fehler.get("message") or fehler.get("type") or "")
        if fehler.get("details"):
            teile.append(str(fehler["details"]))
    for nid, ne in (j.get("node_errors") or {}).items() if isinstance(j, dict) else ():
        for f in ne.get("errors", [])[:2]:
            teile.append(f"{ne.get('class_type', nid)}: {f.get('message', '')} {f.get('details', '')}".strip())
    text = " – ".join(t for t in teile if t) or f"Fehler {code}"
    return f"ComfyUI lehnt den Workflow ab: {text[:400]}"


class Comfy:
    """Kleiner Client für die HTTP-Schnittstelle von ComfyUI (upload, prompt, history, queue, view)."""

    def __init__(self, basis):
        self.basis = basis.rstrip("/")

    def anfrage(self, pfad, daten=None, roh=None, kopf=None, frist=60):
        if daten is not None:
            roh, kopf = json.dumps(daten).encode(), {"Content-Type": "application/json"}
        req = urllib.request.Request(self.basis + pfad, data=roh, headers=kopf or {})
        try:
            with urllib.request.urlopen(req, timeout=frist) as r:
                return r.read()
        except urllib.error.HTTPError as f:
            raise Fehler(_comfy_fehler(f.code, f.read().decode("utf-8", "replace"))) from None
        except (urllib.error.URLError, OSError) as f:
            grund = getattr(f, "reason", None) or f
            raise Fehler(f"ComfyUI unter {self.basis} nicht erreichbar ({grund}) – läuft es? "
                         f"Die Adresse steht in bestof.conf (COMFYUI).") from None

    def json(self, pfad, daten=None, frist=60):
        roh = self.anfrage(pfad, daten=daten, frist=frist)
        try:
            return json.loads(roh or b"{}")
        except ValueError:
            raise Fehler(f"ComfyUI liefert auf {pfad} kein JSON – ist unter {self.basis} wirklich ComfyUI?") from None

    def hochladen(self, name, daten, typ):
        """Bild in den input-Ordner von ComfyUI; Rückgabe: Name, unter dem der Workflow es findet."""
        grenze = "----fotolese" + secrets.token_hex(12)
        feld = lambda n, w: f'--{grenze}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{w}\r\n'.encode()
        roh = b"".join([feld("overwrite", "true"), feld("type", "input"),
                        f'--{grenze}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
                        f'Content-Type: {typ}\r\n\r\n'.encode(), daten, f"\r\n--{grenze}--\r\n".encode()])
        j = json.loads(self.anfrage("/upload/image", roh=roh, frist=300,
                                    kopf={"Content-Type": f"multipart/form-data; boundary={grenze}"}) or b"{}")
        if not j.get("name"):
            raise Fehler("ComfyUI hat das Bild nicht angenommen.")
        return (j["subfolder"] + "/" if j.get("subfolder") else "") + j["name"]

    def erreichbar(self):
        try:
            self.anfrage("/system_stats", frist=2)
            return True
        except Fehler:
            return False


def _hochlade_bild(pfad):
    """Original unverändert hochladen; ist es per EXIF gedreht, aufrecht als JPEG (nicht jeder Knoten dreht selbst)."""
    endung = os.path.splitext(pfad)[1].lower()
    with Image.open(pfad) as im:
        if im.getexif().get(0x0112, 1) in (1, 0, None):
            with open(pfad, "rb") as f:
                return f.read(), ("image/png" if endung == ".png" else "image/jpeg"), (".png" if endung == ".png" else ".jpg")
        puffer = io.BytesIO()
        ImageOps.exif_transpose(im).convert("RGB").save(puffer, "JPEG", quality=95, subsampling=0)
        return puffer.getvalue(), "image/jpeg", ".jpg"


def _exif_ohne_drehung(pfad):
    """EXIF des Originals samt Datum (Exif-IFD) und GPS, Ausrichtung auf 1 – das Ergebnis ist schon aufrecht."""
    try:
        with Image.open(pfad) as im:
            ex = im.getexif()
            if not ex:
                return None
            for ifd in (0x8769, 0x8825):  # erst laden, sonst fehlen sie in tobytes()
                ex.get_ifd(ifd)
            ex[0x0112] = 1
            return ex.tobytes()
    except Exception:
        return None


def _variante(wf, praefix):
    """Jeder Lauf eine neue Variante: Seeds neu würfeln (Verbindungen sind Listen und bleiben) und eigener Dateiname
    bei ComfyUI, damit nichts überschrieben wird. Rückgabe: {Knoten: Seed}."""
    seeds = {}
    for nid, knoten in wf.items():
        eingaben = knoten.get("inputs") if isinstance(knoten, dict) else None
        if not isinstance(eingaben, dict):
            continue
        for k in ("seed", "noise_seed"):
            if isinstance(eingaben.get(k), int) and not isinstance(eingaben.get(k), bool):
                eingaben[k] = seeds[nid] = random.randrange(1 << 48)
        if isinstance(eingaben.get("filename_prefix"), str):
            eingaben["filename_prefix"] = praefix
    return seeds


def _ausfuehrungsfehler(status):
    for art, d in status.get("messages") or []:
        if art == "execution_interrupted":
            return "In ComfyUI abgebrochen."
        if art == "execution_error" and isinstance(d, dict):
            return (f"ComfyUI-Fehler in {d.get('node_type') or 'einem Knoten'}: "
                    f"{str(d.get('exception_message') or '').strip()[:300]}")
    return "ComfyUI meldet einen Fehler – Einzelheiten im ComfyUI-Fenster."


def speichern(app, ordner, name, roh, workflow, stamm=None, notiz=None, text_von=None):
    """Ergebnis als ordner/verbessert/<Name>_<Workflow>[_n].png (oder <stamm>[_n].png); nie überschreiben.
    EXIF und Alben kommen vom Original name; text_von: PNG, dessen ComfyUI-Texte mitkommen. Rückgabe: neuer Name."""
    quelle = os.path.join(app.archiv.pfad, ordner, name)
    ziel = os.path.join(app.archiv.pfad, ordner, VERBESSERT)
    os.makedirs(ziel, exist_ok=True)
    stamm = stamm or f"{os.path.splitext(os.path.basename(name))[0]}_{workflow['kurz']}"
    exif = _exif_ohne_drehung(quelle)
    with Image.open(io.BytesIO(roh)) as im:
        im.load()
        texte = im.info
        if text_von:
            with Image.open(io.BytesIO(text_von)) as t:
                texte = t.info
        info = PngImagePlugin.PngInfo()
        for k, v in texte.items():  # ComfyUI: „prompt“ und „workflow“ – das PNG lässt sich in ComfyUI wieder öffnen
            if isinstance(v, str):
                info.add_text(k, v)
        info.add_text("fotolese", json.dumps({"original": anzeige(name), "workflow": workflow["datei"], **(notiz or {})},
                                             ensure_ascii=False))
        with _SPEICHERN:
            for k in range(1, 10000):
                datei = f"{stamm}{'' if k == 1 else f'_{k}'}.png"
                if not os.path.lexists(os.path.join(ziel, datei)):
                    break
            else:
                raise Fehler("Kein freier Dateiname im Ordner verbessert.")
            tmp = os.path.join(ziel, f".{datei}.tmp")
            im.save(tmp, "PNG", pnginfo=info, **({"exif": exif} if exif else {}))
            if os.path.lexists(os.path.join(ziel, datei)):
                os.unlink(tmp)
                raise OSError(errno.EEXIST, "Datei existiert schon", datei)
            os.rename(tmp, os.path.join(ziel, datei))
    neu = f"{VERBESSERT}/{datei}"
    if app.index:  # Jahr von Hand und Alben gehören zum Foto, nicht zur Datei
        neu_p, alt_p = f"{ordner}/{url_id(neu)}", f"{ordner}/{url_id(name)}"
        with app.index.lock:
            db = app.index.db
            db.execute("INSERT OR IGNORE INTO jahr_manuell SELECT ?, jahr FROM jahr_manuell WHERE pfad=?", (neu_p, alt_p))
            db.execute("INSERT OR IGNORE INTO album_bild(album, pfad) SELECT album, ? FROM album_bild WHERE pfad=?",
                       (neu_p, alt_p))
            db.commit()
    return neu


class Auftrag(threading.Thread):
    """Ein Foto mit einem Workflow verbessern: hochladen, in die Warteschlange, warten, abholen, speichern."""

    def __init__(self, verbesserer, ordner, name, workflow, farbe="off", hinweise=""):
        super().__init__(daemon=True)
        self.v, self.ordner, self.name, self.workflow = verbesserer, ordner, name, workflow
        self.farbe, self.hinweise = farbe, hinweise  # Kolorierung: off/on/auto, Farbhinweise
        self.id = secrets.token_urlsafe(9)
        self.restauriert = None  # Archivname der Fassung aus Pass 1
        self.notizen = []  # fürs Terminal: Streuung, Seed, Fehler der Kolorierung
        self.status = {"id": self.id, "pfad": f"{ordner}/{url_id(name)}", "workflow": workflow["name"],
                       "phase": "Hochladen", "platz": None, "laeuft": True, "fehler": "", "ergebnis": None,
                       "farbmodus": farbe, "farbe": None, "farbfehler": "", "farbinfo": ""}

    def run(self):
        st = self.status
        try:
            st["ergebnis"] = self._ausfuehren()
            if self.farbe != "off":
                if self.v.app.indexer:
                    self.v.app.indexer.weiter.set()  # die Restaurierung schon einlesen, während Pass 2 läuft
                self._kolorieren_sicher()
            st["phase"] = "fertig"
        except Fehler as fehler:
            st["fehler"] = str(fehler)
        except Exception as fehler:
            traceback.print_exc()
            st["fehler"] = f"{type(fehler).__name__}: {fehler}"
        finally:
            st["laeuft"] = False
            if st["ergebnis"] and self.v.app.indexer:
                self.v.app.indexer.weiter.set()  # die neue Fassung gleich einlesen
            print(f"Verbessern ({self.workflow['name']}): {self.ordner}/{anzeige(self.name)} – "
                  f"{st['fehler'] or 'gespeichert als ' + st['ergebnis']['name']}"
                  + "".join(f" · {n}" for n in self.notizen), flush=True)

    def _ausfuehren(self):
        """Pass 1: das Original mit dem Workflow, wie er ist (nur Bild, Seed und Dateiname gesetzt)."""
        app, comfy, w = self.v.app, self.v.comfy, self.workflow
        quelle = os.path.join(app.archiv.pfad, self.ordner, self.name)
        daten, typ, endung = _hochlade_bild(quelle)
        bild = comfy.hochladen(f"fotolese_{secrets.token_hex(8)}{endung}", daten, typ)
        wf = copy.deepcopy(w["daten"])
        wf[w["eingang"]]["inputs"]["image"] = bild
        _variante(wf, f"fotolese/{secrets.token_hex(6)}")
        return self._abholen(self._warten(wf), wf)

    def _warten(self, wf, stufe=""):
        """Workflow in die Warteschlange und warten, bis der Verlauf ihn kennt; Phase und Platz in den Status."""
        comfy, st = self.v.comfy, self.status
        antwort = comfy.json("/prompt", {"prompt": wf, "client_id": "fotolese"}, frist=120)
        pid = antwort.get("prompt_id")
        if not pid:
            raise Fehler(_comfy_fehler(200, json.dumps(antwort)))
        vorne = f"{stufe}: " if stufe else ""
        st.update(phase=vorne + "Warteschlange", platz=None)
        ende = time.time() + FRIST
        while time.time() < ende:
            eintrag = comfy.json(f"/history/{pid}", frist=30).get(pid)
            if eintrag and (eintrag.get("outputs") or (eintrag.get("status") or {}).get("completed")
                            or (eintrag.get("status") or {}).get("status_str") == "error"):
                return eintrag
            schlange = comfy.json("/queue", frist=30)
            laufend = [e[1] for e in schlange.get("queue_running") or [] if len(e) > 1]
            wartend = [e[1] for e in sorted(schlange.get("queue_pending") or [], key=lambda e: e[0]) if len(e) > 1]
            if pid in laufend:
                st.update(phase=f"{stufe} läuft" if stufe else "läuft", platz=None)
            elif pid in wartend:
                st.update(phase=vorne + "Warteschlange", platz=len(laufend) + wartend.index(pid) + 1)
            time.sleep(1)
        raise Fehler("Zeitüberschreitung: ComfyUI hat nach einer Stunde kein Ergebnis geliefert.")

    def _bild_holen(self, eintrag, wf, knoten=None):
        """Ergebnisbild aus dem Verlauf laden: bevorzugt „output“ eines Speicher-Knotens, mit knoten nur von dem."""
        status = eintrag.get("status") or {}
        if status.get("status_str") == "error":
            raise Fehler(_ausfuehrungsfehler(status))
        bilder = []
        for nid, aus in (eintrag.get("outputs") or {}).items():
            if knoten is not None and nid != knoten:
                continue
            klasse = str((wf.get(nid) or {}).get("class_type", "")).lower()
            for b in (aus or {}).get("images") or []:
                if isinstance(b, dict) and b.get("filename"):
                    bilder.append(((0 if b.get("type") == "output" else 1, 0 if "save" in klasse else 1), b))
        if not bilder:
            raise Fehler("Der Workflow hat kein Bild geliefert – hat er einen Speicher-Knoten (Save Image)?")
        b = min(bilder, key=lambda x: x[0])[1]
        return self.v.comfy.anfrage("/view?" + urlencode({"filename": b["filename"], "subfolder": b.get("subfolder", ""),
                                                           "type": b.get("type", "output")}), frist=300)

    def _ergebnis(self, neu):
        self.v.app.archiv.bilder(self.ordner, frisch=True)
        _, _, mt = self.v.app.archiv.datei(self.ordner, neu) or (None, 0, 0)
        uid = url_id(neu)
        return {"name": anzeige(neu), "id": uid, "g": f"/g/{self.ordner}/{uid}?v={mt}", "o": f"/orig/{self.ordner}/{uid}"}

    def _abholen(self, eintrag, wf):
        roh = self._bild_holen(eintrag, wf)
        self.status["phase"] = "Speichern"
        self.restauriert = speichern(self.v.app, self.ordner, self.name, roh, self.workflow)
        return self._ergebnis(self.restauriert)

    def _kolorieren_sicher(self):
        """Pass 2 darf scheitern: dann bleibt es bei der Restaurierung, der Fehler steht im Auftrag und im Terminal."""
        st = self.status
        try:
            self._kolorieren()
        except (Fehler, FarbFehler, OSError, ValueError) as fehler:
            st["farbfehler"] = str(fehler)
        except Exception as fehler:
            traceback.print_exc()
            st["farbfehler"] = f"{type(fehler).__name__}: {fehler}"
        if st["farbfehler"]:
            self.notizen.append(f"Kolorierung fehlgeschlagen: {st['farbfehler']}")

    def _kolorieren(self):
        """Pass 2: die restaurierte Fassung kolorieren, Luma-Lock, als …_koloriert.png speichern."""
        app, st, k, w = self.v.app, self.status, self.v.farbe, self.workflow
        ziele = w["farbe"]
        with tempfile.TemporaryDirectory(prefix="fotolese_") as tmp:
            restored = os.path.join(tmp, "restored.png")  # feste Namen: kein „%“ o. Ä. in den ffmpeg-Argumenten
            shutil.copyfile(os.path.join(app.archiv.pfad, self.ordner, self.restauriert), restored)
            if self.farbe == "auto":
                st["phase"] = "Kolorierung: prüft Farbe"
                streuung = k.streuung(restored)
                self.notizen.append(f"Farbstreuung {streuung:.1f} (Schwelle {k.schwelle:g})")
                if streuung >= k.schwelle:
                    st["farbinfo"] = f"Schon farbig (Streuung {streuung:.1f}) – keine Kolorierung."
                    return
            st["phase"] = "Kolorierung: Hochladen"
            with open(restored, "rb") as f:
                bild = self.v.comfy.hochladen(f"{self.id}_restored.png", f.read(), "image/png")
            wf = copy.deepcopy(w["daten"])
            wf[w["eingang"]]["inputs"]["image"] = bild
            nid, schluessel = ziele["prompt"]
            wf[nid]["inputs"][schluessel] = k.prompt_text(self.hinweise)
            seeds = _variante(wf, f"fotolese/{self.id}_colorize")
            if ziele["lora"]:
                lora_setzen(wf[ziele["lora"]], k.restore_lora)
            self.notizen.append("Seed " + ", ".join(str(s) for s in seeds.values()))
            roh = self._bild_holen(self._warten(wf, "Kolorierung"), wf, knoten=ziele["speichern"])
            farbig = roh
            if k.luma:
                st["phase"] = "Kolorierung: Farbe übertragen"
                roh_pfad, fertig = os.path.join(tmp, "colorized_raw.png"), os.path.join(tmp, "colorized.png")
                with open(roh_pfad, "wb") as f:
                    f.write(roh)
                k.luma_lock(restored, roh_pfad, fertig)
                with open(fertig, "rb") as f:
                    farbig = f.read()
        stamm = f"{os.path.splitext(os.path.basename(self.restauriert))[0]}_{KOLORIERT}"
        notiz = {"pass": "colorize", "seed": list(seeds.values()), "restauriert": anzeige(self.restauriert)}
        neu = speichern(app, self.ordner, self.name, farbig, w, stamm=stamm, notiz=notiz, text_von=roh)
        st["farbe"] = self._ergebnis(neu)
        if k.roh_behalten:
            speichern(app, self.ordner, self.name, roh, w, stamm=f"{stamm}_roh", notiz=notiz)
        self.notizen.append(f"koloriert als {anzeige(neu)}")


class Verbesserer:
    def __init__(self, app, comfy_url, workflow_ordner, farbe=None):
        self.app = app
        self.comfy = Comfy(comfy_url)
        self.workflows = Workflows(workflow_ordner)
        self.farbe = farbe if farbe and farbe.bereit else None  # Kolorierung; None ohne ffmpeg
        self.auftraege = OrderedDict()
        self._lock = threading.Lock()

    def fuer_seite(self):
        """Für die Oberfläche: [{"datei", "name", "farbe"}] der brauchbaren Workflows (farbe: kann kolorieren)."""
        return [{"datei": w["datei"], "name": w["name"], "farbe": bool(self.farbe and w["farbe"])}
                for w in self.workflows.brauchbar()]

    def starten(self, pfad, datei, kolorieren=None, hinweise=None):
        o, _, uid = str(pfad or "").partition("/")
        name = name_aus_id(uid)
        if not (ORDNER_MUSTER.fullmatch(o) and o in self.app.archiv.ordner() and uid and url_id(name) == uid
                and self.app.archiv.datei(o, name)):
            return 404, {"fehler": "Bild nicht gefunden. Seite neu laden."}
        w = next((w for w in self.workflows.brauchbar() if w["datei"] == datei), None)
        if not w:
            return 404, {"fehler": "Workflow nicht gefunden – liegt die Datei noch im Ordner workflows? Seite neu laden."}
        modus = kolorieren if kolorieren in MODI else (self.farbe.standard if self.farbe else "off")
        hinweise = str(hinweise or "").strip()
        if modus != "off" and not (self.farbe and w["farbe"]):
            return 400, {"fehler": "Kolorierung geht hier nicht – " + ("ffmpeg fehlt." if not self.farbe else
                                                                       f"„{w['name']}“ hat keinen Prompt-Text.")}
        if len(hinweise) > MAX_HINWEIS:
            return 400, {"fehler": f"Farbhinweise höchstens {MAX_HINWEIS} Zeichen."}
        auftrag = Auftrag(self, o, name, w, modus, hinweise)
        with self._lock:
            self.auftraege[auftrag.id] = auftrag
            while len(self.auftraege) > MAX_AUFTRAEGE:
                self.auftraege.popitem(last=False)
        auftrag.start()
        return 200, {"auftrag": auftrag.id, "meldung": f"Verbessern mit „{w['name']}“ gestartet – das dauert etwas."}

    def stand(self, ids):
        with self._lock:
            return {i: dict(self.auftraege[i].status) for i in ids if i in self.auftraege}
