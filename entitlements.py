"""Plan entitlements for FlightAlertPro."""

PLANS: dict = {
    "free": {
        "max_active_alerts": 3,
        "max_searches_per_day": 20,
        "max_notifications_per_day": 5,
        "priority": False,
    },
    "pro": {
        "max_active_alerts": 20,
        "max_searches_per_day": 200,
        "max_notifications_per_day": 50,
        "priority": True,
    },
    "elite": {
        "max_active_alerts": 50,
        "max_searches_per_day": 500,
        "max_notifications_per_day": 100,
        "priority": True,
    },
    "business": {
        "max_active_alerts": 200,
        "max_searches_per_day": 2000,
        "max_notifications_per_day": 500,
        "priority": True,
    },
}


def get_plan_limits(plan: str) -> dict:
    """Return entitlement limits for the given plan name (defaults to 'free')."""
    return PLANS.get(plan.lower(), PLANS["free"])
