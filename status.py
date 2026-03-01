"""
Public /api/status endpoint.

Returns a computed system-health summary suitable for display on a public
status page.  No secrets are included.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["status"])

# ---------------------------------------------------------------------------
# Public status endpoint
# ---------------------------------------------------------------------------

@router.get("/api/status")
async def get_status() -> JSONResponse:
    """
    Return a public status summary.

    Computes:
    - overall_status (operational | degraded | outage)
    - components array with individual health
    - last 10 non-resolved incidents
    - last_updated timestamp
    """
    components = _build_components()
    incidents = _recent_incidents()

    # Determine overall status
    statuses = [c["status"] for c in components]
    if any(s == "outage" for s in statuses):
        overall = "outage"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "operational"

    return JSONResponse(
        content={
            "overall_status": overall,
            "components": components,
            "incidents": incidents,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_supabase():
    from supabase import create_client
    from config import config
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def _build_components() -> List[Dict[str, Any]]:
    components = []

    # API component – check recent error rate from service_metrics
    components.append(_api_component())

    # Search providers
    components.append(_search_component())

    # Alerts worker
    components.append(_worker_component())

    # Notifications
    components.append(_notifications_component())

    # Stripe billing
    components.append(_stripe_component())

    return components


def _api_component() -> Dict[str, Any]:
    try:
        supabase = _get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        errors = (
            supabase.table("service_metrics")
            .select("value")
            .eq("metric_name", "api_error_count")
            .gte("ts", since)
            .execute()
        )
        requests = (
            supabase.table("service_metrics")
            .select("value")
            .eq("metric_name", "api_request_count")
            .gte("ts", since)
            .execute()
        )
        err_count = sum(r["value"] for r in (errors.data or []))
        req_count = sum(r["value"] for r in (requests.data or []))
        if req_count > 0 and (err_count / req_count) > 0.1:
            status = "degraded"
        else:
            status = "operational"
    except Exception:
        status = "unknown"

    return {"name": "API", "status": status}


def _search_component() -> Dict[str, Any]:
    try:
        from duffel_service import duffel_service
        from airscraper_service import airscraper_service
        from config import config

        any_enabled = duffel_service.enabled or (config.RAPIDAPI_KEY is not None) or airscraper_service.enabled
        if not any_enabled:
            return {"name": "Search", "status": "degraded", "detail": "No providers configured"}

        # Check recent uptime results
        supabase = _get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        rows = (
            supabase.table("uptime_checks")
            .select("ok")
            .eq("check_name", "api_systemcheck")
            .gte("ts", since)
            .execute()
        )
        checks = rows.data or []
        if checks:
            failures = sum(1 for c in checks if not c["ok"])
            if failures / len(checks) > 0.5:
                return {"name": "Search", "status": "outage"}
            if failures > 0:
                return {"name": "Search", "status": "degraded"}
        return {"name": "Search", "status": "operational"}
    except Exception:
        return {"name": "Search", "status": "unknown"}


def _worker_component() -> Dict[str, Any]:
    try:
        supabase = _get_supabase()
        rows = (
            supabase.table("service_metrics")
            .select("value,ts")
            .eq("metric_name", "worker_last_run_ts")
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        if not rows.data:
            return {"name": "Alerts Worker", "status": "unknown", "detail": "No run recorded"}

        last_val = rows.data[0]["value"]  # epoch seconds
        import time
        age_seconds = time.time() - last_val
        if age_seconds > 3600 * 2:  # more than 2 hours ago
            return {"name": "Alerts Worker", "status": "degraded", "detail": "Last run > 2h ago"}
        return {"name": "Alerts Worker", "status": "operational"}
    except Exception:
        return {"name": "Alerts Worker", "status": "unknown"}


def _notifications_component() -> Dict[str, Any]:
    try:
        supabase = _get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = (
            supabase.table("service_metrics")
            .select("metric_name,value")
            .in_("metric_name", ["notification_success_count", "notification_failure_count"])
            .gte("ts", since)
            .execute()
        )
        success = sum(r["value"] for r in (rows.data or []) if r["metric_name"] == "notification_success_count")
        failure = sum(r["value"] for r in (rows.data or []) if r["metric_name"] == "notification_failure_count")
        total = success + failure
        if total > 0 and (failure / total) > 0.2:
            return {"name": "Notifications", "status": "degraded"}
        return {"name": "Notifications", "status": "operational"}
    except Exception:
        return {"name": "Notifications", "status": "unknown"}


def _stripe_component() -> Dict[str, Any]:
    try:
        from payments import payments_service
        if not payments_service.enabled:
            return {"name": "Stripe Billing", "status": "disabled"}

        # Check last webhook received
        supabase = _get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        rows = (
            supabase.table("service_metrics")
            .select("ts")
            .eq("metric_name", "stripe_webhook_received")
            .gte("ts", since)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        if rows.data:
            return {"name": "Stripe Billing", "status": "operational", "last_webhook": rows.data[0]["ts"]}
        return {"name": "Stripe Billing", "status": "operational"}
    except Exception:
        return {"name": "Stripe Billing", "status": "unknown"}


def _recent_incidents() -> List[Dict[str, Any]]:
    try:
        supabase = _get_supabase()
        rows = (
            supabase.table("incidents")
            .select("id,started_at,ended_at,severity,title,description,status,components_json")
            .neq("status", "resolved")
            .order("started_at", desc=True)
            .limit(10)
            .execute()
        )
        return rows.data or []
    except Exception as exc:
        logger.debug("status: could not load incidents: %s", exc)
        return []
