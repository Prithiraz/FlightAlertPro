"""User profile endpoint (onboarding, currency preference, notification channels)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


class ProfileUpdate(BaseModel):
    home_currency: Optional[str] = None
    default_channels: Optional[List[str]] = None
    onboarded: Optional[bool] = None
    lifecycle_emails_opt_in: Optional[bool] = None


@router.get("/profile")
async def get_profile(user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    try:
        result = (
            supabase.table("user_profiles")
            .select("*")
            .eq("user_id", user.user_id)
            .maybe_single()
            .execute()
        )
        if result.data:
            return result.data
        # Return defaults if no profile row yet
        return {
            "user_id": user.user_id,
            "email": user.email,
            "home_currency": "USD",
            "default_channels": ["email"],
            "onboarded": False,
        }
    except Exception as exc:
        logger.warning("Could not fetch profile for %s: %s", user.user_id, exc)
        return {
            "user_id": user.user_id,
            "email": user.email,
            "home_currency": "USD",
            "default_channels": ["email"],
            "onboarded": False,
        }


@router.post("/profile")
async def upsert_profile(body: ProfileUpdate, user: CurrentUser = Depends(get_current_user)):
    """Create or update the authenticated user's profile."""
    update_data = {"user_id": user.user_id, "email": user.email}
    if body.home_currency is not None:
        update_data["home_currency"] = body.home_currency
    if body.default_channels is not None:
        update_data["default_channels"] = body.default_channels
    if body.onboarded is not None:
        update_data["onboarded"] = body.onboarded
    if body.lifecycle_emails_opt_in is not None:
        update_data["lifecycle_emails_opt_in"] = body.lifecycle_emails_opt_in
    try:
        result = (
            supabase.table("user_profiles")
            .upsert(update_data, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else update_data
    except Exception as exc:
        logger.error("Could not upsert profile for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to save profile")
