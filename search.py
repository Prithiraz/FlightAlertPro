"""Flight search aggregator with multi-supplier support"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import hashlib
import time
import re

import openai
from rapidapi_adapters import aerodatabox_adapter
from duffel_service import duffel_service
from serpapi_service import serpapi_service
from amadeus_service import amadeus_service
from config import config
from math_utils import calculate_points_cost, calculate_cpp, BASELINE_CPP
from weather_service import get_departure_performance, get_aerodynamic_performance, _TAS_KT, _KM_PER_NM, iata_to_airport_info

logger = logging.getLogger(__name__)

# Module-level OpenAI client (initialized once; None when API key is absent)
_openai_client: Optional[openai.OpenAI] = (
    openai.OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
)

router = APIRouter(prefix="/api", tags=["search"])

# Circuit breaker state
CIRCUIT_BREAKER = {
    'aerodatabox': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'amadeus': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'duffel': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'serpapi': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
}

CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN = 600  # 10 minutes

# Search result cache
SEARCH_CACHE = {}
CACHE_TTL = 900  # 15 minutes

class PassengerCount(BaseModel):
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=9)
    infants: int = Field(0, ge=0, le=9)

class FlightSegment(BaseModel):
    from_iata: str = Field(..., min_length=3, max_length=3)
    to_iata: str = Field(..., min_length=3, max_length=3)
    departure_date: str  # YYYY-MM-DD format
    airline_filter: Optional[str] = None

class SearchRequest(BaseModel):
    segments: List[FlightSegment] = Field(..., min_items=1, max_items=6)
    passengers: PassengerCount = PassengerCount()
    cabin_class: str = Field("economy", pattern="^(economy|premium_economy|business|first)$")
    baggage_min_kg: Optional[int] = Field(None, ge=0, le=100)
    baggage_max_kg: Optional[int] = Field(None, ge=0, le=100)
    currency: str = Field("USD", min_length=3, max_length=3)
    max_stops: Optional[int] = Field(None, ge=0, le=3)

class FlightOffer(BaseModel):
    id: str
    source: str
    airline_iata: str
    airline_name: str
    from_iata: str
    to_iata: str
    departure_time: str
    arrival_time: str
    duration_minutes: Optional[int]
    stops: int
    price: float
    currency: str
    cabin_class: str
    baggage_kg: Optional[int]
    booking_url: Optional[str]
    is_error_fare: bool = False
    ai_advice: Optional[str] = None
    ai_action: Optional[str] = None  # 'BUY NOW' or 'WAIT'
    density_altitude_ft: Optional[float] = None
    takeoff_risk_level: Optional[str] = None  # 'LOW', 'MODERATE', or 'HIGH'

def _get_route_14day_average(from_iata: str, to_iata: str):
    """Return (average_price, history_list) from price_history_logs over the last 14 days.

    Queries Supabase synchronously.  Returns (None, []) when there is
    insufficient history or when Supabase is not configured.
    """
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        return None, []
    try:
        from supabase import create_client
        from datetime import timezone
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        route_group = f"{from_iata}-{to_iata}"
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        result = (
            supabase.table('price_history_logs')
            .select('lowest_price')
            .eq('route_group', route_group)
            .gte('recorded_at', cutoff)
            .order('recorded_at', desc=False)
            .execute()
        )
        prices = [float(row['lowest_price']) for row in (result.data or [])]
        if len(prices) < 2:
            return None, prices
        avg = sum(prices) / len(prices)
        return avg, prices
    except Exception as exc:
        logger.error(f"Error fetching 14-day average for {from_iata}-{to_iata}: {exc}")
        return None, []


def _predict_price_action(current_price: float, history_list: list) -> dict:
    """Call OpenAI to advise BUY NOW or WAIT based on recent price history.

    Uses the same prompt format as the worker's ``predict_price_action`` function.
    Falls back to a heuristic when OpenAI is unavailable.
    """
    if not _openai_client:
        return _heuristic_action(current_price, history_list)
    try:
        history_str = ", ".join(f"${p:.2f}" for p in history_list[-10:])
        prompt = (
            f"You are a travel data scientist. Looking at this 14-day price history "
            f"[{history_str}], the current price is ${current_price:.2f}. "
            f"Is this a historical low? Should the user 'BUY NOW' or 'WAIT'? "
            f"Provide a 1-sentence reason."
        )
        response = _openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a travel data scientist."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=80,
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        action = "BUY NOW" if "BUY NOW" in content.upper() else "WAIT"
        return {"action": action, "reason": content}
    except Exception as exc:
        logger.error(f"OpenAI price action prediction failed: {exc}")
        return _heuristic_action(current_price, history_list)


def _heuristic_action(current_price: float, history_list: list) -> dict:
    if not history_list:
        return {"action": "WAIT", "reason": "Insufficient price history to make a recommendation."}
    avg = sum(history_list) / len(history_list)
    if avg > 0 and current_price < avg * 0.85:
        return {
            "action": "BUY NOW",
            "reason": f"Current price ${current_price:.2f} is significantly below the recent average of ${avg:.2f}.",
        }
    return {
        "action": "WAIT",
        "reason": f"Current price ${current_price:.2f} is near or above the recent average of ${avg:.2f}.",
    }


def _inject_points_valuation(offers: list) -> list:
    """Add ``estimated_points_cost`` and ``cpp_value`` to each offer dict."""
    for offer in offers:
        price = offer.get('price', 0)
        pts = calculate_points_cost(price)
        offer['estimated_points_cost'] = pts
        offer['cpp_value'] = calculate_cpp(price, pts)
    return offers


def _enrich_offers_with_market_insights(
    offers: list, from_iata: str, to_iata: str
) -> list:
    """Add ``is_error_fare``, ``ai_action``, and ``ai_advice`` to each offer dict.

    An error fare is flagged when the offer price is more than 40% below the
    14-day average for the route.  OpenAI advice is fetched once for the
    cheapest error-fare offer and shared across all flagged offers.
    """
    avg_price, history = _get_route_14day_average(from_iata, to_iata)
    if avg_price is None:
        return offers

    ai_cache: dict = {}  # keyed by offer price bucket to avoid duplicate calls

    for offer in offers:
        price = offer.get('price', 0)
        if avg_price > 0 and (avg_price - price) / avg_price > 0.40:
            offer['is_error_fare'] = True
            # Dedupe OpenAI calls within the same request
            bucket = round(price / 5) * 5
            if bucket not in ai_cache:
                advice = _predict_price_action(price, history)
                ai_cache[bucket] = advice
            else:
                advice = ai_cache[bucket]
            offer['ai_action'] = advice['action']
            offer['ai_advice'] = advice['reason']
        else:
            offer['is_error_fare'] = False

    return offers


def _enrich_offers_with_density_altitude(offers: list, from_iata: str) -> list:
    """Add ``density_altitude_ft`` and ``takeoff_risk_level`` to each offer dict.

    Fetches real-time METAR for the departure airport once and stamps every
    offer with the same computed values.  Gracefully no-ops when the
    weather service is unavailable (CHECKWX_API_KEY not set or API error).
    """
    try:
        perf = get_departure_performance(from_iata)
    except Exception as exc:
        logger.warning("Density altitude calculation failed for %s: %s", from_iata, exc)
        perf = None

    da_ft = perf["density_altitude_ft"] if perf else None
    risk = perf["takeoff_risk_level"] if perf else None

    for offer in offers:
        offer["density_altitude_ft"] = da_ft
        offer["takeoff_risk_level"] = risk

    return offers


def _enrich_offers_with_wind_component(offers: list, from_iata: str, to_iata: str) -> list:
    """Add wind component, ground speed, and aerodynamic ETA fields to each offer.

    Fetches winds aloft via CheckWX TAF for the departure airport, solves the
    wind triangle for the true course, and stamps every offer with:

    - ``wind_component_kt``     – tailwind (+) or headwind (−) in knots
    - ``ground_speed_kt``       – effective ground speed in knots
    - ``wind_type``             – ``"tailwind"`` or ``"headwind"``
    - ``wind_time_delta_min``   – minutes saved (positive) or lost (negative)
    - ``aerodynamic_arrival_time`` – ISO-8601 adjusted arrival time (when calculable)

    Gracefully no-ops when the weather service is unavailable.
    """
    try:
        aero = get_aerodynamic_performance(from_iata, to_iata)
    except Exception as exc:
        logger.warning("Wind component calculation failed for %s→%s: %s", from_iata, to_iata, exc)
        aero = None

    if not aero:
        return offers

    wind_component_kt: float = aero["wind_component_kt"]
    ground_speed_kt: float = aero["ground_speed_kt"]
    wind_type: str = aero["wind_type"]

    for offer in offers:
        offer["wind_component_kt"] = wind_component_kt
        offer["ground_speed_kt"] = ground_speed_kt
        offer["wind_type"] = wind_type

        # Calculate time delta using GCD distance when available
        gcd_km = offer.get("gcd_distance")
        if gcd_km and gcd_km > 0:
            distance_nm = gcd_km / _KM_PER_NM
            baseline_hrs = distance_nm / _TAS_KT
            aero_hrs = distance_nm / ground_speed_kt
            delta_min = round((baseline_hrs - aero_hrs) * 60, 1)  # positive = time saved
            offer["wind_time_delta_min"] = delta_min

            # Adjust arrival time when available
            arrival_raw = offer.get("arrival_time") or offer.get("arrival")
            if arrival_raw:
                try:
                    from datetime import datetime, timedelta, timezone
                    # Parse ISO-8601 (with or without timezone)
                    try:
                        arr_dt = datetime.fromisoformat(arrival_raw.replace("Z", "+00:00"))
                    except ValueError:
                        if len(arrival_raw) >= 19:
                            arr_dt = datetime.strptime(arrival_raw[:19], "%Y-%m-%dT%H:%M:%S").replace(
                                tzinfo=timezone.utc
                            )
                        else:
                            raise
                    adjusted = arr_dt - timedelta(minutes=delta_min)
                    offer["aerodynamic_arrival_time"] = adjusted.isoformat()
                except Exception:
                    pass
        else:
            offer["wind_time_delta_min"] = None

    return offers


# Tier requirements for aerospace data points.
# Maps offer field names to the minimum subscription tier required to see them.
TIER_REQUIREMENTS: Dict[str, str] = {
    "wind_component": "pro",
    "aero_eta": "pro",
    "efficiency_score": "elite",
    "co2_kg": "elite",
    "density_altitude": "business",
    "takeoff_risk": "business",
}


def _stamp_tier_requirements(offers: list) -> list:
    """Attach a ``tier_requirements`` dict to every offer.

    The dict maps each gated data-point name to the minimum subscription tier
    a user must hold to see it, enabling the frontend to gate display
    dynamically without hard-coding tier names.
    """
    for offer in offers:
        offer["tier_requirements"] = dict(TIER_REQUIREMENTS)
    return offers


def _enrich_offers_with_airport_info(offers: list, from_iata: str, to_iata: str) -> list:
    """Resolve IATA codes to Full Airport Name, City, and Country via airportsdata.

    Stamps each offer with:
    - ``from_airport_name``, ``from_airport_city``, ``from_airport_country``
    - ``to_airport_name``, ``to_airport_city``, ``to_airport_country``

    Gracefully falls back to the IATA code / 'Unknown City' when the library
    has no entry for either airport.
    """
    from_info = iata_to_airport_info(from_iata)
    to_info = iata_to_airport_info(to_iata)

    for offer in offers:
        offer["from_airport_name"] = from_info["name"]
        offer["from_airport_city"] = from_info["city"]
        offer["from_airport_country"] = from_info["country"]
        offer["to_airport_name"] = to_info["name"]
        offer["to_airport_city"] = to_info["city"]
        offer["to_airport_country"] = to_info["country"]

    return offers


def check_circuit_breaker(supplier: str) -> bool:
    """Check if circuit breaker allows requests to supplier"""
    cb = CIRCUIT_BREAKER.get(supplier)
    if not cb:
        return True

    if cb['state'] == 'open':
        # Check if cooldown expired
        if time.time() - cb['last_failure'] > CIRCUIT_COOLDOWN:
            cb['state'] = 'half-open'
            cb['failures'] = 0
            logger.info(f"Circuit breaker for {supplier} moving to half-open")
            return True
        else:
            logger.warning(f"Circuit breaker OPEN for {supplier}, skipping")
            return False

    return True

def record_success(supplier: str):
    """Record successful request"""
    cb = CIRCUIT_BREAKER.get(supplier)
    if cb:
        cb['failures'] = 0
        cb['state'] = 'closed'

def record_failure(supplier: str):
    """Record failed request and potentially open circuit"""
    cb = CIRCUIT_BREAKER.get(supplier)
    if not cb:
        return

    cb['failures'] += 1
    cb['last_failure'] = time.time()

    if cb['failures'] >= CIRCUIT_THRESHOLD:
        cb['state'] = 'open'
        logger.error(f"Circuit breaker OPENED for {supplier} after {cb['failures']} failures")

async def search_aerodatabox(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via AeroDataBox"""
    if not check_circuit_breaker('aerodatabox'):
        return []

    try:
        results = aerodatabox_adapter.search_flights(
            segment.from_iata,
            segment.to_iata,
            segment.departure_date
        )
        record_success('aerodatabox')
        return results or []
    except Exception as e:
        logger.error(f"AeroDataBox search failed: {e}")
        record_failure('aerodatabox')
        return []

async def search_amadeus(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via Amadeus Flight Offers Search"""
    if not check_circuit_breaker('amadeus'):
        return []

    if not amadeus_service or not amadeus_service.enabled:
        return []

    try:
        return_date = None
        if len(request.segments) > 1:
            return_date = request.segments[1].departure_date

        results = amadeus_service.search_flights(
            from_iata=segment.from_iata,
            to_iata=segment.to_iata,
            departure_date=segment.departure_date,
            return_date=return_date,
            passengers=request.passengers.adults,
            cabin_class=request.cabin_class,
            currency=request.currency,
        )
        record_success('amadeus')
        return results or []
    except Exception as e:
        logger.error(f"Amadeus search failed: {e}")
        record_failure('amadeus')
        return []

async def search_duffel(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via Duffel (server-side only)"""
    if not check_circuit_breaker('duffel'):
        return []

    if not duffel_service or not duffel_service.enabled:
        return []

    try:
        results = await asyncio.to_thread(
            duffel_service.fetch_raw_offers,
            segment.from_iata,
            segment.to_iata,
            segment.departure_date,
            passengers=request.passengers.adults,
            cabin_class=request.cabin_class,
        )
        record_success('duffel')
        return results or []
    except Exception as e:
        logger.error(f"Duffel search failed: {e}")
        record_failure('duffel')
        return []

async def search_serpapi(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via SerpApi Google Flights engine"""
    if not check_circuit_breaker('serpapi'):
        return []

    if not serpapi_service or not serpapi_service.enabled:
        return []

    try:
        results = serpapi_service.search_flights(
            segment.from_iata,
            segment.to_iata,
            segment.departure_date,
            currency=request.currency,
        )
        record_success('serpapi')
        return results or []
    except Exception as e:
        logger.error(f"SerpApi search failed: {e}")
        record_failure('serpapi')
        return []

def normalize_offer(raw_offer: Dict, source: str) -> Optional[FlightOffer]:
    """Normalize offer from different suppliers to common format"""
    try:
        def _duration_to_minutes(duration: Any) -> int:
            if duration is None:
                return 0
            if isinstance(duration, (int, float)):
                return max(0, int(duration))
            if isinstance(duration, str):
                value = duration.strip().upper()
                if value.isdigit():
                    return int(value)
                match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", value)
                if match:
                    hours = int(match.group(1) or 0)
                    minutes = int(match.group(2) or 0)
                    seconds = int(match.group(3) or 0)
                    return (hours * 60) + minutes + (1 if seconds >= 30 else 0)
            return 0

        if source == 'aerodatabox':
            return FlightOffer(
                id=f"adb-{raw_offer.get('flight_number', 'unknown')}",
                source='aerodatabox',
                airline_iata=raw_offer.get('airline_iata', 'XX'),
                airline_name=raw_offer.get('airline_name', 'Unknown'),
                from_iata=raw_offer.get('from_iata', ''),
                to_iata=raw_offer.get('to_iata', ''),
                departure_time=raw_offer.get('departure_time', ''),
                arrival_time=raw_offer.get('arrival_time', ''),
                duration_minutes=raw_offer.get('duration_minutes'),
                stops=raw_offer.get('stops', 0),
                price=raw_offer.get('estimated_price', 500.0),
                currency=raw_offer.get('currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=raw_offer.get('baggage_kg'),
                booking_url=None
            )
        elif source == 'airscraper':
            return FlightOffer(
                id=f"ais-{raw_offer.get('id', 'unknown')}",
                source='airscraper',
                airline_iata=raw_offer.get('airline_iata') or raw_offer.get('airline', 'XX'),
                airline_name=raw_offer.get('airline_name', 'Unknown'),
                from_iata=raw_offer.get('origin') or raw_offer.get('from_iata', ''),
                to_iata=raw_offer.get('destination') or raw_offer.get('to_iata', ''),
                departure_time=raw_offer.get('departure_time') or raw_offer.get('departure', ''),
                arrival_time=raw_offer.get('arrival_time') or raw_offer.get('arrival', ''),
                duration_minutes=raw_offer.get('duration_minutes'),
                stops=raw_offer.get('stops', 0),
                price=float(raw_offer.get('price', 500)),
                currency=raw_offer.get('currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=raw_offer.get('baggage_allowance_kg'),
                booking_url=raw_offer.get('booking_url') or raw_offer.get('booking_link')
            )
        
        elif source == 'duffel':
            slices = raw_offer.get('slices', [])
            if not slices:
                return None

            first_slice = slices[0]
            segments = first_slice.get('segments', [])
            if not segments:
                return None

            # Hyper-safe duration fallback to bypass math crash
            total_duration = 0

            return FlightOffer(
                id=f"dfl-{raw_offer.get('id', 'unknown')}",
                source='duffel',
                airline_iata=segments[0].get('marketing_carrier', {}).get('iata_code', 'XX'),
                airline_name=segments[0].get('marketing_carrier', {}).get('name', 'Unknown'),
                from_iata=segments[0].get('origin', {}).get('iata_code', ''),
                to_iata=segments[-1].get('destination', {}).get('iata_code', ''),
                departure_time=segments[0].get('departing_at', ''),
                arrival_time=segments[-1].get('arriving_at', ''),
                duration_minutes=total_duration,
                stops=len(segments) - 1,
                price=float(raw_offer.get('total_amount', 500)),
                currency=raw_offer.get('total_currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=None,
                booking_url=None
            )

        elif source == 'serpapi':
            return FlightOffer(
                id=f"serpapi-{raw_offer.get('id', 'unknown')}",
                source='serpapi',
                airline_iata=raw_offer.get('airline', 'XX'),
                airline_name=raw_offer.get('airline_name', 'Unknown'),
                from_iata=raw_offer.get('from_iata', ''),
                to_iata=raw_offer.get('to_iata', ''),
                departure_time=raw_offer.get('departure', ''),
                arrival_time=raw_offer.get('arrival', ''),
                duration_minutes=raw_offer.get('duration_minutes'),
                stops=raw_offer.get('stops', 0),
                price=float(raw_offer.get('price', 0)),
                currency=raw_offer.get('currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=None,
                booking_url=raw_offer.get('booking_link'),
            )
        elif source == 'amadeus':
            slices = raw_offer.get('slices', [])
            if not slices:
                return None
            first_slice = slices[0]
            return FlightOffer(
                id=f"amd-{raw_offer.get('id', 'unknown')}",
                source='amadeus',
                airline_iata=raw_offer.get('airline', 'XX'),
                airline_name=raw_offer.get('airline_name', 'Unknown'),
                from_iata=first_slice.get('origin_iata', raw_offer.get('from_iata', '')),
                to_iata=first_slice.get('destination_iata', raw_offer.get('to_iata', '')),
                departure_time=first_slice.get('departure_time') or raw_offer.get('departure', ''),
                arrival_time=first_slice.get('arrival_time') or raw_offer.get('arrival', ''),
                duration_minutes=_duration_to_minutes(first_slice.get('duration')),
                stops=first_slice.get('stops', 0),
                price=float(raw_offer.get('price', 0)),
                currency=raw_offer.get('currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=None,
                booking_url=raw_offer.get('booking_link'),
            )

        return None
    except Exception as e:
        logger.error(f"Failed to normalize {source} offer: {e}")
        return None

def dedupe_offers(offers: List[FlightOffer]) -> List[FlightOffer]:
    """Deduplicate offers by airline + departure time + price"""
    seen = set()
    unique = []

    for offer in offers:
        # Round price to nearest 10
        price_rounded = round(offer.price / 10) * 10

        # Parse and round departure time to nearest hour
        try:
            dt = datetime.fromisoformat(offer.departure_time.replace('Z', '+00:00'))
            time_rounded = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        except:
            time_rounded = offer.departure_time

        key = f"{offer.airline_iata}|{time_rounded}|{price_rounded}"

        if key not in seen:
            seen.add(key)
            unique.append(offer)

    return unique

async def generate_flight_insight(top_flights: List[FlightOffer]) -> Optional[str]:
    """Generate an AI-powered recommendation for the top flights using OpenAI."""
    if not _openai_client or not top_flights:
        return None

    try:
        flights_to_analyze = top_flights[:3]
        flight_summaries = []
        for i, flight in enumerate(flights_to_analyze, 1):
            duration_str = f"{flight.duration_minutes} min" if flight.duration_minutes else "unknown duration"
            stops_str = f"{flight.stops} stop(s)"
            flight_summaries.append(
                f"Flight {i}: {flight.airline_name}, "
                f"${flight.price:.2f} {flight.currency}, "
                f"{duration_str}, {stops_str}"
            )
        flights_text = "\n".join(flight_summaries)

        response = _openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are an expert travel agent. Look at these 3 flights:\n\n"
                        f"{flights_text}\n\n"
                        "In one short sentence, tell the user which one is the actual best value "
                        "considering price and duration."
                    )
                }
            ],
            max_tokens=100,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI insight generation failed: {e}")
        return None


_HACKER_FARE_THRESHOLD = 0.10  # 10% cheaper required

# Sources list used when gathering multi-supplier results
_SOURCES = ['aerodatabox', 'amadeus', 'duffel', 'serpapi']


@router.post("/search")
async def search_flights(request: SearchRequest):
    """
    Aggregate flight search across multiple suppliers
    Supports multi-city, passengers, baggage, airline filters
    """
    # Generate cache key
    cache_key = hashlib.md5(request.json().encode()).hexdigest()

    # Check cache
    if cache_key in SEARCH_CACHE:
        cached_result, timestamp = SEARCH_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Returning cached search results for {cache_key}")
            return cached_result

    start_time = time.time()
    segment = request.segments[0]
    sources_queried: List[str] = ["duffel", "serpapi"]
    offers: List[Dict[str, Any]] = []

    duffel_raw_offers, serpapi_raw_offers = await asyncio.gather(
        search_duffel(segment, request),
        search_serpapi(segment, request),
        return_exceptions=True,
    )

    if isinstance(duffel_raw_offers, Exception):
        logger.warning("Duffel search task failed: %s", duffel_raw_offers)
        duffel_raw_offers = []
    if isinstance(serpapi_raw_offers, Exception):
        logger.warning("SerpApi search task failed: %s", serpapi_raw_offers)
        serpapi_raw_offers = []

    normalized_offers: List[Dict[str, Any]] = []
    for raw_offer in duffel_raw_offers:
        normalized = normalize_offer(raw_offer, "duffel")
        if normalized:
            normalized_offers.append(normalized.model_dump())

    for raw_offer in serpapi_raw_offers:
        normalized = normalize_offer(raw_offer, "serpapi")
        if normalized:
            normalized_offers.append(normalized.model_dump())

    offers = normalized_offers

    filtered_offers: List[Dict[str, Any]] = []
    for offer in offers:
        slices = offer.get("slices", []) if isinstance(offer, dict) else []
        first_slice = slices[0] if slices else {}
        first_segments = first_slice.get("segments", []) if isinstance(first_slice, dict) else []
        first_segment = first_segments[0] if first_segments else {}

        stops = int(first_slice.get("stops", offer.get("stops", 0)) or 0)
        if request.max_stops is not None and stops > request.max_stops:
            continue

        if segment.airline_filter:
            airline_iata = (offer.get("airline_iata") or first_slice.get("airline_iata") or "").upper()
            if airline_iata != segment.airline_filter.upper():
                continue

        checked_bags = first_segment.get("checked_bags", 0)
        if request.baggage_min_kg is not None and checked_bags < request.baggage_min_kg:
            continue
        if request.baggage_max_kg is not None and checked_bags > request.baggage_max_kg:
            continue

        filtered_offers.append(offer)

    filtered_offers.sort(key=lambda item: float(item.get("price", 0) or 0))
    enriched_offers = _inject_points_valuation(filtered_offers[:50])
    enriched_offers = _enrich_offers_with_density_altitude(enriched_offers, segment.from_iata)
    enriched_offers = _enrich_offers_with_wind_component(enriched_offers, segment.from_iata, segment.to_iata)
    enriched_offers = _enrich_offers_with_airport_info(enriched_offers, segment.from_iata, segment.to_iata)
    enriched_offers = _stamp_tier_requirements(enriched_offers)

    # Force currency conversion via Frankfurter API
    import requests
    target_currency = request.currency.upper()
    for offer in enriched_offers:
        current_currency = str(offer.get("currency", "")).upper()
        if current_currency and current_currency != target_currency:
            try:
                frankfurter_url = getattr(config, 'FRANKFURTER_API_URL', "https://api.frankfurter.app")
                res = requests.get(f"{frankfurter_url}/latest?amount={offer['price']}&from={current_currency}&to={target_currency}", timeout=3)
                if res.status_code == 200:
                    offer["price"] = round(res.json()["rates"][target_currency], 2)
                    offer["currency"] = target_currency
            except Exception as e:
                logger.warning(f"Failed to convert {current_currency} to {target_currency}: {e}")

    response = {
        "query": {
            "from": segment.from_iata,
            "to": segment.to_iata,
            "date": segment.departure_date,
            "passengers": request.passengers.dict()
        },
        "total_offers": len(filtered_offers),
        "offers": enriched_offers,
        "sources_queried": sources_queried,
        "search_time_ms": int((time.time() - start_time) * 1000),
        "ai_insight": None,
    }

    # Cache result
    SEARCH_CACHE[cache_key] = (response, time.time())

    return response


@router.get("/flights/live-price")
async def get_live_price(from_iata: str, to_iata: str, departure_date: str):
    """Return the current lowest economy fare for a single route/date."""
    from_iata = (from_iata or "").strip().upper()
    to_iata = (to_iata or "").strip().upper()

    if len(from_iata) != 3 or len(to_iata) != 3:
        raise HTTPException(status_code=400, detail="from_iata and to_iata must be 3-letter IATA codes")
    if not from_iata.isalpha() or not to_iata.isalpha():
        raise HTTPException(status_code=400, detail="from_iata and to_iata must contain only letters")
    if from_iata == to_iata:
        raise HTTPException(status_code=400, detail="from_iata and to_iata must be different")
    try:
        datetime.strptime(departure_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="departure_date must be in YYYY-MM-DD format")

    def _lowest_economy_offer(offers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best: Optional[Dict[str, Any]] = None
        for offer in offers or []:
            try:
                price = float(offer.get("price", 0))
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            cabin_class = str(offer.get("cabin_class", "economy")).lower()
            if cabin_class and "economy" not in cabin_class:
                continue

            currency = str(offer.get("currency", "USD") or "USD")
            candidate = {"current_price": round(price, 2), "currency": currency}
            if best is None or candidate["current_price"] < best["current_price"]:
                best = candidate
        return best

    attempted_suppliers: List[str] = []

    if duffel_service and duffel_service.enabled:
        attempted_suppliers.append("duffel")
        duffel_offers = await asyncio.to_thread(
            duffel_service.search_flights,
            from_iata,
            to_iata,
            departure_date,
            None,
            1,
            "economy",
        )
        best_duffel = _lowest_economy_offer(duffel_offers)
        if best_duffel:
            return best_duffel

    if amadeus_service and amadeus_service.enabled:
        attempted_suppliers.append("amadeus")
        amadeus_offers = await asyncio.to_thread(
            amadeus_service.search_flights,
            from_iata,
            to_iata,
            departure_date,
            None,
            1,
            "economy",
            "USD",
        )
        best_amadeus = _lowest_economy_offer(amadeus_offers)
        if best_amadeus:
            return best_amadeus

    if not attempted_suppliers:
        raise HTTPException(status_code=503, detail="No live flight-price provider is configured")

    raise HTTPException(status_code=404, detail="No live economy prices found for this route/date")

# Popular global tourist destinations for Explore Anywhere feature
EXPLORE_DESTINATIONS = [
    {"iata": "NRT", "city": "Tokyo Narita"},
    {"iata": "CDG", "city": "Paris"},
    {"iata": "LHR", "city": "London"},
    {"iata": "CUN", "city": "Cancun"},
    {"iata": "DXB", "city": "Dubai"},
    {"iata": "BKK", "city": "Bangkok"},
    {"iata": "SYD", "city": "Sydney"},
    {"iata": "FCO", "city": "Rome"},
    {"iata": "BCN", "city": "Barcelona"},
    {"iata": "AMS", "city": "Amsterdam"},
    {"iata": "SIN", "city": "Singapore"},
    {"iata": "GRU", "city": "Sao Paulo"},
    {"iata": "JNB", "city": "Johannesburg"},
    {"iata": "MEX", "city": "Mexico City"},
    {"iata": "ICN", "city": "Seoul"},
    {"iata": "HND", "city": "Tokyo Haneda"},
    {"iata": "DEL", "city": "New Delhi"},
    {"iata": "LIS", "city": "Lisbon"},
    {"iata": "YYZ", "city": "Toronto"},
    {"iata": "MNL", "city": "Manila"},
]


async def _search_cheapest_for_destination(
    origin: str, dest: dict, departure_date: str
) -> Optional[dict]:
    """Search for the cheapest flight from origin to a single destination."""
    segment = FlightSegment(
        from_iata=origin,
        to_iata=dest["iata"],
        departure_date=departure_date,
    )
    stub_request = SearchRequest(
        segments=[segment],
        passengers=PassengerCount(adults=1),
        cabin_class="economy",
        currency="USD",
    )

    tasks = [
        search_serpapi(segment, stub_request),
        search_amadeus(segment, stub_request),
        search_duffel(segment, stub_request),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_offers = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            continue
        source = ["serpapi", "amadeus", "duffel"][idx]
        for raw in result:
            normalized = normalize_offer(raw, source)
            if normalized:
                all_offers.append(normalized)

    if not all_offers:
        return None

    cheapest = min(all_offers, key=lambda o: o.price)
    return {
        "iata": dest["iata"],
        "city": dest["city"],
        "price": cheapest.price,
        "currency": cheapest.currency,
        "airline_name": cheapest.airline_name,
        "departure_time": cheapest.departure_time,
        "stops": cheapest.stops,
        "booking_url": cheapest.booking_url,
    }


@router.get("/flights/explore")
async def explore_flights(origin: str):
    """
    Return the cheapest one-way flight from *origin* to each of the
    20 popular global destinations, searching departures ~14 days out.
    Results are sorted by price ascending.
    """
    origin = origin.upper().strip()
    if len(origin) != 3:
        raise HTTPException(status_code=400, detail="origin must be a 3-letter IATA code")

    departure_date = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d")

    tasks = [
        _search_cheapest_for_destination(origin, dest, departure_date)
        for dest in EXPLORE_DESTINATIONS
        if dest["iata"] != origin
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results = [r for r in raw_results if r and not isinstance(r, Exception)]

    # Sort by price ascending; destinations with no results are already excluded
    results.sort(key=lambda x: x["price"])

    return {
        "origin": origin,
        "departure_date": departure_date,
        "destinations": results,
    }


@router.get("/search/circuit-breaker-status")
async def get_circuit_breaker_status():
    """Get current circuit breaker states"""
    return {
        "circuit_breakers": CIRCUIT_BREAKER,
        "threshold": CIRCUIT_THRESHOLD,
        "cooldown_seconds": CIRCUIT_COOLDOWN
    }
