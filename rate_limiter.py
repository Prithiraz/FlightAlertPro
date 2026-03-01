import time
import logging
from typing import Optional
from config import config
from cache import cache_service

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

    def check_search_rate_limit(self, user_id: str, max_per_day: int) -> bool:
        """Check (and increment) the per-user daily search counter against *max_per_day*.

        Returns True when the request is within the limit, False when exceeded.
        The counter TTL is capped at 86 400 s (24 h) so it naturally resets each day.
        """
        key = f"search_daily:{user_id}"
        current = cache_service.get(key) or 0
        if current >= max_per_day:
            logger.warning("Daily search limit (%d) exceeded for user %s", max_per_day, user_id)
            return False
        cache_service.set(key, current + 1, ttl=86400)
        return True

rate_limiter = RateLimiter()
