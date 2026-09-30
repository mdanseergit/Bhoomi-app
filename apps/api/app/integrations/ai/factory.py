from app.core.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.deterministic_provider import DeterministicFallbackProvider
from app.integrations.ai.openai_compatible_provider import OpenAICompatibleProvider


def _nvidia_providers() -> list[AIProvider]:
    """One provider per configured model, in configured order.

    Every model in the chain is served by the same NVIDIA NIM endpoint, so a
    single API key covers primary and fallback. Models are named
    ``nvidia:<model-id>`` so logs and usage records identify exactly which
    model produced a response.
    """
    providers: list[AIProvider] = []
    if not settings.NVIDIA_API_KEY:
        return providers
    for index, model in enumerate(settings.ai_model_chain):
        providers.append(
            OpenAICompatibleProvider(
                name=f"nvidia:{model}",
                base_url=settings.NVIDIA_BASE_URL,
                api_key=settings.NVIDIA_API_KEY,
                model=model,
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
                max_attempts=settings.AI_MAX_ATTEMPTS,
                slot="primary" if index == 0 else "fallback",
            )
        )
    return providers


def build_provider_chain() -> list[AIProvider]:
    """
    Builds the ordered provider fallback chain for the BHOOMI intelligence
    engine. The chain is driven entirely by environment configuration:

        AI_MODEL_CHAIN            (optional explicit comma-separated models)
        AI_PRIMARY_MODEL          first attempt
        AI_FALLBACK_MODEL         second attempt
        AI_PROVIDER_ORDER         which provider families to enable

    The chain always terminates in the deterministic BHOOMI agriculture
    engine, which derives output from the real farm data already collected
    and never fabricates measurements.
    """
    providers: list[AIProvider] = []

    for name in settings.ai_provider_order_list:
        if name == "nvidia":
            providers.extend(_nvidia_providers())
        elif name == "deterministic":
            providers.append(DeterministicFallbackProvider())

    if not any(isinstance(p, DeterministicFallbackProvider) for p in providers):
        providers.append(DeterministicFallbackProvider())

    return providers
