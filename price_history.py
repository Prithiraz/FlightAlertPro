"""Price history tracking and trend analysis (premium feature)"""
from fastapi import APIRouter, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/price-history", tags=["price-history"])

# In-memory price store: route_key -> list of observations
_HISTORY: Dict[str, List[Dict[str, Any]]] = {}
_MAX_ENTRIES_PER_ROUTE = 90


def record_price(
    from_iata: str,
    to_iata: str,
    price: float,
    currency: str = "USD",
    source: str = "search",
) -> None:
    """
    Record a price observation for a route.

    Called automatically by the search endpoint and the background worker so that
    price history accumulates over time without any extra user action.
    """
    route_key = f"{from_iata.upper()}_{to_iata.upper()}_{currency.upper()}"
    entry: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "price": round(float(price), 2),
        "currency": currency.upper(),
        "source": source,
    }

    bucket = _HISTORY.setdefault(route_key, [])
    bucket.append(entry)
    if len(bucket) > _MAX_ENTRIES_PER_ROUTE:
        _HISTORY[route_key] = bucket[-_MAX_ENTRIES_PER_ROUTE:]

    # Persist to Supabase when available
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            sb.table("price_history").insert({
                "from_iata": from_iata.upper(),
                "to_iata": to_iata.upper(),
                "price": entry["price"],
                "currency": entry["currency"],
                "source": source,
                "recorded_at": entry["timestamp"],
            }).execute()
    except Exception as exc:
        logger.debug(f"Could not persist price history to DB: {exc}")


def _compute_trend(prices: List[float]) -> Dict[str, Optional[str]]:
    """
    Simple trend calculation: compare the 3 most-recent prices vs the rest.
    Returns a dict with keys 'trend' and 'recommendation'.
    """
    if len(prices) < 4:
        return {"trend": None, "recommendation": None}

    recent = prices[-3:]
    older = prices[:-3]
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)

    if avg_recent < avg_older * 0.95:
        return {"trend": "falling", "recommendation": "buy_now"}
    elif avg_recent > avg_older * 1.05:
        return {"trend": "rising", "recommendation": "monitor"}
    else:
        return {"trend": "stable", "recommendation": "fair_price"}


@router.get("")
async def get_price_history(
    from_iata: str = Query(..., min_length=3, max_length=3, description="Origin IATA"),
    to_iata: str = Query(..., min_length=3, max_length=3, description="Destination IATA"),
    currency: str = Query("USD", min_length=3, max_length=3),
    days: int = Query(30, ge=7, le=90, description="How many days of history to return"),
):
    """
    Retrieve price history for a route.

    Returns individual data points plus aggregated statistics (min, max, avg) and
    a simple trend indicator so the frontend can render a sparkline / trend badge.
    """
    route_key = f"{from_iata.upper()}_{to_iata.upper()}_{currency.upper()}"
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # In-memory history filtered by cutoff
    mem_history = [h for h in _HISTORY.get(route_key, []) if h["timestamp"] >= cutoff]

    # Try Supabase
    db_history: List[Dict[str, Any]] = []
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            result = (
                sb.table("price_history")
                .select("*")
                .eq("from_iata", from_iata.upper())
                .eq("to_iata", to_iata.upper())
                .eq("currency", currency.upper())
                .gte("recorded_at", cutoff)
                .order("recorded_at")
                .execute()
            )
            if result.data:
                db_history = [
                    {
                        "timestamp": r["recorded_at"],
                        "price": r["price"],
                        "currency": r["currency"],
                        "source": r.get("source", "unknown"),
                    }
                    for r in result.data
                ]
    except Exception as exc:
        logger.debug(f"Could not fetch price history from DB: {exc}")

    # Merge, deduplicate by timestamp
    combined = {h["timestamp"]: h for h in (mem_history + db_history)}
    history = sorted(combined.values(), key=lambda h: h["timestamp"])

    prices = [h["price"] for h in history]
    trend_info = _compute_trend(prices)

    return {
        "from_iata": from_iata.upper(),
        "to_iata": to_iata.upper(),
        "currency": currency.upper(),
        "days": days,
        "data_points": len(history),
        "history": history,
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "trend": trend_info["trend"],
        "recommendation": trend_info["recommendation"],
    }
