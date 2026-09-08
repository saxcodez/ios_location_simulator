#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Duenner Einstiegspunkt, der zu einer eigenstaendigen 'pmd3.exe' gebaut wird.

Grund fuer diese Extra-Datei: Sobald main.py mit PyInstaller zu einer .exe
gefroren wird, zeigt sys.executable auf diese GUI-exe, nicht mehr auf einen
echten Python-Interpreter. device.py ruft aber an vielen Stellen
'sys.executable -m pymobiledevice3 ...' als Unterprozess auf (usbmux list,
mounter auto-mount, developer dvt simulate-location, tunneld, amfi, ...).
Ohne diesen Wrapper wuerde das im gebauten Installer ins Leere laufen.

Diese Datei wird deshalb GETRENNT von main.py zu einer zweiten,
eigenstaendigen Konsolen-exe (pmd3.exe) gebaut, die pymobiledevice3
mitbringt. device.py erkennt den gefrorenen Zustand automatisch (siehe
pymobiledevice3_command() in device.py) und ruft dann diese exe anstelle
von 'python -m pymobiledevice3' auf. Im normalen Python-Betrieb (nicht
gefroren) wird diese Datei gar nicht gebraucht.

Bewusst ueber runpy statt ueber einen direkten Funktionsimport (z.B.
'from pymobiledevice3.__main__ import cli'): der Name der intern
aufgerufenen Funktion in __main__.py hat sich zwischen pymobiledevice3-
Versionen bereits mehrfach geaendert (mal 'cli', mal 'main', ...). runpy
fuehrt das Modul exakt so aus, wie es 'python -m pymobiledevice3' auch
tun wuerde, unabhaengig davon, wie die Funktion intern gerade heisst.
"""

import runpy
import sys

if __name__ == "__main__":
    sys.argv[0] = "pymobiledevice3"
    runpy.run_module("pymobiledevice3.__main__", run_name="__main__")
