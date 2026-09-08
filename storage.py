# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""Persistente Ablage fuer Orte, Routen und Einstellungen."""

from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / "iOSLocationSimulator"
    p.mkdir(parents=True, exist_ok=True)
    return p


DATA_FILE = config_dir() / "data.json"

DEFAULT_DATA = {
    "places": [
        {"name": "Hamburg Rathaus", "lat": 53.550341, "lon": 9.992196},
        {"name": "Muenchen Marienplatz", "lat": 48.137154, "lon": 11.576124},
        {"name": "San Francisco", "lat": 37.774929, "lon": -122.419418},
    ],
    "routes": [],
    "recent": [],
    "settings": {
        "profile": "car",
        "speed_kmh": 50.0,
        "last_lat": 53.550341,
        "last_lon": 9.992196,
        "zoom": 11,
    },
}

MAX_RECENT = 12


class Store:
    def __init__(self):
        self.data = self._load()

    # -- IO ---------------------------------------------------------------

    def _load(self) -> dict:
        if not DATA_FILE.exists():
            self._write(DEFAULT_DATA)
            return json.loads(json.dumps(DEFAULT_DATA))
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return json.loads(json.dumps(DEFAULT_DATA))
        for key, default in DEFAULT_DATA.items():
            data.setdefault(key, json.loads(json.dumps(default)))
        for key, default in DEFAULT_DATA["settings"].items():
            data["settings"].setdefault(key, default)
        return data

    @staticmethod
    def _write(data: dict) -> None:
        tmp = DATA_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(DATA_FILE)

    def save(self) -> None:
        self._write(self.data)

    # -- Orte -------------------------------------------------------------

    @property
    def places(self) -> list:
        return self.data["places"]

    def add_place(self, name: str, lat: float, lon: float) -> None:
        self.places.append({"name": name, "lat": lat, "lon": lon})
        self.save()

    def remove_place(self, index: int) -> dict:
        item = self.places.pop(index)
        self.save()
        return item

    # -- Routen -----------------------------------------------------------

    @property
    def routes(self) -> list:
        return self.data["routes"]

    def add_route(self, name, start, end, profile, start_label="", end_label=""):
        self.routes.append(
            {
                "name": name,
                "start": [start[0], start[1]],
                "end": [end[0], end[1]],
                "profile": profile,
                "start_label": start_label,
                "end_label": end_label,
            }
        )
        self.save()

    def remove_route(self, index: int) -> dict:
        item = self.routes.pop(index)
        self.save()
        return item

    # -- Zuletzt verwendet ------------------------------------------------

    @property
    def recent(self) -> list:
        return self.data["recent"]

    def push_recent(self, entry: dict) -> None:
        key = (
            round(entry.get("start", [0, 0])[0], 5),
            round(entry.get("start", [0, 0])[1], 5),
            round(entry.get("end", [0, 0])[0], 5),
            round(entry.get("end", [0, 0])[1], 5),
        )
        kept = []
        for r in self.recent:
            rk = (
                round(r.get("start", [0, 0])[0], 5),
                round(r.get("start", [0, 0])[1], 5),
                round(r.get("end", [0, 0])[0], 5),
                round(r.get("end", [0, 0])[1], 5),
            )
            if rk != key:
                kept.append(r)
        self.data["recent"] = ([entry] + kept)[:MAX_RECENT]
        self.save()

    # -- Einstellungen ----------------------------------------------------

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    def set_setting(self, key: str, value) -> None:
        self.settings[key] = value
        self.save()

    # -- Export / Import (Orte + Routen), z.B. beim Geraete- oder Rechnerwechsel --

    def export_backup(self, path) -> None:
        """Schreibt Orte, Routen und Zuletzt-verwendet als eine JSON-Datei,
        die spaeter mit import_backup() wieder eingelesen werden kann."""
        payload = {
            "places": self.places,
            "routes": self.routes,
            "recent": self.recent,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def import_backup(self, path) -> tuple:
        """
        Liest eine zuvor exportierte Datei ein und fuegt Orte/Routen hinzu.
        Bereits vorhandene Eintraege (gleicher Name + gleiche Koordinaten)
        werden uebersprungen, nichts wird geloescht oder ueberschrieben.
        Gibt (Anzahl neuer Orte, Anzahl neuer Routen) zurueck.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        added_places = 0
        existing_place_keys = {
            (p.get("name"), round(float(p.get("lat", 0)), 6), round(float(p.get("lon", 0)), 6))
            for p in self.places
        }
        for p in data.get("places", []):
            try:
                lat, lon = float(p["lat"]), float(p["lon"])
                name = str(p["name"])
            except (KeyError, TypeError, ValueError):
                continue
            key = (name, round(lat, 6), round(lon, 6))
            if key in existing_place_keys:
                continue
            self.places.append({"name": name, "lat": lat, "lon": lon})
            existing_place_keys.add(key)
            added_places += 1

        added_routes = 0

        def route_key(r):
            return (
                r.get("name"),
                tuple(round(float(x), 6) for x in r.get("start", [0, 0])),
                tuple(round(float(x), 6) for x in r.get("end", [0, 0])),
                r.get("profile"),
            )

        existing_route_keys = set()
        for r in self.routes:
            try:
                existing_route_keys.add(route_key(r))
            except (TypeError, ValueError):
                continue

        for r in data.get("routes", []):
            if "start" not in r or "end" not in r:
                continue
            try:
                key = route_key(r)
                start = [float(r["start"][0]), float(r["start"][1])]
                end = [float(r["end"][0]), float(r["end"][1])]
            except (TypeError, ValueError, IndexError):
                continue
            if key in existing_route_keys:
                continue
            self.routes.append({
                "name": r.get("name", "Route"),
                "start": start,
                "end": end,
                "profile": r.get("profile", "car"),
                "start_label": r.get("start_label", ""),
                "end_label": r.get("end_label", ""),
            })
            existing_route_keys.add(key)
            added_routes += 1

        if added_places or added_routes:
            self.save()
        return added_places, added_routes
