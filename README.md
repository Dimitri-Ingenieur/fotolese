# Fotolese

Fotos sortieren, Doppelte entfernen, die besten auswählen – lokal, im Browser.
Wie bei der Weinlese: aus jeder Serie die besten Bilder auslesen.

*English: Sorts photos into folders of similar shots and bursts, removes exact duplicates
and lets you pick the best shots in a local web UI (German UI).*

## Was es macht

**fotosort.py** – Kommandozeile
- legt ähnliche Fotos und Serienbilder in nummerierte Ordner `0001`–`9999`
- ergänzt passende bestehende Ordner; gleiche Dateinamen bekommen einen Laufindex (`IMG_0001_1.JPG`)
- erzeugt zu jeder NEF-Datei ein JPG
- übernimmt inhaltsgleiche Dateien (SHA-256) nur einmal
- schreibt ein Protokoll; `MODUS=undo` macht einen Lauf rückgängig

**bestof.py** – Weboberfläche im Browser
- je Ordner bis zu 3 beste Fotos auswählen → Kopie in `Sortiert/BestOf`
- Index mit Datum, Ort und Gesichtern; Filter wie `2023, Leipzig, Anna`
- Gesichter benennen; lernt aus Ihren Korrekturen (`bestof.conf`)
- Seite „Import“: Ordner im Browser wählen, fotosort.py kopiert ihn ins Archiv
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

```bash
MODUS=test python fotosort.py EINGABE AUSGABE   # nur Plan, nichts wird bewegt
MODUS=copy python fotosort.py EINGABE AUSGABE   # kopieren, Quelle bleibt
python fotosort.py EINGABE AUSGABE              # verschieben (Standard)
python bestof.py AUSGABE                        # Browser öffnet http://127.0.0.1:8765
```

Alle Einstellungen: `python fotosort.py -h` und `python bestof.py -h`.
bestof.py legt beim ersten Start `bestof.conf` neben sich an.

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

Benutzung auf eigene Gefahr. fotosort.py verschiebt im Standard (`MODUS=move`).
Probieren Sie es zuerst mit `MODUS=test` oder an einer Kopie.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
