import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx

from config import config

logger = logging.getLogger(__name__)

# ── Airport coordinate lookup (airportsdata) ─────────────────────────────────
try:
    import airportsdata as _airportsdata_lib

    _AIRPORTSDATA_DB: Dict[str, Any] = _airportsdata_lib.load("IATA")
except Exception as _exc:  # pragma: no cover
    logger.warning("airportsdata library unavailable: %s", _exc)
    _AIRPORTSDATA_DB = {}


def _get_airport_coords(iata: str) -> Optional[Tuple[float, float]]:
    """Return (latitude, longitude) for an IATA code using the airportsdata library."""
    entry = _AIRPORTSDATA_DB.get(iata.upper() if iata else "")
    if entry is None:
        return None
    try:
        return (float(entry["lat"]), float(entry["lon"]))
    except (KeyError, TypeError, ValueError):
        return None


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two points (decimal degrees)."""
    EARTH_RADIUS_KM = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


# Emissions factors (ICAO/DEFRA) and Radiative Forcing multiplier
_EMISSIONS_FACTOR_SHORT_HAUL = 0.15   # kg CO₂ per km  (< 3,700 km)
_EMISSIONS_FACTOR_LONG_HAUL  = 0.11   # kg CO₂ per km  (≥ 3,700 km)
_SHORT_HAUL_THRESHOLD_KM     = 3_700
_RADIATIVE_FORCING_MULTIPLIER = 1.9   # high-altitude RF correction


def estimate_carbon_footprint(distance_km: float) -> float:
    """Estimate CO₂-equivalent emissions (kg) for a single flight segment.

    Formula: CO₂ = distance × emissions_factor × RF_multiplier

    Emissions factors (ICAO/DEFRA):
      - Short-haul (< 3,700 km): 0.15 kg/km
      - Long-haul  (≥ 3,700 km): 0.11 kg/km

    A Radiative Forcing (RF) multiplier of 1.9× is applied to account for
    the additional warming effect of high-altitude emissions.
    """
    factor = (
        _EMISSIONS_FACTOR_SHORT_HAUL
        if distance_km < _SHORT_HAUL_THRESHOLD_KM
        else _EMISSIONS_FACTOR_LONG_HAUL
    )
    return distance_km * factor * _RADIATIVE_FORCING_MULTIPLIER


class SkyscannerProvider:
    DEFAULT_HOST = "sky-scrapper.p.rapidapi.com"
    AIRPORT_SEARCH_ENDPOINT = "/api/v1/flights/searchAirport"
    FLIGHT_SEARCH_ENDPOINT = "/api/v2/flights/searchFlightsComplete"

    def __init__(self, api_key: Optional[str] = None, api_host: Optional[str] = None):
        self.api_key = api_key or config.RAPIDAPI_KEY
        raw_host = api_host or config.RAPIDAPI_HOST or self.DEFAULT_HOST
        self.api_host = self._normalize_host(raw_host)
        self.base_url = f"https://{self.api_host}" if self.api_host else ""
        self.enabled = bool(self.api_key and self.api_host)

    @staticmethod
    def _normalize_host(raw_host: Optional[str]) -> str:
        host = str(raw_host or "").strip().strip("/")
        if not host:
            return ""
        parsed = urlsplit(host if "://" in host else f"https://{host}")
        normalized = parsed.netloc or parsed.path
        return normalized.strip().strip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "X-RapidAPI-Key": self.api_key or "",
            "X-RapidAPI-Host": self.api_host or "",
        }

    @staticmethod
    def _first_list_value(value: Any) -> Dict[str, Any]:
        if isinstance(value, list) and value:
            first = value[0]
            return first if isinstance(first, dict) else {}
        return {}

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            # Ensure timezone-aware; assume UTC when no tzinfo is present
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    @classmethod
    def _to_utc_iso(cls, value: Optional[str]) -> str:
        """Parse a datetime string, normalize to UTC, and return an ISO 8601 string.

        Any timezone offset is converted to UTC.  If the input has no timezone
        information it is assumed to already be in UTC.  Returns an empty string
        when *value* is empty or None; returns the original string when it cannot
        be parsed.
        """
        if not value:
            return ""
        dt = cls._parse_dt(value)
        if dt is None:
            return value
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat()

    @classmethod
    def is_valid_itinerary(cls, outbound_slice: Dict[str, Any], inbound_slice: Dict[str, Any]) -> bool:
        """Return *False* when the outbound arrival is after the inbound departure.

        Such a pairing is physically impossible and must be discarded.
        """
        outbound_arrival = cls._parse_dt(outbound_slice.get("arrival_time"))
        inbound_departure = cls._parse_dt(inbound_slice.get("departure_time"))
        if outbound_arrival is not None and inbound_departure is not None:
            return outbound_arrival <= inbound_departure
        return True

    @classmethod
    def _duration_minutes(cls, duration: Any, departure: Optional[str], arrival: Optional[str]) -> int:
        if isinstance(duration, (int, float)):
            return max(0, int(duration))
        dep_dt = cls._parse_dt(departure)
        arr_dt = cls._parse_dt(arrival)
        if dep_dt and arr_dt and arr_dt >= dep_dt:
            return int((arr_dt - dep_dt).total_seconds() // 60)
        return 0

    @classmethod
    def _duration_iso(cls, duration: Any, departure: Optional[str], arrival: Optional[str]) -> str:
        minutes = cls._duration_minutes(duration, departure, arrival)
        hours, mins = divmod(minutes, 60)
        return f"PT{hours}H{mins}M"

    def _airport_identifiers(self, client: httpx.Client, iata: str) -> Tuple[Optional[str], Optional[str]]:
        response = client.get(
            f"{self.base_url}{self.AIRPORT_SEARCH_ENDPOINT}",
            headers=self._headers(),
            params={"query": iata},
        )
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("data", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            sky_id = item.get("skyId")
            navigation = item.get("navigation", {}) if isinstance(item.get("navigation"), dict) else {}
            entity_id = navigation.get("entityId")
            if sky_id and entity_id:
                return sky_id, entity_id
        return None, None

    @staticmethod
    def _resolve_place(place_id: Any, places_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        place = places_by_id.get(str(place_id), {})
        return {
            "name": place.get("name") or place.get("displayName") or place.get("cityName") or "",
            "iata": place.get("iataCode") or place.get("displayCode") or place.get("code") or "",
        }

    @staticmethod
    def _resolve_carrier_name(carrier_ids: Any, carriers_by_id: Dict[str, Dict[str, Any]]) -> str:
        for carrier_id in carrier_ids or []:
            carrier = carriers_by_id.get(str(carrier_id), {})
            name = carrier.get("name")
            if name:
                return str(name)
        return "Unknown Airline"

    def _build_slice(
        self,
        leg: Dict[str, Any],
        places_by_id: Dict[str, Dict[str, Any]],
        carriers_by_id: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        segments = leg.get("segments", []) if isinstance(leg.get("segments"), list) else []

        # Resolve departure/arrival from the leg's own fields first; fall back
        # to the first/last segment when the top-level fields are absent (elis-lab
        # API format stores times on segments rather than on the parent leg).
        departure_time = self._to_utc_iso(
            leg.get("departure") or leg.get("departureDateTime") or leg.get("departureTime") or ""
        )
        if not departure_time and segments:
            first_seg = segments[0] if isinstance(segments[0], dict) else {}
            departure_time = self._to_utc_iso(
                first_seg.get("departure") or first_seg.get("departureDateTime") or first_seg.get("departureTime") or ""
            )

        arrival_time = self._to_utc_iso(
            leg.get("arrival") or leg.get("arrivalDateTime") or leg.get("arrivalTime") or ""
        )
        if not arrival_time and segments:
            last_seg = segments[-1] if isinstance(segments[-1], dict) else {}
            arrival_time = self._to_utc_iso(
                last_seg.get("arrival") or last_seg.get("arrivalDateTime") or last_seg.get("arrivalTime") or ""
            )
        duration_raw = leg.get("durationInMinutes")
        if duration_raw is None:
            duration_raw = leg.get("duration")

        origin = self._resolve_place(leg.get("originPlaceId"), places_by_id)
        destination = self._resolve_place(leg.get("destinationPlaceId"), places_by_id)

        carrier_ids = leg.get("carrierIds") or leg.get("marketingCarrierIds") or []
        carrier_name = self._resolve_carrier_name(carrier_ids, carriers_by_id)
        airline_iata = ""
        if carrier_ids:
            airline_iata = (
                carriers_by_id.get(str(carrier_ids[0]), {}).get("iata")
                or carriers_by_id.get(str(carrier_ids[0]), {}).get("iataCode")
                or ""
            )

        segment_models = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            seg_carrier_ids = seg.get("carrierIds") or seg.get("marketingCarrierIds") or carrier_ids
            seg_carrier_name = self._resolve_carrier_name(seg_carrier_ids, carriers_by_id) or carrier_name
            checked_bags = seg.get("checkedBags")
            if checked_bags is None:
                checked_bags = seg.get("checked_bags")
            if checked_bags is None:
                checked_bags = 0
            segment_models.append(
                {
                    "airline": seg_carrier_name,
                    "checked_bags": int(checked_bags) if isinstance(checked_bags, (int, float, str)) and str(checked_bags).isdigit() else 0,
                    "flight_number": seg.get("flightNumber") or seg.get("number") or "",
                    "origin_iata": self._resolve_place(seg.get("originPlaceId"), places_by_id).get("iata", ""),
                    "destination_iata": self._resolve_place(seg.get("destinationPlaceId"), places_by_id).get("iata", ""),
                    "departing_at": self._to_utc_iso(seg.get("departure") or ""),
                    "arriving_at": self._to_utc_iso(seg.get("arrival") or ""),
                }
            )

        return {
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "duration": self._duration_iso(duration_raw, departure_time, arrival_time),
            "duration_minutes": self._duration_minutes(duration_raw, departure_time, arrival_time),
            "origin_iata": origin["iata"],
            "destination_iata": destination["iata"],
            "origin_name": origin["name"],
            "destination_name": destination["name"],
            "stops": max(0, int(leg.get("stopCount", len(segment_models) - 1) or 0)),
            "segments": segment_models,
            "airline_iata": airline_iata,
            "airline_name": carrier_name,
        }

    def _normalize_response(self, payload: Dict[str, Any], trip_type: str = "one_way") -> List[Dict[str, Any]]:
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        itineraries = data.get("itineraries", [])
        legs = data.get("legs", [])
        carriers = data.get("carriers", [])
        places = data.get("places", [])

        if not isinstance(itineraries, list):
            itineraries = []
        if not isinstance(legs, list):
            legs = []
        if not isinstance(carriers, list):
            carriers = []
        if not isinstance(places, list):
            places = []

        # Merge top-level legs with any legs embedded within individual itineraries
        # (elis-lab API variant stores legs inside each itinerary object).
        all_legs: List[Dict[str, Any]] = list(legs)
        for itin in itineraries:
            if isinstance(itin, dict):
                embedded = itin.get("legs", [])
                if isinstance(embedded, list):
                    all_legs.extend(l for l in embedded if isinstance(l, dict))

        legs_by_id = {str(leg.get("id")): leg for leg in all_legs if isinstance(leg, dict) and leg.get("id") is not None}
        carriers_by_id = {str(carrier.get("id")): carrier for carrier in carriers if isinstance(carrier, dict) and carrier.get("id") is not None}
        places_by_id = {str(place.get("id")): place for place in places if isinstance(place, dict) and place.get("id") is not None}

        offers: List[Dict[str, Any]] = []
        for itinerary in itineraries:
            if not isinstance(itinerary, dict):
                continue

            outbound_leg_id = itinerary.get("outboundLegId")
            inbound_leg_id = itinerary.get("inboundLegId")
            leg_ids = itinerary.get("legIds", []) if isinstance(itinerary.get("legIds"), list) else []
            if outbound_leg_id is None and leg_ids:
                outbound_leg_id = leg_ids[0]
            if inbound_leg_id is None and len(leg_ids) > 1:
                inbound_leg_id = leg_ids[1]

            outbound_leg = legs_by_id.get(str(outbound_leg_id), {})
            inbound_leg = legs_by_id.get(str(inbound_leg_id), {}) if inbound_leg_id is not None else {}
            if not outbound_leg:
                continue

            pricing_options = itinerary.get("pricingOptions", [])
            first_pricing = self._first_list_value(pricing_options)
            price_obj = first_pricing.get("price", {}) if isinstance(first_pricing.get("price"), dict) else {}
            price_amount = self._safe_float(price_obj.get("amount"), 0.0)
            booking_url = (
                first_pricing.get("deeplinkUrl")
                or first_pricing.get("deepLink")
                or first_pricing.get("url")
                or itinerary.get("deeplinkUrl")
                or itinerary.get("deepLink")
                or "https://www.skyscanner.com"
            )

            outbound_slice = self._build_slice(outbound_leg, places_by_id, carriers_by_id)
            slices = [outbound_slice]
            if trip_type == "round_trip" and inbound_leg:
                inbound_slice = self._build_slice(inbound_leg, places_by_id, carriers_by_id)
                if not self.is_valid_itinerary(outbound_slice, inbound_slice):
                    logger.debug(
                        "Discarding round-trip itinerary %s: outbound arrival is after inbound departure",
                        itinerary.get("id"),
                    )
                    continue
                slices.append(inbound_slice)

            airline_name = outbound_slice.get("airline_name") or "Unknown Airline"
            airline_iata = outbound_slice.get("airline_iata") or ""

            from_iata = outbound_slice.get("origin_iata", "")
            to_iata = outbound_slice.get("destination_iata", "")
            from_coords = _get_airport_coords(from_iata) if from_iata else None
            to_coords = _get_airport_coords(to_iata) if to_iata else None

            if from_coords and to_coords:
                gc_km = calculate_haversine_distance(*from_coords, *to_coords)
            else:
                gc_km = None
            # Efficiency score: GCD / (GCD + 100 km estimated route overhead).
            # Expressed as a 0–1 fraction (efficiency_score) and as a 0–100
            # percentage (efficiency_pct) per the Aerospace Phase 1 spec.
            # When coordinates are unknown fall back to the 1.1× baseline (≈ 0.9091).
            if gc_km is not None:
                efficiency_score = round(gc_km / (gc_km + 100), 4)
                co2_emissions_kg = round(estimate_carbon_footprint(gc_km), 2)
            else:
                efficiency_score = round(1 / 1.1, 4)
                co2_emissions_kg = None

            efficiency_pct = round(efficiency_score * 100, 1)

            offers.append(
                {
                    "id": itinerary.get("id") or f"skyscanner-{len(offers)}",
                    "provider": "skyscanner",
                    "source": "skyscanner",
                    "price": float(price_amount),
                    "currency": price_obj.get("unit") or data.get("context", {}).get("currency") or "USD",
                    "airline_name": airline_name,
                    "airline_iata": airline_iata,
                    "booking_url": str(booking_url),
                    "booking_link": str(booking_url),
                    "slices": slices,
                    "cabin_class": str(itinerary.get("cabinClass") or "economy").lower(),
                    "stops": int(outbound_slice.get("stops", 0)),
                    "duration_minutes": int(outbound_slice.get("duration_minutes", 0)),
                    "from_iata": from_iata,
                    "to_iata": to_iata,
                    "departure_time": outbound_slice.get("departure_time", ""),
                    "arrival_time": outbound_slice.get("arrival_time", ""),
                    # Aerospace Phase 1 canonical field names
                    "gcd_km": gc_km,
                    "co2_kg": co2_emissions_kg,
                    "efficiency_pct": efficiency_pct,
                    # Legacy aliases kept for backward compatibility
                    "gcd_distance": gc_km,
                    "efficiency_score": efficiency_score,
                    "co2_emissions_kg": co2_emissions_kg,
                }
            )

        return offers

    def search_flights(
        self,
        from_iata: str,
        to_iata: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        adults: Optional[int] = None,
        children: int = 0,
        currency: str = "USD",
        cabin_class: str = "economy",
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.warning("Skyscanner provider disabled (RapidAPI credentials missing)")
            return []

        try:
            with httpx.Client(timeout=30) as client:
                origin_sky_id, origin_entity_id = self._airport_identifiers(client, from_iata)
                destination_sky_id, destination_entity_id = self._airport_identifiers(client, to_iata)

                if not origin_sky_id or not origin_entity_id or not destination_sky_id or not destination_entity_id:
                    logger.error("Skyscanner airport lookup failed for %s -> %s", from_iata, to_iata)
                    return []

                trip_type = "round_trip" if return_date else "one_way"
                response = client.get(
                    f"{self.base_url}{self.FLIGHT_SEARCH_ENDPOINT}",
                    headers=self._headers(),
                    params={
                        "originSkyId": origin_sky_id,
                        "destinationSkyId": destination_sky_id,
                        "originEntityId": origin_entity_id,
                        "destinationEntityId": destination_entity_id,
                        "date": departure_date,
                        "returnDate": return_date,
                        "tripType": trip_type,
                        "adults": max(1, int(adults if adults is not None else passengers or 1)),
                        "children": max(0, int(children or 0)),
                        "cabinClass": (cabin_class or "economy").lower(),
                        "currency": (currency or "USD").upper(),
                        "market": "US",
                        "locale": "en-US",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return self._normalize_response(payload, trip_type=trip_type)
        except Exception as exc:
            logger.error("Skyscanner flight search failed for %s -> %s: %s", from_iata, to_iata, exc)
            return []


skyscanner_provider = SkyscannerProvider()
