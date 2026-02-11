import requests
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from config import config

logger = logging.getLogger(__name__)

class RapidAPIAdapterCache:
    def __init__(self):
        self.cache = {}
        self.ttl = 300

    def get(self, key: str) -> Optional[List[Dict]]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: List[Dict]):
        self.cache[key] = (value, time.time())

cache = RapidAPIAdapterCache()

class RapidAPIAdapter:
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.RAPIDAPI_KEY
        self.enabled = self.api_key is not None

    def _make_request(self, url: str, headers: Dict, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("RapidAPI key not configured, skipping request")
            return None

        try:
            logger.info(f"RapidAPI Request: {url}")
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by RapidAPI, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(url, headers, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"RapidAPI Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"RapidAPI request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(url, headers, retry_count + 1)
            else:
                logger.error(f"RapidAPI request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

class AeroDataBoxAdapter(RapidAPIAdapter):
    BASE_URL = "https://aerodatabox.p.rapidapi.com"

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("AeroDataBox adapter disabled (no API key)")
            return []

        cache_key = f"aerodatabox:{from_iata}:{to_iata}:{departure_date}:{return_date}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached AeroDataBox results for {cache_key}")
            return cached

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
        }

        url = f"{self.BASE_URL}/flights/airports/iata/{from_iata}/{departure_date}T00:00/{departure_date}T23:59"
        result = self._make_request(url, headers)

        if not result or "departures" not in result:
            return []

        normalized = self._normalize_offers(result["departures"], from_iata, to_iata)
        cache.set(cache_key, normalized)
        return normalized

    def _normalize_offers(self, departures: List[Dict], from_iata: str, to_iata: str) -> List[Dict[str, Any]]:
        normalized = []

        for flight in departures:
            try:
                arrival_airport = flight.get("arrival", {}).get("airport", {}).get("iata")
                if arrival_airport != to_iata:
                    continue

                normalized_offer = {
                    "id": flight.get("number", ""),
                    "provider": "aerodatabox",
                    "price": 0,
                    "currency": "USD",
                    "airline": flight.get("airline", {}).get("iata", ""),
                    "airline_name": flight.get("airline", {}).get("name", ""),
                    "from_iata": from_iata,
                    "to_iata": to_iata,
                    "departure": flight.get("departure", {}).get("scheduledTime", {}).get("utc", ""),
                    "arrival": flight.get("arrival", {}).get("scheduledTime", {}).get("utc", ""),
                    "stops": 0,
                    "duration_minutes": None,
                    "cabin_class": "economy",
                    "booking_link": None,
                    "raw_data": flight
                }

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing AeroDataBox offer: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} AeroDataBox offers")
        return normalized

class AirScraperAdapter(RapidAPIAdapter):
    BASE_URL = "https://airscraper.p.rapidapi.com"

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None, passengers: int = 1) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("AirScraper adapter disabled (no API key)")
            return []

        cache_key = f"airscraper:{from_iata}:{to_iata}:{departure_date}:{return_date}:{passengers}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached AirScraper results for {cache_key}")
            return cached

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "airscraper.p.rapidapi.com"
        }

        trip_type = "return" if return_date else "oneway"
        url = f"{self.BASE_URL}/search?origin={from_iata}&destination={to_iata}&date={departure_date}"

        if return_date:
            url += f"&returnDate={return_date}"

        url += f"&adults={passengers}&currency=USD"

        result = self._make_request(url, headers)

        if not result or "data" not in result:
            return []

        normalized = self._normalize_offers(result["data"])
        cache.set(cache_key, normalized)
        return normalized

    def _normalize_offers(self, offers: List[Dict]) -> List[Dict[str, Any]]:
        normalized = []

        for offer in offers:
            try:
                legs = offer.get("legs", [])
                if not legs:
                    continue

                first_leg = legs[0]
                segments = first_leg.get("segments", [])

                if not segments:
                    continue

                first_segment = segments[0]
                last_segment = segments[-1]

                normalized_offer = {
                    "id": offer.get("id", ""),
                    "provider": "airscraper",
                    "price": float(offer.get("price", {}).get("amount", 0)),
                    "currency": offer.get("price", {}).get("currency", "USD"),
                    "airline": first_segment.get("operatingCarrier", {}).get("code", ""),
                    "airline_name": first_segment.get("operatingCarrier", {}).get("name", ""),
                    "from_iata": first_segment.get("departure", {}).get("airport", ""),
                    "to_iata": last_segment.get("arrival", {}).get("airport", ""),
                    "departure": first_segment.get("departure", {}).get("time", ""),
                    "arrival": last_segment.get("arrival", {}).get("time", ""),
                    "stops": len(segments) - 1,
                    "duration_minutes": first_leg.get("duration", 0),
                    "cabin_class": offer.get("cabinClass", "economy"),
                    "booking_link": offer.get("deepLink"),
                    "raw_data": offer
                }

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing AirScraper offer: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} AirScraper offers")
        return normalized

class FlightAPIAdapter(RapidAPIAdapter):
    BASE_URL = "https://api.flightapi.io/compschedule"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.FLIGHTAPI_KEY
        self.enabled = self.api_key is not None

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("FlightAPI adapter disabled (no API key)")
            return []

        cache_key = f"flightapi:{from_iata}:{to_iata}:{departure_date}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached FlightAPI results for {cache_key}")
            return cached

        url = f"{self.BASE_URL}/{self.api_key}?mode=departures&day=0&iata={from_iata}"

        headers = {"Accept": "application/json"}
        result = self._make_request_flightapi(url, headers)

        if not result:
            return []

        normalized = self._normalize_offers(result, from_iata, to_iata)
        cache.set(cache_key, normalized)
        return normalized

    def _make_request_flightapi(self, url: str, headers: Dict, retry_count: int = 0) -> Optional[List]:
        try:
            logger.info(f"FlightAPI Request: {url}")
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by FlightAPI, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request_flightapi(url, headers, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"FlightAPI Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"FlightAPI request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request_flightapi(url, headers, retry_count + 1)
            else:
                logger.error(f"FlightAPI request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def _normalize_offers(self, flights: List[Dict], from_iata: str, to_iata: str) -> List[Dict[str, Any]]:
        normalized = []

        for flight in flights:
            try:
                arrival_iata = flight.get("arrival", {}).get("iataCode")
                if arrival_iata != to_iata:
                    continue

                normalized_offer = {
                    "id": flight.get("flight", {}).get("iataNumber", ""),
                    "provider": "flightapi",
                    "price": 0,
                    "currency": "USD",
                    "airline": flight.get("airline", {}).get("iataCode", ""),
                    "airline_name": flight.get("airline", {}).get("name", ""),
                    "from_iata": from_iata,
                    "to_iata": to_iata,
                    "departure": flight.get("departure", {}).get("scheduledTime", ""),
                    "arrival": flight.get("arrival", {}).get("scheduledTime", ""),
                    "stops": 0,
                    "duration_minutes": None,
                    "cabin_class": "economy",
                    "booking_link": None,
                    "raw_data": flight
                }

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing FlightAPI offer: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} FlightAPI offers (non-primary)")
        return normalized

aerodatabox_adapter = AeroDataBoxAdapter()
airscraper_adapter = AirScraperAdapter()
flightapi_adapter = FlightAPIAdapter()
