"""Storage 추상화.

Phase 1 은 로컬 디스크만 쓴다. 하지만 SaaS worker 는 결국 S3/R2 에 쓰게 되므로,
파이프라인 바깥에서 **경로 대신 URI 로 말하는 경계**를 지금 만들어 둔다.

파이프라인 자체는 여전히 로컬 경로로 동작한다(FFmpeg 가 그래야 한다). Storage 는
"작업이 끝난 산출물을 어디에 두고 어떤 주소로 부를 것인가" 만 담당한다.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .utils import ensure_dir, get_logger

__all__ = ["Storage", "LocalStorage", "StorageError", "StoredObject"]

LOG = get_logger("storage")


class StorageError(RuntimeError):
    """저장소 작업 실패."""


class StoredObject:
    """저장된 객체 하나."""

    def __init__(self, uri: str, size_bytes: int = 0, local_path: Path | None = None) -> None:
        self.uri = uri
        self.size_bytes = size_bytes
        self.local_path = local_path

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri, "size_bytes": self.size_bytes}

    def __repr__(self) -> str:  # pragma: no cover - 디버깅용
        return f"StoredObject({self.uri!r}, {self.size_bytes}B)"


class Storage(ABC):
    """산출물 저장소 인터페이스.

    Phase 2 에서 S3Storage 를 추가할 때 이 인터페이스만 구현하면 된다.
    """

    @abstractmethod
    def put(self, local_path: str | Path, key: str) -> StoredObject:
        """로컬 파일을 저장소에 올리고 주소를 돌려준다."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """이미 저장돼 있는지. 멱등 재실행 판단에 쓴다."""

    @abstractmethod
    def uri_for(self, key: str) -> str:
        """키에 대응하는 주소."""

    @abstractmethod
    def open_local(self, key: str) -> Path:
        """로컬 경로를 돌려준다. 원격 저장소면 내려받아 캐시한다."""


class LocalStorage(Storage):
    """로컬 디렉터리 기반 구현.

    ``root`` 밖으로 나가는 키는 거부한다. 키가 사용자 입력에서 올 수 있으므로
    ``../`` 같은 경로 탈출을 막아야 한다.
    """

    scheme = "file"

    def __init__(self, root: str | Path) -> None:
        self.root = ensure_dir(Path(root)).resolve()

    def _resolve(self, key: str) -> Path:
        cleaned = str(key).strip().lstrip("/")
        if not cleaned:
            raise StorageError("빈 키는 쓸 수 없습니다.")
        candidate = (self.root / cleaned).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise StorageError(f"저장소 루트를 벗어나는 키입니다: {key!r}")
        return candidate

    def put(self, local_path: str | Path, key: str) -> StoredObject:
        source = Path(local_path)
        if not source.exists():
            raise StorageError(f"올릴 파일이 없습니다: {source}")
        destination = self._resolve(key)
        ensure_dir(destination.parent)
        if source.resolve() != destination:
            shutil.copy2(source, destination)
        size = destination.stat().st_size
        LOG.debug("저장: %s (%d bytes)", key, size)
        return StoredObject(uri=self.uri_for(key), size_bytes=size, local_path=destination)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except StorageError:
            return False

    def uri_for(self, key: str) -> str:
        return f"{self.scheme}://{self._resolve(key)}"

    def open_local(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.exists():
            raise StorageError(f"저장소에 없습니다: {key}")
        return path
