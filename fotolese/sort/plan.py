"""fotolese.sort.plan – Zielnamen säubern/eindeutig machen und den Verschiebeplan erstellen."""
import os
import re
from collections import defaultdict

from fotolese.sort.konst import WINDOWS_FS


_VERBOTEN = set('<>:"\\|?*')


def saeubern(name):
    neu = "".join("_" if (ch in _VERBOTEN or ord(ch) < 32 or 0xDC80 <= ord(ch) <= 0xDCFF) else ch
                  for ch in name)
    stamm, ext = os.path.splitext(neu)
    return (stamm.rstrip(" .") or "bild") + ext


def eindeutig(name, belegt):
    """Freien Namen im Zielordner finden: IMG.JPG, sonst IMG_1.JPG, IMG_2.JPG … (Laufindex).
    Vergleich ohne Groß/Klein, damit es auch auf exFAT/NTFS keine Kollision gibt."""
    stamm, ext = os.path.splitext(name)
    while stamm and len(os.fsencode(stamm + ext)) > 240:
        stamm = stamm[:-1]
    kandidat, n = stamm + ext, 0
    while kandidat.casefold() in belegt:
        n += 1
        kandidat = f"{stamm}_{n}{ext}"
    belegt.add(kandidat.casefold())
    return kandidat


def hoechste_nummer(ausgabe):
    hoch = 0
    try:
        for e in os.scandir(ausgabe):
            if e.is_dir(follow_symlinks=False) and re.fullmatch(r"\d{4}", e.name):
                hoch = max(hoch, int(e.name))
    except OSError:
        pass
    return hoch


def dateisystem(pfad):
    pfad = os.path.realpath(pfad)
    best = ("/", "?")
    try:
        with open("/proc/self/mounts", encoding="utf-8", errors="replace") as f:
            for zeile in f:
                teile = zeile.split()
                if len(teile) < 3:
                    continue
                mp = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), teile[1])
                if (pfad == mp or pfad.startswith(mp.rstrip("/") + "/")) and len(mp) >= len(best[0]):
                    best = (mp, teile[2])
    except OSError:
        pass
    return best


def plane(gruppen, anker, ausgabe, einzeln, start, fs_typ, nef_jpg=frozenset(), bestand_nef=None):
    """Plan [(ordnername, [(quelle, ziel, groesse, dev, art)])] in Ausführungsreihenfolge.
    art: "datei" = verschieben/kopieren, "jpg" = JPG aus dem NEF 'quelle' erzeugen.
    Rückgabe: plan, Anzahl Laufindex-Umbenennungen, Anzahl geplanter JPG (neu, Bestand)."""
    windows = fs_typ in WINDOWS_FS or fs_typ == "?"
    frei = [g for g, a in zip(gruppen, anker) if a is None]
    nummeriert = [g for g in frei if len(g) > 1 or einzeln != "0000"]
    zuteilung = defaultdict(list)
    for g, a in zip(gruppen, anker):
        if a is not None:
            zuteilung[a].extend(g)                 # ergänzt bestehenden Ordner
    for g in frei:
        if len(g) == 1 and einzeln == "0000":
            zuteilung["0000"].extend(g)
    for k, g in enumerate(nummeriert):
        zuteilung[f"{start + k:04d}"].extend(g)    # neuer Ordner
    bestand_nef = bestand_nef or {}
    plan, umbenannt, jpg_neu, jpg_bestand = [], 0, 0, 0

    def jpg_eintrag(nef_jetzt, nef_zielname, groesse, belegt, zielordner):
        """JPG nur, wenn im Zielordner noch keine JPG/JPEG mit gleichem Namensstamm liegt."""
        stamm, ext = os.path.splitext(nef_zielname)
        if f"{stamm}.jpg".casefold() in belegt or f"{stamm}.jpeg".casefold() in belegt:
            return None
        name = eindeutig(stamm + (".JPG" if ext == ".NEF" else ".jpg"), belegt)
        return (nef_jetzt, os.path.join(zielordner, name), max(groesse // 7, 1), None, "jpg")

    for ordner in sorted(set(zuteilung) | set(bestand_nef)):
        g = sorted(zuteilung.get(ordner, []), key=lambda d: (d.t_sort, d.pfad))
        zielordner = os.path.join(ausgabe, ordner)
        try:
            belegt = {n.casefold() for n in os.listdir(zielordner)}
        except OSError:
            belegt = set()
        eintraege = []
        for d in g:
            name = os.path.basename(d.pfad)
            basis = saeubern(name) if windows else name
            neu = eindeutig(basis, belegt)
            if neu != basis:
                umbenannt += 1
            eintraege.append((d.pfad, os.path.join(zielordner, neu), d.groesse, d.dev, "datei"))
            stamm, neu_stamm = os.path.splitext(name)[0], os.path.splitext(neu)[0]
            for b_pfad, b_groesse, b_dev in d.begleit:
                b_name = os.path.basename(b_pfad)
                if b_name.casefold().startswith(name.casefold()):
                    b_neu = neu + b_name[len(name):]
                else:
                    b_neu = neu_stamm + b_name[len(stamm):]
                b_neu = eindeutig(saeubern(b_neu) if windows else b_neu, belegt)
                eintraege.append((b_pfad, os.path.join(zielordner, b_neu), b_groesse, b_dev, "datei"))
        # zweiter Durchgang: alle Namen des Ordners sind jetzt bekannt
        mit_jpg = []
        for e in eintraege:
            mit_jpg.append(e)
            if e[4] == "datei" and e[0] in nef_jpg:
                neu_e = jpg_eintrag(e[1], os.path.basename(e[1]), e[2], belegt, zielordner)
                if neu_e:
                    mit_jpg.append(neu_e)
                    jpg_neu += 1
        for nef, groesse in bestand_nef.get(ordner, []):
            neu_e = jpg_eintrag(nef, os.path.basename(nef), groesse, belegt, zielordner)
            if neu_e:
                mit_jpg.append(neu_e)
                jpg_bestand += 1
        if mit_jpg:
            plan.append((ordner, mit_jpg))
    return plan, umbenannt, jpg_neu, jpg_bestand
