# -*- coding: utf-8 -*-
# Author: saxcodez  |  Copyright (c) 2026 saxcodez  |  License: MIT
"""
Bewegungssimulation entlang einer Route.

Der Motor laeuft in einem eigenen Thread, rechnet die Position anhand der
verstrichenen Zeit und der eingestellten Geschwindigkeit aus und reicht sie
ueber einen Callback nach draussen. Das Setzen auf dem Geraet passiert
absichtlich NICHT hier, sondern im Geraete-Worker der GUI - so bleibt der
Zugriff auf die DVT-Session einthreadig.
"""

from __future__ import annotations

import threading
import time

from routing import haversine, interpolate, bearing

TICK = 1.0  # Sekunden zwischen zwei Positionsupdates


class NavigationEngine:
    def __init__(self, on_position=None, on_state=None, on_finish=None):
        self.on_position = on_position or (lambda *_: None)
        self.on_state = on_state or (lambda *_: None)
        self.on_finish = on_finish or (lambda: None)

        self._points: list = []
        self._cum: list = []          # kumulierte Distanz je Punkt
        self._total = 0.0
        self._travelled = 0.0
        self._speed_mps = 13.9
        self._loop = False

        self._thread = None
        self._run = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()

    # -- Zustand ----------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    @property
    def progress(self) -> float:
        if self._total <= 0:
            return 0.0
        return min(1.0, self._travelled / self._total)

    @property
    def remaining_m(self) -> float:
        return max(0.0, self._total - self._travelled)

    def set_speed_kmh(self, kmh: float):
        with self._lock:
            self._speed_mps = max(0.1, float(kmh)) / 3.6

    def set_loop(self, value: bool):
        self._loop = bool(value)

    # -- Steuerung --------------------------------------------------------

    def start(self, points: list, speed_kmh: float, loop: bool = False):
        self.stop()
        if len(points) < 2:
            raise ValueError("Route braucht mindestens zwei Punkte.")

        self._points = list(points)
        self._cum = [0.0]
        for a, b in zip(self._points, self._points[1:]):
            self._cum.append(self._cum[-1] + haversine(a, b))
        self._total = self._cum[-1]
        self._travelled = 0.0
        self.set_speed_kmh(speed_kmh)
        self._loop = bool(loop)

        self._run.set()
        self._pause.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.on_state("running")

    def pause(self):
        if self.active and not self._pause.is_set():
            self._pause.set()
            self.on_state("paused")

    def resume(self):
        if self.active and self._pause.is_set():
            self._pause.clear()
            self.on_state("running")

    def toggle_pause(self):
        if self.paused:
            self.resume()
        else:
            self.pause()

    def stop(self):
        self._run.clear()
        self._pause.clear()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.5)
        self._thread = None

    # -- Kern -------------------------------------------------------------

    def _position_at(self, distance: float):
        """Punkt auf der Route bei gegebener Weglaenge."""
        if distance <= 0:
            return self._points[0], 0.0
        if distance >= self._total:
            last = self._points[-1]
            prev = self._points[-2] if len(self._points) > 1 else last
            return last, bearing(prev, last)

        lo, hi = 0, len(self._cum) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._cum[mid] <= distance:
                lo = mid
            else:
                hi = mid

        a, b = self._points[lo], self._points[lo + 1]
        seg = self._cum[lo + 1] - self._cum[lo]
        t = 0.0 if seg <= 0 else (distance - self._cum[lo]) / seg
        return interpolate(a, b, t), bearing(a, b)

    def _worker(self):
        last = time.monotonic()
        # Startpunkt sofort setzen
        pos, hdg = self._position_at(0.0)
        self.on_position(pos[0], pos[1], hdg, 0.0)

        while self._run.is_set():
            time.sleep(TICK)
            now = time.monotonic()
            dt = now - last
            last = now

            if self._pause.is_set():
                continue

            with self._lock:
                speed = self._speed_mps
            self._travelled += speed * dt

            if self._travelled >= self._total:
                if self._loop:
                    self._travelled = 0.0
                else:
                    pos, hdg = self._position_at(self._total)
                    self.on_position(pos[0], pos[1], hdg, 1.0)
                    self._run.clear()
                    self.on_state("finished")
                    self.on_finish()
                    return

            pos, hdg = self._position_at(self._travelled)
            self.on_position(pos[0], pos[1], hdg, self.progress)

        self.on_state("stopped")
