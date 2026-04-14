"""Destination Hub – per-trip pre-travel intelligence endpoint."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from supabase import create_client

from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIRALO_AFFILIATE_CODE = "FLIGHTALERTPRO"
AIRALO_BASE_URL = "https://www.airalo.com"

try:
    import openai as _openai_lib
    _openai_available = True
except ImportError:
    _openai_available = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def _iata_to_country(iata: str) -> str:
    """Best-effort mapping from IATA airport code to country name.

    Falls back to the IATA code itself when no mapping is found.
    """
    mapping = {
        "NRT": "Japan", "HND": "Japan", "KIX": "Japan",
        "CDG": "France", "ORY": "France",
        "LHR": "United Kingdom", "LGW": "United Kingdom", "STN": "United Kingdom",
        "JFK": "United States", "LAX": "United States", "ORD": "United States",
        "SFO": "United States", "MIA": "United States", "ATL": "United States",
        "DXB": "United Arab Emirates", "AUH": "United Arab Emirates",
        "SIN": "Singapore",
        "BKK": "Thailand", "DMK": "Thailand",
        "DEL": "India", "BOM": "India", "MAA": "India",
        "SYD": "Australia", "MEL": "Australia",
        "YYZ": "Canada", "YVR": "Canada",
        "FRA": "Germany", "MUC": "Germany",
        "AMS": "Netherlands",
        "MAD": "Spain", "BCN": "Spain",
        "FCO": "Italy", "MXP": "Italy",
        "ICN": "South Korea", "GMP": "South Korea",
        "PEK": "China", "PVG": "China", "CAN": "China",
        "IST": "Turkey",
        "MEX": "Mexico",
        "GRU": "Brazil", "GIG": "Brazil",
        "EZE": "Argentina",
        "CPT": "South Africa", "JNB": "South Africa",
        "CAI": "Egypt",
        "NBO": "Kenya",
        "LOS": "Nigeria",
        "DPS": "Indonesia", "CGK": "Indonesia",
        "KUL": "Malaysia",
        "MNL": "Philippines",
        "HKG": "Hong Kong",
        "TPE": "Taiwan",
        "BNE": "Australia",
        "AKL": "New Zealand",
        "SCL": "Chile",
        "BOG": "Colombia",
        "LIM": "Peru",
        "VIE": "Austria",
        "ZRH": "Switzerland",
        "BRU": "Belgium",
        "LIS": "Portugal",
        "HEL": "Finland",
        "ARN": "Sweden",
        "CPH": "Denmark",
        "OSL": "Norway",
        "WAW": "Poland",
        "PRG": "Czech Republic",
        "BUD": "Hungary",
        "ATH": "Greece",
        "DUB": "Ireland",
    }
    return mapping.get(iata.upper(), iata.upper())


def _iata_to_city(iata: str) -> str:
    """Best-effort mapping from IATA airport code to city name."""
    mapping = {
        "NRT": "Tokyo", "HND": "Tokyo", "KIX": "Osaka",
        "CDG": "Paris", "ORY": "Paris",
        "LHR": "London", "LGW": "London", "STN": "London",
        "JFK": "New York", "LAX": "Los Angeles", "ORD": "Chicago",
        "SFO": "San Francisco", "MIA": "Miami", "ATL": "Atlanta",
        "DXB": "Dubai", "AUH": "Abu Dhabi",
        "SIN": "Singapore",
        "BKK": "Bangkok", "DMK": "Bangkok",
        "DEL": "Delhi", "BOM": "Mumbai", "MAA": "Chennai",
        "SYD": "Sydney", "MEL": "Melbourne",
        "YYZ": "Toronto", "YVR": "Vancouver",
        "FRA": "Frankfurt", "MUC": "Munich",
        "AMS": "Amsterdam",
        "MAD": "Madrid", "BCN": "Barcelona",
        "FCO": "Rome", "MXP": "Milan",
        "ICN": "Seoul", "GMP": "Seoul",
        "PEK": "Beijing", "PVG": "Shanghai", "CAN": "Guangzhou",
        "IST": "Istanbul",
        "MEX": "Mexico City",
        "GRU": "São Paulo", "GIG": "Rio de Janeiro",
        "EZE": "Buenos Aires",
        "CPT": "Cape Town", "JNB": "Johannesburg",
        "CAI": "Cairo",
        "NBO": "Nairobi",
        "LOS": "Lagos",
        "DPS": "Bali", "CGK": "Jakarta",
        "KUL": "Kuala Lumpur",
        "MNL": "Manila",
        "HKG": "Hong Kong",
        "TPE": "Taipei",
        "BNE": "Brisbane",
        "AKL": "Auckland",
        "SCL": "Santiago",
        "BOG": "Bogotá",
        "LIM": "Lima",
        "VIE": "Vienna",
        "ZRH": "Zurich",
        "BRU": "Brussels",
        "LIS": "Lisbon",
        "HEL": "Helsinki",
        "ARN": "Stockholm",
        "CPH": "Copenhagen",
        "OSL": "Oslo",
        "WAW": "Warsaw",
        "PRG": "Prague",
        "BUD": "Budapest",
        "ATH": "Athens",
        "DUB": "Dublin",
    }
    return mapping.get(iata.upper(), iata.upper())


def _call_openai_travel_intel(
    passport_nationality: str,
    destination_country: str,
    travel_month: str,
) -> dict:
    """Call OpenAI to generate visa/weather/packing JSON.

    Returns a dict with keys: visa_requirements, weather_expectation, packing_tips.
    Falls back to a generic placeholder when OpenAI is unavailable.
    """
    if not _openai_available or not config.OPENAI_API_KEY:
        logger.info("trip_service: OpenAI unavailable, returning placeholder intel")
        return _fallback_travel_intel(passport_nationality, destination_country, travel_month)

    prompt = (
        f"The user holds a {passport_nationality} passport and is traveling to "
        f"{destination_country} for a short-term tourist stay (under 30 days) in "
        f"{travel_month}. Return a JSON object with: "
        f"1. A factual 1-sentence visa requirement summary (key: visa_requirements), "
        f"2. A 1-sentence weather expectation (key: weather_expectation), and "
        f"3. Three specific packing tips as a JSON array of strings (key: packing_tips). "
        f"Respond ONLY with valid JSON."
    )

    try:
        client = _openai_lib.OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a travel expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        # Normalise packing_tips to a list
        if isinstance(data.get("packing_tips"), str):
            data["packing_tips"] = [data["packing_tips"]]
        return data
    except Exception as exc:
        logger.error(f"trip_service: OpenAI call failed: {exc}")
        return _fallback_travel_intel(passport_nationality, destination_country, travel_month)


def _fallback_travel_intel(passport_nationality: str, destination_country: str, travel_month: str) -> dict:
    return {
        "visa_requirements": (
            f"Please check the official embassy website for {destination_country} "
            f"visa requirements for {passport_nationality} passport holders."
        ),
        "weather_expectation": (
            f"Weather in {destination_country} during {travel_month} varies; "
            "check a local forecast closer to your departure."
        ),
        "packing_tips": [
            "Pack layers to adapt to changing temperatures.",
            "Bring a universal travel adapter.",
            "Carry a printed copy of your accommodation booking.",
        ],
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{alert_id}/hub")
async def get_trip_hub(alert_id: str, user_email: str):
    """Return pre-trip intelligence for a purchased flight alert.

    Query params:
        user_email: the authenticated user's email address.
    """
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    supabase = _get_supabase()

    # ------------------------------------------------------------------
    # 1. Fetch the price alert
    # ------------------------------------------------------------------
    try:
        alert_result = (
            supabase.table("price_alerts")
            .select("*")
            .eq("id", alert_id)
            .eq("user_email", user_email)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error(f"trip_service: error fetching alert {alert_id}: {exc}")
        raise HTTPException(status_code=404, detail="Alert not found")

    if not alert_result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = alert_result.data

    # ------------------------------------------------------------------
    # 2. Fetch user passport_nationality
    # ------------------------------------------------------------------
    try:
        profile_result = (
            supabase.table("user_profiles")
            .select("passport_nationality")
            .eq("email", user_email)
            .single()
            .execute()
        )
        passport_nationality = (
            profile_result.data.get("passport_nationality") if profile_result.data else None
        ) or "Unknown"
    except Exception as exc:
        logger.warning(f"trip_service: could not fetch passport for {user_email}: {exc}")
        passport_nationality = "Unknown"

    # ------------------------------------------------------------------
    # 3. Derive destination metadata
    # ------------------------------------------------------------------
    to_iata: str = alert.get("to_iata", "")
    from_iata: str = alert.get("from_iata", "")
    departure_date: Optional[str] = alert.get("departure_date")

    destination_country = _iata_to_country(to_iata)
    destination_city = _iata_to_city(to_iata)
    origin_city = _iata_to_city(from_iata)

    travel_month = "your travel month"
    if departure_date:
        try:
            travel_month = datetime.strptime(departure_date, "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # 4. Generate AI travel intel
    # ------------------------------------------------------------------
    intel = _call_openai_travel_intel(passport_nationality, destination_country, travel_month)

    # ------------------------------------------------------------------
    # 5. Build affiliate URL
    # ------------------------------------------------------------------
    country_slug = destination_country.lower().replace(" ", "-")
    esim_affiliate_url = f"{AIRALO_BASE_URL}/{country_slug}?ref={AIRALO_AFFILIATE_CODE}"

    # ------------------------------------------------------------------
    # 6. Compute countdown
    # ------------------------------------------------------------------
    days_until: Optional[int] = None
    if departure_date:
        try:
            dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
            days_until = max(0, (dep_dt - datetime.utcnow()).days)
        except ValueError:
            pass

    return {
        "alert_id": alert_id,
        "destination_city": destination_city,
        "destination_country": destination_country,
        "origin_city": origin_city,
        "from_iata": from_iata,
        "to_iata": to_iata,
        "departure_date": departure_date,
        "airline": alert.get("airline"),
        "purchase_price": alert.get("purchase_price"),
        "passport_nationality": passport_nationality,
        "travel_month": travel_month,
        "days_until_departure": days_until,
        "intel": intel,
        "esim_affiliate_url": esim_affiliate_url,
    }
