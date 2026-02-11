import requests
import logging
from typing import Optional, Dict
from config import config

logger = logging.getLogger(__name__)

class TelegramService:
    BASE_URL = "https://api.telegram.org"

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.enabled = self.bot_token is not None

    def send_message(self, chat_id: str, text: str) -> bool:
        if not self.enabled:
            logger.info(f"Telegram disabled - would send to {chat_id}: {text}")
            return False

        url = f"{self.BASE_URL}/bot{self.bot_token}/sendMessage"

        try:
            response = requests.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }, timeout=10)

            response.raise_for_status()
            logger.info(f"Telegram message sent to {chat_id}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

telegram_service = TelegramService()
