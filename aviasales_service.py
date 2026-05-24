import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_AVIASALES_BASE_URL = "https://api.travelpayouts.com"
_AVIASALES_BOOKING_BASE_URL = "https://aviasales.com"


def _build_booking_link(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    link = str(link).strip()
    if not link:
        return None
    if link.startswith("http://") or link.startswith("https://"):
        return link
    separator = "" if link.startswith("/") else "/"
    return f"{_AVIASALES_BOOKING_BASE_URL}{separator}{link}"


def _normalize_v1_entry(origin: str, destination: str, currency: str, offer: Dict[str, Any]) -> Dict[str, Any]:
    booking_link = _build_booking_link(offer.get("link"))
    airline = str(offer.get("airline") or "XX").upper()
    flight_number_value = offer.get("flight_number")
    flight_number = str(flight_number_value) if flight_number_value is not None else ""
    departure = offer.get("departure_at")
    arrival = offer.get("return_at") or offer.get("arrival_at") or departure
    price = float(offer.get("price") or 0)

    price_id = int(round(price * 100))
    departure_token = re.sub(r"[^0-9A-Za-z]", "", str(departure or "unknown")) or "unknown"
    duration_minutes = None
    if departure and arrival:
        try:
            dep_dt = datetime.fromisoformat(str(departure).replace("Z", "+00:00"))
            arr_dt = datetime.fromisoformat(str(arrival).replace("Z", "+00:00"))
            delta_minutes = int((arr_dt - dep_dt).total_seconds() // 60)
            duration_minutes = delta_minutes if delta_minutes >= 0 else None
        except Exception:
            duration_minutes = None
    return {
        "id": f"aviasales-{origin}-{destination}-{departure_token}-{price_id}-{flight_number or 'NA'}",
        "provider": "aviasales",
        "price": price,
        "currency": (currency or "USD").upper(),
        "airline": airline,
        "airline_name": airline,
        "flight_number": flight_number,
        "from_iata": origin,
        "to_iata": destination,
        "departure": departure or "",
        "arrival": arrival or "",
        "stops": int(offer.get("number_of_changes") or 0),
        "duration_minutes": duration_minutes,
        "cabin_class": "economy",
        "booking_link": booking_link,
        "booking_url": booking_link,
    }


def search_cached_flights(
    origin: str,
    destination: str,
    departure_date: Optional[str] = None,
    currency: str = "USD",
) -> List[Dict[str, Any]]:
    token = os.getenv("TRAVELPAYOUTS_TOKEN")
    if not token:
        logger.warning("TRAVELPAYOUTS_TOKEN not configured, skipping Aviasales request")
        return []

    try:
        response = requests.get(
            f"{_AVIASALES_BASE_URL}/v1/prices/cheap",
            params={
                "origin": (origin or "").upper(),
                "destination": (destination or "").upper(),
                "depart_date": departure_date,
                "currency": (currency or "USD").upper(),
                "token": token,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("Aviasales request failed for %s->%s: %s", origin, destination, exc)
        return []
    except Exception as exc:
        logger.warning("Aviasales response parsing failed for %s->%s: %s", origin, destination, exc)
        return []

    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return []

    results: List[Dict[str, Any]] = []
    for to_iata, offer in data.items():
        if not isinstance(offer, dict):
            continue
        try:
            results.append(
                _normalize_v1_entry(
                    origin=(origin or "").upper(),
                    destination=str(to_iata or destination or "").upper(),
                    currency=(currency or "USD").upper(),
                    offer=offer,
                )
            )
        except Exception as exc:
            logger.warning("Failed to normalize Aviasales offer: %s", exc)
            continue

    return results


class AviasalesService:
    def __init__(self):
        self.enabled = bool(os.getenv("TRAVELPAYOUTS_TOKEN"))

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        currency: str = "USD",
    ) -> List[Dict[str, Any]]:
        return search_cached_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            currency=currency,
        )


aviasales_service = AviasalesService()
