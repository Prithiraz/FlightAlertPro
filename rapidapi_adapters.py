import requests
import httpx
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
            if 400 <= response.status_code < 500:
                logger.error(f"RapidAPI client error {response.status_code}: {response.text[:300]}")
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
    BASE_URL = "https://sky-scrapper.p.rapidapi.com"

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None, passengers: int = 1,
                      adults: Optional[int] = None, children: int = 0,
                      currency: str = "USD", cabin_class: str = "economy") -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("AirScraper adapter disabled (no API key)")
            return []

        adult_count = max(1, int(adults if adults is not None else passengers or 1))
        safe_currency = (currency or "USD").upper()
        safe_cabin_class = (cabin_class or "economy").lower()
        cache_key = f"airscraper:{from_iata}:{to_iata}:{departure_date}:{return_date}:{adult_count}:{children}:{safe_currency}:{safe_cabin_class}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached AirScraper results for {cache_key}")
            return cached

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "sky-scrapper.p.rapidapi.com"
        }

        try:
            with httpx.Client(timeout=30) as client:
                origin_lookup = client.get(
                    f"{self.BASE_URL}/api/v1/flights/searchAirport",
                    headers=headers,
                    params={"query": from_iata},
                )
                origin_lookup.raise_for_status()
                origin_payload = origin_lookup.json()
                origin_airports = origin_payload.get("data") if isinstance(origin_payload, dict) else None
                if not origin_airports:
                    logger.error(f"Sky Scrapper origin lookup returned empty for {from_iata}")
                    return []

                destination_lookup = client.get(
                    f"{self.BASE_URL}/api/v1/flights/searchAirport",
                    headers=headers,
                    params={"query": to_iata},
                )
                destination_lookup.raise_for_status()
                destination_payload = destination_lookup.json()
                destination_airports = destination_payload.get("data") if isinstance(destination_payload, dict) else None
                if not destination_airports:
                    logger.error(f"Sky Scrapper destination lookup returned empty for {to_iata}")
                    return []

                origin = origin_airports[0]
                destination = destination_airports[0]
                origin_sky_id = origin.get("skyId")
                destination_sky_id = destination.get("skyId")
                origin_entity_id = (origin.get("navigation") or {}).get("entityId")
                destination_entity_id = (destination.get("navigation") or {}).get("entityId")
                if not all([origin_sky_id, destination_sky_id, origin_entity_id, destination_entity_id]):
                    logger.error(
                        f"Sky Scrapper lookup missing identifiers for route {from_iata}->{to_iata}"
                    )
                    return []

                search_response = client.get(
                    f"{self.BASE_URL}/api/v1/flights/searchFlights",
                    headers=headers,
                    params={
                        "originSkyId": origin_sky_id,
                        "destinationSkyId": destination_sky_id,
                        "originEntityId": origin_entity_id,
                        "destinationEntityId": destination_entity_id,
                        "date": departure_date,
                        "currency": safe_currency,
                        "adults": adult_count,
                        "cabinClass": safe_cabin_class,
                    },
                )
                search_response.raise_for_status()
                result = search_response.json()
        except httpx.HTTPError as e:
            logger.error(f"Sky Scrapper request failed for {from_iata}->{to_iata}: {e}")
            return []
        except Exception as e:
            logger.error(f"Sky Scrapper search failed for {from_iata}->{to_iata}: {e}")
            return []

        if not result or "data" not in result:
            logger.warning("Sky Scrapper returned no data")
            return []

        payload = result.get("data")
        offers = payload.get("itineraries", []) if isinstance(payload, dict) else payload
        normalized = self._normalize_offers(offers or [])
        if not normalized:
            logger.warning("Sky Scrapper normalization produced no offers")
            return []
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

                price_data = offer.get("price", {}) if isinstance(offer.get("price"), dict) else {}
                amount = price_data.get("amount")
                if amount is None:
                    amount = price_data.get("raw", 0)

                origin_airport = first_segment.get("departure", {}).get("airport", "")
                destination_airport = last_segment.get("arrival", {}).get("airport", "")
                if isinstance(origin_airport, dict):
                    origin_airport = origin_airport.get("iata", "") or origin_airport.get("id", "")
                if isinstance(destination_airport, dict):
                    destination_airport = destination_airport.get("iata", "") or destination_airport.get("id", "")

                normalized_offer = {
                    "id": offer.get("id", ""),
                    "provider": "airscraper",
                    "price": float(amount or 0),
                    "currency": price_data.get("currency", "USD"),
                    "airline": first_segment.get("operatingCarrier", {}).get("code", ""),
                    "airline_name": first_segment.get("operatingCarrier", {}).get("name", ""),
                    "from_iata": origin_airport,
                    "to_iata": destination_airport,
                    "departure": first_segment.get("departure", {}).get("time", ""),
                    "arrival": last_segment.get("arrival", {}).get("time", ""),
                    "stops": len(segments) - 1,
                    "duration_minutes": first_leg.get("duration", first_leg.get("durationInMinutes", 0)),
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
