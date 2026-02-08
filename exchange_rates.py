import requests
import time
import logging
from typing import Optional, Dict
from backend.config import config

logger = logging.getLogger(__name__)

class ExchangeRateService:
    def __init__(self):
        self.base_url = config.FRANKFURTER_API_URL or "https://api.frankfurter.app"
        self.cache = {}
        self.cache_ttl = 3600
        self.last_fetch_time = 0

    def _fetch_rates(self) -> Optional[Dict[str, float]]:
        current_time = time.time()

        if self.cache and (current_time - self.last_fetch_time) < self.cache_ttl:
            logger.info("Using cached exchange rates")
            return self.cache

        try:
            url = f"{self.base_url}/latest?from=GBP"
            logger.info(f"Fetching exchange rates from {url}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            rates = data.get("rates", {})

            rates["GBP"] = 1.0

            self.cache = rates
            self.last_fetch_time = current_time

            logger.info(f"Fetched {len(rates)} exchange rates")
            return rates

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch exchange rates: {str(e)}")

            if self.cache:
                logger.warning("Using stale cached rates")
                return self.cache

            return None

    def convert_to_gbp(self, amount: float, from_currency: str) -> Optional[float]:
        if from_currency == "GBP":
            return amount

        rates = self._fetch_rates()

        if not rates:
            logger.error("No exchange rates available")
            return None

        from_currency = from_currency.upper()

        if from_currency not in rates:
            logger.warning(f"Currency {from_currency} not found in rates, using 1:1")
            return amount

        rate = rates[from_currency]
        gbp_amount = amount / rate

        logger.debug(f"Converted {amount} {from_currency} to {gbp_amount:.2f} GBP (rate: {rate})")
        return gbp_amount

    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        if from_currency == to_currency:
            return amount

        rates = self._fetch_rates()

        if not rates:
            logger.error("No exchange rates available")
            return None

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency not in rates or to_currency not in rates:
            logger.warning(f"Currency conversion {from_currency} -> {to_currency} not available")
            return amount

        gbp_amount = amount / rates[from_currency]
        converted_amount = gbp_amount * rates[to_currency]

        logger.debug(f"Converted {amount} {from_currency} to {converted_amount:.2f} {to_currency}")
        return converted_amount

exchange_rate_service = ExchangeRateService()
