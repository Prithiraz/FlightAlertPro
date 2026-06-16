"""Probabilistic dispatch-decision endpoints backed by the operational_ledger table."""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional
import logging

from supabase import create_client, Client
from config import config
from physics_engine import run_dispatch_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])

# Initialize Supabase client (lazily tolerant — missing config should not crash import)
try:
    supabase: Optional[Client] = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
except Exception as exc:  # pragma: no cover - depends on runtime config
    logger.warning("Supabase client unavailable for dispatch router: %s", exc)
    supabase = None


def _serialize(obj):
    """Recursively convert datetimes to ISO strings for JSON responses."""
    if isinstance(obj, datetime):
        return obj.isoformat() + "Z"
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


@router.post("/calculate")
async def calculate_dispatch(request: dict):
    """Run the probabilistic dispatch pipeline and return the full 4-stage result."""
    result = run_dispatch_pipeline(
        telemetry=request.get("telemetry", {}),
        fbo_data=request.get("fbo_data"),
        aircraft_category=request.get("aircraft_category", "narrow_body"),
        driver_transit_mean_min=request.get("driver_transit_mean_min", 15.0),
    )
    return _serialize(result)


@router.get("/assignment/{ledger_id}")
async def get_assignment(ledger_id: str):
    """Fetch the current driver assignment / flight context from operational_ledger."""
    if supabase is None:
        raise HTTPException(status_code=503, detail="Ledger storage unavailable")
    try:
        res = (
            supabase.table("operational_ledger")
            .select("*")
            .eq("id", ledger_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch assignment %s: %s", ledger_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch assignment")


@router.post("/log_driver_arrival")
async def log_driver_arrival(body: dict):
    """Log driver geofence arrival time to operational_ledger."""
    ledger_id = body.get("ledger_id")
    logged_at = datetime.utcnow().isoformat() + "Z"
    if ledger_id and supabase is not None:
        try:
            supabase.table("operational_ledger").update(
                {"driver_geofence_arrival_time": logged_at, "updated_at": logged_at}
            ).eq("id", ledger_id).execute()
        except Exception as exc:
            logger.error("Failed to log driver arrival for %s: %s", ledger_id, exc)
            raise HTTPException(status_code=500, detail="Failed to log driver arrival")
    return {"status": "ok", "logged_at": logged_at}


@router.post("/log_passenger_met")
async def log_passenger_met(body: dict):
    """Log actual passenger met time to operational_ledger."""
    ledger_id = body.get("ledger_id")
    logged_at = datetime.utcnow().isoformat() + "Z"
    if ledger_id and supabase is not None:
        try:
            supabase.table("operational_ledger").update(
                {"actual_passenger_met_time": logged_at, "updated_at": logged_at}
            ).eq("id", ledger_id).execute()
        except Exception as exc:
            logger.error("Failed to log passenger met for %s: %s", ledger_id, exc)
            raise HTTPException(status_code=500, detail="Failed to log passenger met")
    return {"status": "ok", "logged_at": logged_at}
