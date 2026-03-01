from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
from supabase import create_client
from config import config
from auth_deps import CurrentUser, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


# ---------------------------------------------------------------------------
# Phase 1 – /api/admin/me
# ---------------------------------------------------------------------------

@router.get("/me")
async def admin_me(admin: CurrentUser = Depends(require_admin)):
    """Return the authenticated admin's email for debugging."""
    return {"email": admin.email, "is_admin": True}


# ---------------------------------------------------------------------------
# Phase 2 – System overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def admin_overview(admin: CurrentUser = Depends(require_admin)):
    """Aggregate system health stats."""
    supabase = _get_supabase()
    since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    # Total users
    total_users = 0
    try:
        r = supabase.table("user_profiles").select("id", count="exact").execute()
        total_users = r.count or 0
    except Exception as exc:
        logger.debug("Could not count users: %s", exc)

    # Alerts
    total_alerts = 0
    active_alerts = 0
    try:
        r = supabase.table("price_alerts").select("id,active", count="exact").execute()
        total_alerts = r.count or 0
        active_alerts = sum(1 for row in (r.data or []) if row.get("active"))
    except Exception as exc:
        logger.debug("Could not count alerts: %s", exc)

    # Searches last 24h (from usage_events)
    searches_last_24h = 0
    try:
        r = (
            supabase.table("usage_events")
            .select("id", count="exact")
            .eq("type", "search")
            .gte("ts", since_24h)
            .execute()
        )
        searches_last_24h = r.count or 0
    except Exception as exc:
        logger.debug("Could not count searches: %s", exc)

    # Notifications last 24h
    notif_sent = 0
    notif_failed = 0
    try:
        r = (
            supabase.table("notification_log")
            .select("status")
            .gte("sent_at", since_24h)
            .execute()
        )
        for row in (r.data or []):
            if row.get("status") == "sent":
                notif_sent += 1
            elif row.get("status") == "failed":
                notif_failed += 1
    except Exception as exc:
        logger.debug("Could not count notifications: %s", exc)

    # Provider usage last 24h
    provider_usage: Dict[str, int] = {}
    try:
        r = (
            supabase.table("usage_events")
            .select("provider")
            .gte("ts", since_24h)
            .execute()
        )
        for row in (r.data or []):
            p = row.get("provider") or "unknown"
            provider_usage[p] = provider_usage.get(p, 0) + 1
    except Exception as exc:
        logger.debug("Could not aggregate provider usage: %s", exc)

    # Error summary last 24h
    error_summary: Dict[str, int] = {}
    try:
        r = (
            supabase.table("notification_log")
            .select("error_message")
            .eq("status", "failed")
            .gte("sent_at", since_24h)
            .execute()
        )
        for row in (r.data or []):
            msg = (row.get("error_message") or "unknown")[:120]
            error_summary[msg] = error_summary.get(msg, 0) + 1
    except Exception as exc:
        logger.debug("Could not aggregate errors: %s", exc)

    top_errors = sorted(error_summary.items(), key=lambda x: -x[1])[:10]

    return {
        "total_users": total_users,
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "searches_last_24h": searches_last_24h,
        "notifications_last_24h": {"sent": notif_sent, "failed": notif_failed},
        "provider_usage_last_24h": provider_usage,
        "error_summary_last_24h": [{"message": m, "count": c} for m, c in top_errors],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/providers")
async def admin_providers(admin: CurrentUser = Depends(require_admin)):
    """Per-provider health from provider_metrics."""
    supabase = _get_supabase()
    since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    rows: List[Dict] = []
    try:
        r = (
            supabase.table("provider_metrics")
            .select("*")
            .gte("date", since_24h[:10])
            .execute()
        )
        rows = r.data or []
    except Exception as exc:
        logger.debug("Could not fetch provider_metrics: %s", exc)

    # Aggregate per provider
    agg: Dict[str, Dict] = {}
    for row in rows:
        p = row.get("provider", "unknown")
        if p not in agg:
            agg[p] = {
                "provider": p,
                "enabled": True,
                "requests_24h": 0,
                "failures_24h": 0,
                "avg_latency_ms": None,
                "last_error": None,
            }
        agg[p]["requests_24h"] += row.get("call_count", 0)
        agg[p]["failures_24h"] += row.get("fail_count", 0)
        if row.get("avg_latency_ms") is not None:
            prev = agg[p]["avg_latency_ms"]
            agg[p]["avg_latency_ms"] = (
                row["avg_latency_ms"] if prev is None else (prev + row["avg_latency_ms"]) // 2
            )
        if row.get("last_failure_at"):
            agg[p]["last_error"] = row["last_failure_at"]

    # Mark Duffel as disabled if kill switch is on
    if config.DISABLE_PROVIDER_DUFFEL and "duffel" in agg:
        agg["duffel"]["enabled"] = False

    return {"providers": list(agg.values()), "timestamp": datetime.utcnow().isoformat()}


@router.get("/users")
async def admin_users(
    limit: int = Query(50, ge=1, le=500),
    sort: str = Query("alerts", pattern="^(alerts|searches|notifications)$"),
    admin: CurrentUser = Depends(require_admin),
):
    """List users with plan, alert count, recent activity."""
    supabase = _get_supabase()
    since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    users: List[Dict] = []
    try:
        r = supabase.table("user_profiles").select("id,email,plan,created_at").limit(limit).execute()
        users = r.data or []
    except Exception as exc:
        logger.debug("Could not fetch user_profiles: %s", exc)
        return {"users": [], "count": 0}

    # Enrich each user with live counters
    enriched = []
    for u in users:
        uid = u.get("id")
        email = u.get("email", "")

        active_alerts = 0
        try:
            ar = (
                supabase.table("price_alerts")
                .select("id", count="exact")
                .eq("user_email", email)
                .eq("active", True)
                .execute()
            )
            active_alerts = ar.count or 0
        except Exception:
            pass

        searches_24h = 0
        try:
            sr = (
                supabase.table("usage_events")
                .select("id", count="exact")
                .eq("user_id", uid)
                .eq("type", "search")
                .gte("ts", since_24h)
                .execute()
            )
            searches_24h = sr.count or 0
        except Exception:
            pass

        notifications_24h = 0
        try:
            nr = (
                supabase.table("notification_log")
                .select("id", count="exact")
                .eq("user_id", uid)
                .gte("sent_at", since_24h)
                .execute()
            )
            notifications_24h = nr.count or 0
        except Exception:
            pass

        enriched.append({
            "user_id": uid,
            "email": email,
            "plan": u.get("plan", "free"),
            "created_at": u.get("created_at"),
            "active_alerts": active_alerts,
            "searches_24h": searches_24h,
            "notifications_24h": notifications_24h,
        })

    sort_key = {"alerts": "active_alerts", "searches": "searches_24h", "notifications": "notifications_24h"}.get(sort, "active_alerts")
    enriched.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

    return {"users": enriched, "count": len(enriched)}


@router.get("/user/{user_id}/details")
async def admin_user_details(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
):
    """Detailed view of a single user: profile, recent alerts, notifications, usage."""
    supabase = _get_supabase()

    profile = {}
    try:
        r = supabase.table("user_profiles").select("*").eq("id", user_id).maybe_single().execute()
        profile = r.data or {}
    except Exception as exc:
        logger.debug("Could not fetch profile for %s: %s", user_id, exc)

    email = profile.get("email", "")

    recent_alerts: List[Dict] = []
    try:
        r = (
            supabase.table("price_alerts")
            .select("*")
            .eq("user_email", email)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        recent_alerts = r.data or []
    except Exception as exc:
        logger.debug("Could not fetch alerts: %s", exc)

    recent_notifications: List[Dict] = []
    try:
        r = (
            supabase.table("notification_log")
            .select("*")
            .eq("user_id", user_id)
            .order("sent_at", desc=True)
            .limit(10)
            .execute()
        )
        recent_notifications = r.data or []
    except Exception as exc:
        logger.debug("Could not fetch notifications: %s", exc)

    return {
        "profile": profile,
        "recent_alerts": recent_alerts,
        "recent_notifications": recent_notifications,
    }


# ---------------------------------------------------------------------------
# Phase 5 – Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics")
async def admin_analytics(
    days: int = Query(7, ge=1, le=90),
    admin: CurrentUser = Depends(require_admin),
):
    """Return daily aggregated usage for the last N days."""
    supabase = _get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Searches per day
    searches_by_day: Dict[str, int] = {}
    try:
        r = (
            supabase.table("usage_events")
            .select("ts")
            .eq("type", "search")
            .gte("ts", since)
            .execute()
        )
        for row in (r.data or []):
            day = (row.get("ts") or "")[:10]
            searches_by_day[day] = searches_by_day.get(day, 0) + 1
    except Exception as exc:
        logger.debug("Could not aggregate search events: %s", exc)

    # Notifications per day
    notifications_by_day: Dict[str, int] = {}
    try:
        r = (
            supabase.table("notification_log")
            .select("sent_at,status")
            .eq("status", "sent")
            .gte("sent_at", since)
            .execute()
        )
        for row in (r.data or []):
            day = (row.get("sent_at") or "")[:10]
            notifications_by_day[day] = notifications_by_day.get(day, 0) + 1
    except Exception as exc:
        logger.debug("Could not aggregate notification events: %s", exc)

    # Alerts created per day
    alerts_by_day: Dict[str, int] = {}
    try:
        r = (
            supabase.table("price_alerts")
            .select("created_at")
            .gte("created_at", since)
            .execute()
        )
        for row in (r.data or []):
            day = (row.get("created_at") or "")[:10]
            alerts_by_day[day] = alerts_by_day.get(day, 0) + 1
    except Exception as exc:
        logger.debug("Could not aggregate alert creation events: %s", exc)

    # Build unified daily series
    all_days = sorted(
        set(list(searches_by_day.keys()) + list(notifications_by_day.keys()) + list(alerts_by_day.keys()))
    )

    series = [
        {
            "date": d,
            "searches": searches_by_day.get(d, 0),
            "notifications_sent": notifications_by_day.get(d, 0),
            "alerts_created": alerts_by_day.get(d, 0),
        }
        for d in all_days
    ]

    return {
        "days": days,
        "series": series,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility, now admin-only)
# ---------------------------------------------------------------------------

@router.get("/metrics")
async def get_metrics(admin: CurrentUser = Depends(require_admin)):
    try:
        supabase = _get_supabase()

        provider_metrics = supabase.table('provider_metrics').select('*').order('date', desc=True).limit(100).execute()

        analytics = supabase.table('analytics_events').select('event_type').execute()

        event_counts = {}
        for event in analytics.data:
            event_type = event.get('event_type')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        notifications = supabase.table('notification_log').select('status').execute()

        notif_stats = {
            'sent': len([n for n in notifications.data if n.get('status') == 'sent']),
            'failed': len([n for n in notifications.data if n.get('status') == 'failed']),
            'queued': len([n for n in notifications.data if n.get('status') == 'queued'])
        }

        return {
            "provider_metrics": provider_metrics.data,
            "event_counts": event_counts,
            "notification_stats": notif_stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/quota")
async def get_user_quota(user_id: str, admin: CurrentUser = Depends(require_admin)):
    try:
        supabase = _get_supabase()
        result = supabase.table('users').select('api_calls_count, notification_credits, plan').eq('id', user_id).single().execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching quota: {str(e)}")
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_id}/quota")
async def update_user_quota(
    user_id: str,
    api_calls_count: int = None,
    notification_credits: int = None,
    admin: CurrentUser = Depends(require_admin),
):
    try:
        supabase = _get_supabase()
        updates = {}
        if api_calls_count is not None:
            updates['api_calls_count'] = api_calls_count
        if notification_credits is not None:
            updates['notification_credits'] = notification_credits
        result = supabase.table('users').update(updates).eq('id', user_id).execute()
        logger.info(f"Updated quota for user {user_id}: {updates}")
        return {"status": "updated", "user_id": user_id, "updates": updates}
    except Exception as e:
        logger.error(f"Error updating quota: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments")
async def list_experiments(admin: CurrentUser = Depends(require_admin)):
    try:
        supabase = _get_supabase()
        result = supabase.table('experiments').select('*').execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments")
async def create_experiment(name: str, variants: Dict, admin: CurrentUser = Depends(require_admin)):
    try:
        supabase = _get_supabase()
        result = supabase.table('experiments').insert({
            'name': name,
            'variants': variants,
            'is_active': True
        }).execute()
        logger.info(f"Created experiment: {name}")
        return result.data[0]
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

