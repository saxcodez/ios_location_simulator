# Contributing

Danke für dein Interesse an diesem Projekt! Ein paar kurze Hinweise.

## Entwicklung einrichten

```powershell
git clone https://github.com/<dein-name>/ios-location-simulator.git
cd ios-location-simulator
pip install -r requirements.txt
python main.py
```

Python 3.9+ wird vorausgesetzt, 3.12 empfohlen (siehe README für den Hintergrund).

## Bevor du einen Pull Request öffnest

- `python -m py_compile *.py` sollte fehlerfrei durchlaufen.
- Falls du an der Oberfläche (`ui.py`) etwas änderst: prüfe, dass neue
  statische Texte (Buttons, Labels, Titel) über `i18n.py` laufen, nicht als
  hartkodierter String - sonst bricht die Sprachumschaltung für diese Stelle.
- Halte dich an den bestehenden Stil: deutsche Kommentare/Docstrings,
  Variablennamen englisch, keine Umlaute oder Sonderzeichen in `.ps1`-Dateien
  (siehe Kommentar in `build_installer.ps1` - Windows PowerShell 5.1 liest
  `.ps1`-Dateien ohne BOM nicht zuverlässig als UTF-8).

## Issues

Bug-Reports und Feature-Wünsche gerne über die Issue-Vorlagen. Bei Bugs hilft
die Ausgabe von `python diagnose.py` und ein exportiertes Log (Button im
Tool) enorm bei der Eingrenzung.

## Lizenz

Mit einem Beitrag stimmst du zu, dass er unter der MIT-Lizenz dieses Projekts
veröffentlicht wird (siehe `LICENSE`).
