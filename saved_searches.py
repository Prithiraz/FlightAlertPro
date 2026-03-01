"""Saved searches endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saved-searches", tags=["saved-searches"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


class SaveSearchRequest(BaseModel):
    name: str
    params_json: dict


@router.get("")
async def list_saved_searches(user: CurrentUser = Depends(get_current_user)):
    """List all saved searches for the authenticated user."""
    try:
        result = (
            supabase.table("saved_searches")
            .select("*")
            .eq("user_id", user.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"saved_searches": result.data or []}
    except Exception as exc:
        logger.warning("Could not list saved searches for %s: %s", user.user_id, exc)
        return {"saved_searches": []}


@router.post("", status_code=201)
async def create_saved_search(
    body: SaveSearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Save a new search for the authenticated user."""
    try:
        result = (
            supabase.table("saved_searches")
            .insert({
                "user_id": user.user_id,
                "name": body.name,
                "params_json": body.params_json,
            })
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        logger.error("Could not save search for %s: %s", user.user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to save search")


@router.delete("/{search_id}", status_code=204)
async def delete_saved_search(
    search_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a saved search owned by the authenticated user."""
    try:
        existing = (
            supabase.table("saved_searches")
            .select("id")
            .eq("id", search_id)
            .eq("user_id", user.user_id)
            .maybe_single()
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Saved search not found")
        supabase.table("saved_searches").delete().eq("id", search_id).execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not delete saved search %s: %s", search_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete saved search")
