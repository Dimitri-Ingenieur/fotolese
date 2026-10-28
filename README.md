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
- Alben: jedes Foto in beliebig vielen Alben, sichtbar unter dem Foto, im Filter nutzbar ([mehr](#alben))
- Gesichtserkennung auf der Grafikkarte, wenn eine nutzbar ist – NVIDIA, AMD, Intel, Apple ([GPU](#gpu))
- Seite „Import“: Ordner wählen – bestof.py startet fotosort.py, das ihn ins Archiv kopiert ([mehr](#import-im-browser))
- doppelte Dateien im Archiv → Papierkorb `Sortiert/.duplikate`
- Auflösung und Dateigröße unter jedem Foto

## Installation

Conda:

```bash
git clone https://github.com/Dimitri-Ingenieur/fotolese.git
cd fotolese
conda env create -f environment.yml        # nur CPU
conda env create -f environment-gpu.yml    # oder: mit GPU (NVIDIA, Apple Silicon)
conda activate fotosort
```

Oder pip: `python -m pip install -r requirements.txt`, mit GPU `requirements-gpu.txt`.
Eine vorhandene Umgebung bekommt die GPU-Pakete mit `conda env update -f environment-gpu.yml`.
AMD, Intel und DirectML unter Windows: siehe [GPU](#gpu).

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
   bevorzugt die in BestOf ausgewählte, dann eine mit Ihren Labels (Namen, Jahr, Alben), dann die
   ohne Laufindex. Überzählige kommen in den Papierkorb `Sortiert/.duplikate/<Zeit>/` (mit `liste.csv`),
   ihre Alben gehen auf die behaltene Datei über.
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

### Alben

Ein Foto kann in beliebig vielen Alben stehen, z. B. in „Urlaub 2023“ und „Familie“. Unter jedem Foto
stehen seine Alben; ein Klick darauf zeigt alle Fotos des Albums.

1. **Album anlegen** – auf der Seite „Alben“ oder mit „Neues Album“ über den Fotos.
2. **Fotos markieren** – über den Fotos eines Ordners oder Filterergebnisses „Fotos markieren für
   Album …“ wählen, dann ＋ unter den Fotos anklicken (mit Umschalt alle bis zum zuletzt angeklickten)
   oder in der Lupe <kbd>A</kbd> drücken. „Alle hinzufügen“ nimmt den ganzen Ordner bzw. alle Treffer
   des Filters. Das gewählte Album bleibt beim Wechsel in andere Ordner gewählt.
3. **Einzeln zuordnen** – ohne gewähltes Album öffnet ＋ unter einem Foto (oder „Alben“ in der Lupe) die
   Liste aller Alben zum Ankreuzen; dort lässt sich auch gleich ein neues anlegen.

Filtern: `Album Urlaub 2023` oder nur `Urlaub 2023`; mehrere Alben mit Komma zeigen die Fotos aus
einem davon, kombiniert mit anderem gilt beides (`Urlaub 2023, Anna`). `ohne Album` zeigt, was noch
nirgends einsortiert ist. Auf der Seite „Alben“ lassen sich Alben umbenennen und löschen – die Fotos
bleiben dabei im Archiv. Die Alben stehen im Index (`Sortiert/.bestof-index.sqlite3`), so wie Namen und
Korrekturen: Wer ihn löscht, verliert sie.

## GPU

Die Gesichtserkennung in bestof.py (Index, Gegenprobe, Klick ins Gesicht) rechnet auf der
Grafikkarte, wenn eine nutzbar ist – ohne Einstellung. Beim Start prüft bestof.py die vorhandenen
Möglichkeiten und nimmt die erste, die dieselben Ergebnisse wie die CPU liefert und schneller ist;
sonst bleibt alles auf der CPU. Gesichter und Merkmale sind auf GPU und CPU gleich, ein Wechsel löst
keine neue Gesichtssuche aus.

Ob die GPU rechnet, steht in der Kopfzeile jeder Seite, z. B. „Gesichtserkennung auf der GPU – CUDA
(ONNX Runtime), NVIDIA GeForce RTX 3060“, mit Messwerten auf der Seite „Personen“ und im Terminal.
Rechnet die CPU, steht dort der Grund, etwa „keine GPU gefunden“ oder „libcublasLt.so.13 fehlt“ samt
dem passenden Installationsbefehl.

Dafür braucht es ein zusätzliches Paket in der Umgebung von bestof.py. Für NVIDIA und Apple Silicon
bringen es `environment-gpu.yml` und `requirements-gpu.txt` mit (siehe [Installation](#installation));
sonst eines aus der Tabelle nachinstallieren – nur eines der `onnxruntime`-Pakete, sie schließen sich
gegenseitig aus:

| Grafikkarte | Paket | Hinweis |
|---|---|---|
| NVIDIA | `python -m pip install "onnxruntime-gpu[cuda,cudnn]"` | bringt CUDA 13 und cuDNN mit |
| AMD (Linux) | `python -m pip install onnxruntime-rocm` | braucht eine ROCm-Installation |
| Intel (Linux, Windows) | `python -m pip install onnxruntime-openvino` | Intel-Grafik oder Arc |
| jede unter Windows | `python -m pip install onnxruntime-directml` | |
| Apple Silicon | `python -m pip install onnxruntime` | CoreML |
| Treiber mit OpenCL | – | kann OpenCV schon; genutzt nur, wenn schneller als die CPU |

NVIDIA: `nvidia-smi` zeigt oben rechts, welche CUDA-Version der Treiber kann. Steht dort 12.x, die
Fassung für CUDA 12 nehmen: `python -m pip install "onnxruntime-gpu[cuda,cudnn]<1.27"` – in den beiden
GPU-Dateien dafür hinter `[cuda,cudnn]` noch `<1.27` einfügen.

Einstellungen (in `bestof.conf` oder als Umgebungsvariable):
- `GPU = auto` (Standard) nimmt die GPU, wenn sie nutzbar ist; `GPU = 0` rechnet nur auf der CPU;
  `GPU = cuda` (oder `rocm`, `directml`, `coreml`, `openvino`, `opencv-cuda`, `opencl`) nimmt genau
  dieses, auch wenn es nicht schneller ist.
- `GPU_JOBS = 2`: so viele Index-Prozesse rechnen auf der GPU, die übrigen weiter auf der CPU –
  zusammen sind sie am schnellsten. Jeder GPU-Prozess belegt eigenen GPU-Speicher; bei einer großen
  Karte lohnt ein höherer Wert.

Auf der CPU bleiben das Lesen der Fotos, die Vorschaubilder und fotosort.py – dort geht die Zeit ins
Lesen und Dekodieren der Dateien, nicht ins Rechnen. TensorRT und MIGraphX nutzt bestof.py nicht: Sie
übersetzen das Netz für jede neue Bildgröße neu.

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
│       ├── alben.py         Alben: anlegen, Fotos zuordnen, für Filter und Oberfläche
│       ├── index.py         SQLite-Index und Hintergrund-Indexer
│       ├── gesichter.py     Gesichtserkennung (YuNet/SFace) im Prozess-Pool
│       ├── gpu.py           Gesichtsmodelle auf der GPU: Auswahl, Prüfung, Rückfall auf CPU
│       ├── suche.py         Suchbegriffe deuten: Jahr, Ort, Person, Ordner, Dateiname
│       ├── html.py          Seiten, CSS und JavaScript der Oberfläche
│       ├── server.py        HTTP-Handler und /api-Aktionen
│       ├── lernen.py        aus Korrekturen Schwelle und Abstand lernen
│       ├── importieren.py   Seite „Import“: startet fotosort.py, bereinigt Duplikate
│       └── cli.py           main() und Hilfetext (-h)
├── environment.yml          Conda-Umgebung (CPU)
├── environment-gpu.yml      Conda-Umgebung mit GPU (NVIDIA, Apple Silicon)
├── requirements.txt         Pakete für pip (CPU)
├── requirements-gpu.txt     Pakete für pip mit GPU (NVIDIA, Apple Silicon)
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
