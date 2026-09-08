# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""Tkinter-Oberflaeche des iOS Location Simulators."""

from __future__ import annotations

import queue
import threading
import time
import traceback

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import device as dev
import routing
from navigation import NavigationEngine
from storage import Store
from i18n import I18n
from version import __version__, __author__, __copyright__, about_text

APP_NAME = "iOS Location Simulator"
DEVICE_POLL = 2.0


# --------------------------------------------------------------------------
# Worker: alle Geraeteoperationen laufen hier, nie im GUI-Thread
# --------------------------------------------------------------------------

class Worker(threading.Thread):
    def __init__(self, results: queue.Queue):
        super().__init__(daemon=True)
        self.tasks: queue.Queue = queue.Queue()
        self.results = results

    def submit(self, tag, fn):
        self.tasks.put((tag, fn))

    def stop(self):
        self.tasks.put(None)

    def run(self):
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            item = self.tasks.get()
            if item is None:
                return
            tag, fn = item
            try:
                self.results.put(("ok", tag, fn()))
            except dev.DeviceError as e:
                self.results.put(("err", tag, str(e)))
            except Exception as e:
                self.results.put(("err", tag, f"{e}\n\n{traceback.format_exc(limit=3)}"))


# --------------------------------------------------------------------------
# Auswahldialog fuer Geocoding-Treffer
# --------------------------------------------------------------------------

def choose_place(parent, places: list, lang: str = "de"):
    if not places:
        return None
    if len(places) == 1:
        return places[0]

    win = tk.Toplevel(parent)
    win.title("Treffer auswaehlen" if lang == "de" else "Choose a match")
    win.transient(parent)
    win.grab_set()
    win.geometry("620x320")

    lb = tk.Listbox(win, activestyle="none")
    lb.pack(fill="both", expand=True, padx=8, pady=8)
    for p in places:
        lb.insert("end", p.name)
    lb.selection_set(0)

    result = {"value": None}

    def take():
        sel = lb.curselection()
        if sel:
            result["value"] = places[sel[0]]
        win.destroy()

    lb.bind("<Double-Button-1>", lambda _e: take())
    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(bar, text="Uebernehmen" if lang == "de" else "Apply",
               command=take).pack(side="right")
    ttk.Button(bar, text="Abbrechen" if lang == "de" else "Cancel",
               command=win.destroy).pack(side="right", padx=4)

    parent.wait_window(win)
    return result["value"]


# --------------------------------------------------------------------------
# Hauptfenster
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.i18n = I18n("de")
        self.t = self.i18n.t
        self._i18n_widgets: list = []   # [(widget, key), ...] - generischer Retext
        self._i18n_tabs: list = []      # [(notebook, index, key), ...]

        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("1280x800")
        self.minsize(1020, 660)

        self.store = Store()
        self.backend = dev.IosLocationBackend(log=self._log_threadsafe)
        self.results: queue.Queue = queue.Queue()
        self.worker = Worker(self.results)
        self.worker.start()

        self.nav = NavigationEngine(
            on_position=self._nav_position,
            on_state=lambda s: self.results.put(("navstate", "nav", s)),
        )

        self.map_widget = None
        self.marker = None
        self.start_marker = None
        self.end_marker = None
        self.path_obj = None

        self.available_devices: list = []
        self.device_labels: dict = {}
        self.busy = False
        self._nav_inflight = False
        self._poll_error_shown = False

        self.route: routing.Route | None = None
        self.start_point = None
        self.end_point = None

        self._build_ui()
        self._start_device_poller()
        self.after(100, self._drain)
        self.after(1500, self._refresh_tunnel_state)
        self.after(800, self._refresh_sim_status)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._build_toolbar()

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        left = ttk.Frame(paned, width=260)
        center = ttk.Frame(paned)
        right = ttk.Frame(paned, width=310)
        paned.add(left, weight=0)
        paned.add(center, weight=1)
        paned.add(right, weight=0)

        self._build_sidebar(left)
        self._build_map(center)
        self._build_controls(right)

        log_header = ttk.Frame(self)
        log_header.pack(fill="x", padx=8)
        lbl = ttk.Label(log_header)
        self._reg(lbl, "lbl_protocol")
        lbl.pack(side="left")
        self.copyright_var = tk.StringVar(
            value=f"{APP_NAME} v{__version__} - {__copyright__}"
        )
        ttk.Label(log_header, textvariable=self.copyright_var,
                  foreground="#999").pack(side="right", padx=(0, 10))
        btn = ttk.Button(log_header, command=self.on_export_log)
        self._reg(btn, "btn_export_log")
        btn.pack(side="right")

        self.log_box = tk.Text(self, height=6, wrap="word", state="disabled")
        self.log_box.pack(fill="x", padx=8, pady=(0, 8))

    def _reg(self, widget, key):
        """Registriert ein Widget fuer den generischen Sprachwechsel (Retext)."""
        self._i18n_widgets.append((widget, key))
        widget.configure(text=self.t(key))
        return widget

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(8, 8, 8, 4))
        bar.pack(fill="x")

        lbl = ttk.Label(bar)
        self._reg(lbl, "lbl_device")
        lbl.pack(side="left")
        self.device_var = tk.StringVar()
        self.device_box = ttk.Combobox(
            bar, textvariable=self.device_var, width=38, state="readonly"
        )
        self.device_box.pack(side="left", padx=6)

        self.btn_connect = ttk.Button(bar, command=self.on_connect, state="disabled")
        self._reg(self.btn_connect, "btn_connect")
        self.btn_connect.pack(side="left", padx=2)
        self.btn_disconnect = ttk.Button(bar, command=self.on_disconnect, state="disabled")
        self._reg(self.btn_disconnect, "btn_disconnect")
        self.btn_disconnect.pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)

        self.tunnel_var = tk.StringVar(value=self.t("lbl_tunnel_unknown"))
        ttk.Label(bar, textvariable=self.tunnel_var).pack(side="left")
        btn = ttk.Button(bar, command=self.on_start_tunneld)
        self._reg(btn, "btn_start_tunneld")
        btn.pack(side="left", padx=4)
        btn = ttk.Button(bar, command=self.on_install_wintun)
        self._reg(btn, "btn_install_wintun")
        btn.pack(side="left", padx=2)

        self.status_var = tk.StringVar(value=self.t("status_searching"))
        ttk.Label(bar, textvariable=self.status_var, foreground="#0a5").pack(
            side="right")

        bar2 = ttk.Frame(self, padding=(8, 0, 8, 4))
        bar2.pack(fill="x")

        btn = ttk.Button(bar2, command=self.on_enable_devmode)
        self._reg(btn, "btn_enable_devmode")
        btn.pack(side="left")
        hint = ttk.Label(bar2, foreground="#888")
        self._reg(hint, "hint_devmode")
        hint.pack(side="left", padx=(6, 0))

        self.btn_lang = ttk.Button(bar2, command=self.on_toggle_language, width=10)
        self.btn_lang.pack(side="right", padx=(6, 0))
        self._update_lang_button()

        self.sim_status_var = tk.StringVar(value=self.t("lbl_sim_unknown"))
        ttk.Label(bar2, textvariable=self.sim_status_var, foreground="#0a5").pack(
            side="right", padx=(0, 10))

    def _update_lang_button(self):
        self.btn_lang.configure(text="English" if self.i18n.lang == "de" else "Deutsch")

    def on_toggle_language(self):
        self.i18n.toggle()
        self.apply_language()

    def apply_language(self):
        self.title(f"{self.t('window_title')} v{__version__}")
        for widget, key in self._i18n_widgets:
            try:
                widget.configure(text=self.t(key))
            except Exception:
                pass
        for nb, idx, key in self._i18n_tabs:
            try:
                nb.tab(idx, text=self.t(key))
            except Exception:
                pass
        self._update_lang_button()
        # Nur Platzhalter, keine echten Daten, ueberschreiben:
        if self.route is None:
            self.route_info.set(self.t("route_info_none"))
        if not self.nav.active:
            self.nav_info.set(self.t("nav_ready"))
        if not self.backend.connected:
            self.tunnel_var.set(
                self.t("lbl_tunnel_running") if dev.tunneld_running()
                else self.t("lbl_tunnel_off")
            )

    def _build_sidebar(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)

        # Orte
        tab_places = ttk.Frame(nb, padding=6)
        nb.add(tab_places, text=self.t("tab_places"))
        self._i18n_tabs.append((nb, 0, "tab_places"))
        self.places_list = tk.Listbox(tab_places, activestyle="none", exportselection=False)
        self.places_list.pack(fill="both", expand=True)
        self.places_list.bind("<<ListboxSelect>>", self.on_place_select)
        self.places_list.bind("<Double-Button-1>", lambda _e: self.on_teleport())
        row = ttk.Frame(tab_places)
        row.pack(fill="x", pady=(6, 0))
        btn = ttk.Button(row, command=self.on_place_save)
        self._reg(btn, "btn_save")
        btn.pack(side="left", expand=True, fill="x", padx=1)
        btn = ttk.Button(row, command=self.on_place_delete)
        self._reg(btn, "btn_delete")
        btn.pack(side="left", expand=True, fill="x", padx=1)

        # Routen
        tab_routes = ttk.Frame(nb, padding=6)
        nb.add(tab_routes, text=self.t("tab_routes"))
        self._i18n_tabs.append((nb, 1, "tab_routes"))
        self.routes_list = tk.Listbox(tab_routes, activestyle="none", exportselection=False)
        self.routes_list.pack(fill="both", expand=True)
        self.routes_list.bind("<Double-Button-1>", lambda _e: self.on_route_load())
        row = ttk.Frame(tab_routes)
        row.pack(fill="x", pady=(6, 0))
        btn = ttk.Button(row, command=self.on_route_load)
        self._reg(btn, "btn_load")
        btn.pack(side="left", expand=True, fill="x", padx=1)
        btn = ttk.Button(row, command=self.on_route_delete)
        self._reg(btn, "btn_delete")
        btn.pack(side="left", expand=True, fill="x", padx=1)

        # Zuletzt
        tab_recent = ttk.Frame(nb, padding=6)
        nb.add(tab_recent, text=self.t("tab_recent"))
        self._i18n_tabs.append((nb, 2, "tab_recent"))
        self.recent_list = tk.Listbox(tab_recent, activestyle="none", exportselection=False)
        self.recent_list.pack(fill="both", expand=True)
        self.recent_list.bind("<Double-Button-1>", lambda _e: self.on_recent_load())

        # Sichern/Wiederherstellen - fuer Geraete- oder Rechnerwechsel
        backup_row = ttk.Frame(parent)
        backup_row.pack(side="bottom", fill="x", pady=(6, 0))
        btn = ttk.Button(backup_row, command=self.on_export_backup)
        self._reg(btn, "btn_export_backup")
        btn.pack(side="left", expand=True, fill="x", padx=1)
        btn = ttk.Button(backup_row, command=self.on_import_backup)
        self._reg(btn, "btn_import_backup")
        btn.pack(side="left", expand=True, fill="x", padx=1)

        self._refresh_sidebar()

    def _build_map(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 4))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self.on_map_search())
        btn = ttk.Button(top, command=self.on_map_search)
        self._reg(btn, "btn_map_search")
        btn.pack(side="left", padx=4)

        try:
            import tkintermapview
        except ImportError:
            lbl = ttk.Label(parent, padding=24, justify="left")
            self._reg(lbl, "map_unavailable")
            lbl.pack(fill="both", expand=True)
            return

        self.map_widget = tkintermapview.TkinterMapView(parent, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        s = self.store.settings
        self.map_widget.set_position(s["last_lat"], s["last_lon"])
        self.map_widget.set_zoom(int(s.get("zoom", 11)))
        self.map_widget.add_left_click_map_command(self.on_map_click)
        self.map_widget.add_right_click_menu_command(
            label="Hierher teleportieren" if self.i18n.lang == "de" else "Teleport here",
            command=lambda c: (self.on_map_click(c), self.on_teleport()),
            pass_coords=True)
        self.map_widget.add_right_click_menu_command(
            label="Als Startpunkt" if self.i18n.lang == "de" else "Set as start",
            command=self.set_start_from_coords, pass_coords=True)
        self.map_widget.add_right_click_menu_command(
            label="Als Ziel" if self.i18n.lang == "de" else "Set as destination",
            command=self.set_end_from_coords, pass_coords=True)
        self.map_widget.add_right_click_menu_command(
            label="Koordinaten kopieren" if self.i18n.lang == "de" else "Copy coordinates",
            command=self.copy_coords, pass_coords=True)

    def _build_controls(self, parent):
        # Teleport
        box = ttk.LabelFrame(parent, padding=8)
        self._reg(box, "grp_teleport")
        box.pack(fill="x")
        lbl = ttk.Label(box)
        self._reg(lbl, "lbl_lat")
        lbl.grid(row=0, column=0, sticky="w")
        self.lat_var = tk.StringVar(value=f"{self.store.settings['last_lat']:.6f}")
        e = ttk.Entry(box, textvariable=self.lat_var, width=22)
        e.grid(row=0, column=1, pady=2, sticky="ew")
        e.bind("<FocusOut>", lambda _ev: self._split_pair())
        lbl = ttk.Label(box)
        self._reg(lbl, "lbl_lon")
        lbl.grid(row=1, column=0, sticky="w")
        self.lon_var = tk.StringVar(value=f"{self.store.settings['last_lon']:.6f}")
        ttk.Entry(box, textvariable=self.lon_var, width=22).grid(
            row=1, column=1, pady=2, sticky="ew")
        box.columnconfigure(1, weight=1)
        self.btn_teleport = ttk.Button(box, command=self.on_teleport, state="disabled")
        self._reg(self.btn_teleport, "btn_set_position")
        self.btn_teleport.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.btn_reset = ttk.Button(box, command=self.on_reset, state="disabled")
        self._reg(self.btn_reset, "btn_restore_gps")
        self.btn_reset.grid(row=3, column=0, columnspan=2, sticky="ew", pady=3)

        # Route
        rbox = ttk.LabelFrame(parent, padding=8)
        self._reg(rbox, "grp_route")
        rbox.pack(fill="x", pady=(10, 0))

        lbl = ttk.Label(rbox)
        self._reg(lbl, "lbl_from")
        lbl.grid(row=0, column=0, sticky="w")
        self.from_var = tk.StringVar()
        ttk.Entry(rbox, textvariable=self.from_var).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Button(rbox, text="?", width=3,
                   command=lambda: self.on_geocode("from")).grid(row=0, column=2, padx=2)

        lbl = ttk.Label(rbox)
        self._reg(lbl, "lbl_to")
        lbl.grid(row=1, column=0, sticky="w")
        self.to_var = tk.StringVar()
        ttk.Entry(rbox, textvariable=self.to_var).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(rbox, text="?", width=3,
                   command=lambda: self.on_geocode("to")).grid(row=1, column=2, padx=2)
        rbox.columnconfigure(1, weight=1)

        prow = ttk.Frame(rbox)
        prow.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.profile_var = tk.StringVar(value=self.store.settings.get("profile", "car"))
        for key, i18n_key in (("foot", "profile_foot"), ("bike", "profile_bike"),
                              ("car", "profile_car")):
            rb = ttk.Radiobutton(prow, value=key, variable=self.profile_var,
                                 command=self.on_profile_change)
            self._reg(rb, i18n_key)
            rb.pack(side="left", padx=(0, 8))

        brow = ttk.Frame(rbox)
        brow.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        btn = ttk.Button(brow, command=self.use_current_as_start)
        self._reg(btn, "btn_use_current_as_start")
        btn.pack(fill="x")
        btn = ttk.Button(brow, command=self.on_calculate_route)
        self._reg(btn, "btn_calc_route")
        btn.pack(fill="x", pady=3)
        btn = ttk.Button(brow, command=self.on_route_save)
        self._reg(btn, "btn_save_route")
        btn.pack(fill="x")

        self.route_info = tk.StringVar(value=self.t("route_info_none"))
        ttk.Label(rbox, textvariable=self.route_info, foreground="#555",
                  wraplength=260, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # Fahrt
        nbox = ttk.LabelFrame(parent, padding=8)
        self._reg(nbox, "grp_drive")
        nbox.pack(fill="x", pady=(10, 0))

        srow = ttk.Frame(nbox)
        srow.pack(fill="x")
        lbl = ttk.Label(srow)
        self._reg(lbl, "lbl_speed")
        lbl.pack(side="left")
        self.speed_var = tk.DoubleVar(value=float(self.store.settings.get("speed_kmh", 50)))
        self.speed_label = tk.StringVar(value=f"{self.speed_var.get():.0f} km/h")
        ttk.Scale(srow, from_=1, to=200, variable=self.speed_var,
                  command=self.on_speed_change).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Label(srow, textvariable=self.speed_label, width=9).pack(side="left")

        self.loop_var = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(nbox, variable=self.loop_var,
                              command=lambda: self.nav.set_loop(self.loop_var.get()))
        self._reg(chk, "chk_loop")
        chk.pack(anchor="w", pady=(4, 0))

        crow = ttk.Frame(nbox)
        crow.pack(fill="x", pady=(6, 0))
        self.btn_go = ttk.Button(crow, command=self.on_nav_start, state="disabled")
        self._reg(self.btn_go, "btn_go")
        self.btn_go.pack(side="left", expand=True, fill="x", padx=1)
        self.btn_pause = ttk.Button(crow, command=self.on_nav_pause, state="disabled")
        self._reg(self.btn_pause, "btn_pause")
        self.btn_pause.pack(side="left", expand=True, fill="x", padx=1)
        self.btn_stop = ttk.Button(crow, command=self.on_nav_stop, state="disabled")
        self._reg(self.btn_stop, "btn_stop")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=1)

        self.progress = ttk.Progressbar(nbox, maximum=100)
        self.progress.pack(fill="x", pady=(8, 2))
        self.nav_info = tk.StringVar(value=self.t("nav_ready"))
        ttk.Label(nbox, textvariable=self.nav_info, foreground="#555").pack(anchor="w")

    # ------------------------------------------------------------------
    # Kleinkram
    # ------------------------------------------------------------------

    def log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_threadsafe(self, msg: str):
        self.results.put(("log", "backend", msg))

    def _split_pair(self):
        pair = routing.parse_coordinates(self.lat_var.get())
        if pair and ("," in self.lat_var.get() or " " in self.lat_var.get().strip()):
            self.lat_var.set(f"{pair[0]:.6f}")
            self.lon_var.set(f"{pair[1]:.6f}")

    def _coords(self):
        self._split_pair()
        try:
            lat = float(self.lat_var.get().strip().replace(",", "."))
            lon = float(self.lon_var.get().strip().replace(",", "."))
        except ValueError:
            raise dev.DeviceError("Koordinaten sind keine gueltigen Zahlen.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise dev.DeviceError("Koordinaten ausserhalb des gueltigen Bereichs.")
        return lat, lon

    def _set_marker(self, lat, lon, text="Position"):
        if not self.map_widget:
            return
        if self.marker is not None:
            try:
                self.marker.delete()
            except Exception:
                pass
        self.marker = self.map_widget.set_marker(lat, lon, text=text)

    def _update_buttons(self):
        connected = self.backend.connected
        idle = not self.busy
        navigating = self.nav.active

        self.btn_connect.configure(
            state="normal" if (idle and not connected and self.available_devices)
            else "disabled")
        self.btn_disconnect.configure(
            state="normal" if (idle and connected) else "disabled")
        self.device_box.configure(
            state="disabled" if (self.busy or connected) else "readonly")

        can_act = connected and idle and not navigating
        self.btn_teleport.configure(state="normal" if can_act else "disabled")
        self.btn_reset.configure(state="normal" if can_act else "disabled")
        self.btn_go.configure(
            state="normal" if (connected and idle and not navigating
                               and self.route and self.route.valid) else "disabled")
        self.btn_pause.configure(state="normal" if navigating else "disabled")
        self.btn_stop.configure(state="normal" if navigating else "disabled")

    def _set_busy(self, value: bool):
        self.busy = value
        self._update_buttons()

    def _refresh_tunnel_state(self):
        def check():
            running = dev.tunneld_running()
            self.results.put(("tunnel", "state", running))
        threading.Thread(target=check, daemon=True).start()
        self.after(6000, self._refresh_tunnel_state)

    # ------------------------------------------------------------------
    # Geraeteerkennung
    # ------------------------------------------------------------------

    def _start_device_poller(self):
        def loop():
            while True:
                try:
                    udids = dev.IosLocationBackend.list_devices()
                    self.results.put(("devices", "poll", udids))
                except Exception as e:
                    self.results.put(("devices_err", "poll", str(e)))
                time.sleep(DEVICE_POLL)
        threading.Thread(target=loop, daemon=True).start()

    def _update_devices(self, udids):
        if udids == self.available_devices:
            return
        added = [u for u in udids if u not in self.available_devices]
        gone = [u for u in self.available_devices if u not in udids]
        self.available_devices = udids

        for u in added:
            threading.Thread(
                target=lambda uu=u: self.results.put(
                    ("devlabel", uu, dev.IosLocationBackend.describe(uu))),
                daemon=True).start()
            self.log(f"iPhone erkannt: {u}")
        for u in gone:
            self.device_labels.pop(u, None)
            self.log(f"iPhone abgezogen: {u}")

        self._refresh_device_box()

        if self.backend.connected and self.backend.udid in gone:
            self.log("Verbindung verloren - Geraet wurde abgezogen.")
            self.nav.stop()
            self.backend.force_disconnect()
            self.status_var.set("Verbindung verloren")

        if not self.backend.connected:
            self.status_var.set(
                f"{len(udids)} Geraet(e) gefunden" if udids
                else "Kein iPhone per USB gefunden")
        self._update_buttons()

    def _refresh_device_box(self):
        values = [self.device_labels.get(u, u) for u in self.available_devices]
        self.device_box.configure(values=values)
        if values and self.device_var.get() not in values:
            self.device_var.set(values[0])
        if not values:
            self.device_var.set("")

    def _selected_udid(self):
        label = self.device_var.get()
        for udid in self.available_devices:
            if self.device_labels.get(udid, udid) == label:
                return udid
        return self.available_devices[0] if self.available_devices else None

    # ------------------------------------------------------------------
    # Karte
    # ------------------------------------------------------------------

    def on_map_click(self, coords):
        lat, lon = coords
        self.lat_var.set(f"{lat:.6f}")
        self.lon_var.set(f"{lon:.6f}")
        self._set_marker(lat, lon, "Ziel")

    def copy_coords(self, coords):
        text = f"{coords[0]:.6f}, {coords[1]:.6f}"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log(f"Kopiert: {text}")

    def set_start_from_coords(self, coords):
        self.start_point = (coords[0], coords[1])
        self.from_var.set(f"{coords[0]:.6f}, {coords[1]:.6f}")
        self._draw_endpoint("start", coords)

    def set_end_from_coords(self, coords):
        self.end_point = (coords[0], coords[1])
        self.to_var.set(f"{coords[0]:.6f}, {coords[1]:.6f}")
        self._draw_endpoint("end", coords)

    def _draw_endpoint(self, which, coords):
        if not self.map_widget:
            return
        attr = "start_marker" if which == "start" else "end_marker"
        old = getattr(self, attr)
        if old is not None:
            try:
                old.delete()
            except Exception:
                pass
        label = "Start" if which == "start" else "Ziel"
        setattr(self, attr, self.map_widget.set_marker(coords[0], coords[1], text=label))

    def use_current_as_start(self):
        try:
            lat, lon = self._coords()
        except dev.DeviceError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        self.set_start_from_coords((lat, lon))

    def on_map_search(self):
        query = self.search_var.get().strip()
        if not query:
            return
        self._geocode_async(query, "map")

    def _geocode_async(self, query, tag):
        def work():
            try:
                self.results.put(("geocode", tag, routing.geocode(query)))
            except Exception as e:
                self.results.put(("err", f"geocode:{tag}", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def on_geocode(self, which):
        query = (self.from_var if which == "from" else self.to_var).get().strip()
        if not query:
            return
        self._geocode_async(query, which)

    def _apply_geocode(self, tag, places):
        place = choose_place(self, places, lang=self.i18n.lang)
        if place is None:
            self.log("Keine Auswahl getroffen.")
            return
        if tag == "map":
            if self.map_widget:
                self.map_widget.set_position(place.lat, place.lon)
                self.map_widget.set_zoom(14)
            self.on_map_click((place.lat, place.lon))
        elif tag == "from":
            self.start_point = (place.lat, place.lon)
            self.from_var.set(place.name)
            self._draw_endpoint("start", (place.lat, place.lon))
        elif tag == "to":
            self.end_point = (place.lat, place.lon)
            self.to_var.set(place.name)
            self._draw_endpoint("end", (place.lat, place.lon))

    # ------------------------------------------------------------------
    # Verbindung
    # ------------------------------------------------------------------

    def on_connect(self):
        udid = self._selected_udid()
        if not udid:
            return
        self._set_busy(True)
        self.status_var.set("Verbinde ...")
        self.log(f"Verbinde mit {udid} ...")
        self.worker.submit("connect", lambda: self.backend.connect(udid))

    def on_disconnect(self):
        self.nav.stop()
        self._set_busy(True)
        self.status_var.set("Trenne ...")
        self.worker.submit("disconnect", lambda: self.backend.disconnect(True))

    def on_start_tunneld(self):
        self._set_busy(True)
        self.log("Starte tunneld ...")
        self.worker.submit("tunneld", dev.start_tunneld)

    def on_install_wintun(self):
        self._set_busy(True)
        self.worker.submit("wintun", dev.install_wintun)

    def on_enable_devmode(self):
        udid = self._selected_udid()
        if not udid:
            messagebox.showinfo(APP_NAME, "Kein Geraet ausgewaehlt.")
            return
        self._set_busy(True)
        self.log(f"Aktiviere Entwicklermodus fuer {udid} ...")
        self.worker.submit("devmode", lambda: dev.enable_developer_mode(udid))

    def _refresh_sim_status(self):
        try:
            if self.backend.connected:
                active = self.backend.simulation_active
                self.sim_status_var.set(
                    self.t("lbl_sim_active") if active else self.t("lbl_sim_inactive")
                )
            else:
                self.sim_status_var.set(self.t("lbl_sim_unknown"))
        except Exception:
            pass
        self.after(1000, self._refresh_sim_status)

    def on_export_log(self):
        content = self.log_box.get("1.0", "end")
        default_name = f"log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            parent=self, initialfile=default_name, defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("Alle Dateien" if self.i18n.lang == "de"
                                           else "All files", "*.*")],
        )
        if not path:
            return
        try:
            header = f"{APP_NAME} v{__version__} - {__copyright__}\n{'=' * 40}\n\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + content)
            self.log(f"Log exportiert: {path}" if self.i18n.lang == "de"
                     else f"Log exported: {path}")
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    # ------------------------------------------------------------------
    # Positionsaktionen
    # ------------------------------------------------------------------

    def on_teleport(self):
        try:
            lat, lon = self._coords()
        except dev.DeviceError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        if not self.backend.connected:
            messagebox.showinfo(APP_NAME, "Erst mit dem iPhone verbinden.")
            return
        self._set_marker(lat, lon, "Ziel")
        self.store.set_setting("last_lat", lat)
        self.store.set_setting("last_lon", lon)
        self._set_busy(True)
        self.log(f"Setze Position: {lat:.6f}, {lon:.6f}")
        self.worker.submit("teleport", lambda: self.backend.set_location(lat, lon))

    def on_reset(self):
        if not self.backend.connected:
            return
        self.nav.stop()
        self._set_busy(True)
        self.log("Setze auf echtes GPS zurueck ...")
        self.worker.submit("reset", self.backend.clear_location)

    # ------------------------------------------------------------------
    # Route
    # ------------------------------------------------------------------

    def on_profile_change(self):
        profile = self.profile_var.get()
        self.store.set_setting("profile", profile)
        self.speed_var.set(routing.DEFAULT_SPEED_KMH[profile])
        self.on_speed_change()

    def on_speed_change(self, _value=None):
        kmh = float(self.speed_var.get())
        self.speed_label.set(f"{kmh:.0f} km/h")
        self.nav.set_speed_kmh(kmh)
        self.store.set_setting("speed_kmh", kmh)

    def _resolve_endpoint(self, text, current):
        pair = routing.parse_coordinates(text)
        if pair:
            return pair
        return current

    def on_calculate_route(self):
        start = self._resolve_endpoint(self.from_var.get(), self.start_point)
        end = self._resolve_endpoint(self.to_var.get(), self.end_point)
        if not start or not end:
            messagebox.showinfo(
                APP_NAME,
                "Start und Ziel festlegen - per Rechtsklick auf der Karte, ueber "
                "die Lupe neben dem Feld oder als 'lat, lon'.")
            return
        self.start_point, self.end_point = start, end
        profile = self.profile_var.get()
        self.route_info.set("Berechne Route ...")

        def work():
            try:
                r = routing.calculate_route(start, end, profile)
                self.results.put(("route", "calc", r))
            except Exception as e:
                self.results.put(("err", "route", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _apply_route(self, route: routing.Route):
        self.route = route
        note = " (Luftlinie - Routing-Dienst nicht erreichbar)" if route.approximated else ""
        eta = routing.format_duration(route.duration_s) if route.duration_s else "-"
        self.route_info.set(
            f"{routing.format_distance(route.distance_m)} - Dienst-ETA {eta}"
            f" - {len(route.points)} Punkte{note}")
        self._draw_path(route.points)
        self._draw_endpoint("start", route.points[0])
        self._draw_endpoint("end", route.points[-1])
        if self.map_widget:
            mid = route.points[len(route.points) // 2]
            self.map_widget.set_position(mid[0], mid[1])
        self._update_buttons()
        self.log(f"Route berechnet: {routing.format_distance(route.distance_m)}")

    def _draw_path(self, points):
        if not self.map_widget:
            return
        if self.path_obj is not None:
            try:
                self.path_obj.delete()
            except Exception:
                pass
            self.path_obj = None
        if len(points) < 2:
            return
        step = max(1, len(points) // 1500)
        simplified = points[::step]
        if simplified[-1] != points[-1]:
            simplified.append(points[-1])
        try:
            self.path_obj = self.map_widget.set_path(simplified, width=4)
        except Exception as e:
            self.log(f"Route konnte nicht gezeichnet werden: {e}")

    def on_route_save(self):
        if not (self.start_point and self.end_point):
            messagebox.showinfo(APP_NAME, "Erst Start und Ziel festlegen.")
            return
        name = simpledialog.askstring(APP_NAME, "Name der Route:", parent=self)
        if not name:
            return
        self.store.add_route(name.strip(), self.start_point, self.end_point,
                             self.profile_var.get(),
                             self.from_var.get(), self.to_var.get())
        self._refresh_sidebar()
        self.log(f"Route gespeichert: {name}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def on_nav_start(self):
        if not (self.route and self.route.valid):
            messagebox.showinfo(APP_NAME, "Erst eine Route berechnen.")
            return
        if not self.backend.connected:
            messagebox.showinfo(APP_NAME, "Erst mit dem iPhone verbinden.")
            return
        points = routing.densify(self.route.points, max_segment_m=20.0)
        self.nav.start(points, float(self.speed_var.get()), self.loop_var.get())
        self.store.push_recent({
            "name": f"{self.from_var.get() or 'Start'} -> {self.to_var.get() or 'Ziel'}",
            "start": list(self.start_point),
            "end": list(self.end_point),
            "profile": self.profile_var.get(),
        })
        self._refresh_sidebar()
        self.log("Fahrt gestartet.")
        self._update_buttons()

    def on_nav_pause(self):
        self.nav.toggle_pause()

    def on_nav_stop(self):
        self.nav.stop()
        self.nav_info.set("Gestoppt.")
        self._update_buttons()

    def _nav_position(self, lat, lon, heading, progress):
        self.results.put(("navpos", "nav", (lat, lon, heading, progress)))

    def _handle_nav_position(self, payload):
        lat, lon, heading, progress = payload
        self.progress.configure(value=progress * 100)
        self.nav_info.set(
            f"{lat:.5f}, {lon:.5f} - Kurs {heading:.0f}° - "
            f"noch {routing.format_distance(self.nav.remaining_m)}")
        self._set_marker(lat, lon, "Fahrt")
        if self.map_widget:
            try:
                self.map_widget.set_position(lat, lon)
            except Exception:
                pass
        if self.backend.connected and not self._nav_inflight:
            self._nav_inflight = True
            self.worker.submit("navset", lambda: self.backend.set_location(lat, lon))

    # ------------------------------------------------------------------
    # Seitenleiste
    # ------------------------------------------------------------------

    def _refresh_sidebar(self):
        self.places_list.delete(0, "end")
        for p in self.store.places:
            self.places_list.insert("end", f"{p['name']}  ({p['lat']:.4f}, {p['lon']:.4f})")

        self.routes_list.delete(0, "end")
        for r in self.store.routes:
            self.routes_list.insert(
                "end", f"{r['name']}  [{routing.PROFILE_LABELS.get(r['profile'], '?')}]")

        self.recent_list.delete(0, "end")
        for r in self.store.recent:
            self.recent_list.insert("end", r.get("name", "Route"))

    def on_place_select(self, _event=None):
        sel = self.places_list.curselection()
        if not sel:
            return
        p = self.store.places[sel[0]]
        self.lat_var.set(f"{p['lat']:.6f}")
        self.lon_var.set(f"{p['lon']:.6f}")
        self._set_marker(p["lat"], p["lon"], p["name"])
        if self.map_widget:
            self.map_widget.set_position(p["lat"], p["lon"])

    def on_place_save(self):
        try:
            lat, lon = self._coords()
        except dev.DeviceError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        name = simpledialog.askstring(APP_NAME, "Name fuer diesen Ort:", parent=self)
        if not name:
            return
        self.store.add_place(name.strip(), lat, lon)
        self._refresh_sidebar()

    def on_place_delete(self):
        sel = self.places_list.curselection()
        if sel:
            self.store.remove_place(sel[0])
            self._refresh_sidebar()

    def _load_route_entry(self, entry):
        self.start_point = tuple(entry["start"])
        self.end_point = tuple(entry["end"])
        self.profile_var.set(entry.get("profile", "car"))
        self.from_var.set(entry.get("start_label") or
                          f"{self.start_point[0]:.6f}, {self.start_point[1]:.6f}")
        self.to_var.set(entry.get("end_label") or
                        f"{self.end_point[0]:.6f}, {self.end_point[1]:.6f}")
        self._draw_endpoint("start", self.start_point)
        self._draw_endpoint("end", self.end_point)
        self.on_calculate_route()

    def on_route_load(self):
        sel = self.routes_list.curselection()
        if sel:
            self._load_route_entry(self.store.routes[sel[0]])

    def on_route_delete(self):
        sel = self.routes_list.curselection()
        if sel:
            self.store.remove_route(sel[0])
            self._refresh_sidebar()

    def on_recent_load(self):
        sel = self.recent_list.curselection()
        if sel:
            self._load_route_entry(self.store.recent[sel[0]])

    def on_export_backup(self):
        de = self.i18n.lang == "de"
        path = filedialog.asksaveasfilename(
            parent=self, initialfile="ios_location_simulator_backup.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"),
                      ("Alle Dateien" if de else "All files", "*.*")],
        )
        if not path:
            return
        try:
            self.store.export_backup(path)
            msg = f"Exportiert: {path}" if de else f"Exported: {path}"
            self.log(msg)
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def on_import_backup(self):
        de = self.i18n.lang == "de"
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("JSON", "*.json"),
                      ("Alle Dateien" if de else "All files", "*.*")],
        )
        if not path:
            return
        try:
            added_places, added_routes = self.store.import_backup(path)
            self._refresh_sidebar()
            msg = (f"{added_places} Ort(e) und {added_routes} Route(n) importiert."
                   if de else
                   f"Imported {added_places} place(s) and {added_routes} route(s).")
            self.log(msg)
            messagebox.showinfo(APP_NAME, msg)
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    # ------------------------------------------------------------------
    # Ergebnisse
    # ------------------------------------------------------------------

    def _drain(self):
        try:
            while True:
                kind, tag, payload = self.results.get_nowait()

                if kind == "devices":
                    self._update_devices(payload)
                    self._poll_error_shown = False
                elif kind == "devices_err":
                    if not self._poll_error_shown:
                        self.status_var.set("Geraetesuche fehlgeschlagen")
                        self.log(payload)
                        self._poll_error_shown = True
                elif kind == "devlabel":
                    self.device_labels[tag] = payload
                    self._refresh_device_box()
                elif kind == "log":
                    self.log(payload)
                elif kind == "tunnel":
                    self.tunnel_var.set("Tunnel: laeuft" if payload else "Tunnel: aus")
                elif kind == "geocode":
                    self._apply_geocode(tag, payload)
                elif kind == "route":
                    self._apply_route(payload)
                elif kind == "navpos":
                    self._handle_nav_position(payload)
                elif kind == "navstate":
                    if payload == "finished":
                        self.nav_info.set("Ziel erreicht.")
                        self.log("Fahrt beendet.")
                    self._update_buttons()
                elif kind == "err":
                    if tag == "navset":
                        self._nav_inflight = False
                        self.log(f"Positionsupdate fehlgeschlagen: {payload}")
                        continue
                    self.log(f"FEHLER ({tag}): {payload}")
                    messagebox.showerror(APP_NAME, payload)
                    if tag == "connect":
                        self.backend.disconnect(clear_first=False)
                        self.status_var.set("Nicht verbunden")
                    self._set_busy(False)
                elif kind == "ok":
                    self._handle_ok(tag, payload)
        except queue.Empty:
            pass
        self.after(100, self._drain)

    def _handle_ok(self, tag, payload):
        if tag == "navset":
            self._nav_inflight = False
            return
        if tag == "connect":
            self.status_var.set(f"Verbunden: {payload}")
            self.log(f"Verbunden mit {payload}")
        elif tag == "disconnect":
            self.status_var.set("Nicht verbunden")
            self.log("Getrennt. Echte Position wiederhergestellt.")
        elif tag == "teleport":
            self.log("Position gesetzt.")
        elif tag == "reset":
            self.log("Echte GPS-Position wieder aktiv.")
        elif tag in ("tunneld", "wintun", "devmode"):
            self.log(str(payload))
            messagebox.showinfo(APP_NAME, str(payload))
        self._set_busy(False)

    # ------------------------------------------------------------------

    def _on_close(self):
        self.nav.stop()
        if self.backend.connected:
            if messagebox.askyesno(
                APP_NAME,
                "Noch verbunden. Vor dem Beenden die echte GPS-Position "
                "wiederherstellen?",
            ):
                try:
                    self.backend.disconnect(clear_first=True)
                except Exception:
                    pass
        if self.map_widget:
            try:
                lat, lon = self.map_widget.get_position()
                self.store.set_setting("last_lat", lat)
                self.store.set_setting("last_lon", lon)
                self.store.set_setting("zoom", int(self.map_widget.zoom))
            except Exception:
                pass
        self.worker.stop()
        self.destroy()
