"""
Support bundle endpoint – returns safe diagnostics (no secrets).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from auth_deps import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/support", tags=["support"])


def _get_supabase():
    from supabase import create_client
    from config import config
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


@router.get("/bundle")
async def support_bundle(user: CurrentUser = Depends(get_current_user)) -> JSONResponse:
    """
    Return a JSON support bundle containing safe diagnostics.

    Includes: user plan/usage, last 20 notifications, systemcheck snapshot,
    frontend version.  No secrets are included.
    """
    bundle: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_version": os.getenv("VITE_APP_VERSION", "unknown"),
    }

    # User info
    try:
        supabase = _get_supabase()
        profile = (
            supabase.table("user_profiles")
            .select("plan,onboarded,created_at,home_currency,locale")
            .eq("id", str(user.user_id))
            .single()
            .execute()
        )
        bundle["user"] = {
            "email": user.email,
            "plan": (profile.data or {}).get("plan", "free"),
            "onboarded": (profile.data or {}).get("onboarded", False),
            "created_at": (profile.data or {}).get("created_at"),
            "home_currency": (profile.data or {}).get("home_currency", "USD"),
            "locale": (profile.data or {}).get("locale", "en-US"),
        }
    except Exception as exc:
        logger.debug("support_bundle: profile fetch failed: %s", exc)
        bundle["user"] = {"email": user.email}

    # Last 20 notifications
    try:
        supabase = _get_supabase()
        notifs = (
            supabase.table("notification_log")
            .select("channel,status,sent_at,error_message")
            .eq("user_id", str(user.user_id))
            .order("sent_at", desc=True)
            .limit(20)
            .execute()
        )
        bundle["recent_notifications"] = notifs.data or []
    except Exception as exc:
        logger.debug("support_bundle: notifications fetch failed: %s", exc)
        bundle["recent_notifications"] = []

    # Systemcheck snapshot (lightweight – only provider enabled flags)
    try:
        from config import config as cfg
        from duffel_service import duffel_service
        from airscraper_service import airscraper_service

        bundle["systemcheck"] = {
            "duffel_enabled": duffel_service.enabled,
            "rapidapi_enabled": cfg.RAPIDAPI_KEY is not None,
            "airscraper_enabled": airscraper_service.enabled,
            "supabase_configured": bool(cfg.SUPABASE_URL),
            "stripe_configured": bool(cfg.STRIPE_SECRET_KEY),
        }
    except Exception as exc:
        logger.debug("support_bundle: systemcheck failed: %s", exc)
        bundle["systemcheck"] = {}

    return JSONResponse(content=bundle)
