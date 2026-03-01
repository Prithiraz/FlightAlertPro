"""Alert templates endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alert-templates", tags=["alert-templates"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


class AlertTemplateRequest(BaseModel):
    name: str
    template_json: dict


@router.get("")
async def list_alert_templates(user: CurrentUser = Depends(get_current_user)):
    """List all alert templates for the authenticated user."""
    try:
        result = (
            supabase.table("alert_templates")
            .select("*")
            .eq("user_id", user.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"templates": result.data or []}
    except Exception as exc:
        logger.warning("Could not list alert templates for %s: %s", user.user_id, exc)
        return {"templates": []}


@router.post("", status_code=201)
async def create_alert_template(
    body: AlertTemplateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Save a new alert template for the authenticated user."""
    try:
        result = (
            supabase.table("alert_templates")
            .insert({
                "user_id": user.user_id,
                "name": body.name,
                "template_json": body.template_json,
            })
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        logger.error("Could not save alert template for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to save template")


@router.delete("/{template_id}", status_code=204)
async def delete_alert_template(
    template_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Delete an alert template owned by the authenticated user."""
    try:
        existing = (
            supabase.table("alert_templates")
            .select("id")
            .eq("id", template_id)
            .eq("user_id", user.user_id)
            .maybe_single()
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Template not found")
        supabase.table("alert_templates").delete().eq("id", template_id).execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not delete alert template %s: %s", template_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete template")
