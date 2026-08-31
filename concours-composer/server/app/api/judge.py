"""§6.13 모의 심사 · 콩쿨 결과 기록."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import Store, get_store
from app.config import get_settings
from app.generation.context import build_context
from app.judge.panel import run_panel_claude, run_panel_rules
from app.schemas.quality import JudgePanel

router = APIRouter(prefix="/api", tags=["judge"])


class CompetitionResultIn(BaseModel):
    composition_id: str
    student_id: str
    competition_profile_id: str
    result: str
    judge_comments: str = ""


class JudgeResponse(BaseModel):
    composition_id: str
    panel: JudgePanel
    average: float
    consensus_fixes: list[str]
    engine: str


@router.post("/compositions/{composition_id}/judge", response_model=JudgeResponse)
def judge(composition_id: str, store: Store = Depends(get_store)) -> JudgeResponse:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    request_id = next(
        (rid for rid, e in store.plans.items() if e["plan"] is res.plan), None
    )
    if request_id is None:
        raise HTTPException(409, "이 곡의 생성 요청을 찾을 수 없다")
    ctx = build_context(store.requests[request_id])

    s = get_settings()
    if s.has_api_key:
        panel = run_panel_claude(ctx, res.measures, res.plan, settings=s)
        engine = "claude"
    else:
        panel = run_panel_rules(ctx, res.measures, res.plan, res.motif)
        engine = "rules"

    return JudgeResponse(
        composition_id=composition_id, panel=panel, average=panel.average,
        consensus_fixes=panel.consensus_fixes(), engine=engine,
    )


@router.post("/competition-results")
def record_result(payload: CompetitionResultIn, store: Store = Depends(get_store)) -> dict:
    """§6.13 결과 기록 — 이후 Plan 프롬프트의 '학원 실전 데이터' 로 되먹인다."""
    if payload.composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {payload.composition_id}")
    bucket = store.jobs.setdefault("competition_results", [])
    bucket.append(payload.model_dump())
    return {"recorded": len(bucket), "result": payload.result}


@router.get("/academy-data")
def academy_data(store: Store = Depends(get_store)) -> dict:
    """상위 입상곡의 Plan 특성 요약. Stage 0 컨텍스트에 주입된다."""
    from app.recital.learning import summarize_results

    results = store.jobs.get("competition_results", [])
    return {
        "records": len(results),
        "summary": summarize_results(results, store.compositions),
    }
