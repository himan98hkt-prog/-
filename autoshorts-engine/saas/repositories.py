"""데이터 접근 계층.

모든 메서드는 첫 인자로 ``workspace_id`` 를 받는다(사용자 표 제외). 이것이
:mod:`saas.tenancy` 가 말하는 "질의 수준 격리"의 실제 모습이다. 조회 결과가
비어 있으면 ``None`` 을 돌려주고, 호출부가 :class:`~saas.tenancy.NotFound` 로
바꾼다 — 저장소는 "없다"와 "남의 것"을 구분하지 않는다.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from .auth import (
    InvalidCredentials,
    Principal,
    hash_password,
    new_id,
    new_token,
    normalize_email,
    session_expiry,
    token_fingerprint,
    verify_password,
)
from .db import Database

__all__ = [
    "UserRepository",
    "WorkspaceRepository",
    "ProjectRepository",
    "AssetRepository",
    "TranscriptRepository",
    "ClipRepository",
    "OutputRepository",
    "ProgressRepository",
    "DuplicateEmail",
]


class DuplicateEmail(RuntimeError):
    """이미 가입된 이메일."""


def _jsonb(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


class _Repo:
    def __init__(self, db: Database) -> None:
        self.db = db


# ── 사용자 · 세션 ───────────────────────────────────────────


class UserRepository(_Repo):
    def create(self, email: str, password: str, display_name: str = "") -> dict[str, Any]:
        normalized = normalize_email(email)
        user_id = new_id("usr")
        try:
            with self.db.transaction() as cur:
                cur.execute(
                    "INSERT INTO users (id, email, display_name, password_hash) "
                    "VALUES (%s, %s, %s, %s) RETURNING id, email, display_name, created_at",
                    (user_id, normalized, display_name or normalized.split("@")[0],
                     hash_password(password)),
                )
                row = cur.fetchone()
        except Exception as exc:
            if "users_email_key" in str(exc):
                raise DuplicateEmail("이미 가입된 이메일입니다.") from exc
            raise
        return {"id": row[0], "email": row[1], "display_name": row[2], "created_at": row[3]}

    def get(self, user_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT id, email, display_name, created_at, disabled_at FROM users WHERE id = %s",
            (user_id,),
        )

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        """성공하면 사용자 행. 실패는 이유를 구분하지 않고 같은 예외."""
        try:
            normalized = normalize_email(email)
        except Exception as exc:
            raise InvalidCredentials("이메일 또는 비밀번호가 올바르지 않습니다.") from exc
        row = self.db.fetch_one(
            "SELECT id, email, display_name, password_hash, disabled_at "
            "FROM users WHERE email = %s",
            (normalized,),
        )
        # 계정이 없어도 해시 검증을 한 번 돌려 응답 시간 차이를 줄인다.
        stored = row["password_hash"] if row else (
            "scrypt$16384$8$1$" + "00" * 16 + "$" + "00" * 32
        )
        ok = verify_password(password, stored)
        if not row or not ok or row["disabled_at"] is not None:
            raise InvalidCredentials("이메일 또는 비밀번호가 올바르지 않습니다.")
        return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}

    # ── 세션 ───────────────────────────────────────────────
    def issue_session(self, user_id: str, *, user_agent: str = "") -> tuple[str, datetime]:
        token = new_token()
        expires = session_expiry()
        self.db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, user_agent) "
            "VALUES (%s, %s, %s, %s)",
            (token_fingerprint(token), user_id, expires, user_agent[:200]),
        )
        return token, expires

    def revoke_session(self, token: str) -> None:
        self.db.execute(
            "UPDATE sessions SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
            (token_fingerprint(token),),
        )

    def principal_for_token(self, token: str) -> Principal | None:
        """토큰 → :class:`Principal`. 소속까지 한 번에 읽는다.

        라우트마다 소속을 다시 조회하면 왕복이 늘고, 무엇보다 "조회를 빠뜨린 라우트"가
        생긴다. 신원과 권한을 한 덩어리로 만든다.
        """
        if not token:
            return None
        row = self.db.fetch_one(
            "SELECT u.id, u.email, u.display_name FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.revoked_at IS NULL "
            "  AND s.expires_at > now() AND u.disabled_at IS NULL",
            (token_fingerprint(token),),
        )
        if not row:
            return None
        memberships = {
            m["workspace_id"]: m["role"]
            for m in self.db.fetch_all(
                "SELECT workspace_id, role FROM workspace_members WHERE user_id = %s",
                (row["id"],),
            )
        }
        return Principal(
            user_id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            memberships=memberships,
        )


# ── 워크스페이스 ────────────────────────────────────────────


class WorkspaceRepository(_Repo):
    def create(self, name: str, owner_user_id: str, *, initial_credits: int = 0) -> dict[str, Any]:
        workspace_id = new_id("ws")
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT INTO workspaces (id, name, owner_user_id, credit_balance) "
                "VALUES (%s, %s, %s, %s)",
                (workspace_id, (name or "내 워크스페이스").strip()[:120],
                 owner_user_id, max(0, int(initial_credits))),
            )
            cur.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, 'owner')",
                (workspace_id, owner_user_id),
            )
            if initial_credits:
                cur.execute(
                    "INSERT INTO credit_ledger (id, workspace_id, entry_type, amount, "
                    "balance_after, reserved_after, reason) VALUES (%s, %s, 'grant', %s, %s, 0, %s)",
                    (new_id("cl"), workspace_id, int(initial_credits),
                     int(initial_credits), "가입 기본 크레딧"),
                )
        return {"id": workspace_id, "name": name, "role": "owner"}

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT id, name, owner_user_id, credit_balance, credit_reserved, created_at "
            "FROM workspaces WHERE id = %s",
            (workspace_id,),
        )

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT w.id, w.name, m.role, w.credit_balance, w.credit_reserved "
            "FROM workspaces w JOIN workspace_members m ON m.workspace_id = w.id "
            "WHERE m.user_id = %s ORDER BY w.created_at",
            (user_id,),
        )

    def add_member(self, workspace_id: str, user_id: str, role: str) -> None:
        self.db.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, %s) "
            "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = EXCLUDED.role",
            (workspace_id, user_id, role),
        )

    def members(self, workspace_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT m.user_id, m.role, u.email, u.display_name FROM workspace_members m "
            "JOIN users u ON u.id = m.user_id WHERE m.workspace_id = %s ORDER BY m.created_at",
            (workspace_id,),
        )


# ── 프로젝트 ────────────────────────────────────────────────


class ProjectRepository(_Repo):
    def create(
        self, workspace_id: str, name: str, created_by: str, *, content_mode: str = "auto"
    ) -> dict[str, Any]:
        project_id = new_id("prj")
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT INTO projects (id, workspace_id, name, content_mode, created_by) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING created_at",
                (project_id, workspace_id, (name or "제목 없는 프로젝트").strip()[:200],
                 content_mode, created_by),
            )
            created_at = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO project_revisions (project_id, revision, change_kind, changed_by, snapshot) "
                "VALUES (%s, 1, 'created', %s, %s::jsonb)",
                (project_id, created_by, _jsonb({"name": name, "content_mode": content_mode})),
            )
        return {
            "id": project_id,
            "workspace_id": workspace_id,
            "name": name,
            "content_mode": content_mode,
            "revision": 1,
            "created_at": created_at,
        }

    def get(self, workspace_id: str, project_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT id, workspace_id, name, content_mode, revision, created_by, created_at, "
            "       updated_at, archived_at "
            "FROM projects WHERE id = %s AND workspace_id = %s",
            (project_id, workspace_id),
        )

    def list(self, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, name, content_mode, revision, created_at FROM projects "
            "WHERE workspace_id = %s AND archived_at IS NULL ORDER BY created_at DESC LIMIT %s",
            (workspace_id, max(1, min(int(limit), 200))),
        )

    def bump_revision(
        self,
        workspace_id: str,
        project_id: str,
        change_kind: str,
        *,
        changed_by: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> int:
        """개정 번호를 올리고 이력을 남긴다. 새 번호를 돌려준다."""
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE projects SET revision = revision + 1, updated_at = now() "
                "WHERE id = %s AND workspace_id = %s RETURNING revision",
                (project_id, workspace_id),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError("프로젝트를 찾을 수 없습니다.")
            revision = int(row[0])
            cur.execute(
                "INSERT INTO project_revisions (project_id, revision, change_kind, changed_by, snapshot) "
                "VALUES (%s, %s, %s, %s, %s::jsonb)",
                (project_id, revision, change_kind, changed_by, _jsonb(snapshot)),
            )
        return revision

    def revisions(self, workspace_id: str, project_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT r.revision, r.change_kind, r.changed_by, r.created_at FROM project_revisions r "
            "JOIN projects p ON p.id = r.project_id "
            "WHERE r.project_id = %s AND p.workspace_id = %s ORDER BY r.revision DESC",
            (project_id, workspace_id),
        )


# ── 소스 자산 · 권리 ────────────────────────────────────────


class AssetRepository(_Repo):
    def create(
        self,
        workspace_id: str,
        project_id: str,
        *,
        origin: str,
        uploaded_by: str,
        original_filename: str = "",
        source_url: str = "",
        content_type: str = "",
        storage_key: str = "",
        rights_status: str = "unverified",
    ) -> dict[str, Any]:
        asset_id = new_id("ast")
        self.db.execute(
            "INSERT INTO source_assets (id, workspace_id, project_id, origin, source_url, "
            "  original_filename, uploaded_by, storage_key, content_type, rights_status, upload_state) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (asset_id, workspace_id, project_id, origin, source_url[:2000],
             original_filename[:255], uploaded_by, storage_key, content_type[:120],
             rights_status, "uploaded" if origin == "url" else "pending"),
        )
        return {"id": asset_id, "workspace_id": workspace_id, "project_id": project_id,
                "origin": origin, "rights_status": rights_status}

    def get(self, workspace_id: str, asset_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT id, workspace_id, project_id, origin, source_url, original_filename, "
            "       uploaded_by, storage_key, content_type, size_bytes, checksum_sha256, "
            "       duration_seconds, rights_status, upload_state, created_at "
            "FROM source_assets WHERE id = %s AND workspace_id = %s",
            (asset_id, workspace_id),
        )

    def list(self, workspace_id: str, project_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, origin, original_filename, source_url, size_bytes, rights_status, "
            "       upload_state, created_at "
            "FROM source_assets WHERE workspace_id = %s AND project_id = %s "
            "ORDER BY created_at DESC",
            (workspace_id, project_id),
        )

    def mark_uploaded(
        self, workspace_id: str, asset_id: str, *, size_bytes: int, checksum: str
    ) -> None:
        self.db.execute(
            "UPDATE source_assets SET upload_state = 'uploaded', size_bytes = %s, "
            "  checksum_sha256 = %s WHERE id = %s AND workspace_id = %s",
            (int(size_bytes), checksum, asset_id, workspace_id),
        )

    def confirm_rights(
        self,
        workspace_id: str,
        asset_id: str,
        *,
        status: str,
        confirmed_by: str,
        evidence_uri: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """권리 확인을 기록하고 자산의 현재 상태를 갱신한다.

        확인 이력은 지우지 않는다. 나중에 "누가 언제 무엇을 근거로 확인했나"를
        답할 수 있어야 한다.
        """
        confirmation_id = new_id("rc")
        with self.db.transaction() as cur:
            cur.execute(
                "SELECT 1 FROM source_assets WHERE id = %s AND workspace_id = %s",
                (asset_id, workspace_id),
            )
            if cur.fetchone() is None:
                raise LookupError("자산을 찾을 수 없습니다.")
            cur.execute(
                "INSERT INTO rights_confirmations (id, workspace_id, asset_id, status, "
                "  confirmed_by, evidence_uri, note) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (confirmation_id, workspace_id, asset_id, status, confirmed_by,
                 evidence_uri[:2000], note[:1000]),
            )
            cur.execute(
                "UPDATE source_assets SET rights_status = %s WHERE id = %s AND workspace_id = %s",
                (status, asset_id, workspace_id),
            )
        return {"id": confirmation_id, "asset_id": asset_id, "status": status}

    def rights_history(self, workspace_id: str, asset_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, status, confirmed_by, evidence_uri, note, created_at "
            "FROM rights_confirmations WHERE workspace_id = %s AND asset_id = %s "
            "ORDER BY created_at DESC",
            (workspace_id, asset_id),
        )


# ── 파생 산출물 ─────────────────────────────────────────────


class TranscriptRepository(_Repo):
    def upsert(
        self,
        workspace_id: str,
        project_id: str,
        asset_id: str,
        *,
        language: str,
        model: str,
        storage_key: str,
        word_count: int = 0,
        duration_seconds: float | None = None,
    ) -> str:
        transcript_id = new_id("trs")
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT INTO transcripts (id, workspace_id, project_id, asset_id, language, "
                "  model, storage_key, word_count, duration_seconds) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (asset_id, model, language) DO UPDATE "
                "  SET storage_key = EXCLUDED.storage_key, word_count = EXCLUDED.word_count "
                "RETURNING id",
                (transcript_id, workspace_id, project_id, asset_id, language, model,
                 storage_key, int(word_count), duration_seconds),
            )
            return cur.fetchone()[0]

    def get_for_asset(self, workspace_id: str, asset_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, language, model, storage_key, word_count, duration_seconds, created_at "
            "FROM transcripts WHERE workspace_id = %s AND asset_id = %s ORDER BY created_at DESC",
            (workspace_id, asset_id),
        )


class ClipRepository(_Repo):
    def replace_for_job(
        self, workspace_id: str, project_id: str, job_id: str, candidates: Sequence[dict[str, Any]]
    ) -> list[str]:
        """작업의 후보를 통째로 교체한다. 재실행이 후보를 중복시키지 않게."""
        ids: list[str] = []
        with self.db.transaction() as cur:
            cur.execute(
                "DELETE FROM clip_candidates WHERE job_id = %s AND workspace_id = %s",
                (job_id, workspace_id),
            )
            for position, candidate in enumerate(candidates):
                candidate_id = new_id("cnd")
                cur.execute(
                    "INSERT INTO clip_candidates (id, workspace_id, project_id, job_id, position, "
                    "  start_seconds, end_seconds, title, viral_score, reason, selected) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (candidate_id, workspace_id, project_id, job_id, position,
                     float(candidate.get("start", 0.0)), float(candidate.get("end", 0.0)),
                     str(candidate.get("title", ""))[:300],
                     float(candidate.get("score", 0.0)),
                     str(candidate.get("reason", ""))[:1000],
                     bool(candidate.get("selected", True))),
                )
                ids.append(candidate_id)
        return ids

    def list_for_job(self, workspace_id: str, job_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, position, start_seconds, end_seconds, title, viral_score, reason, selected "
            "FROM clip_candidates WHERE workspace_id = %s AND job_id = %s ORDER BY position",
            (workspace_id, job_id),
        )


class OutputRepository(_Repo):
    def replace_for_job(
        self,
        workspace_id: str,
        project_id: str,
        job_id: str,
        outputs: Sequence[dict[str, Any]],
        *,
        candidate_ids: Sequence[str] = (),
    ) -> list[str]:
        ids: list[str] = []
        with self.db.transaction() as cur:
            cur.execute(
                "DELETE FROM render_outputs WHERE job_id = %s AND workspace_id = %s",
                (job_id, workspace_id),
            )
            for position, output in enumerate(outputs):
                output_id = new_id("out")
                candidate_id = candidate_ids[position] if position < len(candidate_ids) else None
                cur.execute(
                    "INSERT INTO render_outputs (id, workspace_id, project_id, job_id, candidate_id, "
                    "  position, title, storage_key, uri, width, height, duration_seconds, "
                    "  size_bytes, checksum_sha256) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (output_id, workspace_id, project_id, job_id, candidate_id, position,
                     str(output.get("title", ""))[:300], output.get("storage_key", ""),
                     output.get("uri", ""), int(output.get("width", 0)),
                     int(output.get("height", 0)), float(output.get("duration_seconds", 0.0)),
                     int(output.get("size_bytes", 0)), output.get("checksum_sha256", "")),
                )
                ids.append(output_id)
        return ids

    def list_for_job(self, workspace_id: str, job_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, position, title, storage_key, uri, width, height, duration_seconds, "
            "       size_bytes, checksum_sha256, created_at "
            "FROM render_outputs WHERE workspace_id = %s AND job_id = %s ORDER BY position",
            (workspace_id, job_id),
        )

    def get(self, workspace_id: str, output_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT id, workspace_id, project_id, job_id, title, storage_key, uri, size_bytes "
            "FROM render_outputs WHERE id = %s AND workspace_id = %s",
            (output_id, workspace_id),
        )


class ProgressRepository(_Repo):
    def append(
        self, workspace_id: str, job_id: str, stage: str, percent: float, message: str
    ) -> None:
        self.db.execute(
            "INSERT INTO job_progress_events (workspace_id, job_id, stage, percent, message) "
            "VALUES (%s, %s, %s, %s, %s)",
            (workspace_id, job_id, stage[:40], float(percent), message[:500]),
        )

    def list(self, workspace_id: str, job_id: str, *, after_id: int = 0, limit: int = 200):
        return self.db.fetch_all(
            "SELECT id, stage, percent, message, created_at FROM job_progress_events "
            "WHERE workspace_id = %s AND job_id = %s AND id > %s ORDER BY id LIMIT %s",
            (workspace_id, job_id, int(after_id), max(1, min(int(limit), 1000))),
        )
