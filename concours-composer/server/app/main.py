"""FastAPI 앱. 시작 시 모델 문자열 유효성을 확인한다(절대 규칙 12)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compositions, corpus, feedback, health, judge, recitals, students
from app.api.deps import get_store
from app.config import get_settings, validate_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("concours")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    problems = validate_models(s)          # strict 모드면 여기서 기동이 멈춘다
    for p in problems:
        log.warning("모델 설정 확인: %s", p)
    log.info(
        "ConcoursComposer 시작 · COMPOSER_MODEL=%s · WRITER_MODEL=%s · API키=%s · 비용상한=$%.2f",
        s.composer_model, s.writer_model, "있음" if s.has_api_key else "없음(스텁 엔진)",
        s.max_cost_per_composition,
    )
    app.state.model_problems = problems
    if s.store_persist:
        path = s.resolved_store_path()
        get_store().attach(path)
        log.info("저장소 파일 %s", path)
    yield
    get_store().save()          # 종료 직전에 한 번 더


app = FastAPI(
    title="ConcoursComposer",
    version="0.3.0",
    description="학생 맞춤형 AI 콩쿨 독창곡 생성기 (SPEC.md v3 · A축)",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.middleware("http")
async def persist_after_write(request, call_next):  # type: ignore[no-untyped-def]
    """쓰기가 일어난 요청 뒤에 저장소 스냅샷을 남긴다.

    라우터들이 버킷 안쪽을 직접 고치므로(예: `store.jobs["guides"][cid] = ...`)
    dict 쓰기를 가로채는 방식으로는 변경을 놓친다. 요청 단위로 통째 저장한다.
    """
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400:
        get_store().save()
    return response


app.include_router(health.router)
app.include_router(students.router)
app.include_router(corpus.router)
app.include_router(compositions.router)
app.include_router(judge.router)
app.include_router(recitals.router)
app.include_router(feedback.router)
