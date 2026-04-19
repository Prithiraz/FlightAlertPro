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
    user_id: str
    user_email: str
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
        response = supabase.table("user_profiles").select("*").eq("email", user_email).maybe_single().execute()
        if response and hasattr(response, 'data') and response.data:
            return response.data
        return {} 
    except Exception as e:
        logger.error(f"Profile fetch error handled safely: {e}")
        return {}


@router.put("/me/preferences")
async def update_preferences(request: PreferencesUpdate):
    """Update the current user's travel preferences."""
    request_user_email = (request.user_email or "").strip()

    if not request_user_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    if request.default_cabin and request.default_cabin not in VALID_CABINS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cabin class. Must be one of: {', '.join(sorted(VALID_CABINS))}",
        )

    if request.currency and request.currency.upper() not in VALID_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid currency. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}",
        )

    if request.preferred_reward_program and request.preferred_reward_program not in VALID_REWARD_PROGRAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reward program. Must be one of: {', '.join(sorted(VALID_REWARD_PROGRAMS))}",
        )

    try:
        supabase = get_supabase()
        request.user_email = request_user_email

        updates: dict = {}
        if request.home_airport is not None:
            updates["home_airport"] = request.home_airport.strip().upper() if request.home_airport.strip() else None
        if request.default_cabin is not None:
            updates["default_cabin"] = request.default_cabin
        if request.currency is not None:
            updates["preferred_currency"] = request.currency.upper()
        if request.preferred_reward_program is not None:
            updates["preferred_reward_program"] = request.preferred_reward_program
        if request.passport_nationality is not None:
            updates["passport_nationality"] = request.passport_nationality.strip() if request.passport_nationality.strip() else None

        if not updates:
            return {"success": True, "message": "No changes provided"}

        # Assume request.user_id is provided by the frontend
        # Assume request.user_id is provided by the frontend
        if not getattr(request, 'user_id', None):
            raise HTTPException(status_code=400, detail="user_id is required in the payload")
            
        supabase.table("user_profiles").upsert({
            "id": request.user_id, 
            "email": request_user_email, 
            "user_email": request_user_email, 
            **updates
        }).execute()

        return {"success": True, "message": "Preferences updated successfully"}

        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preferences for {request_user_email}: {e}")
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
