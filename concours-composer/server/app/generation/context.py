"""Stage 0 — 스타일 컨텍스트 조립.

하드 제약(학생) + 소프트 선호 + 콩쿨 프로필 + 참고 StyleProfile + 학원 실전 데이터를
하나의 `ComposerContext` 로 모은다. 저작권곡 음표열 배제는 여기서 코드로 강제한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.generation.copyright_guard import CorpusEntry, assert_no_copyrighted_notes, sanitize_corpus
from app.schemas.student import CompetitionProfile, CompositionRequest, Student


@dataclass
class HardConstraints:
    """어기면 저장 불가인 것들. 검증기와 프롬프트가 같은 값을 본다."""

    max_span_semitones: int
    lowest_midi: int
    highest_midi: int
    max_tempo_bpm: int
    max_accidental_ratio: float
    time_limit_sec: int | None
    target_difficulty: float
    difficulty_min: float = 1.0
    difficulty_max: float = 10.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_span_semitones": self.max_span_semitones,
            "lowest_midi": self.lowest_midi,
            "highest_midi": self.highest_midi,
            "max_tempo_bpm": self.max_tempo_bpm,
            "max_accidental_ratio": self.max_accidental_ratio,
            "time_limit_sec": self.time_limit_sec,
            "target_difficulty": self.target_difficulty,
            "difficulty_feasible_range": [self.difficulty_min, self.difficulty_max],
        }


@dataclass
class ComposerContext:
    request: CompositionRequest
    student: Student
    competition: CompetitionProfile | None
    hard: HardConstraints
    style_context: list[dict[str, Any]] = field(default_factory=list)
    academy_data: str = ""   # §6.13 결과 학습 — 상위 입상곡 Plan 특성 요약
    corpus_entries: list[CorpusEntry] = field(default_factory=list)

    def prompt_payload(self) -> dict[str, Any]:
        """프롬프트에 넣는 JSON. 저작권 가드를 통과한 것만 나간다."""
        payload = {
            "student": {
                "level": self.student.level,
                "grade": self.student.grade,
                "years_of_study": self.student.years_of_study,
                "hand_span_interval": self.student.hand_span.max_interval,
                "strengths": self.student.strengths,
                "weaknesses": self.student.weaknesses,
                "repertoire_done": self.student.repertoire_done[:10],
                "reading_level": self.student.reading_level,
                "tempo_comfort_max_bpm": self.student.tempo_comfort_max_bpm,
                "notes": self.student.notes,
            },
            "request": {
                "mood": self.request.mood,
                "form": self.request.form,
                "key_preference": self.request.key_preference,
                "meter": self.request.meter,
                "tempo": self.request.tempo,
                "target_difficulty": self.request.target_difficulty,
                "texture_options": self.request.texture_options,
                "must_include": self.request.must_include,
                "total_measures": self.request.total_measures,
            },
            "competition": None,
            "constraints": self.hard.as_dict(),
            "style_context": self.style_context,
            "academy_data": self.academy_data,
        }
        if self.competition:
            payload["competition"] = {
                "name": self.competition.name,
                "division": self.competition.division,
                "time_limit_sec": self.competition.time_limit_sec,
                "memorization_required": self.competition.memorization_required,
                "repeats_allowed": self.competition.repeats_allowed,
                "criteria_text": self.competition.criteria_text[:2000],
                "judge_notes": self.competition.judge_notes[:1000],
            }
        # 최종 관문: 저작권곡 음표열이 한 조각이라도 섞였으면 여기서 터진다.
        assert_no_copyrighted_notes(payload, self.corpus_entries)
        return payload


def estimate_measures(request: CompositionRequest, meter: str, tempo: int) -> int:
    """제한 시간이 있으면 그 85% 를 목표로 마디 수를 정한다. 없으면 32마디."""
    if request.total_measures:
        return request.total_measures
    limit = request.time_limit_sec
    if not limit:
        return 32
    from music21 import meter as m21meter

    bar_ql = float(m21meter.TimeSignature(meter).barDuration.quarterLength)
    bar_sec = bar_ql * (60.0 / tempo)
    n = int((limit * 0.85) // bar_sec)
    # 프레이즈가 4마디 단위이므로 4의 배수로 내린다. 최소 16, 최대 96.
    return max(16, min(96, (n // 4) * 4))


class InfeasibleRequest(ValueError):
    """고정 파라미터(템포·조성·손 스팬)로는 목표 난이도를 만들 수 없다."""


def check_feasibility(request: CompositionRequest, hard: HardConstraints) -> str | None:
    """요청 단계에서 '만들 수 없는 주문'을 알린다. 생성에 시간을 쓰기 전에."""
    from app.analysis.difficulty import feasible_range

    feas = feasible_range(
        tempo=request.tempo,
        key_sig=(request.key_preference or ["C"])[0],
        max_span_semitones=request.student.hand_span.max_semitones,
        max_accidental_ratio=hard.max_accidental_ratio,
    )
    if feas.contains(request.target_difficulty):
        return None
    return feas.message(request.target_difficulty)


def build_context(
    request: CompositionRequest,
    *,
    corpus: list[CorpusEntry] | None = None,
    academy_data: str = "",
    max_accidental_ratio: float | None = None,
    strict_feasibility: bool = False,
) -> ComposerContext:
    s = request.student
    entries = corpus or []

    # 임시표 상한은 독보 수준에 연동한다 — 읽기 어려우면 학생이 못 친다.
    acc_ratio = max_accidental_ratio if max_accidental_ratio is not None else min(
        0.30, 0.05 + s.reading_level * 0.025
    )

    from app.analysis.difficulty import feasible_range

    feas = feasible_range(
        tempo=request.tempo,
        key_sig=(request.key_preference or ["C"])[0],
        max_span_semitones=s.hand_span.max_semitones,
        max_accidental_ratio=acc_ratio,
    )

    hard = HardConstraints(
        difficulty_min=feas.min_score,
        difficulty_max=feas.max_score,
        max_span_semitones=s.hand_span.max_semitones,
        lowest_midi=s.lowest_midi,
        highest_midi=s.highest_midi,
        max_tempo_bpm=s.tempo_comfort_max_bpm,
        max_accidental_ratio=round(acc_ratio, 3),
        time_limit_sec=request.time_limit_sec,
        target_difficulty=request.target_difficulty,
    )

    if strict_feasibility:
        problem = check_feasibility(request, hard)
        if problem:
            raise InfeasibleRequest(problem)

    return ComposerContext(
        request=request,
        student=s,
        competition=request.competition,
        hard=hard,
        style_context=sanitize_corpus(entries),
        academy_data=academy_data,
        corpus_entries=entries,
    )
