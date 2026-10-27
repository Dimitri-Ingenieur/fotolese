"""
fotosort.py – Fotos rekursiv einsammeln, ähnliche Bilder gruppieren und in
nummerierte Ordner 0001–9999 verschieben (chronologisch, ein Ordner je Gruppe).

Ähnlich heißt:
  * gleiches Bild in anderer Auflösung, Kompression oder leicht bearbeitet
    (Wahrnehmungs-Hashes pHash + dHash, Abstand <= SCHWELLE)
  * Serienbilder: gleiche Kamera, höchstens SERIE_SEK Sekunden zum Nachbarbild,
    Abstand <= SERIE_SCHWELLE
  * NEF+JPG derselben Aufnahme landen dadurch automatisch im selben Ordner.
  * Zu jedem NEF ohne Kamera-JPG wird ein JPG erzeugt (eingebettete Kamera-Vorschau, verlustfrei,
    mit Datum, GPS und Kamera aus dem NEF) – auch für NEF, die schon im Bestand liegen.

Vorhandener Bestand in AUSGABE/0001…9999 bleibt unangetastet:
  * neue Bilder, die zu einem bestehenden Ordner passen, kommen in diesen Ordner
    (bei mehreren passenden Ordnern in den mit dem ähnlichsten Bild)
  * alle übrigen bekommen neue Ordner ab der höchsten vorhandenen Nummer + 1
  * gibt es den Dateinamen im Zielordner schon, erhält die neue Datei einen
    Laufindex: IMG_0001.JPG -> IMG_0001_1.JPG, IMG_0001_2.JPG …
    (Begleitdateien wie DSC_1.NEF.xmp werden passend mit umbenannt)

Aufruf (Conda):
  conda create -n fotosort -c conda-forge python=3.12 pillow numpy rawpy
  conda activate fotosort
  python fotosort.py EINGABE AUSGABE
  MODUS=test python fotosort.py EINGABE AUSGABE      # nur Plan, nichts bewegen
  MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv

Umgebungsvariablen (Standard in Klammern):
  MODUS           (move)   move | copy | link | test | undo
                           link = Vorschau mit symbolischen Links (nur Linux-Dateisysteme)
  JA              (0)      1 = ohne Rückfrage ausführen
  SCHWELLE        (20)     Bildvergleich: max. Abstand pHash+dHash (0–128)
  SERIE_SEK       (3)      Serienbilder: max. Zeitabstand zum Nachbarbild in Sekunden
  SERIE_SCHWELLE  (36)     Serienbilder: max. Abstand pHash+dHash (0–128)
  EINZELN         (ordner) ordner = jedes Einzelbild eigener Ordner, 0000 = alle in Ordner 0000
  JOBS            (Kerne)  parallele Prozesse; Quelle oder Bestand auf HDD/USB-Platte: z. B. 4
  BEGLEIT         (1)      .xmp/.pp3/.aae-Begleitdateien mitnehmen
  AUFRAEUMEN      (1)      leere Quellordner nach dem Verschieben entfernen
  NEF_JPG         (1)      0 = keine JPG aus NEF erzeugen
  DUPLIKATE       (1)      inhaltsgleiche Dateien (SHA-256) nur einmal: Bilder, die es im Bestand schon gibt
                           oder die in der Eingabe mehrfach vorkommen, werden übersprungen (bleiben liegen)
  FORTSCHRITT_JSON (0)     1 = Fortschritt als Zeilen „#FS {json}“ auf stdout (für bestof.py)
  CACHE           (~/.cache/fotosort/cache.sqlite3)  Pfad oder 0 = aus
                           merkt sich auch die Bilder im Bestand: Folgeläufe lesen sie nicht neu

Pakete: pillow numpy rawpy (rawpy optional, für NEF empfohlen; Conda: Kanal conda-forge)
"""
import atexit
import os
import signal
import sys
import time
from collections import Counter
from datetime import datetime

from fotolese.gemein import _env
from fotolese.sort.konst import MAX_ORDNER, VERSION, WINDOWS_FS, _EPOCHE, rawpy
from fotolese.sort.bericht import Fortschritt, dauer, gb, info, zahl
from fotolese.sort.exif import _zeit_aus_name
from fotolese.sort.bild import analyse_parallel
from fotolese.sort.cache import Cache
from fotolese.sort.suche import ordne_begleitdateien, suche, suche_bestand
from fotolese.sort.gruppe import duplikate_finden, finde_anker, gruppiere
from fotolese.sort.plan import dateisystem, hoechste_nummer, plane
from fotolese.sort.lauf import Protokoll, ausfuehren, bestaetigen, leere_ordner_entfernen, rueckgaengig


def main():
    # Strg+C bzw. SIGINT (Abbrechen in bestof.py) immer als KeyboardInterrupt – auch wenn der startende
    # Prozess SIGINT ignoriert (z. B. Hintergrundstart aus einer Shell)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "--hilfe"):
        print(__doc__)
        return 0
    modus = _env("MODUS", "move").lower()
    if modus not in ("move", "copy", "link", "test", "undo"):
        sys.exit(f"Fehler: MODUS={modus!r} – erlaubt: move, copy, link, test, undo")
    if modus == "undo":
        if len(args) != 1:
            sys.exit("Aufruf: MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv")
        return rueckgaengig(os.path.abspath(args[0]))
    if len(args) != 2:
        sys.exit("Aufruf: python fotosort.py EINGABE AUSGABE   (Hilfe: -h)")

    schwelle = _env("SCHWELLE", 20, int)
    serie_sek = _env("SERIE_SEK", 3.0, float)
    serie_schwelle = _env("SERIE_SCHWELLE", 36, int)
    einzeln = _env("EINZELN", "ordner").lower()
    if einzeln not in ("ordner", "0000"):
        sys.exit("Fehler: EINZELN muss 'ordner' oder '0000' sein.")
    jobs = max(1, _env("JOBS", os.cpu_count() or 1, int))
    begleit_an = _env("BEGLEIT", "1") != "0"
    aufraeumen = _env("AUFRAEUMEN", "1") != "0"
    nef_jpg_an = _env("NEF_JPG", "1") != "0"
    duplikate_an = _env("DUPLIKATE", "1") != "0"
    cache_pfad = os.path.expanduser(_env("CACHE", "~/.cache/fotosort/cache.sqlite3"))

    eingabe = os.path.abspath(args[0])
    ausgabe = os.path.abspath(args[1])
    if not os.path.isdir(eingabe):
        sys.exit(f"Fehler: Eingabeordner {eingabe} existiert nicht.")
    if os.path.realpath(eingabe) == os.path.realpath(ausgabe):
        sys.exit("Fehler: Eingabe und Ausgabe sind derselbe Ordner.")
    if os.path.exists(ausgabe) and not os.path.isdir(ausgabe):
        sys.exit(f"Fehler: {ausgabe} ist kein Ordner.")
    if not os.path.isdir(ausgabe):
        if not os.path.isdir(os.path.dirname(ausgabe)):
            sys.exit(f"Fehler: {os.path.dirname(ausgabe)} existiert nicht – Laufwerk eingehängt?")
        os.mkdir(ausgabe)
    mountpunkt, fs_typ = dateisystem(ausgabe)
    if modus == "link" and fs_typ in WINDOWS_FS:
        sys.exit(f"Fehler: MODUS=link braucht ein Linux-Dateisystem, {ausgabe} liegt auf {fs_typ}.")

    info(f"fotosort {VERSION} · Modus {modus} · rawpy {'ja' if rawpy else 'nein (NEF über eingebettete Vorschau)'}")
    info(f"Eingabe:  {eingabe}")
    info(f"Ausgabe:  {ausgabe}  (Laufwerk {mountpunkt}, {fs_typ})")

    t0 = time.time()
    bilder, begleit, scan = suche(eingabe, os.path.realpath(ausgabe))
    typen = Counter(os.path.splitext(d.pfad)[1].lower().lstrip(".") for d in bilder)
    n_begleit = ordne_begleitdateien(bilder, begleit) if begleit_an else 0
    info(f"Gefunden: {zahl(len(bilder))} Bilder ("
         + " · ".join(f"{k} {zahl(v)}" for k, v in typen.most_common())
         + f"), {gb(sum(d.groesse for d in bilder))}; Begleitdateien: {zahl(n_begleit)}")
    if scan["links"] or scan["ordner_fehler"]:
        info(f"Übersprungen: {zahl(scan['links'])} symbolische Links, {zahl(scan['ordner_fehler'])} unlesbare Ordner")
    if not bilder:
        info("Keine Bilder gefunden.")
        return 0
    bestand = suche_bestand(ausgabe, os.path.realpath(eingabe))
    if bestand:
        b_ordner = sorted({d.anker for d in bestand})
        info(f"Bestand:  {zahl(len(bestand))} Bilder in {zahl(len(b_ordner))} Ordnern "
             f"({b_ordner[0]}–{b_ordner[-1]}) – bleiben, wo sie sind")

    # Analyse (mit Cache; Bestandsbilder sind nach dem ersten Lauf dort bekannt)
    cache = Cache(cache_pfad)
    atexit.register(cache.schliessen)
    doppelt = {}
    if duplikate_an:
        doppelt = duplikate_finden(bilder, bestand, cache, jobs)
        if doppelt:
            im_bestand = sum(1 for v in doppelt.values() if v.startswith(ausgabe + os.sep))
            bilder = [d for d in bilder if d.pfad not in doppelt]
            info(f"Duplikate: {zahl(len(doppelt))} Dateien mit gleichem Inhalt werden übersprungen "
                 f"({zahl(im_bestand)} schon im Archiv, {zahl(len(doppelt) - im_bestand)} mehrfach in der Quelle)")
        if not bilder:
            info("Alle Bilder sind schon im Archiv – nichts zu tun.")
            return 0
    alle_bilder = bilder + bestand
    offen = []
    for i, d in enumerate(alle_bilder):
        d.res = cache.holen(d.pfad, d.groesse, d.mtime)
        if d.res is None:
            offen.append(i)
    treffer = len(alle_bilder) - len(offen)
    fort = Fortschritt("Analyse", len(offen))
    zaehler = [0]

    def ablegen(i, res):
        d = alle_bilder[i]
        d.res = res
        if isinstance(res, list):
            cache.ablegen(d.pfad, d.groesse, d.mtime, res)
        zaehler[0] += 1
        fort.melden(zaehler[0])

    try:
        if offen:
            analyse_parallel([(i, alle_bilder[i].pfad) for i in offen], min(jobs, len(offen)), ablegen)
            fort.melden(len(offen), ende=True)
    except KeyboardInterrupt:
        cache.schliessen()
        sys.exit("\nAbgebrochen während der Analyse – nichts verschoben. Bisherige Ergebnisse sind im Cache.")
    info(f"Analyse:  {dauer(time.time() - t0)} (aus Cache: {zahl(treffer)})")

    for d in alle_bilder:
        t_exif = d.res[4] if d.ok else None
        if t_exif is None:
            t_exif = _zeit_aus_name(os.path.basename(d.pfad))
        if t_exif is None:
            try:
                t_exif = (datetime.fromtimestamp(d.mtime / 1e9) - _EPOCHE).total_seconds()
            except (OverflowError, OSError, ValueError):
                t_exif = 0.0
        d.t_sort = t_exif
    defekt = [d for d in bilder if not d.ok]
    abgeschnitten = sum(1 for d in bilder if d.ok and d.res[6])

    gruppen, n_bild, n_serie = gruppiere(bilder, schwelle, serie_sek, serie_schwelle)
    anker = finde_anker(gruppen, bestand, schwelle, serie_sek, serie_schwelle)
    start = hoechste_nummer(ausgabe) + 1
    frei_gruppen = [g for g, a in zip(gruppen, anker) if a is None]
    n_einzeln = sum(1 for g in frei_gruppen if len(g) == 1)
    n_ordner = len(frei_gruppen) - (n_einzeln if einzeln == "0000" else 0)
    if n_ordner and start + n_ordner - 1 > MAX_ORDNER:
        sys.exit(f"Abbruch vor dem Verschieben: {zahl(n_ordner)} neue Ordner nötig, ab {start:04d} frei "
                 f"sind nur {zahl(max(MAX_ORDNER - start + 1, 0))}.\n"
                 f"Möglich: EINZELN=0000 (Einzelbilder in Sammelordner) oder höhere SCHWELLE / SERIE_SCHWELLE.")
    nef_jpg, bestand_nef = set(), {}
    if nef_jpg_an:  # zu jedem NEF ein JPG – außer die Kamera hat schon eins geschrieben
        def stamm(d):
            return os.path.splitext(os.path.basename(d.pfad))[0].casefold()

        def ist(d, *endungen):
            return os.path.splitext(d.pfad)[1].lower() in endungen

        kamera_jpg = {(os.path.dirname(d.pfad), stamm(d)) for d in bilder if d.ok and ist(d, ".jpg", ".jpeg")}
        nef_jpg = {d.pfad for d in bilder
                   if d.ok and ist(d, ".nef") and (os.path.dirname(d.pfad), stamm(d)) not in kamera_jpg}
        bestand_jpg = {(d.anker, stamm(d)) for d in bestand if ist(d, ".jpg", ".jpeg")}
        for d in bestand:
            if (d.ok and ist(d, ".nef") and (d.anker, stamm(d)) not in bestand_jpg
                    and os.path.dirname(d.pfad) == os.path.join(ausgabe, d.anker)):
                bestand_nef.setdefault(d.anker, []).append((d.pfad, d.groesse))
    plan, umbenannt, jpg_neu, jpg_bestand = plane(gruppen, anker, ausgabe, einzeln, start, fs_typ,
                                                  nef_jpg, bestand_nef)

    groessen = sorted(((len(g), g) for g in frei_gruppen if len(g) > 1), key=lambda x: -x[0])
    ordner_von = {}
    for ordner, eintraege in plan:
        for quelle, *_ in eintraege:
            ordner_von[quelle] = ordner
    bereich = f"{start:04d}–{start + n_ordner - 1:04d}" if n_ordner else "–"
    info(f"Gruppen:  {zahl(n_ordner)} neue Ordner ({bereich}) · {zahl(len(groessen))} mit ≥2 Bildern · "
         f"{zahl(n_einzeln)} Einzelbilder" + (" → Ordner 0000" if einzeln == "0000" and n_einzeln else ""))
    if bestand:
        ergaenzt = [g for g, a in zip(gruppen, anker) if a is not None]
        info(f"Ergänzt:  {zahl(sum(len(g) for g in ergaenzt))} Bilder kommen in "
             f"{zahl(len({a for a in anker if a is not None}))} bestehende Ordner")
    if umbenannt:
        info(f"Laufindex: {zahl(umbenannt)} Bilder, deren Name im Zielordner schon existiert (z. B. IMG_0001_1.JPG)")
    if jpg_neu or jpg_bestand:
        info(f"JPG aus NEF: {zahl(jpg_neu + jpg_bestand)} werden erzeugt"
             + (f" (davon {zahl(jpg_bestand)} für NEF im Bestand)" if jpg_bestand else ""))
    info(f"Verknüpft: {zahl(n_bild)} × Bildvergleich (≤{schwelle}), {zahl(n_serie)} × Serie "
         f"(≤{serie_sek:g} s, ≤{serie_schwelle})")
    for anzahl, g in groessen[:5]:
        info(f"  größte: {ordner_von[g[0].pfad]} · {anzahl} Bilder · {os.path.basename(g[0].pfad)} …")
    if defekt:
        info(f"Nicht lesbar: {zahl(len(defekt))} Dateien – bleiben liegen (siehe Protokoll), z. B.:")
        for d in defekt[:5]:
            info(f"  {d.pfad}: {d.res}")
    if abgeschnitten:
        info(f"Hinweis: {zahl(abgeschnitten)} Dateien sind abgeschnitten, aber auswertbar.")

    # Platzbedarf
    ziel_dev = os.stat(ausgabe).st_dev
    sv = os.statvfs(ausgabe)
    cluster = sv.f_frsize or 4096
    frei = sv.f_bavail * sv.f_frsize
    alle = [e for _, eintraege in plan for e in eintraege]
    gesamt = sum(e[2] for e in alle)
    noetig = sum(-(-e[2] // cluster) * cluster for e in alle
                 if e[4] == "jpg" or modus == "copy" or (modus in ("move", "test") and e[3] != ziel_dev))
    if modus == "link":
        noetig = sum(-(-e[2] // cluster) * cluster for e in alle if e[4] == "jpg")
    reserve = (1 << 30) + noetig // 100
    passt = noetig + reserve <= frei
    info(f"Platz:    benötigt {gb(noetig)} (+{gb(reserve)} Reserve), frei {gb(frei)} → "
         + ("passt" if passt else "REICHT NICHT"))
    if fs_typ == "vfat" and any(e[2] >= 4 * 1024 ** 3 for e in alle):
        info("Warnung: FAT32 erlaubt keine Dateien ≥ 4 GiB.")

    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    if modus == "test":
        prot = Protokoll(os.path.join(ausgabe, f"fotosort_plan_{stempel}"))
        for ordner, eintraege in plan:
            for quelle, ziel, groesse, _dev, art in eintraege:
                prot.zeile(ordner, quelle, ziel, groesse, "geplant (JPG aus NEF)" if art == "jpg" else "geplant")
        for d in defekt:
            prot.zeile("", d.pfad, "", d.groesse, f"nicht lesbar: {d.res}")
        prot.schliessen()
        info(f"Plan:     {prot.pfad}")
        info("Probelauf – nichts verändert.")
        return 0
    if not alle:
        info("Nichts zu verschieben.")
        return 0
    if not passt:
        sys.exit("Abbruch: zu wenig Platz im Ziel – nichts verändert.")
    verb = {"move": "verschieben", "copy": "kopieren", "link": "verlinken"}[modus]
    n_dateien = sum(1 for e in alle if e[4] == "datei")
    frage = f"{zahl(n_dateien)} Dateien ({gb(sum(e[2] for e in alle if e[4] == 'datei'))}) nach {ausgabe} {verb}"
    if jpg_neu or jpg_bestand:
        frage += f" und {zahl(jpg_neu + jpg_bestand)} JPG aus NEF erzeugen"
    if not bestaetigen(frage + "?"):
        sys.exit("Abgebrochen – nichts verändert.")

    prot = Protokoll(os.path.join(ausgabe, f"fotosort_{stempel}"))
    logpfad = prot.pfad
    for d in defekt:
        prot.zeile("", d.pfad, "", d.groesse, f"nicht lesbar: {d.res}")
    for quelle, gleich in sorted(doppelt.items()):
        prot.zeile("", quelle, "", "", f"übersprungen: gleicher Inhalt wie {gleich}")
    res_von = {d.pfad: d.res for d in bilder if d.ok}

    def im_cache_merken(quelle, ziel):
        """Neuen Pfad im Cache ablegen – beim nächsten Lauf ist der Bestand dann schon bekannt."""
        res = res_von.get(quelle)
        if res is not None:
            try:
                st = os.stat(ziel)
                cache.ablegen(ziel, st.st_size, st.st_mtime_ns, res)
            except OSError:
                pass

    t1 = time.time()
    beweger, abbruch = ausfuehren(plan, modus, prot, gesamt, nach_erfolg=im_cache_merken)
    prot.schliessen()
    cache.schliessen()
    entfernt = 0
    if modus == "move" and aufraeumen:
        entfernt = leere_ordner_entfernen(beweger.quellordner, eingabe)
    z = beweger.zaehler
    info(f"Fertig in {dauer(time.time() - t1)}: " + " · ".join(f"{zahl(v)} {k}" for k, v in z.most_common())
         + (f" · {zahl(entfernt)} leere Quellordner entfernt" if entfernt else ""))
    info(f"Protokoll: {logpfad}")
    if abbruch:
        info(f"ABGEBROCHEN ({abbruch}). Erneuter Start ergänzt den Rest: passende Bilder kommen "
             f"in die schon angelegten Ordner, übrige in neue.")
    if modus in ("move", "copy", "link"):
        info(f"Rückgängig: MODUS=undo {sys.executable} {os.path.abspath(sys.argv[0])} '{logpfad}'")
    return 1 if abbruch or z["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
