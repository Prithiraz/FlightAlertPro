"""OperationalLedger: ground-truth capture for the driver-dispatch feedback loop.

The mobile driver view records three milestones per trip — arrival at the FBO,
the passenger exiting the terminal, and the passenger being collected. Each event
is timestamped and stored alongside the flight's *original* Predicted On-Block
Time (OBT). Once the passenger is collected we compute ``Driver_Wait_Minutes`` —
the delta between the actual collection time and the predicted OBT — building an
FBO-level dataset that will eventually power FBO-specific micro-models.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

from config import config
from telemetry_store import get_flight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operational", tags=["operational"])

LEDGER_TABLE = "operational_ledger"

# ---------------------------------------------------------------------------
# Driver state machine
# ---------------------------------------------------------------------------
EVENT_ARRIVED = "arrived_at_fbo"
EVENT_EXITED = "passenger_exited"
EVENT_COLLECTED = "passenger_collected"

EVENT_SEQUENCE = [EVENT_ARRIVED, EVENT_EXITED, EVENT_COLLECTED]

EVENT_TIMESTAMP_COLUMN = {
    EVENT_ARRIVED: "arrived_at_fbo_at",
    EVENT_EXITED: "passenger_exited_at",
    EVENT_COLLECTED: "passenger_collected_at",
}


# ---------------------------------------------------------------------------
# Supabase client (lazy — keeps this module importable without DB credentials,
# e.g. in unit tests of the pure feedback-loop function below)
# ---------------------------------------------------------------------------
_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
            raise HTTPException(
                status_code=503,
                detail="Operational ledger storage is not configured",
            )
        _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
    return _supabase


def _parse_dt(value) -> Optional[datetime]:
    """Parse an ISO-8601 string (or pass through a datetime) into an aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Feedback loop
# ---------------------------------------------------------------------------
def calculate_driver_wait_minutes(
    predicted_on_block_time, passenger_collected_time
) -> Optional[int]:
    """Delta, in whole minutes, between actual collection and the predicted OBT.

    ``Driver_Wait_Minutes = Actual_Passenger_Collected_Time - Predicted_OBT``

    * Positive — the passenger was collected *after* the predicted on-block time;
      a driver staged for OBT waited this many minutes.
    * Negative — the passenger was collected *ahead* of the predicted on-block
      time (the aircraft/passenger beat the prediction).
    * ``None`` — either timestamp is missing or unparseable.
    """
    obt = _parse_dt(predicted_on_block_time)
    collected = _parse_dt(passenger_collected_time)
    if obt is None or collected is None:
        return None
    return int(round((collected - obt).total_seconds() / 60.0))


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------
def _fetch_latest_ledger(flight_id: str) -> Optional[dict]:
    sb = _get_supabase()
    resp = (
        sb.table(LEDGER_TABLE)
        .select("*")
        .eq("flight_id", flight_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _fetch_active_ledger(flight_id: str) -> Optional[dict]:
    """Return the most recent not-yet-completed trip for this flight, if any."""
    row = _fetch_latest_ledger(flight_id)
    if row and row.get("status") != "completed":
        return row
    return None


def _next_event(ledger: Optional[dict]) -> Optional[str]:
    """The next milestone the driver should record, or None when the trip is done."""
    if ledger is None:
        return EVENT_ARRIVED
    for event_type in EVENT_SEQUENCE:
        if not ledger.get(EVENT_TIMESTAMP_COLUMN[event_type]):
            return event_type
    return None


# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------
class DriverEventRequest(BaseModel):
    event_type: str
    # ISO-8601 timestamp of the button press; defaults to server time (UTC).
    event_timestamp: Optional[str] = None


class OperationalLedger(BaseModel):
    """Ground-truth record for a single VIP pickup — the FBO 'data moat'.

    One row captures the predicted vs. actual passenger-ready times for a trip,
    plus the realised driver wait and whether the pickup ran late. Accumulated
    across an FBO, these rows are the training set for FBO-specific micro-models.
    """

    flight_id: str
    airport_code: Optional[str] = None
    predicted_ready_time: Optional[datetime] = None
    actual_ready_time: Optional[datetime] = None
    driver_wait_minutes: Optional[float] = None
    late_pickup_boolean: Optional[bool] = None


def _compute_late_pickup(driver_arrival, actual_ready) -> Optional[bool]:
    """True when the driver reached the FBO after the passenger was already ready.

    A late pickup means the VIP had to wait; ``None`` when either timestamp is
    unavailable so we never fabricate a ground-truth label.
    """
    arrival = _parse_dt(driver_arrival)
    ready = _parse_dt(actual_ready)
    if arrival is None or ready is None:
        return None
    return arrival > ready


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/driver/{flight_id}")
async def get_driver_trip(flight_id: str):
    """Flight + passenger context and current ledger state for the driver view."""
    flight = get_flight(flight_id)
    ledger = None
    try:
        ledger = _fetch_latest_ledger(flight_id)
    except HTTPException:
        # Storage not configured — still serve live flight context so the driver
        # view renders; events will surface the 503 on write.
        ledger = None

    if flight is None and ledger is None:
        raise HTTPException(status_code=404, detail="Flight not found in live telemetry")

    flight = flight or {}
    predicted_obt = (ledger or {}).get("predicted_obt") or flight.get("predicted_on_block_time")

    return {
        "flight_id": flight_id,
        "flight_number": flight.get("flight_number") or (ledger or {}).get("flight_number"),
        "passenger_name": flight.get("passenger_name") or (ledger or {}).get("passenger_name"),
        "fbo": flight.get("fbo") or (ledger or {}).get("fbo"),
        "predicted_on_block_time": predicted_obt,
        "predicted_touchdown_time": flight.get("predicted_touchdown_time"),
        "ledger": ledger,
        "next_event": _next_event(ledger),
    }


@router.post("/driver/{flight_id}/event")
async def log_driver_event(flight_id: str, body: DriverEventRequest):
    """Record a driver milestone, capturing its exact timestamp and the OBT."""
    event_type = body.event_type
    if event_type not in EVENT_SEQUENCE:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event_type '{event_type}'. Expected one of {EVENT_SEQUENCE}.",
        )

    event_dt = _parse_dt(body.event_timestamp) or datetime.now(timezone.utc)
    ts_iso = event_dt.isoformat()
    column = EVENT_TIMESTAMP_COLUMN[event_type]

    sb = _get_supabase()
    ledger = _fetch_active_ledger(flight_id)
    flight = get_flight(flight_id) or {}

    if ledger is None:
        # Open a new trip, snapshotting the flight's ORIGINAL predicted OBT.
        predicted_obt = flight.get("predicted_on_block_time")
        row: dict = {
            "flight_id": flight_id,
            "flight_number": flight.get("flight_number"),
            "passenger_name": flight.get("passenger_name"),
            "fbo": flight.get("fbo"),
            "airport_code": flight.get("airport_code"),
            "predicted_obt": predicted_obt,
            "predicted_ready_time": predicted_obt,
            column: ts_iso,
            "status": "completed" if event_type == EVENT_COLLECTED else "in_progress",
        }
        if event_type == EVENT_COLLECTED:
            row["driver_wait_minutes"] = calculate_driver_wait_minutes(predicted_obt, ts_iso)
            row["actual_ready_time"] = ts_iso
            row["late_pickup_boolean"] = _compute_late_pickup(None, ts_iso)
        resp = sb.table(LEDGER_TABLE).insert(row).execute()
        saved = (resp.data or [row])[0]
        logger.info("Opened operational ledger for %s via %s", flight_id, event_type)
        return {"status": "ok", "ledger": saved, "next_event": _next_event(saved)}

    update: dict = {column: ts_iso, "updated_at": datetime.now(timezone.utc).isoformat()}
    if event_type == EVENT_COLLECTED:
        wait = calculate_driver_wait_minutes(ledger.get("predicted_obt"), ts_iso)
        # Ground truth for the data moat: the passenger was "ready" when they
        # exited the terminal (fall back to collection time if not recorded).
        actual_ready = ledger.get("passenger_exited_at") or ts_iso
        update["status"] = "completed"
        update["driver_wait_minutes"] = wait
        update["actual_ready_time"] = actual_ready
        update["late_pickup_boolean"] = _compute_late_pickup(
            ledger.get("arrived_at_fbo_at"), actual_ready
        )
    resp = sb.table(LEDGER_TABLE).update(update).eq("id", ledger["id"]).execute()
    saved = (resp.data or [{**ledger, **update}])[0]
    logger.info("Updated operational ledger %s via %s", ledger.get("id"), event_type)
    return {"status": "ok", "ledger": saved, "next_event": _next_event(saved)}


@router.get("/ledger")
async def list_ledger(limit: int = 50, fbo: Optional[str] = None):
    """Recent completed trips with their Driver_Wait_Minutes — the FBO dataset."""
    sb = _get_supabase()
    query = (
        sb.table(LEDGER_TABLE)
        .select("*")
        .eq("status", "completed")
        .order("passenger_collected_at", desc=True)
        .limit(max(1, min(limit, 500)))
    )
    if fbo:
        query = query.eq("fbo", fbo)
    resp = query.execute()
    rows = resp.data or []
    waits = [r["driver_wait_minutes"] for r in rows if r.get("driver_wait_minutes") is not None]
    avg_wait = round(sum(waits) / len(waits), 1) if waits else None
    return {
        "count": len(rows),
        "average_driver_wait_minutes": avg_wait,
        "trips": rows,
    }
