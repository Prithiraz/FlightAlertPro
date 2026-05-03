"""Weather service: fetches real-time METAR data and computes density altitude."""
import logging
import os
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# CheckWX free-tier base URL
_CHECKWX_BASE_URL = "https://api.checkwx.com"

# Conversion factor: hectopascals → inches of mercury
_HPA_TO_INHG = 33.8639

# Lazy-loaded airport lookup imported from metadata to avoid circular imports
_airports_by_iata: Optional[Dict] = None


def _get_airports_by_iata() -> Dict:
    """Return the AIRPORTS_BY_IATA index, loading it lazily."""
    global _airports_by_iata
    if _airports_by_iata is None:
        try:
            from metadata import AIRPORTS_BY_IATA
            _airports_by_iata = AIRPORTS_BY_IATA
        except Exception as exc:
            logger.warning("weather_service: could not import AIRPORTS_BY_IATA: %s", exc)
            _airports_by_iata = {}
    return _airports_by_iata


def _get_api_key() -> Optional[str]:
    """Return CheckWX API key from environment (avoids importing config at module level)."""
    try:
        from config import config
        return getattr(config, "CHECKWX_API_KEY", None) or os.getenv("CHECKWX_API_KEY")
    except Exception:
        return os.getenv("CHECKWX_API_KEY")


def get_metar_data(icao: str) -> Optional[Dict]:
    """Fetch decoded METAR for the given ICAO station from CheckWX API.

    Returns a dict with at least ``temperature_c`` and ``altimeter_in_hg`` on
    success, or *None* when the API is unavailable or the key is not configured.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("CHECKWX_API_KEY not configured; skipping METAR fetch for %s", icao)
        return None

    icao = icao.upper().strip()
    url = f"{_CHECKWX_BASE_URL}/metar/{icao}/decoded"
    try:
        resp = requests.get(
            url,
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(
                "CheckWX API returned %s for ICAO %s: %s",
                resp.status_code, icao, resp.text[:200],
            )
            return None

        payload = resp.json()
        results = payload.get("data", [])
        if not results:
            logger.warning("No METAR data returned for ICAO %s", icao)
            return None

        station = results[0]

        # --- temperature ---
        temp_entry = station.get("temperature") or {}
        temp_c: Optional[float] = None
        if isinstance(temp_entry, dict):
            temp_c = temp_entry.get("celsius")
        if temp_c is None:
            logger.warning("Temperature not found in METAR for %s", icao)
            return None

        # --- altimeter (pressure) ---
        altimeter_entry = station.get("altimeter") or {}
        altimeter_in_hg: Optional[float] = None
        if isinstance(altimeter_entry, dict):
            altimeter_in_hg = altimeter_entry.get("value")
            if altimeter_entry.get("unit") == "hPa":
                # Convert hPa to inHg
                altimeter_in_hg = float(altimeter_in_hg) / _HPA_TO_INHG
        if altimeter_in_hg is None:
            logger.warning("Altimeter not found in METAR for %s", icao)
            return None

        return {
            "temperature_c": float(temp_c),
            "altimeter_in_hg": float(altimeter_in_hg),
            "icao": icao,
            "raw_text": station.get("raw_text", ""),
        }

    except requests.exceptions.Timeout:
        logger.warning("CheckWX API timed out for ICAO %s", icao)
        return None
    except Exception as exc:
        logger.error("Error fetching METAR for %s: %s", icao, exc)
        return None


def calculate_density_altitude(
    elevation_ft: float,
    temp_c: float,
    altimeter_in_hg: float,
) -> Dict:
    """Apply the standard aerospace density-altitude formulas.

    Formulas
    --------
    Pressure Altitude (PA)  = Elevation + (29.92 - Altimeter) × 1000
    ISA Temperature (°C)    = 15 − (2 × Elevation / 1000)
      (standard ISA lapse rate ~2 °C per 1 000 ft, valid below the tropopause
       at approximately 36 089 ft)
    Density Altitude (DA)   = PA + 120 × (ActualTemp − ISATemp)

    Performance risk thresholds
    ---------------------------
    DA ≥ Elevation + 3 500 ft  →  HIGH
    DA ≥ Elevation + 2 000 ft  →  MODERATE
    otherwise                  →  LOW
    """
    pressure_altitude = elevation_ft + (29.92 - altimeter_in_hg) * 1000
    isa_temp_c = 15.0 - (2.0 * elevation_ft / 1000.0)
    density_altitude = pressure_altitude + 120.0 * (temp_c - isa_temp_c)

    da_above_elevation = density_altitude - elevation_ft
    if da_above_elevation >= 3500:
        risk_level = "HIGH"
    elif da_above_elevation >= 2000:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "elevation_ft": round(elevation_ft, 1),
        "pressure_altitude_ft": round(pressure_altitude, 1),
        "isa_temp_c": round(isa_temp_c, 1),
        "density_altitude_ft": round(density_altitude, 1),
        "da_above_elevation_ft": round(da_above_elevation, 1),
        "takeoff_risk_level": risk_level,
    }


def get_departure_performance(iata: str) -> Optional[Dict]:
    """High-level function: look up airport, fetch METAR, compute density altitude.

    Returns a dict containing ``density_altitude_ft`` and ``takeoff_risk_level``
    (and supporting data), or *None* when any required input is unavailable.
    """
    iata = iata.upper().strip()
    airports = _get_airports_by_iata()
    airport = airports.get(iata)

    if not airport:
        logger.warning("weather_service: airport %s not found in metadata", iata)
        return None

    icao: Optional[str] = airport.get("icao")
    elevation_ft = airport.get("altitude")  # OpenFlights stores altitude in feet

    if not icao:
        logger.warning("weather_service: no ICAO code for airport %s", iata)
        return None

    if elevation_ft is None:
        logger.warning("weather_service: no elevation for airport %s", iata)
        return None

    metar = get_metar_data(icao)
    if not metar:
        return None

    try:
        result = calculate_density_altitude(
            elevation_ft=float(elevation_ft),
            temp_c=metar["temperature_c"],
            altimeter_in_hg=metar["altimeter_in_hg"],
        )
    except (TypeError, ValueError, ArithmeticError) as exc:
        logger.error("Density altitude calculation failed for %s: %s", iata, exc)
        return None

    result["iata"] = iata
    result["icao"] = icao
    result["temperature_c"] = metar["temperature_c"]
    result["altimeter_in_hg"] = metar["altimeter_in_hg"]
    return result
