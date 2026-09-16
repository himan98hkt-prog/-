"""워커 프로세스.

API 와 **완전히 분리된 프로세스**다. 브라우저를 닫아도, API 를 재시작해도 진행 중인
작업은 계속 돈다. 그게 Phase 2 가 요구하는 성질이다.

한 번의 사이클::

    claim(lease) → 작업 행 로드 → EngineService.submit → 결과 반영 → complete/fail

크레딧은 API 가 제출 시 **예약**해 둔 것을 여기서 확정하거나 되돌린다.
성공이면 commit, 실패·취소·재시도면 release. 실패한 렌더가 크레딧을 먹지 않는다.
"""

from __future__ import annotations

import os
import signal
import threading
import time
from pathlib import Path
from typing import Any, Callable

from autoshorts.contracts import RETRYABLE_ERRORS, JobResult, JobSpec, JobStatus
from autoshorts.service import CancellationToken, EngineService
from autoshorts.storage import LocalStorage, Storage
from autoshorts.utils import ensure_dir, get_logger

from .db import Database
from .jobstore import PostgresJobStore
from .ledger import Ledger
from .queue import Lease, PostgresJobQueue
from .repositories import ClipRepository, OutputRepository, ProgressRepository, TranscriptRepository

__all__ = ["Worker", "WorkerConfig", "run_worker"]

LOG = get_logger("saas.worker")

HEARTBEAT_SECONDS = 30
IDLE_SLEEP_SECONDS = 1.0


class WorkerConfig:
    """워커 하나의 설정. 환경변수로만 주입한다(코드에 경로를 박지 않는다)."""

    def __init__(
        self,
        *,
        worker_id: str = "",
        queue_name: str = "default",
        work_root: str | Path = "var/work",
        output_root: str | Path = "var/output",
        storage_root: str | Path = "var/storage",
        poll_interval: float = IDLE_SLEEP_SECONDS,
    ) -> None:
        self.worker_id = worker_id or f"worker-{os.getpid()}"
        self.queue_name = queue_name
        self.work_root = Path(work_root)
        self.output_root = Path(output_root)
        self.storage_root = Path(storage_root)
        self.poll_interval = max(0.05, float(poll_interval))

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "WorkerConfig":
        source = os.environ if env is None else env
        return cls(
            worker_id=source.get("AUTOSHORTS_WORKER_ID", ""),
            queue_name=source.get("AUTOSHORTS_QUEUE", "default"),
            work_root=source.get("AUTOSHORTS_WORK_ROOT", "var/work"),
            output_root=source.get("AUTOSHORTS_OUTPUT_ROOT", "var/output"),
            storage_root=source.get("AUTOSHORTS_STORAGE_ROOT", "var/storage"),
            poll_interval=float(source.get("AUTOSHORTS_POLL_INTERVAL", IDLE_SLEEP_SECONDS)),
        )


class Worker:
    def __init__(
        self,
        db: Database,
        *,
        config: WorkerConfig | None = None,
        storage: Storage | None = None,
        queue: PostgresJobQueue | None = None,
        run_pipeline: Callable | None = None,
    ) -> None:
        self.db = db
        self.config = config or WorkerConfig()
        self.queue = queue or PostgresJobQueue(db)
        self.store = PostgresJobStore(db)
        self.ledger = Ledger(db)
        self.progress_repo = ProgressRepository(db)
        self.clips = ClipRepository(db)
        self.outputs = OutputRepository(db)
        self.transcripts = TranscriptRepository(db)
        self.storage = storage or LocalStorage(ensure_dir(self.config.storage_root))
        self._run_pipeline = run_pipeline

    # ── 루프 ───────────────────────────────────────────────
    def run_once(self) -> bool:
        """작업 하나를 처리한다. 처리했으면 ``True``."""
        self.queue.reclaim_expired()
        lease = self.queue.claim(self.config.worker_id, queue=self.config.queue_name)
        if lease is None:
            return False
        try:
            self._process(lease)
        except BaseException as exc:                    # 워커는 어떤 예외로도 죽지 않는다
            LOG.exception("작업 처리 중 예외: %s", lease.job_id)
            self._release_credits(lease.job_id, reason=f"워커 예외: {type(exc).__name__}")
            self.queue.fail(lease, f"{type(exc).__name__}: {exc}", retry=True)
        return True

    def run_forever(self, stop: threading.Event | None = None) -> None:  # pragma: no cover - 루프
        stop = stop or threading.Event()
        LOG.info("워커 시작: %s (queue=%s)", self.config.worker_id, self.config.queue_name)
        while not stop.is_set():
            try:
                did_work = self.run_once()
            except Exception as exc:
                LOG.error("큐 폴링 실패(계속 진행): %s", type(exc).__name__)
                did_work = False
            if not did_work:
                stop.wait(self.config.poll_interval)
        LOG.info("워커 종료: %s", self.config.worker_id)

    # ── 처리 ───────────────────────────────────────────────
    def _process(self, lease: Lease) -> None:
        row = self.db.fetch_one(
            "SELECT id, workspace_id, project_id, asset_id, spec, status FROM render_jobs WHERE id = %s",
            (lease.job_id,),
        )
        if row is None:
            # 작업이 지워졌다. 큐 항목만 정리하고 넘어간다.
            self.queue.complete(lease)
            return
        if row["status"] in {"succeeded", "cancelled", "failed"}:
            self.queue.complete(lease)
            return

        spec = JobSpec.from_dict(row["spec"] or {})
        workspace_id = row["workspace_id"]
        project_id = row["project_id"]

        # 아직 시작 전에 취소됐으면 바로 정리한다.
        if self.store.cancel_requested(spec.job_id):
            self._finish_cancelled(spec, workspace_id)
            self.queue.complete(lease)
            return

        # 경로는 워커가 주입한다. spec 에 남아 있던 값은 다른 호스트의 것일 수 있다.
        spec.work_dir = str(ensure_dir(self.config.work_root / workspace_id))
        spec.output_dir = str(ensure_dir(self.config.output_root / workspace_id / spec.job_id))

        service = EngineService(
            store=self.store,
            storage=self.storage,
            default_work_dir=spec.work_dir,
            default_output_dir=spec.output_dir,
            run_pipeline=self._run_pipeline,
        )

        # 취소 토큰은 워커가 들고 있다가 진행률 콜백에서 켠다. service 가 만든 record 와
        # 같은 토큰이어야 단계 경계 확인이 실제로 멈춘다.
        token = CancellationToken()
        heartbeat = _Heartbeat(self.queue, lease, self.config.worker_id)
        state = {"last_cancel_check": 0.0}

        def on_progress(event) -> None:
            self.progress_repo.append(
                workspace_id, spec.job_id, event.stage, event.percent, event.message
            )
            self.store.set_progress(spec.job_id, event.stage, event.percent)
            heartbeat.beat()
            # 취소 신호는 다른 프로세스에서 온다. 진행률 이벤트마다 확인하되
            # DB 왕복을 줄이기 위해 2초에 한 번으로 제한한다.
            now = time.monotonic()
            if now - state["last_cancel_check"] > 2.0:
                state["last_cancel_check"] = now
                if self.store.cancel_requested(spec.job_id):
                    token.cancel()

        # 이미 DB 에 행이 있으므로 submit 이 create 해도 ON CONFLICT DO NOTHING 이다.
        # dedupe=False 가 아니면 이 작업이 자기 자신의 멱등성 검사에 걸려 실행되지 않는다.
        result = service.submit(spec, on_progress=on_progress, dedupe=False, token=token)

        if result.status is JobStatus.SUCCEEDED:
            self._persist_success(spec, workspace_id, project_id, result)
            self.queue.complete(lease)
            return

        if result.status is JobStatus.CANCELLED:
            self._release_credits(spec.job_id, reason="작업 취소")
            self.queue.complete(lease)
            return

        if result.status is JobStatus.NEEDS_APPROVAL:
            # 권리 승인 대기는 실패가 아니다. 큐에서 내리고 승인 시 다시 넣는다.
            self._release_credits(spec.job_id, reason="권리 승인 대기")
            self.queue.complete(lease)
            return

        # 실패. 재시도 가능한 오류만 큐로 되돌린다.
        retryable = result.error_code in RETRYABLE_ERRORS if result.error_code else False
        new_state = self.queue.fail(lease, result.error_message or "알 수 없는 실패", retry=retryable)
        if new_state == "ready":
            # 아직 끝난 게 아니다. 행을 'failed' 로 남겨두면 다음 시도가 "이미 끝난
            # 작업"으로 걸러져 영원히 재시도되지 않고, 예약 크레딧도 묶인 채로 남는다.
            self.db.execute(
                "UPDATE render_jobs SET status = 'queued', finished_at = NULL, "
                "  updated_at = now() WHERE id = %s",
                (spec.job_id,),
            )
        else:
            self._release_credits(spec.job_id, reason=f"실패: {result.error_code}")
        self.ledger.record_usage(
            workspace_id,
            event_type="job_failed",
            quantity=1,
            unit="job",
            project_id=project_id,
            job_id=spec.job_id,
            metadata={"error_code": result.error_code.value if result.error_code else ""},
        )

    # ── 결과 반영 ───────────────────────────────────────────
    def _persist_success(
        self, spec: JobSpec, workspace_id: str, project_id: str, result: JobResult
    ) -> None:
        candidates = [
            {"start": o.start, "end": o.end, "title": o.title, "score": o.score,
             "reason": o.reason, "selected": True}
            for o in result.outputs
        ]
        candidate_ids = self.clips.replace_for_job(workspace_id, project_id, spec.job_id, candidates)

        prefix = f"{workspace_id or 'local'}/{project_id or spec.job_id}"
        outputs = [
            {
                "title": o.title,
                "uri": o.uri,
                "storage_key": f"{prefix}/{Path(o.uri).name}",
                "width": spec.render_options.width,
                "height": spec.render_options.height,
                "duration_seconds": o.duration,
                "size_bytes": o.size_bytes,
            }
            for o in result.outputs
        ]
        self.outputs.replace_for_job(
            workspace_id, project_id, spec.job_id, outputs, candidate_ids=candidate_ids
        )

        if result.transcript_uri and spec.metadata.get("asset_id"):
            self.transcripts.upsert(
                workspace_id,
                project_id,
                spec.metadata["asset_id"],
                language=spec.language or "",
                model=spec.quality_profile.value,
                storage_key=result.transcript_uri,
            )

        output_seconds = sum(o.duration for o in result.outputs)
        self.ledger.record_usage(
            workspace_id, event_type="render_output_seconds", quantity=output_seconds,
            unit="seconds", project_id=project_id, job_id=spec.job_id,
            metadata={"clips": len(result.outputs)},
        )
        self.ledger.record_usage(
            workspace_id, event_type="job_succeeded", quantity=1, unit="job",
            project_id=project_id, job_id=spec.job_id,
        )
        self.ledger.record_cost_events(
            workspace_id, spec.job_id, [e.to_dict() for e in result.cost_events]
        )

        reserved = int(spec.metadata.get("reserved_credits", 0) or 0)
        if reserved:
            from .ledger import CREDITS_PER_OUTPUT_SECOND

            actual = int(round(output_seconds * CREDITS_PER_OUTPUT_SECOND))
            self.ledger.commit(
                workspace_id, spec.job_id, reserved=reserved, actual=actual,
                reason=f"클립 {len(result.outputs)}개, {output_seconds:.1f}초",
            )

    def _finish_cancelled(self, spec: JobSpec, workspace_id: str) -> None:
        self.db.execute(
            "UPDATE render_jobs SET status = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE id = %s AND status IN ('queued', 'running')",
            (spec.job_id,),
        )
        self._release_credits(spec.job_id, reason="실행 전 취소")

    def _release_credits(self, job_id: str, *, reason: str) -> None:
        row = self.db.fetch_one(
            "SELECT workspace_id, spec FROM render_jobs WHERE id = %s", (job_id,)
        )
        if not row:
            return
        reserved = int(((row["spec"] or {}).get("metadata") or {}).get("reserved_credits", 0) or 0)
        if reserved <= 0:
            return
        already = self.db.fetch_one(
            "SELECT 1 AS hit FROM credit_ledger WHERE job_id = %s AND entry_type IN ('release', 'commit')",
            (job_id,),
        )
        if already:
            return  # 이미 정산됐다. 재시도가 두 번 돌려주지 않는다.
        try:
            self.ledger.release(row["workspace_id"], job_id, reserved, reason=reason)
        except Exception as exc:  # pragma: no cover - 정산 실패는 로그로만
            LOG.error("크레딧 반환 실패 %s: %s", job_id, exc)


class _Heartbeat:
    """임대 연장기. 매 이벤트마다 UPDATE 하지 않도록 간격을 둔다."""

    def __init__(self, queue: PostgresJobQueue, lease: Lease, worker_id: str) -> None:
        self.queue = queue
        self.lease = lease
        self.worker_id = worker_id
        self._last = 0.0

    def beat(self) -> None:
        now = time.monotonic()
        if now - self._last < HEARTBEAT_SECONDS:
            return
        self._last = now
        self.queue.heartbeat(self.lease, self.worker_id)


def run_worker(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI 진입점
    import argparse

    parser = argparse.ArgumentParser(description="AutoShorts SaaS 워커")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--queue", default=os.environ.get("AUTOSHORTS_QUEUE", "default"))
    parser.add_argument("--once", action="store_true", help="작업 하나만 처리하고 종료")
    args = parser.parse_args(argv)

    db = Database(args.dsn)
    config = WorkerConfig.from_env()
    config.queue_name = args.queue
    worker = Worker(db, config=config)

    if args.once:
        handled = worker.run_once()
        db.close()
        return 0 if handled else 1

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        worker.run_forever(stop)
    finally:
        db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_worker())
