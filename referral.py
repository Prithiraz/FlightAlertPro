"""Referral system – codes, tracking, and attribution."""
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
import logging
import hashlib
import secrets
import string

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/referral", tags=["referral"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def _ip_hash(request: Request) -> str:
    ip = (request.client.host if request.client else "") or "unknown"
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# GET /api/referral/my-code  (auth required)
# ---------------------------------------------------------------------------

@router.get("/my-code")
async def get_my_referral_code(user: CurrentUser = Depends(get_current_user)):
    """Return (or lazily create) the authenticated user's referral code."""
    try:
        result = (
            supabase.table("referral_codes")
            .select("code")
            .eq("user_id", user.user_id)
            .maybe_single()
            .execute()
        )
        if result.data:
            return {"code": result.data["code"]}

        # Create a new code
        code = _generate_code()
        supabase.table("referral_codes").insert({
            "user_id": user.user_id,
            "code": code,
        }).execute()
        return {"code": code}
    except Exception as exc:
        logger.error("referral/my-code error for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Could not fetch referral code")


# ---------------------------------------------------------------------------
# POST /api/referral/track  (public)
# ---------------------------------------------------------------------------

class TrackPayload(BaseModel):
    code: str
    event_type: str = "visit"   # visit | signup | paid


@router.post("/track")
async def track_referral(body: TrackPayload, request: Request):
    """Record a referral event (visit, signup, paid). Public – no auth needed."""
    allowed_types = {"visit", "signup", "paid"}
    if body.event_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid event_type")

    # Resolve referrer user_id from code
    referrer_user_id: Optional[str] = None
    try:
        r = (
            supabase.table("referral_codes")
            .select("user_id")
            .eq("code", body.code)
            .maybe_single()
            .execute()
        )
        if r.data:
            referrer_user_id = r.data["user_id"]
    except Exception as exc:
        logger.debug("Could not resolve referral code %s: %s", body.code, exc)

    try:
        supabase.table("referral_events").insert({
            "referrer_user_id": referrer_user_id,
            "code": body.code,
            "event_type": body.event_type,
            "ip_hash": _ip_hash(request),
            "user_agent": request.headers.get("user-agent", "")[:255],
        }).execute()
    except Exception as exc:
        logger.debug("Could not record referral event: %s", exc)

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/referral/claim  (auth required)
# ---------------------------------------------------------------------------

class ClaimPayload(BaseModel):
    code: str


@router.post("/claim")
async def claim_referral(body: ClaimPayload, user: CurrentUser = Depends(get_current_user)):
    """Attach a referral code to the signed-up user (only once)."""
    try:
        # Check if already attributed
        existing = (
            supabase.table("user_attribution")
            .select("user_id")
            .eq("user_id", user.user_id)
            .maybe_single()
            .execute()
        )
        if existing.data:
            return {"ok": True, "already_claimed": True}

        # Resolve referrer
        r = (
            supabase.table("referral_codes")
            .select("user_id")
            .eq("code", body.code)
            .maybe_single()
            .execute()
        )
        referrer_user_id: Optional[str] = r.data["user_id"] if r.data else None

        supabase.table("user_attribution").insert({
            "user_id": user.user_id,
            "referred_by_code": body.code,
            "referred_by_user_id": referrer_user_id,
        }).execute()

        # Also record a signup referral event
        supabase.table("referral_events").insert({
            "referrer_user_id": referrer_user_id,
            "code": body.code,
            "event_type": "signup",
            "ip_hash": None,
            "user_agent": None,
        }).execute()

        return {"ok": True, "claimed": True}
    except Exception as exc:
        logger.error("referral/claim error for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Could not claim referral")
