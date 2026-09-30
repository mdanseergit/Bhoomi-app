"""
LocalStorageBackend -- filesystem-backed storage for local development.

Uploaded files are written under a randomized, non-guessable path (never
the original filename) and never placed in a publicly web-served directory.
Swap for an S3-compatible backend (`STORAGE_BACKEND=s3`) in production;
`StorageBackend` keeps calling code identical either way.
"""
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.integrations.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self.root = Path(settings.STORAGE_LOCAL_PATH)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, suggested_ext: str, folder: str) -> str:
        subdir = self.root / folder
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{suggested_ext.lstrip('.')}"
        path = subdir / filename
        with open(path, "wb") as fh:
            fh.write(content)
        os.chmod(path, 0o600)
        return f"{folder}/{filename}"

    def url_for(self, key: str) -> str:
        # In local dev this is served through a private API route, not a
        # public static path -- see app.api.v1.disease.get_scan_image.
        return f"/api/v1/disease/image/{key}"
