import time
import logging
from typing import Dict
from backend.services.cache import cache_service

logger = logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout

    def record_failure(self, provider: str):
        key = f"circuit:{provider}:failures"
        failures = cache_service.get(key) or 0
        failures += 1

        cache_service.set(key, failures, ttl=600)

        if failures >= self.failure_threshold:
            logger.warning(f"Circuit breaker opened for {provider}")
            cache_service.set(f"circuit:{provider}:down", True, ttl=self.timeout)

    def record_success(self, provider: str):
        cache_service.delete(f"circuit:{provider}:failures")
        cache_service.delete(f"circuit:{provider}:down")

    def is_available(self, provider: str) -> bool:
        is_down = cache_service.get(f"circuit:{provider}:down")
        return not is_down

circuit_breaker = CircuitBreaker()
