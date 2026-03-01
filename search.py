"""Flight search aggregator with multi-supplier support"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as _jose_jwt
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio
import logging
import hashlib
import time

from auth_deps import require_admin, CurrentUser
from supabase import create_client as _create_supabase_client
from rapidapi_adapters import aerodatabox_adapter, airscraper_adapter
from duffel_service import duffel_service
from config import config
from entitlements import get_plan_limits
from rate_limiter import rate_limiter
from cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

# Optional bearer – does not reject unauthenticated requests
_optional_bearer = HTTPBearer(auto_error=False)

# Module-level Supabase client reused across requests
_supabase = _create_supabase_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY) if config.SUPABASE_URL and config.SUPABASE_ANON_KEY else None

# Circuit breaker state
CIRCUIT_BREAKER = {
    'aerodatabox': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'airscraper': {'failures': 0, 'last_failure': 0, 'state': 'closed'},
    'duffel': {'failures': 0, 'last_failure': 0, 'state': 'closed'}
}

CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN = 600  # 10 minutes

# In-flight dedupe: maps cache_key -> asyncio.Future that resolves to the search result
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

# Simple request-level metrics counters (in-memory, reset on restart)
_metrics: Dict[str, Any] = {
    "search_total": 0,
    "search_cache_hits": 0,
    "search_errors": 0,
    "provider_calls": {},      # provider -> total calls
    "provider_errors": {},     # provider -> error count
    "provider_latency_ms": {},  # provider -> list of recent latencies (last 100)
}

class PassengerCount(BaseModel):
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=9)
    infants: int = Field(0, ge=0, le=9)

class FlightSegment(BaseModel):
    from_iata: str = Field(..., min_length=3, max_length=3)
    to_iata: str = Field(..., min_length=3, max_length=3)
    departure_date: str  # YYYY-MM-DD format
    airline_filter: Optional[str] = None

    @model_validator(mode='after')
    def validate_departure_date(self):
        try:
            dt = datetime.strptime(self.departure_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("departure_date must be in YYYY-MM-DD format")
        now = datetime.now(timezone.utc)
        if dt < now - timedelta(days=1):
            raise ValueError("departure_date cannot be in the past")
        max_future = now + timedelta(days=365)
        if dt > max_future:
            raise ValueError("departure_date cannot be more than 1 year in the future")
        return self

class SearchRequest(BaseModel):
    segments: List[FlightSegment] = Field(..., min_items=1, max_items=2)
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

def _record_provider_latency(provider: str, latency_ms: int):
    """Record per-provider latency for metrics."""
    _metrics["provider_calls"][provider] = _metrics["provider_calls"].get(provider, 0) + 1
    recent = _metrics["provider_latency_ms"].setdefault(provider, [])
    recent.append(latency_ms)
    if len(recent) > 100:
        recent.pop(0)

async def search_aerodatabox(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via AeroDataBox"""
    if not check_circuit_breaker('aerodatabox'):
        return []

    t0 = time.time()
    try:
        results = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: aerodatabox_adapter.search_flights(
                    segment.from_iata,
                    segment.to_iata,
                    segment.departure_date
                )
            ),
            timeout=config.PROVIDER_TIMEOUT_SECONDS,
        )
        record_success('aerodatabox')
        return results or []
    except asyncio.TimeoutError:
        logger.warning("AeroDataBox search timed out")
        record_failure('aerodatabox')
        return []
    except Exception as e:
        logger.error(f"AeroDataBox search failed: {e}")
        record_failure('aerodatabox')
        return []
    finally:
        _record_provider_latency('aerodatabox', int((time.time() - t0) * 1000))

async def search_airscraper(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via AirScraper"""
    if not check_circuit_breaker('airscraper'):
        return []

    t0 = time.time()
    try:
        results = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: airscraper_adapter.search_flights(
                    segment.from_iata,
                    segment.to_iata,
                    segment.departure_date,
                    adults=request.passengers.adults,
                    children=request.passengers.children
                )
            ),
            timeout=config.PROVIDER_TIMEOUT_SECONDS,
        )
        record_success('airscraper')
        return results or []
    except asyncio.TimeoutError:
        logger.warning("AirScraper search timed out")
        record_failure('airscraper')
        return []
    except Exception as e:
        logger.error(f"AirScraper search failed: {e}")
        record_failure('airscraper')
        return []
    finally:
        _record_provider_latency('airscraper', int((time.time() - t0) * 1000))

async def search_duffel(segment: FlightSegment, request: SearchRequest) -> List[Dict]:
    """Search via Duffel (server-side only)"""
    if config.DISABLE_PROVIDER_DUFFEL:
        logger.info("Duffel disabled via DISABLE_PROVIDER_DUFFEL kill switch")
        return []

    if not check_circuit_breaker('duffel'):
        return []

    if not duffel_service or not duffel_service.enabled:
        return []

    t0 = time.time()
    try:
        # Note: duffel_service.search_flights is synchronous, but we need to call it from async context
        # For now, just skip Duffel integration - it would need proper async wrapper
        logger.info("Duffel integration requires async wrapper - skipping")
        return []
    except Exception as e:
        logger.error(f"Duffel search failed: {e}")
        record_failure('duffel')
        return []
    finally:
        _record_provider_latency('duffel', int((time.time() - t0) * 1000))

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
async def search_flights(
    request: SearchRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
):
    """
    Aggregate flight search across multiple suppliers
    Supports multi-city, passengers, baggage, airline filters
    """
    # Kill switch
    if config.DISABLE_SEARCH:
        raise HTTPException(status_code=503, detail="Flight search is temporarily disabled")

    # Enforce per-user daily search rate limit when the caller is authenticated.
    if credentials and config.SUPABASE_JWT_SECRET:
        try:
            payload = _jose_jwt.decode(
                credentials.credentials,
                config.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            user_id: Optional[str] = payload.get("sub")
            user_email: Optional[str] = payload.get("email")
            if user_id and user_email:
                # Look up the user's plan (best-effort; defaults to "free")
                plan = "free"
                try:
                    if _supabase:
                        plan_result = (
                            _supabase.table("user_profiles")
                            .select("plan")
                            .eq("email", user_email)
                            .maybe_single()
                            .execute()
                        )
                        if plan_result.data and plan_result.data.get("plan"):
                            plan = plan_result.data["plan"]
                except Exception as exc:
                    logger.debug("Could not fetch plan for %s: %s", user_email, exc)
                limits = get_plan_limits(plan)
                if not rate_limiter.check_search_rate_limit(user_id, limits["max_searches_per_day"]):
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Daily search limit ({limits['max_searches_per_day']}) reached "
                            f"for the {plan} plan. Upgrade to search more."
                        ),
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug("Optional auth check failed during search: %s", exc)

    # Generate cache key from normalized request payload
    cache_key = hashlib.md5(request.json().encode()).hexdigest()

    _metrics["search_total"] += 1

    # Check cache (shared cache_service supports both Redis and in-memory)
    cached = cache_service.get_search_results(cache_key)
    if cached is not None:
        logger.info(f"Cache hit for search {cache_key}")
        _metrics["search_cache_hits"] += 1
        cached["cache_hit"] = True
        return cached

    # In-flight dedupe: if an identical search is already running, wait for it
    waiting_fut = None
    async with _inflight_lock:
        if cache_key in _inflight:
            waiting_fut = _inflight[cache_key]
        else:
            own_fut = asyncio.get_event_loop().create_future()
            _inflight[cache_key] = own_fut

    if waiting_fut is not None:
        # Another coroutine is executing the same search – wait for its result
        try:
            result = await asyncio.wait_for(asyncio.shield(waiting_fut), timeout=60)
            result["cache_hit"] = True
            return result
        except Exception:
            pass  # fall through to execute search ourselves

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

    # Flatten and normalize results; track per-provider status
    all_offers = []
    provider_status = {}

    for idx, result in enumerate(results):
        source = ['aerodatabox', 'airscraper', 'duffel'][idx]
        if isinstance(result, Exception):
            logger.error(f"Supplier {source} raised exception: {result}")
            _metrics["provider_errors"][source] = _metrics["provider_errors"].get(source, 0) + 1
            provider_status[source] = "error"
            continue

        provider_status[source] = "ok"
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
        "provider_status": provider_status,
        "search_time_ms": int((time.time() - start_time) * 1000),
        "cache_hit": False,
        "cached_at": None,
    }

    # Store in cache
    cached_at = datetime.now(timezone.utc).isoformat()
    response["cached_at"] = cached_at
    cache_service.set_search_results(cache_key, response, ttl=config.CACHE_TTL_SECONDS)

    # Resolve in-flight future so waiting coroutines can return
    async with _inflight_lock:
        resolved_fut = _inflight.pop(cache_key, None)
    if resolved_fut is not None and not resolved_fut.done():
        resolved_fut.set_result(response)

    return response

@router.get("/search/circuit-breaker-status")
async def get_circuit_breaker_status(admin: CurrentUser = Depends(require_admin)):
    """Get current circuit breaker states (admin only)"""
    return {
        "circuit_breakers": CIRCUIT_BREAKER,
        "threshold": CIRCUIT_THRESHOLD,
        "cooldown_seconds": CIRCUIT_COOLDOWN
    }

@router.get("/metrics")
async def get_metrics(admin: CurrentUser = Depends(require_admin)):
    """Expose performance metrics (admin only)."""
    total = _metrics["search_total"]
    hits = _metrics["search_cache_hits"]
    cache_hit_ratio = round(hits / total, 4) if total > 0 else 0.0

    provider_avg_latency = {}
    for provider, latencies in _metrics["provider_latency_ms"].items():
        if latencies:
            provider_avg_latency[provider] = {
                "avg_ms": round(sum(latencies) / len(latencies)),
                "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)]) if len(latencies) >= 20 else None,
                "samples": len(latencies),
            }

    return {
        "search_total": total,
        "search_cache_hits": hits,
        "cache_hit_ratio": cache_hit_ratio,
        "search_errors": _metrics["search_errors"],
        "provider_calls": _metrics["provider_calls"],
        "provider_errors": _metrics["provider_errors"],
        "provider_latency": provider_avg_latency,
        "circuit_breakers": {p: cb["state"] for p, cb in CIRCUIT_BREAKER.items()},
        "cache_ttl_seconds": config.CACHE_TTL_SECONDS,
        "provider_timeout_seconds": config.PROVIDER_TIMEOUT_SECONDS,
    }

