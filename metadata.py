"""Metadata API routes for airports and airlines (offline OpenFlights data)"""
from fastapi import APIRouter, Query
from typing import List, Dict, Optional
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])

# Load data at module level (singleton)
_data_candidate = Path(__file__).parent / "data"
DATA_DIR = _data_candidate if _data_candidate.exists() else Path(__file__).parent

AIRPORTS_ALL = []
AIRPORTS_COMMERCIAL = []
AIRLINES = []

# Indices for fast lookup
AIRPORTS_BY_IATA = {}
AIRPORTS_BY_CITY = {}
AIRLINES_BY_IATA = {}

def load_metadata():
    """Load OpenFlights JSON data into memory"""
    global AIRPORTS_ALL, AIRPORTS_COMMERCIAL, AIRLINES
    global AIRPORTS_BY_IATA, AIRPORTS_BY_CITY, AIRLINES_BY_IATA

    # Load airports
    airports_file = DATA_DIR / "airports_openflights.json"
    commercial_file = DATA_DIR / "airports_commercial.json"
    airlines_file = DATA_DIR / "airlines_openflights.json"

    try:
        with open(airports_file, 'r', encoding='utf-8') as f:
            AIRPORTS_ALL = json.load(f)

        # Build IATA index
        for airport in AIRPORTS_ALL:
            iata = airport.get('iata')
            if iata:
                AIRPORTS_BY_IATA[iata.upper()] = airport

                # Build city index
                city = airport.get('city', '').lower()
                if city:
                    if city not in AIRPORTS_BY_CITY:
                        AIRPORTS_BY_CITY[city] = []
                    AIRPORTS_BY_CITY[city].append(airport)

        print(f"✓ Loaded {len(AIRPORTS_ALL)} airports, indexed {len(AIRPORTS_BY_IATA)} by IATA")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load airports_openflights.json: {e}")
        AIRPORTS_ALL = []

    try:
        with open(commercial_file, 'r', encoding='utf-8') as f:
            AIRPORTS_COMMERCIAL = json.load(f)
        print(f"✓ Loaded {len(AIRPORTS_COMMERCIAL)} commercial airports")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load airports_commercial.json: {e}")
        AIRPORTS_COMMERCIAL = []

    try:
        with open(airlines_file, 'r', encoding='utf-8') as f:
            AIRLINES = json.load(f)

        # Build IATA index
        for airline in AIRLINES:
            iata = airline.get('iata')
            if iata:
                AIRLINES_BY_IATA[iata.upper()] = airline

        print(f"✓ Loaded {len(AIRLINES)} airlines, indexed {len(AIRLINES_BY_IATA)} by IATA")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load airlines_openflights.json: {e}")
        AIRLINES = []

# Load on startup
load_metadata()

def fuzzy_search_airports(query: str, use_commercial: bool = True, limit: int = 10) -> List[Dict]:
    """Fuzzy search airports with prefix priority"""
    if not query:
        return []

    q = query.lower().strip()
    dataset = AIRPORTS_COMMERCIAL if use_commercial else AIRPORTS_ALL

    matches = []
    exact_iata = []
    prefix_matches = []
    substring_matches = []

    for airport in dataset:
        iata = airport.get('iata', '').lower()
        icao = airport.get('icao', '').lower() if airport.get('icao') else ''
        name = airport.get('name', '').lower()
        city = airport.get('city', '').lower()
        country = airport.get('country', '').lower()

        # Exact IATA match
        if iata == q:
            exact_iata.append(airport)
        # Prefix matches (higher priority)
        elif (iata.startswith(q) or city.startswith(q) or
              name.startswith(q) or icao.startswith(q)):
            prefix_matches.append(airport)
        # Substring matches
        elif (q in iata or q in city or q in name or q in country):
            substring_matches.append(airport)

    # Combine results with priority
    matches = exact_iata + prefix_matches + substring_matches

    return matches[:limit]

def group_by_city(airports: List[Dict]) -> List[Dict]:
    """Group airports by city"""
    city_groups = {}

    for airport in airports:
        city = airport.get('city', 'Unknown')
        country = airport.get('country', 'Unknown')
        key = f"{city}|{country}"

        if key not in city_groups:
            city_groups[key] = {
                'city': city,
                'country': country,
                'airports': []
            }

        city_groups[key]['airports'].append({
            'iata': airport.get('iata'),
            'icao': airport.get('icao'),
            'name': airport.get('name'),
            'latitude': airport.get('latitude'),
            'longitude': airport.get('longitude')
        })

    return list(city_groups.values())

@router.get("/airports")
async def search_airports(
    q: str = Query(..., min_length=1, description="Search query"),
    commercial_only: bool = Query(True, description="Show commercial airports only"),
    grouped: bool = Query(True, description="Group results by city"),
    limit: int = Query(10, ge=1, le=50, description="Max results")
):
    """
    Search airports with fuzzy matching
    Returns grouped by city with all airports in each city
    """
    airports = fuzzy_search_airports(q, use_commercial=commercial_only, limit=limit * 3)

    if grouped:
        result = group_by_city(airports)
        return {
            "query": q,
            "count": len(result),
            "cities": result[:limit]
        }
    else:
        return {
            "query": q,
            "count": len(airports),
            "airports": airports[:limit]
        }

@router.get("/airports/{iata}")
async def get_airport_by_iata(iata: str):
    """Get airport details by IATA code"""
    airport = AIRPORTS_BY_IATA.get(iata.upper())

    if not airport:
        return {"error": "Airport not found"}, 404

    return airport

@router.get("/airlines")
async def search_airlines(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results")
):
    """Search airlines with fuzzy matching"""
    if not q:
        return {"query": q, "count": 0, "airlines": []}

    q_lower = q.lower().strip()
    matches = []
    exact_iata = []
    prefix_matches = []
    substring_matches = []

    for airline in AIRLINES:
        iata = airline.get('iata', '').lower()
        icao = airline.get('icao', '').lower() if airline.get('icao') else ''
        name = airline.get('name', '').lower()
        country = airline.get('country', '').lower()

        # Exact IATA match
        if iata == q_lower:
            exact_iata.append(airline)
        # Prefix matches
        elif (iata.startswith(q_lower) or name.startswith(q_lower) or
              icao.startswith(q_lower)):
            prefix_matches.append(airline)
        # Substring matches
        elif (q_lower in iata or q_lower in name or q_lower in country):
            substring_matches.append(airline)

    matches = exact_iata + prefix_matches + substring_matches

    return {
        "query": q,
        "count": len(matches),
        "airlines": matches[:limit]
    }

@router.get("/airlines/{iata}")
async def get_airline_by_iata(iata: str):
    """Get airline details by IATA code"""
    airline = AIRLINES_BY_IATA.get(iata.upper())

    if not airline:
        return {"error": "Airline not found"}, 404

    return airline

@router.get("/stats")
async def get_stats():
    """Get metadata statistics"""
    return {
        "airports_total": len(AIRPORTS_ALL),
        "airports_commercial": len(AIRPORTS_COMMERCIAL),
        "airlines_active": len(AIRLINES),
        "airports_indexed": len(AIRPORTS_BY_IATA),
        "airlines_indexed": len(AIRLINES_BY_IATA),
        "cities_indexed": len(AIRPORTS_BY_CITY)
    }
