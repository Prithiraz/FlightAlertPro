"""Events tracking endpoint – stores funnel/growth events for analytics."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
import logging
import hashlib

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["events"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

# Key funnel events tracked for growth dashboard
ALLOWED_EVENTS = {
    "landing_view", "pricing_view", "signup_start", "signup_complete",
    "first_search", "first_alert_created", "upgrade_click",
    "checkout_started", "paid_success",
}


class EventPayload(BaseModel):
    event_name: str
    props_json: Optional[Dict[str, Any]] = None


def _try_get_current_user(request: Request) -> Optional[CurrentUser]:
    """Best-effort auth extraction – returns None for unauthenticated callers."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt, JWTError
        token = auth_header.split(" ", 1)[1]
        payload = jwt.decode(
            token,
            config.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        uid = payload.get("sub")
        email = payload.get("email")
        if uid and email:
            return CurrentUser(user_id=uid, email=email)
    except Exception:
        pass
    return None


@router.post("/events")
async def record_event(body: EventPayload, request: Request):
    """Record a funnel event. Auth optional – anonymous events are stored with user_id=null."""
    event_name = body.event_name
    if event_name not in ALLOWED_EVENTS:
        # Silently ignore unknown events rather than erroring
        return {"ok": True}

    user = _try_get_current_user(request)
    user_id = user.user_id if user else None

    try:
        supabase.table("growth_events").insert({
            "event_name": event_name,
            "user_id": user_id,
            "props_json": body.props_json or {},
        }).execute()
    except Exception as exc:
        logger.debug("Could not record event %s: %s", event_name, exc)

    return {"ok": True}
