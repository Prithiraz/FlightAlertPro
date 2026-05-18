import os
import logging
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests

try:
    from serpapi import GoogleSearch
except ImportError:  # pragma: no cover - optional dependency fallback
    GoogleSearch = None

logger = logging.getLogger(__name__)

_CACHE_MAX_AGE = timedelta(hours=24)
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".serpapi_cache"


def _safe_filename_part(value: str, *, default: str = "UNK", allow_hyphen: bool = False) -> str:
    pattern = r"[^A-Z0-9-]" if allow_hyphen else r"[^A-Z0-9]"
    cleaned = re.sub(pattern, "", (value or "").upper())
    return cleaned or default


def _resolve_cache_dir(cache_dir: Optional[str]) -> Path:
    if not cache_dir:
        return _DEFAULT_CACHE_DIR

    safe_dir_name = re.sub(r"[^a-zA-Z0-9_.-]", "", Path(cache_dir).name)
    if not safe_dir_name:
        return _DEFAULT_CACHE_DIR
    return _DEFAULT_CACHE_DIR / safe_dir_name


def _cache_file_path(
    from_iata: str,
    to_iata: str,
    departure_date: str,
    currency: str,
    cache_dir: Path,
) -> Path:
    safe_from = _safe_filename_part(from_iata, default="FROM")
    safe_to = _safe_filename_part(to_iata, default="TO")
    safe_date = _safe_filename_part(departure_date, default="DATE", allow_hyphen=True)
    safe_currency = _safe_filename_part(currency, default="USD")
    filename = f"cache_flights_{safe_from}_{safe_to}_{safe_date}_{safe_currency}.json"
    return cache_dir / filename


def _load_cached_response(cache_path: Path) -> Optional[Dict[str, Any]]:
    if not cache_path.exists():
        return None

    try:
        modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        if datetime.now(timezone.utc) - modified_at > _CACHE_MAX_AGE:
            return None
        with cache_path.open("r", encoding="utf-8") as cache_file:
            cached_payload = json.load(cache_file)
            if isinstance(cached_payload, dict):
                return cached_payload
    except Exception as exc:
        logger.warning("Failed reading SerpApi cache file %s: %s", cache_path, exc)
    return None


def _save_cached_response(cache_path: Path, payload: Dict[str, Any]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file)
    except Exception as exc:
        logger.warning("Failed writing SerpApi cache file %s: %s", cache_path, exc)


def _normalize_results(
    result: Dict,
    from_iata: str,
    to_iata: str,
    departure_date: str,
    currency: str,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    best_flights = result.get("best_flights", [])
    all_flights = best_flights if isinstance(best_flights, list) else []
    if not all_flights:
        other_flights = result.get("other_flights", [])
        all_flights = other_flights if isinstance(other_flights, list) else []

    default_booking_link = (
        result.get("search_metadata", {}).get("google_flights_url")
        or result.get("search_parameters", {}).get("google_flights_url")
    )

    if not all_flights:
        logger.info("No flights in SerpApi response for %s->%s", from_iata, to_iata)
        return []

    for flight_group in all_flights:
        try:
            flights = flight_group.get("flights", [])
            if not flights:
                continue

            price = float(flight_group.get("price", 0))
            if price <= 0:
                continue

            first_flight = flights[0]
            last_flight = flights[-1]
            flight_number = str(first_flight.get("flight_number", "")).strip()
            airline_name = first_flight.get("airline", "Unknown")

            parts = flight_number.split(" ", 1)
            airline_iata = parts[0] if parts and parts[0] else "XX"

            departure_time = first_flight.get("departure_airport", {}).get("time", "")
            arrival_time = last_flight.get("arrival_airport", {}).get("time", "")
            total_duration = int(float(flight_group.get("total_duration", 0) or 0))

            stops = len(flights) - 1
            booking_token = (
                flight_group.get("booking_token")
                or flight_group.get("flight_token")
                or first_flight.get("booking_token")
                or first_flight.get("token")
            )
            booking_link = default_booking_link
            if not booking_link and booking_token:
                if str(booking_token).startswith("http"):
                    booking_link = booking_token
                else:
                    booking_link = (
                        "https://www.google.com/travel/flights"
                        f"?hl=en#flt={from_iata}.{to_iata}.{departure_date};tt:o;t:{booking_token}"
                    )

            offer_id = f"serpapi-{from_iata}-{to_iata}-{departure_time}-{price}"
            normalized.append(
                {
                    "id": offer_id,
                    "provider": "serpapi",
                    "price": price,
                    "currency": currency,
                    "airline": airline_iata,
                    "airline_name": airline_name,
                    "flight_number": flight_number,
                    "from_iata": from_iata,
                    "to_iata": to_iata,
                    "departure": departure_time,
                    "arrival": arrival_time,
                    "stops": stops,
                    "duration_minutes": total_duration,
                    "cabin_class": "economy",
                    "booking_link": booking_link,
                    "booking_url": booking_link,
                }
            )
        except Exception as exc:
            logger.error("Error normalizing SerpApi flight offer: %s", exc)
            continue

    normalized.sort(key=lambda x: x["price"])
    logger.info("Normalized %s SerpApi flights for %s->%s", len(normalized), from_iata, to_iata)
    return normalized


def search_google_flights(
    from_iata: str,
    to_iata: str,
    departure_date: str,
    currency: str = "USD",
    *,
    api_key: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    resolved_api_key = api_key or os.getenv("SERPAPI_KEY")
    if not resolved_api_key:
        logger.warning("SerpApi key not configured, skipping request")
        return []

    route_from = (from_iata or "").upper()
    route_to = (to_iata or "").upper()
    route_date = (departure_date or "").strip()
    route_currency = (currency or "USD").upper()
    resolved_cache_dir = _resolve_cache_dir(cache_dir or os.getenv("SERPAPI_CACHE_DIR"))
    cache_path = _cache_file_path(route_from, route_to, route_date, route_currency, resolved_cache_dir)

    cached_payload = _load_cached_response(cache_path)
    if cached_payload is not None:
        return _normalize_results(cached_payload, route_from, route_to, route_date, route_currency)

    params: Dict[str, Any] = {
        "engine": "google_flights",
        "departure_id": route_from,
        "arrival_id": route_to,
        "outbound_date": route_date,
        "currency": route_currency,
        "hl": "en",
        "type": "2",
        "api_key": resolved_api_key,
    }

    try:
        logger.info("SerpApi request: %s -> %s", route_from, route_to)
        if GoogleSearch is not None:
            result = GoogleSearch(params).get_dict()
        else:
            response = requests.get(SerpApiService.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.error("SerpApi HTTP error (%s) for %s->%s: %s", status, route_from, route_to, exc)
        return []
    except requests.RequestException as exc:
        logger.error("SerpApi request failed for %s->%s: %s", route_from, route_to, exc)
        return []
    except Exception as exc:
        logger.error("SerpApi unexpected error for %s->%s: %s", route_from, route_to, exc)
        return []

    if not isinstance(result, dict):
        logger.error("SerpApi response was not a JSON object for %s->%s", route_from, route_to)
        return []
    if "error" in result:
        logger.error("SerpApi returned error for %s->%s: %s", route_from, route_to, result.get("error"))
        return []

    _save_cached_response(cache_path, result)
    return _normalize_results(result, route_from, route_to, route_date, route_currency)


class SerpApiService:
    """Flight search adapter for SerpApi's Google Flights engine."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.enabled = self.api_key is not None
        self.cache_dir = cache_dir or os.getenv("SERPAPI_CACHE_DIR") or ".serpapi_cache"

    def _search_flights_cached(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        currency: str,
    ) -> List[Dict[str, Any]]:
        return search_google_flights(
            from_iata=from_iata,
            to_iata=to_iata,
            departure_date=departure_date,
            currency=currency,
            api_key=self.api_key,
            cache_dir=self.cache_dir,
        )

    def search_flights(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        return_date: Optional[str] = None,
        currency: str = "USD",
    ) -> List[Dict[str, Any]]:
        """
        Search for flights using SerpApi's Google Flights engine.

        Returns a list of normalized flight offer dicts, sorted cheapest first.
        Returns an empty list if the service is disabled, the API returns an
        error, or no flights are found.
        """
        if not self.enabled:
            logger.info("SerpApi service disabled (no SERPAPI_KEY configured)")
            return []

        try:
            # SerpApi integration uses one-way searches only (type=2); return_date is ignored.
            return self._search_flights_cached(
                from_iata.upper(),
                to_iata.upper(),
                departure_date,
                (currency or "USD").upper(),
            )
        except Exception as e:
            logger.error(
                f"SerpApi search raised unexpected exception for {from_iata}->{to_iata}: {str(e)}"
            )
            return []


serpapi_service = SerpApiService()
