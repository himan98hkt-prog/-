#!/usr/bin/env python3
"""작곡 파이프라인 데모 — 모티브 → Plan → 프레이즈 실현 → 비평 루프.

API 키가 있으면 Claude 로, 없으면 규칙 기반 스텁으로 돈다.
`make demo-m3`
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.api.deps import get_engine  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.generation.context import build_context, check_feasibility  # noqa: E402
from app.generation.engines.claude_engine import score_to_text  # noqa: E402
from app.generation.pipeline import CompositionPipeline  # noqa: E402
from app.schemas.student import (  # noqa: E402
    CompetitionProfile,
    CompositionRequest,
    HandSpan,
    Student,
)


def main() -> int:
    s = get_settings()
    student = Student(
        id="s1", name="김민준", grade="초3", years_of_study=2.5,
        hand_span=HandSpan(max_interval=7), level=4,
        strengths=["빠른 손가락"], weaknesses=["옥타브"],
        tempo_comfort_max_bpm=112, reading_level=5, lowest_midi=36, highest_midi=93,
        notes="빠른 곡에 강하고 서정적인 표현은 약하다",
    )
    comp = CompetitionProfile(
        id="c1", name="OO음악콩쿨", organizer="OO문화재단", year=2026,
        division="초등 저학년부", time_limit_sec=150, memorization_required=True,
        judge_notes="테크닉보다 음악성을 본다는 평이 있다",
    )
    req = CompositionRequest(
        id="r1", student=student, competition=comp, target_difficulty=4.0,
        mood="밝고 활기찬 알레그로, 중간에 서정적 대비, 마지막은 화려하게",
        form="ABA", key_preference=["A"], meter="4/4", tempo=104,
        must_include="오른손 스케일 패시지로 학생의 빠른 손가락을 보여줄 것",
    )

    ctx = build_context(req)
    engine = get_engine()
    print(f"엔진: {getattr(engine, 'name', '?')} · COMPOSER_MODEL={s.composer_model}")
    warning = check_feasibility(req, ctx.hard)
    if warning:
        print(f"경고: {warning}")

    pipe = CompositionPipeline(engine, progress=lambda st, _pct, m: print(f"  [{st:8s}] {m}"))

    print("\n── Stage 1 · 모티브 후보 ──")
    motifs = pipe.motifs(ctx, 4)
    for m in motifs:
        print(f"  {m.id}  {m.character_label:12s} {m.key} {m.meter} {m.tempo}bpm")
        print(f"        {m.why_it_works}")
    chosen = motifs[0]
    print(f"  → 선택: {chosen.id} ({chosen.character_label}) · 이후 단계의 불변 입력으로 잠긴다")

    print("\n── Stage 2 · 설계 ──")
    plan, report = pipe.plan(ctx, chosen)
    print(f"  {plan.key} {plan.meter} {plan.tempo}bpm · {plan.total_measures}마디 "
          f"· 예상 {plan.duration_est:.0f}초 (제한 {ctx.hard.time_limit_sec}초)")
    for sec in plan.form:
        treats = ", ".join(p.motif_treatment for p in sec.phrases)
        print(f"  [{sec.label}] {sec.measures[0]}-{sec.measures[1]}마디 · {treats}")
    print(f"  클라이맥스 {plan.climax.measure}마디 — {plan.climax.how}")
    for sc in plan.showcase_measures:
        print(f"  쇼케이스 {sc.range[0]}-{sc.range[1]}마디 — {sc.strength_used}")
    print(f"  규칙 검사: {report.summary()}")
    if not report.passed:
        for i in report.hard_failures:
            print(f"    실패 {i.rule}: {i.message}")
        return 1

    print("\n── Stage 3~5 · 실현 · 채점 · 비평 ──")
    res = pipe.compose(ctx, chosen, plan)

    print("\n── 결과 ──")
    print(f"  마디 {len(res.measures)} · 난이도 {res.difficulty} (목표 {ctx.hard.target_difficulty})")
    print(f"  검증: {res.validation.summary()}")
    for i in res.validation.hard_failures:
        print(f"    실패 {i.rule}: {i.message}")
    for i in res.validation.warnings[:5]:
        print(f"    경고 {i.rule}: {i.message}")

    q = res.quality
    print(f"\n  품질 종합 {q.combined_score} / 문턱 {q.threshold} "
          f"→ {'통과' if q.passed else '초안(미통과)'} · 수정 {q.revision_round}라운드")
    print(f"  musicality {q.musicality['score_10']}/10")
    for k, v in q.musicality["metrics"].items():
        mark = "OK  " if v["met"] else "미달"
        print(f"    {mark} {k:22s} {v['value']:.2f}/{v['target']:.2f}  {v['detail'][:60]}")
    if q.critic:
        print(f"  비평 총점 {sum(q.critic['scores'].values()) / len(q.critic['scores']):.2f}/10")
        for rr in q.critic["revision_requests"]:
            print(f"    수정 {rr['measures']}: {rr['instruction'][:70]}")

    if res.cost:
        print(f"\n  API 비용 ${res.cost.get('total_usd', 0):.4f} / 상한 ${s.max_cost_per_composition}")

    print("\n── 악보(앞 8마디) ──")
    print(score_to_text(res.measures[:8], plan))

    out = ROOT / "data" / "demo.musicxml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(res.musicxml, encoding="utf-8")
    print(f"\nMusicXML 저장: {out} ({len(res.musicxml)} bytes)")
    return 0 if res.savable else 1


if __name__ == "__main__":
    raise SystemExit(main())
