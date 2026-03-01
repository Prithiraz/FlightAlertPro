"""Billing endpoints: Stripe checkout, portal, and subscription status."""
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client, Client
from config import config
from auth_deps import CurrentUser, get_current_user
from payments import payments_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

_VALID_PLANS = {"pro", "elite", "business"}

_FRONTEND_ORIGIN = (config.ALLOWED_ORIGINS[0] if config.ALLOWED_ORIGINS else "http://localhost:5173")


@router.post("/checkout")
async def create_checkout(
    plan: str = Query(..., description="Subscription plan: pro, elite, or business"),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a Stripe Checkout session for the requested plan."""
    if not payments_service.enabled:
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    plan = plan.lower()
    if plan not in _VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan. Must be one of: {', '.join(sorted(_VALID_PLANS))}",
        )

    success_url = f"{_FRONTEND_ORIGIN}/billing?checkout=success"
    cancel_url = f"{_FRONTEND_ORIGIN}/billing?checkout=cancelled"

    session = payments_service.create_checkout_session(
        user_email=user.email,
        plan=plan,
        success_url=success_url,
        cancel_url=cancel_url,
        user_id=user.user_id,
    )

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return session


@router.get("/portal")
async def billing_portal(
    user: CurrentUser = Depends(get_current_user),
):
    """Return a Stripe Billing Portal URL for self-service subscription management."""
    if not payments_service.enabled:
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    return_url = f"{_FRONTEND_ORIGIN}/billing"
    result = payments_service.create_portal_session(
        customer_email=user.email,
        return_url=return_url,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to create portal session")

    return result


@router.get("/status")
async def billing_status(
    user: CurrentUser = Depends(get_current_user),
):
    """Return the user's current subscription and plan information."""
    plan = "free"
    subscription_id = None
    subscription_status = None

    try:
        result = (
            supabase.table("user_profiles")
            .select("plan")
            .eq("email", user.email)
            .maybe_single()
            .execute()
        )
        if result.data:
            plan = result.data.get("plan") or "free"
    except Exception as exc:
        logger.debug("Could not fetch plan for %s: %s", user.email, exc)

    try:
        pay_result = (
            supabase.table("payments")
            .select("subscription_id, status, plan")
            .eq("user_id", user.user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if pay_result.data:
            row = pay_result.data[0]
            subscription_id = row.get("subscription_id")
            subscription_status = row.get("status")
            if row.get("plan"):
                plan = row["plan"]
    except Exception as exc:
        logger.debug("Could not fetch payments for %s: %s", user.email, exc)

    return {
        "plan": plan,
        "subscription_id": subscription_id,
        "subscription_status": subscription_status,
    }
