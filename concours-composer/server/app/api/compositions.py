"""§9 작곡 공동 워크플로 API.

모티브 → Plan → Realize 순서를 URL 로 강제한다. Plan 없이 realize 를 부를 수 없고,
모티브를 고르지 않고 plan 을 부를 수 없다 — 절대 규칙 9 를 API 층에서도 지킨다.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import Store, get_pipeline, get_store
from app.generation.context import InfeasibleRequest, build_context, check_feasibility
from app.generation.pipeline import CompositionPipeline, PlanRejected
from app.schemas.guide import Guide, TitleSuggestion
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.student import CompositionRequest

log = logging.getLogger(__name__)
if TYPE_CHECKING:
    from app.export.package import PackageInput

router = APIRouter(prefix="/api", tags=["compositions"])


class RequestCreated(BaseModel):
    request_id: str
    feasibility_warning: str | None = None
    constraints: dict


class MotifPreview(BaseModel):
    """모티브 하나와 그 미리듣기 MIDI. 원장은 들어보고 고른다(§7.3 Stage 1)."""

    motif: MotifCandidate
    midi_base64: str = Field(description="브라우저가 바로 재생할 수 있는 MIDI")


class MotifResponse(BaseModel):
    request_id: str
    candidates: list[MotifCandidate]
    previews: list[MotifPreview] = Field(default_factory=list)
    engine: str


class PlanResponse(BaseModel):
    request_id: str
    plan: CompositionPlan
    passed: bool
    issues: list[dict]


class CandidateSummary(BaseModel):
    composition_id: str
    combined_score: float
    musicality: float
    difficulty: float
    savable: bool
    revision_rounds: int


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
    candidates: list[CandidateSummary] = Field(
        default_factory=list,
        description="3안 생성 시 전체 안. 첫 항목이 최고 점수안이며 위 필드들이 그 안의 값이다.",
    )


def _ctx(store: Store, request_id: str):
    """Stage 0 컨텍스트. 코퍼스 검색 결과와 학원 실전 데이터를 함께 싣는다."""
    if request_id not in store.requests:
        raise HTTPException(404, f"요청을 찾을 수 없다: {request_id}")
    req = store.requests[request_id]

    from app.api.corpus import get_corpus
    from app.generation.context import search_corpus_entries
    from app.recital.learning import summarize_results

    corpus = get_corpus()
    entries = search_corpus_entries(req, corpus) if corpus.scores else []
    academy = summarize_results(store.jobs.get("competition_results", []), store.compositions)
    return build_context(req, corpus=entries, academy_data=academy)


def _previews(motifs: list[MotifCandidate]) -> list[MotifPreview]:
    """후보마다 미리듣기 MIDI 를 붙인다. 듣지 않고 고르면 공동 작곡의 첫 단추가 어긋난다."""
    from app.export.midi import measures_to_midi

    out: list[MotifPreview] = []
    for m in motifs:
        midi = measures_to_midi(list(m.measures), m.tempo, m.meter)
        out.append(MotifPreview(motif=m, midi_base64=base64.b64encode(midi).decode("ascii")))
    return out


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
        request_id=request_id,
        candidates=candidates,
        previews=_previews(candidates),
        engine=getattr(pipeline.engine, "name", "unknown"),
    )


@router.post("/requests/{request_id}/motifs/custom", response_model=MotifResponse)
def custom_motif(
    request_id: str,
    motif: MotifCandidate,
    store: Store = Depends(get_store),
) -> MotifResponse:
    """원장이 직접 그린 모티브(피아노롤 4마디)를 후보에 넣는다."""
    ctx = _ctx(store, request_id)
    from app.validate.validator import validate_score

    rep = validate_score(
        list(motif.measures),
        ctx.student,
        meter=motif.meter,
        tempo=motif.tempo,
        key_sig=motif.key,
        max_accidental_ratio=ctx.hard.max_accidental_ratio,
    )
    if not rep.passed:
        raise HTTPException(422, {"message": "모티브가 학생 제약을 벗어난다", "issues": _issues(rep)})
    existing = store.motifs.setdefault(request_id, [])
    existing.append(motif)
    return MotifResponse(
        request_id=request_id,
        candidates=existing,
        previews=_previews(existing),
        engine="director",
    )


def _previous_plans(store: Store, exclude: str) -> list[tuple[str, CompositionPlan]]:
    """이미 만든 다른 곡들의 설계도. 형식이 겹치는지 볼 때 쓴다.

    **같은 콩쿨에 나가는 곡끼리만** 비교한다. 형제 같은 곡이 문제가 되는 것은
    한 무대에서 잇따라 들릴 때이지, 다른 대회·다른 해의 곡과 형식이 닮은 것은
    막을 이유가 없다 — 그렇게까지 막으면 쓸 수 있는 형식이 금세 바닥난다.
    콩쿨 정보가 없는 요청은 다른 '콩쿨 없음' 요청들과만 비교한다.
    """
    mine = store.requests.get(exclude)
    my_comp = getattr(getattr(mine, "competition", None), "id", None)

    def same_competition(rid: str) -> bool:
        req = store.requests.get(rid)
        return getattr(getattr(req, "competition", None), "id", None) == my_comp

    return [
        (rid, entry["plan"])
        for rid, entry in store.plans.items()
        if rid != exclude and entry.get("plan") is not None and same_competition(rid)
    ]


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
    store.motifs[request_id] = [m.model_copy(update={"selected": m.id == motif_id}) for m in candidates]
    plan, report = pipeline.plan(ctx, locked, previous_plans=_previous_plans(store, request_id))
    store.plans[request_id] = {"plan": plan, "motif": locked, "approved": report.passed}
    return PlanResponse(request_id=request_id, plan=plan, passed=report.passed, issues=_issues(report))


@router.patch("/requests/{request_id}/plan", response_model=PlanResponse)
def edit_plan(
    request_id: str,
    plan: CompositionPlan,
    store: Store = Depends(get_store),
) -> PlanResponse:
    """원장이 고친 Plan 을 다시 규칙 검사한다(예: 'B 부분을 8마디로 늘려')."""
    entry = store.plans.get(request_id)
    if not entry:
        raise HTTPException(409, "먼저 모티브를 선택해 Plan 을 만들어야 한다")
    ctx = _ctx(store, request_id)
    from app.generation.plan_rules import check_plan

    report = check_plan(
        plan,
        ctx.student,
        time_limit_sec=ctx.hard.time_limit_sec,
        previous_plans=_previous_plans(store, request_id),
    )
    entry["plan"] = plan
    entry["approved"] = report.passed
    return PlanResponse(request_id=request_id, plan=plan, passed=report.passed, issues=_issues(report))


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
    n = store.requests[request_id].n_candidates

    # 표절 검사(§7.6)는 코퍼스가 있어야 의미가 있다. 지금까지 항상 비어 있었다.
    from app.api.corpus import get_corpus

    ngrams = get_corpus().ngram_index() or None

    try:
        results = pipeline.compose_candidates(ctx, entry["motif"], entry["plan"], n=n, corpus_ngrams=ngrams)
    except PlanRejected as e:
        raise HTTPException(422, str(e)) from e
    except InfeasibleRequest as e:
        raise HTTPException(422, str(e)) from e

    # 종합 점수 내림차순이므로 첫 항목이 기본 표시안이다(§7.9 원칙 5).
    summaries: list[CandidateSummary] = []
    for r in results:
        rid_ = store.next_id("comp", store.compositions)
        store.compositions[rid_] = r
        store.versions.setdefault(rid_, []).append(r)
        summaries.append(
            CandidateSummary(
                composition_id=rid_,
                combined_score=r.quality.combined_score,
                musicality=float(r.quality.musicality["score_10"]),
                difficulty=r.difficulty,
                savable=r.savable,
                revision_rounds=r.revision_rounds,
            )
        )
    res = results[0]
    cid = summaries[0].composition_id

    # 만든 곡을 코퍼스에 등록해 **다음 곡의 표절 검사**가 이 곡을 보게 한다.
    # 이게 없으면 같은 학원이 같은 콩쿨에 거의 같은 곡을 두 개 내보내도 통과한다.
    if res.savable:
        get_corpus().register_generated(
            res.measures,
            score_id=f"gen-{cid}",
            title=store.title_of(cid),
            key=res.plan.key,
            meter=res.plan.meter,
            tempo=res.plan.tempo,
            division_tags=[ctx.competition.division] if ctx.competition else [],
        )

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
        candidates=summaries,
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
    # 라이브러리에서 곡을 다시 열 때 화면이 필요한 것을 한 번에 준다 —
    # 예전에는 이 응답만으로 결과 화면을 그릴 수 없어 작곡 직후에만 볼 수 있었다.
    return {
        "composition_id": composition_id,
        "quality": res.quality.model_dump(),
        "difficulty": res.difficulty,
        "shown_as_draft": res.shown_as_draft,
        "savable": res.savable,
        "engine": res.engine,
        "measures": len(res.measures),
        "revision_rounds": res.revision_rounds,
        "title": store.title_of(composition_id),
        "key": res.plan.key,
        "meter": res.plan.meter,
        "tempo": res.plan.tempo,
        "cost": res.cost,
        "validation": {
            "passed": res.validation.passed,
            "summary": res.validation.summary(),
            "issues": _issues(res.validation),
        },
        "candidates": [],
    }


@router.get("/compositions/{composition_id}/measures", response_model=list[Measure])
def get_measures(composition_id: str, store: Store = Depends(get_store)) -> list[Measure]:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    return store.compositions[composition_id].measures


@router.get("/compositions/{composition_id}/midi")
def get_midi(composition_id: str, store: Store = Depends(get_store)) -> Response:
    """재생·외부 편집기용 MIDI. 손별로 트랙이 나뉘어 손 분리 연습에 쓸 수 있다."""
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    from app.export.midi import measures_to_midi

    data = measures_to_midi(res.measures, res.plan.tempo, res.plan.meter)
    return Response(
        content=data,
        media_type="audio/midi",
        headers={"Content-Disposition": f'attachment; filename="{composition_id}.mid"'},
    )


# 같은 곡을 다시 눌렀을 때 3초를 또 기다리지 않는다.
#
# 열쇠에 **판 번호**가 들어가야 한다. 마디 수로만 잡으면 편곡·직접 편집으로 음이 바뀌어도
# 마디 수는 그대로라 옛 음원이 그대로 나간다 — 악보와 다른 MP3 를 학원에 보내는 셈이다.
# 판 번호는 편곡·직접 편집·재작곡 모두에서 하나씩 올라가므로 그것만으로 충분하다.
_AUDIO_CACHE: dict[tuple[str, str, int], tuple[bytes, str]] = {}
_AUDIO_CACHE_MAX = 8


def _audio_key(store: Store, composition_id: str, hands: str) -> tuple[str, str, int]:
    return (composition_id, hands, len(store.versions.get(composition_id, [])))


@router.get("/compositions/{composition_id}/audio")
def get_audio(
    composition_id: str,
    hands: Literal["both", "rh", "lh"] = "both",
    store: Store = Depends(get_store),
) -> Response:
    """곡을 소리 파일로 준다 — 학생·학부모에게 그대로 보낼 수 있는 형태로.

    MIDI 는 재생기를 가리지만 MP3 는 어디서나 열린다. 인코더가 없으면 WAV 로 준다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]

    key = _audio_key(store, composition_id, hands)
    hit = _AUDIO_CACHE.get(key)
    if hit is None:
        from app.export.audio import render_audio
        from app.generation.assemble import measures_to_note_events

        events = measures_to_note_events(res.measures, res.plan.tempo, res.plan.meter)
        song = store.title_of(composition_id)
        hit = render_audio(events, hands=hands, title=song)
        if len(_AUDIO_CACHE) >= _AUDIO_CACHE_MAX:
            _AUDIO_CACHE.pop(next(iter(_AUDIO_CACHE)))
        _AUDIO_CACHE[key] = hit

    data, ext = hit
    # HTTP 헤더는 latin-1 만 담는다. 한글 제목은 RFC 5987 의 filename* 로만 보내고
    # 옛 브라우저용 filename= 은 ASCII 로 남긴다 — 둘을 섞으면 응답 자체가 깨진다.
    ascii_suffix = {"both": "", "rh": "_rh", "lh": "_lh"}[hands]
    korean_suffix = {"both": "", "rh": "_오른손", "lh": "_왼손"}[hands]
    stem = store.title_of(composition_id).replace('"', "")
    return Response(
        content=data,
        media_type="audio/mpeg" if ext == "mp3" else "audio/wav",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{composition_id}{ascii_suffix}.{ext}"; '
                f"filename*=UTF-8''{quote(stem + korean_suffix)}.{ext}"
            ),
            "X-Audio-Format": ext,
        },
    )


class TitleIn(BaseModel):
    """원장이 정한 제목. 비우면 프로그램이 지은 이름으로 돌아간다."""

    title: str = Field(default="", max_length=120)


class TitleOut(BaseModel):
    composition_id: str
    title: str
    suggested: list[str] = Field(default_factory=list)


@router.get("/compositions/{composition_id}/title-current", response_model=TitleOut)
def read_title(composition_id: str, store: Store = Depends(get_store)) -> TitleOut:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    return TitleOut(
        composition_id=composition_id,
        title=store.title_of(composition_id),
        suggested=list(res.plan.title_candidates),
    )


@router.put("/compositions/{composition_id}/title-current", response_model=TitleOut)
def write_title(composition_id: str, body: TitleIn, store: Store = Depends(get_store)) -> TitleOut:
    """제목을 바꾼다.

    파는 곡의 제목은 상품명이다. 여기서 바꾸면 악보·음원 태그·판매 꾸러미·저작권
    등록 초안 전부가 같은 이름을 쓴다 — 파일마다 다른 이름이 찍히면 안 된다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    title = store.set_title(composition_id, body.title)
    # 제목이 바뀌면 이미 만들어 둔 음원의 태그가 낡는다 — 다음 요청에 다시 만든다.
    for key in [k for k in _AUDIO_CACHE if k[0] == composition_id]:
        _AUDIO_CACHE.pop(key, None)
    store.save()
    res = store.compositions[composition_id]
    return TitleOut(composition_id=composition_id, title=title, suggested=list(res.plan.title_candidates))


class CoverOut(BaseModel):
    """콩쿨 제출용 표지에 들어가는 것들."""

    composition_id: str
    title: str
    composer: str
    student_name: str
    student_grade: str
    division: str
    time_limit_sec: int | None
    key: str
    meter: str
    tempo: int
    measures: int
    difficulty: float
    duration_sec: int


@router.get("/compositions/{composition_id}/cover", response_model=CoverOut)
def get_cover(composition_id: str, store: Store = Depends(get_store)) -> CoverOut:
    """표지에 찍을 것들.

    학생 이름은 **반드시 display_name() 을 거친다**(절대 규칙 7). 악보 표지는 밖으로
    나가는 산출물이고, 미디어 동의가 없는 학생의 본명이 콩쿨 제출본에 실리면 안 된다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    req = store.requests.get(res.request_id)

    from app.api.rights import get_composer
    from app.generation.assemble import measures_to_note_events

    events = measures_to_note_events(res.measures, res.plan.tempo, res.plan.meter)
    student = getattr(req, "student", None)
    competition = getattr(req, "competition", None)
    return CoverOut(
        composition_id=composition_id,
        title=store.title_of(composition_id),
        composer=get_composer(store).display(),
        student_name=student.display_name() if student else "",
        student_grade=getattr(student, "grade", "") if student else "",
        division=getattr(competition, "division", "") if competition else "",
        time_limit_sec=getattr(competition, "time_limit_sec", None) if competition else None,
        key=res.plan.key,
        meter=res.plan.meter,
        tempo=res.plan.tempo,
        measures=len(res.measures),
        difficulty=res.difficulty,
        duration_sec=round(events.notes[-1].offset) if events.notes else 0,
    )


def _teaching(store: Store, composition_id: str):  # type: ignore[no-untyped-def]
    """이 곡의 지도용 표기. 해설이 이미 있으면 그 요점까지 끌어다 쓴다."""
    from app.analysis.teaching import teaching_marks

    res = store.compositions[composition_id]
    guide = store.jobs.get("guides", {}).get(composition_id)
    return teaching_marks(res.measures, res.plan, guide)


class SpotOut(BaseModel):
    measure: int
    hand: str | None
    kind: str
    message: str


class TeachingOut(BaseModel):
    composition_id: str
    caution: str
    fingering_count: int
    section_notes: list[tuple[int, str]]
    spots: list[SpotOut]
    markdown: str


@router.get("/compositions/{composition_id}/teaching", response_model=TeachingOut)
def get_teaching(composition_id: str, store: Store = Depends(get_store)) -> TeachingOut:
    """지도용 표기 — 원장이 이 곡으로 가르칠 때 필요한 것.

    손가락 번호는 제안이고, 걸리는 자리는 악보에서 센 사실이다. 둘을 섞어 내되
    어느 쪽이 어느 쪽인지 화면에 적어 준다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    from app.export.teaching_score import teaching_markdown

    marks = _teaching(store, composition_id)
    title = store.title_of(composition_id)
    return TeachingOut(
        composition_id=composition_id,
        caution=marks.caution,
        fingering_count=len(marks.fingering),
        section_notes=marks.section_notes,
        spots=[SpotOut(measure=x.measure, hand=x.hand, kind=x.kind, message=x.message) for x in marks.spots],
        markdown=teaching_markdown(marks, title),
    )


@router.get("/compositions/{composition_id}/teaching.musicxml")
def get_teaching_score(composition_id: str, store: Store = Depends(get_store)) -> Response:
    """지도용 악보 파일. 연주용과 음표는 같고 표기만 다르다."""
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]

    from app.api.rights import get_composer
    from app.export.teaching_score import build_teaching_score
    from app.generation.assemble import AssembleOptions

    title = store.title_of(composition_id)
    xml = build_teaching_score(
        res.measures,
        AssembleOptions(
            title=title,
            composer=get_composer(store).display(),
            key_sig=res.plan.key,
            meter=res.plan.meter,
            tempo=res.plan.tempo,
        ),
        _teaching(store, composition_id),
    )
    return Response(
        content=xml,
        media_type="application/vnd.recordare.musicxml+xml; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{composition_id}-teaching.musicxml"; '
                f"filename*=UTF-8''{quote(title + ' (지도용)')}.musicxml"
            )
        },
    )


def package_input(store: Store, composition_id: str) -> PackageInput:
    """꾸러미 하나를 만드는 재료를 모은다.

    한 곡 꾸러미와 곡집이 같은 재료를 쓴다 — 갈라지면 한쪽에만 파일이 빠지고,
    그것은 학원에 보낸 뒤에야 드러난다.
    """
    res = store.compositions[composition_id]

    from app.api.rights import get_composer, get_rights
    from app.api.studio import judge_summary
    from app.config import get_settings
    from app.export.audio import render_audio
    from app.export.midi import measures_to_midi
    from app.export.package import PackageInput
    from app.export.teaching_score import build_teaching_score, teaching_markdown
    from app.generation.assemble import AssembleOptions, measures_to_note_events

    title = store.title_of(composition_id)
    events = measures_to_note_events(res.measures, res.plan.tempo, res.plan.meter)
    audio, ext = render_audio(events, title=title)
    rights = get_rights(store, composition_id)
    ready, blockers = rights.clearance()
    judge_average, judge_passed = judge_summary(store, composition_id, get_settings())

    # 지도용 판 — 원장이 보고 가르치는 쪽. 연주용과 음표는 같고 표기만 다르다.
    marks = _teaching(store, composition_id)
    composer = get_composer(store).display()
    teaching_xml = build_teaching_score(
        res.measures,
        AssembleOptions(
            title=title,
            composer=composer,
            key_sig=res.plan.key,
            meter=res.plan.meter,
            tempo=res.plan.tempo,
        ),
        marks,
    )
    return PackageInput(
        composition_id=composition_id,
        title=title,
        composer=composer,
        key=res.plan.key,
        meter=res.plan.meter,
        tempo=res.plan.tempo,
        measures=len(res.measures),
        difficulty=res.difficulty,
        duration_sec=round(events.notes[-1].offset) if events.notes else 0,
        musicxml=res.musicxml,
        audio=audio,
        audio_ext=ext,
        midi=measures_to_midi(res.measures, res.plan.tempo, res.plan.meter),
        guide=store.jobs.get("guides", {}).get(composition_id),
        rights=rights,
        rights_ready=ready,
        rights_blockers=blockers,
        combined_score=res.quality.combined_score,
        judge_average=judge_average,
        judge_passed=judge_passed,
        teaching_musicxml=teaching_xml,
        teaching_notes=teaching_markdown(marks, title),
    )


@router.get("/compositions/{composition_id}/package")
def get_package(composition_id: str, store: Store = Depends(get_store)) -> Response:
    """판매 꾸러미 — 악보·음원·MIDI·해설·권리 정보를 ZIP 하나로.

    학원에 팔 때 파일을 하나씩 받아 모으는 일은 사람이 할 일이 아니다. 받는 쪽은
    이 프로그램을 모르므로, 무엇이 들었고 무엇부터 열면 되는지를 안에 적어 보낸다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")

    from app.export.package import build_package

    data, filename = build_package(package_input(store, composition_id))
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{composition_id}.zip\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.post("/compositions/{composition_id}/guide", response_model=Guide)
def make_guide(composition_id: str, store: Store = Depends(get_store)) -> Guide:
    """§6.6 연주법 해설. 모든 마디 참조가 곡 안에 있어야 통과한다."""
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    if res.request_id not in store.requests:
        raise HTTPException(409, f"이 곡의 생성 요청을 찾을 수 없다: {res.request_id}")

    from app.guide.writer import GuideAnchorError, write_guide

    ctx = build_context(store.requests[res.request_id])
    try:
        guide = write_guide(ctx, res.measures, res.plan)
    except GuideAnchorError as e:
        raise HTTPException(422, str(e)) from e
    store.jobs.setdefault("guides", {})[composition_id] = guide
    return guide


@router.get("/compositions/{composition_id}/guide", response_model=Guide)
def get_guide(composition_id: str, store: Store = Depends(get_store)) -> Guide:
    guide = store.jobs.get("guides", {}).get(composition_id)
    if guide is None:
        raise HTTPException(404, "해설이 아직 만들어지지 않았다 — POST 로 먼저 생성하라")
    return guide


@router.post("/compositions/{composition_id}/title", response_model=TitleSuggestion)
def make_title(composition_id: str, store: Store = Depends(get_store)) -> TitleSuggestion:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    res = store.compositions[composition_id]
    if res.request_id not in store.requests:
        raise HTTPException(409, f"이 곡의 생성 요청을 찾을 수 없다: {res.request_id}")

    from app.guide.writer import suggest_title

    ctx = build_context(store.requests[res.request_id])
    return suggest_title(ctx, res.measures, res.plan)
