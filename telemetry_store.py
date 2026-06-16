"""In-memory store for the latest live telemetry snapshot.

The ingest endpoint replaces the snapshot wholesale; the ops dashboard reads the
full snapshot while the mobile driver view reads a single flight out of it by
flight id (ICAO24 hex or flight number).
"""
from __future__ import annotations

from threading import Lock
from typing import Optional

_CACHE: list[dict] = []
_UPDATED_AT: Optional[str] = None
_LOCK = Lock()


def set_snapshot(aircraft: list[dict], updated_at: str) -> None:
    """Replace the current telemetry snapshot."""
    global _CACHE, _UPDATED_AT
    with _LOCK:
        _CACHE = list(aircraft)
        _UPDATED_AT = updated_at


def get_snapshot() -> tuple[list[dict], Optional[str]]:
    """Return a copy of the full snapshot and the time it was last updated."""
    with _LOCK:
        return list(_CACHE), _UPDATED_AT


def get_flight(flight_id: str) -> Optional[dict]:
    """Look up a single flight by ICAO24 hex id or flight number."""
    if not flight_id:
        return None
    with _LOCK:
        for aircraft in _CACHE:
            if aircraft.get("hex_id") == flight_id or aircraft.get("flight_number") == flight_id:
                return dict(aircraft)
    return None
