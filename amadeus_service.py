import logging
import os
from typing import Any, Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

try:
    from amadeus import Client, ResponseError
except ImportError:  # pragma: no cover - import safety when dependency is absent
    Client = None
    ResponseError = Exception


_TRAVEL_CLASS_MAP = {
    "economy": "ECONOMY",
    "premium_economy": "PREMIUM_ECONOMY",
    "business": "BUSINESS",
    "first": "FIRST",
}


class AmadeusService:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.client_id = (
            client_id
            or os.getenv("AMADEUS_CLIENT_ID")
            or getattr(config, "AMADEUS_CLIENT_ID", None)
        )
        self.client_secret = (
            client_secret
            or os.getenv("AMADEUS_CLIENT_SECRET")
            or getattr(config, "AMADEUS_CLIENT_SECRET", None)
        )
        self.enabled = bool(self.client_id and self.client_secret and Client is not None)
        self.client = (
            Client(client_id=self.client_id, client_secret=self.client_secret)
            if self.enabled
            else None
        )

    def search_flights(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
        currency: str = "USD",
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.info("Amadeus service disabled (missing credentials or dependency)")
            return []

        travel_class = _TRAVEL_CLASS_MAP.get((cabin_class or "").lower(), "ECONOMY")
        try:
            adults = int(passengers) if passengers else 1
        except (TypeError, ValueError):
            adults = 1

        params: Dict[str, Any] = {
            "originLocationCode": from_iata,
            "destinationLocationCode": to_iata,
            "departureDate": departure_date,
            "adults": max(1, adults),
            "currencyCode": (currency or "USD").upper(),
            "travelClass": travel_class,
            "max": 25,
        }
        if return_date:
            params["returnDate"] = return_date

        try:
            response = self.client.shopping.flight_offers_search.get(**params)
            payload = response.result if hasattr(response, "result") else {}
            offers = payload.get("data", []) if isinstance(payload, dict) else []
            dictionaries = payload.get("dictionaries", {}) if isinstance(payload, dict) else {}
            return self._normalize_offers(offers, dictionaries)
        except ResponseError as exc:
            logger.error(
                "Amadeus search failed for %s->%s: %s",
                from_iata,
                to_iata,
                exc,
            )
            return []
        except Exception as exc:
            logger.error(
                "Unexpected Amadeus error for %s->%s: %s",
                from_iata,
                to_iata,
                exc,
            )
            return []

    def _normalize_offers(
        self,
        offers: List[Dict[str, Any]],
        dictionaries: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        dictionaries = dictionaries or {}
        carrier_names = dictionaries.get("carriers", {}) if isinstance(dictionaries, dict) else {}
        normalized: List[Dict[str, Any]] = []

        for offer in offers:
            try:
                itineraries = offer.get("itineraries", [])
                if not itineraries:
                    continue

                slices: List[Dict[str, Any]] = []
                for itinerary in itineraries:
                    segments = itinerary.get("segments", [])
                    if not segments:
                        continue

                    first_segment = segments[0]
                    last_segment = segments[-1]
                    slice_segments = []
                    for segment in segments:
                        carrier_code = segment.get("carrierCode", "XX")
                        slice_segments.append(
                            {
                                "flight_number": f"{carrier_code}{segment.get('number', '')}",
                                "airline": carrier_names.get(carrier_code, carrier_code),
                                "departing_at": segment.get("departure", {}).get("at"),
                                "arriving_at": segment.get("arrival", {}).get("at"),
                                "origin_iata": segment.get("departure", {}).get("iataCode", ""),
                                "destination_iata": segment.get("arrival", {}).get("iataCode", ""),
                                "checked_bags": 0,
                            }
                        )

                    slices.append(
                        {
                            "departure_time": first_segment.get("departure", {}).get("at"),
                            "arrival_time": last_segment.get("arrival", {}).get("at"),
                            "duration": itinerary.get("duration"),
                            "origin_iata": first_segment.get("departure", {}).get("iataCode", ""),
                            "destination_iata": last_segment.get("arrival", {}).get("iataCode", ""),
                            "stops": max(0, len(segments) - 1),
                            "segments": slice_segments,
                        }
                    )

                if not slices:
                    continue

                first_segment = itineraries[0].get("segments", [{}])[0]
                first_carrier = first_segment.get("carrierCode", "XX")
                cabin_class = (
                    (
                        offer.get("travelerPricings", [{}])[0]
                        .get("fareDetailsBySegment", [{}])[0]
                        .get("cabin")
                    )
                    or "ECONOMY"
                ).lower()
                first_slice = slices[0]
                total_amount = float(offer.get("price", {}).get("grandTotal", 0) or 0)
                if total_amount <= 0:
                    continue

                normalized.append(
                    {
                        "id": offer.get("id", ""),
                        "provider": "amadeus",
                        "source": "amadeus",
                        "price": total_amount,
                        "currency": offer.get("price", {}).get("currency", "USD"),
                        "airline": first_carrier,
                        "airline_name": carrier_names.get(first_carrier, first_carrier),
                        "from_iata": first_slice.get("origin_iata", ""),
                        "to_iata": first_slice.get("destination_iata", ""),
                        "departure": first_slice.get("departure_time", ""),
                        "arrival": first_slice.get("arrival_time", ""),
                        "stops": first_slice.get("stops", 0),
                        "duration": first_slice.get("duration"),
                        "cabin_class": cabin_class,
                        "slices": slices,
                        "booking_link": None,
                    }
                )
            except Exception as exc:
                logger.error("Error normalizing Amadeus offer: %s", exc)
                continue

        return normalized


amadeus_service = AmadeusService()
