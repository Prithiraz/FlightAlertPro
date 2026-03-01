from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import logging
from payments import payments_service
from cache import cache_service
from config import config
from audit_log import audit

logger = logging.getLogger(__name__)

router = APIRouter()

_PROCESSED_EVENT_TTL = 86400  # 24 hours


def _upsert_user_plan(user_email: str, plan: str, subscription_id: Optional[str] = None):
    """Persist plan/subscription changes into user_profiles (best-effort)."""
    if not user_email:
        return
    try:
        from supabase import create_client
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        update_data = {"plan": plan, "email": user_email}
        if subscription_id:
            update_data["subscription_id"] = subscription_id
        supabase.table("user_profiles").upsert(update_data, on_conflict="email").execute()
        logger.info("Upserted plan=%s for %s", plan, user_email)
    except Exception as exc:
        logger.warning("Could not upsert plan for %s: %s", user_email, exc)


def _extract_customer_email(subscription: dict) -> Optional[str]:
    """Extract the customer email from a Stripe subscription object."""
    return subscription.get("customer_email") or (
        subscription.get("customer_details") or {}
    ).get("email")

@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    if not stripe_signature:
        logger.error("Missing Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        payload = await request.body()

        event = payments_service.verify_webhook_signature(payload, stripe_signature)

        if not event:
            logger.error("Webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")

        event_id = event.get('id')
        event_type = event['type']

        # Idempotency: atomically claim the event; skip if already processed.
        # set_if_not_exists returns False when the key already exists (Redis SET NX).
        if event_id and not cache_service.set_if_not_exists(
            f"stripe_event:{event_id}", True, ttl=_PROCESSED_EVENT_TTL
        ):
            logger.info(f"Duplicate webhook event {event_id} ({event_type}), skipping")
            return {"status": "success", "event_type": event_type, "duplicate": True}

        logger.info(f"Processing webhook event: {event_type}")

        # Record webhook receipt for status page / health monitoring
        try:
            from metrics import record_metric
            record_metric("stripe_webhook_received", 1, {"event_type": event_type})
        except Exception:
            pass

        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            result = payments_service.handle_checkout_completed(session)
            _upsert_user_plan(
                result.get('user_email'),
                result.get('plan', 'pro'),
                result.get('subscription_id'),
            )
            await audit(
                action="plan.upgrade",
                email=result.get('user_email'),
                target_type="subscription",
                target_id=result.get('subscription_id'),
                request=request,
                metadata={"plan": result.get('plan', 'pro'), "event": event_type},
            )
            logger.info(f"Checkout completed processed: {result}")

        elif event_type == 'invoice.paid':
            invoice = event['data']['object']
            result = payments_service.handle_invoice_paid(invoice)

            logger.info(f"Invoice paid processed: {result}")

        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            customer_email = _extract_customer_email(subscription)
            sub_status = subscription.get('status', '')
            plan = subscription.get('metadata', {}).get('plan', 'pro')
            new_plan = plan if sub_status == 'active' else 'free'
            _upsert_user_plan(customer_email, new_plan, subscription.get('id'))
            await audit(
                action="plan.change",
                email=customer_email,
                target_type="subscription",
                target_id=subscription.get('id'),
                request=request,
                metadata={"plan": new_plan, "status": sub_status},
            )
            logger.info(f"Subscription updated: {subscription.get('id')}")

        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_email = _extract_customer_email(subscription)
            _upsert_user_plan(customer_email, 'free', None)
            await audit(
                action="plan.cancel",
                email=customer_email,
                target_type="subscription",
                target_id=subscription.get('id'),
                request=request,
                metadata={"event": event_type},
            )
            logger.info(f"Subscription cancelled: {subscription.get('id')}")

        else:
            logger.info(f"Unhandled event type: {event_type}")

        return {"status": "success", "event_type": event_type}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
