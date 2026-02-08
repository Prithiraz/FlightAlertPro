from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import logging
from backend.services.payments import payments_service

logger = logging.getLogger(__name__)

router = APIRouter()

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

        event_type = event['type']
        logger.info(f"Processing webhook event: {event_type}")

        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            result = payments_service.handle_checkout_completed(session)

            logger.info(f"Checkout completed processed: {result}")

        elif event_type == 'invoice.paid':
            invoice = event['data']['object']
            result = payments_service.handle_invoice_paid(invoice)

            logger.info(f"Invoice paid processed: {result}")

        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            logger.info(f"Subscription updated: {subscription.get('id')}")

        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            logger.info(f"Subscription cancelled: {subscription.get('id')}")

        else:
            logger.info(f"Unhandled event type: {event_type}")

        return {"status": "success", "event_type": event_type}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
