"""Unit tests for the modular probabilistic dispatch pipeline."""
from datetime import datetime, timedelta

import physics_engine as pe


NOW = datetime(2026, 6, 15, 17, 0)


# ---------------------------------------------------------------------------
# Modular chain
# ---------------------------------------------------------------------------
def test_predict_touchdown_projects_eta_forward():
    td = pe.predict_touchdown({"now": NOW, "logistics_eta_min": 40, "confidence_interval_min": 12})
    assert td["touchdown_time"] == NOW + timedelta(minutes=40)
    assert td["uncertainty_minutes"] == 12


def test_predict_touchdown_uses_explicit_time_when_given():
    fixed = datetime(2026, 6, 15, 18, 30)
    td = pe.predict_touchdown({"predicted_touchdown_time": fixed, "logistics_eta_min": 999})
    assert td["touchdown_time"] == fixed


def test_predict_on_block_adds_taxi_and_compounds_uncertainty():
    td = {"touchdown_time": NOW, "uncertainty_minutes": 6.0}
    ob = pe.predict_on_block(td, {"taxi_time_min": 10})
    assert ob["on_block_time"] == NOW + timedelta(minutes=10)
    # Uncertainty grows (quadrature with taxi sigma).
    assert ob["uncertainty_minutes"] > 6.0


def test_predict_passenger_ready_scales_with_aircraft_category():
    ob = {"on_block_time": NOW, "uncertainty_minutes": 5.0}
    light = pe.predict_passenger_ready(ob, "light")
    heavy = pe.predict_passenger_ready(ob, "heavy")
    # Heavier cabins deplane later and with more uncertainty.
    assert heavy["ready_time"] > light["ready_time"]
    assert heavy["uncertainty_minutes"] > light["uncertainty_minutes"]


def test_predict_passenger_ready_unknown_category_uses_default():
    ob = {"on_block_time": NOW, "uncertainty_minutes": 0.0}
    rd = pe.predict_passenger_ready(ob, "spaceship")
    assert rd["ready_time"] == NOW + timedelta(minutes=pe.DEFAULT_READY_OFFSET_MIN)


# ---------------------------------------------------------------------------
# Dispatch window
# ---------------------------------------------------------------------------
def test_dispatch_window_returns_a_range_not_a_point():
    ready = datetime(2026, 6, 15, 18, 0)
    w = pe.calculate_dispatch_window(ready, 10.0, 1.0, 5.0, 35.0)
    assert w["window_end"] > w["window_start"]
    assert w["window_start"] <= w["recommended_dispatch_time"] <= w["window_end"]


def test_dispatch_window_zero_uncertainty_is_tight():
    ready = datetime(2026, 6, 15, 18, 0)
    w = pe.calculate_dispatch_window(ready, 0.0, 1.0, 5.0, 35.0)
    # No uncertainty => the window collapses to (essentially) a single minute.
    assert (w["window_end"] - w["window_start"]) <= timedelta(minutes=1)
    assert w["recommendation_confidence"] == "High"


def test_dispatch_window_high_late_penalty_shifts_earlier():
    ready = datetime(2026, 6, 15, 18, 0)
    balanced = pe.calculate_dispatch_window(ready, 12.0, 1.0, 1.0, 35.0)
    vip = pe.calculate_dispatch_window(ready, 12.0, 1.0, 10.0, 35.0)
    # A heavy VIP late-penalty pulls the recommended dispatch earlier.
    assert vip["recommended_dispatch_time"] < balanced["recommended_dispatch_time"]
    assert vip["expected_driver_wait_minutes"] >= balanced["expected_driver_wait_minutes"]


def test_dispatch_window_higher_uncertainty_widens_window():
    ready = datetime(2026, 6, 15, 18, 0)
    tight = pe.calculate_dispatch_window(ready, 4.0, 1.0, 5.0, 35.0)
    wide = pe.calculate_dispatch_window(ready, 20.0, 1.0, 5.0, 35.0)
    tight_width = tight["window_end"] - tight["window_start"]
    wide_width = wide["window_end"] - wide["window_start"]
    assert wide_width > tight_width
    assert wide["recommendation_confidence"] == "Low"


def test_dispatch_window_subtracts_drive_time():
    ready = datetime(2026, 6, 15, 18, 0)
    near = pe.calculate_dispatch_window(ready, 8.0, 1.0, 5.0, 10.0)
    far = pe.calculate_dispatch_window(ready, 8.0, 1.0, 5.0, 60.0)
    # A longer drive means leaving earlier.
    assert far["recommended_dispatch_time"] < near["recommended_dispatch_time"]
