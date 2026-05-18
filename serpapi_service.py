import os
import logging
from collections import OrderedDict
from typing import Optional, List, Dict, Any
import requests

logger = logging.getLogger(__name__)


class SerpApiService:
    """Flight search adapter for SerpApi's Google Flights engine."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.enabled = self.api_key is not None
        self._cache: OrderedDict[tuple[str, str, str, str], List[Dict[str, Any]]] = OrderedDict()

    def _search_flights_cached(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        currency: str,
    ) -> List[Dict[str, Any]]:
        cache_key = (from_iata, to_iata, departure_date, currency)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return list(self._cache[cache_key])

        if not self.enabled:
            logger.warning("SerpApi key not configured, skipping request")
            return []

        params: Dict[str, Any] = {
            "engine": "google_flights",
            "departure_id": from_iata,
            "arrival_id": to_iata,
            "outbound_date": departure_date,
            "currency": currency,
            "hl": "en",
            "type": "2",
            "api_key": self.api_key,
        }

        try:
            logger.info("SerpApi request: %s -> %s", from_iata, to_iata)
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            logger.error("SerpApi HTTP error (%s) for %s->%s: %s", status, from_iata, to_iata, exc)
            return []
        except requests.RequestException as exc:
            logger.error("SerpApi request failed for %s->%s: %s", from_iata, to_iata, exc)
            return []
        except Exception as exc:
            logger.error("SerpApi unexpected error for %s->%s: %s", from_iata, to_iata, exc)
            return []

        if "error" in result:
            logger.error("SerpApi returned error for %s->%s: %s", from_iata, to_iata, result.get("error"))
            return []

        normalized = self._normalize_results(result, from_iata, to_iata, currency)
        if len(self._cache) >= 100:
            self._cache.popitem(last=False)
        self._cache[cache_key] = normalized
        return list(normalized)

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

    def _normalize_results(
        self, result: Dict, from_iata: str, to_iata: str, currency: str
    ) -> List[Dict[str, Any]]:
        """Parse SerpApi response and convert to the standard internal offer format."""
        normalized: List[Dict[str, Any]] = []

        best_flights = result.get("best_flights", [])
        other_flights = result.get("other_flights", [])
        all_flights = (best_flights if isinstance(best_flights, list) else []) + (
            other_flights if isinstance(other_flights, list) else []
        )
        google_flights_url = (
            result.get("search_metadata", {}).get("google_flights_url")
            or result.get("search_parameters", {}).get("google_flights_url")
        )

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
                        "currency": currency,
                        "airline": airline_iata,
                        "airline_name": airline_name,
                        "from_iata": from_iata,
                        "to_iata": to_iata,
                        "departure": departure_time,
                        "arrival": arrival_time,
                        "stops": stops,
                        "duration_minutes": total_duration,
                        "cabin_class": "economy",
                        "booking_link": google_flights_url,
                        "booking_url": google_flights_url,
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
