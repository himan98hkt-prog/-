#!/usr/bin/env python3
"""설치 자기 점검 — 실제로 한 곡을 끝까지 만들어 본다.

의존성이 들어갔는지만 보는 점검은 쓸모가 없다. music21 이 악보를 만들고
검증기가 통과시키는지까지 확인해야 '설치가 됐다' 고 말할 수 있다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def main() -> int:
    from app.config import get_settings
    from app.generation.context import build_context
    from app.generation.engines.stub import StubComposerEngine
    from app.generation.pipeline import CompositionPipeline
    from app.schemas.student import CompetitionProfile, CompositionRequest, HandSpan, Student

    settings = get_settings()
    student = Student(
        id="check", name="점검", grade="초3", level=4,
        hand_span=HandSpan(max_interval=7), tempo_comfort_max_bpm=112,
    )
    req = CompositionRequest(
        id="check", student=student, target_difficulty=4.0, mood="밝은",
        meter="4/4", tempo=100,
        competition=CompetitionProfile(
            id="c", name="점검", division="초3", time_limit_sec=120, original_allowed=True
        ),
    )
    pipe = CompositionPipeline(StubComposerEngine(), progress=lambda *_: None)
    ctx = build_context(req)
    motifs = pipe.motifs(ctx, 2)
    if not motifs:
        print("  모티브 후보를 하나도 만들지 못했다", file=sys.stderr)
        return 1
    res = pipe.compose(ctx, motifs[0])
    if not res.savable:
        print(f"  검증기 실패: {res.validation.summary()}", file=sys.stderr)
        return 1

    print(
        f"  시험 작곡 {len(res.measures)}마디 · 검증 {res.validation.summary()} "
        f"· 품질 {res.quality.combined_score} · 난이도 {res.difficulty}"
    )
    print(
        "  API 키: "
        + ("있음" if settings.has_api_key else "없음 — 규칙 기반 스텁으로 돈다")
    )
    print(f"  저장 위치: {settings.resolved_store_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
