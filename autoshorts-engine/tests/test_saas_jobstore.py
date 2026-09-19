"""PostgresJobStore — Phase 1 JobStore 계약을 DB 위에서 만족하는지."""

from __future__ import annotations

import pytest

from autoshorts.contracts import ErrorCode, JobResult, JobSpec, JobStatus
from autoshorts.service import JobRecord
from saas.jobstore import PostgresJobStore
from saas.repositories import ProjectRepository, UserRepository, WorkspaceRepository


@pytest.fixture
def tenant(db):
    user = UserRepository(db).create("j@example.com", "a-long-enough-password")
    workspace = WorkspaceRepository(db).create("W", user["id"])["id"]
    project = ProjectRepository(db).create(workspace, "P", user["id"])["id"]
    return {"user": user["id"], "workspace": workspace, "project": project}


@pytest.fixture
def store(db):
    return PostgresJobStore(db)


def make_record(tenant, *, source="a.mp4", status=JobStatus.QUEUED, **meta) -> JobRecord:
    spec = JobSpec(
        source=source,
        workspace_id=tenant["workspace"],
        project_id=tenant["project"],
        metadata={"created_by": tenant["user"], **meta},
    )
    return JobRecord(spec, JobResult(job_id=spec.job_id, status=status,
                                     idempotency_key=spec.idempotency_key))


def test_create_then_get_roundtrip(store, tenant):
    record = make_record(tenant)
    store.create(record)
    loaded = store.get(record.spec.job_id)
    assert loaded.spec.source == "a.mp4"
    assert loaded.spec.workspace_id == tenant["workspace"]
    assert loaded.result.status is JobStatus.QUEUED


def test_missing_job_returns_none(store):
    assert store.get("job_nope") is None


def test_update_persists_terminal_state(store, tenant, db):
    record = make_record(tenant)
    store.create(record)
    record.result.status = JobStatus.FAILED
    record.result.error_code = ErrorCode.RENDER_FAILED
    record.result.error_message = "ffmpeg 가 죽었습니다"
    store.update(record)

    row = db.fetch_one(
        "SELECT status, error_code, error_message, finished_at FROM render_jobs WHERE id = %s",
        (record.spec.job_id,),
    )
    assert row["status"] == "failed"
    assert row["error_code"] == "render_failed"
    assert row["finished_at"] is not None


def test_started_at_set_once(store, tenant, db):
    record = make_record(tenant)
    store.create(record)
    record.result.status = JobStatus.RUNNING
    store.update(record)
    first = db.fetch_one("SELECT started_at FROM render_jobs WHERE id = %s",
                         (record.spec.job_id,))["started_at"]
    store.update(record)
    assert db.fetch_one("SELECT started_at FROM render_jobs WHERE id = %s",
                        (record.spec.job_id,))["started_at"] == first


def test_idempotency_lookup_finds_prior_job(store, tenant):
    record = make_record(tenant)
    store.create(record)
    found = store.find_by_idempotency_key(record.spec.idempotency_key, tenant["workspace"])
    assert found.spec.job_id == record.spec.job_id


def test_idempotency_is_scoped_to_workspace(db, store, tenant):
    """다른 테넌트가 같은 파일을 올렸다고 남의 결과를 받으면 안 된다."""
    record = make_record(tenant)
    store.create(record)
    other_user = UserRepository(db).create("o@example.com", "a-long-enough-password")
    other_ws = WorkspaceRepository(db).create("O", other_user["id"])["id"]
    assert store.find_by_idempotency_key(record.spec.idempotency_key, other_ws) is None


def test_failed_jobs_are_not_reused(store, tenant, db):
    """실패한 작업은 다시 시도할 수 있어야 한다."""
    record = make_record(tenant)
    store.create(record)
    record.result.status = JobStatus.FAILED
    store.update(record)
    assert store.find_by_idempotency_key(record.spec.idempotency_key, tenant["workspace"]) is None


def test_duplicate_idempotency_key_is_refused_by_the_database(db, store, tenant):
    """동시에 같은 키로 두 요청이 들어와도 한 건만 남아야 한다."""
    first = make_record(tenant)
    store.create(first)
    second = make_record(tenant)          # 같은 source → 같은 키
    assert second.spec.idempotency_key == first.spec.idempotency_key
    with pytest.raises(Exception):
        store.create(second)


def test_list_jobs_is_scoped(db, store, tenant):
    store.create(make_record(tenant, source="a.mp4"))
    other_user = UserRepository(db).create("o@example.com", "a-long-enough-password")
    other_ws = WorkspaceRepository(db).create("O", other_user["id"])["id"]
    other_project = ProjectRepository(db).create(other_ws, "P", other_user["id"])["id"]
    store.create(make_record({"workspace": other_ws, "project": other_project,
                              "user": other_user["id"]}, source="b.mp4"))

    mine = store.list_jobs(tenant["workspace"])
    assert [r.spec.source for r in mine] == ["a.mp4"]
    assert len(store.list_jobs()) == 2


def test_row_lookup_is_scoped(db, store, tenant):
    record = make_record(tenant)
    store.create(record)
    other_user = UserRepository(db).create("o@example.com", "a-long-enough-password")
    other_ws = WorkspaceRepository(db).create("O", other_user["id"])["id"]
    assert store.row(tenant["workspace"], record.spec.job_id) is not None
    assert store.row(other_ws, record.spec.job_id) is None


# ── 프로세스 간 취소 ───────────────────────────────────────


def test_cancel_flag_crosses_processes(store, tenant):
    """API 프로세스가 켜고 worker 프로세스가 읽는다."""
    record = make_record(tenant)
    store.create(record)
    assert store.cancel_requested(record.spec.job_id) is False
    assert store.request_cancel(tenant["workspace"], record.spec.job_id) is True
    assert store.cancel_requested(record.spec.job_id) is True


def test_cancel_is_scoped_to_workspace(db, store, tenant):
    record = make_record(tenant)
    store.create(record)
    other_user = UserRepository(db).create("o@example.com", "a-long-enough-password")
    other_ws = WorkspaceRepository(db).create("O", other_user["id"])["id"]
    assert store.request_cancel(other_ws, record.spec.job_id) is False
    assert store.cancel_requested(record.spec.job_id) is False


def test_finished_job_cannot_be_cancelled(store, tenant):
    record = make_record(tenant)
    store.create(record)
    record.result.status = JobStatus.SUCCEEDED
    store.update(record)
    assert store.request_cancel(tenant["workspace"], record.spec.job_id) is False


def test_loaded_record_carries_cancellation_signal(store, tenant):
    record = make_record(tenant)
    store.create(record)
    store.request_cancel(tenant["workspace"], record.spec.job_id)
    assert store.get(record.spec.job_id).token.cancelled is True


def test_queued_job_cancels_immediately_and_leaves_the_queue(db, store, tenant):
    record = make_record(tenant)
    enqueueing = PostgresJobStore(db, enqueue=True)
    enqueueing.create(record)
    assert db.fetch_one("SELECT state FROM job_queue WHERE job_id = %s",
                        (record.spec.job_id,))["state"] == "ready"
    assert store.mark_queued_cancelled(tenant["workspace"], record.spec.job_id) is True
    assert db.fetch_one("SELECT status FROM render_jobs WHERE id = %s",
                        (record.spec.job_id,))["status"] == "cancelled"
    assert db.fetch_one("SELECT state FROM job_queue WHERE job_id = %s",
                        (record.spec.job_id,))["state"] == "done"


def test_progress_is_persisted(store, tenant, db):
    record = make_record(tenant)
    store.create(record)
    store.set_progress(record.spec.job_id, "render", 72.5)
    row = db.fetch_one("SELECT stage, progress FROM render_jobs WHERE id = %s",
                       (record.spec.job_id,))
    assert (row["stage"], row["progress"]) == ("render", 72.5)


def test_metadata_travels_into_columns(store, tenant, db):
    """spec.metadata 의 asset_id/revision/created_by 가 조회 가능한 열이 돼야 한다."""
    from saas.repositories import AssetRepository

    asset = AssetRepository(db).create(
        tenant["workspace"], tenant["project"], origin="upload", uploaded_by=tenant["user"]
    )
    record = make_record(tenant, asset_id=asset["id"], project_revision=4)
    store.create(record)
    row = db.fetch_one("SELECT asset_id, project_revision, created_by FROM render_jobs WHERE id = %s",
                       (record.spec.job_id,))
    assert (row["asset_id"], row["project_revision"], row["created_by"]) == (
        asset["id"], 4, tenant["user"]
    )


def test_unknown_asset_is_refused_by_the_database(store, tenant):
    """존재하지 않는 자산을 가리키는 작업이 만들어지면 안 된다."""
    with pytest.raises(Exception):
        store.create(make_record(tenant, asset_id="ast_does_not_exist"))
