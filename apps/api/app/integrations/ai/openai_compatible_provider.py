"""
Generic OpenAI-compatible chat-completions provider.

NVIDIA NIM exposes an OpenAI-compatible `/chat/completions` endpoint, so the
same client implementation serves both `NVIDIA_*` and `OPENAI_*` (or any
other OpenAI-compatible) configuration -- only the base URL, API key, and
model name differ. This is what keeps BHOOMI from being tightly coupled to
any single AI vendor.
"""
import time

import httpx

from app.core.logging import get_logger
from app.integrations.ai.base import AICompletion, AIMessage, AIProvider, AIProviderError

logger = get_logger("bhoomi.ai.openai_compatible")

# Transient conditions worth one more attempt: shared/free inference endpoints
# routinely return 503 (worker saturated) or 429 (rate limited) and succeed on
# a retry a second later. 4xx client errors are never retried.
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = 0.4


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: int = 20,
        max_attempts: int = 3,
        slot: str = "primary",
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.slot = slot

    def _configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[AIMessage], *, temperature: float = 0.2, max_tokens: int = 700) -> AICompletion:
        if not self._configured():
            raise AIProviderError(f"{self.name} provider is not configured (missing API key).")

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        start = time.monotonic()

        last_error = "unknown error"
        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                except httpx.TimeoutException as exc:
                    logger.warning("ai_provider_timeout", provider=self.name, model=self.model, timeout=self.timeout)
                    raise AIProviderError(f"{self.name} timed out after {self.timeout}s") from exc
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    if attempt < self.max_attempts:
                        logger.warning(
                            "ai_provider_retry_after_error",
                            provider=self.name,
                            model=self.model,
                            attempt=attempt,
                            error=last_error,
                        )
                        time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                        continue
                    logger.warning("ai_provider_request_failed", provider=self.name, error=last_error)
                    raise AIProviderError(f"{self.name} request failed: {last_error}") from exc

                if resp.status_code == 200:
                    break

                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code in RETRY_STATUS and attempt < self.max_attempts:
                    logger.warning(
                        "ai_provider_retrying",
                        provider=self.name,
                        model=self.model,
                        attempt=attempt,
                        status=resp.status_code,
                    )
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue

                logger.warning(
                    "ai_provider_request_failed",
                    provider=self.name,
                    model=self.model,
                    status=resp.status_code,
                )
                raise AIProviderError(f"{self.name} request failed: {last_error}")

        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError, ValueError) as exc:
            raise AIProviderError(f"{self.name} returned an unexpected response shape.") from exc

        # Some shared inference endpoints answer HTTP 200 with an empty or
        # non-string body. Treat that as a failure so the chain advances to
        # the next model instead of surfacing a blank interpretation.
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError(f"{self.name} returned an empty completion.")

        return AICompletion(
            content=content.strip(),
            provider=self.name,
            model=self.model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )
