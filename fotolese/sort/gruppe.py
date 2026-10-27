"""fotolese.sort.gruppe – gleiche Inhalte (SHA-256), ähnliche Bilder gruppieren, Anker im Bestand.

_popcount zählt gesetzte Bits (Hamming-Abstand der Hashes), vektorisiert über numpy.
"""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from fotolese.gemein import sha256
from fotolese.sort.konst import FLACH_STD
from fotolese.sort.bericht import Fortschritt


if hasattr(np, "bitwise_count"):
    def _popcount(x):
        return np.bitwise_count(x)
else:  # numpy < 2.0
    _LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

    def _popcount(x):
        return _LUT[x.view(np.uint8)].reshape(x.shape + (8,)).sum(axis=-1, dtype=np.uint8)


def duplikate_finden(bilder, bestand, cache, jobs):
    """Eingabebilder, deren Inhalt (SHA-256) es schon im Bestand oder weiter vorn in der Eingabe gibt.
    Geprüft werden nur Dateien gleicher Größe – alle anderen können nicht gleich sein.
    Rückgabe: {Eingabepfad: Pfad der gleichen Datei}."""
    bestand_nach_groesse = defaultdict(list)
    for d in bestand:
        bestand_nach_groesse[d.groesse].append(d)
    anzahl_ein = Counter(d.groesse for d in bilder)
    ein = [d for d in bilder if d.groesse in bestand_nach_groesse or anzahl_ein[d.groesse] > 1]
    alt = [b for g in sorted({d.groesse for d in ein}) for b in bestand_nach_groesse.get(g, [])]
    pruefen = ein + alt
    if not pruefen:
        return {}
    shas = {}
    offen = []
    for d in pruefen:
        s = cache.sha_holen(d.pfad, d.groesse, d.mtime)
        if s:
            shas[d.pfad] = s
        else:
            offen.append(d)
    fort = Fortschritt("Prüfsummen", len(offen))
    if offen:
        with ThreadPoolExecutor(max(1, min(jobs, 8))) as ex:
            zukunft = {ex.submit(sha256, d.pfad): d for d in offen}
            for k, f in enumerate(as_completed(zukunft), 1):
                d = zukunft[f]
                try:
                    shas[d.pfad] = f.result()
                    cache.sha_ablegen(d.pfad, d.groesse, d.mtime, shas[d.pfad])
                except OSError:
                    pass
                fort.melden(k)
        fort.melden(len(offen), ende=True)
    bekannt = {}
    for b in alt:
        if b.pfad in shas:
            bekannt.setdefault(shas[b.pfad], b.pfad)
    doppelt = {}
    for d in sorted(ein, key=lambda d: d.pfad):
        s = shas.get(d.pfad)
        if s is None:
            continue
        if s in bekannt:
            doppelt[d.pfad] = bekannt[s]
        else:
            bekannt[s] = d.pfad
    return doppelt


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))
        self.g = [1] * n

    def finde(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def vereinige(self, a, b):
        a, b = self.finde(a), self.finde(b)
        if a == b:
            return False
        if self.g[a] < self.g[b]:
            a, b = b, a
        self.p[b] = a
        self.g[a] += self.g[b]
        return True


def gruppiere(bilder, schwelle, serie_sek, serie_schwelle):
    n = len(bilder)
    uf = UnionFind(n)
    idx = [i for i, d in enumerate(bilder) if d.ok and d.res[2] >= FLACH_STD]
    m = len(idx)
    n_bild = n_serie = 0
    if m > 1:
        ph = np.array([bilder[i].res[0] for i in idx], dtype=np.uint64)
        dh = np.array([bilder[i].res[1] for i in idx], dtype=np.uint64)
        block = max(32, min(4096, 16_000_000 // m))
        for a in range(0, m, block):
            b = min(a + block, m)
            abstand = (_popcount(ph[a:b, None] ^ ph[None, a:]).astype(np.uint16)
                       + _popcount(dh[a:b, None] ^ dh[None, a:]))
            zi, sp = np.nonzero(abstand <= schwelle)
            zi = zi + a
            sp = sp + a
            wahl = sp > zi
            for i, j in zip(zi[wahl].tolist(), sp[wahl].tolist()):
                if uf.vereinige(idx[i], idx[j]):
                    n_bild += 1
    # Serienbilder: gleiche Kamera, zeitlich benachbart, sichtbar ähnlich
    nach_kamera = defaultdict(list)
    for i, d in enumerate(bilder):
        if d.ok and d.res[5] and d.res[3] is not None and d.res[2] >= FLACH_STD:
            nach_kamera[d.res[5]].append(i)
    for liste in nach_kamera.values():
        liste.sort(key=lambda i: (bilder[i].res[3], bilder[i].pfad))
        for k in range(1, len(liste)):
            rk = bilder[liste[k]].res
            j = k - 1
            while j >= 0 and k - j <= 60:
                rj = bilder[liste[j]].res
                if rk[3] - rj[3] > serie_sek:
                    break
                if (rk[0] ^ rj[0]).bit_count() + (rk[1] ^ rj[1]).bit_count() <= serie_schwelle:
                    if uf.vereinige(liste[k], liste[j]):
                        n_serie += 1
                j -= 1
    gruppen = defaultdict(list)
    for i, d in enumerate(bilder):
        if d.ok:
            gruppen[uf.finde(i)].append(d)
    ergebnis = []
    for g in gruppen.values():
        g.sort(key=lambda d: (d.t_sort, d.pfad))
        ergebnis.append(g)
    ergebnis.sort(key=lambda g: (g[0].t_sort, g[0].pfad))
    return ergebnis, n_bild, n_serie


def finde_anker(gruppen, bestand, schwelle, serie_sek, serie_schwelle):
    """Für jede neue Gruppe den bestehenden Ordner mit dem ähnlichsten Bild suchen
    (Bildvergleich <= SCHWELLE oder Serie: gleiche Kamera, <= SERIE_SEK, <= SERIE_SCHWELLE).
    Bestandsordner werden dabei nie verändert oder zusammengelegt.
    Rückgabe: Liste parallel zu gruppen mit Ordnername oder None."""
    anker = [None] * len(gruppen)
    alt = [d for d in bestand if d.ok and d.res[2] >= FLACH_STD]
    neu = [(gi, d) for gi, g in enumerate(gruppen) for d in g if d.res[2] >= FLACH_STD]
    if not alt or not neu:
        return anker
    bestes = {}  # Position in neu -> (abstand, ordner, pfad)

    def merken(pos, abstand, d_alt):
        kandidat = (abstand, d_alt.anker, d_alt.pfad)
        if pos not in bestes or kandidat < bestes[pos]:
            bestes[pos] = kandidat

    ph_a = np.array([d.res[0] for d in alt], dtype=np.uint64)
    dh_a = np.array([d.res[1] for d in alt], dtype=np.uint64)
    ph_n = np.array([d.res[0] for _, d in neu], dtype=np.uint64)
    dh_n = np.array([d.res[1] for _, d in neu], dtype=np.uint64)
    block = max(32, min(4096, 16_000_000 // len(alt)))
    for a in range(0, len(neu), block):
        b = min(a + block, len(neu))
        abstand = (_popcount(ph_n[a:b, None] ^ ph_a[None, :]).astype(np.uint16)
                   + _popcount(dh_n[a:b, None] ^ dh_a[None, :]))
        arg = abstand.argmin(axis=1)
        mins = abstand[np.arange(b - a), arg]
        for k in np.nonzero(mins <= schwelle)[0].tolist():
            merken(a + k, int(mins[k]), alt[int(arg[k])])
    # Serie: neues Bild wenige Sekunden vor/nach einem Bestandsbild derselben Kamera
    pro_kamera = defaultdict(list)
    for d in alt:
        if d.res[5] and d.res[3] is not None:
            pro_kamera[d.res[5]].append(d)
    zeiten = {}
    for kamera, liste in pro_kamera.items():
        liste.sort(key=lambda d: (d.res[3], d.pfad))
        zeiten[kamera] = [d.res[3] for d in liste]
    for pos, (_, d) in enumerate(neu):
        kamera, t = d.res[5], d.res[3]
        if not kamera or t is None or kamera not in pro_kamera:
            continue
        ts = zeiten[kamera]
        fenster = pro_kamera[kamera][bisect_left(ts, t - serie_sek):bisect_right(ts, t + serie_sek)]
        for d_alt in sorted(fenster, key=lambda x: abs(x.res[3] - t))[:60]:
            abstand = (d.res[0] ^ d_alt.res[0]).bit_count() + (d.res[1] ^ d_alt.res[1]).bit_count()
            if abstand <= serie_schwelle:
                merken(pos, abstand, d_alt)
    je_gruppe = {}
    for pos, kandidat in bestes.items():
        gi = neu[pos][0]
        if gi not in je_gruppe or kandidat < je_gruppe[gi]:
            je_gruppe[gi] = kandidat
    for gi, kandidat in je_gruppe.items():
        anker[gi] = kandidat[1]
    return anker
