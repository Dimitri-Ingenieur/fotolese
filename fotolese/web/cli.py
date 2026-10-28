"""
bestof.py – Weboberfläche: Fotos durchsehen, filtern, je Ordner bis zu 3 beste Bilder auswählen.

Auswahl -> sofort Kopie in SORTIERT/BestOf:
  1 Bild ausgewählt    -> 0001.jpg
  2–3 Bilder           -> 0001a.jpg, 0001b.jpg, 0001c.jpg  (a = zuerst ausgewählt)
NEF-Dateien werden nicht angezeigt – fotosort.py legt zu jedem NEF ein JPG an.

Im Hintergrund entsteht ein Index (SORTIERT/.bestof-index.sqlite3):
  * Datum aus den EXIF-Daten (sonst aus dem Dateinamen), GPS -> nächster größerer Ort (GeoNames, offline)
  * Gesichter -> Personen (Person 1, Person 2 …), auf der Seite „Personen“ benennbar
Jahr:
  Jedes Bild hat ein Jahresfeld, vorausgefüllt aus EXIF oder Dateiname. Falsch (Scan, Kamerauhr,
  WhatsApp)? Jahr eintippen, Enter. Gelb = von Hand gesetzt; leeren + Enter = wieder Jahr aus der Datei.
  „für alle Bilder“ auf der Ordnerseite setzt das Jahr für den ganzen Ordner. Ein von Hand gesetztes Jahr
  ersetzt auch den Monat (gilt dann als unbekannt). Gespeichert im Index, die Bilddateien bleiben unverändert.
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
Import (Seite „Import“, braucht fotosort.py neben bestof.py):
  Ordner im Browser wählen, „In Sortiert kopieren“. fotosort.py kopiert alle Fotos samt Unterordnern (Quelle
  bleibt unverändert), sortiert ähnliche in Ordner, ergänzt passende bestehende, legt zu NEF ein JPG an.
  Inhaltsgleiche Dateien (SHA-256) kommen nur einmal ins Archiv; danach behält das Archiv von jedem Inhalt
  genau eine Datei (bevorzugt: in BestOf ausgewählt, mit Labels, ohne Laufindex). Überzählige wandern in den
  Papierkorb SORTIERT/.duplikate/<Zeit>/ (mit liste.csv), „Papierkorb leeren“ löscht sie.
  „Abbrechen“ stoppt nach dem laufenden Ordner, „Import rückgängig“ entfernt die Kopien des letzten Imports.
Ordneransicht: unter jedem Foto Auflösung, Dateigröße und – falls vorhanden – Größe der NEF-Datei;
  die höchste Auflösung im Ordner ist gelb markiert.
Alben (Seite „Alben“: anlegen, umbenennen, löschen):
  Ein Foto kann in beliebig vielen Alben stehen; unter jedem Foto stehen seine Alben, ein Klick darauf filtert.
  Markieren: über den Fotos „Fotos markieren für Album …“ wählen (oder „Neues Album“), dann ＋ unter den Fotos
  (Umschalt = alle bis zum zuletzt angeklickten) oder in der Lupe Taste A; „Alle hinzufügen“ nimmt den ganzen
  Ordner bzw. alle Treffer des Filters. Ohne gewähltes Album öffnet ＋ die Liste aller Alben zum Ankreuzen.
  Gespeichert im Index; doppelte Dateien geben ihre Alben an die behaltene Datei weiter.
Einstellungen und Lernen (bestof.conf neben bestof.py, wird beim ersten Start angelegt):
  NAME = Wert je Zeile; Umgebungsvariablen haben Vorrang. Jede Korrektur einer automatischen Zuordnung
  (Gesicht „Thomas“ ist in Wahrheit „Paul“) und jede Bestätigung (Schild anklicken + Enter, „Ausgewählte
  bestätigen“) ist ein Label. Nach LERNEN_AB Korrekturen stellt bestof.py PERSON_SCHWELLE und ABSTAND so ein,
  dass diese Fehler nicht wieder passieren, ohne bestätigte Gesichter zu verlieren, schreibt sie in bestof.conf
  und verschiebt automatisch zugeordnete Gesichter, die eindeutig zu einer anderen benannten Person passen.
  Ihre eigenen Zuordnungen bleiben unangetastet. Auf „Personen“ steht der Lernstand, „Jetzt lernen“ startet es sofort.
Filter im Suchfeld, Begriffe mit Komma trennen:
  2023, Leipzig, Anna    -> Fotos aus 2023, höchstens NAEHE_KM von Leipzig, auf denen Anna ist
  Juli 2023 | 2023-07 | 0012 (Ordner) | Person 7 | ohne Jahr | Jahr korrigiert | Teil eines Dateinamens
  Album Urlaub (oder nur Urlaub) | ohne Album   -> mehrere Alben: Fotos aus einem davon

Aufruf (Conda-Umgebung von fotosort.py):
  python -m pip install opencv-python-headless   # nur für die Gesichtserkennung nötig
  python bestof.py /media/$USER/EXTERN/Sortiert

Tasten im Ordner:  ← / →  voriger / nächster Ordner,  N  nächster Ordner ohne Auswahl
Tasten in der Lupe: ← / →  Bild,  Leertaste  aus- / abwählen,  G  Gesichter zeigen,  J  Jahr ändern,  Esc  schließen,
                    A  Album: ins gewählte Album aufnehmen/herausnehmen, sonst Alben zuordnen
                    (Namensschild anklicken = benennen: ganze Gruppe oder nur dieses Gesicht;
                     Gesicht fehlt = bei eingeblendeten Gesichtern ins Gesicht klicken)

Umgebungsvariablen (Standard in Klammern):
  PORT       (8765)
  HOST       (127.0.0.1)   0.0.0.0 = auch von Tablet/Handy im Heimnetz (dann PASSWORT setzen)
  PASSWORT   ()            Passwortschutz, Benutzername beliebig
  MAX_BEST   (3)           höchstens so viele Bilder je Ordner
  BESTOF     (BestOf)      Zielordner, relativ zu SORTIERT oder absolut
  VORSCHAU   (SORTIERT/.vorschau)  Ordner für Vorschaubilder, 0 = nur Arbeitsspeicher
  GROSS      (2048)        Kantenlänge der Lupe in Pixel, 0 = Originaldatei
  PRO_SEITE  (120)         Ordner je Übersichtsseite
  BROWSER    (1)           Browser beim Start öffnen
  INDEX      (1)           0 = kein Index (keine Metadaten, Orte, Personen, Filter)
  GESICHTER  (1)           0 = keine Gesichtserkennung
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
  IMPORT     (1)           0 = Seite „Import“ aus (ohne PASSWORT ohnehin nur bei HOST=127.0.0.1)
  IMPORT_JOBS (Kerne/2)    parallele Prozesse für fotosort beim Import (HDD/USB: z. B. 2–4)
  FOTOSORT   (fotosort.py neben bestof.py)
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
import os
import socket
import sqlite3
import sys
import threading
import webbrowser
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


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Abgebrochene Verbindungen (Tab zu, Browser beendet) sind normal – keinen Traceback ins Terminal."""
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


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
    host = _env("HOST", "127.0.0.1")
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
    app.auftrag = None
    app.erkenn_px = max(320, _env("ERKENN_PX", 1920, int))
    app.min_gesicht = max(8, _env("MIN_GESICHT", 48, int))
    app.gesicht_score = min(0.99, max(0.3, _env("GESICHT_SCORE", 0.50, float)))
    app.gegenprobe = min(0.99, max(0.0, _env("GEGENPROBE", 0.80, float)))
    app.sucher = None
    app.aktualisieren = max(30, _env("AKTUALISIEREN", 300, int))
    app.daten = os.path.abspath(os.path.expanduser(_env("DATEN", "~/.cache/fotosort")))
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
        server = Server((host, port), Handler)
    except OSError as fehler:
        sys.exit(f"Fehler: Port {port} auf {host} nicht nutzbar ({fehler.strerror}). Anderen PORT wählen.")
    server.daemon_threads = True
    lokal = host in ("127.0.0.1", "localhost", "::1")
    app.import_erlaubt = _env("IMPORT", "1") != "0" and (lokal or bool(app.passwort))
    adresse = f"http://{'127.0.0.1' if lokal or host == '0.0.0.0' else host}:{port}"
    print(f"bestof {VERSION}")
    print(f"Archiv:   {archiv_pfad}  ({len(app.archiv.ordner())} Ordner, "
          f"{bilder_text(app.auswahl.anzahl_bilder())} ausgewählt)")
    print(f"BestOf:   {bestof}")
    print(f"Vorschau: {vorschau_ordner or 'nur Arbeitsspeicher'}")
    print(f"Index:    {'aus' if not app.index else app.index.pfad + f' ({app.index_jobs} Prozesse)'}")
    print(f"Einstellungen: {konfig.KONFIG.pfad} – Personen: Schwelle {app.person_schwelle:.2f} "
          f"({konfig.QUELLE.get('PERSON_SCHWELLE')}), Abstand {app.abstand:.2f} ({konfig.QUELLE.get('ABSTAND')}), "
          f"Lernen {'an, ab ' + str(app.lernen_ab) + ' Korrekturen' if app.lernen else 'aus'}")
    print(f"Adresse:  {adresse}" + (f"  ·  im Heimnetz: http://{lokale_ip()}:{port}" if host == "0.0.0.0" else ""))
    if not lokal and not app.passwort:
        print("Warnung: ohne PASSWORT kann jeder im Netz die Fotos sehen und die Auswahl ändern.")
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
