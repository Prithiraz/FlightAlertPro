import stripe
import logging
from datetime import datetime
from typing import Optional, Dict
from config import config
from supabase import create_client, Client

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

        # Use service role key for server-side DB writes; fall back to anon key
        supabase_key = config.SUPABASE_SERVICE_KEY or config.SUPABASE_ANON_KEY
        self._supabase: Optional[Client] = None
        if config.SUPABASE_URL and supabase_key:
            self._supabase = create_client(config.SUPABASE_URL, supabase_key)

    def _get_supabase(self) -> Optional[Client]:
        return self._supabase

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

            return session

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

    def _upgrade_user_in_db(self, user_email: str, stripe_customer_id: Optional[str],
                            subscription_id: Optional[str], plan: str) -> bool:
        """Update user subscription fields in Supabase. Returns True on success."""
        supabase = self._get_supabase()
        if not supabase:
            logger.warning("Supabase client not configured – skipping DB upgrade for %s", user_email)
            return False

        valid_tiers = {'pro', 'elite', 'business'}
        subscription_tier = plan.lower() if plan.lower() in valid_tiers else 'pro'

        profile_data: Dict = {
            'email': user_email,
            'subscription_tier': subscription_tier,
            'plan': plan,
            'subscription_status': 'active',
            'updated_at': datetime.utcnow().isoformat(),
        }
        if stripe_customer_id:
            profile_data['stripe_customer_id'] = stripe_customer_id
        if subscription_id:
            profile_data['subscription_id'] = subscription_id

        try:
            result = supabase.table('user_profiles').upsert(
                profile_data, on_conflict='email'
            ).execute()
            if result.data:
                logger.info(
                    "Stripe Webhook received: Upgrade successful for user %s (plan=%s)",
                    user_email, plan
                )
                return True
            logger.error("DB upsert for user %s returned no data", user_email)
            return False
        except Exception as exc:
            logger.error("Failed to upgrade user %s in DB: %s", user_email, str(exc))
            return False

    def handle_checkout_completed(self, session: Dict) -> Dict:
        user_email = (
            session.get('customer_email')
            or session.get('metadata', {}).get('user_email')
        )
        stripe_customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        plan = session.get('metadata', {}).get('plan', 'pro')
        user_id = session.get('metadata', {}).get('user_id')

        logger.info(
            "Checkout completed: %s, plan=%s, subscription=%s",
            user_email, plan, subscription_id
        )

        db_updated = False
        if user_email:
            db_updated = self._upgrade_user_in_db(
                user_email, stripe_customer_id, subscription_id, plan
            )

        return {
            'user_email': user_email,
            'user_id': user_id,
            'stripe_customer_id': stripe_customer_id,
            'subscription_id': subscription_id,
            'plan': plan,
            'status': 'active',
            'db_updated': db_updated,
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
