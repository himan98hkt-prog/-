"""FastAPI 앱. 시작 시 모델 문자열 유효성을 확인한다(절대 규칙 12)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compositions, corpus, health, judge, recitals, students
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
    yield


app = FastAPI(
    title="ConcoursComposer",
    version="0.3.0",
    description="학생 맞춤형 AI 콩쿨 독창곡 생성기 (SPEC.md v3 · A축)",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(students.router)
app.include_router(corpus.router)
app.include_router(compositions.router)
app.include_router(judge.router)
app.include_router(recitals.router)
