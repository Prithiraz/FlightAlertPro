from fastapi import APIRouter, HTTPException
import logging
import json
from supabase import create_client
from config import config
from email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["gdpr"])

def get_supabase():
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

@router.post("/export")
async def export_user_data(user_id: str, email: str):
    try:
        supabase = get_supabase()

        user_result = supabase.table('users').select('*').eq('id', user_id).eq('email', email).single().execute()

        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")

        data = {
            'user': user_result.data,
            'alerts': supabase.table('alerts').select('*').eq('user_id', user_id).execute().data,
            'notification_log': supabase.table('notification_log').select('*').eq('user_id', user_id).execute().data,
            'payments': supabase.table('payments').select('*').eq('user_id', user_id).execute().data,
            'api_keys': supabase.table('user_api_keys').select('id, key_prefix, name, created_at').eq('user_id', user_id).execute().data
        }

        export_json = json.dumps(data, indent=2, default=str)

        email_body = f"""Your data export is ready.

Total records:
- Alerts: {len(data['alerts'])}
- Notifications: {len(data['notification_log'])}
- Payments: {len(data['payments'])}
- API Keys: {len(data['api_keys'])}

Data export attached as JSON."""

        email_service.send_email(email, "Your Data Export", email_body)

        logger.info(f"Data exported for user {user_id}")

        return {
            "status": "exported",
            "user_id": user_id,
            "data": data
        }

    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete")
async def delete_user_data(user_id: str, email: str, confirmation: str):
    if confirmation != "DELETE_MY_DATA":
        raise HTTPException(status_code=400, detail="Invalid confirmation")

    try:
        supabase = get_supabase()

        user_result = supabase.table('users').select('*').eq('id', user_id).eq('email', email).single().execute()

        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")

        supabase.table('alerts').delete().eq('user_id', user_id).execute()
        supabase.table('user_api_keys').delete().eq('user_id', user_id).execute()
        supabase.table('payments').delete().eq('user_id', user_id).execute()
        supabase.table('notification_log').delete().eq('user_id', user_id).execute()
        supabase.table('experiment_assignments').delete().eq('user_id', user_id).execute()

        supabase.table('users').delete().eq('id', user_id).execute()

        logger.info(f"User data deleted: {user_id}")

        email_service.send_email(email, "Data Deletion Confirmation", "Your account and all associated data have been permanently deleted.")

        return {
            "status": "deleted",
            "user_id": user_id,
            "message": "All user data has been permanently deleted"
        }

    except Exception as e:
        logger.error(f"Error deleting data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
