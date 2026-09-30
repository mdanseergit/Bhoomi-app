from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, suggested_ext: str, folder: str) -> str:
        """Persists `content` and returns an opaque, randomized storage key/path."""

    @abstractmethod
    def url_for(self, key: str) -> str:
        """Returns a (signed, in production) URL for reading the stored object."""
