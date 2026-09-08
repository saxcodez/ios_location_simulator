# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Adresssuche und Routenberechnung ueber offene OSM-Dienste.

Geocoding: Nominatim
Routing:   OSRM (oeffentliche Instanzen von openstreetmap.de)

Beides ohne API-Key. Wenn kein Routing-Dienst erreichbar ist, faellt das Modul
auf eine gerade Linie zwischen Start und Ziel zurueck, damit die
Bewegungssimulation trotzdem nutzbar bleibt.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = "iOSLocationSimulator/1.0 (internal QA tool)"

NOMINATIM = "https://nominatim.openstreetmap.org/search"

OSRM_ENDPOINTS = {
    "car": ("https://routing.openstreetmap.de/routed-car", "driving"),
    "bike": ("https://routing.openstreetmap.de/routed-bike", "bike"),
    "foot": ("https://routing.openstreetmap.de/routed-foot", "foot"),
}
OSRM_FALLBACK = ("https://router.project-osrm.org", "driving")

PROFILE_LABELS = {
    "foot": "Zu Fuss",
    "bike": "Fahrrad",
    "car": "Auto",
}

DEFAULT_SPEED_KMH = {"foot": 5.0, "bike": 18.0, "car": 50.0}


class RoutingError(Exception):
    pass


@dataclass
class Place:
    name: str
    lat: float
    lon: float

    def __str__(self):
        return self.name


@dataclass
class Route:
    points: list = field(default_factory=list)   # [(lat, lon), ...]
    distance_m: float = 0.0
    duration_s: float = 0.0
    approximated: bool = False

    @property
    def valid(self) -> bool:
        return len(self.points) >= 2


# --------------------------------------------------------------------------
# Geometrie
# --------------------------------------------------------------------------

EARTH_R = 6371008.8


def haversine(a, b) -> float:
    """Distanz in Metern zwischen (lat, lon)-Tupeln."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def interpolate(a, b, t: float):
    """Lineare Interpolation zwischen zwei Punkten (fuer kurze Segmente ok)."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def bearing(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _get_json(url: str, timeout: float = 12.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Geocoding
# --------------------------------------------------------------------------

def geocode(query: str, limit: int = 6) -> list:
    query = (query or "").strip()
    if not query:
        return []

    # Direkte Koordinateneingabe erlauben: "53.5503, 9.9922"
    coords = parse_coordinates(query)
    if coords:
        return [Place(f"{coords[0]:.6f}, {coords[1]:.6f}", coords[0], coords[1])]

    params = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": str(limit), "addressdetails": "0"}
    )
    try:
        data = _get_json(f"{NOMINATIM}?{params}")
    except Exception as e:
        raise RoutingError(f"Adresssuche nicht erreichbar: {e}") from e

    out = []
    for item in data:
        try:
            out.append(
                Place(item.get("display_name", query), float(item["lat"]), float(item["lon"]))
            )
        except (KeyError, ValueError):
            continue
    return out


def parse_coordinates(text: str):
    """Erkennt 'lat, lon' bzw. 'lat lon'. Gibt None zurueck, wenn kein Paar."""
    cleaned = (text or "").replace(";", ",").strip()
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",")]
    else:
        parts = [p for p in cleaned.split() if p]
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return (lat, lon)
    return None


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------

def calculate_route(start, end, profile: str = "car") -> Route:
    """
    start/end: (lat, lon). profile: foot | bike | car
    Faellt auf eine Luftlinie zurueck, wenn kein Dienst antwortet.
    """
    candidates = []
    if profile in OSRM_ENDPOINTS:
        candidates.append(OSRM_ENDPOINTS[profile])
    candidates.append(OSRM_FALLBACK)

    coord = f"{start[1]:.6f},{start[0]:.6f};{end[1]:.6f},{end[0]:.6f}"
    query = "overview=full&geometries=geojson&alternatives=false&steps=false"

    last_error = None
    for base, osrm_profile in candidates:
        for prof in (osrm_profile, "driving"):
            url = f"{base}/route/v1/{prof}/{coord}?{query}"
            try:
                data = _get_json(url)
            except Exception as e:
                last_error = e
                continue
            if data.get("code") != "Ok" or not data.get("routes"):
                last_error = RoutingError(data.get("message", "Keine Route gefunden"))
                continue
            r = data["routes"][0]
            coords = r["geometry"]["coordinates"]  # [lon, lat]
            points = [(c[1], c[0]) for c in coords]
            return Route(
                points=points,
                distance_m=float(r.get("distance", 0.0)),
                duration_s=float(r.get("duration", 0.0)),
                approximated=False,
            )

    # Fallback: Luftlinie in ~50 m Schritten
    dist = haversine(start, end)
    steps = max(2, min(4000, int(dist / 50)))
    points = [interpolate(start, end, i / steps) for i in range(steps + 1)]
    return Route(points=points, distance_m=dist, duration_s=0.0, approximated=True)


def densify(points: list, max_segment_m: float = 25.0) -> list:
    """
    Fuegt Zwischenpunkte ein, damit lange Geraden gleichmaessig abgefahren
    werden. Verhindert Spruenge bei hohen Geschwindigkeiten.
    """
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        seg = haversine(a, b)
        n = int(seg // max_segment_m)
        for i in range(1, n + 1):
            out.append(interpolate(a, b, i / (n + 1)))
        out.append(b)
    return out


def format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{meters:.0f} m"
    return f"{meters / 1000:.1f} km"


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"
