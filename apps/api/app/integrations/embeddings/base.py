from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    name: str = "base"
    dimension: int = 384

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
