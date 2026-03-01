"""
Admin incident management endpoints.

All routes require admin authentication.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_deps import CurrentUser, require_admin
from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/incidents", tags=["incidents"])


def _get_supabase():
    from supabase import create_client
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "minor"  # minor | major | critical
    components: Optional[List[str]] = None
    status: str = "investigating"


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    components: Optional[List[str]] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
async def list_incidents(
    limit: int = 50,
    admin: CurrentUser = Depends(require_admin),
) -> Dict[str, Any]:
    supabase = _get_supabase()
    rows = (
        supabase.table("incidents")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"incidents": rows.data or []}


@router.post("", status_code=201)
async def create_incident(
    body: IncidentCreate,
    admin: CurrentUser = Depends(require_admin),
) -> Dict[str, Any]:
    if body.severity not in ("minor", "major", "critical"):
        raise HTTPException(status_code=400, detail="severity must be minor, major, or critical")
    if body.status not in ("investigating", "identified", "monitoring", "resolved"):
        raise HTTPException(status_code=400, detail="invalid status value")

    supabase = _get_supabase()
    row = {
        "title": body.title,
        "description": body.description,
        "severity": body.severity,
        "components_json": body.components,
        "status": body.status,
        "created_by": admin.email,
    }
    result = supabase.table("incidents").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create incident")
    return result.data[0]


@router.patch("/{incident_id}")
async def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    admin: CurrentUser = Depends(require_admin),
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.description is not None:
        updates["description"] = body.description
    if body.severity is not None:
        if body.severity not in ("minor", "major", "critical"):
            raise HTTPException(status_code=400, detail="invalid severity")
        updates["severity"] = body.severity
    if body.components is not None:
        updates["components_json"] = body.components
    if body.status is not None:
        if body.status not in ("investigating", "identified", "monitoring", "resolved"):
            raise HTTPException(status_code=400, detail="invalid status")
        updates["status"] = body.status

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    supabase = _get_supabase()
    result = (
        supabase.table("incidents")
        .update(updates)
        .eq("id", incident_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result.data[0]


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    result = (
        supabase.table("incidents")
        .update({"status": "resolved", "ended_at": now, "updated_at": now})
        .eq("id", incident_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result.data[0]
