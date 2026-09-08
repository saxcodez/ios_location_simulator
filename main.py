#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
iOS Location Simulator - Windows
================================
Simuliert die GPS-Position eines per USB verbundenen iPhones.
Nur fuer Test- und Entwicklungszwecke auf eigenen Geraeten.

Start:  python main.py
"""

import sys


def main() -> int:
    if sys.version_info < (3, 9):
        print("Python 3.9 oder neuer wird benoetigt.")
        return 1
    try:
        from ui import App
    except ImportError as e:
        print("Abhaengigkeit fehlt:", e)
        print("Bitte ausfuehren:  pip install -r requirements.txt")
        return 1
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
