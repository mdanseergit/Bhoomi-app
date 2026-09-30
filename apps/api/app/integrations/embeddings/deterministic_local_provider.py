"""
DeterministicLocalEmbeddingProvider -- a dependency-free local embedding
model used when no external embedding API key is configured.

It is a deterministic hashed bag-of-words projection (not a trained neural
embedding). It is sufficient for local development / demo semantic search
over the seeded knowledge base and keeps the RAG pipeline fully functional
without any vendor dependency. Swap in `NVIDIAEmbeddingProvider` or another
API-backed provider in production for real semantic quality.
"""
import hashlib
import math
import re

from app.integrations.embeddings.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-zA-Z]{2,}")


class DeterministicLocalEmbeddingProvider(EmbeddingProvider):
    name = "deterministic_local"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
