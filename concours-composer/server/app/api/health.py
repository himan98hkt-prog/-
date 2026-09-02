from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "composer_model": s.composer_model,
        "writer_model": s.writer_model,
        "engine": "claude" if s.has_api_key else "stub-rule-based",
        "quality_threshold": s.quality_threshold,
        "max_revision_rounds": s.max_revision_rounds,
        "max_cost_per_composition": s.max_cost_per_composition,
        "model_problems": getattr(request.app.state, "model_problems", []),
    }


@router.post("/api/shutdown")
def shutdown(request: Request) -> dict:
    """프로그램을 끈다 — 화면의 '프로그램 끄기' 버튼이 부른다.

    바탕화면 아이콘으로 켜면 명령창이 없어서 Ctrl+C 를 누를 곳이 없다. 그래서
    끄는 길을 화면 안에 둔다. 실행기(scripts/launch.py)가 서버 손잡이를
    `app.state.server` 에 올려 둘 때만 동작한다 — 개발용으로 uvicorn 을 직접
    띄운 경우에는 끄지 않고 그렇게 알린다.
    """
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 끌 수 있다")
    server = getattr(request.app.state, "server", None)
    if server is None:
        raise HTTPException(409, "명령창에서 띄운 서버다 — 그 창에서 Ctrl+C 로 끄십시오")
    server.should_exit = True
    return {"status": "shutting_down"}
