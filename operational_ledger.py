"""OperationalLedger: ground-truth capture for the driver-dispatch feedback loop.

The mobile driver view records two milestones per trip, deliberately split so we
can isolate *passenger readiness* from *driver tardiness*:

* ``driver_arrived``  — the driver reaches the FBO (a simulated geofence
  arrival), stored as ``driver_geofence_arrival_time``.
* ``passenger_met``   — the driver physically meets the passenger (manual),
  stored as ``actual_passenger_met_time``.

Each event is timestamped and stored alongside the flight's predicted touchdown
and passenger-ready times. On completion we derive two metrics:

* ``driver_wait_minutes``  = met − arrival  (the driver idled; the passenger was
  not yet ready).
* ``late_pickup_minutes``  = arrival − predicted_ready  (the driver arrived after
  the passenger was ready, so the VIP waited).

Accumulated across an FBO, these rows are the ground-truth 'data moat' for
FBO-specific micro-models.
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
EVENT_DRIVER_ARRIVED = "driver_arrived"
EVENT_PASSENGER_MET = "passenger_met"

EVENT_SEQUENCE = [EVENT_DRIVER_ARRIVED, EVENT_PASSENGER_MET]

EVENT_TIMESTAMP_COLUMN = {
    EVENT_DRIVER_ARRIVED: "driver_geofence_arrival_time",
    EVENT_PASSENGER_MET: "actual_passenger_met_time",
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
    driver_geofence_arrival_time, actual_passenger_met_time
) -> Optional[int]:
    """Whole minutes the driver idled at the FBO waiting for the passenger.

    ``driver_wait_minutes = max(0, passenger_met - driver_arrival)``

    The driver was in position before the passenger was ready, so this isolates
    *passenger readiness* delay. Clamped at zero (a driver who arrives after the
    passenger did not 'wait'). ``None`` when either timestamp is missing.
    """
    arrival = _parse_dt(driver_geofence_arrival_time)
    met = _parse_dt(actual_passenger_met_time)
    if arrival is None or met is None:
        return None
    return max(0, int(round((met - arrival).total_seconds() / 60.0)))


def calculate_late_pickup_minutes(
    driver_geofence_arrival_time, predicted_ready_time
) -> Optional[int]:
    """Whole minutes the passenger waited because the driver arrived late.

    ``late_pickup_minutes = max(0, driver_arrival - predicted_ready)``

    This isolates *driver tardiness*: if the driver reached the FBO after the
    passenger was predicted ready, the VIP was kept waiting. Clamped at zero;
    ``None`` when either timestamp is missing.
    """
    arrival = _parse_dt(driver_geofence_arrival_time)
    ready = _parse_dt(predicted_ready_time)
    if arrival is None or ready is None:
        return None
    return max(0, int(round((arrival - ready).total_seconds() / 60.0)))


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
        return EVENT_DRIVER_ARRIVED
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
    target_fbo: Optional[str] = None
    aircraft_category: Optional[str] = None
    predicted_touchdown_time: Optional[datetime] = None
    actual_touchdown_time: Optional[datetime] = None
    predicted_ready_time: Optional[datetime] = None
    actual_ready_time: Optional[datetime] = None
    driver_geofence_arrival_time: Optional[datetime] = None
    actual_passenger_met_time: Optional[datetime] = None
    driver_wait_minutes: Optional[float] = None
    late_pickup_minutes: Optional[float] = None
    late_pickup_boolean: Optional[bool] = None


def _apply_completion(target: dict, event_type: str, ledger: dict) -> None:
    """On the ``passenger_met`` event, derive the two ground-truth metrics.

    Mutates ``target`` (the row being inserted/updated) in place.
    """
    if event_type != EVENT_PASSENGER_MET:
        return
    arrival = ledger.get("driver_geofence_arrival_time")
    met = ledger.get("actual_passenger_met_time")
    predicted_ready = ledger.get("predicted_ready_time")
    late = calculate_late_pickup_minutes(arrival, predicted_ready)
    target["status"] = "completed"
    target["driver_wait_minutes"] = calculate_driver_wait_minutes(arrival, met)
    target["late_pickup_minutes"] = late
    target["actual_ready_time"] = met
    target["late_pickup_boolean"] = (late > 0) if late is not None else None


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
    led = ledger or {}
    predicted_obt = led.get("predicted_obt") or flight.get("predicted_on_block_time")

    return {
        "flight_id": flight_id,
        "flight_number": flight.get("flight_number") or led.get("flight_number"),
        "passenger_name": flight.get("passenger_name") or led.get("passenger_name"),
        "fbo": flight.get("fbo") or led.get("target_fbo") or led.get("fbo"),
        "aircraft_category": flight.get("aircraft_category") or led.get("aircraft_category"),
        "predicted_on_block_time": predicted_obt,
        "predicted_touchdown_time": flight.get("predicted_touchdown_time") or led.get("predicted_touchdown_time"),
        "predicted_passenger_ready_time": (
            flight.get("predicted_passenger_ready_time") or led.get("predicted_ready_time")
        ),
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
        # Open a new trip, snapshotting the flight's predictions as ground-truth
        # baselines. actual_touchdown_time is auto-captured (simulated here from
        # the predicted touchdown — a real deployment reads the ADS-B landing).
        predicted_obt = flight.get("predicted_on_block_time")
        predicted_td = flight.get("predicted_touchdown_time")
        predicted_ready = flight.get("predicted_passenger_ready_time") or predicted_obt
        row: dict = {
            "flight_id": flight_id,
            "flight_number": flight.get("flight_number"),
            "passenger_name": flight.get("passenger_name"),
            "fbo": flight.get("fbo"),
            "target_fbo": flight.get("fbo"),
            "airport_code": flight.get("airport_code"),
            "aircraft_category": flight.get("aircraft_category"),
            "predicted_obt": predicted_obt,
            "predicted_touchdown_time": predicted_td,
            "actual_touchdown_time": predicted_td,
            "predicted_ready_time": predicted_ready,
            column: ts_iso,
            "status": "in_progress",
        }
        _apply_completion(row, event_type, ledger=row)
        resp = sb.table(LEDGER_TABLE).insert(row).execute()
        saved = (resp.data or [row])[0]
        logger.info("Opened operational ledger for %s via %s", flight_id, event_type)
        return {"status": "ok", "ledger": saved, "next_event": _next_event(saved)}

    update: dict = {column: ts_iso, "updated_at": datetime.now(timezone.utc).isoformat()}
    _apply_completion(update, event_type, ledger={**ledger, column: ts_iso})
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
        .order("actual_passenger_met_time", desc=True)
        .limit(max(1, min(limit, 500)))
    )
    if fbo:
        query = query.eq("target_fbo", fbo)
    resp = query.execute()
    rows = resp.data or []
    waits = [r["driver_wait_minutes"] for r in rows if r.get("driver_wait_minutes") is not None]
    avg_wait = round(sum(waits) / len(waits), 1) if waits else None
    late = [r["late_pickup_minutes"] for r in rows if r.get("late_pickup_minutes") is not None]
    avg_late = round(sum(late) / len(late), 1) if late else None
    return {
        "count": len(rows),
        "average_driver_wait_minutes": avg_wait,
        "average_late_pickup_minutes": avg_late,
        "trips": rows,
    }
