"""fotolese.sort.suche – Eingabe und bestehende Ordner im Dateisystem finden.

Datei bündelt Pfad, Größe, mtime und die zugeordneten Begleitdateien eines Bildes.
"""
import os
import re
import stat
from collections import Counter

from fotolese.sort.konst import BEGLEIT_EXT, BILD_EXT, SKIP_ORDNER


class Datei:
    __slots__ = ("pfad", "groesse", "mtime", "dev", "res", "t_sort", "begleit", "anker")

    def __init__(self, pfad, st, anker=None):
        self.pfad, self.groesse, self.mtime, self.dev = pfad, st.st_size, st.st_mtime_ns, st.st_dev
        self.res = None
        self.t_sort = 0.0
        self.begleit = []  # [(pfad, groesse, dev)]
        self.anker = anker  # Bestand: Ordnername "NNNN", neue Bilder: None

    @property
    def ok(self):
        return isinstance(self.res, list)


def suche_bestand(ausgabe, eingabe_real):
    """Bilder, die schon in AUSGABE/NNNN liegen. Sie werden nie bewegt, sondern dienen als Anker."""
    bestand = []
    try:
        eintraege = sorted(os.scandir(ausgabe), key=lambda e: e.name)
    except OSError:
        return bestand
    for e in eintraege:
        if not (re.fullmatch(r"\d{4}", e.name) and e.is_dir(follow_symlinks=False)):
            continue
        for wurzel, ordner, dateien in os.walk(e.path):
            echt = os.path.realpath(wurzel)
            if echt == eingabe_real or echt.startswith(eingabe_real + os.sep):
                ordner[:] = []
                continue
            ordner[:] = sorted(o for o in ordner if not o.startswith(".") and o not in SKIP_ORDNER)
            for name in sorted(dateien):
                if name.startswith("._") or os.path.splitext(name)[1].lower() not in BILD_EXT:
                    continue
                pfad = os.path.join(wurzel, name)
                try:
                    st = os.lstat(pfad)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    bestand.append(Datei(pfad, st, anker=e.name))
    return bestand


def suche(eingabe, ausgabe_real):
    bilder, begleit, stat_info = [], {}, Counter()

    def fehler(e):
        stat_info["ordner_fehler"] += 1

    for wurzel, ordner, dateien in os.walk(eingabe, onerror=fehler):
        behalten = []
        for o in sorted(ordner):
            voll = os.path.join(wurzel, o)
            if o.startswith(".") or o in SKIP_ORDNER or os.path.realpath(voll) == ausgabe_real:
                stat_info["ordner_uebersprungen"] += 1
                continue
            behalten.append(o)
        ordner[:] = behalten
        for name in sorted(dateien):
            if name.startswith("._"):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in BILD_EXT and ext not in BEGLEIT_EXT:
                continue
            pfad = os.path.join(wurzel, name)
            try:
                st = os.lstat(pfad)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                stat_info["links"] += 1
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if ext in BILD_EXT:
                bilder.append(Datei(pfad, st))
            else:
                begleit.setdefault(wurzel, {})[name.casefold()] = (name, st.st_size, st.st_dev)
    return bilder, begleit, stat_info


def ordne_begleitdateien(bilder, begleit):
    """.xmp/.pp3/.aae dem passenden Bild zuordnen (NEF zuerst, z. B. DSC_1.xmp gehört zum NEF)."""
    vergeben = set()
    reihenfolge = sorted(bilder, key=lambda d: (os.path.dirname(d.pfad),
                                                os.path.splitext(os.path.basename(d.pfad))[0].casefold(),
                                                not d.pfad.lower().endswith(".nef"), d.pfad))
    anzahl = 0
    for d in reihenfolge:
        ordner, name = os.path.split(d.pfad)
        vorhanden = begleit.get(ordner)
        if not vorhanden:
            continue
        stamm = os.path.splitext(name)[0]
        for kandidat in (name + ".xmp", name + ".pp3", stamm + ".xmp", stamm + ".aae"):
            schluessel = (ordner, kandidat.casefold())
            if schluessel in vergeben or kandidat.casefold() not in vorhanden:
                continue
            echt, groesse, dev = vorhanden[kandidat.casefold()]
            vergeben.add(schluessel)
            d.begleit.append((os.path.join(ordner, echt), groesse, dev))
            anzahl += 1
    return anzahl
