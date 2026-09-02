"""§9 대시보드(스튜디오) API — 컨셉 버튼 하나로 곡을 만들고, 만든 곡을 편곡한다.

기존 워크플로(모티브 → Plan → Realize)는 원장이 단계마다 개입하는 길이다. 그것이
품질의 근거이므로 그대로 둔다. 여기에 얹는 것은 **같은 파이프라인을 사람 대신 지표가
고르며 끝까지 도는 길**이다 — 단계를 건너뛰지 않는다. 모티브도 Plan 도 전부 만들되,
고르는 주체가 사람에서 지표로 바뀔 뿐이다(§7.9 원칙 5 의 3안 자동 선택과 같은 논리).

그리고 원클릭으로 나온 곡은 **모의 심사 3인을 통과해야** '심사 통과' 로 표시된다.
문턱 미달이면 심사위원들이 공통으로 지적한 곳을 겨냥해 한 번 더 고친다.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import Store, get_pipeline, get_store
from app.api.rights import get_rights
from app.config import Settings, get_settings
from app.generation.context import InfeasibleRequest, build_context
from app.generation.pipeline import CompositionPipeline, PlanRejected
from app.generation.presets import BY_ID, PRESETS, pick_key, pick_tempo, suitable
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import JudgePanel
from app.schemas.student import CompetitionProfile, CompositionRequest, Student

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["studio"])


# ── 프리셋 ───────────────────────────────────────────────────────────────────


class PresetOut(BaseModel):
    id: str
    name: str
    blurb: str
    mood: str
    form: str
    meter: str
    tempo: list[int]
    texture_options: list[str]
    keys: list[str]
    level_range: list[int]
    shows_off: list[str]
    avoid_if: list[str]
    recommended: bool = Field(default=True, description="이 학생에게 권할 만한가")


@router.get("/presets", response_model=list[PresetOut])
def list_presets(student_id: str | None = None, store: Store = Depends(get_store)) -> list[PresetOut]:
    """컨셉 카드 목록. 학생을 주면 권할 만한 것을 앞에 놓고 나머지도 함께 준다.

    권하지 않는 것을 **숨기지는 않는다** — 원장이 일부러 어려운 성격을 고를 수 있어야 한다.
    """
    ok_ids: set[str] = {p.id for p in PRESETS}
    if student_id:
        s = store.students.get(student_id)
        if s is None:
            raise HTTPException(404, f"학생을 찾을 수 없다: {student_id}")
        ok_ids = {p.id for p in suitable(s.level, s.weaknesses)}
    out = [
        PresetOut(
            **{**p.as_dict(), "tempo": list(p.tempo), "level_range": list(p.level_range)},
            recommended=p.id in ok_ids,
        )
        for p in PRESETS
    ]
    return sorted(out, key=lambda p: (not p.recommended, p.id))


# ── 원클릭 작곡 ──────────────────────────────────────────────────────────────


class AutoComposeIn(BaseModel):
    model_config = {"extra": "forbid"}

    preset_id: str
    student_id: str | None = None
    student: Student | None = None
    competition_profile_id: str | None = None
    competition: CompetitionProfile | None = None
    target_difficulty: float | None = Field(default=None, ge=1, le=10)
    key: str | None = None
    tempo: int | None = Field(default=None, ge=30, le=240)
    total_measures: int | None = Field(default=None, ge=8, le=200)
    n_candidates: int = Field(default=1, ge=1, le=3)
    must_include: str = ""


class JudgeGate(BaseModel):
    passed: bool
    average: float
    minimum: float
    required_average: float
    required_minimum: float
    rounds: int = Field(description="심사 미달로 다시 고친 횟수")
    consensus_fixes: list[str] = Field(default_factory=list)
    panel: JudgePanel | None = None


class AutoComposeOut(BaseModel):
    request_id: str
    composition_id: str
    preset_id: str
    title: str
    engine: str
    measures: int
    difficulty: float
    key: str
    meter: str
    tempo: int
    savable: bool
    shown_as_draft: bool
    combined_score: float
    musicality: float
    validation: dict
    judge: JudgeGate
    cost: dict


def _resolve_student(body: AutoComposeIn, store: Store) -> Student:
    if body.student is not None:
        return body.student
    if body.student_id:
        s = store.students.get(body.student_id)
        if s is None:
            raise HTTPException(404, f"학생을 찾을 수 없다: {body.student_id}")
        return s
    raise HTTPException(422, "student_id 또는 student 중 하나는 있어야 한다")


def _resolve_competition(body: AutoComposeIn, store: Store) -> CompetitionProfile | None:
    if body.competition is not None:
        return body.competition
    if body.competition_profile_id:
        c = store.competitions.get(body.competition_profile_id)
        if c is None:
            raise HTTPException(404, f"콩쿨 프로필을 찾을 수 없다: {body.competition_profile_id}")
        return c
    return None


def build_request(body: AutoComposeIn, store: Store) -> CompositionRequest:
    """프리셋 + 학생 → 작곡 요청. 프리셋은 초안이고, 넘어온 값이 있으면 그것이 이긴다."""
    preset = BY_ID.get(body.preset_id)
    if preset is None:
        raise HTTPException(404, f"컨셉을 찾을 수 없다: {body.preset_id}")
    student = _resolve_student(body, store)
    competition = _resolve_competition(body, store)

    # 목표 난이도를 안 주면 학생 레벨을 그대로 쓴다 — 레벨 1~10 과 난이도 1~10 은 같은 자다.
    target = body.target_difficulty if body.target_difficulty is not None else float(student.level)
    key = body.key or pick_key(preset, target)
    tempo = body.tempo or pick_tempo(preset, target, student.tempo_comfort_max_bpm)

    rid = store.next_id("req", store.requests)
    req = CompositionRequest(
        id=rid,
        student=student,
        competition=competition,
        target_difficulty=target,
        mood=preset.mood,
        form=preset.form,  # type: ignore[arg-type]
        key_preference=[key],
        meter=preset.meter,
        tempo=tempo,
        total_measures=body.total_measures,
        texture_options=list(preset.texture_options),
        must_include=body.must_include,
        n_candidates=body.n_candidates,
    )
    store.requests[rid] = req
    return req


def _previous_plans(store: Store, exclude: str) -> list[tuple[str, CompositionPlan]]:
    from app.api.compositions import _previous_plans as impl

    return impl(store, exclude)


def _ranked_motifs(ctx: Any, pipeline: CompositionPipeline, n: int) -> list[MotifCandidate]:
    """사람이 고르는 자리를 지표로 대신한다. 좋은 순으로 **전부** 돌려준다.

    모티브는 '머리 음정열이 또렷하고 곡 전체로 퍼뜨리기 좋은가' 가 전부다. 머리가 충분히
    길고 도약이 하나 이상 있는 것을 앞에 놓는다 — 순차로만 된 머리는 어디에 갖다 놔도
    모티브로 들리지 않는다.

    하나만 돌려주지 않는 이유: 설계가 이미 만든 곡과 겹쳐 막히면 **다른 모티브로 다시**
    시도해야 하기 때문이다. 원장이 버튼 하나를 눌렀는데 겹침 오류 벽을 보게 할 수는 없다.
    """
    candidates = pipeline.motifs(ctx, n)
    if not candidates:
        raise HTTPException(422, "학생 제약을 지키는 모티브 후보를 만들지 못했다")

    def rank(m: MotifCandidate) -> tuple[bool, bool, int]:
        head = m.head_intervals()
        leaps = sum(1 for i in head if abs(i) >= 5)
        return (len(head) >= 3, leaps >= 1, len(head))

    return sorted(candidates, key=rank, reverse=True)


def _other_concepts(store: Store, ctx: Any, used_preset: str) -> list[dict[str, str]]:
    """막혔을 때 대신 눌러 볼 컨셉. 최근에 쓴 것과 지금 것은 뺀다.

    "겹칩니다" 로 끝내면 컴퓨터에 익숙하지 않은 원장은 거기서 멈춘다. 다음에 무엇을
    누르면 되는지까지 줘야 프로그램이 길을 막지 않는다.
    """
    recent = {
        j.get("preset_id") for j in list(store.jobs.get("auto_history", []))[-4:] if isinstance(j, dict)
    }
    recent.add(used_preset)
    out: list[dict[str, str]] = []
    for preset in suitable(ctx.student.level, ctx.student.weaknesses):
        if preset.id in recent:
            continue
        out.append({"id": preset.id, "name": preset.name, "blurb": preset.blurb})
        if len(out) == 3:
            break
    return out


def _plan_with_retry(
    ctx: Any,
    pipeline: CompositionPipeline,
    motifs: list[MotifCandidate],
    previous: list[tuple[str, CompositionPlan]],
    alternatives: list[dict[str, str]] | None = None,
) -> tuple[MotifCandidate, CompositionPlan]:
    """설계가 이미 만든 곡과 겹치면 **다른 모티브로 다시** 시도한다.

    겹침 검사(절대 규칙 12)는 하드 실패가 맞다 — 같은 콩쿨에 형제 같은 곡을 내보내는 것이
    개별 곡의 결함보다 크다. 다만 그것은 *이 설계*를 버리라는 뜻이지 원장에게 오류를
    보이라는 뜻이 아니다. 후보를 다 써도 겹치면 그때 사람이 판단할 일이 된다.
    """
    blocked: list[str] = []
    for motif in motifs:
        locked = motif.model_copy(update={"selected": True})
        try:
            plan, report = pipeline.plan(ctx, locked, previous_plans=previous)
        except PlanRejected as e:
            blocked.append(str(e))
            continue
        if report.passed:
            return locked, plan
        blocked.extend(i.message for i in report.hard_failures)
    alt = alternatives or []
    tip = (
        "아래 컨셉 중 하나를 눌러 보십시오 — 이 학생에게 맞으면서 방금 만든 곡과 겹치지 않습니다."
        if alt
        else "목표 난이도나 박자를 바꾸거나, '단계별로 만들기' 에서 설계를 직접 손보십시오."
    )
    raise HTTPException(
        409,
        {
            "message": "방금 만든 곡과 형식이 너무 닮아서 멈췄습니다",
            "what_to_do": tip,
            "issues": blocked[:3],
            "alternatives": alt,
        },
    )


def judge_summary(store: Store, composition_id: str, settings: Settings) -> tuple[float | None, bool | None]:
    """이 곡의 사전 심사 (평균, 통과 여부). 심사 전이면 (None, None).

    보관함·판매 꾸러미·화면이 서로 다른 답을 내면 안 되므로 판정은 여기 한 군데다.
    """
    panel = store.judgements.get(composition_id)
    if panel is None:
        return None, None
    low = min((v.total for v in panel.verdicts), default=None)
    if low is None:
        return panel.average, None
    passed = panel.average >= settings.judge_gate_average and low >= settings.judge_gate_minimum
    return panel.average, passed


def _judge(ctx: Any, measures: list, plan: CompositionPlan, s: Settings) -> JudgePanel:
    from app.judge.panel import run_panel_claude, run_panel_rules

    if s.has_api_key:
        try:
            return run_panel_claude(ctx, measures, plan, settings=s)
        except Exception:  # 심사가 안 돌아도 곡은 나와야 한다
            log.warning("모의 심사 호출 실패 — 규칙 기반으로 대체한다", exc_info=True)
    return run_panel_rules(ctx, measures, plan)


@router.post("/compositions/auto", response_model=AutoComposeOut)
def auto_compose(
    body: AutoComposeIn,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_settings),
) -> AutoComposeOut:
    """컨셉 버튼 하나로 끝까지 — 모티브·Plan·작곡·심사까지.

    단계를 건너뛰지 않는다. 원장이 나중에 모티브나 Plan 을 바꾸고 싶으면 기존
    워크플로 API 로 같은 request_id 위에서 이어서 하면 된다.
    """
    req = build_request(body, store)
    ctx = build_context(req)

    motifs = _ranked_motifs(ctx, pipeline, max(3, body.n_candidates + 2))
    try:
        locked, plan = _plan_with_retry(
            ctx,
            pipeline,
            motifs,
            _previous_plans(store, req.id),
            _other_concepts(store, ctx, body.preset_id),
        )
    except InfeasibleRequest as e:
        raise HTTPException(422, str(e)) from e
    store.motifs[req.id] = [locked]
    store.plans[req.id] = {"plan": plan, "motif": locked, "approved": True}

    from app.api.corpus import get_corpus

    ngrams = get_corpus().ngram_index() or None
    try:
        results = pipeline.compose_candidates(ctx, locked, plan, n=body.n_candidates, corpus_ngrams=ngrams)
    except (PlanRejected, InfeasibleRequest) as e:
        raise HTTPException(422, str(e)) from e

    res = results[0]

    # ── 사전 전문심사 게이트 ────────────────────────────────────────────────
    panel = _judge(ctx, res.measures, res.plan, settings)
    rounds = 0
    for _ in range(settings.judge_gate_rounds):
        lowest = min(v.total for v in panel.verdicts)
        if panel.average >= settings.judge_gate_average and lowest >= settings.judge_gate_minimum:
            break
        fixes = panel.consensus_fixes()
        if not fixes:
            break
        # 심사위원 둘 이상이 같은 취지로 지적한 것만 실행한다. 한 명의 취향은 취향이다.
        retry = pipeline.revise_with_notes(ctx, res, fixes)
        if retry is None:
            break
        rounds += 1
        res = retry
        panel = _judge(ctx, res.measures, res.plan, settings)

    lowest = min(v.total for v in panel.verdicts)
    gate = JudgeGate(
        passed=panel.average >= settings.judge_gate_average and lowest >= settings.judge_gate_minimum,
        average=panel.average,
        minimum=round(lowest, 2),
        required_average=settings.judge_gate_average,
        required_minimum=settings.judge_gate_minimum,
        rounds=rounds,
        consensus_fixes=panel.consensus_fixes(),
        panel=panel,
    )

    cid = store.next_id("comp", store.compositions)
    store.compositions[cid] = res
    store.versions.setdefault(cid, []).append(res)
    # 어떤 컨셉을 최근에 썼는지 남긴다 — 겹쳐서 막혔을 때 다른 컨셉을 권하는 근거다.
    store.jobs.setdefault("auto_history", []).append({"composition_id": cid, "preset_id": body.preset_id})
    store.judgements[cid] = panel

    title = res.plan.title_candidates[0] if res.plan.title_candidates else cid
    if res.savable:
        get_corpus().register_generated(
            res.measures,
            score_id=f"gen-{cid}",
            title=title,
            key=res.plan.key,
            meter=res.plan.meter,
            tempo=res.plan.tempo,
            division_tags=[ctx.competition.division] if ctx.competition else [],
        )

    from app.api.compositions import _issues

    return AutoComposeOut(
        request_id=req.id,
        composition_id=cid,
        preset_id=body.preset_id,
        title=title,
        engine=res.engine,
        measures=len(res.measures),
        difficulty=res.difficulty,
        key=res.plan.key,
        meter=res.plan.meter,
        tempo=res.plan.tempo,
        savable=res.savable,
        shown_as_draft=res.shown_as_draft,
        combined_score=res.quality.combined_score,
        musicality=float(res.quality.musicality["score_10"]),
        validation={
            "passed": res.validation.passed,
            "summary": res.validation.summary(),
            "issues": _issues(res.validation),
        },
        judge=gate,
        cost=res.cost,
    )


# ── 편곡(구간 다시 쓰기) ─────────────────────────────────────────────────────


class RearrangeIn(BaseModel):
    model_config = {"extra": "forbid"}

    measures: list[int] = Field(min_length=2, max_length=2, description="[시작, 끝]")
    instruction: str = Field(min_length=4, description="예: 왼손을 한 옥타브 내려라")


class RearrangeOut(BaseModel):
    composition_id: str
    version: int
    changed_measures: list[int]
    difficulty: float
    combined_score: float
    musicality: float
    validation: dict


@router.post("/compositions/{composition_id}/rearrange", response_model=RearrangeOut)
def rearrange(
    composition_id: str,
    body: RearrangeIn,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> RearrangeOut:
    """원장이 지정한 구간만 다시 쓴다. 그 밖의 마디는 한 음도 건드리지 않는다.

    이전 판은 `store.versions` 에 남으므로 되돌릴 수 있다.
    """
    res = store.compositions.get(composition_id)
    if res is None:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    lo, hi = body.measures
    total = len(res.measures)
    if not (1 <= lo <= hi <= total):
        raise HTTPException(422, f"마디 범위가 곡(1~{total}) 밖이다: {body.measures}")

    req = store.requests.get(res.request_id)
    if req is None:
        raise HTTPException(409, f"이 곡의 생성 요청을 찾을 수 없다: {res.request_id}")
    ctx = build_context(req)

    out = pipeline.rearrange(ctx, res, (lo, hi), body.instruction)
    store.compositions[composition_id] = out
    store.versions.setdefault(composition_id, []).append(out)

    from app.api.compositions import _issues

    return RearrangeOut(
        composition_id=composition_id,
        version=len(store.versions[composition_id]),
        changed_measures=list(range(lo, hi + 1)),
        difficulty=out.difficulty,
        combined_score=out.quality.combined_score,
        musicality=float(out.quality.musicality["score_10"]),
        validation={
            "passed": out.validation.passed,
            "summary": out.validation.summary(),
            "issues": _issues(out.validation),
        },
    )


# ── 라이브러리 ───────────────────────────────────────────────────────────────


class LibraryItem(BaseModel):
    composition_id: str
    title: str
    key: str
    meter: str
    tempo: int
    measures: int
    difficulty: float
    combined_score: float
    savable: bool
    judged: bool
    judge_average: float | None = None
    judge_passed: bool | None = None
    # 팔 수 있는 곡과 아직 권리가 정리 안 된 곡이 목록에서 섞이지 않게.
    work_type: str = "original"
    rights_ready: bool = True
    rights_note: str = ""
    versions: int


@router.get("/compositions", response_model=list[LibraryItem])
def library(
    store: Store = Depends(get_store), settings: Settings = Depends(get_settings)
) -> list[LibraryItem]:
    """만든 곡 목록. 대시보드의 두 번째 탭이다."""
    out: list[LibraryItem] = []
    for cid, res in store.compositions.items():
        avg, judge_passed = judge_summary(store, cid, settings)
        rights = get_rights(store, cid)
        ready, blockers = rights.clearance()
        note = (
            "창작곡"
            if rights.work_type == "original"
            else ("편곡 · 권리 정리됨" if ready else "편곡 · 원곡 확인 필요")
        )
        if not ready and blockers:
            note = "원곡 확인 필요"
        out.append(
            LibraryItem(
                composition_id=cid,
                title=res.plan.title_candidates[0] if res.plan.title_candidates else cid,
                key=res.plan.key,
                meter=res.plan.meter,
                tempo=res.plan.tempo,
                measures=len(res.measures),
                difficulty=res.difficulty,
                combined_score=res.quality.combined_score,
                savable=res.savable,
                judged=avg is not None,
                judge_average=avg,
                judge_passed=judge_passed,
                work_type=rights.work_type,
                rights_ready=ready,
                rights_note=note,
                versions=len(store.versions.get(cid, [res])),
            )
        )
    return sorted(out, key=lambda x: x.composition_id, reverse=True)


# ── 직접 편집(M4) ────────────────────────────────────────────────────────────


class DirectEditIn(BaseModel):
    model_config = {"extra": "forbid"}

    measures: list[Measure] = Field(min_length=1, description="고친 마디만 보낸다")


class DirectEditOut(BaseModel):
    composition_id: str
    version: int
    changed_measures: list[int]
    difficulty: float
    combined_score: float
    musicality: float
    validation: dict
    savable: bool


@router.put("/compositions/{composition_id}/measures", response_model=DirectEditOut)
def direct_edit(
    composition_id: str,
    body: DirectEditIn,
    store: Store = Depends(get_store),
    pipeline: CompositionPipeline = Depends(get_pipeline),
) -> DirectEditOut:
    """원장이 음표를 직접 고친 마디를 받아 넣는다(§7.3 Stage 7 · M4 편집기의 저장 경로).

    작곡 엔진을 부르지 않는다 — 이것은 생성이 아니라 **사람의 편집**이다. 다만 검증기와
    지표는 그대로 돌린다. 학생 제약을 벗어난 편집은 화면에 보여야 하고, 하드 규칙을
    어기면 `savable=false` 로 표시된다(절대 규칙 2 — 통과 못 한 악보는 저장하지 않는다).
    """
    res = store.compositions.get(composition_id)
    if res is None:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    req = store.requests.get(res.request_id)
    if req is None:
        raise HTTPException(409, f"이 곡의 생성 요청을 찾을 수 없다: {res.request_id}")

    known = {m.number for m in res.measures}
    unknown = sorted({m.number for m in body.measures} - known)
    if unknown:
        raise HTTPException(422, f"곡에 없는 마디 번호다: {unknown}")

    edited = {m.number: m for m in body.measures}
    merged = [edited.get(m.number, m) for m in res.measures]
    ctx = build_context(req)
    out = pipeline.finish_edited(
        ctx,
        merged,
        res.plan,
        res.motif,
        rounds=res.revision_rounds,
        notes=[*res.quality.notes, f"원장 직접 편집 {sorted(edited)}마디"],
    )
    store.compositions[composition_id] = out
    store.versions.setdefault(composition_id, []).append(out)

    from app.api.compositions import _issues

    return DirectEditOut(
        composition_id=composition_id,
        version=len(store.versions[composition_id]),
        changed_measures=sorted(edited),
        difficulty=out.difficulty,
        combined_score=out.quality.combined_score,
        musicality=float(out.quality.musicality["score_10"]),
        savable=out.savable,
        validation={
            "passed": out.validation.passed,
            "summary": out.validation.summary(),
            "issues": _issues(out.validation),
        },
    )
