"""Destination explorer - discover where you can go from your home airport (Kayak Explore-style)"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["explore"])

# Popular outbound destinations from major hubs
_HUB_DESTINATIONS: Dict[str, List[str]] = {
    "LAX": ["JFK", "ORD", "MIA", "LHR", "CDG", "NRT", "SYD", "CUN", "DXB", "HNL", "BCN", "FCO"],
    "JFK": ["LAX", "LHR", "CDG", "MIA", "ORD", "BCN", "FCO", "AMS", "NRT", "CUN", "DXB", "SIN"],
    "LHR": ["JFK", "CDG", "AMS", "FCO", "BCN", "DXB", "SIN", "HKG", "NRT", "BKK", "MIA", "ORD"],
    "CDG": ["LHR", "JFK", "BCN", "FCO", "AMS", "DXB", "NRT", "SIN", "MIA", "LAX", "BKK", "HKG"],
    "DXB": ["LHR", "CDG", "BOM", "DEL", "SIN", "BKK", "JFK", "NRT", "SYD", "HKG", "MAN", "LAX"],
    "SYD": ["MEL", "BNE", "PER", "AKL", "SIN", "HKG", "NRT", "LAX", "LHR", "DXB", "BKK", "CDG"],
    "ORD": ["JFK", "LAX", "MIA", "LHR", "CDG", "CUN", "DEL", "NRT", "DFW", "ATL", "BCN", "FCO"],
    "MIA": ["JFK", "LAX", "ORD", "LHR", "CDG", "CUN", "BOG", "GRU", "SCL", "LIM", "MEX", "HAV"],
    "SIN": ["KUL", "BKK", "HKG", "NRT", "SYD", "LHR", "CDG", "DXB", "DEL", "BOM", "ICN", "MEL"],
    "HKG": ["NRT", "SIN", "BKK", "SYD", "LHR", "JFK", "LAX", "CDG", "ICN", "PEK", "TPE", "MNL"],
    "NRT": ["LAX", "JFK", "LHR", "CDG", "SIN", "HKG", "SYD", "BKK", "ICN", "SFO", "DXB", "ORD"],
    "AMS": ["LHR", "CDG", "JFK", "BCN", "FCO", "DXB", "SIN", "NRT", "BKK", "MIA", "ORD", "LAX"],
    "ATL": ["JFK", "LAX", "ORD", "MIA", "LHR", "CDG", "CUN", "NRT", "DXB", "BCN", "FCO", "AMS"],
    "DFW": ["JFK", "LAX", "ORD", "MIA", "LHR", "CDG", "CUN", "NRT", "DXB", "BCN", "FCO", "MEX"],
    "SFO": ["LAX", "JFK", "ORD", "LHR", "NRT", "HKG", "SIN", "SYD", "CDG", "HNL", "CUN", "MEX"],
}

_DEFAULT_DESTINATIONS = [
    "JFK", "LAX", "LHR", "CDG", "DXB", "SIN", "NRT", "SYD", "MIA", "ORD",
    "BCN", "FCO", "AMS", "BKK", "HKG", "CUN", "HNL", "ICN",
]

# Rich destination metadata for display
_DESTINATION_INFO: Dict[str, Dict[str, Any]] = {
    "JFK": {"city": "New York", "country": "USA", "emoji": "🗽", "tags": ["city", "culture", "shopping", "nightlife"]},
    "LAX": {"city": "Los Angeles", "country": "USA", "emoji": "🎬", "tags": ["city", "beach", "entertainment", "celebrities"]},
    "LHR": {"city": "London", "country": "UK", "emoji": "🎡", "tags": ["city", "history", "culture", "theatre"]},
    "CDG": {"city": "Paris", "country": "France", "emoji": "🗼", "tags": ["romance", "culture", "food", "art", "fashion"]},
    "NRT": {"city": "Tokyo", "country": "Japan", "emoji": "🗾", "tags": ["culture", "food", "technology", "anime", "city"]},
    "DXB": {"city": "Dubai", "country": "UAE", "emoji": "🏙️", "tags": ["luxury", "shopping", "beach", "skyscrapers"]},
    "SIN": {"city": "Singapore", "country": "Singapore", "emoji": "🦁", "tags": ["city", "food", "shopping", "cleanliness"]},
    "SYD": {"city": "Sydney", "country": "Australia", "emoji": "🦘", "tags": ["beach", "nature", "city", "outdoor"]},
    "MIA": {"city": "Miami", "country": "USA", "emoji": "🌴", "tags": ["beach", "nightlife", "culture", "art", "party"]},
    "ORD": {"city": "Chicago", "country": "USA", "emoji": "🏙️", "tags": ["city", "food", "culture", "architecture"]},
    "BCN": {"city": "Barcelona", "country": "Spain", "emoji": "🏖️", "tags": ["beach", "culture", "food", "nightlife", "art"]},
    "FCO": {"city": "Rome", "country": "Italy", "emoji": "🏛️", "tags": ["history", "food", "culture", "ancient", "art"]},
    "AMS": {"city": "Amsterdam", "country": "Netherlands", "emoji": "🌷", "tags": ["culture", "canals", "art", "cycling", "nightlife"]},
    "BKK": {"city": "Bangkok", "country": "Thailand", "emoji": "🛕", "tags": ["culture", "food", "temples", "budget", "nightlife"]},
    "HKG": {"city": "Hong Kong", "country": "China", "emoji": "🏮", "tags": ["shopping", "food", "city", "hiking", "nightlife"]},
    "CUN": {"city": "Cancun", "country": "Mexico", "emoji": "🌊", "tags": ["beach", "resort", "party", "ruins", "budget"]},
    "GRU": {"city": "São Paulo", "country": "Brazil", "emoji": "🌎", "tags": ["city", "culture", "food", "nightlife"]},
    "HNL": {"city": "Honolulu", "country": "USA", "emoji": "🌺", "tags": ["beach", "luxury", "nature", "surfing", "paradise"]},
    "ICN": {"city": "Seoul", "country": "South Korea", "emoji": "🇰🇷", "tags": ["technology", "food", "culture", "kpop", "fashion"]},
    "PEK": {"city": "Beijing", "country": "China", "emoji": "🏯", "tags": ["history", "culture", "food", "ancient", "architecture"]},
    "DEL": {"city": "Delhi", "country": "India", "emoji": "🕌", "tags": ["culture", "history", "food", "colour", "budget"]},
    "BOM": {"city": "Mumbai", "country": "India", "emoji": "🎭", "tags": ["city", "culture", "food", "bollywood", "budget"]},
    "MEL": {"city": "Melbourne", "country": "Australia", "emoji": "🎨", "tags": ["culture", "coffee", "sport", "food", "art"]},
    "SCL": {"city": "Santiago", "country": "Chile", "emoji": "🏔️", "tags": ["nature", "wine", "culture", "mountains"]},
    "AKL": {"city": "Auckland", "country": "New Zealand", "emoji": "🥝", "tags": ["nature", "adventure", "outdoor", "beaches"]},
    "SFO": {"city": "San Francisco", "country": "USA", "emoji": "🌉", "tags": ["city", "technology", "food", "culture", "nature"]},
    "ATL": {"city": "Atlanta", "country": "USA", "emoji": "🍑", "tags": ["city", "culture", "food", "music"]},
    "DFW": {"city": "Dallas", "country": "USA", "emoji": "⭐", "tags": ["city", "food", "shopping", "culture"]},
    "KUL": {"city": "Kuala Lumpur", "country": "Malaysia", "emoji": "🌆", "tags": ["food", "shopping", "culture", "budget", "city"]},
}

# Rough price estimates per route pair (USD, one-way)
_ROUTE_PRICE_ESTIMATES: Dict[tuple, float] = {
    ("LAX", "SFO"): 80,  ("JFK", "BOS"): 90,  ("LHR", "CDG"): 100,
    ("SYD", "MEL"): 110, ("SIN", "KUL"): 70,  ("ORD", "DFW"): 120,
    ("JFK", "MIA"): 180, ("JFK", "ORD"): 160, ("LAX", "ORD"): 200,
    ("LHR", "BCN"): 160, ("LHR", "FCO"): 170, ("LHR", "AMS"): 90,
    ("CDG", "BCN"): 120, ("SYD", "BNE"): 130, ("DXB", "BOM"): 200,
    ("DXB", "DEL"): 190, ("LAX", "LHR"): 650, ("JFK", "LHR"): 430,
    ("LAX", "NRT"): 700, ("JFK", "CDG"): 460, ("LHR", "DXB"): 370,
    ("LHR", "NRT"): 750, ("SYD", "LHR"): 1100, ("SYD", "LAX"): 900,
    ("SIN", "LHR"): 680, ("DXB", "SIN"): 340,  ("JFK", "NRT"): 740,
    ("LAX", "SYD"): 890, ("LAX", "HNL"): 340,  ("JFK", "CUN"): 310,
    ("LAX", "CUN"): 370, ("LHR", "BKK"): 560,  ("SIN", "NRT"): 420,
    ("DXB", "BKK"): 280, ("NRT", "ICN"): 180,  ("HKG", "NRT"): 310,
    ("LHR", "HKG"): 700, ("ORD", "LHR"): 520,  ("MIA", "LHR"): 480,
    ("SFO", "NRT"): 680, ("ATL", "LHR"): 500,  ("CDG", "NRT"): 760,
    ("AMS", "SIN"): 620, ("CDG", "BKK"): 580,  ("LHR", "SIN"): 670,
}


def _estimate_price(origin: str, dest: str) -> float:
    pair = (origin, dest)
    rev = (dest, origin)
    price = _ROUTE_PRICE_ESTIMATES.get(pair) or _ROUTE_PRICE_ESTIMATES.get(rev)
    return float(price) if price else 550.0


def _price_tier(price: float) -> str:
    if price < 150:
        return "💚 Budget"
    elif price < 350:
        return "💛 Moderate"
    elif price < 650:
        return "🟠 Premium"
    else:
        return "🔴 Long-haul"


def _best_months_for_dest(dest: str) -> List[str]:
    """Return broadly recommended travel months based on destination hemisphere/climate."""
    tropical = {"CUN", "BKK", "SIN", "KUL", "MNL", "HAV", "HNL", "MIA", "BOG", "LIM"}
    southern_hemi = {"SYD", "MEL", "BNE", "PER", "AKL", "SCL", "GRU"}
    if dest in tropical:
        return ["Nov", "Dec", "Jan", "Feb", "Mar"]
    elif dest in southern_hemi:
        return ["Sep", "Oct", "Nov", "Mar", "Apr"]
    else:
        return ["Mar", "Apr", "May", "Sep", "Oct", "Nov"]


@router.get("/explore")
async def explore_destinations(
    from_iata: str = Query(..., min_length=3, max_length=3, description="Origin IATA code (e.g. LAX)"),
    budget: Optional[float] = Query(None, gt=0, description="Max budget in USD for a one-way fare"),
    tags: Optional[str] = Query(
        None,
        description="Comma-separated interest tags to filter by: beach, city, culture, food, luxury, nature, budget, nightlife",
    ),
    limit: int = Query(12, ge=1, le=30, description="Max number of destinations to return"),
):
    """
    Discover destinations reachable from the given origin airport.

    Works like Kayak's Explore feature — shows a curated list of popular destinations
    with estimated prices, interest tags, and best travel months.
    Optional `budget` and `tags` filters help narrow results to the user's preferences.
    """
    origin = from_iata.upper()
    candidate_iatas = _HUB_DESTINATIONS.get(origin, _DEFAULT_DESTINATIONS)
    candidate_iatas = [d for d in candidate_iatas if d != origin]

    tag_filter = [t.strip().lower() for t in tags.split(",")] if tags else []

    results: List[Dict[str, Any]] = []
    for iata in candidate_iatas:
        info = _DESTINATION_INFO.get(iata, {
            "city": iata,
            "country": "Unknown",
            "emoji": "✈️",
            "tags": [],
        })

        dest_tags: List[str] = info.get("tags", [])
        if tag_filter and not any(t in dest_tags for t in tag_filter):
            continue

        est_price = _estimate_price(origin, iata)

        if budget is not None and est_price > budget:
            continue

        results.append({
            "iata": iata,
            "city": info.get("city", iata),
            "country": info.get("country", ""),
            "emoji": info.get("emoji", "✈️"),
            "tags": dest_tags,
            "estimated_price_usd": est_price,
            "price_tier": _price_tier(est_price),
            "best_months": _best_months_for_dest(iata),
        })

    results.sort(key=lambda r: r["estimated_price_usd"])

    return {
        "from_iata": origin,
        "budget_usd": budget,
        "tag_filter": tag_filter if tag_filter else None,
        "destinations_found": len(results[:limit]),
        "destinations": results[:limit],
    }
