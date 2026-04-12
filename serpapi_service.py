import requests
import time
import logging
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)


class SerpApiService:
    """Flight search adapter for SerpApi's Google Flights engine."""

    BASE_URL = "https://serpapi.com/search"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.FLIGHT_API_KEY
        self.enabled = self.api_key is not None

    def _make_request(self, params: Dict, origin: str = "", destination: str = "", retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("SerpApi key not configured, skipping request")
            return None

        try:
            logger.info(f"SerpApi Request: {origin} -> {destination}")
            response = requests.get(self.BASE_URL, params=params, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by SerpApi, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(params, origin, destination, retry_count + 1)
                else:
                    logger.error("Max retries reached for SerpApi rate limit")
                    return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"SerpApi Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"SerpApi request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(params, origin, destination, retry_count + 1)
            else:
                logger.error(f"SerpApi request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def search_flights(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        return_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for flights using SerpApi's Google Flights engine.

        Returns a list of normalized flight offer dicts, sorted cheapest first.
        Returns an empty list if the service is disabled, the API returns an
        error, or no flights are found.
        """
        if not self.enabled:
            logger.info("SerpApi service disabled (no FLIGHT_API_KEY configured)")
            return []

        # type=1 → round-trip, type=2 → one-way
        params: Dict[str, Any] = {
            "engine": "google_flights",
            "departure_id": from_iata,
            "arrival_id": to_iata,
            "outbound_date": departure_date,
            "currency": "USD",
            "hl": "en",
            "api_key": self.api_key,
            "type": "1" if return_date else "2",
        }

        if return_date:
            params["return_date"] = return_date

        try:
            result = self._make_request(params, origin=from_iata, destination=to_iata)
        except Exception as e:
            logger.error(
                f"SerpApi search raised unexpected exception for {from_iata}->{to_iata}: {str(e)}"
            )
            return []

        if not result:
            logger.info(f"No response from SerpApi for {from_iata}->{to_iata}")
            return []

        if "error" in result:
            logger.error(f"SerpApi returned error for {from_iata}->{to_iata}: {result['error']}")
            return []

        return self._normalize_results(result, from_iata, to_iata)

    def _normalize_results(
        self, result: Dict, from_iata: str, to_iata: str
    ) -> List[Dict[str, Any]]:
        """Parse SerpApi response and convert to the standard internal offer format."""
        normalized: List[Dict[str, Any]] = []

        all_flights = result.get("best_flights", []) + result.get("other_flights", [])

        if not all_flights:
            logger.info(f"No flights in SerpApi response for {from_iata}->{to_iata}")
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

                airline_name = first_flight.get("airline", "Unknown")

                # Extract carrier IATA code from flight_number (e.g. "UA 1234" → "UA")
                flight_number = first_flight.get("flight_number", "")
                parts = flight_number.split(" ", 1)
                airline_iata = parts[0] if parts and parts[0] else "XX"

                departure_time = first_flight.get("departure_airport", {}).get("time", "")
                arrival_time = last_flight.get("arrival_airport", {}).get("time", "")
                total_duration = flight_group.get("total_duration", 0)

                # Number of stops = segments minus 1
                stops = len(flights) - 1

                offer_id = f"serpapi-{from_iata}-{to_iata}-{departure_time}-{price}"

                normalized.append(
                    {
                        "id": offer_id,
                        "provider": "serpapi",
                        "price": price,
                        "currency": "USD",
                        "airline": airline_iata,
                        "airline_name": airline_name,
                        "from_iata": from_iata,
                        "to_iata": to_iata,
                        "departure": departure_time,
                        "arrival": arrival_time,
                        "stops": stops,
                        "duration_minutes": total_duration,
                        "cabin_class": "economy",
                        "booking_link": None,
                    }
                )

            except Exception as e:
                logger.error(f"Error normalizing SerpApi flight offer: {str(e)}")
                continue

        # Sort by price so callers always receive cheapest offers first
        normalized.sort(key=lambda x: x["price"])

        logger.info(
            f"Normalized {len(normalized)} SerpApi flights for {from_iata}->{to_iata}"
        )
        return normalized


serpapi_service = SerpApiService()
