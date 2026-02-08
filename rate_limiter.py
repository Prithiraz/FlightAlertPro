import time
import logging
from typing import Optional
from backend.config import config
from backend.services.cache import cache_service

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.api_limit = config.API_RATE_LIMIT_PER_MINUTE
        self.notification_limit = config.NOTIFICATION_RATE_LIMIT_PER_HOUR

    def check_api_rate_limit(self, user_id: str) -> bool:
        key = f"api_limit:{user_id}"
        current = cache_service.get(key) or 0

        if current >= self.api_limit:
            logger.warning(f"API rate limit exceeded for user {user_id}")
            return False

        cache_service.set(key, current + 1, ttl=60)
        return True

    def check_notification_rate_limit(self, user_id: str) -> bool:
        key = f"notif_limit:{user_id}"
        current = cache_service.get(key) or 0

        if current >= self.notification_limit:
            logger.warning(f"Notification rate limit exceeded for user {user_id}")
            return False

        cache_service.set(key, current + 1, ttl=3600)
        return True

rate_limiter = RateLimiter()
