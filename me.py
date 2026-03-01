"""User profile and usage endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
from entitlements import get_plan_limits
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["me"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def _get_user_plan(user_email: str) -> str:
    """Look up the user's current plan from user_profiles. Defaults to 'free'."""
    try:
        result = (
            supabase.table("user_profiles")
            .select("plan")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )
        if result.data and result.data.get("plan"):
            return result.data["plan"]
    except Exception as exc:
        logger.debug("Could not fetch plan for %s: %s", user_email, exc)
    return "free"


@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's profile, plan, and current usage counters."""
    plan = _get_user_plan(user.email)
    limits = get_plan_limits(plan)

    # Active alerts count
    alerts_active = 0
    try:
        result = (
            supabase.table("price_alerts")
            .select("id", count="exact")
            .eq("user_email", user.email)
            .eq("active", True)
            .execute()
        )
        alerts_active = result.count or 0
    except Exception as exc:
        logger.warning("Could not count alerts for %s: %s", user.email, exc)

    # Saved searches count
    saved_searches_count = 0
    try:
        result = (
            supabase.table("saved_searches")
            .select("id", count="exact")
            .eq("user_id", user.user_id)
            .execute()
        )
        saved_searches_count = result.count or 0
    except Exception as exc:
        logger.debug("Could not count saved searches for %s: %s", user.user_id, exc)

    # Notifications count (all time)
    notifications_count = 0
    try:
        result = (
            supabase.table("notification_log")
            .select("id", count="exact")
            .eq("user_id", user.user_id)
            .execute()
        )
        notifications_count = result.count or 0
    except Exception as exc:
        logger.debug("Could not count notifications for %s: %s", user.user_id, exc)

    return {
        "user_id": user.user_id,
        "email": user.email,
        "plan": plan,
        "limits": limits,
        "usage": {
            "alerts_active": alerts_active,
            "saved_searches_count": saved_searches_count,
            "notifications_count": notifications_count,
        },
    }


@router.get("/notifications/history")
async def get_notification_history(
    limit: int = 20,
    user: CurrentUser = Depends(get_current_user),
):
    """Return the last N notifications sent to the authenticated user."""
    try:
        result = (
            supabase.table("notification_log")
            .select("*")
            .eq("user_id", user.user_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"notifications": result.data or [], "count": len(result.data or [])}
    except Exception as exc:
        logger.warning("Could not fetch notification history for %s: %s", user.user_id, exc)
        return {"notifications": [], "count": 0}
