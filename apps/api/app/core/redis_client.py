"""
Shared Redis client used for caching external provider responses,
rate limiting, and idempotency/duplicate-request detection for AI calls.
"""
from functools import lru_cache
from typing import Any

import redis

from app.core.config import settings

_fake_redis_instance: Any = None


@lru_cache
def get_redis() -> Any:
    if settings.REDIS_URL:
        return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    global _fake_redis_instance
    if _fake_redis_instance is None:
        import fakeredis

        _fake_redis_instance = fakeredis.FakeRedis(decode_responses=True)
    return _fake_redis_instance

