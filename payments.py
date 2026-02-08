"""Payment API routes for Stripe integration"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import stripe
import os

router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class CreateCheckoutRequest(BaseModel):
    price_id: str

@router.post("/create-checkout")
async def create_checkout(request: CreateCheckoutRequest):
    """Create a Stripe checkout session"""
    try:
        if not stripe.api_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        site_url = os.getenv('SITE_URL', '')
        success_url = f"{site_url}/plans?success=true" if site_url else '/plans?success=true'
        cancel_url = f"{site_url}/plans?canceled=true" if site_url else '/plans?canceled=true'

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {
            'session_id': session.id,
            'url': session.url
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment system error: {str(e)}")
