import requests
import time
import logging
from typing import Dict, Optional
from backend.config import config

logger = logging.getLogger(__name__)

class CurrencyService:
    CACHE_TTL = 3600

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or config.FRANKFURTER_API_URL
        self.cache: Optional[tuple[float, Dict[str, float]]] = None

    def _fetch_rates(self) -> Optional[Dict[str, float]]:
        try:
            logger.info(f"Fetching currency rates from {self.api_url}")
            response = requests.get(f"{self.api_url}/latest", timeout=10)
            response.raise_for_status()

            data = response.json()
            rates = data.get("rates", {})
            rates[data.get("base", "EUR")] = 1.0

            logger.info(f"Fetched {len(rates)} currency rates")
            return rates

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch currency rates: {str(e)}")
            return None

    def _get_rates(self) -> Dict[str, float]:
        if self.cache:
            timestamp, rates = self.cache
            if time.time() - timestamp < self.CACHE_TTL:
                return rates

        rates = self._fetch_rates()
        if rates:
            self.cache = (time.time(), rates)
            return rates

        if self.cache:
            _, old_rates = self.cache
            logger.warning("Using stale currency rates")
            return old_rates

        logger.warning("No currency rates available, using defaults")
        return {
            "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "CAD": 1.36,
            "AUD": 1.53, "INR": 83.12, "JPY": 149.50, "SGD": 1.35, "AED": 3.67
        }

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return amount

        rates = self._get_rates()

        if from_currency not in rates or to_currency not in rates:
            logger.warning(f"Currency pair not available: {from_currency} -> {to_currency}")
            return amount

        base_amount = amount / rates[from_currency]
        converted = base_amount * rates[to_currency]

        logger.debug(f"Converted {amount} {from_currency} to {converted:.2f} {to_currency}")
        return converted

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        return self.convert(1.0, from_currency, to_currency)

currency_service = CurrencyService()
