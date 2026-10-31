"""fotolese.web.kolorieren – Kolorierung als zweiter ComfyUI-Lauf nach der Restaurierung, danach Luma-Lock mit ffmpeg.

Pass 2 nimmt denselben Workflow wie die Restaurierung (je Auftrag eine Kopie): Eingang ist die restaurierte Fassung,
der Prompt die Kolorier-Anweisung (dazu Farbhinweise), der Seed neu, die Restore-LoRA aus oder schwach, der Dateiname
eigen. Das Ergebnis kommt nur vom Speicher-Knoten. Der Luma-Lock nimmt die Helligkeit (Y) aus der Restaurierung und
nur die Farbe (Cb/Cr) aus Pass 2: Details, Gesichter und Tonwerte bleiben 1:1, ein Versatz durch das Neuzeichnen
stört nicht. Bildverarbeitung nur mit ffmpeg/ffprobe; fehlen sie, ist die Kolorierung aus.
"""
import json
import re
import shutil
import subprocess

STANDARD_PROMPT = ("Colorize this black-and-white photo with natural, realistic colors: lifelike skin tones, plausible "
                   "period-appropriate colors for clothing, objects and background, neutral white balance without sepia "
                   "or yellow cast. Keep the same composition, framing, people, facial features, lighting and all details "
                   "exactly; change only the colors.")
MODI = ("off", "on", "auto")
MAX_HINWEIS = 300


class FarbFehler(Exception):
    """Fehler in Pass 2 oder ffmpeg – die Restaurierung bleibt gültig."""


def farb_ziele(knoten):
    """Wo Pass 2 eingreift: Prompt-Text (Knoten, Eingang), der Speicher-Knoten und ein LoRA-Loader mit Restore-LoRA.
    Den Prompt-Text findet sie über einen Eingang „prompt“ (Text direkt oder Verbindung zu einem Knoten mit „text“).
    None, wenn das fehlt oder es nicht genau einen Speicher-Knoten gibt."""
    prompt = None
    for nid, k in knoten.items():
        p = k["inputs"].get("prompt")
        if isinstance(p, list) and p and isinstance((knoten.get(str(p[0])) or {}).get("inputs", {}).get("text"), str):
            prompt = (str(p[0]), "text")
            break
        if isinstance(p, str):
            prompt = (nid, "prompt")
            break
    speicher = [nid for nid, k in knoten.items() if "save" in str(k["class_type"]).lower()]
    lora = next((nid for nid, k in knoten.items()
                 if isinstance(k["inputs"].get("loras"), str) and "restore" in k["inputs"]["loras"].lower()), None)
    if not prompt or len(speicher) != 1:
        return None
    return {"prompt": prompt, "speichern": speicher[0], "lora": lora}


def lora_setzen(knoten, staerke):
    """Restore-LoRA im LoRA-Loader: „loras“ ist ein JSON-Text. Eintrag mit „restore“ im Namen (nicht über die
    Stelle) bei Stärke 0 abschalten, sonst einschalten mit dieser Stärke. Turbo-LoRA und Steps bleiben."""
    loras = json.loads(knoten["inputs"]["loras"])
    for eintrag in loras:
        if isinstance(eintrag, dict) and "restore" in str(eintrag.get("name", "")).lower():
            if staerke <= 0:
                eintrag["enabled"] = False
            else:
                eintrag["enabled"], eintrag["strength"] = True, staerke
    knoten["inputs"]["loras"] = json.dumps(loras, separators=(",", ":"))


class Kolorierung:
    """Einstellungen (COLORIZE_…) und die ffmpeg-Schritte: Größe, Monochrom-Prüfung, Luma-Lock."""

    def __init__(self, standard="off", restore_lora=0.0, luma_lock=True, chroma_blur=0.0, schwelle=10.0, prompt="",
                 roh_behalten=False):
        self.standard = standard if standard in MODI else "off"
        self.restore_lora, self.luma, self.chroma_blur = max(0.0, restore_lora), luma_lock, max(0.0, chroma_blur)
        self.schwelle, self.prompt, self.roh_behalten = schwelle, prompt.strip() or STANDARD_PROMPT, roh_behalten
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
        return self.prompt + (f" Color hints: {hinweise.strip()}" if hinweise and hinweise.strip() else "")

    def groesse(self, pfad):
        aus = self._lauf([self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0:s=x", pfad]).strip()
        try:
            breite, hoehe = aus.split("x")[:2]
            return int(breite), int(hoehe)
        except ValueError:
            raise FarbFehler(f"ffprobe kennt die Größe nicht ({aus[:60]}).") from None

    def streuung(self, pfad):
        """Farbstreuung: max(UHIGH−ULOW, VHIGH−VLOW) aus signalstats (10./90. Perzentil). Klein = Schwarzweiß oder
        Sepia – ein Farbstich verschiebt nur den Mittelwert, nicht die Streuung."""
        aus = self._lauf([self.ffmpeg, "-v", "error", "-i", pfad, "-vf",
                          "format=yuv444p,signalstats,metadata=print:file=-", "-f", "null", "-"])
        werte = {k: float(v) for k, v in re.findall(r"lavfi\.signalstats\.(ULOW|UHIGH|VLOW|VHIGH)=([\d.]+)", aus)}
        if len(werte) < 4:
            raise FarbFehler("ffmpeg signalstats lieferte keine Werte.")
        return max(werte["UHIGH"] - werte["ULOW"], werte["VHIGH"] - werte["VLOW"])

    def luma_lock(self, restauriert, roh, ziel):
        """Y aus der Restaurierung, Cb/Cr aus Pass 2 (auf deren Größe skaliert); 16 Bit gegen Rundungsfehler."""
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
