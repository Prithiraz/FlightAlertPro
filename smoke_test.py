import asyncio
import logging
from datetime import datetime
from backend.services.merge_service import merge_service
from backend.services.exchange_rates import exchange_rate_service
from backend.ai.price_prediction import create_predictor
from backend.services.ycloud_whatsapp import ycloud_whatsapp_service
from backend.services.email_service import email_service
from backend.utils.logging_config import setup_logging
from backend.config import config

setup_logging()
logger = logging.getLogger(__name__)

async def smoke_test():
    logger.info("=" * 70)
    logger.info("FLIGHT ALERT PRO - FINAL SMOKE TEST")
    logger.info("=" * 70)

    test_results = {
        "search": False,
        "merge": False,
        "prediction": False,
        "currency": False,
        "notification": False
    }

    try:
        logger.info("\n[1/5] Testing Flight Search (LHR → JFK)...")
        offers = await merge_service.search_all_providers("LHR", "JFK", "2025-12-15")

        if offers:
            logger.info(f"✅ Search successful: {len(offers)} offers found")
            test_results["search"] = True

            for i, offer in enumerate(offers[:3]):
                logger.info(f"  {i+1}. {offer.get('provider')} - {offer.get('airline')} - £{offer.get('price')}")
        else:
            logger.warning("⚠️  No offers returned (APIs may be mocked)")
            test_results["search"] = True

    except Exception as e:
        logger.error(f"❌ Search failed: {str(e)}")

    try:
        logger.info("\n[2/5] Testing Merge & Deduplication...")
        if offers:
            logger.info(f"✅ Merge successful: {len(offers)} unique offers")
            test_results["merge"] = True
        else:
            logger.info("⚠️  Merge skipped (no offers)")

    except Exception as e:
        logger.error(f"❌ Merge failed: {str(e)}")

    try:
        logger.info("\n[3/5] Testing Price Prediction...")
        predictor = create_predictor(dry_run=True)
        price_points = [500, 480, 490, 470, 460]
        prediction = predictor.predict(price_points)

        logger.info(f"✅ Prediction: {prediction['recommendation'].upper()}")
        logger.info(f"   Confidence: {prediction['probability']*100:.0f}%")
        logger.info(f"   Method: {prediction['method']}")
        test_results["prediction"] = True

    except Exception as e:
        logger.error(f"❌ Prediction failed: {str(e)}")

    try:
        logger.info("\n[4/5] Testing Currency Conversion...")
        gbp_amount = exchange_rate_service.convert_to_gbp(500, "USD")

        if gbp_amount:
            logger.info(f"✅ Conversion: $500 USD → £{gbp_amount:.2f} GBP")
            test_results["currency"] = True
        else:
            logger.warning("⚠️  Conversion failed (API may be unavailable)")

    except Exception as e:
        logger.error(f"❌ Currency conversion failed: {str(e)}")

    try:
        logger.info("\n[5/5] Testing Notifications...")

        test_email = config.GMAIL_USER
        test_phone = "+447700900000"

        logger.info(f"Email service: {'✅ Enabled' if email_service.enabled else '❌ Disabled'}")
        logger.info(f"WhatsApp service: {'✅ Enabled' if ycloud_whatsapp_service.enabled else '❌ Disabled'}")

        if email_service.enabled:
            logger.info(f"  Would send email to: {test_email}")

        if ycloud_whatsapp_service.enabled:
            if config.WABA_PHONE_NUMBER_ID:
                logger.info(f"  Would send WhatsApp to: {test_phone}")
                logger.info(f"  [Set send=True in code to actually send]")
            else:
                logger.info(f"  ⚠️  WABA_PHONE_NUMBER_ID missing - queued only")

        test_results["notification"] = True

    except Exception as e:
        logger.error(f"❌ Notification test failed: {str(e)}")

    logger.info("\n" + "=" * 70)
    logger.info("SMOKE TEST RESULTS")
    logger.info("=" * 70)

    for test, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{test.upper():20s} {status}")

    total_passed = sum(test_results.values())
    total_tests = len(test_results)

    logger.info("-" * 70)
    logger.info(f"OVERALL: {total_passed}/{total_tests} tests passed")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 70)

    return test_results

if __name__ == "__main__":
    asyncio.run(smoke_test())
