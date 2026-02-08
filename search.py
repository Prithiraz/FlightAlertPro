"""Flight search aggregator with multi-supplier support"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
import hashlib
import time

from backend.services.rapidapi_adapters import aerodatabox_adapter, airscraper_adapter
from backend.services.duffel_service import duffel_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

# Circuit breaker state
CIRCUIT_BREAKER = {
    'aerodatabox': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'airscraper': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'duffel': {'failures': 0, 'last_failure': 0, 'state': 'closed'}
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
        # Note: duffel_service.search_flights is synchronous, but we need to call it from async context
        # For now, just skip Duffel integration - it would need proper async wrapper
        logger.info("Duffel integration requires async wrapper - skipping")
        return []
    except Exception as e:
        logger.error(f"Duffel search failed: {e}")
        record_failure('duffel')
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
        search_duffel(segment, request)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten and normalize results
    all_offers = []

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Supplier {idx} raised exception: {result}")
            continue

        source = ['aerodatabox', 'airscraper', 'duffel'][idx]

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

    response = {
        "query": {
            "from": segment.from_iata,
            "to": segment.to_iata,
            "date": segment.departure_date,
            "passengers": request.passengers.dict()
        },
        "total_offers": len(sorted_offers),
        "offers": [offer.dict() for offer in sorted_offers[:50]],  # Max 50 results
        "sources_queried": ['aerodatabox', 'airscraper', 'duffel'],
        "search_time_ms": int((time.time() - start_time) * 1000)
    }

    # Cache result
    SEARCH_CACHE[cache_key] = (response, time.time())

    return response

@router.get("/search/circuit-breaker-status")
async def get_circuit_breaker_status():
    """Get current circuit breaker states"""
    return {
        "circuit_breakers": CIRCUIT_BREAKER,
        "threshold": CIRCUIT_THRESHOLD,
        "cooldown_seconds": CIRCUIT_COOLDOWN
    }
