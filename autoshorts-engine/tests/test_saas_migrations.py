"""마이그레이션 테스트 — 실제 PostgreSQL 에 적용한다."""

from __future__ import annotations

import pytest

from saas import migrate
from saas.db import DatabaseError

# 명세(CLAUDE_CODE_EXECUTION_V2.md Phase 2 "DB 최소")가 요구하는 표.
REQUIRED_TABLES = {
    "users", "workspaces", "workspace_members", "projects", "source_assets",
    "transcripts", "clip_candidates", "render_jobs", "render_outputs",
    "usage_events", "cost_events", "rights_confirmations",
}


def table_names(db) -> set[str]:
    return {
        row["tablename"]
        for row in db.fetch_all("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    }


def test_required_tables_exist(db):
    missing = REQUIRED_TABLES - table_names(db)
    assert not missing, f"명세가 요구하는 표가 없습니다: {sorted(missing)}"


def test_every_tenant_table_carries_workspace_id(db):
    """조인을 타야 소유자를 알 수 있는 표가 있으면 격리가 언젠가 샌다."""
    tenant_tables = REQUIRED_TABLES - {"users", "workspaces", "workspace_members"}
    columns = db.fetch_all(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'workspace_id'"
    )
    have = {row["table_name"] for row in columns}
    assert tenant_tables <= have, f"workspace_id 가 없는 표: {sorted(tenant_tables - have)}"


def test_reapply_is_a_noop(db):
    assert migrate.apply_all(db) == []


def test_applied_versions_recorded(db):
    known = migrate.applied_versions(db)
    assert set(known) == {m.version for m in migrate.discover()}


def test_changing_an_applied_migration_is_refused(db, tmp_path):
    """운영 중인 스키마를 조용히 갈아끼우는 사고를 막는다."""
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(DatabaseError, match="바뀌었습니다"):
        migrate.apply_all(db, tmp_path)


def test_duplicate_versions_refused(tmp_path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0001_b.sql").write_text("SELECT 2;", encoding="utf-8")
    with pytest.raises(DatabaseError, match="중복"):
        migrate.discover(tmp_path)


def test_bad_filename_refused(tmp_path):
    (tmp_path / "initial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(DatabaseError, match="이름"):
        migrate.discover(tmp_path)


def test_check_constraints_reject_bad_state(db):
    """상태 문자열은 DB 가 지킨다. 애플리케이션 버그가 데이터를 오염시키지 못한다."""
    db.execute(
        "INSERT INTO users (id, email, password_hash) VALUES ('u1', 'a@b.com', 'x')"
    )
    db.execute("INSERT INTO workspaces (id, name, owner_user_id) VALUES ('w1', 'W', 'u1')")
    with pytest.raises(Exception):
        db.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) "
            "VALUES ('w1', 'u1', 'superadmin')"
        )


def test_credits_cannot_go_negative(db):
    db.execute("INSERT INTO users (id, email, password_hash) VALUES ('u1', 'a@b.com', 'x')")
    db.execute("INSERT INTO workspaces (id, name, owner_user_id) VALUES ('w1', 'W', 'u1')")
    with pytest.raises(Exception):
        db.execute("UPDATE workspaces SET credit_balance = -1 WHERE id = 'w1'")
