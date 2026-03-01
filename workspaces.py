"""Workspace management endpoints for FlightAlertPro Enterprise/Business tier."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from supabase import create_client, Client

from audit_log import audit
from auth_deps import CurrentUser, get_current_user
from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

_ALL_ROLES: Set[str] = {"owner", "admin", "member", "viewer"}
_ADMIN_ROLES: Set[str] = {"owner", "admin"}


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Membership helpers
# ---------------------------------------------------------------------------

def _get_membership(supabase: Client, workspace_id: str, user_id: str) -> Optional[dict]:
    """Return the membership row for (workspace_id, user_id) or None."""
    try:
        result = (
            supabase.table("workspace_memberships")
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.debug("Could not fetch membership %s/%s: %s", workspace_id, user_id, exc)
        return None


def _require_role(
    supabase: Client, workspace_id: str, user_id: str, allowed: Set[str]
) -> dict:
    """Assert the user has one of the allowed roles; raise HTTP 403/404 otherwise."""
    membership = _get_membership(supabase, workspace_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found or access denied")
    if membership.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return membership


def _ensure_personal_workspace(supabase: Client, user: CurrentUser) -> Optional[dict]:
    """Lazily create a personal workspace for the user if they have none."""
    try:
        existing = (
            supabase.table("workspace_memberships")
            .select("workspace_id")
            .eq("user_id", user.user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return None  # user already has at least one workspace
    except Exception as exc:
        logger.debug("Could not check existing workspaces for %s: %s", user.user_id, exc)
        return None

    workspace_name = user.email.split("@")[0].split("+")[0] + "'s Workspace" if "@" in user.email else "Personal Workspace"
    try:
        ws_result = supabase.table("workspaces").insert(
            {"name": workspace_name, "owner_user_id": user.user_id, "plan": "free"}
        ).execute()
        if not ws_result.data:
            return None
        workspace = ws_result.data[0]
        supabase.table("workspace_memberships").insert(
            {"workspace_id": workspace["id"], "user_id": user.user_id, "role": "owner"}
        ).execute()
        logger.info("Auto-created personal workspace for user %s", user.user_id)
        return workspace
    except Exception as exc:
        logger.warning("Could not auto-create workspace for %s: %s", user.user_id, exc)
        return None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class InviteRequest(BaseModel):
    email: str
    role: str = Field("member", pattern="^(admin|member|viewer)$")


class AcceptInviteRequest(BaseModel):
    token: str


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|member|viewer)$")


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_workspaces(user: CurrentUser = Depends(get_current_user)):
    """List workspaces the current user belongs to.
    Auto-creates a personal workspace on first call if the user has none."""
    supabase = _get_supabase()

    try:
        result = (
            supabase.table("workspace_memberships")
            .select("role, workspaces(id, name, plan, owner_user_id, created_at)")
            .eq("user_id", user.user_id)
            .execute()
        )
        workspaces = []
        for row in (result.data or []):
            ws = row.get("workspaces") or {}
            workspaces.append({**ws, "my_role": row.get("role")})

        if not workspaces:
            # Lazy-create personal workspace
            ws = _ensure_personal_workspace(supabase, user)
            if ws:
                workspaces = [{**ws, "my_role": "owner"}]

        return {"workspaces": workspaces}
    except Exception as exc:
        logger.error("Could not list workspaces for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list workspaces")


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new workspace (Business/Elite plan required for additional workspaces)."""
    supabase = _get_supabase()

    # Determine user's plan
    plan = "free"
    try:
        pr = (
            supabase.table("user_profiles")
            .select("plan")
            .eq("email", user.email)
            .maybe_single()
            .execute()
        )
        plan = (pr.data or {}).get("plan", "free") or "free"
    except Exception:
        pass

    if plan not in ("business", "elite"):
        raise HTTPException(
            status_code=403,
            detail="Creating additional workspaces requires a Business or Elite plan",
        )

    try:
        ws_result = supabase.table("workspaces").insert(
            {"name": body.name, "owner_user_id": user.user_id, "plan": plan}
        ).execute()
        if not ws_result.data:
            raise HTTPException(status_code=500, detail="Failed to create workspace")

        workspace = ws_result.data[0]
        supabase.table("workspace_memberships").insert(
            {"workspace_id": workspace["id"], "user_id": user.user_id, "role": "owner"}
        ).execute()

        await audit(
            action="workspace.create",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace",
            target_id=workspace["id"],
            request=request,
            metadata={"name": body.name},
        )
        return workspace
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not create workspace: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create workspace")


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List all members of a workspace."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ALL_ROLES)

    try:
        result = (
            supabase.table("workspace_memberships")
            .select("id, user_id, role, created_at")
            .eq("workspace_id", workspace_id)
            .execute()
        )
        return {"members": result.data or []}
    except Exception as exc:
        logger.error("Could not list members for workspace %s: %s", workspace_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list members")


@router.post("/{workspace_id}/invite", status_code=201)
async def invite_member(
    workspace_id: str,
    body: InviteRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Invite a user to a workspace by email (owner/admin only)."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    token = secrets.token_urlsafe(32)
    try:
        result = supabase.table("workspace_invites").insert({
            "workspace_id": workspace_id,
            "invited_email": body.email,
            "role": body.role,
            "token": token,
            "invited_by": user.user_id,
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invite")

        await audit(
            action="workspace.invite",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace",
            target_id=workspace_id,
            request=request,
            metadata={"invited_email": body.email, "role": body.role},
        )
        return {
            "invite_id": result.data[0]["id"],
            "token": token,
            "invited_email": body.email,
            "role": body.role,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not create invite: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create invite")


@router.post("/invites/accept")
async def accept_invite(
    body: AcceptInviteRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Accept a workspace invite using the invite token."""
    supabase = _get_supabase()
    try:
        invite_result = (
            supabase.table("workspace_invites")
            .select("*")
            .eq("token", body.token)
            .is_("accepted_at", "null")
            .maybe_single()
            .execute()
        )
        if not invite_result.data:
            raise HTTPException(status_code=404, detail="Invalid or already used invite token")

        invite = invite_result.data
        workspace_id = invite["workspace_id"]

        # Check if user is already a member
        existing = _get_membership(supabase, workspace_id, user.user_id)
        if existing:
            raise HTTPException(status_code=409, detail="Already a member of this workspace")

        supabase.table("workspace_memberships").insert({
            "workspace_id": workspace_id,
            "user_id": user.user_id,
            "role": invite["role"],
        }).execute()

        supabase.table("workspace_invites").update(
            {"accepted_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", invite["id"]).execute()

        return {"success": True, "workspace_id": workspace_id, "role": invite["role"]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not accept invite: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to accept invite")


@router.patch("/{workspace_id}/members/{member_id}")
async def update_member_role(
    workspace_id: str,
    member_id: str,
    body: UpdateRoleRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Update a workspace member's role (owner/admin only)."""
    supabase = _get_supabase()
    requester = _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    # Only owner can grant admin role
    if body.role == "admin" and requester.get("role") != "owner":
        raise HTTPException(
            status_code=403, detail="Only the workspace owner can assign the admin role"
        )

    try:
        result = (
            supabase.table("workspace_memberships")
            .update({"role": body.role})
            .eq("id", member_id)
            .eq("workspace_id", workspace_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Member not found")

        await audit(
            action="workspace.role_change",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace_membership",
            target_id=member_id,
            request=request,
            metadata={"workspace_id": workspace_id, "new_role": body.role},
        )
        return {"success": True, "member_id": member_id, "role": body.role}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not update member role: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update role")


@router.delete("/{workspace_id}/members/{member_id}")
async def remove_member(
    workspace_id: str,
    member_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Remove a member from a workspace (owner/admin only)."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    try:
        target = (
            supabase.table("workspace_memberships")
            .select("*")
            .eq("id", member_id)
            .eq("workspace_id", workspace_id)
            .maybe_single()
            .execute()
        )
        if not target.data:
            raise HTTPException(status_code=404, detail="Member not found")
        if target.data.get("role") == "owner":
            raise HTTPException(status_code=403, detail="Cannot remove the workspace owner")

        supabase.table("workspace_memberships").delete().eq("id", member_id).execute()

        await audit(
            action="workspace.remove_member",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace_membership",
            target_id=member_id,
            request=request,
            metadata={"workspace_id": workspace_id},
        )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not remove member: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to remove member")


# ---------------------------------------------------------------------------
# API keys (Business tier)
# ---------------------------------------------------------------------------

@router.post("/{workspace_id}/api-keys", status_code=201)
async def create_api_key(
    workspace_id: str,
    body: CreateApiKeyRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a workspace API key. Business/Elite tier, owner/admin only.
    The plaintext key is returned once and never stored."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    # Verify workspace is on Business/Elite plan
    try:
        ws = (
            supabase.table("workspaces")
            .select("plan")
            .eq("id", workspace_id)
            .single()
            .execute()
        )
        if (ws.data or {}).get("plan") not in ("business", "elite"):
            raise HTTPException(
                status_code=403, detail="API keys require a Business or Elite plan workspace"
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not verify workspace plan: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to verify workspace plan")

    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12]

    try:
        result = supabase.table("workspace_api_keys").insert({
            "workspace_id": workspace_id,
            "name": body.name,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "created_by": user.user_id,
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create API key")

        await audit(
            action="api_key.create",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace_api_key",
            target_id=result.data[0]["id"],
            request=request,
            metadata={"workspace_id": workspace_id, "name": body.name},
        )
        return {
            "api_key": raw_key,
            "key_id": result.data[0]["id"],
            "key_prefix": key_prefix,
            "name": body.name,
            "warning": "Save this key securely — it will not be shown again.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not create API key: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/{workspace_id}/api-keys")
async def list_api_keys(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List active API keys for a workspace (masked, owner/admin only)."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    try:
        result = (
            supabase.table("workspace_api_keys")
            .select("id, name, key_prefix, last_used_at, created_at, created_by")
            .eq("workspace_id", workspace_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .execute()
        )
        return {"api_keys": result.data or []}
    except Exception as exc:
        logger.error("Could not list API keys: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/{workspace_id}/api-keys/{key_id}")
async def revoke_api_key(
    workspace_id: str,
    key_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Revoke a workspace API key (owner/admin only)."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ADMIN_ROLES)

    try:
        result = (
            supabase.table("workspace_api_keys")
            .update({"revoked_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", key_id)
            .eq("workspace_id", workspace_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="API key not found")

        await audit(
            action="api_key.revoke",
            user_id=user.user_id,
            email=user.email,
            target_type="workspace_api_key",
            target_id=key_id,
            request=request,
            metadata={"workspace_id": workspace_id},
        )
        return {"success": True, "key_id": key_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not revoke API key: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------

@router.get("/{workspace_id}/usage")
async def get_workspace_usage(
    workspace_id: str,
    range: str = "7d",
    user: CurrentUser = Depends(get_current_user),
):
    """Get aggregated usage metrics for a workspace."""
    supabase = _get_supabase()
    _require_role(supabase, workspace_id, user.user_id, _ALL_ROLES)

    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(range, 7)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    usage: dict = {}
    for event_type in ("search", "alert_check", "notification"):
        try:
            result = (
                supabase.table("usage_events")
                .select("id", count="exact")
                .eq("workspace_id", workspace_id)
                .eq("type", event_type)
                .gte("ts", since)
                .execute()
            )
            usage[event_type] = result.count or 0
        except Exception:
            usage[event_type] = 0

    return {
        "workspace_id": workspace_id,
        "range": range,
        "usage": usage,
        "since": since,
    }


# ---------------------------------------------------------------------------
# X-API-Key validation utility (used by middleware in main.py)
# ---------------------------------------------------------------------------

def validate_workspace_api_key(raw_key: str) -> Optional[dict]:
    """Validate an X-API-Key value against workspace_api_keys.
    Returns the workspace_api_keys row (with workspace_id) or None."""
    try:
        supabase = _get_supabase()
        key_hash = _hash_key(raw_key)
        result = (
            supabase.table("workspace_api_keys")
            .select("id, workspace_id, workspaces(plan)")
            .eq("key_hash", key_hash)
            .is_("revoked_at", "null")
            .maybe_single()
            .execute()
        )
        if not result.data:
            return None
        # Update last_used_at
        supabase.table("workspace_api_keys").update(
            {"last_used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", result.data["id"]).execute()
        return result.data
    except Exception as exc:
        logger.debug("API key validation error: %s", exc)
        return None
