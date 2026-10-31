"""fotolese.web – bestof: Weboberfläche zum Durchsehen und Filtern; die besten Fotos bekommen einen Stern.

Thematische Module:
  konst       – Konstanten, Muster, Monatsnamen, Modell-Quellen
  konfig      – bestof.conf lesen/schreiben, Einstellungen (_env), Text-/Zeitformate
  archiv      – Zugriff auf den Sortiert-Ordner (Ordner, Bilder, BestOf-Pfade)
  bild        – Vorschaubilder erzeugen und zwischenspeichern
  orte        – GeoNames-Orte offline (GPS -> nächster größerer Ort)
  auswahl     – Sterne (BestOf-Auswahl) je Ordner lesen/schreiben
  papierkorb  – Fotos in den Papierkorb SORTIERT/Musor schieben und zurückholen (nie endgültig löschen)
  alben       – Alben anlegen, Fotos zuordnen (je Foto beliebig viele), API für Leiste, Dialog und Seite „Alben“
  index       – SQLite-Index und Hintergrund-Indexer (Thread)
  gesichter   – Gesichtserkennung (YuNet/SFace) im Prozess-Pool, Nachsuche
  gpu         – Gesichtsmodelle auf der GPU (ONNX Runtime/OpenCV): Auswahl, Prüfung, Rückfall auf die CPU
  suche       – Suchanfragen auswerten (Jahr, Ort, Person, Dateiname)
  html        – Seiten und Bausteine der Oberfläche
  server      – HTTP-Server, Handler und Aktionen (Jahr/Person/Gesicht ändern)
  lernen      – aus Korrekturen Schwelle/Abstand lernen (Thread)
  importieren – Ordner über fotosort ins Archiv holen, Duplikate bereinigen (nur an diesem Rechner)
  cli         – Start (main)
"""
