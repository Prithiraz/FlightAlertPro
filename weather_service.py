"""Weather service: fetches real-time METAR data, computes density altitude,
and calculates aerodynamic wind components for cruise flight."""
import logging
import math
import os
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# CheckWX free-tier base URL
_CHECKWX_BASE_URL = "https://api.checkwx.com"

# Conversion factor: hectopascals → inches of mercury
_HPA_TO_INHG = 33.8639
_ISA_TEMP_C = 15.0
_ISA_ALTIMETER_INHG = 29.92
_ISA_PRESSURE_HPA = 1013.25

# Aerodynamic performance constants
_TAS_KT: float = 450.0          # Standard True Airspeed for commercial jets (knots)
_CRUISE_ALT_FT: int = 30000     # Default cruise altitude: FL300
_KM_PER_NM: float = 1.852       # Kilometres per nautical mile
_EARTH_RADIUS_KM: float = 6371.0

# 16-point compass rose mapping to degrees true
CARDINAL_TO_DEGREES = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}

# Lazy-loaded airport lookup imported from metadata to avoid circular imports
_airports_by_iata: Optional[Dict] = None

# Lazy-loaded airportsdata IATA index (loaded once per process)
_airportsdata_by_iata: Optional[Dict] = None


def _get_airportsdata() -> Dict:
    """Return the airportsdata IATA index, loading it lazily."""
    global _airportsdata_by_iata
    if _airportsdata_by_iata is None:
        try:
            import airportsdata
            _airportsdata_by_iata = airportsdata.load("IATA")
        except Exception as exc:
            logger.warning("weather_service: could not load airportsdata: %s", exc)
            _airportsdata_by_iata = {}
    return _airportsdata_by_iata


def iata_to_icao(iata: str) -> str:
    """Convert an IATA airport code to its 4-letter ICAO code.

    Falls back to the original IATA code when the library has no entry for it,
    so callers always receive a non-empty string.

    Parameters
    ----------
    iata : str
        3-letter IATA airport code (case-insensitive).

    Returns
    -------
    str
        4-letter ICAO code, or *iata* when no mapping is found.
    """
    iata_upper = iata.upper().strip()
    airports = _get_airportsdata()
    airport = airports.get(iata_upper)
    if airport:
        icao = airport.get("icao")
        if icao:
            return str(icao).upper()
    logger.debug("weather_service.iata_to_icao: no ICAO found for %s, using IATA as fallback", iata_upper)
    return iata_upper


def iata_to_airport_info(iata: str) -> Dict:
    """Resolve an IATA code to a dict with Full Airport Name, City, and Country.

    Always returns a dict with ``name``, ``city``, and ``country`` keys.
    Falls back to the IATA code and 'Unknown City' / 'Unknown' when the
    library cannot locate the airport, so callers never receive ``None``.

    Parameters
    ----------
    iata : str
        3-letter IATA airport code (case-insensitive).

    Returns
    -------
    dict
        ``name``    – Full airport name (e.g. "London Heathrow Airport").
        ``city``    – City name (e.g. "London").
        ``country`` – ISO 3166-1 alpha-2 country code (e.g. "GB").
    """
    iata_upper = iata.upper().strip()
    airports = _get_airportsdata()
    airport = airports.get(iata_upper)
    if airport:
        return {
            "name": airport.get("name") or iata_upper,
            "city": airport.get("city") or "Unknown City",
            "country": airport.get("country") or "Unknown",
        }
    logger.debug("weather_service.iata_to_airport_info: no entry for %s, returning defaults", iata_upper)
    return {"name": iata_upper, "city": "Unknown City", "country": "Unknown"}


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

    Uses the airportsdata library as the primary source for the IATA→ICAO
    translation and elevation.  Falls back to the internal OpenFlights metadata
    index for any fields not found in airportsdata.

    Returns a dict containing ``density_altitude_ft`` and ``takeoff_risk_level``
    (and supporting data), or *None* when any required input is unavailable.
    """
    iata = iata.upper().strip()

    # Primary lookup via airportsdata (ICAO + elevation in feet)
    icao: Optional[str] = None
    elevation_ft: Optional[float] = None
    ad_airports = _get_airportsdata()
    ad_entry = ad_airports.get(iata)
    if ad_entry:
        icao = ad_entry.get("icao") or None
        raw_elev = ad_entry.get("elevation")
        if raw_elev is not None:
            try:
                elevation_ft = float(raw_elev)
            except (TypeError, ValueError):
                pass

    # Secondary lookup via internal OpenFlights metadata
    airports = _get_airports_by_iata()
    airport = airports.get(iata)

    if not icao:
        if not airport:
            logger.warning("weather_service: airport %s not found in metadata", iata)
            return None
        icao = airport.get("icao")

    if not icao:
        logger.warning("weather_service: no ICAO code for airport %s", iata)
        return None

    # Use internal metadata elevation as fallback when airportsdata had none
    if elevation_ft is None and airport:
        raw_elev = airport.get("altitude")  # OpenFlights stores altitude in feet
        if raw_elev is not None:
            try:
                elevation_ft = float(raw_elev)
            except (TypeError, ValueError):
                pass

    if elevation_ft is None:
        logger.warning("weather_service: no elevation for airport %s", iata)
        return None

    metar = get_metar_data(icao) or {}
    raw_temp_c = metar.get("temperature_c")
    raw_altimeter_in_hg = metar.get("altimeter_in_hg")

    try:
        temp_c = float(raw_temp_c) if raw_temp_c is not None else _ISA_TEMP_C
    except (TypeError, ValueError):
        temp_c = _ISA_TEMP_C

    try:
        altimeter_in_hg = (
            float(raw_altimeter_in_hg) if raw_altimeter_in_hg is not None else _ISA_ALTIMETER_INHG
        )
    except (TypeError, ValueError):
        altimeter_in_hg = _ISA_ALTIMETER_INHG

    if raw_temp_c is None:
        logger.warning(
            "METAR temperature missing for %s; falling back to ISA %.1f°C",
            icao,
            _ISA_TEMP_C,
        )
    if raw_altimeter_in_hg is None:
        logger.warning(
            "METAR pressure missing for %s; falling back to ISA %.2f inHg (%.2f hPa)",
            icao,
            _ISA_ALTIMETER_INHG,
            _ISA_PRESSURE_HPA,
        )

    try:
        result = calculate_density_altitude(
            elevation_ft=elevation_ft,
            temp_c=temp_c,
            altimeter_in_hg=altimeter_in_hg,
        )
    except (TypeError, ValueError, ArithmeticError) as exc:
        logger.error("Density altitude calculation failed for %s: %s", iata, exc)
        return None

    result["iata"] = iata
    result["icao"] = icao
    result["temperature_c"] = temp_c
    result["altimeter_in_hg"] = altimeter_in_hg
    return result


# ---------------------------------------------------------------------------
# Phase 3: Aerodynamic Performance & Dynamic ETA
# ---------------------------------------------------------------------------

def _calculate_true_course(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial true bearing (degrees, 0–360) from point 1 to point 2.

    Uses the standard forward-azimuth formula on a spherical Earth.
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(delta_lon)
    bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    return bearing


def get_winds_aloft(
    from_icao: str,
    altitude_ft: int = _CRUISE_ALT_FT,
) -> Optional[Dict]:
    """Fetch forecast wind data from the CheckWX TAF endpoint.

    .. note::
        TAF (Terminal Aerodrome Forecast) data describes wind conditions at
        the terminal area (typically surface to a few thousand feet AGL) and
        does not represent true winds-aloft at cruise altitude (FL300).  It is
        used here as an accessible proxy via the existing CheckWX API key.  The
        ``altitude_ft`` parameter is stored in the returned dict for reference
        and to allow callers to log the intended cruise altitude, but the wind
        direction and speed values themselves come from the TAF surface forecast.

    Returns a dict with ``wind_direction_deg``, ``wind_speed_kt``, and
    ``altitude_ft``, or *None* when the API is unavailable.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("CHECKWX_API_KEY not configured; skipping winds aloft for %s", from_icao)
        return None

    icao = from_icao.upper().strip()
    url = f"{_CHECKWX_BASE_URL}/taf/{icao}/decoded"
    try:
        resp = requests.get(
            url,
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(
                "CheckWX TAF returned %s for ICAO %s: %s",
                resp.status_code, icao, resp.text[:200],
            )
            return None

        payload = resp.json()
        results = payload.get("data", [])
        if not results:
            logger.warning("No TAF data returned for ICAO %s", icao)
            return None

        # Use the first available forecast period
        forecasts = results[0].get("forecast", [])
        if not forecasts:
            return None

        wind = forecasts[0].get("wind") or {}
        if not isinstance(wind, dict):
            return None

        wind_dir = wind.get("direction")
        wind_speed = wind.get("speed_kts") or wind.get("speed")

        if wind_dir is None or wind_speed is None:
            return None

        if isinstance(wind_dir, str):
            wind_dir = CARDINAL_TO_DEGREES.get(wind_dir.strip().upper())
            if wind_dir is None:
                logger.warning("Unsupported cardinal wind direction for ICAO %s: %r", icao, wind.get("direction"))
                return None

        return {
            "wind_direction_deg": float(wind_dir),
            "wind_speed_kt": float(wind_speed),
            "altitude_ft": altitude_ft,
            "source": "checkwx_taf",
            "icao": icao,
        }

    except requests.exceptions.Timeout:
        logger.warning("CheckWX TAF API timed out for ICAO %s", icao)
        return None
    except Exception as exc:
        logger.error("Error fetching winds aloft for ICAO %s: %s", icao, exc)
        return None


def calculate_wind_component(
    wind_dir_deg: float,
    wind_speed_kt: float,
    true_course_deg: float,
) -> Dict:
    """Solve the wind triangle and return the headwind / tailwind component.

    Uses the Law of Cosines projection:

        wind_component = -V_wind × cos(WindDir − Course)

    A positive value indicates a **tailwind** (ground speed > TAS);
    a negative value indicates a **headwind** (ground speed < TAS).

    Parameters
    ----------
    wind_dir_deg : float
        Meteorological wind direction – the direction the wind is blowing
        *from*, in degrees true (0–360).
    wind_speed_kt : float
        Wind speed in knots.
    true_course_deg : float
        True course from origin to destination in degrees (0–360).

    Returns
    -------
    dict
        ``wind_component_kt``  – tailwind (+) or headwind (−) in knots.
        ``ground_speed_kt``    – effective ground speed in knots.
        ``wind_type``          – ``"tailwind"`` or ``"headwind"``.
    """
    # Wind direction is meteorological convention: the direction the wind blows FROM.
    # The component along the course is: −V_wind × cos(WindDir − Course).
    # A positive result means the wind is helping (tailwind); negative means opposing (headwind).
    angle_diff = math.radians(wind_dir_deg - true_course_deg)
    wind_component_kt = round(-wind_speed_kt * math.cos(angle_diff), 1)
    ground_speed_kt = max(_TAS_KT + wind_component_kt, 1.0)  # guard against zero/negative GS

    return {
        "wind_component_kt": wind_component_kt,
        "ground_speed_kt": round(ground_speed_kt, 1),
        "wind_type": "tailwind" if wind_component_kt >= 0 else "headwind",
    }


def get_aerodynamic_performance(
    from_iata: str,
    to_iata: str,
    altitude_ft: int = _CRUISE_ALT_FT,
) -> Optional[Dict]:
    """High-level function: compute the wind component and aerodynamic ETA adjustment.

    1. Looks up lat/lon for both airports (internal metadata index).
    2. Resolves the departure ICAO code via airportsdata (falls back to metadata).
    3. Calculates the true course bearing.
    4. Fetches winds aloft from CheckWX TAF for the departure airport.
    5. Solves the wind triangle to get head/tailwind component and ground speed.

    Returns a dict with wind and ground-speed data, or *None* when any
    required input is unavailable.
    """
    from_iata = from_iata.upper().strip()
    to_iata = to_iata.upper().strip()
    airports = _get_airports_by_iata()

    origin = airports.get(from_iata)
    destination = airports.get(to_iata)

    if not origin or not destination:
        logger.warning(
            "aerodynamic_performance: airport(s) not found: %s / %s", from_iata, to_iata
        )
        return None

    lat1 = origin.get("latitude")
    lon1 = origin.get("longitude")
    lat2 = destination.get("latitude")
    lon2 = destination.get("longitude")

    if None in (lat1, lon1, lat2, lon2):
        logger.warning("aerodynamic_performance: missing coordinates for %s or %s", from_iata, to_iata)
        return None

    true_course = _calculate_true_course(float(lat1), float(lon1), float(lat2), float(lon2))

    # Prefer airportsdata for ICAO, fall back to internal metadata.
    # iata_to_icao returns the 3-letter IATA code itself when no ICAO is found
    # in airportsdata, so we also check the metadata index for a 4-letter code.
    candidate_icao: str = iata_to_icao(from_iata)
    if candidate_icao == from_iata:
        # airportsdata had no mapping; try internal metadata
        candidate_icao = origin.get("icao") or ""

    # Validate that we have a proper 4-letter ICAO code before making API calls
    if len(candidate_icao) != 4:
        logger.warning(
            "aerodynamic_performance: could not resolve a valid ICAO code for %s (got %r)",
            from_iata, candidate_icao,
        )
        return None

    origin_icao: str = candidate_icao

    wind = get_winds_aloft(origin_icao, altitude_ft=altitude_ft)
    if not wind:
        return None

    components = calculate_wind_component(
        wind_dir_deg=wind["wind_direction_deg"],
        wind_speed_kt=wind["wind_speed_kt"],
        true_course_deg=true_course,
    )

    return {
        "from_iata": from_iata,
        "to_iata": to_iata,
        "true_course_deg": round(true_course, 1),
        "wind_direction_deg": wind["wind_direction_deg"],
        "wind_speed_kt": wind["wind_speed_kt"],
        "altitude_ft": altitude_ft,
        "tas_kt": _TAS_KT,
        **components,
    }
