"""fotolese.web.suche – Suchbegriffe deuten (Jahr, Monat, Ort, Person, Album, Ordner, Dateiname) und Bilder filtern."""
import re

from fotolese.web.konst import MONAT_NR, MONATE
from fotolese.web.konfig import km_zwischen, name_aus_id


def suche_ausfuehren(app, text):
    """Begriffe mit Komma trennen. Gleiche Art = ODER (2022, 2023; Leipzig, Dresden; zwei Alben),
    verschiedene Arten = UND (2023, Juli, Leipzig), Personen immer UND (Anna, Ben = beide drauf)."""
    jahre, monate, jahr_monat, ordner, orte, personen, texte, erklaerung = set(), set(), set(), set(), [], [], [], []
    namen, anzeige_name, sonder, alben, album_ids = {}, {}, set(), {}, set()
    if app.index:
        for pid, name in app.index.q("SELECT id, name FROM person"):
            if name:
                namen.setdefault(name.casefold(), set()).add(pid)
                anzeige_name[name.casefold()] = name
        alben = {name.casefold(): (aid, name) for aid, name in app.index.q("SELECT id, name FROM album")}

    def deuten(t, nur_pruefen=False):
        k = re.sub(r"\s+", " ", t.casefold())
        if k in ("ohne jahr", "kein jahr", "jahr fehlt"):
            if not nur_pruefen:
                sonder.add("ohne_jahr")
                erklaerung.append("ohne Jahr")
            return True
        if k in ("jahr korrigiert", "jahr manuell", "jahr von hand"):
            if not nur_pruefen:
                sonder.add("korrigiert")
                erklaerung.append("Jahr von Hand gesetzt")
            return True
        if k in ("ohne album", "kein album"):
            if not nur_pruefen:
                sonder.add("ohne_album")
                erklaerung.append("ohne Album")
            return True
        m = re.fullmatch(r"album\s*:?\s*(.+)", t.strip(), re.IGNORECASE)
        if m and k not in alben:  # „Album Urlaub“, „Album: Urlaub“ – auch für Namen wie 2023 oder Leipzig
            if not nur_pruefen:
                gesucht = re.sub(r"\s+", " ", m.group(1)).strip()
                aid, name = alben.get(gesucht.casefold(), (-1, None))  # -1: kein Treffer
                album_ids.add(aid)
                erklaerung.append(f"Album {name}" if name else f"Album „{gesucht}“ gibt es nicht")
            return True
        m = re.fullmatch(r"((?:19|20)\d\d)-(\d{1,2})", k)
        if re.fullmatch(r"(19|20)\d\d", k):
            if not nur_pruefen:
                jahre.add(int(k))
                erklaerung.append(f"Jahr {k}")
            return True
        if m and 1 <= int(m.group(2)) <= 12:
            if not nur_pruefen:
                jahr_monat.add((int(m.group(1)), int(m.group(2))))
                erklaerung.append(f"{MONATE[int(m.group(2))]} {m.group(1)}")
            return True
        if k in MONAT_NR:
            if not nur_pruefen:
                monate.add(MONAT_NR[k])
                erklaerung.append(f"Monat {MONATE[MONAT_NR[k]]}")
            return True
        if re.fullmatch(r"\d{4}", k):
            if not nur_pruefen:
                ordner.add(k)
                erklaerung.append(f"Ordner {k}")
            return True
        m = re.fullmatch(r"person\s*(\d+)", k)
        if k in namen or m:
            if not nur_pruefen:
                personen.append((namen.get(k) or {int(m.group(1))}, t))
                erklaerung.append(f"Person {anzeige_name[k]}" if k in namen else f"Person {m.group(1)}")
            return True
        if k in alben:
            if not nur_pruefen:
                album_ids.add(alben[k][0])
                erklaerung.append(f"Album {alben[k][1]}")
            return True
        if app.indexer and app.indexer.orte.bereit:
            ort = app.indexer.orte.suchen(t)
            if ort:
                if not nur_pruefen:
                    orte.append(ort)
                    erklaerung.append(f"bei {t[:1].upper() + t[1:]} (bis {app.naehe_km:g} km)")
                return True
        if app.index and app.index.einer("SELECT 1 FROM bild WHERE ort = ? COLLATE NOCASE LIMIT 1", (t,)):
            if not nur_pruefen:
                orte.append({"name": t, "lat": None, "lon": None})
                erklaerung.append(f"Ort {t}")
            return True
        return False

    for term in (t.strip() for t in re.split(r"[,;]", text)):
        if not term:
            continue
        if deuten(term):
            continue
        teile = term.split()
        if len(teile) > 1 and all(deuten(t, nur_pruefen=True) for t in teile):
            for t in teile:
                deuten(t)
            continue
        texte.append(term.casefold())
        erklaerung.append(f"Dateiname enthält „{term}“")

    if not app.index:
        return [], erklaerung
    # bild_eff: von Hand gesetztes Jahr vor EXIF/Dateiname; der Monat gilt dann als unbekannt
    sql, args = ["SELECT ordner, datei, zeit, ort, ort_km, lat, lon FROM bild_eff WHERE 1=1"], []
    if jahre:  # gleiche Art ODER, verschiedene Arten UND: „2023, Juli“ = Juli 2023
        sql.append(f"AND jahr_eff IN ({','.join('?' * len(jahre))})")
        args += sorted(jahre)
    if monate:
        sql.append(f"AND monat_eff IN ({','.join('?' * len(monate))})")
        args += sorted(monate)
    if "ohne_jahr" in sonder:
        sql.append("AND jahr_eff IS NULL")
    if "korrigiert" in sonder:
        sql.append("AND jahr_man IS NOT NULL")
    if jahr_monat:
        sql.append("AND (" + " OR ".join("(jahr_eff=? AND monat_eff=?)" for _ in jahr_monat) + ")")
        for j, m in sorted(jahr_monat):
            args += [j, m]
    if ordner:
        sql.append(f"AND ordner IN ({','.join('?' * len(ordner))})")
        args += sorted(ordner)
    for ids, _ in personen:
        sql.append(f"AND pfad IN (SELECT pfad FROM gesicht WHERE person IN ({','.join('?' * len(ids))}))")
        args += sorted(ids)
    if album_ids:
        sql.append(f"AND pfad IN (SELECT pfad FROM album_bild WHERE album IN ({','.join('?' * len(album_ids))}))")
        args += sorted(album_ids)
    if "ohne_album" in sonder:
        sql.append("AND pfad NOT IN (SELECT pfad FROM album_bild)")
    sql.append("ORDER BY sortzeit IS NULL, sortzeit, ordner, datei")
    zeilen = app.index.q(" ".join(sql), args)
    if orte:
        def nahe(z):
            for o in orte:
                if o["lat"] is None:
                    if (z[3] or "").casefold() == o["name"].casefold():
                        return True
                elif z[5] is not None and km_zwischen(z[5], z[6], o["lat"], o["lon"]) <= app.naehe_km:
                    return True
            return False
        zeilen = [z for z in zeilen if nahe(z)]
    for t in texte:
        zeilen = [z for z in zeilen if t in name_aus_id(z[1]).casefold()]
    return zeilen, erklaerung
