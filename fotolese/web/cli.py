"""
bestof.py – Weboberfläche: Fotos durchsehen, filtern, je Ordner bis zu 3 beste Bilder mit Stern markieren.

Stern (☆ unter dem Bild) -> sofort Kopie in SORTIERT/BestOf:
  1 Bild mit Stern     -> 0001.jpg
  2–3 Bilder           -> 0001a.jpg, 0001b.jpg, 0001c.jpg  (a = zuerst markiert)
NEF-Dateien werden nicht angezeigt – fotosort.py legt zu jedem NEF ein JPG an.

Im Hintergrund entsteht ein Index (SORTIERT/.bestof-index.sqlite3):
  * Datum aus den EXIF-Daten (sonst aus dem Dateinamen), GPS -> nächster größerer Ort (GeoNames, offline)
  * Gesichter -> Personen (Person 1, Person 2 …), auf der Seite „Personen“ benennbar
Jahr:
  Jedes Bild hat ein Jahresfeld, vorausgefüllt aus EXIF oder Dateiname. Falsch (Scan, Kamerauhr,
  WhatsApp)? Jahr eintippen, Enter. Gelb = von Hand gesetzt; leeren + Enter = wieder Jahr aus der Datei.
  „für alle Bilder“ auf der Ordnerseite setzt das Jahr für den ganzen Ordner. Viele Fotos auf einmal: oben
  bei „Jahr per Klick“ das Jahr eintippen, dann → Jahr unter den Fotos (Umschalt = alle bis zum zuletzt
  angeklickten). Ein von Hand gesetztes Jahr ersetzt auch den Monat (gilt dann als unbekannt). Gespeichert
  im Index, die Bilddateien bleiben unverändert.
Gesichter:
  Suche in zwei Stufen (GESICHT_SCORE, GEGENPROBE), kleine Gesichter mit Merkmalen aus dem Originalbild.
  Fehlt trotzdem eins (sehr klein, Profil, verdeckt)? In der Lupe Gesichter einblenden (G) und ins Gesicht
  klicken – dort wird genauer gesucht. Findet die Suche nichts, lässt sich die Stelle mit Namen markieren.
  Der Knopf „Gesichter (N)“ ist immer da; die Zeile oben im Bild sagt, ob das Bild schon durchsucht ist.
Personen:
  Gleicher Name = dieselbe Person. Kinder- und Erwachsenenfotos landen oft in getrennten Gruppen;
  beide „Anna“ nennen genügt. Die Gruppen bleiben getrennt (je eigener Mittelwert), der Filter
  „Anna“ findet beide. „Gruppe lösen“ nimmt den Namen wieder weg.
  In der Lupe (G) das Namensschild anklicken: Name eintippen, dann
    „Alle N Gesichter dieser Gruppe“  – die ganze Gruppe heißt so (Standard bei „Person N“), oder
    „Nur dieses Gesicht“              – Korrektur: das Gesicht wechselt zur ähnlichsten Gruppe dieses
                                        Namens oder bildet eine neue; sehr ähnliche Gesichter derselben
                                        alten Gruppe (z. B. Serienbilder) wandern mit (NACHZIEHEN).
  Auf „Personen“: Namensfeld = ganze Gruppe, ✎ = nur dieses Gesicht (mit Nachziehen), ✕ = kein Gesicht.
  „Alle prüfen“ zeigt alle Gesichter einer Gruppe, untypische zuerst – dort stecken Verwechslungen
  (z. B. Kind in der Gruppe eines Elternteils). Anklicken (Umschalt = Bereich), Namen eintippen, fertig.
Import (Seite „Import“, braucht fotosort.py neben bestof.py; nur an diesem Rechner, nie aus dem Heimnetz):
  Ordner im Browser wählen, „In Sortiert kopieren“. fotosort.py kopiert alle Fotos samt Unterordnern (Quelle
  bleibt unverändert), sortiert ähnliche in Ordner, ergänzt passende bestehende, legt zu NEF ein JPG an.
  Inhaltsgleiche Dateien (SHA-256) kommen nur einmal ins Archiv; danach behält das Archiv von jedem Inhalt
  genau eine Datei (bevorzugt: mit Stern in BestOf, mit Labels, ohne Laufindex). Überzählige wandern in den
  Papierkorb SORTIERT/Musor/Duplikate/<Zeit>/ (mit liste.csv). Optional ein Album (vorhanden oder neu): alle
  Fotos des Imports kommen hinein, auch die schon vorhandenen gleichen Inhalts.
  „Abbrechen“ stoppt nach dem laufenden Ordner, „Import rückgängig“ entfernt die Kopien des letzten Imports
  und seine Album-Zuordnungen.
Papierkorb (Eimer unter jedem Foto, in der Lupe Taste Entf):
  Das Foto wandert samt NEF und Begleitdateien (.xmp, .pp3) nach SORTIERT/Musor/<Ordner>/, Musor/liste.csv
  vermerkt die Herkunft. „Rückgängig“ bzw. „Zurückholen“ legt es zurück. Fotos mit Stern bleiben (erst den
  Stern entfernen). Endgültig löschen geht über die Weboberfläche nie – den Papierkorb leert man im Dateimanager.
Bearbeiten (Lupe, Knopf „✎ Bearbeiten“ oder Taste E):
  Drehen um 90° (R, Umschalt+R = links), waagerecht spiegeln (H), Helligkeit, Kontrast, Sättigung – mit Vorschau.
  „Speichern“ legt eine neue Fassung SORTIERT/<Ordner>/verbessert/<Name>_bearbeitet.png an (wie beim Verbessern,
  mit Datum, Ort, Jahr und Alben des Fotos); das Foto bleibt unverändert. Esc oder „Abbrechen“ verwirft.
Verbessern (ComfyUI, z. B. auf demselben Rechner, Port 8188):
  In der Lupe Workflow wählen und „✦ Verbessern“: bestof lädt das Foto zu ComfyUI, wartet und legt das Ergebnis
  verlustfrei als SORTIERT/<Ordner>/verbessert/<Name>_<Workflow>.png ab – mit Datum und Ort des Originals, das
  Original bleibt. Danach zeigt der Schieber Vorher/Nachher (Taste V); nach dem Neuladen steht die Fassung als
  eigene Kachel hinter dem Original und lässt sich wie jedes Foto mit Stern markieren. Workflows: in ComfyUI mit
  „Export (API)“ speichern und in den Ordner workflows neben bestof.py legen (WORKFLOWS); jede Datei = eine Wahl.
  Kolorieren (braucht ffmpeg) ist ein eigener Knopf „◐ Kolorieren“ in der Lupe: färbt das gezeigte Foto ein – das
  Original direkt oder eine verbesserte Fassung –, optional mit Farbhinweisen. Ergebnis <Name>_koloriert.png im
  Unterordner verbessert; Helligkeit und Details aus dem Foto (Luma-Lock), nur die Farbe von ComfyUI. Workflow:
  FARBE_WORKFLOW, sonst der in der Lupe gewählte, wenn er einen Prompt-Text hat. Die Farbhinweise gelten auch
  beim Verbessern: Sie kommen ans Ende des Prompt-Texts des Workflows („Color hints: …“), falls er einen hat.
Ordner zusammenfassen (Übersicht, Knopf „Ordner zusammenfassen“):
  Ordner anklicken (Umschalt = Bereich), „Zusammenfassen …“: alle Fotos kommen in den Zielordner (vorgewählt die
  kleinste Nummer: 0004, 0005, 0006 -> 0004), samt NEF, Begleitdateien und verbesserten Fassungen; gleiche Namen
  bekommen einen Laufindex. Sterne, Alben, Jahr und Gesichter wandern mit; „Rückgängig“ in der Meldung. Der Dialog
  nennt, mit welchem Wert (SCHWELLE, SERIE_SEK, SERIE_SCHWELLE) fotosort die Fotos beim Import selbst
  zusammengelegt hätte und was der Wert sonst zusammenlegen würde; „Übernehmen“ speichert ihn.
Fotos verschieben (Ordnerseite, Knopf „Fotos verschieben …“):
  Fotos anklicken, die nicht in den Ordner gehören (Umschalt = Bereich), dann „In neue Gruppe“ (nächste freie
  Ordnernummer) oder Nummer eines vorhandenen Ordners + „In diesen Ordner“. NEF, Begleitdateien, Fassungen, Sterne,
  Alben, Jahr und Gesichter wandern mit; „Rückgängig“ in der Meldung, ein leerer Ordner verschwindet.
Ähnliche Fotos (Lupe, Knopf „≈ Ähnliche“):
  Die ähnlichsten Fotos im ganzen Archiv, nach Ähnlichkeit sortiert. Verglichen wird der Bildinhalt mit dem KI-Modell
  CLIP: Der Index berechnet je Foto einmal Merkmale (auf der CPU, mit ONNX Runtime oder OpenCV ab 5). Das Modell,
  rund 350 MB, lädt bestof.py beim ersten Mal von Hugging Face; die Fotos bleiben auf dem Rechner. Ähnlichkeit in
  Prozent: ab 95 fast gleich, ab 88 sehr ähnlich, ab 80 ähnlich, darunter bis AEHNLICH_MIN entfernt ähnlich; höchstens
  AEHNLICH_ANZAHL Fotos. Ohne KI (KI = 0, INDEX = 0, Modell nicht ladbar) nur fast gleiche Fotos per Bildvergleich wie
  beim Import (pHash+dHash). „Fotos verschieben …“ bringt gewählte Fotos in den Ordner des Ausgangsfotos, in eine
  neue Gruppe oder einen anderen Ordner.
Einstellungen (Seite „Einstellungen“):
  Ähnlichkeit beim Import, Workflows (Vorwahl, eigener fürs Kolorieren, hochladen), Kolorieren, Anzeige,
  Personen, Import – geschrieben in bestof.conf, gültig sofort. „Neu gruppieren“ gruppiert dort das ganze Archiv
  mit den Werten neu: erst Vorschau, dann ausführen, „Letzten Umzug rückgängig“ stellt alles wieder her
  (Protokoll in SORTIERT/.bestof-umzug/). ComfyUI-Adresse und Hochladen nur an diesem Rechner.
Heimnetz:
  bestof.py lauscht auf allen Netzwerken: vom Tablet, Handy oder anderen Rechner http://<Rechnername>:8765,
  z. B. http://tigris:8765 (Name und IP stehen in der Startausgabe). Alles geht von dort – außer Importieren,
  der ComfyUI-Adresse und dem Hochladen von Workflows.
  PASSWORT schützt die Seiten; HOST = 127.0.0.1 = nur dieser Rechner. Firewall: Port 8765 freigeben.
Ordneransicht: unter jedem Foto Auflösung, Dateigröße und – falls vorhanden – Größe der NEF-Datei;
  die höchste Auflösung im Ordner ist gelb markiert.
Alben (Seite „Alben“: anlegen, umbenennen, löschen):
  Ein Foto kann in beliebig vielen Alben stehen; unter jedem Foto stehen seine Alben, ein Klick darauf filtert.
  Ein Album zeigt sich in Gruppen: je Ordner eine Kachel, Vorschau = Foto mit Stern, sonst das zuletzt geänderte
  (gilt auch auf der Ordner-Übersicht); Klick = die Fotos der Gruppe einzeln. „Gruppen | Einzeln“ schaltet um.
  Markieren: über den Fotos „Fotos markieren für Album …“ wählen (oder „Neues Album“), dann ＋ unter den Fotos
  (Umschalt = alle bis zum zuletzt angeklickten) oder in der Lupe Taste A; „Alle hinzufügen“ nimmt den ganzen
  Ordner bzw. alle Treffer des Filters. Ohne gewähltes Album öffnet ＋ die Liste aller Alben zum Ankreuzen.
  Gespeichert im Index; doppelte Dateien geben ihre Alben an die behaltene Datei weiter.
Einstellungen und Lernen (bestof.conf neben bestof.py, wird beim ersten Start angelegt):
  NAME = Wert je Zeile; Umgebungsvariablen haben Vorrang. Die Seite „Einstellungen“ ändert die meisten Werte. Jede Korrektur einer automatischen Zuordnung
  (Gesicht „Thomas“ ist in Wahrheit „Paul“) und jede Bestätigung (Schild anklicken + Enter, „Ausgewählte
  bestätigen“) ist ein Label. Nach LERNEN_AB Korrekturen stellt bestof.py PERSON_SCHWELLE und ABSTAND so ein,
  dass diese Fehler nicht wieder passieren, ohne bestätigte Gesichter zu verlieren, schreibt sie in bestof.conf
  und verschiebt automatisch zugeordnete Gesichter, die eindeutig zu einer anderen benannten Person passen.
  Ihre eigenen Zuordnungen bleiben unangetastet. Auf „Personen“ steht der Lernstand, „Jetzt lernen“ startet es sofort.
Filter im Suchfeld, Begriffe mit Komma trennen:
  2023, Leipzig, Anna    -> Fotos aus 2023, höchstens NAEHE_KM von Leipzig, auf denen Anna ist
  Juli 2023 | 2023-07 | 0012 (Ordner) | Person 7 | ohne Jahr | Jahr korrigiert | Teil eines Dateinamens
  Album Urlaub (oder nur Urlaub) | ohne Album   -> mehrere Alben: Fotos aus einem davon
  Alle Fotos (Knopf neben „Filtern“)            -> das ganze Archiv nach Datum, z. B. zum Einordnen
  Gruppen | Einzeln (neben den Chips)           -> Treffer je Ordner als Kachel oder jedes Foto einzeln; ein Album
                                                   zeigt sich in Gruppen, alles andere einzeln
  Ohne Album (Knopf daneben)                    -> nur Fotos, die noch in keinem Album sind; eingeordnete werden
                                                   blass, nach dem Neuladen bleiben die übrigen

Aufruf (Conda-Umgebung von fotosort.py):
  python -m pip install opencv-python-headless   # nur für die Gesichtserkennung nötig
  python bestof.py /media/$USER/EXTERN/Sortiert

Tasten im Ordner:  ← / →  voriger / nächster Ordner,  N  nächster Ordner ohne Stern
Tasten in der Lupe: ← / →  Bild (mit der Maus: ‹ › am linken und rechten Bildschirmrand),  Leertaste / S  Stern,
                    Entf  Papierkorb,  G  Gesichter zeigen,  J  Jahr ändern,
                    V  Vorher/Nachher (verbesserte oder kolorierte Fassung),  Esc  schließen,
                    E  Bearbeiten (darin R / Umschalt+R drehen, H spiegeln, Esc abbrechen),
                    A  Album: ins gewählte Album aufnehmen/herausnehmen, sonst Alben zuordnen
                    (Namensschild anklicken = benennen: ganze Gruppe oder nur dieses Gesicht;
                     Gesicht fehlt = bei eingeblendeten Gesichtern ins Gesicht klicken)

Umgebungsvariablen (Standard in Klammern):
  PORT       (8765)
  HOST       ()            leer = alle Netzwerke: im Heimnetz unter http://<Rechnername>:8765, z. B. vom Tablet;
                           127.0.0.1 = nur dieser Rechner
  PASSWORT   ()            Passwortschutz, Benutzername beliebig
  MAX_BEST   (3)           höchstens so viele Sterne (BestOf-Bilder) je Ordner
  BESTOF     (BestOf)      Zielordner, relativ zu SORTIERT oder absolut
  VORSCHAU   (SORTIERT/.vorschau)  Ordner für Vorschaubilder, 0 = nur Arbeitsspeicher
  GROSS      (2048)        Kantenlänge der Lupe in Pixel, 0 = Originaldatei
  PRO_SEITE  (120)         Ordner je Übersichtsseite
  BROWSER    (1)           Browser beim Start öffnen
  INDEX      (1)           0 = kein Index (keine Metadaten, Orte, Personen, Filter)
  GESICHTER  (1)           0 = keine Gesichtserkennung
  KI         (1)           0 = keine KI-Suche für „Ähnliche Fotos“ (dann nur fast gleiche Fotos per Bildvergleich)
  AEHNLICH_MIN (72)        „Ähnliche Fotos“: ab so viel Prozent Ähnlichkeit zeigen
  AEHNLICH_ANZAHL (150)    „Ähnliche Fotos“: höchstens so viele
  INDEX_JOBS (Kerne/2)     parallele Prozesse für den Index
  GPU        (auto)        Gesichtserkennung auf der GPU, wenn eine nutzbar ist (Pakete je Hersteller: README, GPU);
                           0 = nur CPU; cuda | rocm | directml | coreml | openvino | opencv-cuda | opencl = nur dieses
  GPU_JOBS   (2)           so viele Index-Prozesse rechnen auf der GPU, die übrigen auf der CPU (mehr = mehr GPU-Speicher)
  ORT_MIN_EW (10000)       „größerer Ort“ = mindestens so viele Einwohner
  NAEHE_KM   (15)          Umkreis für Ortsfilter
  PERSON_SCHWELLE (0.40)   Ähnlichkeit für dieselbe Person (höher = strenger) – wird gelernt
  ABSTAND    (0.00)        so viel ähnlicher als jede andere benannte Person, sonst neue Gruppe – wird gelernt
  LERNEN     (1)           0 = Schwelle und Abstand nie automatisch ändern
  LERNEN_AB  (5)           neu lernen nach so vielen korrigierten Fehlzuordnungen
  BESTOF_CONF (bestof.conf neben dem Skript)  andere Einstellungsdatei
  IMPORT     (1)           0 = Seite „Import“ aus; sonst nur an diesem Rechner (nie aus dem Heimnetz)
  IMPORT_JOBS (Kerne/2)    parallele Prozesse für fotosort beim Import (HDD/USB: z. B. 2–4)
  SCHWELLE   (20)          Ähnlichkeit für fotosort (Import, Neu gruppieren): max. Abstand pHash+dHash (0–128)
  SERIE_SEK  (3)           Serienbilder: max. Sekunden zum Nachbarbild derselben Kamera …
  SERIE_SCHWELLE (36)      … und max. Abstand
  EINZELN    (ordner)      Einzelbilder: ordner = je eigener Ordner, 0000 = alle in Ordner 0000
  FOTOSORT   (fotosort.py neben bestof.py)
  COMFYUI    (http://127.0.0.1:8188)  ComfyUI für „Verbessern“; 0 = aus
  WORKFLOWS  (workflows neben bestof.py)  Ordner mit Workflows im API-Format (ComfyUI: Export (API))
  VERBESSERN_WORKFLOW ()   in der Lupe vorgewählter Workflow (Dateiname); leer = der zuletzt gewählte
  FARBE_WORKFLOW ()        Workflow für „Kolorieren“; leer = der in der Lupe gewählte (braucht einen Prompt-Text)
  COLORIZE_RESTORE_LORA (0)  Restore-LoRA beim Kolorieren: 0 = aus, 0.3–0.5 bei Farbsäumen
  COLORIZE_LUMA_LOCK (1)   0 = Bild von ComfyUI ohne Luma-Lock übernehmen
  COLORIZE_CHROMA_BLUR (0) Weichzeichnen der Farbe (Sigma) gegen Farbsäume
  COLORIZE_PROMPT ()       eigene Kolorier-Anweisung statt der eingebauten
  COLORIZE_KEEP_RAW (0)    1 = Bild von ComfyUI zusätzlich als …_koloriert_roh.png behalten
  NACHZIEHEN (0.50)        beim Korrigieren eines Gesichts wandern Gesichter derselben Gruppe mit, die ihm
                           mindestens so ähnlich sind und ihm ähnlicher als dem Rest der Gruppe; 1 = aus
  ERKENN_PX  (1920)        Bildgröße für die Gesichtssuche (größer = findet kleinere Gesichter, langsamer);
                           die Merkmale kleiner Gesichter kommen aus dem Originalbild
  MIN_GESICHT (48)         kleinere Gesichter ignorieren (Pixel im Originalbild)
  GESICHT_SCORE (0.50)     Mindestsicherheit der Gesichtssuche, 1. Stufe (kleiner = mehr Kandidaten)
  GEGENPROBE (0.80)        2. Stufe: Kandidat muss im vergrößerten Ausschnitt erneut gefunden werden –
                           filtert Muster (Buchstaben, Fell, Stoff) heraus; 0 = aus
                           Ändert sich einer dieser Werte, durchsucht der Index alle Bilder neu nach Gesichtern;
                           Namen und Korrekturen bleiben erhalten (Gesicht an gleicher Stelle im Bild).
  AKTUALISIEREN (300)      Sekunden bis zur nächsten Suche nach neuen Bildern
  DATEN      (~/.cache/fotosort)   Ablage für Gesichtsmodelle und Ortsdaten

Daten, die beim ersten Start einmalig geladen werden:
  GeoNames cities1000 (CC BY 4.0)        https://download.geonames.org/export/dump/cities1000.zip
  YuNet Gesichtserkennung (MIT), SFace Gesichtsmerkmale (Apache 2.0) aus github.com/opencv/opencv_zoo
Alles Weitere läuft lokal; keine Fotos verlassen den Rechner.
"""
import errno
import os
import socket
import sqlite3
import sys
import threading
import webbrowser
from collections import OrderedDict
from http.server import ThreadingHTTPServer

from fotolese.web import konfig
from fotolese.web.konst import VERSION
from fotolese.web.konfig import Konfig, _env, bilder_text
from fotolese.web.archiv import Archiv
from fotolese.web.auswahl import Auswahl
from fotolese.web.bild import Vorschau
from fotolese.web.index import Index, Indexer
from fotolese.web.lernen import Lerner
from fotolese.web.server import App, Handler
from fotolese.web.kolorieren import Kolorierung
from fotolese.web.verbessern import Verbesserer


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Abgebrochene Verbindungen (Tab zu, Browser beendet) sind normal – keinen Traceback ins Terminal."""
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class Server6(Server):
    """IPv6-Socket, der auch IPv4 annimmt: erreichbar über jede Adresse, unter der der Rechner im Heimnetz
    bekannt ist (tigris, tigris.local, 192.168.…, IPv6). IPv4-Absender erscheinen als ::ffff:a.b.c.d."""
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


def server_starten(host, port):
    """HOST leer = alle Netzwerke (IPv6 samt IPv4, ohne IPv6 nur IPv4), sonst genau diese Adresse."""
    if host:
        return (Server6 if ":" in host else Server)((host.strip("[]"), port), Handler)
    if socket.has_ipv6:
        try:
            server = Server6(("::", port), Handler)
            if not server.socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY):
                return server
            server.server_close()  # System erlaubt kein IPv4 auf dem IPv6-Socket
        except OSError as fehler:
            if fehler.errno == errno.EADDRINUSE:
                raise
    return Server(("0.0.0.0", port), Handler)


def lokale_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "IP-des-Rechners"


def main(skript_ordner=None):
    # 'neben bestof.py' = Verzeichnis des Starters (fotosort.py/bestof.conf liegen dort)
    basis = skript_ordner or os.path.dirname(os.path.abspath(sys.argv[0]))
    args = sys.argv[1:]
    if len(args) != 1 or args[0] in ("-h", "--help", "--hilfe"):
        print(__doc__)
        return 0 if args else 2
    archiv_pfad = os.path.abspath(args[0])
    if not os.path.isdir(archiv_pfad):
        sys.exit(f"Fehler: {archiv_pfad} existiert nicht – Laufwerk eingehängt?")
    konfig.KONFIG = Konfig(os.path.abspath(os.path.expanduser(os.environ.get("BESTOF_CONF", "").strip()
                                                       or os.path.join(basis,
                                                                       "bestof.conf"))))
    port = _env("PORT", 8765, int)
    host = _env("HOST", "")
    bestof = _env("BESTOF", "BestOf")
    bestof = bestof if os.path.isabs(bestof) else os.path.join(archiv_pfad, bestof)
    vorschau_ordner = _env("VORSCHAU", os.path.join(archiv_pfad, ".vorschau"))
    if vorschau_ordner == "0":
        vorschau_ordner = None
    else:
        vorschau_ordner = os.path.abspath(os.path.expanduser(vorschau_ordner))
        try:
            os.makedirs(vorschau_ordner, exist_ok=True)
            probe = os.path.join(vorschau_ordner, ".schreibtest")
            with open(probe, "w") as f:
                f.write("ok")
            os.unlink(probe)
        except OSError as fehler:
            print(f"Hinweis: {vorschau_ordner} nicht beschreibbar ({fehler.strerror}) – Vorschaubilder nur im Arbeitsspeicher.")
            vorschau_ordner = None

    app = App()
    app.archiv = Archiv(archiv_pfad)
    app.auswahl = Auswahl(app.archiv, bestof, max(1, min(26, _env("MAX_BEST", 3, int))))
    app.vorschau = Vorschau(vorschau_ordner, max(0, _env("GROSS", 2048, int)))
    app.pro_seite = max(12, _env("PRO_SEITE", 120, int))
    app.passwort = _env("PASSWORT", "")
    app.gesichter = _env("GESICHTER", "1") != "0"
    app.ki = _env("KI", "1") != "0"  # KI-Suche „Ähnliche Fotos“ (CLIP)
    app.ki_beim_start = app.ki  # die Seite „Einstellungen“ ändert app.ki, wirksam erst nach dem Neustart
    app.aehnlich_min = min(99, max(0, _env("AEHNLICH_MIN", 72, int)))
    app.aehnlich_anzahl = min(1000, max(1, _env("AEHNLICH_ANZAHL", 150, int)))
    app.index_jobs = max(1, _env("INDEX_JOBS", max(1, (os.cpu_count() or 2) // 2), int))
    app.gpu = _env("GPU", "auto")
    app.gpu_jobs = max(0, _env("GPU_JOBS", 2, int))
    app.ort_min_ew = _env("ORT_MIN_EW", 10000, int)
    app.naehe_km = _env("NAEHE_KM", 15.0, float)
    app.person_schwelle = _env("PERSON_SCHWELLE", 0.40, float)
    app.nachziehen = _env("NACHZIEHEN", 0.50, float)
    app.abstand = min(0.3, max(0.0, _env("ABSTAND", 0.0, float)))
    app.lernen = _env("LERNEN", "1") != "0"
    app.lernen_ab = max(1, _env("LERNEN_AB", 5, int))
    app.lerner = None
    app.fotosort = os.path.abspath(os.path.expanduser(_env("FOTOSORT", os.path.join(
        basis, "fotosort.py"))))
    app.import_jobs = max(1, _env("IMPORT_JOBS", app.index_jobs, int))
    einzeln = _env("EINZELN", "ordner").lower()
    app.gruppe = {"SCHWELLE": min(128, max(0, _env("SCHWELLE", 20, int))),  # Ähnlichkeit für fotosort
                  "SERIE_SEK": min(86400.0, max(0.0, _env("SERIE_SEK", 3.0, float))),
                  "SERIE_SCHWELLE": min(128, max(0, _env("SERIE_SCHWELLE", 36, int))),
                  "EINZELN": einzeln if einzeln in ("ordner", "0000") else "ordner"}
    app.auftrag = None
    app.rechnungen, app.rechnungen_lock = OrderedDict(), threading.Lock()  # Analyse und Plan (fotosort)
    app.umzug_sperre = threading.Lock()  # Umzug läuft: der Index liest das Archiv erst danach
    app.erkenn_px = max(320, _env("ERKENN_PX", 1920, int))
    app.min_gesicht = max(8, _env("MIN_GESICHT", 48, int))
    app.gesicht_score = min(0.99, max(0.3, _env("GESICHT_SCORE", 0.50, float)))
    app.gegenprobe = min(0.99, max(0.0, _env("GEGENPROBE", 0.80, float)))
    app.sucher = None
    app.aktualisieren = max(30, _env("AKTUALISIEREN", 300, int))
    app.daten = os.path.abspath(os.path.expanduser(_env("DATEN", "~/.cache/fotosort")))
    comfyui = _env("COMFYUI", "http://127.0.0.1:8188")
    workflow_ordner = os.path.abspath(os.path.expanduser(_env("WORKFLOWS", os.path.join(basis, "workflows"))))
    farbe = None
    if comfyui != "0":
        farbe = Kolorierung(_env("COLORIZE_RESTORE_LORA", 0.0, float), _env("COLORIZE_LUMA_LOCK", "1") != "0",
                            _env("COLORIZE_CHROMA_BLUR", 0.0, float), _env("COLORIZE_PROMPT", ""),
                            _env("COLORIZE_KEEP_RAW", "0") != "0")
    vorwahl, farb_workflow = _env("VERBESSERN_WORKFLOW", ""), _env("FARBE_WORKFLOW", "")
    app.verbesserer = (None if comfyui == "0" else
                       Verbesserer(app, comfyui, workflow_ordner, farbe, vorwahl=vorwahl, farb_workflow=farb_workflow))
    app.workflow_ordner = workflow_ordner
    app.index, app.indexer = None, None
    if _env("INDEX", "1") != "0":
        try:
            app.index = Index(os.path.join(archiv_pfad, ".bestof-index.sqlite3"))
            app.indexer = Indexer(app)
            app.lerner = Lerner(app)
        except sqlite3.Error as fehler:
            print(f"Hinweis: Index nicht nutzbar ({fehler}) – ohne Metadaten und Filter.")
            app.index = None
    Handler.app = app

    try:
        server = server_starten(host, port)
    except OSError as fehler:
        sys.exit(f"Fehler: Port {port} auf {host or 'allen Netzwerken'} nicht nutzbar ({fehler.strerror}). "
                 f"Anderen PORT wählen.")
    server.daemon_threads = True
    app.port = port
    app.anfrage = threading.local()  # je Anfrage: kommt sie von diesem Rechner? (Handler._lokal)
    rechner = socket.gethostname().lower().rstrip(".")
    app.lokale_namen = {"localhost", rechner, rechner.split(".")[0], rechner.split(".")[0] + ".local"}
    app.import_erlaubt = _env("IMPORT", "1") != "0"  # und nur für Anfragen von diesem Rechner
    netz = server.server_address[0] in ("::", "0.0.0.0")
    nur_hier = host in ("127.0.0.1", "localhost", "::1")
    adresse = f"http://{'127.0.0.1' if netz or nur_hier else (f'[{host}]' if ':' in host else host)}:{port}"
    print(f"bestof {VERSION}")
    print(f"Archiv:   {archiv_pfad}  ({len(app.archiv.ordner())} Ordner, "
          f"{bilder_text(app.auswahl.anzahl_bilder())} mit Stern)")
    print(f"BestOf:   {bestof}")
    print(f"Vorschau: {vorschau_ordner or 'nur Arbeitsspeicher'}")
    print(f"Index:    {'aus' if not app.index else app.index.pfad + f' ({app.index_jobs} Prozesse)'}")
    print(f"Einstellungen: {konfig.KONFIG.pfad} – Personen: Schwelle {app.person_schwelle:.2f} "
          f"({konfig.QUELLE.get('PERSON_SCHWELLE')}), Abstand {app.abstand:.2f} ({konfig.QUELLE.get('ABSTAND')}), "
          f"Lernen {'an, ab ' + str(app.lernen_ab) + ' Korrekturen' if app.lernen else 'aus'}")
    if app.verbesserer:
        brauchbar = app.verbesserer.workflows.brauchbar()
        print(f"Verbessern: ComfyUI {comfyui} ({'erreichbar' if app.verbesserer.comfy.erreichbar() else 'nicht erreichbar'})"
              f" · {len(brauchbar)} Workflow{'' if len(brauchbar) == 1 else 's'} in {workflow_ordner}"
              + (f": {', '.join(w['name'] for w in brauchbar)}" if brauchbar else ""))
        for w in app.verbesserer.workflows.liste():
            if w["fehler"]:
                print(f"Hinweis: Workflow {w['datei']} übersprungen – {w['fehler']}.")
        if farbe.bereit:
            koennen = [w["name"] for w in brauchbar if w["farbe"]]
            fw = app.verbesserer.farb_wf()
            print(f"Kolorieren: ffmpeg {farbe.version}, Restore-LoRA {farbe.restore_lora:g}"
                  f"{', ohne Luma-Lock' if not farbe.luma else ''} · "
                  + (f"Workflow {fw['name']}" if fw else f"Workflows: {', '.join(koennen) or 'keiner geeignet'}"))
        else:
            print(f"Kolorieren aus: {farbe.grund} (z. B. sudo apt install ffmpeg).")
    print(f"Adresse:  {adresse}")
    if netz:
        print(f"Heimnetz: http://{rechner.split('.')[0]}:{port}  ·  http://{lokale_ip()}:{port}"
              f"  (Import nur an diesem Rechner)")
    elif nur_hier:
        print("Nur auf diesem Rechner erreichbar (HOST = 127.0.0.1).")
    if not nur_hier and not app.passwort:
        print("Hinweis: Ohne PASSWORT kann jeder im Heimnetz die Fotos sehen, Sterne, Alben und Namen ändern und "
              "Fotos in den Papierkorb schieben – importieren geht nur hier, endgültig löschen gar nicht.")
    print("Strg+C beendet.", flush=True)
    if app.indexer:
        app.indexer.start()
    if app.lerner:
        app.lerner.start()
        app.lerner.anstossen()  # Korrekturen aus der letzten Sitzung?
    if _env("BROWSER", "1") != "0":
        threading.Timer(0.8, lambda: webbrowser.open(adresse)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        if app.indexer:
            app.indexer.stoppen()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
