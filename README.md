# Fotolese

Fotos sortieren, Doppelte entfernen, die besten auswählen – lokal, im Browser.
Wie bei der Weinlese: aus jeder Serie die besten Bilder auslesen.

*English: Sorts photos into folders of similar shots and bursts, removes exact duplicates
and lets you pick the best shots in a local web UI (German UI).*

## Was es macht

Zwei Programme, die zusammenarbeiten: fotosort.py sortiert Fotos in ein Archiv, in bestof.py sehen
Sie es im Browser durch und wählen die besten aus. bestof.py kann fotosort.py über die Seite „Import“
auch selbst aufrufen – dann müssen Sie fotosort.py nicht von Hand starten.

**fotosort.py** – Kommandozeile (Paket `fotolese/sort/`)
- legt ähnliche Fotos und Serienbilder in nummerierte Ordner `0001`–`9999`
- ergänzt passende bestehende Ordner; gleiche Dateinamen bekommen einen Laufindex (`IMG_0001_1.JPG`)
- erzeugt zu jeder NEF-Datei ein JPG
- übernimmt inhaltsgleiche Dateien (SHA-256) nur einmal
- schreibt ein Protokoll; `MODUS=undo` macht einen Lauf rückgängig

**bestof.py** – Weboberfläche im Browser (Paket `fotolese/web/`)
- je Ordner bis zu 3 beste Fotos auswählen → Kopie in `Sortiert/BestOf`
- Index mit Datum, Ort und Gesichtern; Filter wie `2023, Leipzig, Anna`
- Gesichter benennen; lernt aus Ihren Korrekturen (`bestof.conf`)
- Seite „Import“: Ordner wählen – bestof.py startet fotosort.py, das ihn ins Archiv kopiert ([mehr](#import-im-browser))
- doppelte Dateien im Archiv → Papierkorb `Sortiert/.duplikate`
- Auflösung und Dateigröße unter jedem Foto

## Installation

Conda:

```bash
git clone https://github.com/IHR-GITHUB-NAME/fotolese.git
cd fotolese
conda env create -f environment.yml
conda activate fotosort
```

Oder pip: `python -m pip install -r requirements.txt`

## Nutzung

**Weg 1 – Kommandozeile:** fotosort.py selbst aufrufen, danach mit bestof.py auswählen.

```bash
MODUS=test python fotosort.py EINGABE AUSGABE   # nur Plan, nichts wird bewegt
MODUS=copy python fotosort.py EINGABE AUSGABE   # kopieren, Quelle bleibt
python fotosort.py EINGABE AUSGABE              # verschieben (Standard)
python bestof.py AUSGABE                        # Browser öffnet http://127.0.0.1:8765
```

**Weg 2 – alles im Browser:** nur bestof.py starten und Fotos auf der Seite „Import“ holen;
bestof.py ruft fotosort.py dann selbst auf (siehe [Import im Browser](#import-im-browser)).

```bash
mkdir AUSGABE              # nur beim ersten Mal: leeres Archiv anlegen
python bestof.py AUSGABE   # dann Seite „Import“ → Ordner wählen → „In Sortiert kopieren“
```

Alle Einstellungen: `python fotosort.py -h` und `python bestof.py -h`.
bestof.py legt beim ersten Start `bestof.conf` neben sich an (im Projektordner, nicht in `fotolese/web/`).

### Import im Browser

Die Seite „Import“ ist eine Oberfläche für fotosort.py: bestof.py sortiert nicht selbst, sondern
ruft fotosort.py auf und räumt danach auf.

1. **Ordner wählen.** Die Seite zeigt die Ordner des Rechners, auf dem bestof.py läuft, mit
   Schnellzugriff auf persönlichen Ordner, Bilder und eingehängte Laufwerke (SD-Karte, USB-Platte).
   Hochgeladen wird nichts – auch nicht, wenn die Seite auf Tablet oder Handy offen ist.
2. **„In Sortiert kopieren“.** bestof.py startet `fotosort.py QUELLE AUSGABE` als eigenen Prozess,
   immer mit `MODUS=copy` (die Quelle bleibt unverändert) und ohne Rückfrage. Fortschrittsbalken
   und Ausgabe von fotosort.py erscheinen im Browser.
3. **Duplikate bereinigen.** Danach behält das Archiv von jedem Inhalt (SHA-256) genau eine Datei:
   bevorzugt die in BestOf ausgewählte, dann eine mit Ihren Labels, dann die ohne Laufindex.
   Überzählige kommen in den Papierkorb `Sortiert/.duplikate/<Zeit>/` (mit `liste.csv`).
   „Papierkorb leeren“ löscht sie endgültig, „Jetzt prüfen“ bereinigt auch ohne Import.
4. **Einlesen.** Der Index liest die neuen Bilder sofort ein (Datum, Ort, Gesichter).

„Abbrechen“ stoppt fotosort.py sauber (ein gerade kopierter Ordner wird noch fertig); schon
Kopiertes bleibt im Archiv. „Import rückgängig“ ruft fotosort.py mit `MODUS=undo` auf und entfernt
die Kopien des letzten Imports. Das Protokoll liegt im Archiv; nach einem Neustart von
bestof.py geht das auch auf der Kommandozeile: `MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv`.

Voraussetzungen: `fotosort.py` liegt neben `bestof.py` (wie im Projektordner; an anderem Ort
`FOTOSORT` setzen). Die Seite ist nur freigegeben, wenn bestof.py ausschließlich am eigenen Rechner erreichbar ist
(`HOST=127.0.0.1`, Standard) oder ein `PASSWORT` gesetzt ist; `IMPORT=0` schaltet sie ganz ab.
`IMPORT_JOBS` legt fest, wie viele Prozesse fotosort.py beim Import nutzt (HDD/USB: z. B. 2–4).

## Aufbau

`fotosort.py` und `bestof.py` sind schlanke Starter. Die Funktionalität liegt im Paket
`fotolese/`, thematisch aufgeteilt in `sort` (fotosort) und `web` (bestof):

```text
fotolese/                    Projektordner
├── fotosort.py              Starter für die Kommandozeile → fotolese.sort.cli
├── bestof.py                Starter für die Weboberfläche → fotolese.web.cli
├── fotolese/                Python-Paket
│   ├── gemein.py            Helfer für beide: Einstellungen, SHA-256, Datum aus Dateiname
│   ├── sort/                fotosort: einsammeln, gruppieren, verschieben
│   │   ├── konst.py         Konstanten, Dateiendungen, optionales rawpy
│   │   ├── bericht.py       Zahlen- und Größenformate, Fortschritt (#FS-Zeilen für bestof)
│   │   ├── exif.py          Zeit, Orientierung und Kamera aus EXIF oder Dateiname
│   │   ├── bild.py          Wahrnehmungs-Hashes (pHash/dHash), Analyse im Prozess-Pool
│   │   ├── nef.py           NEF lesen, verlustfrei ein JPG daraus erzeugen
│   │   ├── cache.py         Analyse-Ergebnisse und Prüfsummen in SQLite
│   │   ├── suche.py         Eingabe und Bestand finden, Begleitdateien zuordnen
│   │   ├── gruppe.py        Duplikate (SHA-256), Gruppierung, passende Bestandsordner
│   │   ├── plan.py          Zielnamen mit Laufindex, Verschiebeplan
│   │   ├── lauf.py          verschieben, kopieren, verlinken; Protokoll; Rückgängig
│   │   └── cli.py           main() und Hilfetext (-h)
│   └── web/                 bestof: durchsehen, filtern, BestOf auswählen
│       ├── konst.py         Konstanten, Muster, Monatsnamen, Quellen der Modelle
│       ├── konfig.py        bestof.conf lesen und schreiben, Einstellungen, Textformate
│       ├── archiv.py        Zugriff auf den Sortiert-Ordner (Ordner, Bilder, NEF)
│       ├── bild.py          Vorschaubilder erzeugen und zwischenspeichern
│       ├── orte.py          GeoNames offline: GPS → nächster größerer Ort
│       ├── auswahl.py       BestOf-Auswahl je Ordner, Kopien in BestOf
│       ├── index.py         SQLite-Index und Hintergrund-Indexer
│       ├── gesichter.py     Gesichtserkennung (YuNet/SFace) im Prozess-Pool
│       ├── suche.py         Suchbegriffe deuten: Jahr, Ort, Person, Ordner, Dateiname
│       ├── html.py          Seiten, CSS und JavaScript der Oberfläche
│       ├── server.py        HTTP-Handler und /api-Aktionen
│       ├── lernen.py        aus Korrekturen Schwelle und Abstand lernen
│       ├── importieren.py   Seite „Import“: startet fotosort.py, bereinigt Duplikate
│       └── cli.py           main() und Hilfetext (-h)
├── environment.yml          Conda-Umgebung
├── requirements.txt         Pakete für pip
└── LICENSE
```

- Die Starter lassen sich aus jedem Ordner aufrufen (`python ~/fotolese/fotosort.py …`),
  müssen aber neben dem Ordner `fotolese/` liegen. Wer sie an einen anderen Ort kopiert,
  nimmt `fotolese/` mit – sonst `ModuleNotFoundError: No module named 'fotolese'`.
- `sort` und `web` importieren sich nicht gegenseitig; gemeinsamer Code liegt in `gemein.py`.
  Verbunden sind sie nur über den [Import im Browser](#import-im-browser): `web/importieren.py`
  startet `fotosort.py` mit demselben Python als Unterprozess (`MODUS=copy`, `DUPLIKATE=1`,
  `JOBS` aus `IMPORT_JOBS`, `JA=1`, `FORTSCHRITT_JSON=1`) und liest dessen Ausgabe mit:
  `#FS {json}`-Zeilen (aus `sort/bericht.py`) für den Fortschrittsbalken, die Zeile
  `Protokoll: …` für „Import rückgängig“.

## Datenschutz

- Alles läuft lokal. Fotos verlassen den Rechner nicht.
- Der Index `Sortiert/.bestof-index.sqlite3` enthält Gesichtsmerkmale (biometrische Daten).
  Geben Sie ihn nicht weiter.
- Die Weboberfläche ist im Standard nur am eigenen Rechner erreichbar (`HOST=127.0.0.1`).
  Für Tablet oder Handy im Heimnetz: `HOST=0.0.0.0` und immer `PASSWORT` setzen.

## Daten und Modelle von Dritten

Nicht Teil dieses Repositorys. bestof.py lädt sie beim ersten Start nach `~/.cache/fotosort`:

| Was | Quelle | Lizenz |
|---|---|---|
| Ortsdaten cities1000 | [GeoNames](https://www.geonames.org) | CC BY 4.0 |
| Gesichtserkennung YuNet | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | MIT |
| Gesichtsmerkmale SFace | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) | Apache-2.0 |

## Haftung

Benutzung auf eigene Gefahr. fotosort.py verschiebt im Standard (`MODUS=move`); der Import in
bestof.py kopiert nur.
Probieren Sie es zuerst mit `MODUS=test` oder an einer Kopie.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
