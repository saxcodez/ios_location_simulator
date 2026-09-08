<div align="center">

**🇬🇧 [English](README.md) | 🇩🇪 Deutsch**

</div>

<div align="center">

# 📍 iOS Location Simulator

**GPS-Positionen auf einem per USB verbundenen iPhone simulieren - von Windows aus, ohne Mac.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](#)

*by [saxcodez](https://github.com/saxcodez)*

</div>

---

Ein Windows-Tool zur Simulation von GPS-Standorten auf einem angeschlossenen
iPhone - mit klickbarer Karte, Routenplanung, Bewegungssimulation und
automatischer Erkennung des angeschlossenen iPhones. Läuft für **alle
iOS-Versionen von 12 bis 26**, mit oder ohne Entwicklermodus-Vorwissen.

> ⚠️ **Nur für eigene Geräte und Testzwecke.** Gedacht für App-Entwickler und
> Tester, die Standort-abhängiges Verhalten prüfen wollen, ohne physisch
> woanders hinzufahren.

---

## Inhalt

- [Funktionen](#funktionen)
- [Installation](#installation)
- [Erste Schritte am iPhone](#erste-schritte-am-iphone)
- [Bedienung](#bedienung)
- [Unterstützte iOS-Versionen](#unterstützte-ios-versionen)
- [Funktionsweise](#funktionsweise)
- [Fehlersuche](#fehlersuche)
- [Aus dem Quellcode bauen](#aus-dem-quellcode-bauen)
- [Mitmachen](#mitmachen)
- [Lizenz](#lizenz)

---

## Funktionen

| | |
|---|---|
| 🗺️ **Teleport** | Linksklick auf die Karte, manuelle Koordinaten oder gespeicherte Orte |
| 🖱️ **Rechtsklick-Menü** | Hierher teleportieren - als Start/Ziel setzen - Koordinaten kopieren |
| 🛣️ **Routenplanung** | Von/Nach per Adresssuche oder Kartenklick, echte Straßenrouten (OSRM) |
| 🚗 **Bewegungssimulation** | Zu Fuß / Fahrrad / Auto, Tempo 1-200 km/h, Pause/Stopp, Schleife |
| 💾 **Gespeicherte Orte & Routen** | Plus "Zuletzt verwendet" |
| 📤 **Export/Import** | Orte & Routen als JSON sichern - praktisch beim Geräte- oder Rechnerwechsel |
| 🔌 **Automatische Geräteerkennung** | iPhone einstecken, fertig - keine manuelle UDID-Eingabe |
| 📶 **Alle iOS-Versionen** | 12-26, automatische Wahl des richtigen Verbindungswegs |
| 🛠️ **Entwicklermodus-Aktivierung** | Per Klick (sofern kein Sperrcode gesetzt ist) |
| 🟢 **Live-Simulationsstatus** | Zeigt jederzeit, ob gerade eine Position aktiv gesetzt ist |
| 🌍 **Deutsch/Englisch** | Sprachumschaltung direkt in der Oberfläche |
| 📄 **Log-Export** | Für Fehlersuche und Support |

---

## Installation

### Variante A - Fertiger Installer (empfohlen)

1. Neueste Version von der [Releases-Seite](../../releases) herunterladen
   (`iOSLocationSimulator-Setup.exe` oder das portable ZIP)
2. Ausführen - kein Python, kein `pip`, keine PowerShell-Befehle nötig
3. Zusätzlich benötigt: **Apple-USB-Treiber** - ["Apple Devices"](https://apps.microsoft.com/detail/9np83lwlpz9k)
   aus dem Microsoft Store oder klassisches iTunes von apple.com

### Variante B - Aus dem Quellcode

```powershell
git clone https://github.com/saxcodez/ios-location-simulator.git
cd ios-location-simulator
pip install -r requirements.txt
python main.py
```

Python 3.9+ genügt, 3.12 empfohlen (siehe [Fehlersuche](#fehlersuche) für den Hintergrund).

---

## Erste Schritte am iPhone

1. Per USB anschließen, entsperren, **"Diesem Computer vertrauen"** bestätigen
2. Einstellungen -> Datenschutz & Sicherheit -> **Entwicklermodus** einschalten
   (im Tool auch per Klick anstoßbar - funktioniert nur ohne Gerätesperrcode)
3. Bei iOS 17 und neuer: Das Tool startet den nötigen Tunnel (`tunneld`) beim
   ersten Verbinden automatisch selbst; einmalig muss dafür `wintun.dll`
   eingerichtet werden - ebenfalls ein Klick im Tool

---

## Bedienung

**Teleport:** Punkt auf der Karte anklicken -> *Position setzen*. Oder
Koordinaten direkt eintippen - `53.5503, 9.9922` ins Breitenfeld eingefügt
wird automatisch auf beide Felder verteilt.

**Route abfahren:**
1. Start und Ziel setzen (Adresssuche, Kartenklick oder Rechtsklick-Menü)
2. Fortbewegungsart wählen
3. *Route berechnen*, Tempo einstellen, *Start*

**Zurück zum echten GPS:** Button *Echtes GPS wiederherstellen*, oder
einfach *Trennen* - beim Beenden fragt das Tool ebenfalls nach.

---

## Unterstützte iOS-Versionen

| iOS | Verbindungsweg | Besonderheit |
|---|---|---|
| 12 - 16 | `lockdown` direkt über USB | Einmaliger Befehl, Position bleibt auch nach Abstecken aktiv |
| 17 - 26 | RemoteXPC-Tunnel (`tunneld`) | Position bleibt nur aktiv, solange die Verbindung steht (wie bei Xcodes "Simulate Location") |

Das Tool erkennt die Version selbst und wählt automatisch den passenden Weg.

---

## Funktionsweise

Unter der Haube nutzt das Tool
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - dieselbe
offene Bibliothek, die auch Xcodes eigene Standort-Simulation im Kern
verwendet. Angesprochen wird ausschließlich über dessen Kommandozeile, nicht
über interne Python-Klassen: die ändern sich zwischen Versionen von
pymobiledevice3 spürbar häufiger als die öffentliche CLI, was das Tool
deutlich robuster gegen zukünftige Updates macht.

---

## Fehlersuche

Erste Anlaufstelle bei Problemen:

```powershell
python diagnose.py
```

Prüft der Reihe nach die komplette Kette (Python, pymobiledevice3, Apple-USB-Dienst,
Geräteerkennung, Developer Disk Image, Tunnel) und sagt bei jedem Schritt,
was zu tun ist.

Häufige Stolpersteine:

| Symptom | Ursache |
|---|---|
| Kein Gerät in der Liste | Apple-Treiber fehlt, reines Ladekabel, oder "Vertrauen" nicht bestätigt |
| "Developer Mode is disabled" | Entwicklermodus aktivieren (Button im Tool oder manuell in den Einstellungen) |
| Position ändert sich nicht am Gerät | Bei iOS 17+ muss die Verbindung aktiv bleiben - siehe Live-Simulationsstatus im Tool |
| `pip install` schlägt mit Compiler-Fehler fehl | Python 3.14 hat noch keine fertigen Wheels für alle Abhängigkeiten - Python 3.12 verwenden |

---

## Aus dem Quellcode bauen

Einen eigenen Windows-Installer erzeugen (einmalig, auf einem Windows-Rechner
mit Python 3.12):

```powershell
powershell -ExecutionPolicy Bypass -File build_installer.ps1
```

Details dazu - inklusive warum dabei zwei `.exe`-Dateien entstehen - im
Skript selbst kommentiert. Mit installiertem
[Inno Setup](https://jrsoftware.org/isdl.php) entsteht eine fertige
`Setup.exe`, sonst automatisch ein portables ZIP als Fallback.

Bei jedem gepushten Versions-Tag (`vX.Y.Z`) baut GitHub Actions denselben
Installer automatisch und hängt ihn ans zugehörige Release an - siehe
[`.github/workflows/release.yml`](.github/workflows/release.yml).

---

## Mitmachen

Bug-Reports, Feature-Wünsche und Pull Requests sind willkommen - siehe
[CONTRIBUTING.md](CONTRIBUTING.md). Änderungen an der Oberfläche bitte über
`i18n.py` laufen lassen, damit die Sprachumschaltung konsistent bleibt.

## Lizenz

[MIT](LICENSE) © 2026 [saxcodez](https://github.com/saxcodez)
