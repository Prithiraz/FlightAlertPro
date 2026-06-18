"""
physics_engine.py — Modular Probabilistic Dispatch-Decision Pipeline for AeroLogix.

Each function in the chain takes the output of the previous stage and returns
a dict with a point estimate plus a standard deviation (sigma) representing
prediction uncertainty.
"""
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from weather_service import calculate_adsb_aerodynamics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1: Touchdown Prediction
# ---------------------------------------------------------------------------

def predict_touchdown(telemetry: Dict) -> Dict:
    """
    Predict aircraft touchdown time from live ADS-B telemetry.

    Parameters
    ----------
    telemetry : dict
        Keys: altitude_ft, ground_speed_kt, heading_deg, lat, lon,
              destination_lat, destination_lon (optional), scheduled_arrival (ISO str, optional)

    Returns
    -------
    dict
        predicted_touchdown_utc : datetime
        sigma_minutes : float  — 1-sigma uncertainty in minutes
        method : str           — 'adsb_kinematic' | 'schedule_fallback'
        aerodynamics : dict | None — wind/TAS context from weather_service
    """
    altitude_ft = float(telemetry.get("altitude_ft", 0))
    ground_speed_kt = float(telemetry.get("ground_speed_kt", 1))
    scheduled_arrival_str = telemetry.get("scheduled_arrival")

    # Pull aerodynamic context (TAS, wind component, density altitude) so the
    # descent estimate reflects the current wind environment, not just altitude.
    aerodynamics = None
    descent_rate_fpm = 1500.0
    try:
        aerodynamics = calculate_adsb_aerodynamics(
            altitude_ft=altitude_ft,
            ground_speed_kt=ground_speed_kt,
            heading_deg=float(telemetry.get("heading_deg", 0)),
        )
        # A strong tailwind shortens the approach (faster ground track), a
        # headwind lengthens it. Nudge the effective descent rate accordingly.
        descent_rate_fpm += aerodynamics["wind_component_kt"] * 5.0
        descent_rate_fpm = max(800.0, descent_rate_fpm)
    except (ValueError, KeyError, TypeError):
        logger.debug("aerodynamic enrichment unavailable; using nominal descent rate")

    # Kinematic estimate: time to descend from current altitude
    time_to_ground_min = altitude_ft / descent_rate_fpm if altitude_ft > 0 else 0.0

    # Uncertainty grows with altitude (further out = less certain)
    sigma_minutes = max(1.0, altitude_ft / 10000.0 * 3.0)

    now = datetime.utcnow()
    predicted_touchdown_utc = now + timedelta(minutes=time_to_ground_min)

    # If aircraft is on the ground or nearly so, fall back to schedule
    if altitude_ft < 500 and scheduled_arrival_str:
        try:
            predicted_touchdown_utc = datetime.fromisoformat(scheduled_arrival_str.replace("Z", "+00:00"))
            sigma_minutes = 2.0
            return {
                "predicted_touchdown_utc": predicted_touchdown_utc,
                "sigma_minutes": sigma_minutes,
                "method": "schedule_fallback",
                "aerodynamics": aerodynamics,
            }
        except (ValueError, TypeError):
            pass

    return {
        "predicted_touchdown_utc": predicted_touchdown_utc,
        "sigma_minutes": sigma_minutes,
        "method": "adsb_kinematic",
        "aerodynamics": aerodynamics,
    }


# ---------------------------------------------------------------------------
# Stage 2: On-Block Prediction
# ---------------------------------------------------------------------------

# Typical taxi-in times by FBO/airport category (minutes)
_TAXI_IN_DEFAULTS = {
    "large_hub": 12.0,
    "medium_hub": 8.0,
    "small_hub": 5.0,
    "default": 8.0,
}

def predict_on_block(touchdown: Dict, fbo_data: Optional[Dict] = None) -> Dict:
    """
    Predict when the aircraft will be on-block (chocks in) at the FBO.

    Parameters
    ----------
    touchdown : dict
        Output of predict_touchdown().
    fbo_data : dict, optional
        Keys: airport_category ('large_hub'|'medium_hub'|'small_hub'),
              historical_taxi_mean_min (float), historical_taxi_sigma_min (float)

    Returns
    -------
    dict
        predicted_on_block_utc : datetime
        sigma_minutes : float
        taxi_mean_min : float
    """
    fbo_data = fbo_data or {}
    airport_category = fbo_data.get("airport_category", "default")
    taxi_mean = float(
        fbo_data.get("historical_taxi_mean_min")
        or _TAXI_IN_DEFAULTS.get(airport_category, _TAXI_IN_DEFAULTS["default"])
    )
    taxi_sigma = float(fbo_data.get("historical_taxi_sigma_min") or 2.5)

    # Propagate uncertainty: combined sigma = sqrt(touchdown_sigma^2 + taxi_sigma^2)
    combined_sigma = math.sqrt(touchdown["sigma_minutes"] ** 2 + taxi_sigma ** 2)

    predicted_on_block_utc = touchdown["predicted_touchdown_utc"] + timedelta(minutes=taxi_mean)

    return {
        "predicted_on_block_utc": predicted_on_block_utc,
        "sigma_minutes": round(combined_sigma, 2),
        "taxi_mean_min": taxi_mean,
    }


# ---------------------------------------------------------------------------
# Stage 3: Passenger Ready Prediction
# ---------------------------------------------------------------------------

# Deboarding + customs + FBO transit times by aircraft category (minutes)
_DEPLANE_DEFAULTS = {
    "wide_body": {"mean": 35.0, "sigma": 8.0},
    "narrow_body": {"mean": 20.0, "sigma": 5.0},
    "regional": {"mean": 12.0, "sigma": 3.0},
    "private": {"mean": 8.0, "sigma": 2.0},
    "default": {"mean": 20.0, "sigma": 5.0},
}

def predict_passenger_ready(on_block: Dict, aircraft_category: str = "default") -> Dict:
    """
    Predict when the passenger will be ready for pickup at the FBO curb.

    Parameters
    ----------
    on_block : dict
        Output of predict_on_block().
    aircraft_category : str
        One of 'wide_body', 'narrow_body', 'regional', 'private'.

    Returns
    -------
    dict
        predicted_passenger_ready_utc : datetime
        sigma_minutes : float
        deplane_mean_min : float
    """
    params = _DEPLANE_DEFAULTS.get(aircraft_category, _DEPLANE_DEFAULTS["default"])
    deplane_mean = params["mean"]
    deplane_sigma = params["sigma"]

    combined_sigma = math.sqrt(on_block["sigma_minutes"] ** 2 + deplane_sigma ** 2)

    predicted_passenger_ready_utc = on_block["predicted_on_block_utc"] + timedelta(minutes=deplane_mean)

    return {
        "predicted_passenger_ready_utc": predicted_passenger_ready_utc,
        "sigma_minutes": round(combined_sigma, 2),
        "deplane_mean_min": deplane_mean,
    }


# ---------------------------------------------------------------------------
# Stage 4: Dispatch Window (Expected Cost Formula)
# ---------------------------------------------------------------------------

# Cost asymmetry: being late is worse than making the driver wait.
# C_late / C_wait ratio drives the optimal dispatch offset.
_COST_RATIO = 2.5   # late is 2.5x more costly than waiting
_DRIVER_TRANSIT_MEAN_MIN = 15.0   # assumed mean drive time to FBO
_DRIVER_TRANSIT_SIGMA_MIN = 4.0   # uncertainty in driver transit

def calculate_dispatch_window(
    passenger_ready: Dict,
    driver_transit_mean_min: float = _DRIVER_TRANSIT_MEAN_MIN,
    driver_transit_sigma_min: float = _DRIVER_TRANSIT_SIGMA_MIN,
) -> Dict:
    """
    Apply the expected-cost formula to return a recommended dispatch window
    rather than a single point estimate.

    The optimal dispatch time minimises:
        E[Cost] = C_wait * P(driver arrives early) + C_late * P(driver arrives late)

    For a Gaussian passenger-ready distribution, the optimal dispatch offset
    from the mean is: offset = sigma * Phi^{-1}(C_late / (C_late + C_wait))
    which simplifies to: offset = sigma * Phi^{-1}(C_ratio / (C_ratio + 1))

    The window is [optimal - 0.5*window_width, optimal + 0.5*window_width]
    where window_width = 1-sigma of the combined uncertainty.

    Parameters
    ----------
    passenger_ready : dict
        Output of predict_passenger_ready().
    driver_transit_mean_min : float
        Expected drive time from driver's current location to FBO.
    driver_transit_sigma_min : float
        Uncertainty in driver transit time.

    Returns
    -------
    dict
        dispatch_window_start : datetime
        dispatch_window_end : datetime
        dispatch_window_str : str   e.g. "18:04–18:10"
        expected_driver_wait_min : float
        recommendation_confidence : str  'High' | 'Moderate' | 'Low'
        optimal_dispatch_utc : datetime
    """
    passenger_ready_utc = passenger_ready["predicted_passenger_ready_utc"]
    total_sigma = math.sqrt(
        passenger_ready["sigma_minutes"] ** 2 + driver_transit_sigma_min ** 2
    )

    # Phi^{-1}(C_ratio / (C_ratio + 1)) ≈ 0.674 for C_ratio=2.5 (68th percentile)
    # Using a simple lookup for common ratios to avoid scipy dependency.
    # For C_ratio=2.5: Phi^{-1}(2.5/3.5) = Phi^{-1}(0.714) ≈ 0.57
    cost_percentile = _COST_RATIO / (_COST_RATIO + 1.0)
    # Approximate inverse normal CDF via rational approximation
    z = _approx_inv_normal(cost_percentile)
    optimal_offset_min = total_sigma * z

    # Optimal time for passenger to be met = passenger_ready - driver_transit + offset
    optimal_dispatch_utc = (
        passenger_ready_utc
        - timedelta(minutes=driver_transit_mean_min)
        + timedelta(minutes=optimal_offset_min)
    )

    # Window = ±0.5 * total_sigma around optimal
    half_window = max(3.0, total_sigma * 0.5)
    window_start = optimal_dispatch_utc - timedelta(minutes=half_window)
    window_end = optimal_dispatch_utc + timedelta(minutes=half_window)

    # Expected driver wait = how long driver will wait if dispatched at window_start
    expected_driver_wait_min = max(0.0, driver_transit_mean_min - optimal_offset_min + half_window)

    # Confidence based on total sigma
    if total_sigma <= 5.0:
        confidence = "High"
    elif total_sigma <= 10.0:
        confidence = "Moderate"
    else:
        confidence = "Low"

    fmt = "%H:%M"
    window_str = f"{window_start.strftime(fmt)}–{window_end.strftime(fmt)}"

    return {
        "dispatch_window_start": window_start,
        "dispatch_window_end": window_end,
        "dispatch_window_str": window_str,
        "expected_driver_wait_min": round(expected_driver_wait_min, 1),
        "recommendation_confidence": confidence,
        "optimal_dispatch_utc": optimal_dispatch_utc,
        "total_sigma_minutes": round(total_sigma, 2),
    }


def _approx_inv_normal(p: float) -> float:
    """Rational approximation of the inverse normal CDF (Abramowitz & Stegun 26.2.17)."""
    if p <= 0.0:
        return -6.0
    if p >= 1.0:
        return 6.0
    if p < 0.5:
        return -_approx_inv_normal(1.0 - p)
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t ** 2) / (1.0 + d1 * t + d2 * t ** 2 + d3 * t ** 3)


# ---------------------------------------------------------------------------
# High-level convenience runner
# ---------------------------------------------------------------------------

def run_dispatch_pipeline(
    telemetry: Dict,
    fbo_data: Optional[Dict] = None,
    aircraft_category: str = "narrow_body",
    driver_transit_mean_min: float = _DRIVER_TRANSIT_MEAN_MIN,
    driver_transit_sigma_min: float = _DRIVER_TRANSIT_SIGMA_MIN,
) -> Dict:
    """Run the full 4-stage pipeline and return a combined result dict."""
    td = predict_touchdown(telemetry)
    ob = predict_on_block(td, fbo_data)
    pr = predict_passenger_ready(ob, aircraft_category)
    dw = calculate_dispatch_window(pr, driver_transit_mean_min, driver_transit_sigma_min)
    return {
        "touchdown": td,
        "on_block": ob,
        "passenger_ready": pr,
        "dispatch_window": dw,
    }
