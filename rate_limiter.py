import time
import logging
from typing import Optional
from config import config
from cache import cache_service

logger = logging.getLogger(__name__)

# In-memory IP tracking (sufficient for single-process deployments).
# NOTE: For multi-process deployments (e.g., multiple Gunicorn workers), use
# a shared cache such as Redis via RateLimiter.check_api_rate_limit() instead.
_ip_requests: dict = {}   # ip -> list of timestamps
_ip_blocked: dict = {}    # ip -> block_until timestamp


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

    # ------------------------------------------------------------------
    # Per-IP search rate limiting (in-memory, anti-abuse)
    # ------------------------------------------------------------------

    def check_ip_search_limit(self, ip: str) -> bool:
        """Return False (and log) when the IP exceeds the per-minute search cap
        or is currently in a temporary block window.

        A temporary 15-minute block is applied automatically when the IP has
        produced repeated 429s (> 3× the per-minute cap within one minute).
        """
        now = time.time()
        limit = config.SEARCH_IP_RATE_LIMIT_PER_MINUTE
        block_seconds = config.SEARCH_IP_BLOCK_MINUTES * 60

        # Check if the IP is currently blocked
        block_until = _ip_blocked.get(ip, 0)
        if now < block_until:
            logger.warning("Blocked IP %s attempted search (blocked until %s)", ip, block_until)
            return False

        # Slide the request window (last 60 s)
        window = _ip_requests.get(ip, [])
        window = [ts for ts in window if now - ts < 60]
        window.append(now)
        _ip_requests[ip] = window

        if len(window) > limit:
            # If the IP is 3× over the limit, apply a temporary block
            if len(window) > limit * 3:
                _ip_blocked[ip] = now + block_seconds
                logger.warning(
                    "IP %s temporarily blocked for %d minutes after excessive requests",
                    ip,
                    config.SEARCH_IP_BLOCK_MINUTES,
                )
            else:
                logger.warning("Per-IP search rate limit exceeded for %s (%d req/min)", ip, len(window))
            return False

        return True


rate_limiter = RateLimiter()
