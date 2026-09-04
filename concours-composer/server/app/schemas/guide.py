"""§6.6 연주법 해설 스키마.

모든 지적에 **실제 존재하는 마디 번호**가 붙어야 한다 — 화면에서 카드를 누르면
그 마디로 커서가 점프하기 때문이다. 곡 밖을 가리키는 앵커는 검증에서 걸러낸다.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

MeasureRange = Annotated[list[int], Field(min_length=2, max_length=2)]


class GuideSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measures: MeasureRange
    title: str
    points: list[str] = Field(min_length=1, description="연주 요점")


class FingeringNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measure: int = Field(ge=1)
    note: str


class PracticeWeek(BaseModel):
    model_config = ConfigDict(extra="forbid")
    week: int = Field(ge=1, le=8)
    goal: str
    method: str
    metronome_bpm: int = Field(ge=30, le=240)


class MemorizationChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measures: MeasureRange
    cue: str = Field(description="기억 단서")


class Guide(BaseModel):
    """연주법 해설. WRITER_MODEL 이 만든다."""

    model_config = ConfigDict(extra="forbid")

    overview: str
    sections: list[GuideSection] = Field(min_length=1)
    fingering_notes: list[FingeringNote] = Field(default_factory=list)
    practice_plan: list[PracticeWeek] = Field(default_factory=list)
    competition_tips: list[str] = Field(default_factory=list)
    memorization_map: list[MemorizationChunk] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ranges_ordered(self) -> Guide:
        for s in self.sections:
            if s.measures[1] < s.measures[0]:
                raise ValueError(f"섹션 마디 범위가 뒤집혔다: {s.measures}")
        for c in self.memorization_map:
            if c.measures[1] < c.measures[0]:
                raise ValueError(f"암보 구획 범위가 뒤집혔다: {c.measures}")
        return self

    def invalid_anchors(self, total_measures: int) -> list[str]:
        """곡 밖을 가리키는 마디 참조. 비어 있어야 화면의 마디 점프가 전부 동작한다."""
        bad: list[str] = []
        for s in self.sections:
            if not (1 <= s.measures[0] <= s.measures[1] <= total_measures):
                bad.append(f"섹션 '{s.title}' {s.measures}")
        for f in self.fingering_notes:
            if not 1 <= f.measure <= total_measures:
                bad.append(f"운지 {f.measure}마디")
        for c in self.memorization_map:
            if not (1 <= c.measures[0] <= c.measures[1] <= total_measures):
                bad.append(f"암보 구획 {c.measures}")
        return bad


class TitleSuggestion(BaseModel):
    """§7.3 Stage 6 제목 확정."""

    model_config = ConfigDict(extra="forbid")
    candidates: list[str] = Field(min_length=1, max_length=5)
    recommended: str
    rationale: str = ""

    @model_validator(mode="after")
    def _recommended_is_a_candidate(self) -> TitleSuggestion:
        if self.recommended not in self.candidates:
            raise ValueError(f"추천 제목이 후보에 없다: {self.recommended!r} / {self.candidates}")
        return self
