# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier festgehalten.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/).

## [1.0.0] - 2026

### Hinzugefügt
- Teleport per Kartenklick, manueller Koordinateneingabe oder gespeicherten Orten
- Rechtsklick-Menü auf der Karte (teleportieren, als Start/Ziel setzen, Koordinaten kopieren)
- Routenplanung (Adresssuche oder Kartenklick) mit echten Straßenrouten über OSRM
- Bewegungssimulation entlang einer Route (zu Fuß / Fahrrad / Auto, 1-200 km/h, Pause/Stopp, Schleife)
- Gespeicherte Orte, gespeicherte Routen und "Zuletzt verwendet"
- Automatische USB-Geräteerkennung, Unterstützung für iOS 12-26
- Automatische Wahl des richtigen Verbindungswegs (lockdown für iOS ≤16, RemoteXPC-Tunnel für iOS ≥17)
- Live-Status, ob die simulierte Position gerade aktiv ist
- Entwicklermodus-Aktivierung per Klick (sofern kein Sperrcode gesetzt ist)
- Sprachumschaltung Deutsch/Englisch für die Oberfläche
- Log-Export als Textdatei
- Export/Import von Orten und Routen (JSON-Backup, z. B. für Geräte- oder Rechnerwechsel)
- Automatisierter Windows-Installer-Build (PyInstaller + Inno Setup) über `build_installer.ps1`
- GitHub-Actions-Workflows: Smoke-Test bei jedem Push, automatischer Installer-Build bei jedem Versions-Tag
