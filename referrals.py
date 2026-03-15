"""Referral program - generate shareable codes and track usage (revenue feature)"""
import hashlib
import logging
import secrets as secrets_lib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/referrals", tags=["referrals"])

# Per-referral reward credited to the referrer (USD)
REFERRAL_CREDIT_USD: float = 10.0
# Discount on first paid plan upgrade for the referred user (USD)
REFERRAL_BONUS_USD: float = 5.0

# In-memory fallback stores
_CODES: dict = {}        # code -> {user_email, created_at, uses, credits_earned_usd}
_EMAIL_TO_CODE: dict = {}  # user_email -> code


def _make_code(email: str) -> str:
    raw = f"{email}-{datetime.utcnow().isoformat()}-{secrets_lib.token_hex(8)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def _load_from_db(email: str) -> Optional[dict]:
    """Return existing DB row for *email* or None."""
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            result = sb.table("referral_codes").select("*").eq("user_email", email).execute()
            if result.data:
                return result.data[0]
    except Exception as exc:
        logger.debug(f"DB referral lookup failed: {exc}")
    return None


def _load_code_from_db(code: str) -> Optional[dict]:
    """Return existing DB row for *code* or None."""
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            result = sb.table("referral_codes").select("*").eq("code", code).execute()
            if result.data:
                return result.data[0]
    except Exception as exc:
        logger.debug(f"DB code lookup failed: {exc}")
    return None


class GenerateCodeRequest(BaseModel):
    user_email: EmailStr


class UseCodeRequest(BaseModel):
    referral_code: str
    new_user_email: EmailStr


@router.post("/generate")
async def generate_referral_code(request: GenerateCodeRequest):
    """
    Generate (or return) the referral code for a user.

    Each user gets exactly one shareable code.  When a referred friend upgrades
    to any paid plan, the referrer earns a ${REFERRAL_CREDIT_USD} account credit.
    """
    email = request.user_email.lower()

    # Return cached code
    if email in _EMAIL_TO_CODE:
        code = _EMAIL_TO_CODE[email]
        data = _CODES.get(code, {})
        return _build_response(code, data, "Your existing referral code")

    # Check DB
    row = _load_from_db(email)
    if row:
        code = row["code"]
        _EMAIL_TO_CODE[email] = code
        _CODES[code] = row
        return _build_response(code, row, "Your existing referral code")

    # Create new code
    code = _make_code(email)
    now = datetime.utcnow().isoformat()
    data = {
        "user_email": email,
        "code": code,
        "created_at": now,
        "uses": 0,
        "credits_earned_usd": 0.0,
    }
    _CODES[code] = data
    _EMAIL_TO_CODE[email] = code

    # Persist
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            sb.table("referral_codes").insert(data).execute()
    except Exception as exc:
        logger.debug(f"Could not persist referral code: {exc}")

    msg = (
        f"New referral code generated! "
        f"Earn ${REFERRAL_CREDIT_USD:.0f} credit for every friend who upgrades."
    )
    return _build_response(code, data, msg)


@router.post("/use")
async def use_referral_code(request: UseCodeRequest):
    """
    Apply a referral code when a new user signs up.

    The referred user receives a ${REFERRAL_BONUS_USD} discount on their first upgrade.
    The referrer's usage counter is incremented (credits are added on upgrade).
    """
    code = request.referral_code.strip().upper()
    new_email = request.new_user_email.lower()

    data = _CODES.get(code) or _load_code_from_db(code)
    if not data:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    referrer = (data.get("user_email") or "").lower()
    if referrer == new_email:
        raise HTTPException(status_code=400, detail="You cannot use your own referral code")

    # Increment uses
    new_uses = data.get("uses", 0) + 1
    if code in _CODES:
        _CODES[code]["uses"] = new_uses
    try:
        from supabase import create_client
        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            sb = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            sb.table("referral_codes").update({"uses": new_uses}).eq("code", code).execute()
    except Exception as exc:
        logger.debug(f"Could not update referral usage: {exc}")

    return {
        "success": True,
        "referrer_email": referrer,
        "new_user_bonus_usd": REFERRAL_BONUS_USD,
        "message": (
            f"Referral code applied! "
            f"You'll receive a ${REFERRAL_BONUS_USD:.0f} discount on your first plan upgrade."
        ),
    }


@router.get("/stats")
async def get_referral_stats(user_email: str = Query(..., description="User email")):
    """Get referral statistics for the requesting user."""
    email = user_email.lower()
    code = _EMAIL_TO_CODE.get(email)

    if not code:
        row = _load_from_db(email)
        if row:
            code = row["code"]
            _EMAIL_TO_CODE[email] = code
            _CODES[code] = row

    if not code:
        return {
            "has_code": False,
            "code": None,
            "uses": 0,
            "credits_earned_usd": 0.0,
            "referral_link": None,
            "per_referral_credit_usd": REFERRAL_CREDIT_USD,
        }

    data = _CODES.get(code, {})
    return {
        "has_code": True,
        **_build_response(code, data, ""),
        "per_referral_credit_usd": REFERRAL_CREDIT_USD,
    }


def _build_response(code: str, data: dict, message: str) -> dict:
    return {
        "code": code,
        "uses": data.get("uses", 0),
        "credits_earned_usd": data.get("credits_earned_usd", 0.0),
        "referral_link": f"https://flightalertpro.com/signup?ref={code}",
        "message": message,
    }
