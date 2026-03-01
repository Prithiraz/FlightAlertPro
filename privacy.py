"""Privacy & compliance endpoints — data export, account deletion, consent preferences.

Phase 1 — Data export    GET  /api/privacy/export
Phase 2 — Delete request POST /api/privacy/delete-request
           Delete confirm POST /api/privacy/delete-confirm
Phase 5 — Admin events   GET  /api/admin/privacy/events  (in admin.py)
"""
from __future__ import annotations

import hashlib
import logging
import os
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from supabase import create_client

from audit_log import audit
from auth_deps import CurrentUser, get_current_user
from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/privacy", tags=["privacy"])

_NOTIFICATION_HISTORY_DAYS = int(os.getenv("RETAIN_NOTIFICATION_LOG_DAYS", "90"))
_PRICE_HISTORY_LIMIT = 500
_MAX_ALERTS_FOR_EXPORT = 20


def _get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def _hash(value: str) -> str:
    """Irreversible SHA-256 hex digest, truncated to 32 chars."""
    return hashlib.sha256(value.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Phase 1 – Data export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_user_data(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    price_history: bool = Query(True, description="Include price history (up to 500 pts per alert)"),
):
    """Return a single JSON blob with all data owned by the authenticated user."""
    supabase = _get_supabase()
    uid = user.user_id
    email = user.email

    # Profile
    profile: dict = {}
    try:
        r = supabase.table("user_profiles").select("*").eq("user_id", uid).maybe_single().execute()
        profile = r.data or {}
    except Exception as exc:
        logger.debug("export: could not fetch profile for %s: %s", uid, exc)

    # Alerts (active + inactive)
    alerts: list = []
    try:
        r = (
            supabase.table("price_alerts")
            .select("*")
            .eq("user_email", email)
            .execute()
        )
        alerts = r.data or []
    except Exception as exc:
        logger.debug("export: could not fetch alerts: %s", exc)

    # Saved searches
    saved_searches: list = []
    try:
        r = supabase.table("saved_searches").select("*").eq("user_id", uid).execute()
        saved_searches = r.data or []
    except Exception as exc:
        logger.debug("export: could not fetch saved_searches: %s", exc)

    # Alert templates
    alert_templates: list = []
    try:
        r = supabase.table("alert_templates").select("*").eq("user_id", uid).execute()
        alert_templates = r.data or []
    except Exception as exc:
        logger.debug("export: could not fetch alert_templates: %s", exc)

    # Notification history (last N days)
    since = (datetime.now(timezone.utc) - timedelta(days=_NOTIFICATION_HISTORY_DAYS)).isoformat()
    notification_history: list = []
    try:
        r = (
            supabase.table("notification_log")
            .select("id,alert_id,channel,status,sent_at,error_message")
            .eq("user_id", uid)
            .gte("sent_at", since)
            .order("sent_at", desc=True)
            .limit(1000)
            .execute()
        )
        notification_history = r.data or []
    except Exception as exc:
        logger.debug("export: could not fetch notification_log: %s", exc)

    # Price history (optional; capped per alert)
    price_history_data: list = []
    if price_history and alerts:
        alert_ids = [a["id"] for a in alerts if a.get("id")][:_MAX_ALERTS_FOR_EXPORT]
        for aid in alert_ids:
            try:
                r = (
                    supabase.table("price_history")
                    .select("alert_id,price,checked_at,source")
                    .eq("alert_id", aid)
                    .order("checked_at", desc=True)
                    .limit(_PRICE_HISTORY_LIMIT)
                    .execute()
                )
                price_history_data.extend(r.data or [])
            except Exception as exc:
                logger.debug("export: price_history for alert %s: %s", aid, exc)

    # Billing status summary (no raw card/token data)
    billing_summary: dict = {}
    try:
        r = (
            supabase.table("user_profiles")
            .select("plan,stripe_customer_id")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        if r.data:
            billing_summary = {
                "plan": r.data.get("plan", "free"),
                "stripe_customer_linked": bool(r.data.get("stripe_customer_id")),
            }
    except Exception as exc:
        logger.debug("export: billing summary: %s", exc)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "alerts": alerts,
        "saved_searches": saved_searches,
        "alert_templates": alert_templates,
        "notification_history": notification_history,
        "price_history": price_history_data,
        "billing_summary": billing_summary,
    }

    await audit(
        action="privacy.export",
        user_id=uid,
        email=email,
        request=request,
        metadata={"alerts": len(alerts), "notifications": len(notification_history)},
    )

    return payload


# ---------------------------------------------------------------------------
# Phase 2 – Account deletion / right-to-erasure
# ---------------------------------------------------------------------------

class DeleteRequestBody(BaseModel):
    confirmation: str  # must equal "DELETE_MY_ACCOUNT"


class DeleteConfirmBody(BaseModel):
    token: str


@router.post("/delete-request")
async def request_account_deletion(
    body: DeleteRequestBody,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Initiate account deletion.  Returns a one-time confirmation token."""
    if body.confirmation != "DELETE_MY_ACCOUNT":
        raise HTTPException(
            status_code=400,
            detail="confirmation must be the string 'DELETE_MY_ACCOUNT'",
        )

    supabase = _get_supabase()
    uid = user.user_id
    email = user.email

    token = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    token_hash = _hash(token)

    try:
        supabase.table("deletion_requests").insert({
            "user_id": uid,
            "email_hash": _hash(email),
            "token_hash": token_hash,
            "status": "pending",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.error("Could not insert deletion_request for %s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Failed to create deletion request")

    await audit(
        action="privacy.delete_request",
        user_id=uid,
        email=email,
        request=request,
    )

    return {
        "status": "pending",
        "message": "Deletion request received. Confirm with the token provided.",
        "confirm_token": token,
    }


@router.post("/delete-confirm")
async def confirm_account_deletion(
    body: DeleteConfirmBody,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Confirm and execute account deletion using the one-time token."""
    supabase = _get_supabase()
    uid = user.user_id
    email = user.email

    token_hash = _hash(body.token)

    # Retrieve pending request for this user
    try:
        r = (
            supabase.table("deletion_requests")
            .select("id,status")
            .eq("user_id", uid)
            .eq("token_hash", token_hash)
            .eq("status", "pending")
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Could not query deletion_request: %s", exc)
        raise HTTPException(status_code=500, detail="Deletion confirmation failed")

    if not r.data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired deletion token",
        )

    req_id = r.data["id"]

    # Mark as processing
    try:
        supabase.table("deletion_requests").update({"status": "processing"}).eq("id", req_id).execute()
    except Exception:
        pass

    # --- Anonymise / delete user data ---
    _delete_user_data(supabase, uid, email)

    # Mark deletion request as done (anonymise email after this point)
    try:
        supabase.table("deletion_requests").update({
            "status": "done",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "email_hash": _hash(email),   # ensure PII is hashed
            "user_id": None,              # remove user_id link so record is not re-identifiable
        }).eq("id", req_id).execute()
    except Exception as exc:
        logger.warning("Could not finalize deletion_request %s: %s", req_id, exc)

    await audit(
        action="privacy.delete_confirmed",
        user_id=uid,
        email=email,
        request=request,
        metadata={"req_id": str(req_id)},
    )

    return {
        "status": "done",
        "message": "Your account and associated data have been deleted.",
    }


def _delete_user_data(supabase, uid: str, email: str) -> None:
    """Delete or anonymise all PII for a user.  Best-effort — logs but does not raise."""
    steps = [
        # (table, column, value)
        ("price_alerts", "user_email", email),
        ("saved_searches", "user_id", uid),
        ("alert_templates", "user_id", uid),
        ("push_subscriptions", "user_id", uid),
        ("experiment_assignments", "user_id", uid),
        ("workspace_members", "user_id", uid),
    ]
    for table, col, val in steps:
        try:
            supabase.table(table).delete().eq(col, val).execute()
        except Exception as exc:
            logger.warning("delete_user_data: %s.%s=%s failed: %s", table, col, val, exc)

    # Anonymise notification_log (keep audit trail but remove user_id)
    try:
        supabase.table("notification_log").update({"user_id": None}).eq("user_id", uid).execute()
    except Exception as exc:
        logger.warning("delete_user_data: anonymise notification_log: %s", exc)

    # Delete price history rows for the user's alerts
    try:
        supabase.table("price_history").delete().eq("user_id", uid).execute()
    except Exception as exc:
        logger.warning("delete_user_data: price_history: %s", exc)

    # Delete profile
    try:
        supabase.table("user_profiles").delete().eq("user_id", uid).execute()
    except Exception as exc:
        logger.warning("delete_user_data: user_profiles: %s", exc)
