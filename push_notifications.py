"""Push notification subscription management for FlightAlertPro.

Endpoints:
  POST   /api/push/subscribe    – save (or update) a Web Push subscription for the authenticated user
  DELETE /api/push/unsubscribe  – remove the user's push subscription

Subscriptions are stored in the `push_subscriptions` table (see migration SQL).
Web-push delivery is handled by the worker via pywebpush when VAPID keys are set.
"""
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_deps import CurrentUser, get_current_user
from config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/push", tags=["push"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    expirationTime: Optional[Any] = None


# ── Subscribe ──────────────────────────────────────────────────────────────────

@router.post("/subscribe")
async def subscribe(
    body: PushSubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Save (upsert) a Web Push subscription for the authenticated user."""
    try:
        from supabase import create_client
        sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

        record = {
            "user_id": user.user_id,
            "user_email": user.email,
            "endpoint": body.endpoint,
            "p256dh": body.keys.p256dh,
            "auth": body.keys.auth,
        }

        # Upsert on (user_id, endpoint) so re-subscribing on the same device updates keys
        sb.table("push_subscriptions").upsert(
            record,
            on_conflict="user_id,endpoint",
        ).execute()

        return {"status": "subscribed"}
    except Exception as exc:
        logger.error("Failed to save push subscription for user %s: %s", user.email, exc)
        raise HTTPException(status_code=500, detail="Failed to save push subscription")


# ── Unsubscribe ────────────────────────────────────────────────────────────────

@router.delete("/unsubscribe")
async def unsubscribe(user: CurrentUser = Depends(get_current_user)):
    """Remove all push subscriptions for the authenticated user."""
    try:
        from supabase import create_client
        sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        sb.table("push_subscriptions").delete().eq("user_id", user.user_id).execute()
        return {"status": "unsubscribed"}
    except Exception as exc:
        logger.error("Failed to remove push subscription for user %s: %s", user.email, exc)
        raise HTTPException(status_code=500, detail="Failed to remove push subscription")


# ── Delivery helper (used by worker) ─────────────────────────────────────────

def send_push_notification(user_email: str, title: str, body: str, url: str = "/") -> int:
    """
    Send a Web Push notification to all subscriptions of *user_email*.

    Returns the number of successful deliveries.
    Requires pywebpush to be installed and VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY set.
    Silently skips if pywebpush is not installed or VAPID keys are missing.
    """
    if not config.VAPID_PRIVATE_KEY or not config.VAPID_PUBLIC_KEY:
        logger.debug("VAPID keys not configured – skipping push for %s", user_email)
        return 0

    try:
        from pywebpush import webpush, WebPushException  # type: ignore
    except ImportError:
        logger.debug("pywebpush not installed – skipping push for %s", user_email)
        return 0

    try:
        from supabase import create_client
        sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        result = sb.table("push_subscriptions").select("*").eq("user_email", user_email).execute()
        subscriptions = result.data or []
    except Exception as exc:
        logger.error("Failed to fetch push subscriptions for %s: %s", user_email, exc)
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = 0
    stale_ids = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=config.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{config.VAPID_CONTACT_EMAIL or user_email}"},
            )
            sent += 1
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                # Endpoint expired – mark for cleanup
                stale_ids.append(sub["id"])
            else:
                logger.warning("Push delivery failed for %s (endpoint=%s): %s", user_email, sub["endpoint"][:40], exc)

    # Clean up stale subscriptions
    if stale_ids:
        try:
            from supabase import create_client
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            for sid in stale_ids:
                sb.table("push_subscriptions").delete().eq("id", sid).execute()
        except Exception:
            pass

    return sent
