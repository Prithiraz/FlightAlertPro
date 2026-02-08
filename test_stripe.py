import logging
from payments import payments_service
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def test_stripe_checkout():
    logger.info("=" * 60)
    logger.info("Stripe Checkout Test")
    logger.info("=" * 60)

    if not payments_service.enabled:
        logger.error("Stripe not configured!")
        return

    test_mode = "TEST" if payments_service.is_test_mode else "LIVE"
    logger.info(f"Stripe Mode: {test_mode}")

    test_email = "test@example.com"
    success_url = "https://yourdomain.com/success"
    cancel_url = "https://yourdomain.com/cancel"

    logger.info(f"\nCreating checkout session for PRO plan...")
    logger.info(f"Email: {test_email}")

    session = payments_service.create_checkout_session(
        user_email=test_email,
        plan="pro",
        success_url=success_url,
        cancel_url=cancel_url
    )

    if session:
        logger.info(f"\n✅ Checkout session created!")
        logger.info(f"Session ID: {session['session_id']}")
        logger.info(f"Checkout URL: {session['url']}")
        logger.info(f"\nNext steps:")
        logger.info(f"1. Open the URL in your browser")
        logger.info(f"2. Complete the payment in Stripe")
        logger.info(f"3. Check webhook logs for confirmation")
        logger.info(f"4. Verify user.plan updated in database")
    else:
        logger.error("❌ Failed to create checkout session")

    logger.info("=" * 60)

if __name__ == "__main__":
    test_stripe_checkout()
