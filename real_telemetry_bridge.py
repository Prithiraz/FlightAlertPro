import os
import time
from typing import Any

import requests

OPENSKY_URL = (
    "https://opensky-network.org/api/states/all"
    "?lamin=51.0&lomin=-0.5&lamax=52.0&lomax=0.5"
)
DEFAULT_INGEST_PATH = "/api/ingest_flight_data"
METERS_TO_FEET = 3.28084
MPS_TO_KNOTS = 1.94384


def _ingest_url() -> str:
    custom_url = os.getenv("TELEMETRY_INGEST_URL")
    if custom_url:
        return custom_url
    backend_host = os.getenv("TELEMETRY_BACKEND_HOST", "localhost")
    backend_port = os.getenv("TELEMETRY_BACKEND_PORT", "8000")
    return f"http://{backend_host}:{backend_port}{DEFAULT_INGEST_PATH}"


def _parse_state_vector(state: list[Any]) -> dict[str, Any] | None:
    if len(state) < 10:
        return None

    altitude_m = state[7]
    lon = state[5]
    lat = state[6]

    if altitude_m is None or lon is None or lat is None:
        return None

    flight_number = (state[1] or "").strip()
    ground_speed_kt = (state[9] or 0) * MPS_TO_KNOTS
    heading_deg = state[10] if len(state) > 10 and state[10] is not None else 0.0

    return {
        "hex_id": state[0],
        "flight_number": flight_number,
        "lon": lon,
        "lat": lat,
        "altitude": altitude_m * METERS_TO_FEET,
        "ground_speed": ground_speed_kt,
        "speed": ground_speed_kt,
        "heading": heading_deg,
    }


def fetch_aircraft() -> list[dict[str, Any]]:
    response = requests.get(OPENSKY_URL, timeout=15)
    response.raise_for_status()
    payload = response.json()
    states = payload.get("states") or []

    aircraft: list[dict[str, Any]] = []
    for state in states:
        if not isinstance(state, list):
            continue
        parsed = _parse_state_vector(state)
        if parsed:
            aircraft.append(parsed)
    return aircraft


def send_aircraft(aircraft: list[dict[str, Any]]) -> None:
    payload = {"aircraft": aircraft}
    response = requests.post(_ingest_url(), json=payload, timeout=15)
    response.raise_for_status()


def main() -> None:
    while True:
        try:
            aircraft = fetch_aircraft()
            send_aircraft(aircraft)
            print(f"Sent {len(aircraft)} aircraft")
        except requests.RequestException as exc:
            print(f"Telemetry bridge error: {exc}")
        time.sleep(10)


if __name__ == "__main__":
    main()
