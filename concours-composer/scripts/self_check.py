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

    bad = check_api_schemas()
    if bad:
        print("  실제 작곡(Claude)에 쓸 수 없는 스키마가 있다:", file=sys.stderr)
        for line in bad:
            print(f"    {line}", file=sys.stderr)
        return 1
    print("  Claude 호출 스키마: 전부 통과 — 키를 넣으면 그대로 돈다")
    return 0


def check_api_schemas() -> list[str]:
    """실제 Claude 호출에 쓰는 스키마가 **보내지기 전에** 성립하는지 본다.

    스텁 엔진은 API 를 부르지 않는다. 그래서 스키마가 깨져 있어도 여기까지의 점검은
    전부 통과하고, 원장님이 키를 넣은 뒤 첫 곡에서야 터진다 — 실제로 그랬다.
    이 검사는 돈도 인터넷도 쓰지 않는다. 스키마 변환은 요청을 보내기 전 단계다.
    """
    try:
        from anthropic import transform_schema
        from app.generation.engines.claude_engine import MotifBatch
        from app.guide.writer import Guide, TitleSuggestion
        from app.schemas.music import CompositionPlan, PhraseRealization
        from app.schemas.quality import CriticReport, JudgeVerdict
        from pydantic import TypeAdapter
    except ImportError as e:
        return [f"스키마 점검을 못 했다: {e}"]

    models = [
        MotifBatch, CompositionPlan, PhraseRealization,
        CriticReport, JudgeVerdict, Guide, TitleSuggestion,
    ]
    problems: list[str] = []
    for m in models:
        try:
            transform_schema(TypeAdapter(m).json_schema())
        except Exception as e:  # 무엇이 됐든 실제 호출을 막는다
            problems.append(f"{m.__name__}: {e}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
