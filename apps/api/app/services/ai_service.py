"""
AIService -- the single entry point the rest of the application uses to
talk to a language model.

Responsibilities:
  - walk the provider fallback chain (NVIDIA NIM -> OpenAI-compatible -> deterministic)
  - enforce per-user daily quotas
  - cache identical requests briefly to avoid duplicate spend
  - record every call to `ai_usage` for cost observability
  - never let an AI outage take down the rest of the app
"""
import hashlib
import json
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.prompts import SYSTEM_PROMPT
from app.core.redis_client import get_redis
from app.integrations.ai.base import AICompletion, AIMessage, AIProviderError
from app.integrations.ai.factory import build_provider_chain
from app.integrations.ai.deterministic_provider import DeterministicFallbackProvider
from app.models.system import AIUsage

logger = get_logger("bhoomi.ai.service")


class AIQuotaExceededError(Exception):
    pass


class InvalidAIResponseError(AIProviderError):
    """Raised when a model returns text BHOOMI refuses to surface."""


# Substrings that indicate the model is echoing scaffolding, leaking the
# system prompt, or emitting obvious filler rather than real analysis.
_REFUSAL_MARKERS = (
    "i'm sorry",
    "i am sorry",
    "as an ai language model",
    "i cannot",
    "i can't help",
    "<|",
    "[inst]",
    "system prompt:",
    "you are a helpful",
    "bhoomi master system prompt",
    "lorem ipsum",
    "todo",
    "tbd",
    "xxx",
    "placeholder",
    "dummy value",
    "example.com",
    "john doe",
    "farm 01",
    "sample farm",
    "demo user",
    "test user",
)

# Structural scaffolding the model may echo back. Their *presence* is fine
# (the BHOOMI output format uses headings); leaking the instructions around
# them is not.
_LEAK_MARKERS = (
    "you are bhoomi",
    "bhoomi master system prompt",
    "user:",
    "assistant:",
)


def validate_ai_response(text: str) -> str:
    """Returns cleaned text, or raises InvalidAIResponseError.

    BHOOMI must never display a model response that is empty, is obviously
    placeholder/filler, or that exposes the internal system prompt.
    """
    if not isinstance(text, str):
        raise InvalidAIResponseError("Model response was not text.")

    cleaned = text.strip()
    if len(cleaned) < settings.AI_MIN_RESPONSE_CHARS:
        raise InvalidAIResponseError("Model response was too short to be useful.")

    lowered = cleaned.lower()
    for marker in _REFUSAL_MARKERS:
        if marker in lowered:
            raise InvalidAIResponseError(f"Model response contained a refusal or filler marker: {marker!r}.")

    for marker in _LEAK_MARKERS:
        if marker in lowered:
            raise InvalidAIResponseError("Model response appeared to leak internal instructions.")

    return cleaned


class AIService:
    def __init__(self) -> None:
        self.chain = build_provider_chain()
        self.redis = get_redis()

    def _quota_key(self, user_id: str) -> str:
        from datetime import date

        return f"ai:quota:{user_id}:{date.today().isoformat()}"

    def _check_quota(self, user_id: str | None) -> None:
        if not user_id:
            return
        key = self._quota_key(user_id)
        try:
            current = int(self.redis.get(key) or 0)
        except Exception:
            return
        if current >= settings.AI_DAILY_USER_QUOTA:
            raise AIQuotaExceededError("Daily AI request quota exceeded for this account.")

    def _increment_quota(self, user_id: str | None) -> None:
        if not user_id:
            return
        key = self._quota_key(user_id)
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60 * 60 * 26)
            pipe.execute()
        except Exception:
            pass

    def _cache_key(self, user_prompt: str) -> str:
        # The prompt *and* the active model chain are part of the key, so
        # rotating models or the BHOOMI prompt cannot serve stale output.
        signature = "|".join([user_prompt, ",".join(settings.ai_model_chain), settings.AI_PROVIDER_ORDER])
        digest = hashlib.sha256(signature.encode()).hexdigest()
        return f"ai:cache:{digest}"

    def explain(
        self,
        db: Session,
        *,
        user_id: str | None,
        request_type: str,
        user_prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        temperature: float = 0.2,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        """Returns (explanation_text, provider_name_used)."""
        try:
            self._check_quota(user_id)
        except AIQuotaExceededError as exc:
            logger.info("ai_quota_exceeded", user_id=user_id)
            self._log_usage(db, provider="none", model="none", user_id=user_id, request_type=request_type, status="quota_exceeded")
            return (
                "Daily AI usage limit reached for this account. Showing the deterministic "
                "advisory instead. Please try the AI explanation again tomorrow.",
                "quota_exceeded",
            )

        cache_key = self._cache_key(user_prompt)
        if use_cache:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    return cached, "cache"
            except Exception:
                pass

        messages = [AIMessage(role="system", content=system_prompt), AIMessage(role="user", content=user_prompt)]

        for provider in self.chain:
            if isinstance(provider, DeterministicFallbackProvider):
                break
            attempts = 2 if settings.AI_MAX_ATTEMPTS > 1 else 1
            for attempt in range(1, attempts + 1):
                try:
                    completion: AICompletion = provider.complete(
                        messages, temperature=temperature, max_tokens=settings.AI_MAX_TOKENS_OUT
                    )
                    content = validate_ai_response(completion.content)
                except InvalidAIResponseError as exc:
                    logger.warning(
                        "ai_response_rejected",
                        provider=provider.name,
                        model=getattr(provider, "model", "?"),
                        attempt=attempt,
                        error=str(exc),
                    )
                    if attempt < attempts:
                        continue
                    break
                except AIProviderError as exc:
                    logger.warning("ai_provider_failed_trying_next", provider=provider.name, error=str(exc))
                    break

                self._increment_quota(user_id)
                self._log_usage(
                    db,
                    provider=completion.provider,
                    model=completion.model,
                    user_id=user_id,
                    request_type=request_type,
                    tokens_in=completion.tokens_in,
                    tokens_out=completion.tokens_out,
                    latency_ms=completion.latency_ms,
                    status="success",
                )
                if use_cache:
                    try:
                        self.redis.setex(cache_key, 900, content)
                    except Exception:
                        pass
                return content, completion.provider

        # Deterministic rule engine: derived only from the real farm data
        # already collected, and explicitly labelled as rules-based output.
        deterministic = next((p for p in self.chain if isinstance(p, DeterministicFallbackProvider)), None)
        if deterministic is not None:
            try:
                completion = deterministic.complete(messages, temperature=0.0, max_tokens=settings.AI_MAX_TOKENS_OUT)
                self._log_usage(
                    db,
                    provider=completion.provider,
                    model=completion.model,
                    user_id=user_id,
                    request_type=request_type,
                    latency_ms=completion.latency_ms,
                    status="fallback",
                )
                return completion.content, completion.provider
            except AIProviderError:
                pass

        return (
            "AI explanation is currently unavailable. Rely on the structured advisory above.",
            "unavailable",
        )

    def _log_usage(
        self,
        db: Session,
        *,
        provider: str,
        model: str,
        user_id: str | None,
        request_type: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
        status: str = "success",
    ) -> None:
        try:
            db.add(
                AIUsage(
                    provider=provider,
                    model=model,
                    user_id=user_id,
                    request_type=request_type,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    status=status,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("ai_usage_log_failed")
