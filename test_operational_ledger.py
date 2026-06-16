"""Unit tests for the driver-dispatch feedback loop."""
from datetime import datetime, timezone

from operational_ledger import (
    EVENT_SEQUENCE,
    EVENT_TIMESTAMP_COLUMN,
    OperationalLedger,
    calculate_driver_wait_minutes,
    calculate_late_pickup_minutes,
    _next_event,
)


# ---------------------------------------------------------------------------
# driver_wait_minutes = max(0, passenger_met - driver_arrival)
# ---------------------------------------------------------------------------
def test_driver_wait_positive_when_passenger_met_after_arrival():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00Z", "2026-06-15T10:12:00Z"
        )
        == 12
    )


def test_driver_wait_clamped_to_zero_when_met_before_arrival():
    # Driver arrived after the passenger was already out — driver did not wait.
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:10:00+00:00", "2026-06-15T10:00:00+00:00"
        )
        == 0
    )


def test_driver_wait_rounds_to_nearest_minute():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00Z", "2026-06-15T10:00:40Z"
        )
        == 1
    )


def test_driver_wait_accepts_datetime_objects():
    arrival = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
    met = datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc)
    assert calculate_driver_wait_minutes(arrival, met) == 30


def test_driver_wait_none_on_missing_or_bad_input():
    assert calculate_driver_wait_minutes(None, "2026-06-15T10:00:00Z") is None
    assert calculate_driver_wait_minutes("2026-06-15T10:00:00Z", None) is None
    assert calculate_driver_wait_minutes("not-a-date", "2026-06-15T10:00:00Z") is None


# ---------------------------------------------------------------------------
# late_pickup_minutes = max(0, driver_arrival - predicted_ready)
# ---------------------------------------------------------------------------
def test_late_pickup_minutes_positive_when_driver_arrives_after_ready():
    # Driver reached the FBO 10 min after the passenger was predicted ready.
    assert (
        calculate_late_pickup_minutes(
            "2026-06-15T10:10:00Z", "2026-06-15T10:00:00Z"
        )
        == 10
    )


def test_late_pickup_minutes_zero_when_driver_arrives_before_ready():
    assert (
        calculate_late_pickup_minutes(
            "2026-06-15T09:50:00Z", "2026-06-15T10:00:00Z"
        )
        == 0
    )


def test_late_pickup_minutes_none_when_timestamp_missing():
    assert calculate_late_pickup_minutes(None, "2026-06-15T10:00:00Z") is None
    assert calculate_late_pickup_minutes("2026-06-15T10:00:00Z", None) is None


# ---------------------------------------------------------------------------
# Two-event state machine
# ---------------------------------------------------------------------------
def test_next_event_progression():
    assert _next_event(None) == EVENT_SEQUENCE[0]

    ledger = {col: None for col in EVENT_TIMESTAMP_COLUMN.values()}
    assert _next_event(ledger) == "driver_arrived"

    ledger["driver_geofence_arrival_time"] = "2026-06-15T10:00:00Z"
    assert _next_event(ledger) == "passenger_met"

    ledger["actual_passenger_met_time"] = "2026-06-15T10:10:00Z"
    assert _next_event(ledger) is None


# ---------------------------------------------------------------------------
# Ground-truth model (the FBO 'data moat')
# ---------------------------------------------------------------------------
def test_operational_ledger_model_has_phase3_fields():
    record = OperationalLedger(
        flight_id="A1B2C3",
        airport_code="KTEB",
        target_fbo="Signature TEB",
        aircraft_category="heavy",
        predicted_touchdown_time=datetime(2026, 6, 15, 16, 40, tzinfo=timezone.utc),
        actual_touchdown_time=datetime(2026, 6, 15, 16, 42, tzinfo=timezone.utc),
        predicted_ready_time=datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc),
        driver_geofence_arrival_time=datetime(2026, 6, 15, 16, 58, tzinfo=timezone.utc),
        actual_passenger_met_time=datetime(2026, 6, 15, 17, 8, tzinfo=timezone.utc),
        driver_wait_minutes=10,
        late_pickup_minutes=0,
    )
    assert record.flight_id == "A1B2C3"
    assert record.target_fbo == "Signature TEB"
    assert record.aircraft_category == "heavy"
    assert record.driver_wait_minutes == 10
    assert record.late_pickup_minutes == 0


def test_operational_ledger_model_minimal():
    record = OperationalLedger(flight_id="ONLY_ID")
    assert record.flight_id == "ONLY_ID"
    assert record.airport_code is None
    assert record.target_fbo is None
    assert record.late_pickup_minutes is None
