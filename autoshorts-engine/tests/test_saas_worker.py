"""워커 — 큐에서 꺼내 엔진을 돌리고 정산까지 마치는지."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from saas_fakes import fake_pipeline

from autoshorts.contracts import JobResult, JobSpec, JobStatus
from autoshorts.service import JobRecord
from autoshorts.storage import LocalStorage
from saas.jobstore import PostgresJobStore
from saas.ledger import Ledger
from saas.queue import PostgresJobQueue
from saas.repositories import (
    ClipRepository,
    OutputRepository,
    ProgressRepository,
    ProjectRepository,
    UserRepository,
    WorkspaceRepository,
)
from saas.worker import Worker, WorkerConfig

RESERVED = 300


@pytest.fixture
def tenant(db):
    user = UserRepository(db).create("w@example.com", "a-long-enough-password")
    workspace = WorkspaceRepository(db).create("W", user["id"], initial_credits=5000)["id"]
    project = ProjectRepository(db).create(workspace, "P", user["id"])["id"]
    return {"user": user["id"], "workspace": workspace, "project": project}


def submit(db, tenant, *, source="a.mp4", reserved=RESERVED, rights="owned") -> str:
    """API 가 하는 일(예약 + 작업 행 + 큐 삽입)을 최소한으로 재현한다.

    ``rights`` 기본값이 "owned" 인 이유: 계약의 기본값은 ``unverified`` 이고 그건
    렌더 전에 승인 대기로 멈춘다(그 동작은 아래 전용 테스트에서 확인한다).
    """
    spec = JobSpec(
        source=source,
        workspace_id=tenant["workspace"],
        project_id=tenant["project"],
        rights_status=rights,
        metadata={"created_by": tenant["user"], "reserved_credits": reserved},
    )
    Ledger(db).reserve(tenant["workspace"], spec.job_id, reserved)
    PostgresJobStore(db, enqueue=True).create(
        JobRecord(spec, JobResult(job_id=spec.job_id, status=JobStatus.QUEUED,
                                  idempotency_key=spec.idempotency_key))
    )
    return spec.job_id


def make_worker(db, tmp_path, *, name="worker-1", **pipeline_kwargs) -> Worker:
    return Worker(
        db,
        config=WorkerConfig(
            worker_id=name,
            work_root=tmp_path / "work",
            output_root=tmp_path / "output",
            storage_root=tmp_path / "storage",
        ),
        storage=LocalStorage(tmp_path / "storage"),
        run_pipeline=fake_pipeline(**pipeline_kwargs),
    )


# ── 성공 경로 ──────────────────────────────────────────────


def test_worker_processes_a_job_end_to_end(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    assert make_worker(db, tmp_path).run_once() is True

    row = db.fetch_one("SELECT status, progress, finished_at FROM render_jobs WHERE id = %s",
                       (job_id,))
    assert row["status"] == "succeeded"
    assert row["progress"] == 100.0
    assert row["finished_at"] is not None


def test_idle_queue_reports_no_work(db, tmp_path):
    assert make_worker(db, tmp_path).run_once() is False


def test_outputs_and_candidates_are_persisted(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    make_worker(db, tmp_path, clips=3).run_once()

    outputs = OutputRepository(db).list_for_job(tenant["workspace"], job_id)
    assert len(outputs) == 3
    assert [o["position"] for o in outputs] == [0, 1, 2]
    assert all(o["size_bytes"] == 2048 for o in outputs)
    assert all(o["storage_key"].startswith(f"{tenant['workspace']}/") for o in outputs)

    candidates = ClipRepository(db).list_for_job(tenant["workspace"], job_id)
    assert len(candidates) == 3
    assert candidates[0]["title"] == "테스트 클립 1"
    # 산출물은 후보를 가리킨다. 편집 UI(Phase 6)가 이 연결을 쓴다.
    assert outputs[0]["id"] and candidates[0]["id"]


def test_output_file_is_readable_from_storage(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    make_worker(db, tmp_path).run_once()
    output = OutputRepository(db).list_for_job(tenant["workspace"], job_id)[0]
    assert LocalStorage(tmp_path / "storage").open_local(output["storage_key"]).exists()


def test_progress_events_are_persisted_in_order(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    make_worker(db, tmp_path).run_once()
    events = ProgressRepository(db).list(tenant["workspace"], job_id)
    assert [e["stage"] for e in events] == ["ingest", "transcribe", "analyze", "render"]
    percents = [e["percent"] for e in events]
    assert percents == sorted(percents)
    assert percents[-1] == 100.0


def test_usage_and_cost_ledgers_are_written(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    make_worker(db, tmp_path, clips=2).run_once()
    summary = Ledger(db).summary(tenant["workspace"])
    usage = {row["event_type"]: row["total"] for row in summary["usage"]}
    assert usage["job_succeeded"] == 1
    assert usage["render_output_seconds"] == pytest.approx(80.0)   # 40초 × 2
    assert {row["resource"] for row in summary["cost"]} >= {"render", "storage"}
    assert db.fetch_one("SELECT COUNT(*) AS n FROM usage_events WHERE job_id = %s",
                        (job_id,))["n"] >= 2


def test_success_commits_only_the_credits_actually_used(db, tenant, tmp_path):
    submit(db, tenant, reserved=300)
    assert Ledger(db).state(tenant["workspace"]).balance == 4700
    make_worker(db, tmp_path, clips=2).run_once()
    state = Ledger(db).state(tenant["workspace"])
    assert state.reserved == 0
    assert state.balance == 5000 - 80          # 80초만 차감, 220 은 반환


# ── 실패 · 취소 ────────────────────────────────────────────


def test_non_retryable_failure_refunds_all_credits(db, tenant, tmp_path):
    """Master Guard 11: 실패한 렌더가 사용자 크레딧을 소모하지 않는다."""
    submit(db, tenant)
    worker = make_worker(db, tmp_path, fail_with=ValueError("잘못된 입력입니다"))
    worker.run_once()

    assert db.fetch_one("SELECT status FROM render_jobs")["status"] == "failed"
    assert Ledger(db).state(tenant["workspace"]).balance == 5000
    assert Ledger(db).state(tenant["workspace"]).reserved == 0
    assert db.fetch_one("SELECT state FROM job_queue")["state"] == "dead"


def test_retryable_failure_keeps_the_job_in_the_queue(db, tenant, tmp_path):
    """공급자 장애는 재시도 대상이다. 그동안 예약은 유지된다."""
    from autoshorts.transcriber import TranscriptionError

    submit(db, tenant)
    make_worker(db, tmp_path, fail_with=TranscriptionError("모델 서버 응답 없음")).run_once()

    row = db.fetch_one("SELECT state, attempts FROM job_queue")
    assert (row["state"], row["attempts"]) == ("ready", 1)
    assert Ledger(db).state(tenant["workspace"]).reserved == 300
    # 재시도 대기 중인 작업을 'failed' 로 남겨두면 다음 시도가 "이미 끝난 작업"으로
    # 걸러져 영원히 재시도되지 않는다.
    assert db.fetch_one("SELECT status FROM render_jobs")["status"] == "queued"


def test_retries_exhausted_eventually_refunds(db, tenant, tmp_path):
    from autoshorts.transcriber import TranscriptionError

    submit(db, tenant)
    worker = make_worker(db, tmp_path, fail_with=TranscriptionError("계속 죽습니다"))
    for _ in range(3):
        db.execute("UPDATE job_queue SET available_at = now()")
        worker.run_once()

    assert db.fetch_one("SELECT state FROM job_queue")["state"] == "dead"
    assert Ledger(db).state(tenant["workspace"]).balance == 5000


def test_refund_happens_only_once(db, tenant, tmp_path):
    submit(db, tenant)
    worker = make_worker(db, tmp_path, fail_with=ValueError("bad"))
    worker.run_once()
    worker._release_credits(db.fetch_one("SELECT id FROM render_jobs")["id"], reason="중복 호출")
    assert Ledger(db).state(tenant["workspace"]).balance == 5000      # 5300 이 아니다
    assert db.fetch_one(
        "SELECT COUNT(*) AS n FROM credit_ledger WHERE entry_type = 'release'"
    )["n"] == 1


def test_cancelled_before_start_is_not_rendered(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    PostgresJobStore(db).request_cancel(tenant["workspace"], job_id)
    make_worker(db, tmp_path).run_once()

    assert db.fetch_one("SELECT status FROM render_jobs")["status"] == "cancelled"
    assert OutputRepository(db).list_for_job(tenant["workspace"], job_id) == []
    assert Ledger(db).state(tenant["workspace"]).balance == 5000


def test_unverified_rights_hold_the_job_before_rendering(db, tenant, tmp_path):
    """권리가 확인되지 않은 소스는 렌더까지 가지 않는다. 실패가 아니라 승인 대기다."""
    job_id = submit(db, tenant, rights="unverified")
    make_worker(db, tmp_path).run_once()

    row = db.fetch_one("SELECT status, result FROM render_jobs WHERE id = %s", (job_id,))
    assert row["status"] == "needs_approval"
    assert OutputRepository(db).list_for_job(tenant["workspace"], job_id) == []
    assert any(w["code"] == "rights_not_confirmed" for w in row["result"]["warnings"])
    # 승인 대기 중에는 크레딧을 잡아두지 않는다.
    assert Ledger(db).state(tenant["workspace"]).reserved == 0
    assert Ledger(db).state(tenant["workspace"]).balance == 5000


def test_already_finished_job_is_skipped(db, tenant, tmp_path):
    job_id = submit(db, tenant)
    db.execute("UPDATE render_jobs SET status = 'succeeded' WHERE id = %s", (job_id,))
    make_worker(db, tmp_path).run_once()
    assert db.fetch_one("SELECT state FROM job_queue")["state"] == "done"
    assert OutputRepository(db).list_for_job(tenant["workspace"], job_id) == []


def test_worker_survives_an_unexpected_exception(db, tenant, tmp_path):
    """워커는 어떤 예외로도 죽지 않는다. 죽으면 큐 전체가 멈춘다."""
    submit(db, tenant)
    worker = make_worker(db, tmp_path)
    worker.store = _ExplodingStore(db)
    assert worker.run_once() is True                       # 예외가 새어나가지 않는다
    assert Ledger(db).state(tenant["workspace"]).balance == 5000


class _ExplodingStore(PostgresJobStore):
    def cancel_requested(self, job_id: str) -> bool:
        raise RuntimeError("의도적 폭발")


# ── 동시성 ─────────────────────────────────────────────────


def test_three_jobs_run_concurrently_across_two_workers(db, tenant, tmp_path):
    """명세의 E2E: '3 jobs concurrent queue'."""
    job_ids = [submit(db, tenant, source=f"source_{i}.mp4") for i in range(3)]

    def drain(name: str) -> None:
        worker = make_worker(db, tmp_path / name, name=name, delay=0.15)
        while worker.run_once():
            pass

    threads = [threading.Thread(target=drain, args=(f"w{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    statuses = db.fetch_all("SELECT id, status FROM render_jobs ORDER BY created_at")
    assert [row["status"] for row in statuses] == ["succeeded"] * 3
    assert {row["id"] for row in statuses} == set(job_ids)
    # 어떤 작업도 두 번 처리되지 않았다 — 산출물이 중복되지 않는다.
    assert db.fetch_one("SELECT COUNT(*) AS n FROM render_outputs")["n"] == 6
    assert Ledger(db).state(tenant["workspace"]).reserved == 0


def test_job_survives_the_submitter_going_away(db, tenant, tmp_path):
    """'browser close 후 worker 지속' 의 구조적 근거.

    작업은 제출한 연결이 아니라 DB + 큐에 산다. 제출 측 객체를 전부 버리고
    나중에 새로 만든 워커가 처리해도 결과가 남는다.
    """
    job_id = submit(db, tenant)
    del tenant["user"]                                     # 제출자 컨텍스트 폐기
    assert db.fetch_one("SELECT state FROM job_queue")["state"] == "ready"

    make_worker(db, tmp_path, name="later-worker").run_once()
    assert db.fetch_one("SELECT status FROM render_jobs WHERE id = %s",
                        (job_id,))["status"] == "succeeded"


def test_spec_paths_are_replaced_by_the_worker(db, tenant, tmp_path):
    """다른 호스트에서 만들어진 경로를 그대로 믿으면 안 된다."""
    spec = JobSpec(
        source="a.mp4", workspace_id=tenant["workspace"], project_id=tenant["project"],
        rights_status="owned", work_dir="/somewhere/else", output_dir="/not/here",
        metadata={"reserved_credits": RESERVED},
    )
    Ledger(db).reserve(tenant["workspace"], spec.job_id, RESERVED)
    PostgresJobStore(db, enqueue=True).create(
        JobRecord(spec, JobResult(job_id=spec.job_id, status=JobStatus.QUEUED))
    )
    make_worker(db, tmp_path).run_once()

    # 산출물이 spec 에 적힌 남의 경로가 아니라 이 워커의 루트 아래에 놓였는지 본다.
    outputs = OutputRepository(db).list_for_job(tenant["workspace"], spec.job_id)
    assert outputs and all(str(tmp_path) in o["uri"] for o in outputs)
    assert not Path("/not/here").exists()
    assert all(o["storage_key"].startswith(f"{tenant['workspace']}/") for o in outputs)
