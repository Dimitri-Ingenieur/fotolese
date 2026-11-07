"""fotolese.sort.neu – Neu-Gruppierung des Archivs (MODUS=gruppen) und Analyse einer Auswahl (MODUS=analyse).

Beide Modi planen nur, verschoben wird nichts. bestof.py führt den Plan aus und nimmt dabei Sterne, Alben, Jahr,
Gesichter und verbesserte Fassungen mit (Einstellungen → Neu gruppieren, Ordner zusammenfassen).

Neu-Gruppierung: Die Bilder direkt in den Ordnern 0000–99999 werden mit den eingestellten Werten gruppiert, als
kämen sie alle in einem Import. Dateien gleichen Namensstamms im selben Ordner (IMG_1.JPG + IMG_1.NEF) bleiben
beisammen. Jede Gruppe behält den Ordner, in dem schon die meisten ihrer Bilder liegen – ein Ordner gehört höchstens
einer Gruppe, vergeben wird nach Bildzahl, damit möglichst wenig wandert. Übrige Gruppen bekommen neue Nummern ab
der höchsten + 1 (Einzelbilder mit EINZELN=0000 kommen nach 0000). Einfarbige oder unlesbare Bilder lassen sich
nicht vergleichen und bleiben, wo sie sind.

Analyse: Mit welchem Wert hätte fotosort die Bilder der gewählten Ordner beim Import in eine Gruppe gelegt? Je Wert
(SCHWELLE, SERIE_SEK, SERIE_SCHWELLE) der kleinste, der bei sonst gleichen Einstellungen genügt: die schwächste
Verbindung im minimalen Spannbaum der Auswahl. Dazu die Folgen im ganzen Archiv – welche Ordner mit diesem Wert bei
einer Neu-Gruppierung außerdem zusammenkämen.
"""
import atexit
import json
import math
import os
import stat
import sys
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

from fotolese.gemein import _env, ist_ordner, ordner_folge
from fotolese.sort.konst import BILD_EXT, FLACH_STD, MAX_ORDNER, VERSION
from fotolese.sort.bericht import Fortschritt, info, json_zeile, zahl, JSON_FORTSCHRITT
from fotolese.sort.bild import analysieren
from fotolese.sort.cache import Cache
from fotolese.sort.gruppe import UnionFind, _popcount
from fotolese.sort.suche import Datei

SAMMEL = "0000"        # Sammelordner für Einzelbilder (EINZELN=0000)
SERIE_FENSTER = 60     # wie gruppiere: Serienpartner höchstens 60 Bilder zurück (gleiche Kamera, nach Zeit)
MAX_AUSWAHL = 3000     # Analyse: höchstens so viele vergleichbare Bilder in den gewählten Ordnern
FOLGEN_BIS = 50        # Folgen im Archiv nur bis zu dieser SCHWELLE – darüber ähneln sich fast alle Fotos
BEISPIELE = 30         # so viele Beispiele (Zusammenlegungen, Teilungen) stehen im Plan


def suche_archiv(ausgabe):
    """Alle Bilder direkt in AUSGABE/0000–99999 (ohne Unterordner wie „verbessert“ und ohne versteckte Dateien);
    anker = Ordnername."""
    bilder = []
    try:
        ordner = sorted((e.name for e in os.scandir(ausgabe)
                         if ist_ordner(e.name) and e.is_dir(follow_symlinks=False)), key=ordner_folge)
    except OSError:
        return bilder
    for o in ordner:
        try:
            eintraege = sorted(os.scandir(os.path.join(ausgabe, o)), key=lambda e: e.name)
        except OSError:
            continue
        for e in eintraege:
            if e.name.startswith(".") or os.path.splitext(e.name)[1].lower() not in BILD_EXT:
                continue
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                bilder.append(Datei(e.path, st, anker=o))
    return bilder


def vergleichbar(d):
    """Lesbar und nicht (fast) einfarbig – nur solche Bilder verbindet fotosort über Hashes oder als Serie."""
    return d.ok and d.res[2] >= FLACH_STD


def _stamm(d):
    return d.anker, os.path.splitext(os.path.basename(d.pfad))[0].casefold()


def _rel(d):
    return f"{d.anker}/{os.path.basename(d.pfad)}"


def _kopie(uf):
    neu = UnionFind(0)
    neu.p, neu.g = list(uf.p), list(uf.g)
    return neu


def stamm_kanten(bilder):
    """Paare gleichen Namensstamms im selben Ordner (IMG_1.JPG, IMG_1.NEF): bleiben immer zusammen."""
    erstes, kanten = {}, []
    for i, d in enumerate(bilder):
        k = _stamm(d)
        if k in erstes:
            kanten.append((erstes[k], i))
        else:
            erstes[k] = i
    return kanten


def bild_kanten(bilder, ufs, titel="Vergleich"):
    """Paare vergleichbarer Bilder mit Abstand pHash+dHash ≤ Schwelle verbinden – für jedes (Schwelle, UnionFind)
    in ufs, alle in einem blockweisen Durchgang wie in gruppiere."""
    idx = [i for i, d in enumerate(bilder) if vergleichbar(d)]
    m = len(idx)
    if m < 2 or not ufs:
        return
    idx = np.array(idx, dtype=np.int64)
    ph = np.array([bilder[i].res[0] for i in idx], dtype=np.uint64)
    dh = np.array([bilder[i].res[1] for i in idx], dtype=np.uint64)
    hoch = max(s for s, _ in ufs)
    block = max(32, min(4096, 16_000_000 // m))
    gesamt, erledigt = m * (m - 1) // 2, 0
    fort = Fortschritt(titel, m, "Bilder")
    for a in range(0, m, block):
        b = min(a + block, m)
        abstand = (_popcount(ph[a:b, None] ^ ph[None, a:]).astype(np.uint16)
                   + _popcount(dh[a:b, None] ^ dh[None, a:]))
        zi, sp = np.nonzero(abstand <= hoch)
        wahl = sp > zi
        zi, sp = zi[wahl], sp[wahl]
        werte = abstand[zi, sp]
        gi, gj = idx[zi + a], idx[sp + a]
        for s, uf in ufs:
            k = werte <= s
            for i, j in zip(gi[k].tolist(), gj[k].tolist()):
                uf.vereinige(i, j)
        erledigt += (b - a) * (m - 1) - (b - a) * (a + b - 1) // 2
        fort.melden(round(m * erledigt / gesamt))
    fort.melden(m, ende=True)


def serien_kanten(bilder, sek, schwelle):
    """Serienpaare wie in gruppiere: gleiche Kamera, nach Aufnahmezeit höchstens SERIE_FENSTER Bilder auseinander,
    Zeitabstand ≤ sek, Abstand ≤ schwelle. Rückgabe: [(i, j, Sekunden, Abstand)]."""
    nach_kamera = defaultdict(list)
    for i, d in enumerate(bilder):
        if vergleichbar(d) and d.res[5] and d.res[3] is not None:
            nach_kamera[d.res[5]].append(i)
    kanten = []
    for liste in nach_kamera.values():
        liste.sort(key=lambda i: (bilder[i].res[3], bilder[i].pfad))
        for k in range(1, len(liste)):
            rk = bilder[liste[k]].res
            for j in range(k - 1, max(-1, k - SERIE_FENSTER - 1), -1):
                rj = bilder[liste[j]].res
                dt = rk[3] - rj[3]
                if dt > sek:
                    break
                ab = (rk[0] ^ rj[0]).bit_count() + (rk[1] ^ rj[1]).bit_count()
                if ab <= schwelle:
                    kanten.append((liste[k], liste[j], dt, ab))
    return kanten


def _komponenten(uf, n):
    je = defaultdict(list)
    for i in range(n):
        je[uf.finde(i)].append(i)
    return list(je.values())


def gruppieren(bilder, schwelle, serie_sek, serie_schwelle):
    """Union-Find über alle Bilder: Bildvergleich, Serien und gleiche Namensstämme."""
    uf = UnionFind(len(bilder))
    for i, j in stamm_kanten(bilder):
        uf.vereinige(i, j)
    bild_kanten(bilder, [(schwelle, uf)])
    for i, j, _, _ in serien_kanten(bilder, serie_sek, serie_schwelle):
        uf.vereinige(i, j)
    return uf


def ordner_zuteilen(bilder, gruppen, einzeln, start):
    """Ziel je Gruppe: der Ordner mit den meisten ihrer Bilder, solange keine andere Gruppe ihn hat – vergeben nach
    Bildzahl (bei Gleichstand nach Anteil an der Gruppe, dann kleinere Nummer), damit möglichst wenig wandert.
    0000 bekommt keine Gruppe, Einzelbilder dürfen dort bleiben. Übrige Gruppen: neue Ordner ab start in zeitlicher
    Folge, Einzelbilder mit EINZELN=0000 nach 0000. gruppen müssen zeitlich sortiert sein.
    Rückgabe: (Ziele parallel zu gruppen, neue Ordner)."""
    ziele, kandidaten = [None] * len(gruppen), []
    for gi, g in enumerate(gruppen):
        anzahl = Counter(bilder[i].anker for i in g)
        if len({_stamm(bilder[i]) for i in g}) == 1 and SAMMEL in anzahl:
            ziele[gi] = SAMMEL  # Einzelbild im Sammelordner bleibt dort
            continue
        for ordner, k in anzahl.items():
            if ordner != SAMMEL:
                kandidaten.append((-k, -k / len(g), ordner_folge(ordner), ordner, gi))
    kandidaten.sort()
    belegt = set()
    for _, _, _, ordner, gi in kandidaten:
        if ziele[gi] is None and ordner not in belegt:
            ziele[gi] = ordner
            belegt.add(ordner)
    neu, nummer = [], start
    for gi, g in enumerate(gruppen):
        if ziele[gi] is None:
            if einzeln == SAMMEL and len({_stamm(bilder[i]) for i in g}) == 1:
                ziele[gi] = SAMMEL
            else:
                ziele[gi] = f"{nummer:04d}"
                neu.append(ziele[gi])
                nummer += 1
    return ziele, neu


def gruppen_plan(bilder, schwelle, serie_sek, serie_schwelle, einzeln, start):
    """Plan der Neu-Gruppierung (ohne Pfad- und Zeitangaben, siehe plan_schreiben)."""
    n = len(bilder)
    uf = gruppieren(bilder, schwelle, serie_sek, serie_schwelle)
    gruppen, fest = [], []
    for g in _komponenten(uf, n):
        if any(vergleichbar(bilder[i]) for i in g):
            g.sort(key=lambda i: (bilder[i].t_sort, bilder[i].pfad))
            gruppen.append(g)
        else:
            fest += g  # nicht vergleichbar: bleibt, wo es ist
    gruppen.sort(key=lambda g: (bilder[g[0]].t_sort, bilder[g[0]].pfad))
    ziele, neu = ordner_zuteilen(bilder, gruppen, einzeln, start)
    if neu and int(neu[-1]) > MAX_ORDNER:
        raise ValueError(f"{zahl(len(neu))} neue Ordner nötig, ab {start:04d} frei sind nur "
                         f"{zahl(max(MAX_ORDNER - start + 1, 0))}. Möglich: EINZELN=0000 oder höhere Werte.")
    umzuege, ziel_von, zusammen = [], {}, []
    for gi, g in enumerate(gruppen):
        quellen = sorted({bilder[i].anker for i in g}, key=ordner_folge)
        for i in g:
            ziel_von[i] = ziele[gi]
            if bilder[i].anker != ziele[gi]:
                umzuege.append([_rel(bilder[i]), ziele[gi]])
        if len([q for q in quellen if q != SAMMEL]) >= 2:
            zusammen.append({"ziel": ziele[gi], "aus": quellen, "bilder": len(g)})
    nach = defaultdict(set)
    for i, z in ziel_von.items():
        if bilder[i].anker != SAMMEL:
            nach[bilder[i].anker].add(z)
    geteilt = [{"ordner": o, "nach": sorted(z, key=ordner_folge)}
               for o, z in sorted(nach.items(), key=lambda oz: ordner_folge(oz[0])) if len(z) > 1]
    zusammen.sort(key=lambda z: (-z["bilder"], ordner_folge(z["ziel"])))
    einheiten = [len({_stamm(bilder[i]) for i in g}) for g in gruppen]
    return {
        "parameter": {"SCHWELLE": schwelle, "SERIE_SEK": serie_sek, "SERIE_SCHWELLE": serie_schwelle,
                      "EINZELN": einzeln},
        "bilder": n, "vergleichbar": sum(1 for d in bilder if vergleichbar(d)),
        "nicht_lesbar": sum(1 for d in bilder if not d.ok), "fest": len(fest),
        "gruppen": sum(1 for k in einheiten if k > 1), "einzeln": sum(1 for k in einheiten if k == 1),
        "ordner_vorher": len({d.anker for d in bilder}),
        "ordner_nachher": len(set(ziel_von.values()) | {bilder[i].anker for i in fest}),
        "bewegt": len(umzuege), "aus_sammel": sum(1 for i, z in ziel_von.items()
                                                  if bilder[i].anker == SAMMEL and z != SAMMEL),
        "n_zusammen": len(zusammen), "zusammen": zusammen[:BEISPIELE],
        "n_geteilt": len(geteilt), "geteilt": geteilt[:BEISPIELE],
        "neue_ordner": neu, "umzuege": umzuege,
    }


def plan_text(plan):
    """Zusammenfassung des Plans in Zeilen für das Terminal (und das Protokoll in bestof)."""
    p = plan["parameter"]
    zeilen = [f"Neu-Gruppierung mit SCHWELLE {p['SCHWELLE']}, SERIE_SEK {p['SERIE_SEK']:g}, "
              f"SERIE_SCHWELLE {p['SERIE_SCHWELLE']}, EINZELN {p['EINZELN']}:",
              f"Bilder:   {zahl(plan['bilder'])} in {zahl(plan['ordner_vorher'])} Ordnern"
              + (f" – {zahl(plan['fest'])} einfarbig oder unlesbar, {'bleibt' if plan['fest'] == 1 else 'bleiben'}, "
                 f"wo {'es ist' if plan['fest'] == 1 else 'sie sind'}" if plan["fest"] else ""),
              f"Danach:   {zahl(plan['ordner_nachher'])} Ordner · {zahl(plan['gruppen'])} Gruppen mit mehreren "
              f"Bildern · {zahl(plan['einzeln'])} Einzelbilder"]
    if not plan["bewegt"]:
        zeilen.append("Umzug:    keiner – das Archiv ist schon so gruppiert.")
        return zeilen
    n_neu = len(plan["neue_ordner"])
    zeilen.append(f"Umzug:    {zahl(plan['bewegt'])} {'Bild' if plan['bewegt'] == 1 else 'Bilder'} · "
                  f"{zahl(plan['n_zusammen'])} {'Gruppe' if plan['n_zusammen'] == 1 else 'Gruppen'} aus mehreren Ordnern"
                  f" · {zahl(plan['n_geteilt'])} Ordner geteilt"
                  + (f" · {'1 neuer Ordner' if n_neu == 1 else zahl(n_neu) + ' neue Ordner'} ab {plan['neue_ordner'][0]}"
                     if n_neu else "")
                  + (f" · {zahl(plan['aus_sammel'])} aus {SAMMEL} zugeordnet" if plan["aus_sammel"] else ""))
    for z in plan["zusammen"][:5]:
        zeilen.append(f"  zusammen: {' + '.join(z['aus'])} → {z['ziel']} ({zahl(z['bilder'])} Bilder)")
    for g in plan["geteilt"][:5]:
        zeilen.append(f"  geteilt:  {g['ordner']} → {', '.join(g['nach'])}")
    return zeilen


# ---- Analyse einer Auswahl

def _engpass(w):
    """Kleinste Schranke t, bei der alle Knoten über Kanten ≤ t verbunden sind – die größte Kante im minimalen
    Spannbaum (Prim auf der dichten Matrix w, inf = keine Kante) – und das Knotenpaar dazu; None ohne Verbindung."""
    m = len(w)
    drin = np.zeros(m, bool)
    drin[0] = True
    best, von = w[0].copy(), np.zeros(m, np.int64)
    groesste, paar = 0.0, None
    for _ in range(m - 1):
        kand = np.where(drin, np.inf, best)
        k = int(kand.argmin())
        wert = float(kand[k])
        if not math.isfinite(wert):
            return None
        if paar is None or wert > groesste:
            groesste, paar = wert, (int(von[k]), k)
        drin[k] = True
        besser = w[k] < best
        best = np.where(besser, w[k], best)
        von = np.where(besser, k, von)
    return groesste, paar


def _knoten(bilder):
    """Knoten je Bild für die Ordnersicht: der Ordner; Bilder im Sammelordner 0000 je ein eigener Knoten."""
    namen, nummer, knoten = [], {}, []
    for d in bilder:
        schluessel = d.anker if d.anker != SAMMEL else _rel(d)
        if schluessel not in nummer:
            nummer[schluessel] = len(namen)
            namen.append(d.anker)
        knoten.append(nummer[schluessel])
    return knoten, namen


def _ordner_cluster(bilder, uf, knoten, n_knoten):
    """Ordner verbinden, deren vergleichbare Bilder in derselben Gruppe liegen. Rückgabe: Cluster je Knoten."""
    k_uf, erster = UnionFind(n_knoten), {}
    for i, d in enumerate(bilder):
        if not vergleichbar(d):
            continue
        r = uf.finde(i)
        if r in erster:
            k_uf.vereinige(erster[r], knoten[i])
        else:
            erster[r] = knoten[i]
    return [k_uf.finde(x) for x in range(n_knoten)]


def _folgen(basis, neu, auswahl, namen):
    """Was ein Vorschlag im Archiv ändert, verglichen mit den jetzigen Werten: welche Ordner an die Auswahl
    angehängt würden (mit) und welche anderen Ordner zusammenkämen (zusammen = Zahl der Zusammenlegungen)."""
    je = defaultdict(lambda: (set(), set()))
    for x, c in enumerate(neu):
        je[c][0].add(basis[x])
        je[c][1].add(x)
    eigene = {neu[x] for x in auswahl}
    basis_auswahl = {basis[x] for x in auswahl}
    mit = sorted({namen[x] for c in eigene for x in je[c][1] if x not in auswahl and basis[x] not in basis_auswahl},
                 key=ordner_folge)
    zusammen, beispiele = 0, []
    for c, (bs, xs) in je.items():
        if c in eigene or len(bs) < 2:
            continue
        zusammen += len(bs) - 1
        beispiele.append(sorted({namen[x] for x in xs}, key=ordner_folge))
    beispiele.sort(key=lambda b: (-len(b), [ordner_folge(o) for o in b]))
    return {"mit": mit[:20], "n_mit": len(mit), "zusammen": zusammen, "beispiele": beispiele[:5]}


def analyse(bilder, auswahl, schwelle, serie_sek, serie_schwelle):
    """Welche Werte hätten die Bilder der Ordner in auswahl automatisch in eine Gruppe gebracht? Siehe Modulhilfe."""
    auswahl = sorted(set(auswahl), key=ordner_folge)
    jetzt = {"SCHWELLE": schwelle, "SERIE_SEK": serie_sek, "SERIE_SCHWELLE": serie_schwelle}
    sel = [i for i, d in enumerate(bilder) if d.anker in auswahl]
    teil = [i for i in sel if vergleichbar(bilder[i])]
    nicht = [_rel(bilder[i]) for i in sel if not vergleichbar(bilder[i])]
    ergebnis = {"ordner": auswahl, "bilder": len(sel), "vergleichbar": len(teil), "n_nicht": len(nicht),
                "nicht": nicht[:10], "jetzt": jetzt, "teile": len(teil), "vorschlaege": [],
                "archiv": {"bilder": len(bilder), "ordner": len({d.anker for d in bilder})}}
    if len(teil) < 2:
        ergebnis["teile"] = len(teil)
        return ergebnis
    if len(teil) > MAX_AUSWAHL:
        raise ValueError(f"Zu viele Bilder für die Analyse ({zahl(len(teil))}, höchstens {zahl(MAX_AUSWAHL)}).")
    m = len(teil)
    unter = [bilder[i] for i in teil]
    ph = np.array([d.res[0] for d in unter], dtype=np.uint64)
    dh = np.array([d.res[1] for d in unter], dtype=np.uint64)
    abst = (_popcount(ph[:, None] ^ ph[None, :]).astype(np.int32) + _popcount(dh[:, None] ^ dh[None, :]))
    serie = serien_kanten(unter, math.inf, 128)  # alle Kandidaten im Fenster: (k, l, Sekunden, Abstand)
    staemme = stamm_kanten(unter)

    def matrix(bild_gewicht, serie_gewicht):
        w = bild_gewicht(abst).astype(np.float32)
        for k, l, dt, ab in serie:
            g = serie_gewicht(dt, ab)
            if g is not None and g < w[k, l]:
                w[k, l] = w[l, k] = g
        for k, l in staemme:
            w[k, l] = w[l, k] = 0
        return w

    def nur_bis(s):
        return lambda a: np.where(a <= s, 0.0, np.inf)

    w0 = matrix(nur_bis(schwelle), lambda dt, ab: 0.0 if dt <= serie_sek and ab <= serie_schwelle else None)
    uf = UnionFind(m)
    for k, l in zip(*np.nonzero(w0 == 0)):
        uf.vereinige(int(k), int(l))
    ergebnis["teile"] = len({uf.finde(k) for k in range(m)})
    if ergebnis["teile"] == 1:
        return ergebnis
    rechnung = [
        ("SCHWELLE", matrix(lambda a: a, lambda dt, ab: 0.0 if dt <= serie_sek and ab <= serie_schwelle else None)),
        ("SERIE_SEK", matrix(nur_bis(schwelle), lambda dt, ab: float(dt) if ab <= serie_schwelle else None)),
        ("SERIE_SCHWELLE", matrix(nur_bis(schwelle), lambda dt, ab: float(ab) if dt <= serie_sek else None)),
    ]
    # Serien überhaupt möglich (ohne Grenzen für Zeit und Abstand)? Sonst andere Kamera, ohne Zeit, zu weit weg
    serie_moeglich = _engpass(matrix(nur_bis(schwelle), lambda dt, ab: 0.0)) is not None
    gruende = {"SCHWELLE": "nicht verbindbar",
               "SERIE_SCHWELLE": "nur zusammen mit längerem SERIE_SEK" if serie_moeglich else "",
               "SERIE_SEK": "nur zusammen mit höherem SERIE_SCHWELLE" if serie_moeglich else ""}
    vorschlaege = {}
    for name, w in rechnung:
        e = _engpass(w)
        if e is None:
            ergebnis["vorschlaege"].append({"name": name, "wert": None, "grund": gruende[name] or (
                "keine Serie: andere Kamera, ohne Aufnahmezeit oder zu viele Bilder dazwischen")})
            continue
        wert, (k, l) = e
        if name == "SERIE_SEK":
            wert = math.ceil(wert * 10) / 10
            if wert < e[0]:
                wert += 0.1
            wert = round(wert, 1)
        else:
            wert = int(round(wert))
        a, b = sorted((_rel(unter[k]), _rel(unter[l])), key=lambda r: (ordner_folge(r.partition("/")[0]), r))
        vorschlaege[name] = wert
        rk, rl = unter[k].res, unter[l].res
        mit_zeit = rk[5] and rk[5] == rl[5] and rk[3] is not None and rl[3] is not None  # gleiche Kamera, mit Zeit
        ergebnis["vorschlaege"].append({"name": name, "wert": wert, "paar": [a, b], "abstand": int(abst[k, l]),
                                        "sekunden": round(abs(rk[3] - rl[3]), 1) if mit_zeit else None})
    # Folgen im ganzen Archiv: Ordner-Cluster mit jetzigen Werten und mit jedem Vorschlag
    n = len(bilder)
    s_a = vorschlaege.get("SCHWELLE")
    rechne_a = s_a is not None and s_a <= FOLGEN_BIS
    u0 = UnionFind(n)
    for i, j in stamm_kanten(bilder):
        u0.vereinige(i, j)
    ua = _kopie(u0) if rechne_a else None
    bild_kanten(bilder, [(schwelle, u0)] + ([(s_a, ua)] if rechne_a else []), "Vergleich im Archiv")
    sek_max = max(serie_sek, vorschlaege.get("SERIE_SEK") or 0)
    ss_max = max(serie_schwelle, vorschlaege.get("SERIE_SCHWELLE") or 0)
    alle_serien = serien_kanten(bilder, sek_max, ss_max)

    def mit_serien(basis, sek, ss):
        uf = _kopie(basis)
        for i, j, dt, ab in alle_serien:
            if dt <= sek and ab <= ss:
                uf.vereinige(i, j)
        return uf

    knoten, namen = _knoten(bilder)
    auswahl_knoten = {knoten[i] for i in sel}
    jetzt_uf = mit_serien(u0, serie_sek, serie_schwelle)
    basis = _ordner_cluster(bilder, jetzt_uf, knoten, len(namen))
    eigene = {basis[x] for x in auswahl_knoten}
    ergebnis["verbunden_jetzt"] = sorted({namen[x] for x in range(len(namen))
                                          if basis[x] in eigene and x not in auswahl_knoten}, key=ordner_folge)[:20]
    ergebnis["schon_global"] = len({jetzt_uf.finde(i) for i in teil}) == 1
    for v in ergebnis["vorschlaege"]:
        if v["wert"] is None:
            continue
        if v["name"] == "SCHWELLE":
            if not rechne_a:
                v["folgen"] = {"zu_hoch": True}
                continue
            uf = mit_serien(ua, serie_sek, serie_schwelle)
        elif v["name"] == "SERIE_SCHWELLE":
            uf = mit_serien(u0, serie_sek, v["wert"])
        else:
            uf = mit_serien(u0, v["wert"], serie_schwelle)
        v["folgen"] = _folgen(basis, _ordner_cluster(bilder, uf, knoten, len(namen)), auswahl_knoten, namen)
    return ergebnis


def _zahlwert(name, wert):
    return f"{wert:g}".replace(".", ",") if name == "SERIE_SEK" else str(wert)


def analyse_text(erg):
    """Ergebnis der Analyse in Zeilen für das Terminal."""
    j = erg["jetzt"]
    zeilen = [f"Analyse von {', '.join(erg['ordner'])}: {zahl(erg['bilder'])} Bilder, "
              f"{zahl(erg['vergleichbar'])} vergleichbar"
              + (f" – {zahl(erg['n_nicht'])} einfarbig oder unlesbar, die ordnet fotosort nie automatisch zu"
                 if erg["n_nicht"] else "")]
    werte = f"SCHWELLE {j['SCHWELLE']}, SERIE_SEK {_zahlwert('SERIE_SEK', j['SERIE_SEK'])}, " \
            f"SERIE_SCHWELLE {j['SERIE_SCHWELLE']}"
    if erg["vergleichbar"] < 2:
        zeilen.append("Zu wenig vergleichbare Bilder für eine Analyse.")
        return zeilen
    if erg["teile"] == 1:
        zeilen.append(f"Mit den jetzigen Werten ({werte}) wären sie schon eine Gruppe. fotosort legt beim Import "
                      f"aber bestehende Ordner nie zusammen – Zusammenfassen oder Neu-Gruppieren erledigt das.")
        return zeilen
    zeilen.append(f"Mit den jetzigen Werten ({werte}): {erg['teile']} getrennte Teile.")
    if erg.get("schon_global"):
        zeilen.append("Über andere Bilder im Archiv hängen sie schon jetzt zusammen.")
    zeilen.append("Eine dieser Änderungen hätte genügt:")
    for v in erg["vorschlaege"]:
        if v["wert"] is None:
            zeilen.append(f"  {v['name']}: – ({v['grund']})")
            continue
        einheit = " s" if v["name"] == "SERIE_SEK" else ""
        zeile = f"  {v['name']} = {_zahlwert(v['name'], v['wert'])}{einheit}   engste Stelle: {v['paar'][0]} ↔ " \
                f"{v['paar'][1]} (Abstand {v['abstand']}" + \
                (f", {_zahlwert('SERIE_SEK', v['sekunden'])} s" if v.get("sekunden") is not None else "") + ")"
        zeilen.append(zeile)
        f = v.get("folgen") or {}
        if f.get("zu_hoch"):
            zeilen.append("      Folgen: so hoch, dass sehr viele unähnliche Fotos zusammenkämen.")
        elif f:
            teile = []
            if f["n_mit"]:
                teile.append(f"käme mit dazu: {', '.join(f['mit'][:6])}" + (" …" if f["n_mit"] > 6 else ""))
            teile.append(("außerdem 1 weitere Zusammenlegung im Archiv" if f["zusammen"] == 1 else
                          f"außerdem {zahl(f['zusammen'])} weitere Zusammenlegungen im Archiv") if f["zusammen"]
                         else "sonst keine Zusammenlegungen im Archiv")
            if f["beispiele"]:
                teile.append("z. B. " + "; ".join(" + ".join(b[:4]) + (" …" if len(b) > 4 else "")
                                                  for b in f["beispiele"][:3]))
            zeilen.append("      Folgen: " + ", ".join(teile))
    return zeilen


# ---- Ähnliche Fotos zu einem Foto

def aehnliche(bilder, bezug, anzahl=150, bis=24):
    """Die Bilder, die bezug am ähnlichsten sind: pHash+dHash-Abstand ≤ bis, nach Abstand sortiert, höchstens anzahl.
    Ohne bezug selbst und seine Aufnahme (gleicher Ordner und Namensstamm, z. B. die NEF zum JPG) und ohne NEF, zu der
    es im selben Ordner ein JPG/PNG gibt (bestof zeigt das JPG). Rückgabe: [(Datei, Abstand, Sekunden oder None)] –
    Sekunden nur bei gleicher Kamera und bekannter Aufnahmezeit."""
    if not vergleichbar(bezug):
        return []
    eigen, echt = _stamm(bezug), os.path.realpath(bezug.pfad)
    gezeigt = {_stamm(d) for d in bilder if os.path.splitext(d.pfad)[1].lower() in (".jpg", ".jpeg", ".png")}
    kand = [d for d in bilder if vergleichbar(d) and _stamm(d) != eigen and os.path.realpath(d.pfad) != echt
            and not (os.path.splitext(d.pfad)[1].lower() == ".nef" and _stamm(d) in gezeigt)]
    if not kand:
        return []
    ph = np.array([d.res[0] for d in kand], dtype=np.uint64)
    dh = np.array([d.res[1] for d in kand], dtype=np.uint64)
    abstand = (_popcount(ph ^ np.uint64(bezug.res[0])).astype(np.int32)
               + _popcount(dh ^ np.uint64(bezug.res[1])).astype(np.int32))
    treffer, rb = [], bezug.res
    for k in np.argsort(abstand, kind="stable")[:anzahl].tolist():
        a = int(abstand[k])
        if a > bis:
            break
        r = kand[k].res
        sek = abs(r[3] - rb[3]) if r[5] and r[5] == rb[5] and r[3] is not None and rb[3] is not None else None
        treffer.append((kand[k], a, sek))
    return treffer


def aehnlich_main(args, jobs, cache_pfad):
    """MODUS=aehnlich AUSGABE BILD: die ähnlichsten Fotos im Archiv zu BILD (auch eine Fassung in „verbessert“)."""
    if len(args) != 2:
        sys.exit("Aufruf: MODUS=aehnlich python fotosort.py AUSGABE BILD   (BILD z. B. 0004/IMG_0001.JPG)")
    ausgabe = os.path.abspath(args[0])
    pfad = os.path.abspath(args[1] if os.path.isabs(args[1]) else os.path.join(ausgabe, args[1]))
    rel = os.path.relpath(pfad, ausgabe)
    teile = rel.split(os.sep)
    if not os.path.isdir(ausgabe) or rel.startswith("..") or len(teile) < 2 or not ist_ordner(teile[0]) \
            or not os.path.isfile(pfad) or os.path.splitext(pfad)[1].lower() not in BILD_EXT:
        sys.exit(f"Fehler: {args[1]} ist kein Bild in einem Ordner 0000–99999 von {ausgabe}.")
    anzahl = max(1, _env("AEHNLICH_ANZAHL", 150, int))
    bis = min(128, max(0, _env("AEHNLICH_BIS", 24, int)))
    info(f"fotosort {VERSION} · Modus aehnlich · {rel}")
    bilder = suche_archiv(ausgabe)
    echt = os.path.realpath(pfad)
    bezug = next((d for d in bilder if os.path.realpath(d.pfad) == echt), None)
    alle = bilder if bezug else bilder + [Datei(pfad, os.stat(pfad), anker=teile[0])]
    bezug = bezug or alle[-1]
    info(f"Gefunden: {zahl(len(bilder))} Bilder in {zahl(len({d.anker for d in bilder}))} Ordnern")
    cache = Cache(cache_pfad)
    atexit.register(cache.schliessen)
    try:
        analysieren(alle, cache, jobs)
    except KeyboardInterrupt:
        cache.schliessen()
        sys.exit("\nAbgebrochen während der Analyse. Bisherige Ergebnisse sind im Cache.")
    cache.schliessen()
    grund = "" if vergleichbar(bezug) else ("nicht lesbar" if not bezug.ok else "einfarbig – lässt sich nicht vergleichen")
    treffer = aehnliche(bilder, bezug, anzahl, bis)
    info(f"Ähnlich zu {rel.replace(os.sep, '/')}: {zahl(len(treffer))} Fotos mit Abstand bis {bis}"
         + (f" – {grund}" if grund else ""))
    for d, a, sek in treffer[:10]:
        info(f"  {a:3d}  {_rel(d)}" + (f"  (gleiche Kamera, {sek:g} s)" if sek is not None else ""))
    json_zeile({"aehnlich": {"bezug": rel.replace(os.sep, "/"), "bilder": len(bilder), "bis": bis, "grund": grund,
                             "treffer": [[_rel(d), a, None if sek is None else round(sek, 1)] for d, a, sek in treffer]}})
    return 0


# ---- Kommandozeile

def neu_main(modus, args, schwelle, serie_sek, serie_schwelle, einzeln, jobs, cache_pfad):
    if modus == "gruppen" and len(args) != 1:
        sys.exit("Aufruf: MODUS=gruppen python fotosort.py AUSGABE")
    if modus == "analyse" and len(args) < 3:
        sys.exit("Aufruf: MODUS=analyse python fotosort.py AUSGABE ORDNER ORDNER …   (z. B. 0004 0005 0006)")
    ausgabe = os.path.abspath(args[0])
    if not os.path.isdir(ausgabe):
        sys.exit(f"Fehler: {ausgabe} existiert nicht.")
    auswahl = []
    for o in args[1:]:
        name = os.path.basename(o.rstrip("/\\"))
        if not ist_ordner(name) or name == SAMMEL or not os.path.isdir(os.path.join(ausgabe, name)):
            sys.exit(f"Fehler: {o} ist kein Ordner 0001–99999 in {ausgabe}.")
        auswahl.append(name)
    info(f"fotosort {VERSION} · Modus {modus} · Archiv {ausgabe}")
    bilder = suche_archiv(ausgabe)
    info(f"Gefunden: {zahl(len(bilder))} Bilder in {zahl(len({d.anker for d in bilder}))} Ordnern")
    cache = Cache(cache_pfad)
    atexit.register(cache.schliessen)
    try:
        treffer = analysieren(bilder, cache, jobs)
    except KeyboardInterrupt:
        cache.schliessen()
        sys.exit("\nAbgebrochen während der Analyse. Bisherige Ergebnisse sind im Cache.")
    cache.schliessen()
    info(f"Analyse:  aus Cache {zahl(treffer)}, neu gelesen {zahl(len(bilder) - treffer)}")
    try:
        if modus == "analyse":
            erg = analyse(bilder, auswahl, schwelle, serie_sek, serie_schwelle)
            for z in analyse_text(erg):
                info(z)
            json_zeile({"analyse": erg})
            return 0
        hoch = max([int(d.anker) for d in bilder] + [int(e.name) for e in os.scandir(ausgabe)
                                                     if ist_ordner(e.name) and e.is_dir()] + [0])
        plan = gruppen_plan(bilder, schwelle, serie_sek, serie_schwelle, einzeln, hoch + 1)
    except KeyboardInterrupt:
        sys.exit("\nAbgebrochen.")
    except ValueError as fehler:
        sys.exit(f"Abbruch: {fehler}")
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan.update(version=1, fotosort=VERSION, zeit=stempel, ausgabe=ausgabe)
    ziel = os.environ.get("PLAN", "").strip() or os.path.join(ausgabe, f"fotosort_gruppen_{stempel}.json")
    tmp = ziel + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=0)
    os.replace(tmp, ziel)
    for z in plan_text(plan):
        info(z)
    info(f"Plan:     {ziel}")
    if not JSON_FORTSCHRITT:
        info("Nichts verschoben. Ausführen lässt sich der Plan in bestof.py (Einstellungen → Neu gruppieren) – "
             "dort wandern Sterne, Alben, Jahr und Gesichter mit, und Rückgängig ist möglich.")
    json_zeile({"plan": ziel})
    return 0
