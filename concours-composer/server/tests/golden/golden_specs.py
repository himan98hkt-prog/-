"""골든 요청 20건과 컨텍스트 생성기."""
from __future__ import annotations

import json
from pathlib import Path

from app.generation.context import build_context
from app.schemas.student import CompetitionProfile, CompositionRequest, HandSpan, Student

GOLDEN = json.loads((Path(__file__).parent / "requests.json").read_text(encoding="utf-8"))


def make_context(spec: dict):
    student = Student(
        id=f"student-{spec['id']}", name="학생", grade=spec["grade"],
        hand_span=HandSpan(max_interval=spec["span"]), level=spec["level"],
        strengths=spec["strengths"], weaknesses=spec["weaknesses"],
        tempo_comfort_max_bpm=spec["comfort"], reading_level=min(10, spec["level"] + 1),
        lowest_midi=36, highest_midi=96,
    )
    comp = CompetitionProfile(
        id=f"comp-{spec['id']}", name="골든 콩쿨", division=spec["grade"],
        time_limit_sec=spec["limit"], original_allowed=True,
    )
    req = CompositionRequest(
        id=spec["id"], student=student, competition=comp,
        target_difficulty=spec["difficulty"], mood=spec["mood"],
        form=spec.get("form", "ABA"), key_preference=[spec["key"]],
        meter=spec["meter"], tempo=spec["tempo"],
    )
    return build_context(req)


