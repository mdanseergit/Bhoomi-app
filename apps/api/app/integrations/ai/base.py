"""
AIProvider abstraction.

BHOOMI must never be tightly coupled to a single AI vendor. Every concrete
provider (NVIDIA NIM, any OpenAI-compatible endpoint, future local
inference) implements this same interface so the rest of the application
only ever talks to `AIProvider`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class AICompletion:
    content: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class AIProviderError(Exception):
    pass


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, messages: list[AIMessage], *, temperature: float = 0.2, max_tokens: int = 700) -> AICompletion:
        ...
