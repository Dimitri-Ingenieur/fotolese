"""fotolese.web.kolorieren – Fotos mit ComfyUI kolorieren, danach Luma-Lock mit ffmpeg.

Kolorieren ist ein eigener Schritt in der Lupe, unabhängig vom Verbessern: Es färbt das gezeigte Foto ein – das
Original direkt oder eine verbesserte Fassung. Genommen wird der Workflow FARBE_WORKFLOW, sonst der in der Lupe
gewählte, wenn er einen Prompt-Text hat (je Auftrag eine Kopie): Eingang ist das Foto, der Prompt die
Kolorier-Anweisung (dazu Farbhinweise), der Seed neu, die Restore-LoRA aus oder schwach, der Dateiname eigen. Das
Ergebnis kommt nur vom Speicher-Knoten. Der Luma-Lock nimmt die Helligkeit (Y) aus dem Eingangsfoto und nur die Farbe
(Cb/Cr) aus ComfyUI: Details, Gesichter und Tonwerte bleiben 1:1, ein Versatz durch das Neuzeichnen stört nicht. Der
Prompt ist der erste Text-Encoder vor dem Speicher-Knoten (Qwen, CLIP Text Encode für SD/SDXL/Flux …), nie der
negative; ein Knoten mit „fotolese“ im Titel legt ihn fest. Bildverarbeitung nur mit ffmpeg/ffprobe; fehlen sie,
ist das Kolorieren aus.
"""
import json
import shutil
import subprocess

STANDARD_PROMPT = ("Colorize this black-and-white photo with natural, realistic colors: lifelike skin tones, plausible "
                   "period-appropriate colors for clothing, objects and background, neutral white balance without sepia "
                   "or yellow cast. Keep the same composition, framing, people, facial features, lighting and all details "
                   "exactly; change only the colors.")
MAX_HINWEIS = 300
OHNE_PROMPT = ("kein Prompt-Text gefunden (Text-Encoder vor dem Speicher-Knoten) oder nicht genau ein Speicher-Knoten. "
               "Den Prompt-Knoten in ComfyUI im Titel mit „fotolese“ kennzeichnen.")


class FarbFehler(Exception):
    """Fehler beim Kolorieren (ffmpeg) mit einem Text für die Oberfläche."""


TEXT_FELDER = ("prompt", "text", "t5xxl", "clip_l", "text_g", "text_l")  # Prompt-Eingänge von Text-Encodern
QUELL_FELDER = ("text", "value", "string", "prompt")  # Text in einem verbundenen Knoten (Text-, String-Knoten)


def mit_hinweisen(text, hinweise=""):
    """Farbhinweise ans Ende eines Prompt-Texts: „… Color hints: the dress is dark blue“; ohne Hinweise unverändert.
    So beim Kolorieren (an die Kolorier-Anweisung) und beim Verbessern (an den Prompt des Workflows)."""
    hinweise = str(hinweise or "").strip()
    return f"{text.rstrip()} Color hints: {hinweise}".lstrip() if hinweise else text


def _titel(k):
    return str((k.get("_meta") or {}).get("title", "")).lower()


def _verbindung(wert, knoten):
    """Eingang als Verbindung [Knoten, Ausgang] -> ID des Knotens, sonst None."""
    if isinstance(wert, list) and len(wert) == 2 and str(wert[0]) in knoten:
        return str(wert[0])
    return None


def _felder(knoten, nid, encoder=True):
    """Prompt-Felder eines Text-Encoders als [(Knoten, Eingang)]: Text direkt im Eingang oder im verbundenen Knoten.
    Mit encoder=True leer, wenn der Knoten kein Text-Encoder ist (kein „clip“, nicht „…Encode…“/„…Prompt…“)."""
    k = knoten[nid]
    eingaenge, klasse = k["inputs"], str(k["class_type"]).lower()
    if encoder and not ("clip" in eingaenge or "encode" in klasse or "prompt" in klasse):
        return []
    ziele = []
    for feld in TEXT_FELDER:
        wert = eingaenge.get(feld)
        quelle = _verbindung(wert, knoten)
        if isinstance(wert, str):
            ziele.append((nid, feld))
        elif quelle:
            q = knoten[quelle]["inputs"]
            schluessel = next((s for s in QUELL_FELDER if isinstance(q.get(s), str)), None)
            if schluessel:
                ziele.append((quelle, schluessel))
    return list(dict.fromkeys(ziele))


def _markiert(knoten):
    """Knoten mit „fotolese“ im Titel, der Text hat – so legt man den Prompt fest, wenn die Suche danebenliegt."""
    for nid, k in knoten.items():
        if "fotolese" in _titel(k):
            felder = [(nid, f) for f in dict.fromkeys(TEXT_FELDER + QUELL_FELDER) if isinstance(k["inputs"].get(f), str)]
            felder = felder or _felder(knoten, nid, encoder=False)
            if felder:
                return felder
    return []


def _prompt_suchen(knoten, start):
    """Vom Speicher-Knoten rückwärts zum nächsten Text-Encoder, über alle Verbindungen außer negativen (negative,
    negative_prompt, Titel „negative“): das ist der positive Prompt – bei Qwen (Eingang „prompt“), CLIP Text Encode
    (SD, SDXL, Flux) und ähnlichen. Notizen und unverbundene Knoten erreicht die Suche gar nicht."""
    gesehen, schlange = set(), [start]
    while schlange:
        nid = schlange.pop(0)
        if nid in gesehen or "negativ" in _titel(knoten[nid]):
            continue
        gesehen.add(nid)
        ziele = _felder(knoten, nid)
        if ziele:
            return ziele
        for name, wert in knoten[nid]["inputs"].items():
            quelle = _verbindung(wert, knoten)
            if quelle and "negativ" not in name.lower():
                schlange.append(quelle)
    return []


def _restore_lora(k):
    """LoRA mit „restore“ im Namen: AusBoss-Loader (JSON in „loras“), LoraLoader („lora_name“), Power Lora Loader."""
    e = k["inputs"]
    if isinstance(e.get("loras"), str) and "restore" in e["loras"].lower():
        return True
    if isinstance(e.get("lora_name"), str) and "restore" in e["lora_name"].lower():
        return True
    return any(isinstance(v, dict) and "restore" in str(v.get("lora", "")).lower() for v in e.values())


def farb_ziele(knoten):
    """Wo das Kolorieren eingreift: die Prompt-Felder [(Knoten, Eingang)], der Speicher-Knoten und die Knoten mit
    einer Restore-LoRA. Den Prompt findet sie über einen Knoten mit „fotolese“ im Titel, sonst als ersten
    Text-Encoder vor dem Speicher-Knoten (nicht den negativen), zur Not über einen Eingang „prompt“.
    None, wenn kein Prompt zu finden ist oder es nicht genau einen Speicher-Knoten gibt."""
    speicher = [nid for nid, k in knoten.items() if "save" in str(k["class_type"]).lower()]
    if len(speicher) != 1:
        return None
    prompt = _markiert(knoten) or _prompt_suchen(knoten, speicher[0])
    if not prompt:  # Rückfall wie früher: irgendein Eingang „prompt“
        for nid, k in knoten.items():
            p = k["inputs"].get("prompt")
            quelle = _verbindung(p, knoten)
            if quelle and isinstance(knoten[quelle]["inputs"].get("text"), str):
                prompt = [(quelle, "text")]
                break
            if isinstance(p, str):
                prompt = [(nid, "prompt")]
                break
    if not prompt:
        return None
    return {"prompt": prompt, "speichern": speicher[0],
            "lora": [nid for nid, k in knoten.items() if _restore_lora(k)]}


def lora_setzen(knoten, staerke):
    """Restore-LoRA eines Knotens bei Stärke 0 abschalten, sonst mit dieser Stärke einschalten – im AusBoss-Loader
    („loras“ ist JSON; Eintrag mit „restore“ im Namen, nicht über die Stelle), im LoraLoader (Stärken) und im Power
    Lora Loader (Einträge mit „lora“ und „on“). Turbo-LoRA und Steps bleiben."""
    e = knoten["inputs"]
    if isinstance(e.get("loras"), str) and "restore" in e["loras"].lower():
        loras = json.loads(e["loras"])
        for eintrag in loras:
            if isinstance(eintrag, dict) and "restore" in str(eintrag.get("name", "")).lower():
                if staerke <= 0:
                    eintrag["enabled"] = False
                else:
                    eintrag["enabled"], eintrag["strength"] = True, staerke
        e["loras"] = json.dumps(loras, separators=(",", ":"))
    if isinstance(e.get("lora_name"), str) and "restore" in e["lora_name"].lower():
        for s in ("strength_model", "strength_clip"):
            if isinstance(e.get(s), (int, float)) and not isinstance(e.get(s), bool):
                e[s] = max(0.0, staerke)
    for v in e.values():
        if isinstance(v, dict) and "restore" in str(v.get("lora", "")).lower():
            v["on"] = staerke > 0
            if staerke > 0:
                v["strength"] = staerke


class Kolorierung:
    """Einstellungen (COLORIZE_…) und die ffmpeg-Schritte: Größe, Luma-Lock."""

    def __init__(self, restore_lora=0.0, luma_lock=True, chroma_blur=0.0, prompt="", roh_behalten=False):
        self.restore_lora, self.luma, self.chroma_blur = max(0.0, restore_lora), luma_lock, max(0.0, chroma_blur)
        self.prompt, self.roh_behalten = prompt.strip() or STANDARD_PROMPT, roh_behalten
        self.ffmpeg, self.ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        self.version, self.neue_syntax, self.grund = "", True, ""
        if not (self.ffmpeg and self.ffprobe):
            self.grund = "ffmpeg/ffprobe fehlt"
        else:
            try:
                kopf = self._lauf([self.ffmpeg, "-hide_banner", "-version"], 20).split()
                self.version = kopf[2] if len(kopf) > 2 else "?"
                self._lauf([self.ffprobe, "-hide_banner", "-version"], 20)
                hilfe = subprocess.run([self.ffmpeg, "-hide_banner", "-h", "filter=mergeplanes"], capture_output=True,
                                       text=True, timeout=20)
                self.neue_syntax = "map1s" in hilfe.stdout + hilfe.stderr  # sonst alte Schreibweise 0x001020
            except (OSError, subprocess.SubprocessError, FarbFehler) as fehler:
                self.grund = f"ffmpeg nicht nutzbar ({fehler})"
        self.bereit = not self.grund

    @staticmethod
    def _lauf(argumente, frist=300):
        try:
            r = subprocess.run(argumente, capture_output=True, text=True, timeout=frist)
        except subprocess.TimeoutExpired:
            raise FarbFehler(f"{argumente[0]} antwortet nicht.") from None
        if r.returncode:
            letzte = ((r.stderr or r.stdout).strip().splitlines() or ["Fehler"])[-1]
            raise FarbFehler(f"ffmpeg: {letzte[:300]}")
        return r.stdout

    def prompt_text(self, hinweise=""):
        return mit_hinweisen(self.prompt, hinweise)

    def groesse(self, pfad):
        aus = self._lauf([self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0:s=x", pfad]).strip()
        try:
            breite, hoehe = aus.split("x")[:2]
            return int(breite), int(hoehe)
        except ValueError:
            raise FarbFehler(f"ffprobe kennt die Größe nicht ({aus[:60]}).") from None

    def luma_lock(self, restauriert, roh, ziel):
        """Y aus dem Eingangsfoto (restauriert), Cb/Cr aus dem Bild von ComfyUI (roh, auf die Größe des Eingangs
        skaliert); 16 Bit gegen Rundungsfehler."""
        breite, hoehe = self.groesse(restauriert)
        farbe = f"[1:v]scale={breite}:{hoehe}:flags=lanczos,format=yuv444p16le,extractplanes=u+v"
        if self.chroma_blur > 0:  # gegen Farbsäume durch Restversatz
            s = f"{self.chroma_blur:g}"
            farbe += f"[u0][v0];[u0]gblur=sigma={s}[u];[v0]gblur=sigma={s}[v];"
        else:
            farbe += "[u][v];"
        mischen = ("mergeplanes=map1s=1:map2s=2:format=yuv444p16le" if self.neue_syntax
                   else "mergeplanes=0x001020:yuv444p16le")
        self._lauf([self.ffmpeg, "-v", "error", "-y", "-i", restauriert, "-i", roh, "-filter_complex",
                    farbe + f"[0:v]format=yuv444p16le,extractplanes=y[y];[y][u][v]{mischen},format=rgb24",
                    "-frames:v", "1", "-update", "1", ziel])
