"""Currency conversion using Frankfurter API"""
from fastapi import APIRouter, Query, HTTPException
import requests
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/currency", tags=["currency"])

# Rate cache: {from_to: (rate, timestamp)}
RATE_CACHE = {}
CACHE_TTL = 3600  # 1 hour

@router.get("/convert")
async def convert_currency(
    amount: float = Query(..., gt=0),
    from_currency: str = Query(..., regex="^[A-Z]{3}$"),
    to_currency: str = Query(..., regex="^[A-Z]{3}$")
):
    """Convert currency using Frankfurter API with 1-hour caching"""
    if from_currency == to_currency:
        return {
            "amount": amount,
            "from": from_currency,
            "to": to_currency,
            "converted": amount,
            "rate": 1.0,
            "cached": False
        }

    cache_key = f"{from_currency}_{to_currency}"

    # Check cache
    if cache_key in RATE_CACHE:
        rate, timestamp = RATE_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            converted = amount * rate
            logger.info(f"Currency conversion (cached): {amount} {from_currency} = {converted} {to_currency}")
            return {
                "amount": amount,
                "from": from_currency,
                "to": to_currency,
                "converted": converted,
                "rate": rate,
                "cached": True
            }

    # Call Frankfurter API
    try:
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_currency}&to={to_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        converted = data['rates'][to_currency]
        rate = converted / amount

        # Cache the rate
        RATE_CACHE[cache_key] = (rate, time.time())

        logger.info(f"Currency conversion (live): {amount} {from_currency} = {converted} {to_currency}")

        return {
            "amount": amount,
            "from": from_currency,
            "to": to_currency,
            "converted": converted,
            "rate": rate,
            "cached": False
        }

    except Exception as e:
        logger.error(f"Currency conversion failed: {e}")
        raise HTTPException(status_code=503, detail=f"Currency conversion unavailable: {str(e)}")

@router.get("/rates")
async def get_rates(base: str = Query("USD", regex="^[A-Z]{3}$")):
    """Get all exchange rates for a base currency"""
    try:
        url = f"https://api.frankfurter.app/latest?from={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "base": base,
            "date": data['date'],
            "rates": data['rates']
        }

    except Exception as e:
        logger.error(f"Failed to fetch rates: {e}")
        raise HTTPException(status_code=503, detail=f"Rates unavailable: {str(e)}")
