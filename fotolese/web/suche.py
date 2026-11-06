"""fotolese.web.suche – Suchbegriffe deuten (Jahr, Monat, Ort, Person, Album, Ordner, Dateiname) und Bilder filtern."""
import re

from fotolese.web.konst import MONAT_NR, MONATE, ORDNER_MUSTER
from fotolese.web.konfig import km_zwischen, name_aus_id

ALLE_FOTOS = "Alle Fotos"  # Knopf neben „Filtern“: das ganze Archiv nach Datum
OHNE_ALBUM = "Ohne Album"  # Knopf daneben: Fotos, die noch in keinem Album sind


def suche_ausfuehren(app, text):
    """Begriffe mit Komma trennen. Gleiche Art = ODER (2022, 2023; Leipzig, Dresden; zwei Alben),
    verschiedene Arten = UND (2023, Juli, Leipzig), Personen immer UND (Anna, Ben = beide drauf).
    Alben mit „+“ verknüpft = in allen davon (Reisen + Paris). „Alle Fotos“ schränkt nichts ein."""
    jahre, monate, jahr_monat, ordner, orte, personen, texte, erklaerung = set(), set(), set(), set(), [], [], [], []
    namen, anzeige_name, sonder, alben = {}, {}, set(), {}
    album_gruppen = []  # je Gruppe {Album-IDs}: das Foto ist in allen; von mehreren Gruppen genügt eine
    if app.index:
        for pid, name in app.index.q("SELECT id, name FROM person"):
            if name:
                namen.setdefault(name.casefold(), set()).add(pid)
                anzeige_name[name.casefold()] = name
        alben = {name.casefold(): (aid, name) for aid, name in app.index.q("SELECT id, name FROM album")}

    def album_merken(aid, name, gesucht, gruppe):
        """Ein Album für sich ist eine eigene Gruppe (Komma: eines davon genügt), im „+“-Begriff kommt es in
        dessen Gruppe (alle müssen zutreffen). aid -1: Album gibt es nicht."""
        if gruppe is not None:
            gruppe.append((aid, name, gesucht, len(erklaerung)))  # Stelle für den Chip der Gruppe
            return
        album_gruppen.append({aid})
        erklaerung.append(f"Album {name}" if aid != -1 else f"Album „{gesucht}“ gibt es nicht")

    def deuten(t, nur_pruefen=False, gruppe=None):
        k = re.sub(r"\s+", " ", t.casefold())
        if k in ("alle fotos", "alle bilder", "alle", "alles"):
            if not nur_pruefen:
                erklaerung.append("alle Fotos")
            return True
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
            gesucht = re.sub(r"\s+", " ", m.group(1)).strip()
            if "+" in gesucht and gesucht.casefold() not in alben:
                return False  # „Album Reisen + Paris“: Verknüpfung, siehe unten
            if not nur_pruefen:
                aid, name = alben.get(gesucht.casefold(), (-1, None))  # -1: kein Treffer
                album_merken(aid, name, gesucht, gruppe)
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
        if ORDNER_MUSTER.fullmatch(k):
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
                album_merken(*alben[k], t, gruppe)
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

    def begriff(t, nur_pruefen=False, gruppe=None):
        """Ein Begriff – oder mehrere Wörter, die jedes für sich einer sind (Juli 2023). Rückgabe: erkannt?"""
        if deuten(t, nur_pruefen, gruppe):
            return True
        woerter = t.split()
        if len(woerter) > 1 and all(deuten(w, nur_pruefen=True) for w in woerter):
            if not nur_pruefen:
                for w in woerter:
                    deuten(w, gruppe=gruppe)
            return True
        return False

    for term in (t.strip() for t in re.split(r"[,;]", text)):
        if not term or begriff(term):
            continue
        teile = [t.strip() for t in term.split("+")]
        if len(teile) > 1 and all(teile) and all(begriff(t, nur_pruefen=True) for t in teile):
            gruppe = []  # „Reisen + Paris“: Fotos in allen diesen Alben; anderes (Anna, 2023) zählt wie mit Komma
            for t in teile:
                begriff(t, gruppe=gruppe)
            if gruppe:
                album_gruppen.append({aid for aid, *_ in gruppe})
                da = list(dict.fromkeys(name for aid, name, *_ in gruppe if aid != -1))
                chips = [("Alben " if len(da) > 1 else "Album ") + " + ".join(da)] if da else []
                chips += [f"Album „{gesucht}“ gibt es nicht" for aid, _, gesucht, _ in gruppe if aid == -1]
                erklaerung[gruppe[0][3]:gruppe[0][3]] = chips  # dort, wo das erste Album im Begriff steht
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
    if album_gruppen:  # Gruppe: in allen ihren Alben (je Album und Foto höchstens eine Zeile); eine Gruppe genügt
        bedingungen = []
        for g in album_gruppen:
            ids = sorted(g)
            bedingungen.append(f"pfad IN (SELECT pfad FROM album_bild WHERE album IN ({','.join('?' * len(ids))}) "
                               "GROUP BY pfad HAVING COUNT(*) = ?)")
            args += ids + [len(ids)]
        sql.append("AND (" + " OR ".join(bedingungen) + ")")
    if "ohne_album" in sonder:
        sql.append("AND pfad NOT IN (SELECT pfad FROM album_bild)")
    sql.append("ORDER BY sortzeit IS NULL, sortzeit, length(ordner), ordner, datei")  # 9999 vor 10000
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
