"""Shared FastAPI authentication dependencies for FlightAlertPro."""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import config

import logging

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str   # JWT 'sub' claim
    email: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
    """Verify the Supabase JWT and return the authenticated user context."""
    if not config.SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=500, detail="Server authentication not configured")
    try:
        payload = jwt.decode(
            credentials.credentials,
            config.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: Optional[str] = payload.get("sub")
        email: Optional[str] = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Token does not contain email")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token does not contain user id")
        return CurrentUser(user_id=user_id, email=email)
    except JWTError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
