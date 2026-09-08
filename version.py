# -*- coding: utf-8 -*-
"""Zentrale Versions- und Urheberangaben - an einer Stelle, damit sie beim
naechsten Release nur hier geaendert werden muessen."""

__version__ = "1.0.0"
__author__ = "saxcodez"
__copyright__ = "© 2026 saxcodez"

APP_TITLE = "iOS Location Simulator"


def full_title() -> str:
    return f"{APP_TITLE} v{__version__}"


def about_text() -> str:
    return f"{APP_TITLE}\nVersion {__version__}\n{__copyright__}"
