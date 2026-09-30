"""
Redis-backed fixed-window rate limiter.

Applied per-user (when authenticated) or per-IP (anonymous) to
authentication, AI, disease-analysis, search, model, and upload endpoints.

Limits are never hardcoded at the call site: buckets resolve their ceiling
from `Settings` so operators can retune them via the environment.
"""
import time

from fastapi import Depends, Request
from redis import RedisError

from app.core.config import settings
from app.core.deps import get_optional_user
from app.core.exceptions import RateLimitedError
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.models.user import User

logger = get_logger("bhoomi.rate_limit")

# bucket name -> (settings attribute, default)
_BUCKETS: dict[str, tuple[str, int]] = {
    "default": ("RATE_LIMIT_DEFAULT_PER_MINUTE", 120),
    "auth": ("RATE_LIMIT_AUTH_PER_MINUTE", 10),
    "ai": ("RATE_LIMIT_AI_PER_MINUTE", 10),
    "disease": ("RATE_LIMIT_DISEASE_PER_MINUTE", 6),
}


def _client_key(request: Request, user: User | None) -> str:
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _limit_for(bucket: str, override: int | None) -> int:
    if override is not None:
        return override
    attr, default = _BUCKETS.get(bucket, _BUCKETS["default"])
    return int(getattr(settings, attr, default))


def rate_limit(bucket: str, limit_per_minute: int | None = None):
    """Return a FastAPI dependency enforcing a requests-per-60s ceiling.

    `limit_per_minute` is optional; omitting it resolves the ceiling from
    settings using the bucket name.
    """

    def _dep(request: Request, user: User | None = Depends(get_optional_user)) -> None:
        limit = _limit_for(bucket, limit_per_minute)
        r: RedisError | get_redis
        r = get_redis()
        window = int(time.time() // 60)
        key = f"ratelimit:{bucket}:{_client_key(request, user)}:{window}"
        try:
            current = r.incr(key)
            if current == 1:
                r.expire(key, 65)
        except Exception:
            # Without Redis there is no counter to enforce. In production we
            # reject rather than silently removing the protection; in
            # development a hard failure would be more disruptive than useful.
            if settings.is_production:
                logger.error("rate_limit_backend_unavailable", bucket=bucket)
                raise RateLimitedError()
            logger.warning("rate_limit_backend_unavailable_fail_open", bucket=bucket)
            return
        if current > limit:
            raise RateLimitedError()

    return _dep
