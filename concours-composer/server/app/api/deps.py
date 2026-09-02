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
from app.store.backup import BackupKeeper
from app.store.persistence import SqlitePersistence

log = logging.getLogger(__name__)

# 파일로 내리는 버킷. 순서가 곧 저장 순서다.
PERSISTED = (
    "students",
    "competitions",
    "requests",
    "motifs",
    "plans",
    "compositions",
    "versions",
    "jobs",
    "recitals",
    "judgements",
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
    # 만든 곡이 파일 하나에 들어 있다 — 한 번의 사고로 전부 잃지 않게 사본을 뜬다.
    backups: BackupKeeper | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # 저장은 요청 밖에서 몰아 한다 — 곡이 쌓여도 버튼이 느려지지 않게.
    _dirty: bool = False
    _dirty_lock: threading.Lock = field(default_factory=threading.Lock)
    _writer: threading.Thread | None = None

    def next_id(self, prefix: str, bucket: dict) -> str:
        with self._lock:
            return f"{prefix}-{len(bucket) + 1:04d}"

    # ── 곡 제목 ──────────────────────────────────────────────────────────
    # 파는 곡의 제목은 상품명이다. 프로그램이 지은 이름을 그대로 쓸 수도 있지만,
    # 원장이 고쳐 두면 그 이름이 악보·음원·꾸러미·등록 서류 전부에 따라간다.
    # 제목을 여러 군데서 따로 계산하면 파일마다 다른 이름이 찍힌다 — 그래서 여기 하나다.
    def title_of(self, composition_id: str) -> str:
        custom = self.jobs.get("titles", {}).get(composition_id)
        if isinstance(custom, str) and custom.strip():
            return custom.strip()
        res = self.compositions.get(composition_id)
        if res is None:
            return composition_id
        return res.plan.title_candidates[0] if res.plan.title_candidates else composition_id

    def set_title(self, composition_id: str, title: str) -> str:
        """빈 제목이면 프로그램이 지은 이름으로 되돌린다."""
        titles = self.jobs.setdefault("titles", {})
        clean = title.strip()
        if clean:
            titles[composition_id] = clean
        else:
            titles.pop(composition_id, None)
        return self.title_of(composition_id)

    # ── 영속화 ───────────────────────────────────────────────────────────
    def attach(self, path: Path) -> None:
        """SQLite 파일에 붙이고 있던 내용을 곧바로 읽어들인다."""
        self.persistence = SqlitePersistence(path)
        self.backups = BackupKeeper(path)
        self.load()

    def load(self) -> None:
        if self.persistence is None:
            return
        for name, value in self.persistence.load().items():
            if name in PERSISTED and isinstance(value, dict):
                setattr(self, name, value)

    def save_soon(self) -> None:
        """저장을 예약한다 — 요청을 붙잡아 두지 않는다.

        저장은 버킷 전체를 다시 직렬화하는 일이라 곡이 쌓일수록 느려진다(200곡에 2초).
        그것을 요청 경로에 두면 곡이 늘수록 버튼 하나가 느려진다. 그래서 표시만 해 두고
        일꾼 하나가 몰아서 저장한다 — 연달아 눌러도 저장은 한 번이면 된다.

        대신 저장 전에 프로그램이 죽으면 마지막 몇 초를 잃는다. 끄기 버튼과 종료 훅이
        동기 저장을 하므로 정상 종료에서는 잃지 않고, 비정상 종료는 백업이 받는다.
        """
        if self.persistence is None:
            return
        with self._dirty_lock:
            self._dirty = True
            if self._writer is not None and self._writer.is_alive():
                return
            self._writer = threading.Thread(target=self._drain, daemon=True, name="store-save")
            self._writer.start()

    def _drain(self) -> None:
        """더러운 표시가 사라질 때까지 저장한다. 몰린 쓰기를 한 번으로 합친다."""
        while True:
            with self._dirty_lock:
                if not self._dirty:
                    return
                self._dirty = False
            self.save()

    def flush(self) -> None:
        """예약된 저장이 끝날 때까지 기다린다 — 종료 직전에 쓴다."""
        writer = self._writer
        if writer is not None and writer.is_alive():
            writer.join(timeout=20)
        self.save()

    def save(self) -> None:
        if self.persistence is None:
            return
        try:
            self.persistence.save({name: getattr(self, name) for name in PERSISTED})
        except (sqlite3.Error, OSError) as e:
            # 저장에 실패해도 응답은 나가야 한다. 다음 쓰기에서 다시 시도한다.
            log.warning("저장소 스냅샷 실패: %s", e)
            return
        if self.backups is not None:
            # 사본은 시간 간격을 두고 뜬다(BackupKeeper). 실패해도 저장을 막지 않는다.
            self.backups.maybe_backup()


STORE = Store()


def get_store() -> Store:
    return STORE
