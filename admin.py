from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List
import logging
from datetime import datetime, timedelta
from supabase import create_client
from backend.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

def get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

@router.get("/metrics")
async def get_metrics():
    try:
        supabase = get_supabase()

        provider_metrics = supabase.table('provider_metrics').select('*').order('date', desc=True).limit(100).execute()

        analytics = supabase.table('analytics_events').select('event_type').execute()

        event_counts = {}
        for event in analytics.data:
            event_type = event.get('event_type')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        notifications = supabase.table('notification_log').select('status').execute()

        notif_stats = {
            'sent': len([n for n in notifications.data if n.get('status') == 'sent']),
            'failed': len([n for n in notifications.data if n.get('status') == 'failed']),
            'queued': len([n for n in notifications.data if n.get('status') == 'queued'])
        }

        return {
            "provider_metrics": provider_metrics.data,
            "event_counts": event_counts,
            "notification_stats": notif_stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/quota")
async def get_user_quota(user_id: str):
    try:
        supabase = get_supabase()

        result = supabase.table('users').select('api_calls_count, notification_credits, plan').eq('id', user_id).single().execute()

        return result.data

    except Exception as e:
        logger.error(f"Error fetching quota: {str(e)}")
        raise HTTPException(status_code=404, detail="User not found")

@router.post("/users/{user_id}/quota")
async def update_user_quota(user_id: str, api_calls_count: int = None, notification_credits: int = None):
    try:
        supabase = get_supabase()

        updates = {}
        if api_calls_count is not None:
            updates['api_calls_count'] = api_calls_count
        if notification_credits is not None:
            updates['notification_credits'] = notification_credits

        result = supabase.table('users').update(updates).eq('id', user_id).execute()

        logger.info(f"Updated quota for user {user_id}: {updates}")

        return {"status": "updated", "user_id": user_id, "updates": updates}

    except Exception as e:
        logger.error(f"Error updating quota: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experiments")
async def list_experiments():
    try:
        supabase = get_supabase()

        result = supabase.table('experiments').select('*').execute()

        return result.data

    except Exception as e:
        logger.error(f"Error fetching experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/experiments")
async def create_experiment(name: str, variants: Dict):
    try:
        supabase = get_supabase()

        result = supabase.table('experiments').insert({
            'name': name,
            'variants': variants,
            'is_active': True
        }).execute()

        logger.info(f"Created experiment: {name}")

        return result.data[0]

    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
