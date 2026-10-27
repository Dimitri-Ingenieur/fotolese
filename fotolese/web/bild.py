"""fotolese.web.bild – Vorschaubilder (klein, Lupe, Gesichtsausschnitt) erzeugen und zwischenspeichern.

Vorschau legt kleine Bilder auf Platte ab (Standard SORTIERT/.vorschau), Lupenbilder im RAM.
"""
import hashlib
import io
import os
import threading
from collections import OrderedDict

from PIL import Image, ImageOps

from fotolese.web.konst import THUMB


def _draft_groesse(w, h, kante):
    if w >= h:
        return kante, max(1, kante * h // max(w, 1))
    return max(1, kante * w // max(h, 1)), kante


def _rgb(img):
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N"):
        img = img.convert("I")
    if img.mode in ("I", "F"):
        hoch = img.getextrema()[1] or 1
        if hoch > 255:
            img = img.point(lambda v: v * (255.0 / hoch))
        img = img.convert("L")
    if img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        weiss = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(weiss, rgba)
    return img.convert("RGB")


def oeffne(pfad, kante):
    """Bild aufrecht als RGB laden; JPEG nur so groß dekodieren wie nötig (kante 0 = voll)."""
    with Image.open(pfad) as img:
        if kante and img.format in ("JPEG", "MPO"):
            img.draft("RGB", _draft_groesse(img.width, img.height, kante))
        img.load()
        img = ImageOps.exif_transpose(img)
        return _rgb(img)


def als_jpeg(img, kante, qualitaet):
    if kante and max(img.size) > kante:
        img.thumbnail((kante, kante), Image.Resampling.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=qualitaet)
    return b.getvalue()


def thumb_schluessel(pfad, groesse, mt):
    return hashlib.sha1(f"{pfad}|{groesse}|{mt}|{THUMB}".encode("utf-8", "surrogateescape")).hexdigest()


def atomar_schreiben(datei, daten):
    os.makedirs(os.path.dirname(datei), exist_ok=True)
    tmp = f"{datei}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "wb") as f:
        f.write(daten)
    os.replace(tmp, datei)


PLATZHALTER = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><rect width="120" height="90" '
               b'fill="#444"/><text x="60" y="50" fill="#bbb" font-size="11" text-anchor="middle" '
               b'font-family="sans-serif">nicht lesbar</text></svg>')


class Vorschau:
    """Vorschaubilder auf Platte (Standard: SORTIERT/.vorschau), Lupenbilder im Arbeitsspeicher."""

    def __init__(self, ordner, gross):
        self.ordner = ordner
        self.gross = gross
        self._ram = OrderedDict()
        self._ram_bytes = 0
        self._lock = threading.Lock()

    def _ram_holen(self, key):
        with self._lock:
            if key in self._ram:
                self._ram.move_to_end(key)
                return self._ram[key]
        return None

    def _ram_ablegen(self, key, daten):
        with self._lock:
            if key in self._ram:
                return
            self._ram[key] = daten
            self._ram_bytes += len(daten[1])
            while self._ram_bytes > 256 * 1024 * 1024 and self._ram:
                _, alt = self._ram.popitem(last=False)
                self._ram_bytes -= len(alt[1])

    def _platte(self, key, erzeugen):
        if self.ordner:
            datei = os.path.join(self.ordner, key[:2], key + ".jpg")
            try:
                with open(datei, "rb") as f:
                    return "image/jpeg", f.read()
            except OSError:
                pass
        treffer = self._ram_holen(key)
        if treffer:
            return treffer
        daten = ("image/jpeg", erzeugen())
        if self.ordner:
            try:
                atomar_schreiben(datei, daten[1])
                return daten
            except OSError:
                pass
        self._ram_ablegen(key, daten)
        return daten

    def klein(self, pfad, groesse, mt):
        return self._platte(thumb_schluessel(pfad, groesse, mt),
                            lambda: als_jpeg(oeffne(pfad, THUMB), THUMB, 80))

    def gesicht(self, gid, pfad, mt, box):
        x, y, w, h = box

        def erzeugen():
            seite = max(w, h)
            with Image.open(pfad) as img:
                lang = max(img.size)
                if img.format in ("JPEG", "MPO"):
                    ziel = min(lang, int(320 / max(seite, 0.01)))
                    img.draft("RGB", _draft_groesse(img.width, img.height, ziel))
                img.load()
                bild = _rgb(ImageOps.exif_transpose(img))
            bw, bh = bild.size
            cx, cy, s = (x + w / 2) * bw, (y + h / 2) * bh, max(w * bw, h * bh) * 0.8
            ausschnitt = bild.crop((int(cx - s), int(cy - s), int(cx + s), int(cy + s)))
            return als_jpeg(ausschnitt.resize((176, 176), Image.Resampling.LANCZOS), 0, 85)

        schluessel = f"gesicht|{gid}|{pfad}|{mt}|{x:.4f}|{y:.4f}|{w:.4f}|{h:.4f}"  # Kasten gehört dazu: IDs können neu vergeben werden
        return self._platte(hashlib.sha1(schluessel.encode("utf-8", "surrogateescape")).hexdigest(), erzeugen)

    def gross_bild(self, pfad, groesse, mt):
        ext = os.path.splitext(pfad)[1].lower()
        if self.gross == 0:
            with open(pfad, "rb") as f:
                return ("image/png" if ext == ".png" else "image/jpeg"), f.read()
        key = f"{pfad}|{groesse}|{mt}|{self.gross}"
        treffer = self._ram_holen(key)
        if treffer:
            return treffer
        daten = ("image/jpeg", als_jpeg(oeffne(pfad, self.gross), self.gross, 88))
        self._ram_ablegen(key, daten)
        return daten
