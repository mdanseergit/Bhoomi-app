from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.embeddings.deterministic_local_provider import DeterministicLocalEmbeddingProvider
from app.integrations.embeddings.nvidia_provider import EmbeddingProviderError, NVIDIAEmbeddingProvider

logger = get_logger("bhoomi.embeddings")


class EmbeddingService:
    def __init__(self) -> None:
        self.local = DeterministicLocalEmbeddingProvider(dimension=settings.EMBEDDING_DIM)
        self.nvidia = NVIDIAEmbeddingProvider(dimension=settings.EMBEDDING_DIM)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if settings.EMBEDDING_PROVIDER == "nvidia":
            try:
                return self.nvidia.embed(texts)
            except EmbeddingProviderError as exc:
                logger.warning("embedding_provider_failed_falling_back", error=str(exc))
        return self.local.embed(texts)
