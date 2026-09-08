# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Bridge zu pymobiledevice3 - deckt alle iOS-Versionen ab.

WICHTIG: Dieses Modul importiert absichtlich KEINE internen Klassen aus
pymobiledevice3.services.* mehr. Diese Interna werden zwischen Versionen
teils komplett umgebaut (z.B. wurde dvt_secure_socket_proxy in v9.0
ersatzlos entfernt und durch eine neue DvtProvider-Architektur ersetzt).
Stattdessen wird ausschliesslich die CLI angesprochen - die bleibt ueber
Versionen hinweg deutlich stabiler, weil sie der dokumentierte, oeffentliche
Nutzungsweg ist.

Verbindungswege je nach iOS-Version:

  iOS  <= 16   pymobiledevice3 developer simulate-location set/clear
               (direkt ueber usbmux, kein Tunnel noetig)
  iOS  >= 17   pymobiledevice3 developer dvt simulate-location set/clear
               --rsd <host> <port>   (Tunnel via tunneld)
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

TUNNELD_HOST = "127.0.0.1"
TUNNELD_PORT = 49151
TUNNELD_URL = f"http://{TUNNELD_HOST}:{TUNNELD_PORT}/"

WINTUN_ZIP_URL = "https://www.wintun.net/builds/wintun-0.14.1.zip"

IS_WINDOWS = os.name == "nt"


class DeviceError(Exception):
    """Fehler mit einer Meldung, die direkt angezeigt werden kann."""


# --------------------------------------------------------------------------
# Umgebung
# --------------------------------------------------------------------------

def app_dir() -> Path:
    """
    Ordner, in dem die Anwendung tatsaechlich liegt - im normalen
    Python-Betrieb der Ordner dieser Datei, in einer mit PyInstaller
    gebauten .exe dagegen der Ordner der .exe selbst (NICHT der
    Temp-Entpackungsordner von sys._MEIPASS, wo wintun.dll niemand
    dauerhaft ablegen koennte).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def is_admin() -> bool:
    if not IS_WINDOWS:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def wintun_present() -> bool:
    return (app_dir() / "wintun.dll").exists()


def install_wintun() -> str:
    if not IS_WINDOWS:
        return "wintun.dll wird nur unter Windows benoetigt."
    if wintun_present():
        return "wintun.dll ist bereits vorhanden."

    arch = (os.environ.get("PROCESSOR_ARCHITECTURE") or "").upper()
    arch_dir = {"AMD64": "amd64", "ARM64": "arm64", "X86": "x86"}.get(arch, "amd64")

    try:
        req = urllib.request.Request(
            WINTUN_ZIP_URL, headers={"User-Agent": "iOSLocationSimulator/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read()
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            target = f"wintun/bin/{arch_dir}/wintun.dll"
            names = zf.namelist()
            if target not in names:
                matches = [n for n in names if n.endswith(f"/{arch_dir}/wintun.dll")]
                if not matches:
                    raise DeviceError(f"wintun.dll fuer {arch_dir} nicht im Archiv.")
                target = matches[0]
            (app_dir() / "wintun.dll").write_bytes(zf.read(target))
    except DeviceError:
        raise
    except Exception as e:
        raise DeviceError(
            "Download von wintun.dll fehlgeschlagen.\n"
            "Manuell von https://www.wintun.net herunterladen und "
            f"wintun.dll nach {app_dir()} kopieren.\n"
            f"Details: {e}"
        ) from e
    return f"wintun.dll installiert ({arch_dir})."


def pymobiledevice3_command() -> list:
    """
    Im normalen Python-Betrieb: das aktuelle Interpreter-Modul aufrufen.
    In einer mit PyInstaller gebauten .exe zeigt sys.executable auf die
    eigene GUI-exe, nicht auf einen echten Python-Interpreter - dort wird
    stattdessen die separat mitgebaute pmd3.exe im Unterordner 'pmd3'
    benutzt (siehe build_installer.ps1 / pmd3_entry.py). Diese liegt
    bewusst als --onedir-Build vor (nicht --onefile): sie wird von diesem
    Modul dutzende Male pro Sitzung aufgerufen, und ein --onefile-Build
    wuerde sich bei jedem einzelnen Aufruf neu in einen Temp-Ordner
    auspacken - spuerbar langsam bis praktisch unbenutzbar.
    """
    if getattr(sys, "frozen", False):
        sibling = app_dir() / "pmd3" / ("pmd3.exe" if IS_WINDOWS else "pmd3")
        if sibling.exists():
            return [str(sibling)]
        return ["pymobiledevice3"]  # Fallback, falls doch eine System-Installation existiert
    return [sys.executable, "-m", "pymobiledevice3"]


def run_cli(args: list, timeout: float = 120.0, tolerate_timeout: bool = False):
    """
    Fuehrt ein pymobiledevice3-CLI-Kommando aus und gibt (returncode, output)
    zurueck.

    Manche pymobiledevice3-Versionen beenden 'developer dvt simulate-location
    set/clear' nicht von selbst, sondern warten auf ein Interrupt-Signal,
    obwohl der eigentliche Befehl laengst durchgefuehrt wurde. Mit
    tolerate_timeout=True wird ein Zeitablauf deshalb als Erfolg gewertet
    (der Prozess wird von subprocess.run bereits beendet).
    """
    cmd = pymobiledevice3_command() + args
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=flags, encoding="utf-8", errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        if tolerate_timeout:
            return 0, out
        raise DeviceError(
            f"Zeitueberschreitung bei: {' '.join(args)}\n{out.strip()[-800:]}"
        ) from e


# --------------------------------------------------------------------------
# tunneld
# --------------------------------------------------------------------------

def tunneld_devices(timeout: float = 3.0):
    try:
        with urllib.request.urlopen(TUNNELD_URL, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def tunneld_running() -> bool:
    return tunneld_devices(timeout=1.5) is not None


def start_tunneld() -> str:
    if tunneld_running():
        return "tunneld laeuft bereits."

    if IS_WINDOWS and not wintun_present():
        raise DeviceError(
            "wintun.dll fehlt - tunneld kann ohne sie keinen Tunnel aufbauen.\n"
            "Im Tool auf 'wintun.dll einrichten' klicken oder die Datei von "
            f"https://www.wintun.net nach {app_dir()} kopieren."
        )

    workdir = str(app_dir())
    if is_admin():
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if IS_WINDOWS else 0
        subprocess.Popen(
            pymobiledevice3_command() + ["remote", "tunneld"],
            cwd=workdir,
            creationflags=flags,
        )
    elif IS_WINDOWS:
        import ctypes
        cmd_parts = pymobiledevice3_command() + ["remote", "tunneld"]
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", cmd_parts[0],
            " ".join(f'"{p}"' if " " in p else p for p in cmd_parts[1:]),
            workdir, 1,
        )
        if rc <= 32:
            raise DeviceError(
                "Start von tunneld abgebrochen oder abgelehnt (UAC).\n"
                "Alternativ eine Konsole als Administrator oeffnen und dort "
                "ausfuehren:\n    python -m pymobiledevice3 remote tunneld"
            )
    else:
        raise DeviceError("tunneld muss als root gestartet werden.")

    for _ in range(30):
        time.sleep(1.0)
        if tunneld_running():
            return "tunneld gestartet."
    raise DeviceError(
        "tunneld wurde gestartet, antwortet aber nicht auf "
        f"{TUNNELD_HOST}:{TUNNELD_PORT}. Konsolenfenster auf Fehler pruefen."
    )


# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------

class IosLocationBackend:
    def __init__(self, log=None):
        self.log = log or (lambda _m: None)
        self.udid = None
        self.device_name = None
        self.ios_version = None
        self.ios_major = 0
        self.mode = None          # "legacy" (<=16) oder "rsd" (>=17)
        self.rsd_host = None
        self.rsd_port = None
        self._connected = False
        self._sim_proc = None    # laufender 'dvt simulate-location set'-Prozess (iOS 17+)
        self._legacy_sim_active = False  # Simulationsstatus fuer iOS <=16 (kein Prozess zum Prüfen)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def simulation_active(self) -> bool:
        """
        Ob aus Sicht dieses Tools gerade eine simulierte Position aktiv ist.
        Bei iOS 17+ ist das direkt pruefbar (laeuft der haltende Prozess noch?);
        bei iOS <=16 gibt es keinen Prozess, den man befragen koennte - dort
        wird der zuletzt bekannte Status gemerkt.
        """
        if self.mode == "rsd":
            return self._sim_proc is not None and self._sim_proc.poll() is None
        return self._legacy_sim_active

    # -- Geraeteliste (ueber CLI, kein Python-Import von pymobiledevice3) -

    @staticmethod
    def _usbmux_list() -> list:
        code, out = run_cli(["usbmux", "list"], timeout=15)
        if code != 0:
            raise DeviceError(
                "Apple-Geraetedienst nicht erreichbar. 'Apple Devices' "
                "(Microsoft Store) oder iTunes installieren und pruefen, ob "
                "der Dienst 'Apple Mobile Device Service' laeuft.\n"
                f"Ausgabe:\n{out.strip()[-800:]}"
            )
        try:
            start = out.index("[")
            return json.loads(out[start:])
        except Exception as e:
            raise DeviceError(
                f"Unerwartete Ausgabe von 'usbmux list':\n{out.strip()[-800:]}"
            ) from e

    @staticmethod
    def list_devices() -> list:
        data = IosLocationBackend._usbmux_list()
        out = []
        for d in data:
            ctype = str(d.get("ConnectionType", "USB"))
            if ctype.lower().startswith("net"):
                continue
            udid = d.get("Identifier") or d.get("UniqueDeviceID")
            if udid:
                out.append(udid)
        return sorted(set(out))

    @staticmethod
    def describe(udid: str) -> str:
        try:
            data = IosLocationBackend._usbmux_list()
        except DeviceError:
            return udid
        for d in data:
            if udid in (d.get("Identifier"), d.get("UniqueDeviceID")):
                name = d.get("DeviceName", udid)
                ver = d.get("ProductVersion", "?")
                return f"{name} - iOS {ver}"
        return udid

    # -- Vorbereitung -----------------------------------------------------

    def mount_ddi(self, udid: str) -> str:
        code, out = run_cli(["mounter", "auto-mount", "--udid", udid], timeout=300)
        text = out.strip().splitlines()[-1] if out.strip() else ""
        if code == 0:
            return text or "DDI gemountet."
        low = out.lower()
        if "already" in low or "mounted" in low:
            return "DDI war bereits gemountet."
        raise DeviceError(
            "Developer Disk Image konnte nicht gemountet werden.\n"
            "Pruefen: iPhone entsperrt, 'Vertrauen' bestaetigt, Entwicklermodus "
            "aktiv (Einstellungen > Datenschutz & Sicherheit > Entwicklermodus).\n"
            f"Ausgabe:\n{out.strip()[-1200:]}"
        )

    # -- Verbinden --------------------------------------------------------

    def connect(self, udid: str, auto_tunnel: bool = True, auto_mount: bool = True) -> str:
        self._terminate_sim_proc()
        data = self._usbmux_list()
        info = next(
            (d for d in data if udid in (d.get("Identifier"), d.get("UniqueDeviceID"))),
            None,
        )
        if not info:
            raise DeviceError(
                "Geraet nicht mehr erreichbar - USB-Verbindung pruefen und "
                "erneut versuchen."
            )

        self.udid = udid
        self.device_name = info.get("DeviceName", udid)
        self.ios_version = str(info.get("ProductVersion", "0"))
        try:
            self.ios_major = int(self.ios_version.split(".")[0])
        except ValueError:
            self.ios_major = 0

        self.log(f"Geraet: {self.device_name}, iOS {self.ios_version}")

        if auto_mount:
            try:
                self.log(self.mount_ddi(udid))
            except DeviceError as e:
                self.log(f"Hinweis: {str(e).splitlines()[0]}")

        if self.ios_major and self.ios_major < 17:
            self.mode = "legacy"
            self.rsd_host = self.rsd_port = None
            self.log("Verbindungsart: klassisch ueber usbmux (iOS 16 und aelter).")
        else:
            self.mode = "rsd"
            tdata = tunneld_devices()
            if tdata is None:
                if not auto_tunnel:
                    raise DeviceError(
                        "Ab iOS 17 wird ein laufender Tunnel benoetigt. "
                        "tunneld ist nicht erreichbar."
                    )
                self.log("tunneld nicht erreichbar - starte ihn ...")
                self.log(start_tunneld())
                tdata = tunneld_devices()
                if tdata is None:
                    raise DeviceError("tunneld antwortet weiterhin nicht.")
            host, port = self._pick_tunnel(tdata, udid)
            self.rsd_host, self.rsd_port = host, port
            self.log(f"Tunnel gefunden: {host}:{port}")

        self._connected = True
        return f"{self.device_name} (iOS {self.ios_version})"

    @staticmethod
    def _pick_tunnel(data: dict, udid: str):
        entries = data.get(udid)
        if not entries:
            flat = [e for v in data.values() for e in v]
            if len(flat) == 1:
                entries = flat
            elif not flat:
                raise DeviceError(
                    "tunneld kennt aktuell kein Geraet. iPhone abziehen, wieder "
                    "anstecken, entsperren und tunneld neu starten."
                )
            else:
                raise DeviceError(
                    "Fuer diese UDID existiert kein Tunnel, es sind aber andere "
                    "Geraete verbunden. tunneld neu starten."
                )
        entry = entries[0]
        host = entry.get("tunnel-address") or entry.get("address")
        port = entry.get("tunnel-port") or entry.get("port")
        if not host or not port:
            raise DeviceError(f"Unerwartete tunneld-Antwort: {entry}")
        return host, int(port)

    # -- Positionsbefehle (ausschliesslich ueber CLI) ----------------------

    def _location_args(self, sub: str, lat: float = None, lon: float = None) -> list:
        if self.mode == "rsd":
            base = [
                "developer", "dvt", "simulate-location", sub,
                "--rsd", self.rsd_host, str(self.rsd_port),
            ]
        else:
            base = ["developer", "simulate-location", sub]
        if lat is not None:
            base = base + ["--", f"{lat:.7f}", f"{lon:.7f}"]
        return base

    def _run_with_udid(self, args, timeout, tolerate_timeout=False):
        """
        Setzt PYMOBILEDEVICE3_UDID fuer den Aufruf, damit die CLI bei mehreren
        angeschlossenen Geraeten nicht interaktiv nachfragt (das schlaegt in
        einem Hintergrundprozess ohne Terminal sonst fehl).
        """
        env = dict(os.environ)
        if self.udid:
            env["PYMOBILEDEVICE3_UDID"] = self.udid
        cmd = pymobiledevice3_command() + args
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                creationflags=flags, encoding="utf-8", errors="replace", env=env,
            )
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or "") + (e.stderr or "")
            if tolerate_timeout:
                return 0, out
            raise DeviceError(
                f"Zeitueberschreitung bei: {' '.join(args)}\n{out.strip()[-800:]}"
            ) from e

    def _terminate_sim_proc(self):
        """Beendet einen evtl. laufenden 'set'-Prozess sauber, falls vorhanden."""
        proc = self._sim_proc
        self._sim_proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            pass

    @staticmethod
    def _drain(proc, captured: list):
        """Liest die Ausgabe eines langlaufenden Prozesses kontinuierlich,
        damit dessen Pipe nicht vollläuft und den Prozess blockiert."""
        try:
            for line in iter(proc.stdout.readline, ""):
                captured.append(line)
                if len(captured) > 200:
                    captured.pop(0)
        except Exception:
            pass

    def _set_location_rsd(self, lat: float, lon: float):
        """
        Ab iOS 17 muss die 'set'-Verbindung offen bleiben, damit die
        simulierte Position aktiv bleibt - genau wie bei Xcodes 'Simulate
        Location'. Ein einmaliger Aufruf, der sich sofort wieder beendet,
        wuerde die Position sofort auf die echte zurueckfallen lassen.
        Deshalb wird der Prozess hier bewusst am Leben gehalten und erst
        beim naechsten 'set', bei 'clear' oder beim Trennen beendet.
        """
        self._terminate_sim_proc()

        cmd = pymobiledevice3_command() + self._location_args("set", lat, lon)
        env = dict(os.environ)
        if self.udid:
            env["PYMOBILEDEVICE3_UDID"] = self.udid
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=flags, env=env,
        )
        captured: list = []
        threading.Thread(target=self._drain, args=(proc, captured), daemon=True).start()

        # Kurze Gnadenfrist: entweder der Prozess haelt die Verbindung offen
        # (Normalfall bei iOS 17+) oder er beendet sich sofort erfolgreich
        # (manche Versionen). Nur ein frueher Fehler ist ein echtes Problem.
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.2)

        if proc.poll() is None:
            self._sim_proc = proc
            return
        if proc.returncode == 0:
            self._sim_proc = None
            return
        raise DeviceError(
            f"Position konnte nicht gesetzt werden:\n{''.join(captured).strip()[-800:]}"
        )

    def set_location(self, lat: float, lon: float):
        if not self.connected:
            raise DeviceError("Nicht verbunden.")
        if self.mode == "rsd":
            self._set_location_rsd(lat, lon)
        else:
            code, out = self._run_with_udid(
                self._location_args("set", lat, lon), timeout=20, tolerate_timeout=True
            )
            if code != 0:
                raise DeviceError(
                    f"Position konnte nicht gesetzt werden:\n{out.strip()[-800:]}"
                )
            self._legacy_sim_active = True

    def clear_location(self):
        if not self.connected:
            raise DeviceError("Nicht verbunden.")
        self._terminate_sim_proc()
        code, out = self._run_with_udid(
            self._location_args("clear"), timeout=20, tolerate_timeout=True
        )
        self._legacy_sim_active = False
        if code != 0:
            raise DeviceError(f"Zuruecksetzen fehlgeschlagen:\n{out.strip()[-800:]}")

    def disconnect(self, clear_first: bool = True):
        if clear_first and self.connected:
            try:
                self.clear_location()
            except Exception:
                pass
        self._terminate_sim_proc()
        self._connected = False
        self._legacy_sim_active = False
        self.udid = self.device_name = self.ios_version = None
        self.ios_major = 0
        self.mode = self.rsd_host = self.rsd_port = None

    def force_disconnect(self):
        """
        Setzt den Verbindungsstatus zurueck, OHNE einen CLI-Befehl abzusetzen.
        Fuer den Fall, dass das Geraet physisch abgezogen wurde - ein
        'clear'-Aufruf wuerde dort ohnehin nur eine weitere Fehlermeldung
        erzeugen. Ein evtl. noch laufender 'set'-Prozess wird trotzdem
        beendet (er ist ohnehin schon durch den Verbindungsabbruch tot oder
        wird es gleich sein).
        """
        self._terminate_sim_proc()
        self._connected = False
        self._legacy_sim_active = False
        self.udid = self.device_name = self.ios_version = None
        self.ios_major = 0
        self.mode = self.rsd_host = self.rsd_port = None


# --------------------------------------------------------------------------
# Entwicklermodus (AMFI)
# --------------------------------------------------------------------------

def developer_mode_status(udid: str):
    """
    Gibt True/False zurueck, oder None wenn der Status aus der Ausgabe nicht
    eindeutig bestimmbar ist (z.B. weil sich das CLI-Ausgabeformat zwischen
    Versionen unterscheidet).
    """
    code, out = run_cli(["amfi", "developer-mode-status", "--udid", udid], timeout=20)
    if code != 0:
        return None
    low = out.lower()
    if "true" in low:
        return True
    if "false" in low:
        return False
    return None


def enable_developer_mode(udid: str) -> str:
    """
    Aktiviert den Entwicklermodus per AMFI. Funktioniert nur, wenn das iPhone
    KEINEN Sperrcode eingerichtet hat - mit Code lehnt iOS das aus
    Sicherheitsgruenden explizit ab, das ist keine Einschraenkung dieses
    Tools. Der Vorgang startet das Geraet neu; pymobiledevice3 wartet dabei
    von sich aus auf den Neustart und bestaetigt den Dialog automatisch mit.
    """
    try:
        code, out = run_cli(["amfi", "enable-developer-mode", "--udid", udid], timeout=180)
    except DeviceError as e:
        raise DeviceError(
            "Der Vorgang braucht laenger als erwartet (das Geraet startet "
            "dabei neu). Aufs iPhone schauen: erscheint dort eine Meldung "
            "'Entwicklermodus einschalten?', dort bestaetigen und den Code "
            "eingeben. Danach im Tool neu verbinden.\n"
            f"Details: {e}"
        ) from e

    low = out.lower()
    if "passcode" in low:
        raise DeviceError(
            "Das iPhone hat einen Sperrcode eingerichtet - Aktivierung per "
            "Kommandozeile ist damit nicht moeglich (Apple-Sicherheitssperre).\n"
            "Manuell: Einstellungen > Datenschutz & Sicherheit > ganz nach "
            "unten scrollen > Entwicklermodus > an, danach Geraet neu starten "
            "und die Bestaetigung antippen.\n"
            "Falls der Menuepunkt in den Einstellungen gar nicht auftaucht: "
            "trotzdem einmal auf 'Verbinden' in diesem Tool klicken (auch "
            "wenn es fehlschlaegt) und das iPhone danach neu starten - der "
            "Menuepunkt erscheint oft erst, nachdem ein Entwicklertool einmal "
            "Kontakt aufgenommen hat."
        )
    if code != 0:
        raise DeviceError(f"Aktivierung fehlgeschlagen:\n{out.strip()[-800:]}")
    return "Entwicklermodus aktiviert."
