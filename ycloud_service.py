import requests
import time
import logging
from typing import Optional, Dict
from config import config

logger = logging.getLogger(__name__)

class YCloudService:
    BASE_URL = "https://api.ycloud.com/v2"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self, api_key: Optional[str] = None, phone_number: Optional[str] = None):
        self.api_key = api_key or config.YCLOUD_API_KEY
        self.phone_number = phone_number or config.YCLOUD_PHONE_NUMBER
        self.enabled = self.api_key is not None and self.phone_number is not None

    def _make_request(self, endpoint: str, data: Dict, retry_count: int = 0) -> Optional[Dict]:
        if not self.enabled:
            logger.warning("YCloud not configured, skipping WhatsApp send")
            return None

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        try:
            logger.info(f"YCloud WhatsApp send to {data.get('to')}")
            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self._make_request(endpoint, data, retry_count + 1)
                else:
                    logger.error("Max retries reached")
                    return None

            response.raise_for_status()
            result = response.json()

            message_id = result.get("id", "unknown")
            status = result.get("status", "unknown")

            logger.info(f"YCloud message sent: {message_id}, status: {status}")

            return {
                "message_id": message_id,
                "status": status,
                "response": result
            }

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"Request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self._make_request(endpoint, data, retry_count + 1)
            else:
                logger.error(f"Failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def send_message(self, to: str, text: str) -> Optional[Dict]:
        if not self.enabled:
            logger.info(f"YCloud disabled - would send to {to}: {text}")
            return {"message_id": "dry_run", "status": "disabled"}

        if not to.startswith('+'):
            to = f'+{to}'

        data = {
            "from": self.phone_number,
            "to": to,
            "type": "text",
            "text": {
                "body": text
            }
        }

        return self._make_request("/whatsapp/messages", data)

ycloud_service = YCloudService()
