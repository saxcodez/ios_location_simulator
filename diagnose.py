#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Diagnose fuer den iOS Location Simulator.

Prueft dieselbe Kette, die device.py auch benutzt (rein ueber die
pymobiledevice3-CLI, keine internen Python-Klassen), und sagt bei jedem
Schritt, was zu tun ist.

Start:  python diagnose.py
"""

import json
import os
import socket
import subprocess
import sys

OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FEHL]"
problems = []


def line(status, text, hint=""):
    print(f"{status} {text}")
    if hint:
        for h in hint.splitlines():
            print(f"       {h}")
    if status == FAIL:
        problems.append(text)


def head(text):
    print()
    print(text)
    print("-" * len(text))


def run(args, timeout=30):
    cmd = [sys.executable, "-m", "pymobiledevice3"] + args
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=flags, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or "") + (e.stderr or "")
    except FileNotFoundError as e:
        return -1, str(e)


# ---------------------------------------------------------------- Python
head("1. Python")
print(f"       Interpreter: {sys.executable}")
print(f"       Version:     {sys.version.split()[0]}")
if sys.version_info < (3, 9):
    line(FAIL, "Python zu alt", "Python 3.9 oder neuer installieren.")
else:
    line(OK, "Python-Version ausreichend")

# ------------------------------------------------------- pymobiledevice3
head("2. pymobiledevice3")
try:
    import pymobiledevice3
    ver = getattr(pymobiledevice3, "__version__", "unbekannt")
    line(OK, f"importierbar (Version {ver})")
    print(f"       Pfad: {os.path.dirname(pymobiledevice3.__file__)}")
except ImportError as e:
    line(FAIL, "nicht importierbar",
         f"{e}\n"
         "Genau mit DIESEM Interpreter installieren:\n"
         f'  "{sys.executable}" -m pip install pymobiledevice3')

# ------------------------------------------------------------ tkintermapview
head("3. tkintermapview (Karte, optional)")
try:
    import tkintermapview  # noqa: F401
    line(OK, "vorhanden")
except ImportError:
    line(WARN, "fehlt - Tool laeuft, aber ohne Karte",
         f'"{sys.executable}" -m pip install tkintermapview')

# ------------------------------------------------- Apple Mobile Device Service
head("4. Apple-Geraetedienst")
if os.name == "nt":
    found = False
    for name in ("Apple Mobile Device Service", "AppleMobileDeviceService"):
        try:
            p = subprocess.run(["sc", "query", name], capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
        except Exception:
            break
        if p.returncode == 0:
            found = True
            state = "RUNNING" if "RUNNING" in p.stdout.upper() else "GESTOPPT"
            if state == "RUNNING":
                line(OK, f"Dienst '{name}' laeuft")
            else:
                line(FAIL, f"Dienst '{name}' ist gestoppt",
                     f'In einer Admin-Konsole starten:\n  net start "{name}"')
            break
    if not found:
        line(FAIL, "Dienst nicht gefunden",
             "Es fehlt der Apple-USB-Treiber. Installieren:\n"
             "  - iTunes von apple.com (klassisches Setup, nicht Store), ODER\n"
             "  - 'Apple Devices' aus dem Microsoft Store\n"
             "Danach Rechner neu starten.")
else:
    line(WARN, "Kein Windows - hier uebernimmt usbmuxd diese Rolle")

# ---------------------------------------------------------------- usbmux Port
head("5. usbmux-Schnittstelle (127.0.0.1:27015)")
if os.name == "nt":
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect(("127.0.0.1", 27015))
        line(OK, "erreichbar")
    except Exception as e:
        line(FAIL, "nicht erreichbar", f"{e}\nSiehe Schritt 4.")
    finally:
        s.close()
else:
    line(WARN, "uebersprungen (nur Windows)")

# ---------------------------------------------------------------- Geraeteliste
head("6. Angeschlossene Geraete (pymobiledevice3 usbmux list)")
devices = []
code, out = run(["usbmux", "list"])
if code != 0:
    line(FAIL, "Befehl fehlgeschlagen", out.strip()[-1000:])
else:
    try:
        start = out.index("[")
        devices = json.loads(out[start:])
    except Exception as e:
        line(FAIL, "Ausgabe nicht als JSON lesbar", f"{e}\n{out.strip()[-600:]}")
    if not devices:
        line(FAIL, "keine Geraete gemeldet",
             "Pruefen:\n"
             " - iPhone entsperrt?\n"
             " - 'Diesem Computer vertrauen' bestaetigt? (sonst Kabel neu "
             "einstecken)\n"
             " - Datenkabel, kein reines Ladekabel?\n"
             " - direkt am Rechner statt am USB-Hub?\n"
             " - Geraete-Manager: taucht 'Apple Mobile Device USB Device' auf?")
    else:
        for d in devices:
            ctype = d.get("ConnectionType", "USB")
            name = d.get("DeviceName", "?")
            ver = d.get("ProductVersion", "?")
            udid = d.get("Identifier") or d.get("UniqueDeviceID")
            line(OK, f"{name} - iOS {ver} - {udid}  ({ctype})")

usb_devices = [d for d in devices if str(d.get("ConnectionType", "USB")).upper() == "USB"]

# ------------------------------------------------------------ DDI mounten
head("7. Developer Disk Image")
if not usb_devices:
    line(WARN, "uebersprungen - kein Geraet per USB")
else:
    for d in usb_devices:
        udid = d.get("Identifier") or d.get("UniqueDeviceID")
        code, out = run(["mounter", "auto-mount", "--udid", udid], timeout=120)
        low = out.lower()
        if code == 0 or "already" in low or "mounted" in low:
            line(OK, f"{udid}: gemountet oder bereits gemountet")
        else:
            line(FAIL, f"{udid}: Mounten fehlgeschlagen",
                 "Entwicklermodus aktiv? iPhone entsperrt? 'Vertrauen' "
                 f"bestaetigt?\n{out.strip()[-800:]}")

# --------------------------------------------------------------------- wintun
head("8. wintun.dll (nur iOS 17+)")
here = os.path.dirname(os.path.abspath(__file__))
if os.name != "nt":
    line(WARN, "uebersprungen (nur Windows)")
elif os.path.exists(os.path.join(here, "wintun.dll")):
    line(OK, f"vorhanden in {here}")
else:
    line(WARN, "fehlt",
         "Im Tool auf 'wintun.dll einrichten' klicken, oder manuell von "
         f"https://www.wintun.net nach {here} kopieren.")

# --------------------------------------------------------------------- tunneld
head("9. tunneld (nur iOS 17+)")
tunnel_info = {}
try:
    import urllib.request
    with urllib.request.urlopen("http://127.0.0.1:49151/", timeout=3) as r:
        tunnel_info = json.loads(r.read().decode())
    if tunnel_info:
        for udid, entries in tunnel_info.items():
            line(OK, f"Tunnel fuer {udid}: {entries}")
    else:
        line(WARN, "laeuft, kennt aber kein Geraet",
             "iPhone abziehen, anstecken, entsperren, tunneld neu starten.")
except Exception:
    line(WARN, "nicht erreichbar",
         "Nur noetig ab iOS 17. Admin-Konsole im Tool-Ordner:\n"
         "  python -m pymobiledevice3 remote tunneld")

# ----------------------------------------------------- simulate-location Test
head("10. Location-Simulation ansprechbar? (--help, aendert nichts)")
if not usb_devices:
    line(WARN, "uebersprungen - kein Geraet per USB")
for d in usb_devices:
    udid = d.get("Identifier") or d.get("UniqueDeviceID")
    ver = str(d.get("ProductVersion", "0"))
    try:
        major = int(ver.split(".")[0])
    except ValueError:
        major = 0

    if major >= 17:
        entries = tunnel_info.get(udid) or [e for v in tunnel_info.values() for e in v]
        if not entries:
            line(WARN, f"{udid}: uebersprungen - kein Tunnel (siehe Schritt 9)")
            continue
        host = entries[0].get("tunnel-address") or entries[0].get("address")
        port = entries[0].get("tunnel-port") or entries[0].get("port")
        code, out = run(["developer", "dvt", "simulate-location", "--rsd",
                         str(host), str(port), "--help"], timeout=25)
    else:
        env = dict(os.environ)
        env["PYMOBILEDEVICE3_UDID"] = udid
        cmd = [sys.executable, "-m", "pymobiledevice3",
               "developer", "simulate-location", "--help"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                               creationflags=flags, encoding="utf-8",
                               errors="replace", env=env)
            code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired as e:
            code, out = None, (e.stdout or "") + (e.stderr or "")

    if code == 0:
        line(OK, f"{udid}: Location-Simulation erreichbar")
    else:
        line(FAIL, f"{udid}: nicht erreichbar", out.strip()[-1000:])

# --------------------------------------------------------------------- Fazit
print()
print("=" * 60)
if problems:
    print("Offene Punkte (von oben nach unten abarbeiten):")
    for p in problems:
        print(f"  - {p}")
else:
    print("Keine harten Fehler gefunden - das Tool sollte funktionieren.")
print("=" * 60)
