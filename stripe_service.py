import stripe
import logging
from typing import Optional, Dict
from config import config

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.STRIPE_SECRET_KEY
        self.webhook_secret = config.STRIPE_WEBHOOK_KEY
        self.price_id = config.PRO_PLAN_PRICE_ID
        self.enabled = self.api_key is not None

        if self.enabled:
            stripe.api_key = self.api_key

    def create_checkout_session(self, user_email: str, success_url: str,
                               cancel_url: str) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("Stripe not configured")
            return None

        try:
            session = stripe.checkout.Session.create(
                customer_email=user_email,
                payment_method_types=['card'],
                line_items=[{
                    'price': self.price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={'user_email': user_email}
            )

            logger.info(f"Checkout session created for {user_email}: {session.id}")

            return {
                'session_id': session.id,
                'url': session.url
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> Optional[Dict]:
        if not self.webhook_secret:
            logger.error("Webhook secret not configured")
            return None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return None

    def handle_checkout_completed(self, session: Dict) -> Dict:
        user_email = session.get('customer_email') or session.get('metadata', {}).get('user_email')
        subscription_id = session.get('subscription')

        logger.info(f"Checkout completed for {user_email}, subscription: {subscription_id}")

        return {
            'user_email': user_email,
            'subscription_id': subscription_id,
            'status': 'active'
        }

    def handle_invoice_paid(self, invoice: Dict) -> Dict:
        subscription_id = invoice.get('subscription')
        customer_email = invoice.get('customer_email')

        logger.info(f"Invoice paid for {customer_email}, subscription: {subscription_id}")

        return {
            'subscription_id': subscription_id,
            'customer_email': customer_email,
            'status': 'paid'
        }

stripe_service = StripeService()
