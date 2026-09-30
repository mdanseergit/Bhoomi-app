"""
Shared Redis client used for caching external provider responses,
rate limiting, and idempotency/duplicate-request detection for AI calls.
"""
from functools import lru_cache

import redis

from app.core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
