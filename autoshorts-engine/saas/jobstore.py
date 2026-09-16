"""Phase 1 :class:`~autoshorts.service.JobStore` 의 PostgreSQL 구현.

Phase 1 ADR 의 핸드오프 항목 P1 이 이것이다. 인터페이스는 한 줄도 바꾸지 않았고,
``InMemoryJobStore`` 를 이 클래스로 갈아끼우면 엔진이 그대로 다중 프로세스에서 돈다.

취소는 프로세스를 넘나들어야 한다. API 프로세스가 ``cancel_requested`` 를 켜고
worker 프로세스가 진행률 콜백에서 읽는다. Phase 1 의 협조적 취소(단계 경계 확인)를
그대로 쓰되, 신호만 DB 를 통해 전달한다.
"""

from __future__ import annotations

import json
from typing import Any

from autoshorts.contracts import JobResult, JobSpec, JobStatus
from autoshorts.service import JobRecord, JobStore
from autoshorts.utils import get_logger

from .db import Database
from .queue import enqueue_in_transaction

__all__ = ["PostgresJobStore", "record_from_row"]

LOG = get_logger("saas.jobstore")

_COLUMNS = (
    "id, workspace_id, project_id, asset_id, project_revision, status, stage, progress, "
    "idempotency_key, reused_from_job_id, spec, result, error_code, error_message, "
    "cancel_requested, created_by, created_at, started_at, finished_at"
)


def record_from_row(row: dict[str, Any]) -> JobRecord:
    """DB 행 → :class:`JobRecord`.

    ``spec`` / ``result`` 는 JSONB 라 psycopg 가 이미 dict 로 준다.
    """
    spec = JobSpec.from_dict(row["spec"] or {})
    result_data = row["result"] or {}
    if not result_data:
        result_data = {"job_id": row["id"], "status": row["status"]}
    result = JobResult.from_dict(result_data)
    # DB 의 status 가 진실이다. worker 가 쓰다 죽어도 행의 상태는 갱신돼 있다.
    result.status = JobStatus(row["status"])
    record = JobRecord(spec, result)
    if row.get("cancel_requested"):
        record.token.cancel()
    return record


class PostgresJobStore(JobStore):
    def __init__(self, db: Database, *, enqueue: bool = False, queue_name: str = "default") -> None:
        self.db = db
        # API 는 제출과 동시에 큐에 넣는다. worker 는 이미 꺼낸 작업을 쓰므로 넣지 않는다.
        self.enqueue = enqueue
        self.queue_name = queue_name

    # ── JobStore 인터페이스 ─────────────────────────────────
    def create(self, record: JobRecord) -> None:
        spec, result = record.spec, record.result
        metadata = spec.metadata or {}
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT INTO render_jobs (id, workspace_id, project_id, asset_id, "
                "  project_revision, status, idempotency_key, reused_from_job_id, spec, result, "
                "  created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (
                    spec.job_id,
                    spec.workspace_id,
                    spec.project_id,
                    metadata.get("asset_id"),
                    int(metadata.get("project_revision", 1) or 1),
                    result.status.value,
                    spec.idempotency_key or "",
                    result.reused_from_job_id,
                    json.dumps(spec.to_dict(), ensure_ascii=False),
                    json.dumps(result.to_dict(), ensure_ascii=False),
                    metadata.get("created_by"),
                ),
            )
            if self.enqueue and result.status is JobStatus.QUEUED:
                enqueue_in_transaction(
                    cur,
                    job_id=spec.job_id,
                    workspace_id=spec.workspace_id,
                    queue=self.queue_name,
                )

    def get(self, job_id: str) -> JobRecord | None:
        row = self.db.fetch_one(
            f"SELECT {_COLUMNS} FROM render_jobs WHERE id = %s", (job_id,)
        )
        return record_from_row(row) if row else None

    def update(self, record: JobRecord) -> None:
        spec, result = record.spec, record.result
        stage = result.stage_timings[-1].stage if result.stage_timings else ""
        progress = 100.0 if result.status is JobStatus.SUCCEEDED else None
        self.db.execute(
            "UPDATE render_jobs SET status = %s, result = %s::jsonb, "
            "  error_code = %s, error_message = %s, "
            "  stage = COALESCE(NULLIF(%s, ''), stage), "
            "  progress = COALESCE(%s, progress), "
            "  started_at = COALESCE(started_at, CASE WHEN %s THEN now() END), "
            "  finished_at = CASE WHEN %s THEN COALESCE(finished_at, now()) ELSE finished_at END, "
            "  reused_from_job_id = COALESCE(%s, reused_from_job_id), "
            "  updated_at = now() "
            "WHERE id = %s",
            (
                result.status.value,
                json.dumps(result.to_dict(), ensure_ascii=False),
                result.error_code.value if result.error_code else None,
                (result.error_message or "")[:4000],
                stage,
                progress,
                result.status is not JobStatus.QUEUED,
                result.is_terminal,
                result.reused_from_job_id,
                spec.job_id,
            ),
        )

    def find_by_idempotency_key(self, key: str, workspace_id: str) -> JobRecord | None:
        if not key:
            return None
        row = self.db.fetch_one(
            f"SELECT {_COLUMNS} FROM render_jobs "
            "WHERE workspace_id = %s AND idempotency_key = %s AND status <> 'failed' "
            "ORDER BY created_at LIMIT 1",
            (workspace_id, key),
        )
        return record_from_row(row) if row else None

    def list_jobs(self, workspace_id: str = "", limit: int = 50) -> list[JobRecord]:
        limit = max(1, min(int(limit), 200))
        if workspace_id:
            rows = self.db.fetch_all(
                f"SELECT {_COLUMNS} FROM render_jobs WHERE workspace_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (workspace_id, limit),
            )
        else:
            rows = self.db.fetch_all(
                f"SELECT {_COLUMNS} FROM render_jobs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
        return [record_from_row(row) for row in rows]

    # ── SaaS 계층 확장 ──────────────────────────────────────
    def row(self, workspace_id: str, job_id: str) -> dict[str, Any] | None:
        """워크스페이스로 범위를 좁힌 조회. API 는 항상 이쪽을 쓴다."""
        return self.db.fetch_one(
            f"SELECT {_COLUMNS} FROM render_jobs WHERE id = %s AND workspace_id = %s",
            (job_id, workspace_id),
        )

    def rows_for_workspace(
        self, workspace_id: str, *, project_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        if project_id:
            return self.db.fetch_all(
                f"SELECT {_COLUMNS} FROM render_jobs WHERE workspace_id = %s AND project_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (workspace_id, project_id, limit),
            )
        return self.db.fetch_all(
            f"SELECT {_COLUMNS} FROM render_jobs WHERE workspace_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (workspace_id, limit),
        )

    def set_progress(self, job_id: str, stage: str, percent: float) -> None:
        self.db.execute(
            "UPDATE render_jobs SET stage = %s, progress = %s, updated_at = now() WHERE id = %s",
            (stage[:40], float(percent), job_id),
        )

    def request_cancel(self, workspace_id: str, job_id: str) -> bool:
        """취소 요청 플래그를 켠다. 이미 끝난 작업이면 ``False``.

        여기서 직접 상태를 ``cancelled`` 로 바꾸지 않는다. 실행 중인 worker 가
        단계 경계에서 멈춘 뒤 자기 손으로 기록해야 산출물이 반쯤 남지 않는다.
        """
        rows = self.db.execute(
            "UPDATE render_jobs SET cancel_requested = TRUE, updated_at = now() "
            "WHERE id = %s AND workspace_id = %s AND status IN ('queued', 'running', 'needs_approval')",
            (job_id, workspace_id),
        )
        return rows > 0

    def cancel_requested(self, job_id: str) -> bool:
        row = self.db.fetch_one("SELECT cancel_requested FROM render_jobs WHERE id = %s", (job_id,))
        return bool(row and row["cancel_requested"])

    def mark_queued_cancelled(self, workspace_id: str, job_id: str) -> bool:
        """아직 아무도 잡지 않은 작업을 즉시 취소 처리한다."""
        rows = self.db.execute(
            "UPDATE render_jobs SET status = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE id = %s AND workspace_id = %s AND status = 'queued'",
            (job_id, workspace_id),
        )
        if rows:
            self.db.execute(
                "UPDATE job_queue SET state = 'done', updated_at = now() "
                "WHERE job_id = %s AND state = 'ready'",
                (job_id,),
            )
        return rows > 0
