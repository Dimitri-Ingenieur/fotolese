"""fotolese.sort – fotosort: Fotos einsammeln, ähnliche gruppieren, verschieben.

Thematische Module:
  konst   – Konstanten und Erweiterungslisten
  exif    – EXIF/Zeit aus Bildern lesen
  bild    – Graustufen, Wahrnehmungs-Hashes, Bild-/NEF-Analyse (Prozess-Pool)
  nef     – NEF lesen und verlustfrei ein JPG daraus erzeugen
  cache   – Analyse-Ergebnisse in SQLite zwischenspeichern
  suche   – Eingabe und Bestand im Dateisystem finden
  gruppe  – Duplikate, Gruppierung ähnlicher Bilder, Anker im Bestand
  plan    – Zielnamen und Verschiebeplan
  lauf    – Ausführung (verschieben/kopieren), Protokoll, Rückgängig
  cli     – Kommandozeile (main)
"""
import os

# 32 Prozesse x 32 BLAS-Threads vermeiden – muss vor dem ersten numpy-Import stehen.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
