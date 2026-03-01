"""Price alerts management with Supabase"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field, field_validator
from pydantic.functional_validators import model_validator
from typing import List, Optional
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
from entitlements import get_plan_limits
from audit_log import audit
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Initialize Supabase client
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


_ALLOWED_CHANNELS = frozenset({"email", "sms", "whatsapp", "telegram", "push"})


def get_current_user_email(user: CurrentUser = Depends(get_current_user)) -> str:
    """Compatibility shim: return only the email from the current user context."""
    return user.email

class CreateAlertRequest(BaseModel):
    from_iata: str = Field(..., min_length=3, max_length=3, pattern=r'^[A-Za-z]{3}$')
    to_iata: str = Field(..., min_length=3, max_length=3, pattern=r'^[A-Za-z]{3}$')
    max_price: float = Field(..., gt=0)
    currency: str = Field("USD", min_length=3, max_length=3, pattern=r'^[A-Za-z]{3}$')
    departure_date: Optional[str] = None
    notification_channels: List[str] = Field(default=["email"])
    phone: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def coerce_channels(cls, data):
        # Accept legacy "channels" field as an alias for notification_channels
        if isinstance(data, dict):
            if 'channels' in data and 'notification_channels' not in data:
                data = dict(data)
                data['notification_channels'] = data.pop('channels')
        return data

    @field_validator('notification_channels')
    @classmethod
    def validate_channels(cls, v):
        invalid = [c for c in v if c not in _ALLOWED_CHANNELS]
        if invalid:
            raise ValueError(f"Invalid notification channels: {invalid}. Allowed: {sorted(_ALLOWED_CHANNELS)}")
        return v

@router.post("/create", status_code=201)
async def create_alert(
    alert: CreateAlertRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new price alert"""
    user_email = user.email
    try:
        # Validate phone if SMS/WhatsApp selected
        if ("sms" in alert.notification_channels or "whatsapp" in alert.notification_channels):
            if not alert.phone:
                raise HTTPException(
                    status_code=400,
                    detail="Phone number required for SMS/WhatsApp alerts"
                )

        # Determine the user's plan limit for active alerts.
        plan = "free"
        try:
            plan_result = (
                supabase.table("user_profiles")
                .select("plan")
                .eq("email", user_email)
                .maybe_single()
                .execute()
            )
            if plan_result.data and plan_result.data.get("plan"):
                plan = plan_result.data["plan"]
        except Exception as exc:
            logger.debug("Could not fetch plan for %s: %s", user_email, exc)
        max_alerts = get_plan_limits(plan)["max_active_alerts"]

        # Enforce per-user active alert limit (anti-abuse).
        # This application-level check gives callers a clear 429 error.
        # For strict enforcement under concurrent load, pair this with a
        # database-level CHECK constraint or trigger on the price_alerts table.
        count_result = (
            supabase.table('price_alerts')
            .select('id', count='exact')
            .eq('user_email', user_email)
            .eq('active', True)
            .execute()
        )
        if (count_result.count or 0) >= max_alerts:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum of {max_alerts} active alerts reached for the {plan} plan"
            )

        # Insert into Supabase
        result = supabase.table('price_alerts').insert({
            'user_email': user_email,
            'from_iata': alert.from_iata.upper(),
            'to_iata': alert.to_iata.upper(),
            'max_price': alert.max_price,
            'currency': alert.currency.upper(),
            'departure_date': alert.departure_date,
            'notification_channels': alert.notification_channels,
            'phone': alert.phone,
            'active': True
        }).execute()

        if result.data:
            alert_id = result.data[0]['id']
            logger.info(f"Created alert {alert_id} for {user_email}")
            await audit(
                action="alert.create",
                user_id=user.user_id,
                email=user_email,
                target_type="price_alert",
                target_id=alert_id,
                request=request,
                metadata={"from_iata": alert.from_iata.upper(), "to_iata": alert.to_iata.upper()},
            )
            return {
                "success": True,
                "alert_id": alert_id,
                "message": f"Alert created successfully for {alert.from_iata} → {alert.to_iata}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create alert")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        raise HTTPException(status_code=500, detail="Alert creation failed")

@router.get("/list")
async def list_alerts(
    active_only: bool = True,
    user_email: str = Depends(get_current_user_email),
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
async def delete_alert(
    alert_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Deactivate a price alert"""
    user_email = user.email
    try:
        # Verify ownership
        existing = supabase.table('price_alerts').select('*').eq('id', alert_id).eq('user_email', user_email).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Alert not found or unauthorized")

        # Soft delete by setting active=false
        result = supabase.table('price_alerts').update({'active': False}).eq('id', alert_id).execute()

        if result.data:
            logger.info(f"Deactivated alert {alert_id}")
            await audit(
                action="alert.delete",
                user_id=user.user_id,
                email=user_email,
                target_type="price_alert",
                target_id=alert_id,
                request=request,
            )
            return {"success": True, "message": "Alert deactivated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to deactivate alert")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete alert")

@router.get("/{alert_id}/history")
async def get_alert_history(
    alert_id: str,
    limit: int = 100,
    user_email: str = Depends(get_current_user_email),
):
    """Return price history points for a specific alert (owner only)."""
    try:
        # Verify ownership
        existing = (
            supabase.table('price_alerts')
            .select('id')
            .eq('id', alert_id)
            .eq('user_email', user_email)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Alert not found or unauthorized")

        result = (
            supabase.table('price_history')
            .select('id, checked_at, lowest_price, currency, provider')
            .eq('alert_id', alert_id)
            .order('checked_at', desc=True)
            .limit(max(1, min(limit, 500)))
            .execute()
        )
        return {"alert_id": alert_id, "history": result.data or []}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch history for alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve price history: {str(e)}")


@router.get("/stats")
async def get_alert_stats(user: CurrentUser = Depends(get_current_user)):
    """Get aggregate alert statistics (authenticated users only)."""
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
