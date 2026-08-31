"""학생·콩쿨·생성 요청 스키마. 하드 제약은 전부 여기서 나온다."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CompetitionResult = Literal["grand", "first", "second", "third", "honorable", "none"]


class MediaConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reels_public: bool = False
    show_full_name: bool = False


class HandSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_interval: int = Field(ge=2, le=15, description="편하게 닿는 최대 음정(도). 7 = 7도")

    @property
    def max_semitones(self) -> int:
        """도 단위 음정을 반음 상한으로. 장/단 구분 없이 넉넉한 쪽(장음정)을 쓴다."""
        table = {2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 8: 12, 9: 14, 10: 16, 11: 17, 12: 19}
        return table.get(self.max_interval, min(24, self.max_interval * 2))


class Student(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    birth_year: int | None = None
    grade: str = ""
    years_of_study: float = 0
    hand_span: HandSpan
    level: int = Field(ge=1, le=10)
    repertoire_done: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    tempo_comfort_max_bpm: int = Field(default=120, ge=30, le=240)
    reading_level: int = Field(default=5, ge=1, le=10)
    lowest_midi: int = Field(default=21, ge=21, le=108)
    highest_midi: int = Field(default=108, ge=21, le=108)
    notes: str = ""
    media_consent: MediaConsent = Field(default_factory=MediaConsent)

    def display_name(self) -> str:
        """동의가 없으면 마스킹한다 — 릴스 자막·프로그램북 공통 규칙(절대 규칙 7)."""
        if self.media_consent.show_full_name:
            return self.name
        if len(self.name) <= 1:
            return self.name
        if len(self.name) == 2:
            return self.name[0] + "○"
        return self.name[0] + "○" * (len(self.name) - 2) + self.name[-1]


class CompetitionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    organizer: str = ""
    year: int | None = None
    division: str = ""
    time_limit_sec: int | None = Field(default=None, gt=0)
    original_allowed: bool = True
    score_submission_rules: str = ""
    memorization_required: bool = False
    repeats_allowed: bool = True
    criteria_text: str = ""
    judge_notes: str = ""


class CompositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    student: Student
    competition: CompetitionProfile | None = None
    target_difficulty: float = Field(ge=1, le=10)
    mood: str = ""
    form: Literal["AB", "ABA", "rondo", "sonatina", "variations"] = "ABA"
    key_preference: list[str] = Field(default_factory=list)
    meter: str = "4/4"
    tempo: int = Field(default=100, ge=30, le=240)
    total_measures: int | None = Field(default=None, ge=8, le=200)
    reference_style_ids: list[str] = Field(default_factory=list)
    texture_options: list[str] = Field(default_factory=list)
    must_include: str = ""
    n_candidates: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def _competition_allows_original(self) -> CompositionRequest:
        # SPEC §6.13 / §13: 창작곡 불허 대회는 생성 자체를 막는다.
        if self.competition and not self.competition.original_allowed:
            raise ValueError(
                f"'{self.competition.name} {self.competition.division}' 은(는) 창작곡을 허용하지 않는다. "
                "콩쿨 프로필의 original_allowed 를 확인하라."
            )
        return self

    @property
    def time_limit_sec(self) -> int | None:
        return self.competition.time_limit_sec if self.competition else None
