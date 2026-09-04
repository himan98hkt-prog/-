"""화면에서 **의뢰서를 뽑고, 받아온 곡을 넣는** 두 개의 문.

원장님 설계 그대로다. 프로그램이 프롬프트를 만들고 → 대화창에서 곡이 오고 →
그 곡을 프로그램에 넣으면 → 편집·곡집·판매 꾸러미·저작권 서류·보관함이 전부 열린다.

**둘 다 API 를 부르지 않는다. 비용 0 이다.**
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import Store, get_store
from app.config import Settings, get_settings
from app.generation.context import InfeasibleRequest, build_context
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import CriticReport
from app.schemas.student import CompetitionProfile, CompositionRequest, Student

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/handoff", tags=["handoff"])


def _context(
    tier_id: str, preset_id: str,
    student: Student | None, competition: CompetitionProfile | None,
    target_difficulty: float | None,
):
    """작곡 경로가 쓰는 것과 **똑같은** 조건을 세운다.

    여기서 다른 값을 쓰면 의뢰서와 검사가 어긋난다 — 의뢰서대로 만들어 왔는데
    떨어지는 곡이 나온다. 그러니 같은 함수를 부른다.
    """
    from app.generation.market import BY_TIER, standard_competition, standard_student
    from app.generation.presets import BY_ID, pick_key, pick_tempo

    tier = BY_TIER.get(tier_id) if tier_id else None
    preset = BY_ID.get(preset_id) if preset_id else None
    if tier_id and tier is None:
        raise HTTPException(404, f"그런 급수가 없습니다: {tier_id}")
    if preset_id and preset is None:
        raise HTTPException(404, f"그런 성격이 없습니다: {preset_id}")

    stu: Student
    comp: CompetitionProfile | None
    if tier is not None:
        stu = standard_student(tier)
        comp = standard_competition(tier)
        diff = float(tier.level)
    else:
        if student is None:
            raise HTTPException(422, "급수(tier_id)나 학생 중 하나는 주셔야 합니다")
        stu, comp, diff = student, competition, float(target_difficulty or student.level)

    req = CompositionRequest(
        id="handoff",
        student=stu,
        competition=comp,
        target_difficulty=diff,
        mood=preset.mood if preset else "",
        form=preset.form if preset else "ABA",
        key_preference=[pick_key(preset, diff)] if preset else [],
        meter=preset.meter if preset else "4/4",
        tempo=pick_tempo(preset, diff, stu.tempo_comfort_max_bpm) if preset else 100,
    )
    try:
        ctx = build_context(req)
    except InfeasibleRequest as e:
        raise HTTPException(422, str(e)) from e
    return ctx, preset, tier


class BriefIn(BaseModel):
    model_config = {"extra": "forbid"}

    tier_id: str = ""
    preset_id: str = ""
    student: Student | None = None
    competition: CompetitionProfile | None = None
    target_difficulty: float | None = Field(default=None, ge=1.0, le=10.0)
    # 원장님만 쓰시는 칸. 나머지는 프로그램이 채운다.
    wish: str = Field(default="", max_length=2000)


@router.post("/brief")
def make_brief(body: BriefIn) -> dict:
    """대화창에 그대로 붙여 넣을 **작곡 의뢰서** 한 장."""
    from app.generation.context import estimate_measures
    from app.handoff.brief import build_brief

    ctx, preset, tier = _context(
        body.tier_id, body.preset_id, body.student, body.competition, body.target_difficulty,
    )
    hint = 0
    try:
        hint = estimate_measures(ctx.request, ctx.request.meter, ctx.request.tempo)
    except Exception:      # 마디 수를 못 셈해도 의뢰서는 나와야 한다
        log.debug("마디 수 추정 실패 — 의뢰서에서 뺀다", exc_info=True)
    text = build_brief(
        ctx, preset, tier_name=tier.name if tier else "", wish=body.wish, measures_hint=hint,
    )
    return {
        "brief": text,
        "chars": len(text),
        "filename": f"작곡의뢰서_{tier.name if tier else '맞춤'}_{preset.name if preset else '자유'}.md",
        "how": [
            "1. 아래 글을 통째로 복사합니다",
            "2. Claude 대화창에 붙여 넣고 보냅니다",
            "3. 돌아온 JSON 을 아래 '받아온 곡 넣기' 에 붙여 넣습니다",
        ],
    }


class TakeInIn(BaseModel):
    model_config = {"extra": "forbid"}

    # 어떤 조건으로 의뢰했는지 — 검사가 같은 잣대를 쓰도록 그대로 다시 받는다.
    tier_id: str = ""
    preset_id: str = ""
    student: Student | None = None
    competition: CompetitionProfile | None = None
    target_difficulty: float | None = Field(default=None, ge=1.0, le=10.0)

    # 대화창에서 받아 온 것.
    title: str = Field(default="", max_length=120)
    plan: CompositionPlan
    motif: MotifCandidate
    measures: list[Measure] = Field(min_length=1, max_length=400)
    critic: CriticReport


@router.post("/take-in")
def take_in_piece(
    body: TakeInIn,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """받아온 곡을 **검사해서** 보관함에 넣는다. 통과 못 하면 넣지 않는다."""
    from app.api.corpus import get_corpus
    from app.api.studio import _judge
    from app.handoff.receive import numbering_problems, summarize, take_in

    ctx, _preset, _tier = _context(
        body.tier_id, body.preset_id, body.student, body.competition, body.target_difficulty,
    )

    # 검증기 앞에서 걸러야 할 것 — 마디 번호가 빠졌다는 말을 음악 오류로 하면 안 된다.
    early = numbering_problems(body.measures, body.plan)
    if early:
        raise HTTPException(422, {
            "message": "악보를 읽다 막혔습니다",
            "what_to_do": "아래 내용을 대화창에 그대로 알려 주시고 고친 JSON 을 받아 주십시오.",
            "issues": early,
        })

    # **요청을 저장소에 등록해 둔다.**
    # 이걸 빼먹으면 곡은 저장되는데 연주 해설이 안 나온다 — 해설은 "누가 치는 곡인가"
    # 를 알아야 쓸 수 있고, 그것을 요청에서 읽기 때문이다. 실제로 한 번 빠뜨렸다.
    rid = store.next_id("req", store.requests)
    ctx.request.id = rid
    store.requests[rid] = ctx.request

    ngrams = get_corpus().ngram_index() or None
    res = take_in(
        ctx, measures=body.measures, plan=body.plan, motif=body.motif,
        critic=body.critic, title=body.title, corpus_ngrams=ngrams,
    )

    from app.api.compositions import _issues

    if not res.savable:
        # **저장하지 않는다.** 밖에서 왔다고 문을 낮추면 절대 규칙 2 가 무너진다.
        raise HTTPException(422, {
            "message": "검증을 통과하지 못해 넣지 않았습니다",
            "what_to_do": (
                "아래 지적을 대화창에 그대로 붙여 넣고 '이 부분을 고쳐 달라' 고 하십시오. "
                "고친 JSON 을 다시 넣으시면 됩니다. 비용은 들지 않습니다."
            ),
            "issues": _issues(res.validation),
        })

    panel = _judge(ctx, res.measures, res.plan, settings)
    lowest = min(v.total for v in panel.verdicts)

    cid = store.next_id("comp", store.compositions)
    store.compositions[cid] = res
    store.versions.setdefault(cid, []).append(res)
    store.judgements[cid] = panel
    # 대화창에서 붙여 준 제목이 있으면 그것이 이 곡의 이름이다 — 설계도의
    # 제목 후보보다 우선한다. 원장님이 보시는 이름과 악보에 찍히는 이름이 달라지면 안 된다.
    if body.title.strip():
        store.set_title(cid, body.title)
    store.jobs.setdefault("auto_history", []).append({
        "composition_id": cid,
        "preset_id": body.preset_id,
        "market_tier": body.tier_id,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cost_usd": 0.0,          # 대화창에서 만든 곡이다 — API 비용이 없다
        "source": "handoff",
    })
    store.save_soon()

    # 만든 곡은 코퍼스에 넣는다 — 다음 곡이 자기 형제와 겹치지 않게(§7.8).
    try:
        get_corpus().register_generated(
            res.measures,
            score_id=f"gen-{cid}",
            title=store.title_of(cid),
            key=res.plan.key,
            meter=res.plan.meter,
            tempo=res.plan.tempo,
            division_tags=[ctx.competition.division] if ctx.competition else [],
        )
    except Exception:
        # 등록이 실패했다고 방금 들인 곡을 버릴 이유는 없다.
        log.exception("[%s] 코퍼스 등록에 실패했다 — 곡은 그대로 둔다", cid)

    out = summarize(res)
    out["title"] = store.title_of(cid)
    out.update({
        "composition_id": cid,
        "judge": {
            "passed": panel.average >= settings.judge_gate_average
            and lowest >= settings.judge_gate_minimum,
            "average": panel.average,
            "minimum": round(lowest, 2),
        },
        "validation": {
            "passed": res.validation.passed,
            "summary": res.validation.summary(),
            "issues": _issues(res.validation),
        },
        "cost_usd": 0.0,
    })
    return out
