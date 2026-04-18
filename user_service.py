from fastapi import APIRouter, HTTPException
import logging
import random
import string
from typing import Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from supabase import create_client
from config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])

VALID_CABINS = {"economy", "premium_economy", "business", "first"}
VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "INR", "JPY", "CHF", "SEK", "NOK", "DKK", "SGD", "HKD", "NZD", "ZAR"}
VALID_REWARD_PROGRAMS = {"chase_ur", "amex_mr", "capital_one", "none"}

REFERRAL_REWARD_DAYS = 30
DEFAULT_PREFERENCES = {
    "home_airport": None,
    "default_cabin": "economy",
    "currency": "USD",
    "preferred_reward_program": "none",
    "passport_nationality": None,
}


def get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def get_auth_user_id(user_email: str, supabase=None) -> Optional[str]:
    """Fetch auth.users UUID for an email."""
    client = supabase or get_supabase()
    try:
        result = (
            client.schema("auth")
            .table("users")
            .select("id")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )
        return result.data.get("id") if result and result.data else None
    except Exception as exc:
        logger.error("Failed to fetch auth user id for %s: %s", user_email, exc)
        return None


def generate_referral_code() -> str:
    """Generate a unique short referral code in the format FLIGHT-XXXX."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"FLIGHT-{suffix}"


def get_or_create_referral_code(user_email: str) -> str:
    """Return existing referral_code for the user or generate and store a new one."""
    supabase = get_supabase()
    profile_result = (
        supabase.table("user_profiles")
        .select("id, referral_code")
        .eq("email", user_email)
        .maybe_single()
        .execute()
    )
    profile_row = profile_result.data or {}
    existing_code = profile_row.get("referral_code")
    if existing_code:
        return existing_code

    # Generate a collision-free code
    user_id = profile_row.get("id") or get_auth_user_id(user_email, supabase)
    if not user_id:
        raise RuntimeError(f"No auth user found for {user_email}")

    for _ in range(10):
        code = generate_referral_code()
        check = (
            supabase.table("user_profiles")
            .select("id")
            .eq("referral_code", code)
            .execute()
        )
        if not check.data:
            if profile_row:
                supabase.table("user_profiles").update(
                    {"referral_code": code}
                ).eq("email", user_email).execute()
            else:
                supabase.table("user_profiles").insert(
                    {"id": user_id, "email": user_email, "referral_code": code}
                ).execute()
            return code

    raise RuntimeError("Failed to generate a unique referral code after multiple attempts")


def grant_referral_reward(referrer_code: str) -> bool:
    """Add REFERRAL_REWARD_DAYS days of Pro referral access to the owner of referrer_code.

    Returns True if the reward was applied, False if the code was not found.
    """
    supabase = get_supabase()
    result = (
        supabase.table("user_profiles")
        .select("email, elite_until, subscription_tier")
        .eq("referral_code", referrer_code)
        .execute()
    )
    if not result.data:
        logger.warning("grant_referral_reward: referral code %s not found", referrer_code)
        return False

    row = result.data[0]
    now = datetime.now(timezone.utc)

    current_until_raw = row.get("elite_until")
    if current_until_raw:
        try:
            current_until = datetime.fromisoformat(current_until_raw.replace("Z", "+00:00"))
            if current_until.tzinfo is None:
                current_until = current_until.replace(tzinfo=timezone.utc)
        except ValueError:
            current_until = now
    else:
        current_until = now

    # Extend from the later of now or the existing elite_until
    base = max(now, current_until)
    new_until = base + timedelta(days=REFERRAL_REWARD_DAYS)

    updates = {"elite_until": new_until.isoformat()}
    current_tier = row.get("subscription_tier")
    if current_tier in (None, "free"):
        updates["subscription_tier"] = "pro"

    supabase.table("user_profiles").update(updates).eq("referral_code", referrer_code).execute()

    logger.info(
        "Referral reward granted: code=%s, new pro access until=%s",
        referrer_code,
        new_until.isoformat(),
    )
    return True


class PreferencesUpdate(BaseModel):
    home_airport: Optional[str] = None
    default_cabin: Optional[str] = None
    currency: Optional[str] = None
    preferred_reward_program: Optional[str] = None
    passport_nationality: Optional[str] = None


@router.get("/me/preferences")
async def get_preferences(user_email: str):
    """Fetch the current user's travel preferences."""
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    try:
        supabase = get_supabase()
        result = (
            supabase.table("user_profiles")
            .select("home_airport, default_cabin, preferred_currency, preferred_reward_program, passport_nationality")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )
        if not result.data:
            return DEFAULT_PREFERENCES

        data = result.data
        return {
            "home_airport": data.get("home_airport"),
            "default_cabin": data.get("default_cabin") or "economy",
            "currency": data.get("preferred_currency") or "USD",
            "preferred_reward_program": data.get("preferred_reward_program") or "none",
            "passport_nationality": data.get("passport_nationality"),
        }
    except Exception as e:
        logger.error(f"Error fetching preferences for {user_email}: {e}")
        # Return defaults when profile doesn't exist yet
        return DEFAULT_PREFERENCES


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

    if body.preferred_reward_program and body.preferred_reward_program not in VALID_REWARD_PROGRAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reward program. Must be one of: {', '.join(sorted(VALID_REWARD_PROGRAMS))}",
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
        if body.preferred_reward_program is not None:
            updates["preferred_reward_program"] = body.preferred_reward_program
        if body.passport_nationality is not None:
            updates["passport_nationality"] = body.passport_nationality.strip() if body.passport_nationality.strip() else None

        if not updates:
            return {"success": True, "message": "No changes provided"}

        existing_profile = (
            supabase.table("user_profiles")
            .select("id")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )
        raw_profile_data = existing_profile.data
        existing_profile_data = raw_profile_data if isinstance(raw_profile_data, dict) else None
        if raw_profile_data is not None and existing_profile_data is None:
            logger.warning("Unexpected profile payload type while updating preferences for %s", user_email)
        fetched_user_id = existing_profile_data.get("id") if existing_profile_data else None
        if not fetched_user_id and existing_profile_data:
            logger.warning("Profile exists but id missing for %s; falling back to auth.users lookup", user_email)
        if not fetched_user_id:
            if raw_profile_data is None:
                logger.info("No user_profiles row found for %s; resolving auth.users id for upsert", user_email)
            fetched_user_id = get_auth_user_id(user_email, supabase)
        if not fetched_user_id:
            raise HTTPException(status_code=404, detail="Auth user not found for provided email")

        supabase.table("user_profiles").upsert(
            {"id": fetched_user_id, "email": user_email, **updates}
        ).execute()

        return {"success": True, "message": "Preferences updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences for {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


# ---------------------------------------------------------------------------
# Referral endpoints
# ---------------------------------------------------------------------------

class RegisterUserRequest(BaseModel):
    email: str
    referred_by: Optional[str] = None


@router.post("/register")
async def register_user(body: RegisterUserRequest):
    """Called after Supabase Auth sign-up to assign a referral code and log referred_by."""
    if not body.email:
        raise HTTPException(status_code=400, detail="email is required")

    try:
        supabase = get_supabase()

        existing = (
            supabase.table("user_profiles")
            .select("id, referral_code")
            .eq("email", body.email)
            .maybe_single()
            .execute()
        )
        existing_row = existing.data or {}
        existing_code = existing_row.get("referral_code")
        update_data: dict = {}
        insert_data: dict = {}

        if not existing_code:
            for _ in range(10):
                code = generate_referral_code()
                check = (
                    supabase.table("user_profiles")
                    .select("id")
                    .eq("referral_code", code)
                    .execute()
                )
                if not check.data:
                    if existing_row:
                        update_data["referral_code"] = code
                    else:
                        insert_data["referral_code"] = code
                    break

        if body.referred_by:
            if existing_row:
                update_data["referred_by"] = body.referred_by
            else:
                insert_data["referred_by"] = body.referred_by

        if existing_row:
            if update_data:
                supabase.table("user_profiles").update(update_data).eq("email", body.email).execute()
        else:
            auth_user_id = get_auth_user_id(body.email, supabase)
            if not auth_user_id:
                raise HTTPException(status_code=404, detail="Auth user not found for provided email")
            supabase.table("user_profiles").insert(
                {"id": auth_user_id, "email": body.email, **insert_data}
            ).execute()

        # Grant reward to the referrer
        if body.referred_by:
            grant_referral_reward(body.referred_by)

        return {"success": True, "referral_code": update_data.get("referral_code") or insert_data.get("referral_code") or existing_code}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user {body.email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user")


@router.get("/me/referral")
async def get_referral_info(user_email: str):
    """Return the user's referral code, number of successful referrals, and referral expiry timestamp."""
    if not user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    try:
        supabase = get_supabase()

        result = (
            supabase.table("user_profiles")
            .select("referral_code, elite_until")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )

        if not result.data:
            # Ensure the user has a profile + referral code
            code = get_or_create_referral_code(user_email)
            return {"referral_code": code, "referred_count": 0, "elite_until": None}

        data = result.data
        code = data.get("referral_code")
        if not code:
            code = get_or_create_referral_code(user_email)

        # Count how many users used this referral code
        referred_result = (
            supabase.table("user_profiles")
            .select("id", count="exact")
            .eq("referred_by", code)
            .execute()
        )
        referred_count = referred_result.count if referred_result.count is not None else 0

        return {
            "referral_code": code,
            "referred_count": referred_count,
            "elite_until": data.get("elite_until"),
        }
    except Exception as e:
        logger.error(f"Error fetching referral info for {user_email}: {e}")
        try:
            code = get_or_create_referral_code(user_email)
            return {"referral_code": code, "referred_count": 0, "elite_until": None}
        except Exception as inner:
            logger.error("Unable to recover referral info by creating fallback code for %s: %s", user_email, inner)
            return {"referral_code": None, "referred_count": 0, "elite_until": None}
