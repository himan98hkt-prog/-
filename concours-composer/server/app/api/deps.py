"""API 공통 의존성 — 엔진 선택과 저장소.

v1 은 단일 학원 PC 배포다. 버킷은 프로세스 메모리에 두되, 쓰기가 일어난 요청마다
SQLite 파일로 스냅샷을 남긴다 — 서버를 재시작해도 만든 곡이 사라지지 않는다.
PostgreSQL 전환 지점은 여전히 `Store` 한 군데다.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.generation.engines.base import ComposerEngine
from app.generation.engines.stub import StubComposerEngine
from app.generation.pipeline import CompositionPipeline
from app.store.persistence import SqlitePersistence

log = logging.getLogger(__name__)

# 파일로 내리는 버킷. 순서가 곧 저장 순서다.
PERSISTED = (
    "students", "competitions", "requests", "motifs",
    "plans", "compositions", "versions", "jobs", "recitals", "judgements",
    "rights",
)


def get_engine() -> ComposerEngine:
    """API 키가 있으면 Claude, 없으면 규칙 기반 스텁."""
    s = get_settings()
    if s.has_api_key:
        from app.generation.engines.claude_engine import ClaudeComposerEngine

        return ClaudeComposerEngine(s)
    return StubComposerEngine()


def get_pipeline() -> CompositionPipeline:
    return CompositionPipeline(get_engine())


@dataclass
class Store:
    """PostgreSQL 로 옮길 때 이 클래스만 바꾸면 된다."""

    students: dict[str, Any] = field(default_factory=dict)
    competitions: dict[str, Any] = field(default_factory=dict)
    requests: dict[str, Any] = field(default_factory=dict)
    motifs: dict[str, list] = field(default_factory=dict)
    plans: dict[str, Any] = field(default_factory=dict)
    compositions: dict[str, Any] = field(default_factory=dict)
    versions: dict[str, list] = field(default_factory=dict)
    # 사전 전문심사 결과. 곡을 내놓기 전에 통과했는지 판단하는 근거이므로 함께 남긴다.
    judgements: dict[str, Any] = field(default_factory=dict)
    # 작곡가 신원(예명·실명)과 곡별 권리 상태. 실명은 이 파일 밖으로 나가지 않는다.
    rights: dict[str, Any] = field(default_factory=dict)
    jobs: dict[str, Any] = field(default_factory=dict)
    recitals: dict[str, Any] = field(default_factory=dict)
    persistence: SqlitePersistence | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def next_id(self, prefix: str, bucket: dict) -> str:
        with self._lock:
            return f"{prefix}-{len(bucket) + 1:04d}"

    # ── 영속화 ───────────────────────────────────────────────────────────
    def attach(self, path: Path) -> None:
        """SQLite 파일에 붙이고 있던 내용을 곧바로 읽어들인다."""
        self.persistence = SqlitePersistence(path)
        self.load()

    def load(self) -> None:
        if self.persistence is None:
            return
        for name, value in self.persistence.load().items():
            if name in PERSISTED and isinstance(value, dict):
                setattr(self, name, value)

    def save(self) -> None:
        if self.persistence is None:
            return
        try:
            self.persistence.save({name: getattr(self, name) for name in PERSISTED})
        except (sqlite3.Error, OSError) as e:
            # 저장에 실패해도 응답은 나가야 한다. 다음 쓰기에서 다시 시도한다.
            log.warning("저장소 스냅샷 실패: %s", e)


STORE = Store()


def get_store() -> Store:
    return STORE
