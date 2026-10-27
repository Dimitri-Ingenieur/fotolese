"""fotolese.web.lernen – aus bestätigten/korrigierten Gesichtern Schwelle und Abstand lernen.

Schreibt die gelernten Werte in bestof.conf (konfig.KONFIG) und sortiert eindeutige
Fehlzuordnungen um. Der Lerner-Thread stößt das im Hintergrund an.
"""
import json
import threading
import time
import traceback

import numpy as np

from fotolese.web import konfig


def _lernlog(db, art, gid, von=None, zu=None, aehnlich=None, abstand=None):
    """Protokoll Ihrer Labels: korrektur (automatisch falsch zugeordnet), label, bestaetigt, entfernt, umsortiert."""
    db.execute("INSERT INTO lernlog VALUES(?,?,?,?,?,?,?)",
               (time.strftime("%Y-%m-%d %H:%M:%S"), art, gid, von, zu, aehnlich, abstand))


def _fehler_aehnlichkeit(db, pid, v, name):
    """Wie ähnlich war ein falsch zugeordnetes Gesicht seiner Gruppe (ohne sich selbst) – und um wie viel
    ähnlicher als der nächsten anderen benannten Person? Beides braucht das Lernen."""
    z = db.execute("SELECT summe, anzahl FROM person WHERE id=?", (pid,)).fetchone()
    if not z or z[1] < 2:
        return None, None
    rest = np.frombuffer(z[0], np.float32) - v
    laenge = float(np.linalg.norm(rest))
    if laenge <= 1e-6:
        return None, None
    falsch = float(rest @ v) / laenge
    andere = []
    for summe, n in db.execute("SELECT summe, name FROM person WHERE name IS NOT NULL AND anzahl > 0 "
                               "AND ignoriert = 0").fetchall():
        s_vec = np.frombuffer(summe, np.float32)
        l2 = float(np.linalg.norm(s_vec))
        if n.casefold() != name.casefold() and l2 > 0:
            andere.append(float(s_vec @ v) / l2)
    return falsch, (falsch - max(andere)) if andere else None


def offene_korrekturen(app):
    if not app.index:
        return 0
    z = app.index.einer("SELECT COUNT(*) FROM lernlog WHERE art='korrektur' AND zeit > "
                        "COALESCE((SELECT v FROM meta WHERE k='lernen_zeit'), '')")
    return z[0] if z else 0


def _kosten(T, M, neg_a, neg_d, pos_a, pos_o):
    """Bewertet Schwelle T und Abstand M an Ihren Labels: Fehlzuordnungen zählen dreifach, verpasste einfach.
    neg: korrigierte Fehlzuordnungen (Ähnlichkeit zur falschen Gruppe, Vorsprung vor der nächsten Person),
    pos: bestätigte Gesichter (Ähnlichkeit zur eigenen Person, beste andere Person)."""
    falsch = int(np.sum((neg_a >= T) & (neg_d >= M)))
    richtig = (pos_a >= T) & (pos_a - pos_o >= M)
    daneben = (pos_o >= T) & (pos_o - pos_a >= M)
    falsch += int(np.sum(daneben))
    verpasst = int(np.sum(~richtig & ~daneben))
    return 3 * falsch + verpasst, falsch, verpasst


def _zahl(x):
    return f"{x:.2f}".replace(".", ",")


def lern_text(st):
    if st.get("kalibriert"):
        if (st["T"], st["M"]) != (st["T_vorher"], st["M_vorher"]):
            teil = (f"Schwelle {_zahl(st['T_vorher'])} → {_zahl(st['T'])}, "
                    f"Abstand {_zahl(st['M_vorher'])} → {_zahl(st['M'])}")
        else:
            teil = f"Schwelle {_zahl(st['T'])} und Abstand {_zahl(st['M'])} passen"
        teil += (f" (aus {st['korrekturen']} Korrekturen und {st['labels']} bestätigten Gesichtern; "
                 f"Fehlzuordnungen darin {st['fehler_vorher']} → {st['fehler_nachher']}, "
                 f"verpasst {st['verpasst_vorher']} → {st['verpasst_nachher']})")
    else:
        teil = (f"Schwelle bleibt {_zahl(st['T'])} – zum Einstellen braucht es mindestens 3 Korrekturen und "
                f"10 bestätigte Gesichter (jetzt {st['korrekturen']} und {st['labels']})")
    return f"Gelernt: {teil}; {st['umsortiert']} Gesichter umsortiert."


def lernen(app, anlass="automatisch"):
    """Lernen aus Ihren Labels.
    1. Schwelle und Abstand so wählen, dass Ihre korrigierten Fehlzuordnungen möglichst nicht wieder passieren,
       ohne bestätigte Gesichter zu verlieren (Gitter, Schritt je Runde begrenzt) -> bestof.conf.
    2. Automatisch zugeordnete Gesichter, die eindeutig besser zu einer anderen benannten Person passen,
       dorthin verschieben. Vorbild jeder Gruppe sind Ihre bestätigten Gesichter (ab 3), sonst alle.
    Von Ihnen gesetzte Zuordnungen bleiben unangetastet."""
    if not (app.index and app.indexer):
        return {"meldung": "Ohne Index gibt es nichts zu lernen."}
    T0, M0 = app.person_schwelle, app.abstand
    with app.index.lock:
        db = app.index.db
        personen = {pid: (name, ign) for pid, name, ign in db.execute("SELECT id, name, ignoriert FROM person")}
        zeilen = [z for z in db.execute("SELECT id, person, emb, manuell FROM gesicht WHERE person IS NOT NULL "
                                        "AND emb IS NOT NULL").fetchall() if z[1] in personen]
        neg = np.array(db.execute("SELECT aehnlich, COALESCE(abstand, 9) FROM lernlog WHERE art='korrektur' "
                                  "AND aehnlich IS NOT NULL ORDER BY zeit DESC LIMIT 2000").fetchall(),
                       dtype=float).reshape(-1, 2)
        if not zeilen:
            return {"meldung": "Noch keine Gesichter im Index."}
        gruppen = sorted({z[1] for z in zeilen})
        nummer = {p: i for i, p in enumerate(gruppen)}
        g = np.array([nummer[z[1]] for z in zeilen])
        E = np.stack([np.frombuffer(z[2], np.float32) for z in zeilen]).astype(np.float64)
        von_hand = np.array([bool(z[3]) for z in zeilen])
        k = len(gruppen)
        alle = np.zeros((k, E.shape[1]))
        np.add.at(alle, g, E)
        labels = np.zeros_like(alle)
        np.add.at(labels, g[von_hand], E[von_hand])
        mit_labels = np.bincount(g[von_hand], minlength=k) >= 3
        P = np.where(mit_labels[:, None], labels, alle)
        drin = np.where(mit_labels[g], von_hand, True)  # steckt das Gesicht im Vorbild seiner Gruppe?
        schl = [(personen[p][0] or "").casefold() for p in gruppen]
        spalten = np.array([i for i in range(k) if schl[i] and not personen[gruppen[i]][1]], dtype=int)
        namen_u = sorted({schl[i] for i in spalten})
        if len(namen_u) < 2:
            return {"meldung": "Zum Lernen braucht es mindestens zwei benannte Personen."}
        Pn = P[spalten]
        laenge = np.linalg.norm(Pn, axis=1)
        roh = E @ Pn.T
        S = np.where(laenge[None, :] > 0, roh / np.where(laenge > 0, laenge, 1)[None, :], -1.0)
        spalte_von = np.full(k, -1)
        spalte_von[spalten] = np.arange(len(spalten))
        z_i = np.where((spalte_von[g] >= 0) & drin)[0]
        c = spalte_von[g[z_i]]
        nenner = np.sqrt(np.maximum(laenge[c] ** 2 - 2 * roh[z_i, c] + 1, 0))
        S[z_i, c] = np.where(nenner > 1e-6, (roh[z_i, c] - 1) / np.maximum(nenner, 1e-6), -1.0)
        name_von_spalte = np.array([namen_u.index(schl[i]) for i in spalten])
        Mx = np.stack([S[:, name_von_spalte == u].max(axis=1) for u in range(len(namen_u))], axis=1)
        eigen_u = np.array([namen_u.index(schl[i]) if schl[i] in namen_u else -1 for i in g])
        # 1. Schwelle und Abstand
        pos = np.where(von_hand & (eigen_u >= 0))[0]
        pos_a = Mx[pos, eigen_u[pos]]
        andere = Mx[pos].copy()
        andere[np.arange(len(pos)), eigen_u[pos]] = -1.0
        pos_o = andere.max(axis=1) if len(pos) else np.zeros(0)
        neg_a, neg_d = neg[:, 0], neg[:, 1]
        kalibriert = len(neg) >= 3 and len(pos) >= 10
        T1, M1 = T0, M0
        vorher = _kosten(T0, M0, neg_a, neg_d, pos_a, pos_o)
        if kalibriert:
            beste = min((_kosten(T, M, neg_a, neg_d, pos_a, pos_o)[0], abs(T - T0) + abs(M - M0), T, M)
                        for T in np.round(np.arange(0.30, 0.7001, 0.01), 2)
                        for M in np.round(np.arange(0.0, 0.2001, 0.01), 2))
            T1 = round(float(np.clip(T0 + np.clip(beste[2] - T0, -0.08, 0.08), 0.30, 0.70)), 2)
            M1 = round(float(np.clip(M0 + np.clip(beste[3] - M0, -0.05, 0.05), 0.0, 0.20)), 2)
        nachher = _kosten(T1, M1, neg_a, neg_d, pos_a, pos_o)
        # 2. umsortieren
        M_um = max(M1, 0.05)
        auto = np.where(~von_hand)[0]
        bewegen = []
        if len(auto):
            ziel_u = Mx[auto].argmax(axis=1)
            s_b = Mx[auto, ziel_u]
            zweit = Mx[auto].copy()
            zweit[np.arange(len(auto)), ziel_u] = -1.0
            s_2 = zweit.max(axis=1)
            eigen = P[g[auto]]
            weg = np.where(drin[auto][:, None], E[auto], 0.0)
            l_e = np.linalg.norm(eigen - weg, axis=1)
            s_cur = np.where(l_e > 1e-6, (np.einsum("ij,ij->i", eigen, E[auto]) - np.where(drin[auto], 1.0, 0.0))
                             / np.maximum(l_e, 1e-6), -1.0)
            for j, r in enumerate(auto):
                if eigen_u[r] == ziel_u[j] or not (s_b[j] >= T1 and s_b[j] - s_2[j] >= M_um
                                                    and s_b[j] - s_cur[j] >= M_um):
                    continue
                kandidaten = np.where(name_von_spalte == ziel_u[j])[0]
                beste_spalte = kandidaten[int(np.argmax(S[r, kandidaten]))]
                bewegen.append((float(s_b[j] - max(s_2[j], s_cur[j])), int(r), gruppen[spalten[beste_spalte]]))
        bewegen.sort(reverse=True)
        plus, minus, umsortiert = [], [], 0
        for _, r, ziel in bewegen[:max(20, len(auto) // 4)]:
            gid, alt, emb = zeilen[r][0], zeilen[r][1], zeilen[r][2]
            if db.execute("UPDATE gesicht SET person=? WHERE id=? AND manuell=0 AND person=?",
                          (ziel, gid, alt)).rowcount:
                plus.append((ziel, emb))
                minus.append((alt, emb))
                umsortiert += 1
                _lernlog(db, "umsortiert", gid, personen[alt][0], personen[ziel][0])
        if plus:
            app.indexer._personen_aendern(db, plus=plus, minus=minus)
        jetzt = time.strftime("%Y-%m-%d %H:%M:%S")
        stand = {"zeit": jetzt, "anlass": anlass, "T_vorher": T0, "M_vorher": M0, "T": T1, "M": M1,
                 "korrekturen": int(len(neg)), "labels": int(len(pos)), "fehler_vorher": vorher[1],
                 "verpasst_vorher": vorher[2], "fehler_nachher": nachher[1], "verpasst_nachher": nachher[2],
                 "umsortiert": umsortiert, "kalibriert": bool(kalibriert)}
        db.execute("INSERT OR REPLACE INTO meta VALUES('lernen_zeit', ?)", (jetzt,))
        db.execute("INSERT OR REPLACE INTO meta VALUES('lernen_stand', ?)", (json.dumps(stand),))
        db.commit()
    if konfig.QUELLE.get("PERSON_SCHWELLE") != "Umgebung":
        app.person_schwelle = T1
    if konfig.QUELLE.get("ABSTAND") != "Umgebung":
        app.abstand = M1
    stand["meldung"] = lern_text(stand)
    if konfig.KONFIG is not None:
        notiz = f"{jetzt[:16]} – {stand['meldung'][9:]}"
        konfig.KONFIG.setzen({"PERSON_SCHWELLE": f"{T1:.2f}", "ABSTAND": f"{M1:.2f}"} if kalibriert else {}, notiz)
    return stand


def lern_zeile(app):
    """Kurzfassung für die Seite „Personen“."""
    if not app.lernen:
        return "Automatisches Lernen ist aus (LERNEN = 0 in bestof.conf)."
    offen = offene_korrekturen(app)
    z = app.index.einer("SELECT v FROM meta WHERE k='lernen_stand'")
    text = f"Lernen: Schwelle {_zahl(app.person_schwelle)}, Abstand {_zahl(app.abstand)}."
    if z:
        st = json.loads(z[0])
        text += f" Zuletzt am {st['zeit'][8:10]}.{st['zeit'][5:7]}. um {st['zeit'][11:16]}: {st['umsortiert']} umsortiert."
    return text + (f" Seitdem {offen} {'Korrektur' if offen == 1 else 'Korrekturen'} – neu gelernt wird ab "
                   f"{app.lernen_ab}.")


class Lerner(threading.Thread):
    """Lernt im Hintergrund, sobald LERNEN_AB Fehlzuordnungen korrigiert sind."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.ereignis = threading.Event()

    def anstossen(self):
        self.ereignis.set()

    def run(self):
        while True:
            self.ereignis.wait()
            time.sleep(5)  # weitere Korrekturen abwarten, dann einmal lernen
            self.ereignis.clear()
            try:
                if self.app.lernen and offene_korrekturen(self.app) >= self.app.lernen_ab:
                    print(f"Personen: {lernen(self.app, 'automatisch')['meldung']}", flush=True)
            except Exception:
                traceback.print_exc()
