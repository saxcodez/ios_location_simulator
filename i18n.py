# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Sprachumschaltung fuer die statische Oberflaeche (Fenstertitel, Buttons,
Rahmentitel, feste Hinweistexte).

Bewusste Abgrenzung: Das Protokollfenster (Verbindungsmeldungen, Fehler-
texte) bleibt deutsch, egal welche Sprache eingestellt ist. Diese Meldungen
sind an Dutzenden Stellen im Code als freier Text formuliert; sie alle
zweisprachig zu halten haette den Umfang dieser Aenderung vervielfacht.
Was hier umschaltet, ist alles, was der Anwender als feste Beschriftung
sieht, bevor er irgendetwas anklickt.
"""

from __future__ import annotations

LANGUAGES = ("de", "en")

STRINGS = {
    "window_title": {"de": "iOS Location Simulator", "en": "iOS Location Simulator"},
    "lbl_device": {"de": "Geraet:", "en": "Device:"},
    "btn_connect": {"de": "Verbinden", "en": "Connect"},
    "btn_disconnect": {"de": "Trennen", "en": "Disconnect"},
    "lbl_tunnel_unknown": {"de": "Tunnel: unbekannt", "en": "Tunnel: unknown"},
    "lbl_tunnel_running": {"de": "Tunnel: laeuft", "en": "Tunnel: running"},
    "lbl_tunnel_off": {"de": "Tunnel: aus", "en": "Tunnel: off"},
    "btn_start_tunneld": {"de": "tunneld starten", "en": "start tunneld"},
    "btn_install_wintun": {"de": "wintun.dll einrichten", "en": "set up wintun.dll"},
    "btn_enable_devmode": {"de": "Entwicklermodus aktivieren", "en": "Enable Developer Mode"},
    "hint_devmode": {
        "de": "(nur ohne Sperrcode automatisch - sonst manuell in den Einstellungen)",
        "en": "(automatic only without a passcode - otherwise set it manually in Settings)",
    },
    "lbl_sim_unknown": {"de": "Simulation: -", "en": "Simulation: -"},
    "lbl_sim_active": {"de": "Simulation: aktiv", "en": "Simulation: active"},
    "lbl_sim_inactive": {"de": "Simulation: inaktiv", "en": "Simulation: inactive"},
    "status_searching": {"de": "Suche Geraete ...", "en": "Searching for devices ..."},
    "tab_places": {"de": "Orte", "en": "Places"},
    "tab_routes": {"de": "Routen", "en": "Routes"},
    "tab_recent": {"de": "Zuletzt", "en": "Recent"},
    "btn_save": {"de": "Speichern", "en": "Save"},
    "btn_delete": {"de": "Loeschen", "en": "Delete"},
    "btn_load": {"de": "Laden", "en": "Load"},
    "btn_map_search": {"de": "Karte suchen", "en": "Search map"},
    "map_unavailable": {
        "de": ("Karte nicht verfuegbar.\n\n    pip install tkintermapview\n\n"
               "Alle Funktionen bleiben ueber die Koordinaten- und "
               "Adressfelder rechts nutzbar."),
        "en": ("Map unavailable.\n\n    pip install tkintermapview\n\n"
               "Everything else still works via the coordinate and address "
               "fields on the right."),
    },
    "grp_teleport": {"de": "Teleport", "en": "Teleport"},
    "lbl_lat": {"de": "Breite", "en": "Latitude"},
    "lbl_lon": {"de": "Laenge", "en": "Longitude"},
    "btn_set_position": {"de": "Position setzen", "en": "Set position"},
    "btn_restore_gps": {"de": "Echtes GPS wiederherstellen", "en": "Restore real GPS"},
    "grp_route": {"de": "Route", "en": "Route"},
    "lbl_from": {"de": "Von", "en": "From"},
    "lbl_to": {"de": "Nach", "en": "To"},
    "btn_use_current_as_start": {
        "de": "Aktuelle Position als Start", "en": "Use current position as start",
    },
    "btn_calc_route": {"de": "Route berechnen", "en": "Calculate route"},
    "btn_save_route": {"de": "Route speichern", "en": "Save route"},
    "route_info_none": {"de": "Keine Route berechnet.", "en": "No route calculated."},
    "grp_drive": {"de": "Fahrt simulieren", "en": "Simulate drive"},
    "lbl_speed": {"de": "Tempo", "en": "Speed"},
    "chk_loop": {"de": "Route wiederholen", "en": "Repeat route"},
    "btn_go": {"de": "Start", "en": "Start"},
    "btn_pause": {"de": "Pause", "en": "Pause"},
    "btn_stop": {"de": "Stopp", "en": "Stop"},
    "nav_ready": {"de": "Bereit.", "en": "Ready."},
    "lbl_protocol": {"de": "Protokoll", "en": "Log"},
    "btn_export_log": {"de": "Log exportieren", "en": "Export log"},
    "profile_foot": {"de": "Zu Fuss", "en": "Walk"},
    "profile_bike": {"de": "Fahrrad", "en": "Bike"},
    "profile_car": {"de": "Auto", "en": "Drive"},
    "dlg_choose_match": {"de": "Treffer auswaehlen", "en": "Choose a match"},
    "btn_apply": {"de": "Uebernehmen", "en": "Apply"},
    "btn_cancel": {"de": "Abbrechen", "en": "Cancel"},
    "menu_language": {"de": "Sprache", "en": "Language"},
    "btn_export_backup": {"de": "Exportieren", "en": "Export"},
    "btn_import_backup": {"de": "Importieren", "en": "Import"},
}


class I18n:
    """Haelt die aktuelle Sprache und liefert Uebersetzungen dazu."""

    def __init__(self, lang: str = "de"):
        self.lang = lang if lang in LANGUAGES else "de"

    def set(self, lang: str):
        if lang in LANGUAGES:
            self.lang = lang

    def toggle(self):
        self.lang = "en" if self.lang == "de" else "de"

    def t(self, key: str) -> str:
        entry = STRINGS.get(key)
        if not entry:
            return key
        return entry.get(self.lang, entry.get("de", key))
