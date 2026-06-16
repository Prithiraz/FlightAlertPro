"""Unit tests for the driver-dispatch feedback loop."""
from datetime import datetime, timezone

from operational_ledger import (
    EVENT_SEQUENCE,
    EVENT_TIMESTAMP_COLUMN,
    calculate_driver_wait_minutes,
    _next_event,
)


def test_wait_minutes_positive_when_collected_after_obt():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00Z", "2026-06-15T10:12:00Z"
        )
        == 12
    )


def test_wait_minutes_negative_when_collected_before_obt():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00+00:00", "2026-06-15T09:55:00+00:00"
        )
        == -5
    )


def test_wait_minutes_rounds_to_nearest_minute():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00Z", "2026-06-15T10:00:40Z"
        )
        == 1
    )


def test_wait_minutes_accepts_datetime_objects():
    obt = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
    collected = datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc)
    assert calculate_driver_wait_minutes(obt, collected) == 30


def test_wait_minutes_handles_naive_datetimes_as_utc():
    assert (
        calculate_driver_wait_minutes(
            "2026-06-15T10:00:00", "2026-06-15T10:20:00"
        )
        == 20
    )


def test_wait_minutes_none_on_missing_or_bad_input():
    assert calculate_driver_wait_minutes(None, "2026-06-15T10:00:00Z") is None
    assert calculate_driver_wait_minutes("2026-06-15T10:00:00Z", None) is None
    assert calculate_driver_wait_minutes("not-a-date", "2026-06-15T10:00:00Z") is None


def test_next_event_progression():
    assert _next_event(None) == EVENT_SEQUENCE[0]

    ledger = {col: None for col in EVENT_TIMESTAMP_COLUMN.values()}
    assert _next_event(ledger) == "arrived_at_fbo"

    ledger["arrived_at_fbo_at"] = "2026-06-15T10:00:00Z"
    assert _next_event(ledger) == "passenger_exited"

    ledger["passenger_exited_at"] = "2026-06-15T10:05:00Z"
    assert _next_event(ledger) == "passenger_collected"

    ledger["passenger_collected_at"] = "2026-06-15T10:10:00Z"
    assert _next_event(ledger) is None
