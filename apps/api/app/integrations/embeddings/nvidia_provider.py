"""
NVIDIAEmbeddingProvider -- calls an NVIDIA NIM (or any OpenAI-compatible)
`/embeddings` endpoint. Requires NVIDIA_API_KEY to be configured; otherwise
`EmbeddingService` falls back to the deterministic local provider.
"""
import httpx

from app.core.config import settings
from app.integrations.embeddings.base import EmbeddingProvider


class EmbeddingProviderError(Exception):
    pass


class NVIDIAEmbeddingProvider(EmbeddingProvider):
    name = "nvidia"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not settings.NVIDIA_API_KEY:
            raise EmbeddingProviderError("NVIDIA_API_KEY is not configured.")
        headers = {"Authorization": f"Bearer {settings.NVIDIA_API_KEY}"}
        try:
            with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
                resp = client.post(
                    f"{settings.NVIDIA_BASE_URL}/embeddings",
                    json={"model": "nvidia/nv-embed-v1", "input": texts},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(str(exc)) from exc
