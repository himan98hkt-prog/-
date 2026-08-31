"""§6.6 연주법 해설 · §7.3 Stage 6 제목.

WRITER_MODEL(중간 모델)로 충분한 작업이다 — 음악적 판단이 아니라 글쓰기다.
API 키가 없으면 악보 분석만으로 규칙 기반 해설을 만든다(화면·테스트용).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.analysis.difficulty import difficulty_score
from app.config import Settings, get_settings
from app.generation.client import ClaudeClient, CostLedger
from app.generation.context import ComposerContext
from app.generation.engines.claude_engine import score_to_text
from app.schemas.guide import (
    FingeringNote,
    Guide,
    GuideSection,
    MemorizationChunk,
    PracticeWeek,
    TitleSuggestion,
)
from app.schemas.music import CompositionPlan, Measure

GUIDE_PROMPT = Path(__file__).resolve().parent / "prompts" / "guide.md"
TITLE_PROMPT = (
    Path(__file__).resolve().parents[1] / "generation" / "prompts" / "title.md"
)


class GuideAnchorError(ValueError):
    """해설이 곡에 없는 마디를 가리킨다. 화면의 마디 점프가 깨지므로 통과시키지 않는다."""


def _payload(ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan) -> str:
    diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
    return json.dumps(
        {
            "score_text": score_to_text(measures, plan),
            "plan": plan.model_dump(),
            "student": ctx.prompt_payload()["student"],
            "competition": ctx.prompt_payload()["competition"],
            "total_measures": len(measures),
            "difficulty": diff.score,
            "difficulty_division": diff.division_hint(),
        },
        ensure_ascii=False, indent=1, default=str,
    )


def write_guide(
    ctx: ComposerContext,
    measures: list[Measure],
    plan: CompositionPlan,
    *,
    settings: Settings | None = None,
    ledger: CostLedger | None = None,
) -> Guide:
    """해설을 만들고 마디 앵커를 검증한다. 앵커가 틀리면 한 번 다시 요청한다."""
    s = settings or get_settings()
    if not s.has_api_key:
        return rule_based_guide(ctx, measures, plan)

    client = ClaudeClient(s, ledger)
    system = GUIDE_PROMPT.read_text(encoding="utf-8")
    user = _payload(ctx, measures, plan)
    total = len(measures)

    for attempt in range(2):
        guide = client.parse(
            stage="guide", system=system, user=user, output_model=Guide,
            model=s.writer_model,
        )
        bad = guide.invalid_anchors(total)
        if not bad:
            return guide
        if attempt == 0:
            user += (
                f"\n\n앞선 시도가 곡에 없는 마디를 가리켰다: {bad}. "
                f"이 곡은 1~{total}마디뿐이다. 그 안의 번호만 써라."
            )
    raise GuideAnchorError(f"해설의 마디 참조가 곡 밖을 가리킨다: {bad}")


def suggest_title(
    ctx: ComposerContext,
    measures: list[Measure],
    plan: CompositionPlan,
    *,
    settings: Settings | None = None,
    ledger: CostLedger | None = None,
) -> TitleSuggestion:
    s = settings or get_settings()
    if not s.has_api_key:
        candidates = plan.title_candidates or ["무제"]
        return TitleSuggestion(
            candidates=candidates[:3], recommended=candidates[0],
            rationale="API 키가 없어 Plan 의 후보를 그대로 쓴다.",
        )
    client = ClaudeClient(s, ledger)
    return client.parse(
        stage="title",
        system=TITLE_PROMPT.read_text(encoding="utf-8"),
        user=_payload(ctx, measures, plan),
        output_model=TitleSuggestion,
        model=s.writer_model,
    )


# ── 규칙 기반 대역 ───────────────────────────────────────────────────────────


def rule_based_guide(
    ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan
) -> Guide:
    """악보 분석만으로 만드는 해설. 문장은 투박하지만 마디 참조는 항상 정확하다."""
    total = len(measures)
    diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
    by_number = {m.number: m for m in measures}

    sections: list[GuideSection] = []
    for sec in plan.form:
        lo, hi = sec.measures
        lo, hi = max(1, lo), min(total, hi)
        if hi < lo:
            continue
        treatments = ", ".join(dict.fromkeys(p.motif_treatment for p in sec.phrases))
        dyns = [m.dynamics for m in measures if lo <= m.number <= hi and m.dynamics]
        points = [
            f"모티브 처리: {treatments}",
            f"왼손: {sec.phrases[0].texture_lh}" if sec.phrases else "왼손: 반주",
        ]
        if dyns:
            points.append(f"다이내믹 {' → '.join(dyns)}")
        if lo <= plan.climax.measure <= hi:
            points.append(f"{plan.climax.measure}마디가 클라이맥스 — {plan.climax.how}")
        sections.append(GuideSection(measures=[lo, hi], title=f"{sec.label} 부분", points=points))

    fingering: list[FingeringNote] = []
    for m in measures:
        wide = [
            e for v in m.lh for e in v.events
            if len(e.pitches) >= 2
        ]
        if wide and len(fingering) < 5:
            from app.analysis.pitch import pitch_to_midi

            span = max(
                pitch_to_midi(max(e.pitches, key=pitch_to_midi))
                - pitch_to_midi(min(e.pitches, key=pitch_to_midi))
                for e in wide
            )
            if span >= ctx.hard.max_span_semitones - 2:
                fingering.append(
                    FingeringNote(
                        measure=m.number,
                        note=f"왼손 화음 폭 {span}반음 — 손목을 낮추고 미리 벌려 둔다",
                    )
                )

    base = min(plan.tempo, ctx.student.tempo_comfort_max_bpm)
    practice = [
        PracticeWeek(week=1, goal="음과 리듬을 정확히 읽는다",
                     method="양손 따로, 4마디씩 끊어 천천히", metronome_bpm=max(40, int(base * 0.6))),
        PracticeWeek(week=2, goal="양손을 맞춘다",
                     method="프레이즈 단위로 이어 붙이고 프레이즈 끝 호흡을 지킨다",
                     metronome_bpm=max(50, int(base * 0.75))),
        PracticeWeek(week=3, goal="다이내믹과 프레이징을 넣는다",
                     method=f"{plan.climax.measure}마디 클라이맥스를 향해 소리를 쌓는다",
                     metronome_bpm=max(60, int(base * 0.9))),
        PracticeWeek(week=4, goal="암보와 무대 연습",
                     method="구획별로 암보 확인 후 처음부터 끝까지 멈추지 않고", metronome_bpm=base),
    ]

    memo: list[MemorizationChunk] = []
    for sec in plan.form:
        lo, hi = max(1, sec.measures[0]), min(total, sec.measures[1])
        if hi >= lo:
            first = by_number.get(lo)
            cue = ""
            if first:
                tops = [p for v in first.rh for e in v.events for p in e.pitches]
                cue = f"{sec.label} 시작음 {tops[0]}" if tops else f"{sec.label} 시작"
            memo.append(MemorizationChunk(measures=[lo, hi], cue=cue))

    tips = [
        "첫 음을 놓기 전에 속으로 한 마디를 세고 시작한다",
        f"{plan.climax.measure}마디 클라이맥스에서 소리가 거칠어지지 않게 팔 무게로 친다",
        f"마지막 {max(1, total - 3)}~{total}마디는 서두르지 말고 끝까지 소리를 남긴다",
    ]
    if ctx.competition and ctx.competition.memorization_required:
        tips.append("이 대회는 암보가 필수다 — 3주차부터 악보 없이 연습한다")

    return Guide(
        overview=(
            f"{plan.key} {plan.meter} {plan.tempo}bpm, {total}마디 곡이다. "
            f"형식은 {'-'.join(s.label for s in plan.form)}, 난이도 {diff.score}"
            f"({diff.division_hint()}) 수준이다. "
            f"{plan.climax.measure}마디의 클라이맥스를 향해 쌓았다가 정리하는 흐름으로 친다."
        ),
        sections=sections or [GuideSection(measures=[1, total], title="전체", points=["처음부터 끝까지"])],
        fingering_notes=fingering,
        practice_plan=practice,
        competition_tips=tips,
        memorization_map=memo,
    )
