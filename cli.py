import asyncio
import logging
from datetime import datetime
from backend.services.merge_service import merge_service
from backend.services.exchange_rates import exchange_rate_service
from backend.ai.price_prediction import create_predictor
from backend.utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

async def run_dry_run():
    logger.info("=" * 60)
    logger.info("DRY RUN - Full Pipeline Test")
    logger.info("=" * 60)

    from_iata = "LHR"
    to_iata = "JFK"
    departure_date = "2025-12-15"

    logger.info(f"\n1. SEARCH: {from_iata} → {to_iata} on {departure_date}")
    logger.info("-" * 60)

    offers = await merge_service.search_all_providers(from_iata, to_iata, departure_date)

    logger.info(f"Found {len(offers)} offers from providers")
    for i, offer in enumerate(offers[:5]):
        logger.info(f"  {i+1}. {offer.get('provider')}: {offer.get('airline')} - £{offer.get('price')} - {offer.get('stops')} stops")

    if not offers:
        logger.warning("No offers found - pipeline test incomplete")
        return

    logger.info(f"\n2. MERGE & DEDUPE")
    logger.info("-" * 60)
    logger.info(f"Merged and deduped to {len(offers)} unique offers")

    logger.info(f"\n3. CURRENCY CONVERSION")
    logger.info("-" * 60)

    for offer in offers[:3]:
        original_price = offer.get('price')
        original_currency = offer.get('currency', 'USD')

        if original_currency != 'GBP':
            gbp_price = exchange_rate_service.convert_to_gbp(original_price, original_currency)
            logger.info(f"  {original_price} {original_currency} → £{gbp_price:.2f}")
            offer['price_gbp'] = gbp_price
        else:
            offer['price_gbp'] = original_price

    logger.info(f"\n4. PRICE PREDICTION (DRY RUN)")
    logger.info("-" * 60)

    predictor = create_predictor(dry_run=True)

    if offers:
        price_points = [offer.get('price_gbp', offer.get('price')) for offer in offers[:5]]
        prediction = predictor.predict(price_points)

        logger.info(f"  Recommendation: {prediction['recommendation'].upper()}")
        logger.info(f"  Confidence: {prediction['probability']*100:.0f}%")
        logger.info(f"  Method: {prediction['method']}")
        logger.info(f"  Details: {prediction['details']}")

    logger.info(f"\n5. SIMULATE NOTIFICATION (DRY RUN)")
    logger.info("-" * 60)

    test_user = "test@example.com"
    test_phone = "+447700900000"

    message = f"Price alert for {from_iata}→{to_iata}: Best price £{offers[0].get('price_gbp', offers[0].get('price')):.2f}"

    logger.info(f"  Would send to: {test_user}")
    logger.info(f"  WhatsApp: {test_phone}")
    logger.info(f"  Message: {message}")
    logger.info(f"  [DRY RUN - No actual send]")

    logger.info(f"\n{'=' * 60}")
    logger.info("DRY RUN COMPLETE")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_dry_run())
