@echo off
REM Startet den iOS Location Simulator im Verzeichnis dieser Datei.
REM Nutzt bevorzugt Python 3.12 (fertige Wheels fuer alle Abhaengigkeiten).
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 main.py 2>nul
    if not errorlevel 1 goto :eof
    echo Python 3.12 nicht gefunden, versuche Standard-Python ...
)
python main.py
if errorlevel 1 pause
