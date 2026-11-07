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
- legt ähnliche Fotos und Serienbilder in nummerierte Ordner `0001`–`99999` (bis `9999` vierstellig, ab
  `10000` fünfstellig – bestehende Ordner behalten ihren Namen)
- ergänzt passende bestehende Ordner; gleiche Dateinamen bekommen einen Laufindex (`IMG_0001_1.JPG`)
- erzeugt zu jeder NEF-Datei ein JPG
- übernimmt inhaltsgleiche Dateien (SHA-256) nur einmal
- schreibt ein Protokoll; `MODUS=undo` macht einen Lauf rückgängig
- plant eine Neu-Gruppierung des ganzen Archivs (`MODUS=gruppen`) und nennt die Ähnlichkeitswerte, mit denen
  bestimmte Ordner zusammengekommen wären (`MODUS=analyse`) – ausgeführt wird in bestof.py
- nennt zu einem Foto die ähnlichsten im Archiv, nach Ähnlichkeit sortiert (`MODUS=aehnlich`)

**bestof.py** – Weboberfläche im Browser (Paket `fotolese/web/`)
- je Ordner bis zu 3 beste Fotos mit Stern ☆ markieren → Kopie in `Sortiert/BestOf`
- Index mit Datum, Ort und Gesichtern; Filter wie `2023, Leipzig, Anna` ([mehr](#filter))
- Gesichter benennen; lernt aus Ihren Korrekturen (`bestof.conf`)
- Alben: jedes Foto in beliebig vielen Alben, sichtbar unter dem Foto, im Filter nutzbar ([mehr](#alben))
- „Alle Fotos“, „Ohne Album“ und Jahr per Klick: das Archiv durchgehen, Alben und Jahre schnell zuordnen
  ([mehr](#alle-fotos-und-jahr-per-klick))
- Ähnliche Fotos: „≈ Ähnliche“ in der Lupe zeigt die ähnlichsten Fotos im ganzen Archiv, nach Ähnlichkeit
  sortiert, jedes mit seinem Abstand; gefundene Fotos lassen sich zum Ausgangsfoto verschieben
  ([mehr](#ähnliche-fotos))
- Papierkorb: ein Klick schiebt ein Foto nach `Sortiert/Musor`, mit „Rückgängig“; endgültig gelöscht wird
  nur im Dateimanager ([mehr](#papierkorb))
- im Heimnetz erreichbar, z. B. `http://tigris:8765` vom Tablet; importieren nur am Rechner selbst
  ([mehr](#im-heimnetz))
- Bearbeiten in der Lupe: drehen, spiegeln, Helligkeit, Kontrast, Sättigung – gespeichert als neue Fassung
  `…_bearbeitet.png`, das Foto bleibt ([mehr](#bearbeiten))
- Verbessern und Kolorieren mit ComfyUI, zwei eigene Knöpfe in der Lupe: Fassungen kommen in den Unterordner
  `verbessert`, Vorher/Nachher-Schieber; koloriert wird das Original direkt oder eine verbesserte Fassung
  ([mehr](#verbessern-mit-comfyui))
- Ordner zusammenfassen (z. B. 0004, 0005, 0006 → 0004), Fotos, die nicht in einen Ordner gehören, in eine
  eigene Gruppe verschieben und das ganze Archiv mit neuen Ähnlichkeitswerten neu gruppieren – Sterne, Alben,
  Jahr, Gesichter und Fassungen wandern mit, „Rückgängig“ inklusive; dazu die Werte, mit denen fotosort die
  Ordner selbst zusammengelegt hätte ([mehr](#ordner-zusammenfassen-und-neu-gruppieren))
- Seite „Einstellungen“: Ähnlichkeit beim Import, Workflows (auch hochladen), Kolorieren, Anzeige, Personen
  ([mehr](#einstellungen))
- Gesichtserkennung auf der Grafikkarte, wenn eine nutzbar ist – NVIDIA, AMD, Intel, Apple ([GPU](#gpu))
- Seite „Import“: Ordner wählen – bestof.py startet fotosort.py, das ihn ins Archiv kopiert ([mehr](#import-im-browser))
- doppelte Dateien im Archiv → Papierkorb `Sortiert/Musor/Duplikate`
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
   und Ausgabe von fotosort.py erscheinen im Browser. Wahlweise vorher ein **Album** eintragen
   (vorhandenes oder neuer Name): Alle Fotos des Imports kommen hinein – auch die, die fotosort als
   schon im Archiv vorhanden übersprungen hat.
3. **Duplikate bereinigen.** Danach behält das Archiv von jedem Inhalt (SHA-256) genau eine Datei:
   bevorzugt die mit Stern (in BestOf), dann eine mit Ihren Labels (Namen, Jahr, Alben), dann die
   ohne Laufindex. Überzählige kommen in den Papierkorb `Sortiert/Musor/Duplikate/<Zeit>/` (mit
   `liste.csv`), ihre Alben gehen auf die behaltene Datei über. „Jetzt prüfen“ bereinigt auch ohne Import.
4. **Einlesen.** Der Index liest die neuen Bilder sofort ein (Datum, Ort, Gesichter).

„Abbrechen“ stoppt fotosort.py sauber (ein gerade kopierter Ordner wird noch fertig); schon
Kopiertes bleibt im Archiv. „Import rückgängig“ ruft fotosort.py mit `MODUS=undo` auf und entfernt
die Kopien des letzten Imports, dazu seine Album-Zuordnungen; ein eigens dafür angelegtes Album
verschwindet, wenn es danach leer ist. Das Protokoll liegt im Archiv; nach einem Neustart von
bestof.py geht das auch auf der Kommandozeile: `MODUS=undo python fotosort.py AUSGABE/fotosort_<zeit>.csv`.

Voraussetzungen: `fotosort.py` liegt neben `bestof.py` (wie im Projektordner; an anderem Ort
`FOTOSORT` setzen). Importieren geht nur an dem Rechner, auf dem bestof.py läuft – aus dem Heimnetz
ist die Seite gesperrt, weil die Ordnerwahl die Laufwerke dieses Rechners zeigt. `IMPORT=0` schaltet sie
ganz ab.
`IMPORT_JOBS` legt fest, wie viele Prozesse fotosort.py beim Import nutzt (HDD/USB: z. B. 2–4).

### Filter

Das Suchfeld oben auf jeder Seite filtert das ganze Archiv (dafür braucht es den Index, `INDEX = 1`,
Standard). Begriffe mit Komma trennen; die Chips unter dem Feld zeigen, wie bestof.py jeden Begriff
verstanden hat. Die Treffer stehen nach Datum, 240 je Seite, Fotos ohne Datum am Ende. Groß- und
Kleinschreibung spielt keine Rolle.

| Eingabe | zeigt |
|---|---|
| `2023` | Fotos aus 2023 – ein von Hand gesetztes Jahr zählt vor EXIF und Dateiname |
| `Juli`, auch `Jul`, `Mär`, `Okt` … | diesen Monat in jedem Jahr |
| `Juli 2023` oder `2023-07` | Juli 2023 |
| `ohne Jahr` | Fotos ohne Datum |
| `Jahr korrigiert` | Fotos, deren Jahr von Hand gesetzt ist |
| `Leipzig` | Fotos höchstens `NAEHE_KM` (Standard 15 km) von Leipzig – über die GPS-Daten |
| `Anna`, `Person 7` | Fotos mit dieser Person (Name oder Nummer einer unbenannten Gruppe) |
| `Urlaub 2023` oder `Album Urlaub 2023` | Fotos in diesem Album |
| `Reisen + Paris` | Fotos, die in beiden Alben sind (mit `+` beliebig viele Alben) |
| `ohne Album` | Fotos, die in keinem Album sind |
| `0012`, `12345` | Ordner 0012 bzw. 12345 |
| `Alle Fotos` | das ganze Archiv |
| anderer Text, z. B. `IMG_45` | Fotos, deren Dateiname diesen Text enthält |

Kombiniert wird so:
- **verschiedene Arten müssen alle zutreffen:** `2023, Leipzig, Anna` = aus 2023, bei Leipzig und mit Anna;
- **gleiche Art heißt „eines davon“:** `2022, 2023`, `Leipzig, Dresden` oder `Urlaub, Familie`;
- **Personen müssen alle auf dem Foto sein:** `Anna, Ben` zeigt nur Fotos mit beiden.
- **Alben mit `+` müssen alle zutreffen:** `Reisen + Paris` zeigt nur Fotos, die in beiden Alben sind –
  `Reisen, Paris` dagegen alle aus einem der beiden. Beides lässt sich kombinieren: `Reisen + Paris, Familie`
  = in Reisen und Paris oder in Familie; `Reisen + Paris, 2023` = in beiden Alben und aus 2023.

Mehrere Wörter ohne Komma gelten einzeln, wenn jedes für sich ein Begriff ist (`Juli 2023`); sonst zählt
der ganze Text – als Album, Person oder Ort, und wenn nichts davon passt, als Teil des Dateinamens.

Mit einem Klick: „Alle Fotos“ und „Ohne Album“ neben dem Suchfeld (siehe
[Alle Fotos und Jahr per Klick](#alle-fotos-und-jahr-per-klick)); ein Album unter einem Foto anklicken
zeigt alle Fotos darin. Auf der Ordner-Übersicht filtern „Alle“, „Ohne Stern“ und „Mit Stern“ ganze
Ordner, das Feld „Ordner“ öffnet einen Ordner über seine Nummer.

Gut zu wissen:
- Ist das Jahr eines Fotos von Hand gesetzt, gilt sein Monat als unbekannt – `Juli` findet es dann nicht.
- Ordnernummern von 1900 bis 2099 versteht der Filter als Jahr: `2005` zeigt das Jahr 2005. Solche Ordner
  öffnet das Feld „Ordner“ auf der Übersicht.
- Die Ortssuche im Umkreis braucht die Ortsdaten von GeoNames, die bestof.py beim ersten Start lädt. Ohne
  sie findet ein Ort nur Fotos, für die der Index genau diesen Ortsnamen kennt.

### Alben

Ein Foto kann in beliebig vielen Alben stehen, z. B. in „Urlaub 2023“ und „Familie“. Unter jedem Foto
stehen seine Alben; ein Klick darauf zeigt alle Fotos des Albums.

1. **Album anlegen** – auf der Seite „Alben“ oder mit „Neues Album“ über den Fotos. Beim Import geht es
   in einem Schritt: Feld „Album“ auf der Seite „Import“ ([mehr](#import-im-browser)).
2. **Fotos markieren** – über den Fotos eines Ordners oder Filterergebnisses „Fotos markieren für
   Album …“ wählen, dann ＋ unter den Fotos anklicken (mit Umschalt alle bis zum zuletzt angeklickten)
   oder in der Lupe <kbd>A</kbd> drücken. „Alle hinzufügen“ nimmt den ganzen Ordner bzw. alle Treffer
   des Filters. Das gewählte Album bleibt beim Wechsel in andere Ordner gewählt.
3. **Einzeln zuordnen** – ohne gewähltes Album öffnet ＋ unter einem Foto (oder „Alben“ in der Lupe) die
   Liste aller Alben zum Ankreuzen; dort lässt sich auch gleich ein neues anlegen.

[Filtern](#filter): `Album Urlaub 2023` oder nur `Urlaub 2023`; mehrere Alben mit Komma zeigen die Fotos
aus einem davon, kombiniert mit anderem gilt beides (`Urlaub 2023, Anna`). `ohne Album` (oder der Knopf
„Ohne Album“ neben „Filtern“) zeigt, was noch nirgends einsortiert ist. Auf der Seite „Alben“ lassen sich
Alben umbenennen und löschen – die Fotos bleiben dabei im Archiv. Die Alben stehen im Index
(`Sortiert/.bestof-index.sqlite3`), so wie Namen und Korrekturen: Wer ihn löscht, verliert sie.

### Alle Fotos und Jahr per Klick

„Alle Fotos“ neben „Filtern“ zeigt das ganze Archiv nach Datum, 240 Fotos je Seite, Fotos ohne Datum
am Ende. Darüber steht dieselbe Leiste wie bei jedem Filter: Album wählen und mit ＋ einordnen, so
lässt sich das Archiv Seite für Seite durchgehen. Nur die Fotos ohne Datum zeigt der Filter `ohne Jahr`.

„Ohne Album“ daneben zeigt nur die Fotos, die noch in keinem Album sind – ebenfalls nach Datum. Wer
eines einordnet, sieht es sofort blass werden, über den Fotos steht, wie viele hier noch fehlen. Nach
dem Neuladen bleiben nur die übrigen, so schrumpft die Liste, bis jedes Foto ein Album hat.

**Jahr per Klick:** rechts in der Leiste das Jahr eintippen, z. B. `1994`, dann „→ 1994“ unter den
Fotos anklicken; mit Umschalt bekommen alle Fotos bis zum zuletzt angeklickten das Jahr. Das geht in
jedem Ordner und Filterergebnis, auch in der Lupe. ✕ oder <kbd>Esc</kbd> im Jahresfeld der Leiste
beendet es. Wie beim Jahresfeld unter dem Foto gilt das Jahr vor EXIF und Dateiname (gelb = von Hand);
leeren + Enter im Feld unter dem Foto gibt wieder das Jahr aus der Datei.

### Ähnliche Fotos

In der Lupe sucht **≈ Ähnliche** zum gezeigten Foto die ähnlichsten im ganzen Archiv. Gerechnet wird wie
beim Import: fotosort.py kennt von jedem Foto zwei Wahrnehmungs-Fingerabdrücke (pHash und dHash, je 64 Bit),
der Abstand zählt die Bits, in denen sie sich unterscheiden – 0 heißt gleich, um 60 ganz verschieden. Die
Seite zeigt vorn das Ausgangsfoto, dahinter die Treffer nach Abstand sortiert, jeden mit Abstand und Wort:

| Abstand | Wort | meist |
|---|---|---|
| 0 | gleich | dieselbe Aufnahme, auch in anderer Größe |
| 1–8 | fast gleich | andere Kompression, leicht nachbearbeitete Kopie |
| bis `SCHWELLE` (20) | sehr ähnlich | beim Import kämen die Fotos in eine Gruppe – Abstand in Gelb |
| bis 36 | ähnlich | Serienbilder, dasselbe Motiv kurz danach |
| bis 48 | entfernt ähnlich | ähnlicher Bildaufbau, oft schon ein anderes Motiv |

Mit der Maus über dem Abstand stehen Einzelheiten, bei Fotos derselben Kamera auch, wie viele Sekunden
dazwischen liegen. Gezeigt werden höchstens 150 Fotos bis Abstand 48 (`AEHNLICH_ANZAHL`, `AEHNLICH_BIS` als
Umgebungsvariablen beim Start von bestof.py). Das Foto selbst und seine NEF fehlen in der Liste, ebenso
einfarbige und unlesbare Fotos – die lassen sich nicht vergleichen. Die Fassungen im Unterordner `verbessert`
(verbessert, koloriert, bearbeitet) stehen nicht in der Liste, taugen aber als Ausgangsfoto.

Beim ersten Mal liest fotosort.py alle Fotos, die es noch nicht kennt; bei einem großen Archiv dauert das,
die Seite zeigt den Fortschritt. Danach kommen die Fingerabdrücke aus dem Cache, und eine Suche braucht nur
Sekunden. „Neu suchen“ rechnet noch einmal.

Sonst ist die Seite ein Kontaktbogen wie ein Ordner: Lupe, Stern, Papierkorb, Alben und Jahr gehen auch
hier. **Fotos verschieben …** holt Treffer zum Ausgangsfoto: Fotos anklicken (Umschalt = Bereich), dann
„Zu 0004 (Ausgangsfoto)“ – oder wie auf der Ordnerseite „In neue Gruppe“ bzw. eine Ordnernummer eintippen.
Alles wandert mit wie beim [Verschieben](#ordner-zusammenfassen-und-neu-gruppieren), die Meldung hat
„Rückgängig“, und die Seite sucht danach neu. Auf der Kommandozeile:

```bash
MODUS=aehnlich python fotosort.py AUSGABE 0004/IMG_0001.JPG   # die ähnlichsten Fotos zu diesem Foto
```

### Papierkorb

Der Eimer neben dem Stern (in der Lupe auch die Taste <kbd>Entf</kbd>) schiebt ein Foto in den
Papierkorb: Es wandert samt NEF und Begleitdateien (`.xmp`, `.pp3`) nach `Sortiert/Musor/<Ordner>/`,
`Musor/liste.csv` vermerkt, woher es kam. Die Kachel bleibt bis zum Neuladen als „Im Papierkorb“
stehen; „Rückgängig“ in der Meldung oder „Zurückholen“ an der Kachel legt das Foto zurück. Fotos mit
Stern lassen sich nicht wegwerfen – erst den Stern entfernen.

Endgültig löschen geht über die Weboberfläche nie, auch nicht im Heimnetz. Den Papierkorb leeren Sie
bei Bedarf im Dateimanager; dort liegen auch die überzähligen Duplikate (`Musor/Duplikate`). Ein Foto
von Hand zurückholen: aus `Musor/0012/` zurück nach `0012/` verschieben – bestof.py liest es wieder ein,
Namen, Jahr und Alben sind noch da. Ältere Versionen legten Duplikate in den versteckten Ordner
`Sortiert/.duplikate`; der bleibt, wie er ist.

### Im Heimnetz

bestof.py ist im ganzen Heimnetz erreichbar: Läuft es auf dem Rechner `tigris`, öffnen Sie auf
Tablet, Handy oder einem anderen Rechner `http://tigris:8765`. Beim Start nennt bestof.py den Namen
und die IP-Adresse; klappt der Name nicht, hilft `http://tigris.local:8765` oder die IP
(z. B. `http://192.168.178.20:8765`). Blockiert eine Firewall, Port 8765 freigeben, unter Ubuntu
z. B. `sudo ufw allow 8765/tcp`.

Aus dem Heimnetz geht alles außer dem Import: Fotos ansehen, Sterne, Alben, Jahre, Namen, Papierkorb,
ähnliche Fotos, Ordner zusammenfassen, Fotos verschieben, Einstellungen. Importieren geht nur an dem Rechner selbst
(`http://localhost:8765`), ebenso das Ändern der ComfyUI-Adresse und das Hochladen von Workflows –
bestof.py erkennt das an der Absenderadresse, nicht an einem Passwort. Wer im Heimnetz nicht jedem die
Fotos zeigen will, setzt in `bestof.conf` ein `PASSWORT` (der Benutzername ist beliebig). `HOST = 127.0.0.1`
macht bestof.py wieder nur am eigenen Rechner erreichbar, etwa auf einem Laptop in fremden Netzen.

### Bearbeiten

In der Lupe öffnet **✎ Bearbeiten** (Taste <kbd>E</kbd>) eine eigene Leiste: ↺ und ↻ drehen um 90° (Tasten
<kbd>Umschalt</kbd>+<kbd>R</kbd> und <kbd>R</kbd>), ⇋ spiegelt waagerecht (<kbd>H</kbd>), dazu Regler für
Helligkeit, Kontrast und Sättigung (Doppelklick setzt einen Regler auf 0). Die Lupe zeigt jede Änderung sofort.

„Speichern“ legt eine neue Fassung an, wie beim Verbessern: `Sortiert/<Ordner>/verbessert/<Name>_bearbeitet.png`,
weitere als `…_bearbeitet_2.png`. Das Foto selbst bleibt unverändert. Die Fassung bekommt Datum, Ort, Jahr und
Alben des Fotos und steht nach dem Neuladen als Kachel „✦ bearbeitet“ direkt dahinter; ohne Drehung zeigt
gleich danach der Schieber Vorher/Nachher. Bearbeiten lässt sich jedes Foto, auch eine Fassung aus ComfyUI –
deren Workflow bleibt im PNG. „Abbrechen“ oder <kbd>Esc</kbd> verwirft die Änderungen; solange die Leiste offen
ist, blättern die Pfeiltasten nicht und Stern und Papierkorb ruhen.

### Verbessern mit ComfyUI

Läuft [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (Standard: auf demselben Rechner, Port 8188),
hat die Lupe den Knopf **✦ Verbessern**:

1. Foto öffnen, daneben den Workflow wählen (bei mehreren), „✦ Verbessern“ klicken. Steht etwas im Feld
   **Farbhinweise** (z. B. „the dress is dark blue“), hängt bestof.py es als „Color hints: …“ an den
   Prompt-Text des Workflows an – etwa für die Farben, die „Foto restore flux2“ beim Restaurieren
   zurückholt. Welcher Text als Prompt gilt, steht unter [Kolorieren](#kolorieren); ein Workflow ohne
   Prompt-Text läuft ohne die Hinweise, das sagt die Meldung.
2. bestof.py lädt das Foto zu ComfyUI und zeigt oben rechts den Stand („wartet, Platz 2“,
   „läuft · 0:35“). Derweil lässt sich weiterblättern, auch weitere Fotos können warten.
3. Das Ergebnis landet verlustfrei als PNG in `Sortiert/<Ordner>/verbessert/<Name>_<Workflow>.png`,
   ein weiterer Lauf als `…_2.png`; das Original bleibt unverändert. Die Fassung bekommt Datum und Ort
   des Originals (EXIF), dazu ein von Hand gesetztes Jahr und die Alben; ComfyUI schreibt den
   verwendeten Workflow ins PNG.
4. Danach erscheint der Schieber **Vorher/Nachher**: ziehen (auch mit dem Finger) oder den Regler
   bewegen; <kbd>V</kbd> schaltet ihn um.
5. Nach dem Neuladen steht die Fassung als eigene Kachel mit dem Kennzeichen „✦ <Workflow>“ direkt
   hinter dem Original. Sie lässt sich wie jedes Foto mit Stern markieren, einem Album zuordnen oder in
   den Papierkorb schieben; in der Lupe vergleicht <kbd>V</kbd> sie mit dem Original.

**Workflows:** in ComfyUI den Workflow öffnen, mit „Export (API)“ speichern und die JSON-Datei in den
Ordner `workflows/` neben `bestof.py` legen (anderer Ort: `WORKFLOWS` in `bestof.conf`) – oder auf der Seite
[Einstellungen](#einstellungen) mit „Workflow hochladen …“. Jede Datei ist eine Wahl neben „Verbessern“, der
Name kommt aus dem Dateinamen (`Foto_restore_API.json` → „Foto restore“). Welcher in der Lupe vorgewählt
ist, legt `VERBESSERN_WORKFLOW` fest (leer = der zuletzt gewählte). bestof.py setzt das Foto in den Bild-Eingang (`LoadImage` oder ein anderer Knoten mit dem
Eingang `image`; bei mehreren den, in dessen Titel „fotolese“ steht), würfelt den Seed jedes Mal neu
und holt das Bild des Speicher-Knotens (`Save Image`). Ein Workflow im normalen statt im API-Format
wird beim Start mit Hinweis übersprungen. Mitgeliefert sind „Foto restore“ (Qwen) und „Foto restore
flux2“ (Flux 2), beide auch zum Kolorieren (siehe
[Daten und Modelle von Dritten](#daten-und-modelle-von-dritten)).

ComfyUI auf einem anderen Rechner: `COMFYUI = http://rechner:8188`; `COMFYUI = 0` schaltet die Funktion
ab. Fehler – ComfyUI nicht erreichbar, Modell oder Knoten fehlt – erscheinen als Meldung in der
Oberfläche. ComfyUI legt die hochgeladenen Fotos in seinem Ordner `input` ab (`fotolese_…`), die
Ergebnisse zusätzlich in `output/fotolese/`; dort darf man aufräumen.

#### Kolorieren

Kolorieren ist ein eigener Knopf in der Lupe, unabhängig vom Verbessern: **◐ Kolorieren** färbt das
gerade gezeigte Foto ein. Das kann das Original sein – dann wird es direkt koloriert – oder eine schon
verbesserte Fassung, etwa nach „Foto restore“. Daneben steht ein Feld für Farbhinweise (z. B. „the dress
is dark blue“, höchstens 300 Zeichen, <kbd>Enter</kbd> startet das Kolorieren). „✦ Verbessern“ dagegen
setzt keine Kolorier-Anweisung ein: Es lässt den Prompt des Workflows stehen und hängt nur die
Farbhinweise an, wenn das Feld nicht leer ist.

bestof.py lädt das Foto zu ComfyUI und setzt statt des Prompts die Kolorier-Anweisung ein, würfelt einen
neuen Seed und schaltet die Restore-LoRA ab (sie hielte das Bild grau). Der Stand zeigt „Kolorieren mit
„…“: wartet …“ bzw. „läuft“. Danach vergleicht der Schieber das Foto mit der kolorierten Fassung; die
Schilder „Vorher ↗“ und „Nachher ↗“ öffnen die Dateien. Gespeichert wird
`…/verbessert/<Name>_koloriert.png` – für ein Original also `IMG_0001_koloriert.png`, für eine
Restaurierung `IMG_0001_Foto_restore_koloriert.png` –, als Kachel direkt hinter dem Foto, mit Datum, Ort,
Jahr und Alben des Fotos.

Der **Luma-Lock** nimmt Helligkeit, Details und Gesichter 1:1 aus dem Foto und von ComfyUI nur die Farbe;
dass das Modell beim Neuzeichnen um ein paar Pixel verrutscht oder die Größe ändert, stört so nicht.

Dafür braucht der Rechner `ffmpeg` (unter Ubuntu `sudo apt install ffmpeg`); fehlt es, bietet bestof.py
kein Kolorieren an und sagt das beim Start. Koloriert wird mit dem Workflow `FARBE_WORKFLOW`; ist keiner
eingestellt, mit dem in der Lupe gewählten. Kolorieren kann jeder Workflow mit genau einem Speicher-Knoten
und einem Prompt-Text – der mitgelieferte „Foto restore“ (Qwen) ebenso wie „Foto restore flux2“ und andere
mit „CLIP Text Encode“ für SD, SDXL oder Flux. Als Prompt gilt der erste Text-Encoder auf dem Weg vom
Speicher-Knoten zurück zum Sampler, nie der negative; liegt die Erkennung daneben, den richtigen Knoten
in ComfyUI im Titel mit „fotolese“ kennzeichnen. Einstellungen in `bestof.conf` oder auf der Seite
[Einstellungen](#einstellungen):

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `FARBE_WORKFLOW` | leer | Workflow fürs Kolorieren; leer = der in der Lupe gewählte (mit Prompt-Text) |
| `COLORIZE_RESTORE_LORA` | `0` | 0 = Restore-LoRA (Name mit „restore“, in jedem LoRA-Loader) aus; 0.3–0.5 bei Farbsäumen |
| `COLORIZE_LUMA_LOCK` | `1` | 0 = Bild von ComfyUI unverändert übernehmen |
| `COLORIZE_CHROMA_BLUR` | `0` | Farbe weichzeichnen (Sigma) gegen Farbsäume |
| `COLORIZE_PROMPT` | leer | eigene Kolorier-Anweisung statt der eingebauten |
| `COLORIZE_KEEP_RAW` | `0` | 1 = Bild von ComfyUI zusätzlich als `…_koloriert_roh.png` behalten |

Das Terminal nennt je Auftrag Workflow, Seed, Farbhinweise und Ergebnis. Frühere Versionen kannten noch
die Wahl „+ Kolorierung“ beim Verbessern (`COLORIZE_DEFAULT`, `COLORIZE_MONO_THRESHOLD`); beides gibt es
nicht mehr.

### Ordner zusammenfassen und neu gruppieren

fotosort.py legt beim Import ähnliche Fotos in einen Ordner. Was dabei getrennt blieb – etwa weil die
Fotos in verschiedenen Importen kamen oder sich mehr unterscheiden, als die Einstellungen erlauben –,
lässt sich nachträglich zusammenführen: von Hand oder für das ganze Archiv.

**Zusammenfassen:** Auf der Übersicht „Ordner zusammenfassen“ klicken, dann die Ordner anklicken, die
zusammengehören (Umschalt = alle bis zum zuletzt angeklickten), und „Zusammenfassen …“. Der Dialog zeigt,
was passiert: Alle Fotos kommen in den Zielordner – vorgewählt der mit der kleinsten Nummer, also
0004, 0005, 0006 → 0004 –, die übrigen Ordner verschwinden. Mit jedem Foto wandern NEF, Begleitdateien
(`.xmp`, `.pp3`, `.aae`) und die verbesserten Fassungen. Gibt es einen Namen im Ziel schon, bekommt die
Aufnahme einen Laufindex (`IMG_0001_1.JPG`, die Fassungen passend dazu). Sterne, Alben, ein von Hand
gesetztes Jahr, Gesichter und Namen bleiben erhalten; mehr Sterne als `MAX_BEST` je Ordner fallen weg –
das sagt der Dialog vorher. Danach öffnet sich der Zielordner, die Meldung hat „Rückgängig“.

**Fotos in eine eigene Gruppe:** Sind in einen Ordner Fotos geraten, die nicht dazugehören, auf der
Ordnerseite „Fotos verschieben …“ klicken und die Fotos anklicken (Umschalt = alle bis zum zuletzt
angeklickten). „In neue Gruppe“ legt sie in einen neuen Ordner mit der nächsten freien Nummer; wer weiß,
wohin sie gehören, tippt stattdessen die Nummer eines vorhandenen Ordners ein und wählt „In diesen
Ordner“. Wie beim Zusammenfassen wandern NEF, Begleitdateien, verbesserte Fassungen (eine gewählte
Fassung nimmt ihr Original mit), Sterne, Alben, Jahr und Gesichter mit; die Meldung danach hat
„Rückgängig“ und öffnet auf Wunsch den neuen Ordner. Wird ein Ordner dabei leer, verschwindet er.
<kbd>Esc</kbd> oder „Fertig“ beendet die Auswahl. Verstreute Fotos eines Motivs sammelt
[Ähnliche Fotos](#ähnliche-fotos) ein.

**Welche Ähnlichkeit hätte gereicht?** Im selben Dialog rechnet fotosort.py aus, mit welchem Wert es
diese Fotos beim Import selbst in eine Gruppe gelegt hätte: je Einstellung der kleinste, der bei sonst
gleichen Werten genügt – Bildvergleich (`SCHWELLE`), Serie: Zeitabstand (`SERIE_SEK`) oder Serie: Abstand
(`SERIE_SCHWELLE`). Dazu die engste Stelle (die zwei Fotos, die am schlechtesten zusammenpassen) und die
Folgen: welche anderen Ordner mit diesem Wert bei „Neu gruppieren“ außerdem zusammenkämen. „Übernehmen“
speichert den Wert in `bestof.conf`, er gilt für künftige Importe. Werte ab etwa 50 machen fast alle Fotos
ähnlich – der Dialog warnt davor. Wären die Fotos schon mit den jetzigen Werten eine Gruppe gewesen, sagt
er auch das: fotosort.py legt beim Import bestehende Ordner nie zusammen, dafür ist Zusammenfassen da.

**Neu gruppieren:** Auf der Seite [Einstellungen](#einstellungen) gruppiert „Neu gruppieren“ das ganze
Archiv mit den eingestellten Werten neu, als kämen alle Fotos in einem Import. Jede Gruppe behält den
Ordner, in dem schon die meisten ihrer Fotos liegen; neue Gruppen bekommen Nummern hinter der höchsten,
einfarbige und unlesbare Fotos bleiben, wo sie sind. Zuerst kommt eine Vorschau – wie viele Fotos wandern,
welche Ordner zusammenkommen oder geteilt werden –, verschoben wird erst nach „Jetzt neu gruppieren“.
„Letzten Umzug rückgängig“ stellt den alten Stand wieder her: Dateien, Sterne, Index.

Jeder Umzug – Zusammenfassen, Verschieben, Neu gruppieren – steht in
`Sortiert/.bestof-umzug/umzug-<Zeit>.json`; zurücknehmen lässt sich der letzte.
Während eines Umzugs ruhen Import, Verbessern und der Index. Auf der Kommandozeile rechnet fotosort.py
dasselbe, verschiebt aber nichts:

```bash
MODUS=analyse python fotosort.py AUSGABE 0004 0005 0006   # welche Werte hätten diese Ordner zusammengebracht?
MODUS=gruppen python fotosort.py AUSGABE                  # Plan für das ganze Archiv (JSON); ausführen in bestof.py
```

### Einstellungen

Die Seite „Einstellungen“ zeigt die wichtigsten Werte aus `bestof.conf` und ändert sie; sie gelten sofort.

- **Ähnlichkeit beim Import:** `SCHWELLE`, `SERIE_SEK`, `SERIE_SCHWELLE` und `EINZELN` gibt bestof.py an
  fotosort.py weiter – beim Import, bei der Analyse und bei „Neu gruppieren“ (darunter auf derselben Seite).
- **Verbessern mit ComfyUI:** die ComfyUI-Adresse, der in der Lupe vorgewählte Workflow
  (`VERBESSERN_WORKFLOW`) und ein eigener Workflow fürs Kolorieren (`FARBE_WORKFLOW`). Die Liste zeigt
  jeden Workflow mit seinem Zustand; „Workflow hochladen …“ legt eine JSON-Datei im API-Format in den
  Ordner `workflows`.
- **Kolorieren:** die Werte aus der Tabelle oben.
- **Anzeige, Personen, Import:** Sterne je Ordner, Ordner je Übersichtsseite, Umkreis für den Ortsfilter;
  Ähnlichkeit für dieselbe Person, Abstand, Lernen; Prozesse für fotosort.py.

„Standard“ neben einem Feld nimmt wieder den eingebauten Wert (die Zeile in `bestof.conf` wird
auskommentiert). Was eine Umgebungsvariable setzt, hat Vorrang und ist auf der Seite gesperrt. Die
ComfyUI-Adresse und das Hochladen von Workflows gehen nur am Rechner selbst, nicht aus dem Heimnetz –
beides bestimmt, was ComfyUI ausführt. Eine ausgeschaltete ComfyUI-Anbindung (`COMFYUI = 0`) kommt erst
nach einem Neustart wieder.

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

**ComfyUI auf derselben Grafikkarte:** Solange bestof.py ein Foto über ComfyUI verbessert oder koloriert,
liest der Index neue Bilder auf der CPU. Hält ComfyUI seine Modelle auch danach im GPU-Speicher, kann eine
GPU-Sitzung des Index mit „GPU-Speicher voll“ scheitern (im Terminal von ONNX Runtime als „CUBLAS failure 3:
the resource allocation failed“); der betroffene Prozess rechnet dann auf der CPU weiter, verloren geht nichts.
Abhilfe, wenn es oft vorkommt: `GPU_JOBS = 1` oder `GPU = 0` in `bestof.conf`, oder ComfyUI mit
`--reserve-vram 2` starten (hält 2 GB für andere Programme frei).

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
│   │   ├── neu.py           Neu-Gruppierung des Archivs (Plan), Analyse nötiger Werte, ähnliche Fotos
│   │   └── cli.py           main() und Hilfetext (-h)
│   └── web/                 bestof: durchsehen, filtern, Sterne für BestOf
│       ├── konst.py         Konstanten, Muster, Monatsnamen, Quellen der Modelle
│       ├── konfig.py        bestof.conf lesen und schreiben, Einstellungen, Textformate
│       ├── archiv.py        Zugriff auf den Sortiert-Ordner (Ordner, Bilder, NEF)
│       ├── bild.py          Vorschaubilder erzeugen und zwischenspeichern
│       ├── orte.py          GeoNames offline: GPS → nächster größerer Ort
│       ├── auswahl.py       Sterne je Ordner, Kopien in BestOf
│       ├── papierkorb.py    Fotos nach Musor schieben und zurückholen, nie löschen
│       ├── verbessern.py    Fotos mit ComfyUI verbessern, Fassung in <Ordner>/verbessert
│       ├── bearbeiten.py    Bearbeiten in der Lupe: drehen, spiegeln, Farben; Fassung …_bearbeitet.png
│       ├── kolorieren.py    Kolorieren: Prompt-Erkennung, Luma-Lock mit ffmpeg
│       ├── alben.py         Alben: anlegen, Fotos zuordnen, für Filter und Oberfläche
│       ├── index.py         SQLite-Index und Hintergrund-Indexer
│       ├── gesichter.py     Gesichtserkennung (YuNet/SFace) im Prozess-Pool
│       ├── gpu.py           Gesichtsmodelle auf der GPU: Auswahl, Prüfung, Rückfall auf CPU
│       ├── suche.py         Suchbegriffe: Jahr, Ort, Person, Album, Ordner, Dateiname
│       ├── html.py          Seiten, CSS und JavaScript der Oberfläche
│       ├── server.py        HTTP-Handler und /api-Aktionen
│       ├── lernen.py        aus Korrekturen Schwelle und Abstand lernen
│       ├── importieren.py   Seite „Import“ (nur am Rechner selbst): fotosort.py, Duplikate
│       ├── gruppieren.py    Ordner zusammenfassen, Plan ausführen, Rückgängig (Umzug mit Index)
│       ├── aehnlich.py      Seite „Ähnliche Fotos“: Treffer von fotosort als Kontaktbogen
│       ├── einstellungen.py Seite „Einstellungen“, Workflows hochladen
│       └── cli.py           main() und Hilfetext (-h)
├── workflows/               ComfyUI-Workflows (API-Format) für „Verbessern“
│   ├── Foto_restore_API.json  Qwen Image 2.1 Restore (AusBoss)
│   └── Foto_restore_flux2.json  Restaurieren mit FLUX.2 [dev]
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
  Verbunden sind sie nur über Unterprozesse: `web/importieren.py` startet `fotosort.py` mit demselben
  Python – für den [Import im Browser](#import-im-browser) mit `MODUS=copy`, `DUPLIKATE=1`, `JOBS` aus
  `IMPORT_JOBS`, für die Analyse und die Vorschau von „Neu gruppieren“ mit `MODUS=analyse` bzw.
  `MODUS=gruppen` (Plan als JSON in `Sortiert/.bestof-umzug/`), für [Ähnliche Fotos](#ähnliche-fotos) mit
  `MODUS=aehnlich`, immer mit den Ähnlichkeitswerten aus den Einstellungen, `JA=1` und `FORTSCHRITT_JSON=1`.
  bestof.py liest die Ausgabe mit: `#FS {json}`-Zeilen (aus `sort/bericht.py`) für Fortschritt und
  Ergebnisse, die Zeile `Protokoll: …` für „Import rückgängig“.
  Verschoben wird beim Neu-Gruppieren von `web/gruppieren.py`, damit Sterne, Alben und Index mitwandern.

## Datenschutz

- Alles läuft lokal. Fotos verlassen den Rechner nicht – außer zum ComfyUI unter `COMFYUI`, wenn Sie
  „Verbessern“ nutzen (Standard: derselbe Rechner).
- Der Index `Sortiert/.bestof-index.sqlite3` enthält Gesichtsmerkmale (biometrische Daten).
  Geben Sie ihn nicht weiter.
- Die Weboberfläche ist im Heimnetz erreichbar ([Im Heimnetz](#im-heimnetz)); ohne `PASSWORT` kann dort
  jeder die Fotos sehen. In fremden Netzen (Laptop unterwegs) `HOST=127.0.0.1` oder ein `PASSWORT` setzen.

## Daten und Modelle von Dritten

Nicht Teil dieses Repositorys. bestof.py lädt sie beim ersten Start nach `~/.cache/fotosort`:

| Was | Quelle | Lizenz |
|---|---|---|
| Ortsdaten cities1000 | [GeoNames](https://www.geonames.org) | CC BY 4.0 |
| Gesichtserkennung YuNet | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | MIT |
| Gesichtsmerkmale SFace | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) | Apache-2.0 |

Der mitgelieferte Workflow `workflows/Foto_restore_API.json` („Qwen Image 2.1 Restore“) stammt von
[AusBoss](https://github.com/ausboss). Er braucht ComfyUI 0.38 oder neuer, die Knoten
[ComfyUI-AusBoss](https://github.com/ausboss/ComfyUI-AusBoss) und die Modelle aus der Notiz im Workflow
(Qwen Image 2.1, Text-Encoder, VAE, Restore- und Turbo-LoRA, zusammen rund 18 GB). Die lädt und
verwaltet ComfyUI, nicht bestof.py; für die Turbo-LoRA gilt die Qwen Research License.

`workflows/Foto_restore_flux2.json` („Foto restore flux2“) nutzt FLUX.2 [dev] von Black Forest Labs mit
Text-Encoder, VAE und Turbo-LoRA, wie sie in den Knoten des Workflows stehen, dazu die Knoten
[rgthree-comfy](https://github.com/rgthree/rgthree-comfy) (Power Lora Loader, Image Comparer). Auch diese
Modelle verwaltet ComfyUI; es gelten die Lizenzbedingungen ihrer Anbieter.

## Haftung

Benutzung auf eigene Gefahr. fotosort.py verschiebt im Standard (`MODUS=move`); der Import in
bestof.py kopiert nur.
Probieren Sie es zuerst mit `MODUS=test` oder an einer Kopie.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
