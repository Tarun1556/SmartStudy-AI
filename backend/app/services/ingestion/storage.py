from abc import ABC, abstractmethod
import os
import re
import uuid
from typing import Optional, BinaryIO
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class StorageProvider(ABC):
    @abstractmethod
    def save(self, directory: str, filename: str, data: bytes | BinaryIO) -> str:
        ...

    @abstractmethod
    def load(self, file_path: str) -> bytes:
        ...

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        ...

    @abstractmethod
    def delete(self, file_path: str) -> None:
        ...

    @abstractmethod
    def get_absolute_path(self, file_path: str) -> str:
        ...


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _safe(self, name: str) -> str:
        name = re.sub(r'[^\w.\- ]', '_', name)
        return name.strip() or f"file_{uuid.uuid4().hex}"

    def save(self, directory: str, filename: str, data: bytes | BinaryIO) -> str:
        full_dir = self.base_path / directory
        full_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe(filename)
        unique = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        target = full_dir / unique

        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            with open(target, "wb") as f:
                while True:
                    chunk = data.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

        return str(target.relative_to(self.base_path))

    def load(self, file_path: str) -> bytes:
        full = self.base_path / file_path
        return full.read_bytes()

    def exists(self, file_path: str) -> bool:
        return (self.base_path / file_path).exists()

    def delete(self, file_path: str) -> None:
        full = self.base_path / file_path
        if full.exists():
            full.unlink()

    def get_absolute_path(self, file_path: str) -> str:
        return str(self.base_path / file_path)


def get_storage_provider() -> StorageProvider:
    prov = settings.STORAGE_PROVIDER.lower()
    if prov == "local":
        return LocalStorageProvider(settings.STORAGE_LOCAL_PATH)
    return LocalStorageProvider(settings.STORAGE_LOCAL_PATH)
