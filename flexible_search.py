"""Flexible date search - find cheapest flights around a target date (Kayak-style fare calendar)"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging

from rapidapi_adapters import airscraper_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["flexible-search"])


class FlexibleSearchRequest(BaseModel):
    from_iata: str = Field(..., min_length=3, max_length=3)
    to_iata: str = Field(..., min_length=3, max_length=3)
    departure_date: str  # YYYY-MM-DD base date
    flex_days: int = Field(3, ge=1, le=7, description="Search ± this many days around the base date")
    passengers: int = Field(1, ge=1, le=9)
    cabin_class: str = Field("economy")
    currency: str = Field("USD")


async def _search_one_date(from_iata: str, to_iata: str, date_str: str, passengers: int) -> tuple:
    """Search flights for a single date; returns (date_str, offers_list)."""
    try:
        results = airscraper_adapter.search_flights(
            from_iata,
            to_iata,
            date_str,
            adults=passengers,
        )
        return date_str, results or []
    except Exception as e:
        logger.warning(f"Flexible search failed for {date_str}: {e}")
        return date_str, []


@router.post("/search/flexible")
async def flexible_date_search(request: FlexibleSearchRequest):
    """
    Search flights on the specified date ± flex_days.

    Returns a fare calendar showing the cheapest price per day so users can
    pick the most affordable travel window (Kayak-style flexible dates).
    """
    try:
        base_date = datetime.strptime(request.departure_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid departure_date format. Use YYYY-MM-DD")

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    dates = [
        (base_date + timedelta(days=delta)).strftime("%Y-%m-%d")
        for delta in range(-request.flex_days, request.flex_days + 1)
        if base_date + timedelta(days=delta) >= today
    ]

    if not dates:
        raise HTTPException(status_code=400, detail="All dates in range are in the past")

    origin = request.from_iata.upper()
    dest = request.to_iata.upper()

    tasks = [_search_one_date(origin, dest, d, request.passengers) for d in dates]
    raw_results = await asyncio.gather(*tasks)

    calendar: List[Dict[str, Any]] = []
    cheapest_date = None
    cheapest_price = float("inf")

    for date_str, offers in raw_results:
        if offers:
            prices = [float(o.get("price", 999999)) for o in offers]
            min_price = min(prices)
            best = min(offers, key=lambda o: float(o.get("price", 999999)))
            calendar.append({
                "date": date_str,
                "min_price": round(min_price, 2),
                "offer_count": len(offers),
                "best_offer": best,
                "is_cheapest": False,
            })
            if min_price < cheapest_price:
                cheapest_price = min_price
                cheapest_date = date_str
        else:
            calendar.append({
                "date": date_str,
                "min_price": None,
                "offer_count": 0,
                "best_offer": None,
                "is_cheapest": False,
            })

    # Flag the cheapest date
    for day in calendar:
        if day["date"] == cheapest_date:
            day["is_cheapest"] = True

    calendar.sort(key=lambda d: d["date"])

    return {
        "from_iata": origin,
        "to_iata": dest,
        "base_date": request.departure_date,
        "flex_days": request.flex_days,
        "dates_searched": len(dates),
        "cheapest_date": cheapest_date,
        "cheapest_price": round(cheapest_price, 2) if cheapest_price < float("inf") else None,
        "currency": request.currency,
        "calendar": calendar,
    }
