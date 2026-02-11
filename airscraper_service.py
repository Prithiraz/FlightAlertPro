import requests
import time
import logging
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class AirScraperService:
    BASE_URL = "https://tripadvisor-scraper.p.rapidapi.com"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.RAPIDAPI_KEY
        self.enabled = self.api_key is not None

    def _make_request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("RapidAPI key not configured, skipping AirScraper request")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "tripadvisor-scraper.p.rapidapi.com"
        }

        try:
            logger.info(f"AirScraper Request: {endpoint}")
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error("Max retries reached")
                    return None

            response.raise_for_status()
            result = response.json()
            logger.info(f"AirScraper Response: {response.status_code}")
            return result

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"Request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"Request failed after retries: {str(e)}")
                return None

    def search_flights(self, from_iata: str, to_iata: str, departure_date: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.error(
                "AirScraper service unavailable",
                extra={
                    "service": "airscraper",
                    "reason": "RapidAPI key not configured",
                    "route": f"{from_iata} -> {to_iata}",
                    "date": departure_date
                }
            )
            return []

        logger.error(
            "AirScraper search not implemented",
            extra={
                "service": "airscraper",
                "reason": "API integration pending",
                "route": f"{from_iata} -> {to_iata}",
                "date": departure_date
            }
        )
        return []

airscraper_service = AirScraperService()
