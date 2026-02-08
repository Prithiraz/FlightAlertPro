from fastapi import APIRouter, HTTPException, Header
import logging
import secrets
import hashlib
from typing import Optional
from supabase import create_client
from backend.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])

def get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

@router.post("/create")
async def create_api_key(user_id: str, name: str):
    try:
        supabase = get_supabase()

        user_result = supabase.table('users').select('plan').eq('id', user_id).single().execute()

        if user_result.data.get('plan') != 'business':
            raise HTTPException(status_code=403, detail="API keys only available for Business plan users")

        raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
        key_hash = hash_key(raw_key)
        key_prefix = raw_key[:12]

        result = supabase.table('user_api_keys').insert({
            'user_id': user_id,
            'key_hash': key_hash,
            'key_prefix': key_prefix,
            'name': name,
            'is_active': True
        }).execute()

        logger.info(f"API key created for user {user_id}: {key_prefix}")

        return {
            "api_key": raw_key,
            "key_id": result.data[0]['id'],
            "key_prefix": key_prefix,
            "name": name,
            "warning": "Save this key securely. It won't be shown again."
        }

    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_api_keys(user_id: str):
    try:
        supabase = get_supabase()

        result = supabase.table('user_api_keys').select('id, key_prefix, name, is_active, created_at, last_used_at').eq('user_id', user_id).execute()

        return result.data

    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{key_id}")
async def revoke_api_key(key_id: str, user_id: str):
    try:
        supabase = get_supabase()

        result = supabase.table('user_api_keys').update({'is_active': False}).eq('id', key_id).eq('user_id', user_id).execute()

        logger.info(f"API key {key_id} revoked for user {user_id}")

        return {"status": "revoked", "key_id": key_id}

    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def validate_api_key(x_api_key: Optional[str] = Header(None)) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    try:
        supabase = get_supabase()
        key_hash = hash_key(x_api_key)

        result = supabase.table('user_api_keys').select('*, users(plan, subscription_expires_at)').eq('key_hash', key_hash).eq('is_active', True).single().execute()

        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid API key")

        supabase.table('user_api_keys').update({'last_used_at': 'now()'}).eq('key_hash', key_hash).execute()

        return result.data

    except Exception as e:
        logger.error(f"API key validation error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid API key")
