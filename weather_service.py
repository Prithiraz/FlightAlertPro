"""Aerospace Phase 2: Thermodynamic Performance Risk Analysis.

Provides real-time METAR data fetching via the CheckWX API and density-altitude
calculations following standard aerospace formulae.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import requests

from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CheckWX API client
# ---------------------------------------------------------------------------
CHECKWX_BASE_URL = "https://api.checkwx.com"


def fetch_metar(airport_iata: str) -> Optional[dict]:
    """Fetch the current METAR report for *airport_iata* via the CheckWX API.

    Returns a dict with keys ``temp_c``, ``altimeter_inhg``, and
    ``elevation_ft`` on success, or *None* when the API is unavailable or
    the key is not configured.
    """
    api_key = config.CHECKWX_API_KEY
    if not api_key:
        logger.warning(
            "CHECKWX_API_KEY not configured – density-altitude enrichment disabled."
        )
        return None

    url = f"{CHECKWX_BASE_URL}/metar/{airport_iata.upper()}/decoded"
    try:
        response = requests.get(
            url,
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(
                "CheckWX API returned status %s for %s",
                response.status_code,
                airport_iata,
            )
            return None

        payload = response.json()
        data_list = payload.get("data", [])
        if not data_list:
            logger.warning("No METAR data returned for %s", airport_iata)
            return None

        metar = data_list[0]

        # --- Temperature (°C) -----------------------------------------------
        temp_obj = metar.get("temperature", {})
        temp_c: Optional[float] = temp_obj.get("celsius") if isinstance(temp_obj, dict) else None

        # --- Altimeter (in Hg) -----------------------------------------------
        altimeter_obj = metar.get("altimeter", {})
        if isinstance(altimeter_obj, dict):
            # CheckWX returns both 'inhg' and 'kpa' sub-keys
            altimeter_inhg: Optional[float] = altimeter_obj.get("inhg")
        else:
            altimeter_inhg = None

        # --- Station elevation (ft) ------------------------------------------
        station = metar.get("station", {})
        # CheckWX provides elevation in metres inside station.elevation
        elevation_m: Optional[float] = (
            station.get("elevation", {}).get("meters")
            if isinstance(station, dict)
            else None
        )
        elevation_ft: Optional[float] = (
            round(elevation_m * 3.28084, 0) if elevation_m is not None else None
        )

        if temp_c is None or altimeter_inhg is None or elevation_ft is None:
            logger.warning(
                "Incomplete METAR data for %s (temp=%s, alt=%s, elev=%s)",
                airport_iata,
                temp_c,
                altimeter_inhg,
                elevation_ft,
            )
            return None

        return {
            "temp_c": float(temp_c),
            "altimeter_inhg": float(altimeter_inhg),
            "elevation_ft": float(elevation_ft),
        }

    except requests.RequestException as exc:
        logger.error("CheckWX request failed for %s: %s", airport_iata, exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error in fetch_metar for %s: %s", airport_iata, exc)
        return None


# ---------------------------------------------------------------------------
# Aerospace formulae
# ---------------------------------------------------------------------------

def calculate_density_altitude(
    elevation_ft: float,
    altimeter_inhg: float,
    temp_c: float,
) -> float:
    """Return the density altitude in feet using the standard aerospace formula.

    Formula:
        Pressure Altitude (PA) = Elevation + (29.92 - Altimeter) * 1000
        ISA Temperature (°C)   = 15 - (2 * Elevation / 1000)
        Density Altitude       = PA + 120 * (ActualTemp - ISATemp)

    Args:
        elevation_ft:     Physical field elevation in feet.
        altimeter_inhg:   Altimeter (station pressure) in inches of mercury.
        temp_c:           Actual outside air temperature in °C.

    Returns:
        Density altitude in feet (float).
    """
    pressure_altitude = elevation_ft + (29.92 - altimeter_inhg) * 1000
    isa_temp = 15 - (2 * elevation_ft / 1000)
    density_altitude = pressure_altitude + 120 * (temp_c - isa_temp)
    return round(density_altitude, 0)


def assess_takeoff_risk(density_altitude_ft: float, elevation_ft: float) -> str:
    """Return a takeoff performance risk level string.

    Rules:
        DA >= Elevation + 3500 ft → 'HIGH'
        DA >= Elevation + 2000 ft → 'MODERATE'
        Otherwise                 → 'LOW'

    Args:
        density_altitude_ft: Computed density altitude in feet.
        elevation_ft:        Physical field elevation in feet.

    Returns:
        One of 'LOW', 'MODERATE', or 'HIGH'.
    """
    delta = density_altitude_ft - elevation_ft
    if delta >= 3500:
        return "HIGH"
    if delta >= 2000:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def get_density_altitude_data(airport_iata: str) -> Tuple[Optional[float], Optional[str]]:
    """Fetch METAR and compute density altitude + takeoff risk for *airport_iata*.

    Returns:
        A tuple of (density_altitude_ft, takeoff_risk_level).
        Both values are *None* when METAR data is unavailable.
    """
    metar = fetch_metar(airport_iata)
    if metar is None:
        return None, None

    da = calculate_density_altitude(
        elevation_ft=metar["elevation_ft"],
        altimeter_inhg=metar["altimeter_inhg"],
        temp_c=metar["temp_c"],
    )
    risk = assess_takeoff_risk(da, metar["elevation_ft"])
    return da, risk
