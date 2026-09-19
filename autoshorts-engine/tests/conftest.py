"""공용 테스트 픽스처."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autoshorts.models import Segment, Transcript, Word  # noqa: E402


def make_segment(start: float, end: float, text: str) -> Segment:
    """텍스트를 공백 단위로 균등 분할해 단어 타임스탬프를 붙인 세그먼트."""
    tokens = text.split()
    span = (end - start) / max(len(tokens), 1)
    words = [
        Word(start + index * span, start + (index + 1) * span, token)
        for index, token in enumerate(tokens)
    ]
    return Segment(start=start, end=end, text=text, words=words)


@pytest.fixture
def transcript() -> Transcript:
    """5초 단위 발화 36개 = 180초짜리 전사본."""
    lines = [
        "안녕하세요 오늘은 아주 중요한 이야기를 해보려고 합니다",
        "사실 이 방법은 아무도 알려주지 않는 비밀입니다",
        "제가 처음 시작했을 때는 정말 막막했어요",
        "그런데 한 가지 원칙을 지키니까 결과가 달라졌습니다",
        "왜냐하면 사람들은 대부분 이 단계를 건너뛰기 때문입니다",
        "구독과 좋아요 부탁드립니다",
    ]
    segments = []
    for index in range(36):
        start = index * 5.0
        segments.append(make_segment(start, start + 4.5, lines[index % len(lines)]))
    return Transcript(segments=segments, language="ko", duration=180.0)


@pytest.fixture
def short_transcript() -> Transcript:
    """40초짜리 짧은 전사본."""
    segments = [
        make_segment(0.0, 12.0, "첫 번째 문장입니다 아주 중요한 내용이 여기 있습니다"),
        make_segment(12.5, 26.0, "두 번째 문장은 조금 더 길게 이어집니다 진짜 핵심은 이것입니다"),
        make_segment(26.5, 40.0, "마지막 문장으로 이야기를 정리하겠습니다 감사합니다"),
    ]
    return Transcript(segments=segments, language="ko", duration=40.0)


# ── Phase 2 (SaaS) 픽스처 ──────────────────────────────────
#
# 진짜 PostgreSQL 에 붙는다. 격리·동시성·SKIP LOCKED 는 가짜로 검증할 수 없다.
# DSN 이 없거나 서버가 없으면 해당 테스트만 건너뛴다(엔진 테스트는 영향 없음).

import os  # noqa: E402


def _test_dsn() -> str:
    return (
        os.environ.get("AUTOSHORTS_TEST_DATABASE_URL")
        or os.environ.get("AUTOSHORTS_DATABASE_URL")
        or ""
    )


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    dsn = _test_dsn()
    if not dsn:
        pytest.skip("AUTOSHORTS_TEST_DATABASE_URL 이 없어 DB 테스트를 건너뜁니다.")
    try:
        import psycopg  # noqa: PLC0415
    except ImportError:
        pytest.skip("psycopg 가 설치되어 있지 않습니다.")
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(f"테스트 데이터베이스에 연결할 수 없습니다: {type(exc).__name__}")
    return dsn


@pytest.fixture(scope="session")
def _migrated_db(pg_dsn):
    """스키마를 처음부터 만든다. 세션당 한 번."""
    from saas import migrate
    from saas.db import Database

    db = Database(pg_dsn, max_connections=12)
    db.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    migrate.apply_all(db)
    yield db
    db.close()


@pytest.fixture
def db(_migrated_db):
    """테스트마다 데이터만 비운다. 스키마 재생성은 느리다."""
    _migrated_db.execute(
        "TRUNCATE users, workspaces, workspace_members, projects, project_revisions, "
        "source_assets, rights_confirmations, upload_tickets, transcripts, render_jobs, "
        "clip_candidates, render_outputs, job_progress_events, job_queue, usage_events, "
        "cost_events, credit_ledger, sessions RESTART IDENTITY CASCADE"
    )
    return _migrated_db
