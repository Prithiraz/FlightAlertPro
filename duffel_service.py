import requests
import time
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)

class DuffelService:
    BASE_URL = "https://api.duffel.com"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DUFFEL_ACCESS_TOKEN") or config.DUFFEL_ACCESS_TOKEN or config.DUFFEL_API_KEY
        self.enabled = self.api_key is not None

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("Duffel API key not configured, skipping request")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Duffel-Version": "v2"
        }

        try:
            logger.info(f"Duffel API Request: {method} {endpoint}")

            if method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by Duffel, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(method, endpoint, data, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None
            if 400 <= response.status_code < 500:
                logger.error(f"Duffel client error {response.status_code}: {response.text[:500]}")
                return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"Duffel API Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"Duffel request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(method, endpoint, data, retry_count + 1)
            else:
                logger.error(f"Duffel request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def fetch_raw_offers(self, from_iata: str, to_iata: str, departure_date: str,
                        return_date: Optional[str] = None, passengers: int = 1,
                        cabin_class: str = "economy") -> List[Dict[str, Any]]:
        """Fetch raw offers from Duffel API without normalization"""
        if not self.enabled:
            logger.info("Duffel adapter disabled (no API key)")
            return []

        slices = [{
            "origin": from_iata,
            "destination": to_iata,
            "departure_date": departure_date
        }]

        if return_date:
            slices.append({
                "origin": to_iata,
                "destination": from_iata,
                "departure_date": return_date
            })

        safe_cabin_class = cabin_class if cabin_class in {"economy", "premium_economy", "business", "first"} else "economy"
        request_data = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(max(1, int(passengers or 1)))],
                "cabin_class": safe_cabin_class,
                "return_offers": True
            }
        }

        result = self._make_request("POST", "/air/offer_requests", request_data)

        if not result or "data" not in result or "id" not in result["data"]:
            logger.warning("Duffel offer request failed")
            return []

        offer_request_id = result["data"]["id"]

        time.sleep(2)

        offers_result = self._make_request("GET", f"/air/offers?offer_request_id={offer_request_id}")

        if not offers_result or "data" not in offers_result:
            logger.warning("Duffel offers fetch failed")
            return []

        return offers_result["data"]

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None, passengers: int = 1,
                      cabin_class: str = "economy") -> List[Dict[str, Any]]:
        raw_offers = self.fetch_raw_offers(
            from_iata, to_iata, departure_date,
            return_date=return_date, passengers=passengers, cabin_class=cabin_class
        )
        return self._normalize_offers(raw_offers)

    def _normalize_offers(self, duffel_offers: List[Dict]) -> List[Dict[str, Any]]:
        normalized = []

        for offer in duffel_offers:
            try:
                raw_slices = offer.get("slices", [])
                if not raw_slices:
                    continue

                price_data = offer.get("total_amount", "0")
                currency = offer.get("total_currency", "USD")
                
                # Grab the main airline from the first segment
                first_segment = raw_slices[0].get("segments", [{}])[0]
                main_airline = first_segment.get("owner", {}).get("name") or first_segment.get("marketing_carrier", {}).get("name", "Unknown Airline")

                # Build the outer "Doll" (The Offer)
                normalized_offer = {
                    "id": offer.get("id"),
                    "provider": "duffel",
                    "price": float(price_data),
                    "currency": currency,
                    "airline_name": main_airline,
                    "cabin_class": offer.get("cabin_class", "economy"),
                    "slices": [], # We will put outbound and return flights in here
                    "booking_link": f"https://duffel.com/book/{offer.get('id')}",
                }

                # Build the inner "Dolls" (The Slices and Segments)
                for raw_slice in raw_slices:
                    segments = raw_slice.get("segments", [])
                    if not segments:
                        continue

                    slice_data = {
                        "departure_time": segments[0].get("departing_at"),
                        "arrival_time": segments[-1].get("arriving_at"),
                        "duration": raw_slice.get("duration"),
                        "origin_iata": raw_slice.get("origin", {}).get("iata_code", ""),
                        "destination_iata": raw_slice.get("destination", {}).get("iata_code", ""),
                        "stops": len(segments) - 1,
                        "segments": []
                    }

                    for segment in segments:
                        # Extract baggage (Duffel hides this deep in the passenger list)
                        checked_bags = 0
                        passengers = segment.get("passengers", [])
                        if passengers:
                            baggages = passengers[0].get("baggages", [])
                            for bag in baggages:
                                if bag.get("type") == "checked":
                                    checked_bags += bag.get("quantity", 1)

                        slice_data["segments"].append({
                            "flight_number": segment.get("operating_carrier_flight_number", ""),
                            "airline": segment.get("operating_carrier", {}).get("name", ""),
                            "departing_at": segment.get("departing_at"),
                            "arriving_at": segment.get("arriving_at"),
                            "origin_iata": segment.get("origin", {}).get("iata_code", ""),
                            "destination_iata": segment.get("destination", {}).get("iata_code", ""),
                            "checked_bags": checked_bags
                        })

                    normalized_offer["slices"].append(slice_data)

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing Duffel offer: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} Duffel offers")
        return normalized

duffel_service = DuffelService()
