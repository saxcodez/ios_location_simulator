<div align="center">

**🇬🇧 English | 🇩🇪 [Deutsch](README.de.md)**

</div>

<div align="center">

# 📍 iOS Location Simulator

**Simulate GPS locations on a USB-connected iPhone - from Windows, no Mac required.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](#)
[![CI](https://github.com/saxcodez/ios-location-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/saxcodez/ios-location-simulator/actions/workflows/ci.yml)
[![Release](https://github.com/saxcodez/ios-location-simulator/actions/workflows/release.yml/badge.svg)](https://github.com/saxcodez/ios-location-simulator/actions/workflows/release.yml)

*by [saxcodez](https://github.com/saxcodez)*

</div>

---

A Windows tool for simulating GPS locations on a connected iPhone -
with a clickable map, route planning, drive simulation, and automatic
detection of the connected iPhone. Works with **all iOS versions from 12 to
26**, no prior developer-mode knowledge required.

> ⚠️ **For your own devices and testing purposes only.** Built for app
> developers and testers who need to check location-dependent behavior
> without physically travelling somewhere else.

---

## Contents

- [Features](#features)
- [Installation](#installation)
- [First steps on the iPhone](#first-steps-on-the-iphone)
- [Usage](#usage)
- [Supported iOS versions](#supported-ios-versions)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Building from source](#building-from-source)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| | |
|---|---|
| 🗺️ **Teleport** | Left-click on the map, manual coordinates, or saved places |
| 🖱️ **Right-click menu** | Teleport here - set as start/destination - copy coordinates |
| 🛣️ **Route planning** | From/to via address search or map click, real road routes (OSRM) |
| 🚗 **Drive simulation** | Walk / bike / drive, speed 1-200 km/h, pause/stop, loop |
| 💾 **Saved places & routes** | Plus "recently used" |
| 📤 **Export/import** | Back up places & routes as JSON - handy when switching devices or PCs |
| 🔌 **Automatic device detection** | Plug in the iPhone, done - no manual UDID entry |
| 📶 **All iOS versions** | 12-26, automatically picks the right connection method |
| 🛠️ **Developer Mode activation** | One click (works only without a device passcode) |
| 🟢 **Live simulation status** | Always shows whether a simulated position is currently active |
| 🌍 **German/English** | Language toggle right in the UI |
| 📄 **Log export** | For troubleshooting and support |

---

## Installation

### Option A - Prebuilt installer (recommended)

1. Download the latest version from the [Releases page](../../releases)
   (`iOSLocationSimulator-Setup.exe` or the portable ZIP)
2. Run it - no Python, no `pip`, no PowerShell commands needed
3. Also required: **Apple's USB driver** - [Apple Devices](https://apps.microsoft.com/detail/9np83lwlpz9k)
   from the Microsoft Store, or the classic iTunes from apple.com

### Option B - From source

```powershell
git clone https://github.com/saxcodez/ios-location-simulator.git
cd ios-location-simulator
pip install -r requirements.txt
python main.py
```

Python 3.9+ works, 3.12 is recommended (see [Troubleshooting](#troubleshooting) for why).

---

## First steps on the iPhone

1. Connect via USB, unlock it, confirm **"Trust This Computer"**
2. Settings -> Privacy & Security -> turn on **Developer Mode**
   (can also be triggered with one click from the tool - only works without
   a device passcode)
3. On iOS 17 and newer: the tool starts the required tunnel (`tunneld`)
   automatically on first connect; `wintun.dll` needs a one-time setup -
   also a single click in the tool

---

## Usage

**Teleport:** click a point on the map -> *Set position*. Or type
coordinates directly - pasting `53.5503, 9.9922` into the latitude field
automatically splits it across both fields.

**Drive a route:**
1. Set a start and destination (address search, map click, or right-click menu)
2. Choose a mode of travel
3. *Calculate route*, set the speed, *Start*

**Back to real GPS:** the *Restore real GPS* button, or simply *Disconnect*
- the tool asks about this on exit too.

---

## Supported iOS versions

| iOS | Connection method | Notes |
|---|---|---|
| 12 - 16 | `lockdown` directly over USB | One-shot command; the position stays active even after unplugging |
| 17 - 26 | RemoteXPC tunnel (`tunneld`) | Position only stays active while the connection is held open (same as Xcode's "Simulate Location") |

The tool detects the iOS version itself and automatically picks the right method.

---

## How it works

Under the hood, this tool uses
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - the same
open-source library that powers Xcode's own location simulation. It's
driven exclusively through pymobiledevice3's command-line interface rather
than its internal Python classes: those internals change noticeably more
often between pymobiledevice3 releases than the public CLI does, which
makes this tool considerably more resilient to future updates.

---

## Troubleshooting

First stop for any issue:

```powershell
python diagnose.py
```

It walks through the entire chain (Python, pymobiledevice3, Apple's USB
service, device detection, Developer Disk Image, tunnel) and tells you what
to do at each step.

Common pitfalls:

| Symptom | Cause |
|---|---|
| No device in the list | Apple driver missing, charge-only cable, or "Trust" not confirmed |
| "Developer Mode is disabled" | Enable Developer Mode (button in the tool, or manually in Settings) |
| Position doesn't change on the device | On iOS 17+ the connection has to stay open - check the live simulation status in the tool |
| `pip install` fails with a compiler error | Python 3.14 doesn't have prebuilt wheels for all dependencies yet - use Python 3.12 |

---

## Building from source

To produce your own Windows installer (one-time, on a Windows machine with
Python 3.12):

```powershell
powershell -ExecutionPolicy Bypass -File build_installer.ps1
```

Details - including why this produces two `.exe` files - are commented
directly in the script. With [Inno Setup](https://jrsoftware.org/isdl.php)
installed, this produces a proper `Setup.exe`; otherwise it automatically
falls back to a portable ZIP.

On every pushed version tag (`vX.Y.Z`), GitHub Actions builds the same
installer automatically and attaches it to the corresponding release - see
[`.github/workflows/release.yml`](.github/workflows/release.yml).

---

## Contributing

Bug reports, feature requests, and pull requests are welcome - see
[CONTRIBUTING.md](CONTRIBUTING.md). Please route any new UI text through
`i18n.py` so the language toggle stays consistent.

## License

[MIT](LICENSE) © 2026 [saxcodez](https://github.com/saxcodez)
