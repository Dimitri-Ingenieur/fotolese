#!/usr/bin/env python3
"""bestof.py – Starter.

Weboberfläche zum Durchsehen und Filtern; die besten Fotos je Ordner bekommen einen Stern.
Die Funktionalität liegt im Paket fotolese.web; die vollständige Hilfe zeigt
    python bestof.py -h

Der Ordner dieses Starters gilt als „neben bestof.py“: hier sucht bestof.py die
Datei bestof.conf und fotosort.py (für die Seite „Import“).
"""
import os
import sys

from fotolese.web.cli import main

if __name__ == "__main__":
    sys.exit(main(os.path.dirname(os.path.abspath(__file__))))
