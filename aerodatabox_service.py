import requests
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)

class AeroDataBoxService:
    BASE_URL = "https://aerodatabox.p.rapidapi.com"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1
    CACHE_TTL = 300

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.RAPIDAPI_KEY
        self.enabled = self.api_key is not None
        self.cache: Dict[str, tuple[float, List[Dict]]] = {}

    def _get_cache_key(self, from_iata: str, to_iata: str, date: str) -> str:
        return f"{from_iata}_{to_iata}_{date}"

    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL:
                logger.info(f"Cache hit for {cache_key}")
                return data
            else:
                del self.cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, data: List[Dict]):
        self.cache[cache_key] = (time.time(), data)

    def _make_request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("RapidAPI key not configured, skipping AeroDataBox request")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
        }

        try:
            logger.info(f"AeroDataBox Request: {endpoint}")
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"AeroDataBox Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"Request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"Request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None, passengers: int = 1) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("AeroDataBox adapter disabled (no RapidAPI key)")
            return []

        cache_key = self._get_cache_key(from_iata, to_iata, departure_date)
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        endpoint = f"/flights/airports/iata/{from_iata}/{departure_date}"
        params = {"withLocation": "false"}

        result = self._make_request(endpoint, params)

        if not result or "departures" not in result:
            return []

        normalized = self._normalize_flights(result["departures"], from_iata, to_iata)

        self._save_to_cache(cache_key, normalized)

        return normalized

    def _normalize_flights(self, departures: List[Dict], from_iata: str, to_iata: str) -> List[Dict[str, Any]]:
        normalized = []

        for flight in departures:
            try:
                arrival = flight.get("arrival", {})
                if arrival.get("airport", {}).get("iata") != to_iata:
                    continue

                departure_time = flight.get("departure", {}).get("scheduledTime", {}).get("utc")
                arrival_time = arrival.get("scheduledTime", {}).get("utc")

                if not departure_time or not arrival_time:
                    continue

                dep_dt = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                arr_dt = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
                duration_minutes = int((arr_dt - dep_dt).total_seconds() / 60)

                airline_code = flight.get("airline", {}).get("iata", "")
                airline_name = flight.get("airline", {}).get("name", "")

                normalized_offer = {
                    "id": f"aerodatabox_{flight.get('number', '')}",
                    "provider": "aerodatabox",
                    "price": 0,
                    "currency": "USD",
                    "airline": airline_code,
                    "airline_name": airline_name,
                    "from_iata": from_iata,
                    "to_iata": to_iata,
                    "departure": departure_time,
                    "arrival": arrival_time,
                    "stops": 0,
                    "duration_minutes": duration_minutes,
                    "cabin_class": "economy",
                    "booking_link": f"https://www.google.com/flights?q={from_iata}+to+{to_iata}",
                    "raw_data": flight
                }

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing AeroDataBox flight: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} AeroDataBox flights")
        return normalized

aerodatabox_service = AeroDataBoxService()
