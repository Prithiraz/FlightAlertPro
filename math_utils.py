"""Utility functions for points & miles valuation calculations."""

# Baseline cents-per-point used to convert cash prices to point costs.
# Industry standard "floor" value: 1.25 cpp.
BASELINE_CPP: float = 1.25


def calculate_points_cost(cash_price_usd: float) -> int:
    """Return the estimated points cost for a given cash price.

    Uses a standard baseline of 1.25 cents per point:
        Point Cost = (Cash Price in Cents) / 1.25

    Args:
        cash_price_usd: Ticket price in US dollars.

    Returns:
        Estimated points required, rounded to the nearest whole number.
        Returns 0 for non-positive prices.
    """
    if cash_price_usd <= 0:
        return 0
    cash_in_cents = cash_price_usd * 100
    return round(cash_in_cents / BASELINE_CPP)


def calculate_cpp(cash_price: float, point_cost: int) -> float:
    """Calculate the cents-per-point (CPP) value of a redemption.

    Args:
        cash_price: Ticket price in US dollars.
        point_cost: Number of points required for the ticket.

    Returns:
        CPP value rounded to two decimal places.
        Returns 0.0 when point_cost is zero or negative.
    """
    if point_cost <= 0:
        return 0.0
    cash_in_cents = cash_price * 100
    return round(cash_in_cents / point_cost, 2)
