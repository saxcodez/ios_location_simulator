# build_installer.ps1
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
#
# Baut aus diesem Projektordner einen fertigen Windows-Installer, den man
# als eine einzelne Datei weitergeben kann - ohne dass der Endnutzer Python,
# pip oder sonst etwas manuell installieren muss.
#
# EINMALIG auf einem Windows-Rechner mit Python 3.12 ausfuehren:
#   powershell -ExecutionPolicy Bypass -File build_installer.ps1
#
# Ergebnis:
#   - Falls Inno Setup installiert ist (https://jrsoftware.org/isdl.php):
#       installer_output\iOSLocationSimulator-Setup.exe
#     -> das ist die eine Datei, die Endnutzer bekommen und ausfuehren.
#   - Falls Inno Setup NICHT installiert ist:
#       iOSLocationSimulator-portable.zip
#     -> entpacken, iOSLocationSimulator.exe direkt starten (kein Setup,
#        aber ebenfalls ohne manuelle Python-Installation beim Endnutzer).
#
# Was hier passiert und warum zwei .exe-Dateien entstehen:
#   Das Tool ruft intern mehrfach "python -m pymobiledevice3 ..." als
#   Unterprozess auf (Geraeteliste, Tunnel, Positionsbefehle). Eine mit
#   PyInstaller gebaute GUI-exe kann sich selbst nicht so aufrufen wie einen
#   echten Python-Interpreter. Deshalb wird pymobiledevice3 als zweite,
#   eigenstaendige Konsolen-exe (pmd3.exe) mitgebaut; device.py erkennt das
#   automatisch und spricht dann mit dieser exe statt mit "python -m ...".

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Resolve-Python312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 --version *> $null
        if ($LASTEXITCODE -eq 0) { return @("py", "-3.12") }
    }
    Write-Host "Python 3.12 wurde nicht gefunden."
    Write-Host "Bitte von https://www.python.org/downloads/release/python-3120/ installieren"
    Write-Host "('Add python.exe to PATH' beim Setup ankreuzen) und dieses Skript erneut starten."
    exit 1
}

$py = Resolve-Python312
Write-Host "Verwende Interpreter: $($py -join ' ')`n"

function Invoke-Py {
    param([string[]]$PyArgs)
    & $py[0] $py[1] @PyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Befehl fehlgeschlagen: $($py -join ' ') $($PyArgs -join ' ')"
    }
}

Write-Host "[1/5] Abhaengigkeiten installieren ..."
Invoke-Py @("-m", "pip", "install", "--upgrade", "pip", "pyinstaller", "-q")
Invoke-Py @("-m", "pip", "install", "-r", "requirements.txt", "-q")

Write-Host "`n[2/5] pmd3.exe bauen (pymobiledevice3-CLI, eigenstaendig) ..."
# WICHTIG: --onedir statt --onefile. Die Oberflaeche ruft pmd3.exe nicht
# einmal auf, sondern alle paar Sekunden erneut (Geraete-Polling, jede
# Positionsaenderung). Ein --onefile-Build packt sich bei JEDEM Start neu
# in einen Temp-Ordner aus - bei pymobiledevice3s Abhaengigkeiten dauert
# das mehrere Sekunden PRO AUFRUF und macht das Tool praktisch unbenutzbar
# (aeussert sich als "Geraet nicht gefunden" oder ein scheinbar
# eingefrorenes schwarzes Fenster). --onedir legt alles bereits entpackt
# ab, Start ist praktisch verzoegerungsfrei.
Invoke-Py @(
    "-m", "PyInstaller", "--noconfirm", "--onedir", "--console",
    "--name", "pmd3", "--collect-all", "pymobiledevice3",
    "pmd3_entry.py"
)

Write-Host "`n[3/5] iOSLocationSimulator.exe bauen (GUI) ..."
# Die GUI selbst wird nur einmal pro Sitzung gestartet, daher ist --onefile
# hier unproblematisch und praktischer fuer die Weitergabe.
Invoke-Py @(
    "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
    "--name", "iOSLocationSimulator",
    "main.py"
)

Write-Host "`n[4/5] Dateien zusammenfuehren ..."
if (-not (Test-Path "dist\pmd3\pmd3.exe")) {
    throw "dist\pmd3\pmd3.exe wurde nicht gefunden - PyInstaller-Ausgabe oben pruefen."
}
if (-not (Test-Path "dist\iOSLocationSimulator.exe")) {
    $found = Get-ChildItem -Path "dist" -Recurse -Filter "iOSLocationSimulator.exe" -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { Copy-Item $found.FullName "dist\iOSLocationSimulator.exe" -Force }
}
if (Test-Path "wintun.dll") {
    Copy-Item "wintun.dll" "dist\wintun.dll" -Force
    Write-Host "wintun.dll mit eingepackt."
} else {
    Write-Host "Hinweis: wintun.dll liegt hier nicht vor - das Tool laedt sie beim"
    Write-Host "ersten Start selbst nach (Button 'wintun.dll einrichten' / 'set up wintun.dll')."
}

Write-Host "`n[5/5] Installer paketieren ..."
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    New-Item -ItemType Directory -Force -Path "installer_output" | Out-Null
    & $iscc "iOSLocationSimulator.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup ist fehlgeschlagen." }
    Write-Host "`nFertig: installer_output\iOSLocationSimulator-Setup.exe"
    Write-Host "Das ist die eine Datei, die du weitergeben kannst."
} else {
    Write-Host "`nInno Setup wurde nicht gefunden (https://jrsoftware.org/isdl.php)."
    Write-Host "Stattdessen wird ein portabler ZIP-Ordner gepackt:"
    $items = @("dist\iOSLocationSimulator.exe", "dist\pmd3")
    if (Test-Path "dist\wintun.dll") { $items += "dist\wintun.dll" }
    Compress-Archive -Path $items -DestinationPath "iOSLocationSimulator-portable.zip" -Force
    Write-Host "Fertig: iOSLocationSimulator-portable.zip"
    Write-Host "Entpacken und iOSLocationSimulator.exe direkt starten - kein Python noetig."
    Write-Host "(Fuer eine richtige Setup.exe: Inno Setup installieren und dieses Skript erneut laufen lassen.)"
}
