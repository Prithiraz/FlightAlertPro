from fastapi import APIRouter, HTTPException
import logging
from typing import Optional
from pydantic import BaseModel
from supabase import create_client
from config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])

VALID_CABINS = {"economy", "premium_economy", "business", "first"}
VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "INR", "JPY", "CHF", "SEK", "NOK", "DKK", "SGD", "HKD", "NZD", "ZAR"}


def get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


class PreferencesUpdate(BaseModel):
    home_airport: Optional[str] = None
    default_cabin: Optional[str] = None
    currency: Optional[str] = None


@router.get("/me/preferences")
async def get_preferences(user_email: str):
    """Fetch the current user's travel preferences."""
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    try:
        supabase = get_supabase()
        result = (
            supabase.table("user_profiles")
            .select("home_airport, default_cabin, preferred_currency")
            .eq("email", user_email)
            .single()
            .execute()
        )
        if not result.data:
            return {"home_airport": None, "default_cabin": "economy", "currency": "USD"}

        data = result.data
        return {
            "home_airport": data.get("home_airport"),
            "default_cabin": data.get("default_cabin") or "economy",
            "currency": data.get("preferred_currency") or "USD",
        }
    except Exception as e:
        logger.error(f"Error fetching preferences for {user_email}: {e}")
        # Return defaults when profile doesn't exist yet
        return {"home_airport": None, "default_cabin": "economy", "currency": "USD"}


@router.put("/me/preferences")
async def update_preferences(user_email: str, body: PreferencesUpdate):
    """Update the current user's travel preferences."""
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    if body.default_cabin and body.default_cabin not in VALID_CABINS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cabin class. Must be one of: {', '.join(sorted(VALID_CABINS))}",
        )

    if body.currency and body.currency.upper() not in VALID_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid currency. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}",
        )

    try:
        supabase = get_supabase()

        updates: dict = {}
        if body.home_airport is not None:
            updates["home_airport"] = body.home_airport.strip().upper() if body.home_airport.strip() else None
        if body.default_cabin is not None:
            updates["default_cabin"] = body.default_cabin
        if body.currency is not None:
            updates["preferred_currency"] = body.currency.upper()

        if not updates:
            return {"success": True, "message": "No changes provided"}

        # Upsert so new users get a profile row automatically
        updates["email"] = user_email
        supabase.table("user_profiles").upsert(updates, on_conflict="email").execute()

        return {"success": True, "message": "Preferences updated successfully"}
    except Exception as e:
        logger.error(f"Error updating preferences for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")
