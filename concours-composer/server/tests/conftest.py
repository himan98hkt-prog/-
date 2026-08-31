from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from app.generation.context import ComposerContext, build_context  # noqa: E402
from app.generation.engines.stub import StubComposerEngine  # noqa: E402
from app.generation.pipeline import CompositionPipeline  # noqa: E402
from app.schemas.music import Measure, ScoreEvent, Voice  # noqa: E402
from app.schemas.student import (  # noqa: E402
    CompetitionProfile,
    CompositionRequest,
    HandSpan,
    Student,
)


@pytest.fixture
def student() -> Student:
    return Student(
        id="s1", name="김민준", grade="초3", years_of_study=2.5,
        hand_span=HandSpan(max_interval=7), level=4,
        strengths=["빠른 손가락"], weaknesses=["옥타브"],
        tempo_comfort_max_bpm=112, reading_level=5,
        lowest_midi=36, highest_midi=93,
    )


@pytest.fixture
def competition() -> CompetitionProfile:
    return CompetitionProfile(
        id="c1", name="OO음악콩쿨", organizer="OO문화재단", year=2026,
        division="초등 저학년부", time_limit_sec=150, original_allowed=True,
        memorization_required=True, repeats_allowed=True,
    )


@pytest.fixture
def request_obj(student: Student, competition: CompetitionProfile) -> CompositionRequest:
    return CompositionRequest(
        id="r1", student=student, competition=competition, target_difficulty=4.0,
        mood="밝고 활기찬", form="ABA", key_preference=["A"], meter="4/4", tempo=104,
    )


@pytest.fixture
def ctx(request_obj: CompositionRequest) -> ComposerContext:
    return build_context(request_obj)


@pytest.fixture
def engine() -> StubComposerEngine:
    return StubComposerEngine()


@pytest.fixture
def pipeline(engine: StubComposerEngine) -> CompositionPipeline:
    return CompositionPipeline(engine, progress=lambda *_: None)
