import requests
import time
import logging
from typing import Optional, Dict
from config import config

logger = logging.getLogger(__name__)

class YCloudWhatsAppService:
    BASE_URL = "https://api.ycloud.com/v2/whatsapp/messages"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1

    def __init__(self):
        self.api_key = config.YCLOUD_API_KEY
        self.phone_number_id = config.WABA_PHONE_NUMBER_ID
        self.enabled = self.api_key is not None

    def send_whatsapp(self, to: str, template_name: str, params: Dict, retry_count: int = 0) -> Optional[str]:
        if not self.enabled:
            logger.warning("YCloud API key not configured - cannot send WhatsApp message")
            return None

        if not self.phone_number_id:
            logger.warning(f"Phone ID missing - message queued for {to}; add WABA_PHONE_NUMBER_ID to send")
            return "queued_no_phone_id"

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        to_clean = to.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "to": to_clean,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "policy": "deterministic",
                    "code": "en"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(value)}
                            for value in params.values()
                        ]
                    }
                ]
            }
        }

        try:
            logger.info(f"Sending WhatsApp via YCloud to {to_clean}")

            response = requests.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by YCloud, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self.send_whatsapp(to, template_name, params, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None

            response.raise_for_status()
            result = response.json()

            message_id = result.get("id")
            logger.info(f"WhatsApp sent successfully via YCloud: {message_id}")

            return message_id

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"YCloud request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self.send_whatsapp(to, template_name, params, retry_count + 1)
            else:
                logger.error(f"YCloud request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

    def send_text(self, to: str, body: str, retry_count: int = 0) -> Optional[str]:
        if not self.enabled:
            logger.warning("YCloud API key not configured - cannot send WhatsApp message")
            return None

        if not self.phone_number_id:
            logger.warning(f"Phone ID missing - message queued for {to}; add WABA_PHONE_NUMBER_ID to send")
            return "queued_no_phone_id"

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        to_clean = to.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "to": to_clean,
            "type": "text",
            "text": {
                "body": body
            }
        }

        try:
            logger.info(f"Sending WhatsApp text via YCloud to {to_clean}")

            response = requests.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                    logger.warning(f"Rate limited by YCloud, retrying in {backoff}s")
                    time.sleep(backoff)
                    return self.send_text(to, body, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limit")
                    return None

            response.raise_for_status()
            result = response.json()

            message_id = result.get("id")
            logger.info(f"WhatsApp text sent successfully via YCloud: {message_id}")

            return message_id

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                backoff = self.INITIAL_BACKOFF * (2 ** retry_count)
                logger.warning(f"YCloud request failed, retrying in {backoff}s: {str(e)}")
                time.sleep(backoff)
                return self.send_text(to, body, retry_count + 1)
            else:
                logger.error(f"YCloud request failed after {self.MAX_RETRIES} retries: {str(e)}")
                return None

ycloud_whatsapp_service = YCloudWhatsAppService()
