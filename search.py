"""Flight search aggregator with multi-supplier support"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import hashlib
import time

import openai
from rapidapi_adapters import aerodatabox_adapter, airscraper_adapter
from duffel_service import duffel_service
from serpapi_service import serpapi_service
from config import config

logger = logging.getLogger(__name__)

# Module-level OpenAI client (initialized once; None when API key is absent)
_openai_client: Optional[openai.OpenAI] = (
    openai.OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
)

router = APIRouter(prefix="/api", tags=["search"])

# Circuit breaker state
CIRCUIT_BREAKER = {
    'aerodatabox': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'airscraper': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
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

async def search_airscraper(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via AirScraper"""
    if not check_circuit_breaker('airscraper'):
        return []

    try:
        results = airscraper_adapter.search_flights(
            segment.from_iata,
            segment.to_iata,
            segment.departure_date,
            adults=request.passengers.adults,
            children=request.passengers.children
        )
        record_success('airscraper')
        return results or []
    except Exception as e:
        logger.error(f"AirScraper search failed: {e}")
        record_failure('airscraper')
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
        return_date = None
        if len(request.segments) > 1:
            return_date = request.segments[1].departure_date

        results = serpapi_service.search_flights(
            segment.from_iata,
            segment.to_iata,
            segment.departure_date,
            return_date=return_date,
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
                airline_iata=raw_offer.get('airline_iata', 'XX'),
                airline_name=raw_offer.get('airline_name', 'Unknown'),
                from_iata=raw_offer.get('origin', ''),
                to_iata=raw_offer.get('destination', ''),
                departure_time=raw_offer.get('departure_time', ''),
                arrival_time=raw_offer.get('arrival_time', ''),
                duration_minutes=raw_offer.get('duration_minutes'),
                stops=raw_offer.get('stops', 0),
                price=float(raw_offer.get('price', 500)),
                currency=raw_offer.get('currency', 'USD'),
                cabin_class=raw_offer.get('cabin_class', 'economy'),
                baggage_kg=raw_offer.get('baggage_allowance_kg'),
                booking_url=raw_offer.get('booking_url')
            )
        elif source == 'duffel':
            slices = raw_offer.get('slices', [])
            if not slices:
                return None

            first_slice = slices[0]
            segments = first_slice.get('segments', [])
            if not segments:
                return None

            total_duration = sum(s.get('duration', 0) for s in segments)

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

    # Search first segment only for now (multi-city requires sequential booking)
    segment = request.segments[0]

    # Launch parallel searches
    tasks = [
        search_aerodatabox(segment, request),
        search_airscraper(segment, request),
        search_duffel(segment, request),
        search_serpapi(segment, request),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten and normalize results
    all_offers = []

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Supplier {idx} raised exception: {result}")
            continue

        source = ['aerodatabox', 'airscraper', 'duffel', 'serpapi'][idx]

        for raw_offer in result:
            normalized = normalize_offer(raw_offer, source)
            if normalized:
                # Apply filters
                if request.max_stops is not None and normalized.stops > request.max_stops:
                    continue

                if segment.airline_filter:
                    if normalized.airline_iata.upper() != segment.airline_filter.upper():
                        continue

                if request.baggage_min_kg and normalized.baggage_kg:
                    if normalized.baggage_kg < request.baggage_min_kg:
                        continue

                if request.baggage_max_kg and normalized.baggage_kg:
                    if normalized.baggage_kg > request.baggage_max_kg:
                        continue

                all_offers.append(normalized)

    # Dedupe and sort by price
    unique_offers = dedupe_offers(all_offers)
    sorted_offers = sorted(unique_offers, key=lambda x: x.price)

    # Generate AI insight for the top 3 cheapest flights
    ai_insight = await generate_flight_insight(sorted_offers)

    response = {
        "query": {
            "from": segment.from_iata,
            "to": segment.to_iata,
            "date": segment.departure_date,
            "passengers": request.passengers.dict()
        },
        "total_offers": len(sorted_offers),
        "offers": [offer.dict() for offer in sorted_offers[:50]],  # Max 50 results
        "sources_queried": ['aerodatabox', 'airscraper', 'duffel', 'serpapi'],
        "search_time_ms": int((time.time() - start_time) * 1000),
        "ai_insight": ai_insight,
    }

    # Cache result
    SEARCH_CACHE[cache_key] = (response, time.time())

    return response

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
        search_airscraper(segment, stub_request),
        search_duffel(segment, stub_request),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_offers = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            continue
        source = ["serpapi", "airscraper", "duffel"][idx]
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
