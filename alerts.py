"""Price alerts management with Supabase"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field, EmailStr
from pydantic.functional_validators import model_validator
from typing import List, Optional
from supabase import create_client, Client
from config import config
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Initialize Supabase client
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

class CreateAlertRequest(BaseModel):
    user_email: EmailStr
    from_iata: str = Field(..., min_length=3, max_length=3)
    to_iata: str = Field(..., min_length=3, max_length=3)
    max_price: float = Field(..., gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    # Legacy exact-date field (kept for backward compatibility)
    departure_date: Optional[str] = None
    # Flexible-date range fields (Elite/Business tier)
    departure_start_date: Optional[str] = None
    departure_end_date: Optional[str] = None
    notification_channels: List[str] = Field(default=["email"])
    phone: Optional[str] = None
    # Points-based threshold (Business tier only); stored alongside max_price
    max_points: Optional[int] = Field(None, gt=0)
    # Post-Booking Travel Credit Engine fields
    is_purchased: bool = Field(False)
    purchase_price: Optional[float] = Field(None, gt=0)
    airline: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def coerce_channels(cls, data):
        # Accept legacy "channels" field as an alias for notification_channels
        if isinstance(data, dict):
            if 'channels' in data and 'notification_channels' not in data:
                data = dict(data)
                data['notification_channels'] = data.pop('channels')
        return data

@router.post("/create", status_code=201)
async def create_alert(alert: CreateAlertRequest):
    """Create a new price alert"""
    try:
        # Validate phone if SMS/WhatsApp selected
        if ("sms" in alert.notification_channels or "whatsapp" in alert.notification_channels):
            if not alert.phone:
                raise HTTPException(
                    status_code=400,
                    detail="Phone number required for SMS/WhatsApp alerts"
                )

        # Insert into Supabase
        result = supabase.table('price_alerts').insert({
            'user_email': alert.user_email,
            'from_iata': alert.from_iata.upper(),
            'to_iata': alert.to_iata.upper(),
            'max_price': alert.max_price,
            'currency': alert.currency.upper(),
            'departure_date': alert.departure_date,
            'departure_start_date': alert.departure_start_date,
            'departure_end_date': alert.departure_end_date,
            'notification_channels': alert.notification_channels,
            'phone': alert.phone,
            'active': True,
            'max_points': alert.max_points,
            'is_purchased': alert.is_purchased,
            'purchase_price': alert.purchase_price,
            'airline': alert.airline,
        }).execute()

        if result.data:
            logger.info(f"Created alert {result.data[0]['id']} for {alert.user_email}")
            return {
                "success": True,
                "alert_id": result.data[0]['id'],
                "message": f"Alert created successfully for {alert.from_iata} → {alert.to_iata}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create alert")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        raise HTTPException(status_code=500, detail=f"Alert creation failed: {str(e)}")

@router.get("/list")
async def list_alerts(
    user_email: str,
    active_only: bool = True
):
    """List user's price alerts"""
    try:
        query = supabase.table('price_alerts').select('*').eq('user_email', user_email)

        if active_only:
            query = query.eq('active', True)

        result = query.order('created_at', desc=True).execute()

        return {
            "count": len(result.data),
            "alerts": result.data
        }

    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")

@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, user_email: str):
    """Deactivate a price alert"""
    try:
        # Verify ownership
        existing = supabase.table('price_alerts').select('*').eq('id', alert_id).eq('user_email', user_email).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Alert not found or unauthorized")

        # Soft delete by setting active=false
        result = supabase.table('price_alerts').update({'active': False}).eq('id', alert_id).execute()

        if result.data:
            logger.info(f"Deactivated alert {alert_id}")
            return {"success": True, "message": "Alert deactivated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to deactivate alert")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")

@router.get("/stats")
async def get_alert_stats():
    """Get alert statistics"""
    try:
        total = supabase.table('price_alerts').select('id', count='exact').execute()
        active = supabase.table('price_alerts').select('id', count='exact').eq('active', True).execute()
        triggered = supabase.table('price_alerts').select('id', count='exact').not_.is_('triggered_at', 'null').execute()

        return {
            "total_alerts": total.count,
            "active_alerts": active.count,
            "triggered_alerts": triggered.count
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"total_alerts": 0, "active_alerts": 0, "triggered_alerts": 0}
