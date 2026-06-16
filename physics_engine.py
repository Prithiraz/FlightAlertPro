"""Modular probabilistic dispatch pipeline.

AeroLogix's "final architectural form" breaks a dispatch decision into a chain of
small, independently-improvable predictors:

    telemetry --> predict_touchdown --> predict_on_block --> predict_passenger_ready
                                                                     |
                                                                     v
                                                        calculate_dispatch_window

Each stage returns both a point estimate and an uncertainty (minutes, 1-sigma)
that compounds down the chain. The final stage turns that distribution into an
*acceptable dispatch window* by minimising the expected cost of a driver idling
versus a late VIP — never a single "exact" minute.

The predictors here are deliberately simple placeholders: they expose the right
interfaces so FBO-specific micro-models can be dropped in later without changing
callers.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, Optional

from weather_service import (
    DEFAULT_TAXI_TIME_MIN,
    DEFAULT_DRIVE_TIME_MIN,
    DEFAULT_WAIT_COST_PER_MIN,
    DEFAULT_LATE_COST_PER_MIN,
)

# Minutes from on-block to the passenger being curbside, by aircraft category.
# Larger cabins deplane more slowly and with more variance.
CATEGORY_READY_OFFSET_MIN: Dict[str, float] = {
    "light": 4.0,
    "midsize": 5.0,
    "super-midsize": 6.0,
    "heavy": 9.0,
    "ultra-long-range": 11.0,
    "airliner": 14.0,
}
DEFAULT_READY_OFFSET_MIN: float = 6.0

# Per-stage 1-sigma process noise (minutes) added in quadrature down the chain.
_TAXI_SIGMA_MIN: float = 2.0
CATEGORY_READY_SIGMA_MIN: Dict[str, float] = {
    "light": 2.0,
    "midsize": 2.5,
    "super-midsize": 3.0,
    "heavy": 4.0,
    "ultra-long-range": 5.0,
    "airliner": 6.0,
}
DEFAULT_READY_SIGMA_MIN: float = 3.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _quad(a: float, b: float) -> float:
    """Combine two independent 1-sigma errors in quadrature."""
    return math.sqrt(max(0.0, a) ** 2 + max(0.0, b) ** 2)


def _category_key(aircraft_category: Optional[str]) -> str:
    return (aircraft_category or "").strip().lower()


# ---------------------------------------------------------------------------
# Stage 1 — touchdown
# ---------------------------------------------------------------------------
def predict_touchdown(telemetry: Dict) -> Dict:
    """Predict the absolute touchdown time from a live telemetry sample.

    Placeholder model: projects the planning-horizon ETA forward from the sample
    time. Future work swaps this for an approach/runway-aware model.

    Parameters
    ----------
    telemetry : dict
        Expects ``logistics_eta_min`` (minutes to touchdown) and optionally
        ``now`` (datetime), ``predicted_touchdown_time`` (datetime, used
        verbatim if given) and ``confidence_interval_min`` (uncertainty).
    """
    now = telemetry.get("now") or datetime.utcnow()
    touchdown = telemetry.get("predicted_touchdown_time")
    if isinstance(touchdown, datetime):
        td = touchdown
    else:
        eta_min = float(telemetry.get("logistics_eta_min") or 0.0)
        td = now + timedelta(minutes=eta_min)
    td = td.replace(second=0, microsecond=0)
    uncertainty = float(telemetry.get("confidence_interval_min") or 0.0)
    return {"touchdown_time": td, "uncertainty_minutes": max(0.0, uncertainty)}


# ---------------------------------------------------------------------------
# Stage 2 — on-block
# ---------------------------------------------------------------------------
def predict_on_block(touchdown: Dict, fbo_data: Optional[Dict] = None) -> Dict:
    """Predict gate/stand on-block time from touchdown + FBO taxi profile.

    ``touchdown`` is the dict returned by :func:`predict_touchdown`. ``fbo_data``
    may carry a route-specific ``taxi_time_min``; otherwise the operator default
    applies.
    """
    fbo_data = fbo_data or {}
    taxi_min = fbo_data.get("taxi_time_min")
    taxi_min = float(taxi_min) if taxi_min is not None else float(DEFAULT_TAXI_TIME_MIN)

    td_time = touchdown["touchdown_time"]
    on_block = (td_time + timedelta(minutes=taxi_min)).replace(second=0, microsecond=0)
    uncertainty = _quad(touchdown.get("uncertainty_minutes", 0.0), _TAXI_SIGMA_MIN)
    return {"on_block_time": on_block, "uncertainty_minutes": uncertainty}


# ---------------------------------------------------------------------------
# Stage 3 — passenger ready
# ---------------------------------------------------------------------------
def predict_passenger_ready(on_block: Dict, aircraft_category: Optional[str] = None) -> Dict:
    """Predict when the passenger is curbside, given the aircraft category.

    Heavier cabins deplane more slowly and with more variance; the offset and
    process noise are looked up by category.
    """
    key = _category_key(aircraft_category)
    offset = CATEGORY_READY_OFFSET_MIN.get(key, DEFAULT_READY_OFFSET_MIN)
    cat_sigma = CATEGORY_READY_SIGMA_MIN.get(key, DEFAULT_READY_SIGMA_MIN)

    ob_time = on_block["on_block_time"]
    ready = (ob_time + timedelta(minutes=offset)).replace(second=0, microsecond=0)
    uncertainty = _quad(on_block.get("uncertainty_minutes", 0.0), cat_sigma)
    return {"ready_time": ready, "uncertainty_minutes": uncertainty, "aircraft_category": aircraft_category}


# ---------------------------------------------------------------------------
# Expected-cost dispatch window
# ---------------------------------------------------------------------------
def _expected_cost(presence_offset_min: float, sigma: float, wait_cost: float, late_cost: float) -> float:
    """Expected cost (per-trip) of staging the driver ``presence_offset_min``
    minutes relative to the median passenger-ready time.

    With ready time R ~ N(0, sigma) (offsets measured from the median):
        G(T) = E[(T - R)+] = T*Phi(T/sigma) + sigma*phi(T/sigma)
        cost = wait*(E[(R - T)+]) + late*(E[(T - R)+])
             = wait*(G - T) + late*G        (since E[(R-T)+] = G - T when mu=0)
    """
    t = presence_offset_min
    if sigma <= 0:
        # Degenerate: driver should arrive exactly at the (certain) ready time.
        late = late_cost * max(0.0, t)
        wait = wait_cost * max(0.0, -t)
        return late + wait
    z = t / sigma
    g = t * _norm_cdf(z) + sigma * _norm_pdf(z)
    return wait_cost * (g - t) + late_cost * g


def _expected_driver_wait(presence_offset_min: float, sigma: float) -> float:
    """Expected minutes the driver idles: E[(R - T)+] with R ~ N(0, sigma)."""
    t = presence_offset_min
    if sigma <= 0:
        return max(0.0, -t)
    z = t / sigma
    g = t * _norm_cdf(z) + sigma * _norm_pdf(z)
    return g - t


def _confidence_label(sigma: float) -> str:
    if sigma <= 6.0:
        return "High"
    if sigma <= 14.0:
        return "Moderate"
    return "Low"


def calculate_dispatch_window(
    predicted_ready_time: datetime,
    uncertainty_minutes: float,
    wait_cost_per_min: float = DEFAULT_WAIT_COST_PER_MIN,
    late_cost_per_min: float = DEFAULT_LATE_COST_PER_MIN,
    drive_time_min: float = DEFAULT_DRIVE_TIME_MIN,
    cost_tolerance: float = 0.10,
) -> Dict:
    """Return an *acceptable* dispatch window rather than a single minute.

    The driver should be staged at the pickup at the offset ``T*`` (relative to
    the median ready time) that minimises expected cost. The window spans every
    staging time whose expected cost is within ``cost_tolerance`` (fraction) of
    that minimum; subtracting the drive time converts staging times into
    leave-by (dispatch) clock times.

    Returns ``window_start`` / ``window_end`` (dispatch datetimes), the midpoint
    ``recommended_dispatch_time``, ``expected_driver_wait_minutes`` and a
    coarse ``recommendation_confidence`` label.
    """
    if not isinstance(predicted_ready_time, datetime):
        raise TypeError("predicted_ready_time must be a datetime instance")

    sigma = max(0.0, float(uncertainty_minutes))
    wait = max(0.0, float(wait_cost_per_min))
    late = max(0.0, float(late_cost_per_min))
    drive = max(0.0, float(drive_time_min))

    # Scan presence offsets (minutes from median ready time) for the minimum.
    span = max(8.0, 4.0 * sigma)
    step = 0.25
    n = int((2 * span) / step) + 1
    offsets = [(-span + i * step) for i in range(n)]
    costs = [(o, _expected_cost(o, sigma, wait, late)) for o in offsets]
    best_offset, best_cost = min(costs, key=lambda oc: oc[1])

    budget = best_cost * (1.0 + cost_tolerance)
    accepted = [o for (o, c) in costs if c <= budget] or [best_offset]
    low_offset, high_offset = min(accepted), max(accepted)

    def _presence(offset: float) -> datetime:
        return (predicted_ready_time + timedelta(minutes=offset)).replace(second=0, microsecond=0)

    def _dispatch(offset: float) -> datetime:
        return (predicted_ready_time + timedelta(minutes=offset - drive)).replace(second=0, microsecond=0)

    # Earlier presence => earlier (smaller) dispatch time, so map low->start.
    window_start = _dispatch(low_offset)
    window_end = _dispatch(high_offset)
    recommended = _dispatch(best_offset)

    expected_wait = _expected_driver_wait(best_offset, sigma)

    return {
        "window_start": window_start,
        "window_end": window_end,
        "recommended_dispatch_time": recommended,
        "recommended_presence_time": _presence(best_offset),
        "expected_driver_wait_minutes": int(round(max(0.0, expected_wait))),
        "recommendation_confidence": _confidence_label(sigma),
        "uncertainty_minutes": int(round(sigma)),
        "buffer_minutes": int(round(-best_offset)),
    }
