#!/usr/bin/env python3
"""모의 심사 3인 패널 데모. `make demo-judge`"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.api.deps import get_engine  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.generation.context import build_context  # noqa: E402
from app.generation.pipeline import CompositionPipeline  # noqa: E402
from app.judge.panel import PERSONA_KO, run_panel_claude, run_panel_rules  # noqa: E402
from app.schemas.student import CompetitionProfile, CompositionRequest, HandSpan, Student  # noqa: E402


def main() -> int:
    s = get_settings()
    student = Student(
        id="s1", name="김민준", grade="초3", hand_span=HandSpan(max_interval=7), level=4,
        strengths=["빠른 손가락"], weaknesses=["옥타브"], tempo_comfort_max_bpm=112,
        reading_level=5, lowest_midi=36, highest_midi=93,
    )
    comp = CompetitionProfile(
        id="c1", name="OO음악콩쿨", division="초등 저학년부", time_limit_sec=150,
        criteria_text="정확성 30% · 음악성 40% · 난이도 적절성 30%",
    )
    req = CompositionRequest(
        id="r1", student=student, competition=comp, target_difficulty=4.0,
        mood="밝고 활기찬", key_preference=["A"], meter="4/4", tempo=104,
    )
    ctx = build_context(req)
    pipe = CompositionPipeline(get_engine(), progress=lambda *_: None)
    motif = pipe.motifs(ctx, 1)[0]
    res = pipe.compose(ctx, motif)

    panel = (
        run_panel_claude(ctx, res.measures, res.plan, settings=s)
        if s.has_api_key
        else run_panel_rules(ctx, res.measures, res.plan, motif)
    )

    print(f"곡: {len(res.measures)}마디 · 난이도 {res.difficulty} · {comp.name} {comp.division}\n")
    for v in panel.verdicts:
        print(f"── 심사위원 {PERSONA_KO[v.persona]} · 총점 {v.total}/10")
        print(f"   정확 {v.accuracy} · 표현 {v.expression} · 구조 {v.structure} "
              f"· 난이도 {v.difficulty_fit} · 인상 {v.impression}")
        print(f"   {v.comment}")
        for f in v.fix_in_score:
            print(f"   [곡 수정] {f}")
        for f in v.fix_in_practice:
            print(f"   [연습 보완] {f}")
        print()
    print(f"평균 {panel.average}/10")
    consensus = panel.consensus_fixes()
    if consensus:
        print("둘 이상이 지적한 것 (먼저 고칠 것):")
        for c in consensus:
            print(f"  - {c}")
    print("\n※ 입상은 곡·연주·심사위원 취향의 결과다. 이 리포트는 약점을 미리 찾기 위한 것이며")
    print("  어떤 결과도 보장하지 않는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
