import math
from physics_engine import calculate_arrival_metrics

def test_nominal_approach():
    # Test a standard approach: 4000 ft, 150 knots, 10 nm out
    result = calculate_arrival_metrics(4000, 150.0, 10.0)
    assert result is not None
    assert result["performance_advisory"] == "NOMINAL"
    # Base time: 10nm / (150/60) = 4 mins. Alt < 5000 penalty = 2 mins. Total = 6 mins.
    assert result["logistics_eta_min"] == 6.0

def test_high_energy_advisory():
    # Test fast and low: 300 knots at 8000 ft
    result = calculate_arrival_metrics(8000, 300.0, 20.0)
    assert result["performance_advisory"] == "HIGH_ENERGY_APPROACH"

def test_confidence_interval_widens_with_altitude():
    # Low altitude (3000 ft)
    low_result = calculate_arrival_metrics(3000, 200.0, 15.0)
    # High altitude (35000 ft)
    high_result = calculate_arrival_metrics(35000, 450.0, 100.0)
    
    # The confidence interval (uncertainty) MUST be higher for the high-altitude flight
    assert high_result["confidence_interval_min"] > low_result["confidence_interval_min"]

def test_invalid_inputs():
    # Negative altitude or dangerously low speeds should return None
    assert calculate_arrival_metrics(-100, 200, 10) is None
    assert calculate_arrival_metrics(5000, 10, 10) is None
