import requests
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.config import config

logger = logging.getLogger(__name__)

class DuffelService:
    BASE_URL = "https://api.duffel.com"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.DUFFEL_API_KEY
        self.enabled = self.api_key is not None

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("Duffel API key not configured, skipping request")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Duffel-Version": "v1"
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

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str,
                      return_date: Optional[str] = None, passengers: int = 1,
                      cabin_class: str = "economy") -> List[Dict[str, Any]]:
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

        request_data = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(passengers)],
                "cabin_class": cabin_class
            }
        }

        result = self._make_request("POST", "/air/offer_requests", request_data)

        if not result or "data" not in result:
            return []

        offer_request_id = result["data"]["id"]

        time.sleep(2)

        offers_result = self._make_request("GET", f"/air/offers?offer_request_id={offer_request_id}")

        if not offers_result or "data" not in offers_result:
            return []

        return self._normalize_offers(offers_result["data"])

    def _normalize_offers(self, duffel_offers: List[Dict]) -> List[Dict[str, Any]]:
        normalized = []

        for offer in duffel_offers:
            try:
                slices = offer.get("slices", [])
                if not slices:
                    continue

                first_slice = slices[0]
                segments = first_slice.get("segments", [])

                if not segments:
                    continue

                first_segment = segments[0]
                last_segment = segments[-1]

                price_data = offer.get("total_amount", "0")
                currency = offer.get("total_currency", "USD")

                normalized_offer = {
                    "id": offer.get("id"),
                    "provider": "duffel",
                    "price": float(price_data),
                    "currency": currency,
                    "airline": first_segment.get("marketing_carrier", {}).get("iata_code", ""),
                    "airline_name": first_segment.get("marketing_carrier", {}).get("name", ""),
                    "from_iata": first_segment.get("origin", {}).get("iata_code", ""),
                    "to_iata": last_segment.get("destination", {}).get("iata_code", ""),
                    "departure": first_segment.get("departing_at", ""),
                    "arrival": last_segment.get("arriving_at", ""),
                    "stops": len(segments) - 1,
                    "duration_minutes": first_slice.get("duration"),
                    "cabin_class": offer.get("cabin_class", "economy"),
                    "booking_link": f"https://duffel.com/book/{offer.get('id')}",
                    "raw_data": offer
                }

                normalized.append(normalized_offer)

            except Exception as e:
                logger.error(f"Error normalizing Duffel offer: {str(e)}")
                continue

        logger.info(f"Normalized {len(normalized)} Duffel offers")
        return normalized

duffel_service = DuffelService()
