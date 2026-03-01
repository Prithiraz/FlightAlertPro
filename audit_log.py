"""Lightweight audit logging for sensitive actions.

Usage::

    from audit_log import audit

    # inside an async FastAPI handler
    await audit(
        action="alert.create",
        user_id=user.user_id,
        email=user.email,
        target_type="price_alert",
        target_id=alert_id,
        request=request,   # optional FastAPI Request for IP / UA
        metadata={"from": "LHR", "to": "JFK"},
    )

The function is best-effort: any database error is caught and logged but
never re-raised so that a failed audit write never breaks the main request.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Lazily initialised Supabase client so that importing this module before the
# config is ready doesn't blow up.
_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            from config import config
            if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
                _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        except Exception as exc:
            logger.debug("Could not create Supabase client for audit: %s", exc)
    return _supabase


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    """One-way hash of an IP address for GDPR-friendly storage."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


async def audit(
    action: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    request=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one audit log entry.  Never raises."""
    ip_hash: Optional[str] = None
    user_agent: Optional[str] = None

    if request is not None:
        try:
            ip = request.client.host if request.client else None
            ip_hash = _hash_ip(ip)
            user_agent = request.headers.get("user-agent", "")[:256]
        except Exception:
            pass

    row = {
        "action": action,
        "user_id": user_id,
        "email": email,
        "target_type": target_type,
        "target_id": target_id,
        "ip_hash": ip_hash,
        "user_agent": user_agent,
        "metadata": metadata,
    }

    try:
        client = _get_supabase()
        if client:
            client.table("audit_log").insert(row).execute()
        else:
            logger.info("audit (no-db): %s", row)
    except Exception as exc:
        logger.warning("Failed to write audit log entry: %s", exc)
