"""§9 작곡 공동 워크플로 API.

모티브 → Plan → Realize 순서를 URL 로 강제한다. Plan 없이 realize 를 부를 수 없고,
모티브를 고르지 않고 plan 을 부를 수 없다 — 절대 규칙 9 를 API 층에서도 지킨다.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import Store, get_pipeline, get_store
from app.generation.context import InfeasibleRequest, build_context, check_feasibility
from app.generation.pipeline import CompositionPipeline, PlanRejected
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.student import CompositionRequest

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["compositions"])


class RequestCreated(BaseModel):
    request_id: str
    feasibility_warning: str | None = None
    constraints: dict


class MotifResponse(BaseModel):
    request_id: str
    candidates: list[MotifCandidate]
    engine: str


class PlanResponse(BaseModel):
    request_id: str
    plan: CompositionPlan
    passed: bool
    issues: list[dict]


class ComposeResponse(BaseModel):
    composition_id: str
    engine: str
    measures: int
    difficulty: float
    savable: bool
    shown_as_draft: bool = Field(description="비평 문턱 미달이면 '초안(미통과)' 으로만 표시한다")
    validation: dict
    quality: dict
    revision_rounds: int
    cost: dict
    musicxml_bytes: int


def _ctx(store: Store, request_id: str):
    if request_id not in store.requests:
        raise HTTPException(404, f"요청을 찾을 수 없다: {request_id}")
    return build_context(store.requests[request_id])


def _issues(report) -> list[dict]:
    return [
        {"rule": i.rule, "severity": i.severity, "message": i.message, "measures": i.measures}
        for i in report.issues
    ]


@router.post("/requests", response_model=RequestCreated)
def create_request(req: CompositionRequest, store: Store = Depends(get_store)) -> RequestCreated:
    """생성 요청 등록. 만들 수 없는 주문이면 생성 전에 알린다."""
    rid = req.id or store.next_id("req", store.requests)
    saved = req.model_copy(update={"id": rid})
    store.requests[rid] = saved
    ctx = build_context(saved)
    return RequestCreated(
        request_id=rid,
        feasibility_warning=check_feasibility(saved, ctx.hard),
        constraints=ctx.hard.as_dict(),
    )


@router.post("/requests/{request_id}/motifs", response_model=MotifResponse)
def create_motifs(
    request_id: str,
    n: int = Body(default=4, embed=True, ge=1, le=5),
    feedback: str = Body(default="", embed=True),
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> MotifResponse:
    """Stage 1 — 모티브 후보. 학생 제약을 못 지키는 후보는 여기서 걸러진다."""
    ctx = _ctx(store, request_id)
    candidates = pipeline.motifs(ctx, n, feedback)
    if not candidates:
        raise HTTPException(422, "학생 제약을 지키는 모티브 후보를 만들지 못했다")
    store.motifs[request_id] = candidates
    return MotifResponse(
        request_id=request_id, candidates=candidates,
        engine=getattr(pipeline.engine, "name", "unknown"),
    )


@router.post("/requests/{request_id}/motifs/custom", response_model=MotifResponse)
def custom_motif(
    request_id: str,
    motif: MotifCandidate,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> MotifResponse:
    """원장이 직접 그린 모티브(피아노롤 4마디)를 후보에 넣는다."""
    ctx = _ctx(store, request_id)
    from app.validate.validator import validate_score

    rep = validate_score(
        list(motif.measures), ctx.student, meter=motif.meter, tempo=motif.tempo,
        key_sig=motif.key, max_accidental_ratio=ctx.hard.max_accidental_ratio,
    )
    if not rep.passed:
        raise HTTPException(422, {"message": "모티브가 학생 제약을 벗어난다", "issues": _issues(rep)})
    existing = store.motifs.setdefault(request_id, [])
    existing.append(motif)
    return MotifResponse(request_id=request_id, candidates=existing, engine="director")


@router.post("/requests/{request_id}/motifs/{motif_id}/select", response_model=PlanResponse)
def select_motif_and_plan(
    request_id: str,
    motif_id: str,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> PlanResponse:
    """Stage 2 — 모티브를 잠그고 설계도를 만든다. 규칙 검사 결과를 함께 준다."""
    candidates = store.motifs.get(request_id)
    if not candidates:
        raise HTTPException(409, "먼저 모티브 후보를 만들어야 한다")
    motif = next((m for m in candidates if m.id == motif_id), None)
    if motif is None:
        raise HTTPException(404, f"모티브를 찾을 수 없다: {motif_id}")

    ctx = _ctx(store, request_id)
    locked = motif.model_copy(update={"selected": True})
    store.motifs[request_id] = [
        m.model_copy(update={"selected": m.id == motif_id}) for m in candidates
    ]
    plan, report = pipeline.plan(ctx, locked)
    store.plans[request_id] = {"plan": plan, "motif": locked, "approved": report.passed}
    return PlanResponse(
        request_id=request_id, plan=plan, passed=report.passed, issues=_issues(report)
    )


@router.patch("/requests/{request_id}/plan", response_model=PlanResponse)
def edit_plan(
    request_id: str,
    plan: CompositionPlan,
    store: Store = Depends(get_store),
    store_: Store = Depends(get_store),
) -> PlanResponse:
    """원장이 고친 Plan 을 다시 규칙 검사한다(예: 'B 부분을 8마디로 늘려')."""
    entry = store.plans.get(request_id)
    if not entry:
        raise HTTPException(409, "먼저 모티브를 선택해 Plan 을 만들어야 한다")
    ctx = _ctx(store, request_id)
    from app.generation.plan_rules import check_plan

    report = check_plan(plan, ctx.student, time_limit_sec=ctx.hard.time_limit_sec)
    entry["plan"] = plan
    entry["approved"] = report.passed
    return PlanResponse(
        request_id=request_id, plan=plan, passed=report.passed, issues=_issues(report)
    )


@router.post("/requests/{request_id}/realize", response_model=ComposeResponse)
def realize(
    request_id: str,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> ComposeResponse:
    """Stage 3~5 — 프레이즈 실현 → 조립 → 채점 → 비평 루프 → 저장."""
    entry = store.plans.get(request_id)
    if not entry:
        raise HTTPException(409, "먼저 모티브를 선택해 Plan 을 만들어야 한다")
    if not entry["approved"]:
        raise HTTPException(409, "Plan 이 규칙 검사를 통과하지 못했다 — 수정 후 다시 시도하라")

    ctx = _ctx(store, request_id)
    try:
        res = pipeline.compose(ctx, entry["motif"], entry["plan"])
    except PlanRejected as e:
        raise HTTPException(422, str(e)) from e
    except InfeasibleRequest as e:
        raise HTTPException(422, str(e)) from e

    cid = store.next_id("comp", store.compositions)
    store.compositions[cid] = res
    store.versions.setdefault(cid, []).append(res)

    return ComposeResponse(
        composition_id=cid,
        engine=res.engine,
        measures=len(res.measures),
        difficulty=res.difficulty,
        savable=res.savable,
        shown_as_draft=res.shown_as_draft,
        validation={
            "passed": res.validation.passed,
            "summary": res.validation.summary(),
            "issues": _issues(res.validation),
        },
        quality=res.quality.model_dump(),
        revision_rounds=res.revision_rounds,
        cost=res.cost,
        musicxml_bytes=len(res.musicxml),
    )


@router.get("/compositions/{composition_id}/musicxml")
def get_musicxml(composition_id: str, store: Store = Depends(get_store)) -> dict:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    if not res.savable:
        raise HTTPException(409, "검증을 통과하지 못한 악보는 내보낼 수 없다(절대 규칙 2)")
    return {"composition_id": composition_id, "musicxml": res.musicxml}


@router.get("/compositions/{composition_id}/quality")
def get_quality(composition_id: str, store: Store = Depends(get_store)) -> dict:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    return {
        "composition_id": composition_id,
        "quality": res.quality.model_dump(),
        "difficulty": res.difficulty,
        "shown_as_draft": res.shown_as_draft,
    }


@router.get("/compositions/{composition_id}/measures", response_model=list[Measure])
def get_measures(composition_id: str, store: Store = Depends(get_store)) -> list[Measure]:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    return store.compositions[composition_id].measures
