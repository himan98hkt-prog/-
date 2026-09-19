"""Phase 1 — 최소 HTTP API.

``POST /jobs`` · ``GET /jobs/{job_id}`` · ``POST /jobs/{job_id}/cancel``

FastAPI 는 **선택 의존성**이다. 설치돼 있지 않아도 패키지 임포트와 테스트가
동작해야 하므로 지연 임포트한다.

Phase 1 범위이므로 인증·DB·큐가 없다. 작업은 요청 스레드에서 동기 실행되고
저장소는 in-memory 다. Phase 2 에서 worker/PostgreSQL 로 교체한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import JobSpec, JobStatus
from .service import EngineService
from .utils import get_logger

__all__ = ["create_app", "build_service"]

LOG = get_logger("api")


def build_service(work_dir: str | Path = "work", output_dir: str | Path = "output") -> EngineService:
    return EngineService(default_work_dir=work_dir, default_output_dir=output_dir)


def create_app(service: EngineService | None = None):
    """FastAPI 앱을 만든다. FastAPI 가 없으면 안내와 함께 예외."""
    try:
        from fastapi import Body, FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise RuntimeError(
            "HTTP API 에는 FastAPI 가 필요합니다.\n"
            "  pip install 'fastapi' 'uvicorn'"
        ) from exc

    service = service or build_service()
    app = FastAPI(
        title="AutoShorts Engine API",
        version="0.1.0",
        description="Phase 1 — 엔진 서비스 경계. 인증·큐·DB 는 Phase 2 범위.",
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.post("/jobs", status_code=202)
    def create_job(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """작업을 제출한다.

        같은 ``idempotency_key`` 의 작업이 이미 있으면 새로 실행하지 않고
        기존 결과를 돌려준다(``reused_from_job_id`` 로 확인 가능).
        권리 미확인 소스는 ``needs_approval`` 로 멈춘다.
        """
        try:
            spec = JobSpec.from_dict(payload)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

        try:
            result = service.submit(spec)
        except Exception as exc:                 # pragma: no cover - 방어
            LOG.exception("작업 제출 실패")
            raise HTTPException(status_code=500, detail=str(exc)) from None
        return result.to_dict()

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        result = service.get(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        return result.to_dict()

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        result = service.cancel(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        return result.to_dict()

    @app.post("/jobs/{job_id}/approve-rights")
    def approve_rights(job_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """권리 확인 승인 후 재개. 승인자 식별자를 반드시 남긴다."""
        approver = str(payload.get("approver", "")).strip()
        if not approver:
            raise HTTPException(status_code=422, detail="approver 가 필요합니다.")
        result = service.approve_rights(job_id, approver)
        if result is None:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        return result.to_dict()

    @app.get("/jobs")
    def list_jobs(workspace_id: str = "", limit: int = 50) -> dict[str, Any]:
        rows = service.list_jobs(workspace_id, limit)
        return {"jobs": [r.to_dict() for r in rows], "count": len(rows)}

    return app
