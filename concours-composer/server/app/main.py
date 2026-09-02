"""FastAPI 앱. 시작 시 모델 문자열 유효성을 확인한다(절대 규칙 12)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    compositions,
    corpus,
    feedback,
    health,
    judge,
    recitals,
    rights,
    students,
    studio,
)
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

    # 원장이 폴더에 넣어 둔 참고 악보를 시작할 때 한 번 읽는다.
    # 업로드 화면을 거치지 않아도 참고가 걸리게 하는 것이 목적이다.
    try:
        import sys
        from pathlib import Path

        scripts = Path(__file__).resolve().parents[2] / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from import_scores import sync as sync_reference_scores

        from app.api.corpus import get_corpus

        r = sync_reference_scores(get_corpus(), quiet=True)
        app.state.reference_scores = r
        if r["added"] or r["failed"]:
            log.info("참고 악보 적재 %s", r)
    except Exception:                                  # 참고 악보가 없다고 기동을 막지 않는다
        log.warning("참고 악보 폴더를 읽지 못했다", exc_info=True)
        app.state.reference_scores = {"added": 0, "skipped": 0, "failed": 0}

    if s.store_persist:
        path = s.resolved_store_path()
        get_store().attach(path)
        log.info("저장소 파일 %s", path)

    # 저장해 둔 예명을 불러온다. 악보에 찍히는 이름은 이것 하나다(실명은 등록 서류에만).
    try:
        from app.api.rights import get_composer
        from app.identity import set_alias

        set_alias(get_composer(get_store()).alias)
    except Exception:                                  # 이름 때문에 기동을 막지 않는다
        log.warning("작곡가 예명을 불러오지 못했다", exc_info=True)
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
app.include_router(studio.router)
app.include_router(rights.router)
app.include_router(judge.router)
app.include_router(recitals.router)
app.include_router(feedback.router)

# 원장 화면을 API 와 **같은 주소**로 내보낸다. 학원 PC 에서 서버 하나만 띄우면
# 브라우저에서 바로 열린다 — 정적 파일 서버를 따로 돌리지 않아도 된다.
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
if WEB_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")

    @app.get("/", include_in_schema=False)
    def _home() -> RedirectResponse:
        return RedirectResponse("/app/")
else:  # pragma: no cover - 배포 형태에 따라 web/ 이 없을 수 있다
    log.warning("web/ 디렉터리를 찾지 못했다 — 화면 없이 API 만 돈다: %s", WEB_DIR)
