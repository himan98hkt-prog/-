"""HTTP API 계약 테스트. FastAPI 가 없으면 건너뛴다."""

from __future__ import annotations

import pytest

from autoshorts.contracts import JobStatus
from autoshorts.models import Clip
from autoshorts.pipeline import PipelineResult
from autoshorts.service import EngineService, InMemoryJobStore
from autoshorts.storage import LocalStorage

fastapi = pytest.importorskip("fastapi", reason="FastAPI 미설치 환경에서는 건너뜀")
from fastapi.testclient import TestClient  # noqa: E402

from autoshorts.api import create_app  # noqa: E402


def make_render(tmp_path, index=1):
    path = tmp_path / f"output_{index:02d}_클립.mp4"
    path.write_bytes(b"video")
    return type("R", (), {
        "clip": Clip(start=0.0, end=40.0, title="클립", reason="r", score=80, index=index),
        "output_path": path, "size_bytes": 5, "subtitle_path": None,
    })()


@pytest.fixture
def client(tmp_path):
    service = EngineService(
        store=InMemoryJobStore(),
        storage=LocalStorage(tmp_path / "storage"),
        default_work_dir=tmp_path / "work",
        default_output_dir=tmp_path / "out",
        run_pipeline=lambda settings, on_progress=None, **k: PipelineResult(
            source=settings.source, renders=[make_render(tmp_path)]
        ),
    )
    return TestClient(create_app(service)), service


class TestHealth:
    def test_health(self, client):
        api, _ = client
        assert api.get("/health").json() == {"status": "ok"}


class TestCreateJob:
    def test_accepts_valid_spec(self, client):
        api, _ = client
        response = api.post("/jobs", json={
            "source": "a.mp4", "workspace_id": "w1", "rights_status": "owned",
        })
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == JobStatus.SUCCEEDED.value
        assert len(body["outputs"]) == 1
        assert body["job_id"].startswith("job_")

    def test_rejects_missing_source(self, client):
        api, _ = client
        assert api.post("/jobs", json={"workspace_id": "w1"}).status_code == 422

    def test_rejects_unknown_enum(self, client):
        api, _ = client
        response = api.post("/jobs", json={"source": "a.mp4", "content_mode": "asmr"})
        assert response.status_code == 422
        assert "content_mode" in response.json()["detail"]

    def test_unverified_rights_returns_needs_approval(self, client):
        api, _ = client
        body = api.post("/jobs", json={"source": "a.mp4", "workspace_id": "w1"}).json()
        assert body["status"] == JobStatus.NEEDS_APPROVAL.value
        assert body["outputs"] == []

    def test_idempotent_resubmit(self, client):
        api, _ = client
        payload = {"source": "a.mp4", "workspace_id": "w1", "rights_status": "owned"}
        first = api.post("/jobs", json=payload).json()
        second = api.post("/jobs", json=payload).json()
        assert second["reused_from_job_id"] == first["job_id"]

    def test_response_is_json_serialisable_contract(self, client):
        api, _ = client
        body = api.post("/jobs", json={"source": "a.mp4", "rights_status": "owned"}).json()
        for key in ("job_id", "status", "outputs", "stage_timings", "warnings",
                    "quality_checks", "cost_events", "is_retryable", "idempotency_key"):
            assert key in body


class TestGetJob:
    def test_returns_job(self, client):
        api, _ = client
        job_id = api.post("/jobs", json={"source": "a.mp4", "rights_status": "owned"}).json()["job_id"]
        assert api.get(f"/jobs/{job_id}").json()["job_id"] == job_id

    def test_unknown_is_404(self, client):
        api, _ = client
        assert api.get("/jobs/nope").status_code == 404


class TestCancelJob:
    def test_cancel_finished_job_keeps_status(self, client):
        api, _ = client
        job_id = api.post("/jobs", json={"source": "a.mp4", "rights_status": "owned"}).json()["job_id"]
        assert api.post(f"/jobs/{job_id}/cancel").json()["status"] == JobStatus.SUCCEEDED.value

    def test_cancel_pending_approval(self, client):
        api, _ = client
        job_id = api.post("/jobs", json={"source": "a.mp4"}).json()["job_id"]
        assert api.post(f"/jobs/{job_id}/cancel").json()["status"] == JobStatus.CANCELLED.value

    def test_unknown_is_404(self, client):
        api, _ = client
        assert api.post("/jobs/nope/cancel").status_code == 404


class TestApproveRights:
    def test_approval_runs_job(self, client):
        api, _ = client
        job_id = api.post("/jobs", json={"source": "a.mp4", "workspace_id": "w1"}).json()["job_id"]
        body = api.post(f"/jobs/{job_id}/approve-rights", json={"approver": "user:1"}).json()
        assert body["status"] == JobStatus.SUCCEEDED.value

    def test_approver_is_required(self, client):
        api, _ = client
        job_id = api.post("/jobs", json={"source": "a.mp4"}).json()["job_id"]
        assert api.post(f"/jobs/{job_id}/approve-rights", json={}).status_code == 422

    def test_unknown_is_404(self, client):
        api, _ = client
        assert api.post("/jobs/nope/approve-rights", json={"approver": "u"}).status_code == 404


class TestListJobs:
    def test_lists_and_filters(self, client):
        api, _ = client
        api.post("/jobs", json={"source": "a.mp4", "workspace_id": "w1", "rights_status": "owned"})
        api.post("/jobs", json={"source": "b.mp4", "workspace_id": "w2", "rights_status": "owned"})
        assert api.get("/jobs").json()["count"] == 2
        assert api.get("/jobs", params={"workspace_id": "w1"}).json()["count"] == 1
