"""내구성 큐 — SKIP LOCKED 로 워커들이 겹치지 않는지 실제로 확인한다."""

from __future__ import annotations

import json
import threading

import pytest

from saas.queue import Lease, PostgresJobQueue
from saas.repositories import ProjectRepository, UserRepository, WorkspaceRepository


@pytest.fixture
def tenant(db):
    user = UserRepository(db).create("q@example.com", "a-long-enough-password")
    workspace = WorkspaceRepository(db).create("W", user["id"])["id"]
    project = ProjectRepository(db).create(workspace, "P", user["id"])["id"]
    return {"user": user["id"], "workspace": workspace, "project": project}


def make_job(db, tenant, job_id: str) -> str:
    db.execute(
        "INSERT INTO render_jobs (id, workspace_id, project_id, spec) VALUES (%s, %s, %s, %s::jsonb)",
        (job_id, tenant["workspace"], tenant["project"], json.dumps({"source": "x.mp4"})),
    )
    return job_id


@pytest.fixture
def queue(db):
    return PostgresJobQueue(db, lease_seconds=60, max_attempts=3)


def test_enqueue_then_claim(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    assert lease.job_id == "job_1"
    assert lease.attempts == 1
    assert queue.claim("worker-b") is None      # 이미 점유됨


def test_empty_queue_returns_none(queue):
    assert queue.claim("worker-a") is None


def test_same_job_is_not_queued_twice(db, queue, tenant):
    """중복 제출이 워커 두 개를 태우지 않게 한다."""
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    queue.enqueue("job_1", tenant["workspace"])
    assert queue.depth() == 1


def test_completed_job_can_be_requeued(db, queue, tenant):
    """부분 유니크 인덱스는 살아있는 항목만 막는다. 끝난 작업은 다시 넣을 수 있어야 한다."""
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    queue.complete(queue.claim("worker-a"))
    queue.enqueue("job_1", tenant["workspace"])
    assert queue.depth() == 1


def test_concurrent_workers_never_take_the_same_job(db, tenant):
    """세 작업, 다섯 워커. 어떤 작업도 두 번 잡히면 안 된다."""
    for index in range(3):
        make_job(db, tenant, f"job_{index}")
        PostgresJobQueue(db).enqueue(f"job_{index}", tenant["workspace"])

    claimed: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(5)

    def worker(name: str) -> None:
        queue = PostgresJobQueue(db)
        barrier.wait()
        for _ in range(3):
            lease = queue.claim(name)
            if lease is None:
                continue
            with lock:
                claimed.append(lease.job_id)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(claimed) == ["job_0", "job_1", "job_2"]
    assert len(claimed) == len(set(claimed)), "같은 작업을 두 워커가 잡았습니다"


def test_three_jobs_are_all_processed_in_order_of_priority(db, queue, tenant):
    for index in range(3):
        make_job(db, tenant, f"job_{index}")
    queue.enqueue("job_0", tenant["workspace"], priority=0)
    queue.enqueue("job_1", tenant["workspace"], priority=9)
    queue.enqueue("job_2", tenant["workspace"], priority=5)
    order = [queue.claim("w").job_id for _ in range(3)]
    assert order == ["job_1", "job_2", "job_0"]


def test_retryable_failure_goes_back_to_ready_with_backoff(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    assert queue.fail(lease, "공급자 일시 장애", retry=True) == "ready"
    # 백오프 때문에 곧바로는 다시 잡히지 않는다.
    assert queue.claim("worker-b") is None
    row = db.fetch_one("SELECT state, attempts, last_error FROM job_queue WHERE job_id = 'job_1'")
    assert (row["state"], row["attempts"]) == ("ready", 1)
    assert "장애" in row["last_error"]


def test_exhausted_attempts_go_to_dead_letter(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"], max_attempts=2)
    for _ in range(2):
        db.execute("UPDATE job_queue SET available_at = now() WHERE job_id = 'job_1'")
        lease = queue.claim("worker-a")
        state = queue.fail(lease, "계속 실패")
    assert state == "dead"
    assert queue.stats()["dead"] == 1
    db.execute("UPDATE job_queue SET available_at = now() WHERE job_id = 'job_1'")
    assert queue.claim("worker-a") is None


def test_non_retryable_failure_dies_immediately(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    assert queue.fail(lease, "잘못된 입력", retry=False) == "dead"


def test_expired_lease_is_reclaimed(db, queue, tenant):
    """워커가 죽어도 작업이 영원히 묶여 있으면 안 된다."""
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    queue.claim("worker-that-dies")
    db.execute("UPDATE job_queue SET lease_expires_at = now() - interval '1 minute'")
    assert queue.reclaim_expired() == 1
    assert queue.claim("worker-b").job_id == "job_1"


def test_live_lease_is_not_reclaimed(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    queue.claim("worker-a")
    assert queue.reclaim_expired() == 0


def test_heartbeat_extends_lease(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    db.execute("UPDATE job_queue SET lease_expires_at = now() + interval '1 second'")
    assert queue.heartbeat(lease, "worker-a") is True
    assert queue.reclaim_expired() == 0


def test_heartbeat_from_wrong_worker_fails(db, queue, tenant):
    """임대를 빼앗긴 워커는 즉시 알아채고 멈춰야 한다."""
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    assert queue.heartbeat(lease, "worker-b") is False


def test_heartbeat_after_reclaim_fails(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    lease = queue.claim("worker-a")
    db.execute("UPDATE job_queue SET lease_expires_at = now() - interval '1 minute'")
    queue.reclaim_expired()
    assert queue.heartbeat(lease, "worker-a") is False


def test_named_queues_are_independent(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"], queue="gpu")
    assert queue.claim("worker-a", queue="default") is None
    assert queue.claim("worker-a", queue="gpu").job_id == "job_1"


def test_stats_report_every_state(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    assert queue.stats() == {"ready": 1, "leased": 0, "done": 0, "dead": 0}
    lease = queue.claim("worker-a")
    assert queue.stats()["leased"] == 1
    queue.complete(lease)
    assert queue.stats() == {"ready": 0, "leased": 0, "done": 1, "dead": 0}


def test_deleting_a_job_removes_its_queue_entry(db, queue, tenant):
    make_job(db, tenant, "job_1")
    queue.enqueue("job_1", tenant["workspace"])
    db.execute("DELETE FROM render_jobs WHERE id = 'job_1'")
    assert queue.depth() == 0


def test_lease_reports_last_attempt():
    assert Lease(1, "j", "w", attempts=3, max_attempts=3).is_last_attempt is True
    assert Lease(1, "j", "w", attempts=1, max_attempts=3).is_last_attempt is False
