"""API 공통 의존성 — 엔진 선택과 인메모리 저장소.

v1 은 단일 학원 PC 배포이므로 저장소는 프로세스 메모리 + 파일로 시작한다.
PostgreSQL 전환 지점을 한 군데(`Store`)로 모아 둔다.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.generation.engines.base import ComposerEngine
from app.generation.engines.stub import StubComposerEngine
from app.generation.pipeline import CompositionPipeline


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
    jobs: dict[str, Any] = field(default_factory=dict)
    recitals: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def next_id(self, prefix: str, bucket: dict) -> str:
        with self._lock:
            return f"{prefix}-{len(bucket) + 1:04d}"


STORE = Store()


def get_store() -> Store:
    return STORE
