import logging
import time
from typing import Optional, Any
from collections import OrderedDict
from config import config

logger = logging.getLogger(__name__)

class LRUCache:
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> Optional[tuple]:
        if key in self.cache:
            self.cache.move_to_end(key)
            value, expiry = self.cache[key]
            if time.time() < expiry:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time() + ttl)

        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()

class CacheService:
    def __init__(self):
        self.redis_client = None
        self.redis_url = config.REDIS_URL

        if self.redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed, using in-memory cache: {str(e)}")
                self.redis_client = None

        if not self.redis_client:
            logger.info("Using in-memory LRU cache")
            self.lru_cache = LRUCache()

    def get(self, key: str) -> Optional[Any]:
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    import json
                    return json.loads(value)
                return None
            else:
                return self.lru_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        try:
            if self.redis_client:
                import json
                self.redis_client.setex(key, ttl, json.dumps(value))
            else:
                self.lru_cache.set(key, value, ttl)
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")

    def delete(self, key: str):
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.lru_cache.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")

    def clear(self):
        try:
            if self.redis_client:
                self.redis_client.flushdb()
            else:
                self.lru_cache.clear()
        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")

    def get_search_results(self, key: str) -> Optional[Any]:
        return self.get(f"search:{key}")

    def set_search_results(self, key: str, value: Any, ttl: int = 900):
        self.set(f"search:{key}", value, ttl)

    def get_fx_rates(self) -> Optional[Any]:
        return self.get("fx:rates")

    def set_fx_rates(self, value: Any):
        self.set("fx:rates", value, ttl=3600)

    def get_prediction(self, key: str) -> Optional[Any]:
        return self.get(f"prediction:{key}")

    def set_prediction(self, key: str, value: Any):
        self.set(f"prediction:{key}", value, ttl=3600)

cache_service = CacheService()
