#!/usr/bin/env python3
"""fotosort.py – Starter.

Fotos einsammeln, ähnliche gruppieren und in nummerierte Ordner verschieben.
Die Funktionalität liegt im Paket fotolese.sort; die vollständige Hilfe zeigt
    python fotosort.py -h
"""
import sys

from fotolese.sort.cli import main

if __name__ == "__main__":
    sys.exit(main())
