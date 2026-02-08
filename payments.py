import stripe
import logging
from typing import Optional, Dict
from backend.config import config

logger = logging.getLogger(__name__)

class PaymentsService:
    def __init__(self):
        self.api_key = config.STRIPE_SECRET_KEY
        self.webhook_key = config.STRIPE_WEBHOOK_KEY
        self.pro_price_id = config.PRO_PLAN_PRICE_ID
        self.elite_price_id = config.ELITE_PLAN_PRICE_ID
        self.business_price_id = config.BUSINESS_PLAN_PRICE_ID

        self.enabled = self.api_key is not None
        self.is_test_mode = self.api_key and self.api_key.startswith('sk_test')

        if self.enabled:
            stripe.api_key = self.api_key
            mode = "TEST" if self.is_test_mode else "LIVE"
            logger.info(f"Stripe initialized in {mode} mode")

    def create_checkout_session(self, user_email: str, plan: str, success_url: str,
                               cancel_url: str, user_id: Optional[str] = None) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("Stripe not configured - cannot create checkout session")
            return None

        price_id_map = {
            "pro": self.pro_price_id,
            "elite": self.elite_price_id,
            "business": self.business_price_id
        }

        price_id = price_id_map.get(plan.lower())

        if not price_id:
            logger.error(f"Invalid plan: {plan}")
            return None

        try:
            metadata = {
                'user_email': user_email,
                'plan': plan
            }

            if user_id:
                metadata['user_id'] = user_id

            session = stripe.checkout.Session.create(
                customer_email=user_email,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata
            )

            logger.info(f"Checkout session created for {user_email}: {session.id} ({plan} plan)")

            return {
                'session_id': session.id,
                'url': session.url,
                'plan': plan
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {str(e)}")
            return None

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> Optional[Dict]:
        if not self.webhook_key:
            logger.error("Webhook key not configured")
            return None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_key
            )
            logger.info(f"Webhook verified: {event['type']}")
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return None

    def handle_checkout_completed(self, session: Dict) -> Dict:
        user_email = session.get('customer_email') or session.get('metadata', {}).get('user_email')
        subscription_id = session.get('subscription')
        plan = session.get('metadata', {}).get('plan', 'pro')
        user_id = session.get('metadata', {}).get('user_id')

        logger.info(f"Checkout completed: {user_email}, plan: {plan}, subscription: {subscription_id}")

        return {
            'user_email': user_email,
            'user_id': user_id,
            'subscription_id': subscription_id,
            'plan': plan,
            'status': 'active'
        }

    def handle_invoice_paid(self, invoice: Dict) -> Dict:
        subscription_id = invoice.get('subscription')
        customer_email = invoice.get('customer_email')

        logger.info(f"Invoice paid: {customer_email}, subscription: {subscription_id}")

        return {
            'subscription_id': subscription_id,
            'customer_email': customer_email,
            'status': 'paid'
        }

    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        if not self.enabled:
            return None

        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                'id': subscription.id,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving subscription: {str(e)}")
            return None

payments_service = PaymentsService()
