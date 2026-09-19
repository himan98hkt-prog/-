"""내구성 있는 작업 큐.

Redis 대신 PostgreSQL ``SELECT ... FOR UPDATE SKIP LOCKED`` 를 쓴다. 명세가 허용한
"또는 동등" 쪽이다. 이유는 셋이다.

1. **원자성** — 작업 행 INSERT 와 큐 INSERT 가 같은 트랜잭션에 들어간다. Redis 면
   "큐에는 있는데 DB 에는 없는" 또는 그 반대 상태가 반드시 생기고, 그걸 막으려면
   outbox 패턴을 따로 만들어야 한다.
2. **재수거** — lease 만료 회수가 그냥 UPDATE 한 줄이다. Redis 로 같은 걸 하려면
   sorted set + 별도 reaper 프로세스가 필요하다.
3. **운영 부담** — 이미 PostgreSQL 이 필수다. 인프라를 하나 더 늘리지 않는다.

보장은 **at-least-once** 다. 같은 작업이 두 번 실행될 수 있으므로 멱등성은
``render_jobs.idempotency_key`` 와 엔진의 단계별 캐시가 담당한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from autoshorts.utils import get_logger

from .db import Database

__all__ = ["JobQueue", "PostgresJobQueue", "Lease", "enqueue_in_transaction"]

LOG = get_logger("saas.queue")

DEFAULT_LEASE_SECONDS = 900          # 렌더가 길 수 있다. 하트비트로 연장한다.
DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Lease:
    """한 워커가 점유한 큐 항목."""

    entry_id: int
    job_id: str
    workspace_id: str
    attempts: int
    max_attempts: int

    @property
    def is_last_attempt(self) -> bool:
        return self.attempts >= self.max_attempts


def enqueue_in_transaction(
    cur,
    *,
    job_id: str,
    workspace_id: str,
    queue: str = "default",
    priority: int = 0,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """이미 열린 트랜잭션 안에서 큐에 넣는다.

    작업 행을 만드는 트랜잭션과 같은 트랜잭션에 묶기 위한 것이다. 부분 유니크
    인덱스가 "살아있는 항목 1개"를 보장하므로 중복 제출은 조용히 무시된다.
    """
    cur.execute(
        "INSERT INTO job_queue (job_id, workspace_id, queue, priority, max_attempts) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (job_id, workspace_id, queue, int(priority), int(max_attempts)),
    )


class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, job_id: str, workspace_id: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def claim(self, worker_id: str, *, queue: str = "default") -> Lease | None: ...

    @abstractmethod
    def heartbeat(self, lease: Lease, worker_id: str) -> bool: ...

    @abstractmethod
    def complete(self, lease: Lease) -> None: ...

    @abstractmethod
    def fail(self, lease: Lease, error: str, *, retry: bool = True) -> str: ...

    @abstractmethod
    def reclaim_expired(self) -> int: ...


class PostgresJobQueue(JobQueue):
    def __init__(
        self,
        db: Database,
        *,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.db = db
        self.lease_seconds = max(10, int(lease_seconds))
        self.max_attempts = max(1, int(max_attempts))

    def enqueue(
        self,
        job_id: str,
        workspace_id: str,
        *,
        queue: str = "default",
        priority: int = 0,
        max_attempts: int | None = None,
    ) -> None:
        with self.db.transaction() as cur:
            enqueue_in_transaction(
                cur,
                job_id=job_id,
                workspace_id=workspace_id,
                queue=queue,
                priority=priority,
                max_attempts=self.max_attempts if max_attempts is None else max_attempts,
            )

    def claim(self, worker_id: str, *, queue: str = "default") -> Lease | None:
        """준비된 항목 하나를 점유한다. 없으면 ``None``.

        ``SKIP LOCKED`` 덕분에 워커 N 개가 동시에 호출해도 서로 다른 항목을 가져간다.
        잠금 대기 없이 즉시 다음 행으로 넘어가기 때문이다.
        """
        with self.db.transaction() as cur:
            cur.execute(
                "WITH picked AS ("
                "  SELECT id FROM job_queue "
                "  WHERE queue = %s AND state = 'ready' AND available_at <= now() "
                "  ORDER BY priority DESC, available_at, id "
                "  FOR UPDATE SKIP LOCKED LIMIT 1"
                ") "
                "UPDATE job_queue q SET state = 'leased', attempts = q.attempts + 1, "
                "  leased_by = %s, lease_expires_at = now() + make_interval(secs => %s), "
                "  updated_at = now() "
                "FROM picked WHERE q.id = picked.id "
                "RETURNING q.id, q.job_id, q.workspace_id, q.attempts, q.max_attempts",
                (queue, worker_id, float(self.lease_seconds)),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Lease(entry_id=row[0], job_id=row[1], workspace_id=row[2],
                     attempts=int(row[3]), max_attempts=int(row[4]))

    def heartbeat(self, lease: Lease, worker_id: str) -> bool:
        """임대를 연장한다. 이미 회수됐으면 ``False`` — 워커는 즉시 중단해야 한다."""
        rows = self.db.execute(
            "UPDATE job_queue SET lease_expires_at = now() + make_interval(secs => %s), "
            "  updated_at = now() "
            "WHERE id = %s AND state = 'leased' AND leased_by = %s",
            (float(self.lease_seconds), lease.entry_id, worker_id),
        )
        return rows > 0

    def complete(self, lease: Lease) -> None:
        self.db.execute(
            "UPDATE job_queue SET state = 'done', lease_expires_at = NULL, updated_at = now() "
            "WHERE id = %s",
            (lease.entry_id,),
        )

    def fail(self, lease: Lease, error: str, *, retry: bool = True) -> str:
        """실패 처리. 돌려주는 값은 새 상태(``ready`` 또는 ``dead``).

        재시도 간격은 지수 백오프. 공급자 장애 때 워커가 같은 작업을 초당 수십 번
        두드리면 장애를 키운다.
        """
        retryable = retry and lease.attempts < lease.max_attempts
        if retryable:
            backoff = min(300.0, 5.0 * (2 ** (lease.attempts - 1)))
            self.db.execute(
                "UPDATE job_queue SET state = 'ready', leased_by = NULL, lease_expires_at = NULL, "
                "  available_at = now() + make_interval(secs => %s), last_error = %s, "
                "  updated_at = now() WHERE id = %s",
                (backoff, (error or "")[:2000], lease.entry_id),
            )
            return "ready"
        self.db.execute(
            "UPDATE job_queue SET state = 'dead', leased_by = NULL, lease_expires_at = NULL, "
            "  last_error = %s, updated_at = now() WHERE id = %s",
            ((error or "")[:2000], lease.entry_id),
        )
        return "dead"

    def reclaim_expired(self) -> int:
        """임대가 만료된 항목을 다시 ready 로. 워커가 죽었을 때의 복구 경로다."""
        return self.db.execute(
            "UPDATE job_queue SET state = 'ready', leased_by = NULL, lease_expires_at = NULL, "
            "  last_error = '워커 임대 만료로 회수됨', updated_at = now() "
            "WHERE state = 'leased' AND lease_expires_at IS NOT NULL AND lease_expires_at < now()",
            (),
        )

    def stats(self, queue: str = "default") -> dict[str, int]:
        rows = self.db.fetch_all(
            "SELECT state, COUNT(*) AS n FROM job_queue WHERE queue = %s GROUP BY state",
            (queue,),
        )
        counts = {row["state"]: int(row["n"]) for row in rows}
        return {state: counts.get(state, 0) for state in ("ready", "leased", "done", "dead")}

    def depth(self, queue: str = "default") -> int:
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM job_queue WHERE queue = %s AND state = 'ready'",
            (queue,),
        )
        return int(row["n"]) if row else 0
