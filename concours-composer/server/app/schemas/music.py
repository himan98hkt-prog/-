"""악보·연주 데이터의 공용 스키마.

SoT 두 개(CLAUDE.md):
- 작곡 축: MusicXML (이 모듈의 JSON → music21 → MusicXML)
- 시각화 축: NoteEvents JSON (`NoteEvent`)

절대 규칙 1에 따라 LLM 은 여기 정의된 JSON 만 출력하고, MusicXML 문자열은
절대 만들지 않는다.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Hand = Literal["L", "R"]
Staff = Literal[1, 2]  # 1 = 오른손(높은음자리), 2 = 왼손

# ── 시각화 축 SoT ────────────────────────────────────────────────────────────


class PedalSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    onset: float = Field(ge=0)
    offset: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> PedalSpan:
        if self.offset <= self.onset:
            raise ValueError("페달 offset 은 onset 보다 커야 한다")
        return self


class NoteEvent(BaseModel):
    """초 단위 절대 시간 노트. MIDI·MusicXML·채보 결과를 모두 이 형식으로 정규화."""

    model_config = ConfigDict(extra="forbid")

    onset: float = Field(ge=0, description="초")
    offset: float = Field(gt=0, description="초")
    pitch: int = Field(ge=21, le=108, description="MIDI 노트 번호(88건반)")
    velocity: int = Field(ge=1, le=127, default=80)
    hand: Hand | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> NoteEvent:
        if self.offset <= self.onset:
            raise ValueError(f"offset({self.offset}) 은 onset({self.onset}) 보다 커야 한다")
        return self

    @property
    def duration(self) -> float:
        return self.offset - self.onset


class NoteEvents(BaseModel):
    """시각화·하이라이트·채보가 공유하는 정규화 컨테이너."""

    model_config = ConfigDict(extra="forbid")

    notes: list[NoteEvent] = Field(default_factory=list)
    pedal: list[PedalSpan] = Field(default_factory=list)
    tempo_bpm: float | None = Field(default=None, gt=0)
    meter: str | None = None
    source: Literal["composition", "transcription", "midi"] = "composition"
    engine: str | None = None

    @property
    def duration(self) -> float:
        return max((n.offset for n in self.notes), default=0.0)

    def sorted_notes(self) -> list[NoteEvent]:
        return sorted(self.notes, key=lambda n: (n.onset, n.pitch))


# ── 작곡 축: LLM 이 출력하는 구조화 JSON ────────────────────────────────────

Articulation = Literal["staccato", "accent", "tenuto", "marcato", "none"]


def _nullable_choice(schema: dict[str, object]) -> None:
    """`Literal[..., None]` 이 만드는 **type 없는 enum** 을 anyOf 로 바꾼다.

    이것이 없으면 실제 Claude 호출이 네트워크에 닿기도 전에 죽는다. pydantic 은
    `Literal["start", "stop", None]` 을 `{"enum": ["start", "stop", null]}` 로 내놓는데,
    거기에는 `type` 이 없다. Anthropic SDK 는 Structured Outputs 스키마를 보내기 직전에
    변환하면서 type/anyOf/oneOf/allOf 가 하나도 없는 자리를 거부한다 —
    `ValueError: Schema must have a 'type', 'anyOf', 'oneOf', or 'allOf' field.`

    그 예외는 SDK 예외가 아니라서 한국어 안내로도 안 바뀌고, 화면에는 `{}` 만 남는다.
    음표를 만드는 모든 단계(모티브·프레이즈 실현)가 이 스키마를 쓰므로, 키를 넣는
    순간부터 곡이 **한 곡도** 만들어지지 않는다. 스텁 엔진은 API 를 안 부르니 조용했다.
    """
    raw = schema.pop("enum", [])
    values = [v for v in raw if v is not None] if isinstance(raw, list) else []
    schema.pop("type", None)
    schema["anyOf"] = [{"type": "string", "enum": values}, {"type": "null"}]


# 붙임줄·이음줄은 "없음" 이 정상 상태다. 그래서 None 을 품은 채로 스키마가 성립해야 한다.
Tie = Annotated[
    Literal["start", "stop", "continue", None], Field(json_schema_extra=_nullable_choice)
]
Slur = Annotated[Literal["start", "stop", None], Field(json_schema_extra=_nullable_choice)]

Dynamic = Literal["ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"]


class ScoreEvent(BaseModel):
    """한 성부의 한 시점. `pitches` 가 비면 쉼표."""

    model_config = ConfigDict(extra="forbid")

    dur: float = Field(gt=0, description="4분음표 = 1.0 인 길이")
    pitches: list[str] = Field(default_factory=list, description='["C4","E4"] 형식. 빈 배열 = 쉼표')
    tie: Tie = None
    artic: Articulation = "none"
    slur: Slur = None

    @field_validator("pitches")
    @classmethod
    def _pitch_names(cls, v: list[str]) -> list[str]:
        for p in v:
            if not p or p[0].upper() not in "ABCDEFG":
                raise ValueError(f"잘못된 음이름: {p!r}")
        return v

    @property
    def is_rest(self) -> bool:
        return not self.pitches


class Voice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: int = Field(default=1, ge=1, le=4)
    events: list[ScoreEvent] = Field(min_length=1)

    @property
    def total_dur(self) -> float:
        return sum(e.dur for e in self.events)


class Measure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int = Field(ge=1)
    rh: list[Voice] = Field(default_factory=list)
    lh: list[Voice] = Field(default_factory=list)
    dynamics: Dynamic | None = None
    text: str | None = None
    pedal: bool = False

    def all_pitches(self) -> list[str]:
        out: list[str] = []
        for v in (*self.rh, *self.lh):
            for e in v.events:
                out.extend(e.pitches)
        return out


class PhraseRealization(BaseModel):
    """Stage 3 출력 — 프레이즈(보통 4마디) 단위."""

    model_config = ConfigDict(extra="forbid")
    measures: list[Measure] = Field(min_length=1)


# ── 모티브 ───────────────────────────────────────────────────────────────────


class MotifSource(StrEnum):
    ai = "ai"
    drawn = "drawn"
    transcribed = "transcribed"


class MotifCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    measures: list[Measure] = Field(min_length=2, max_length=4)
    key: str
    meter: str
    tempo: int = Field(ge=30, le=240)
    character_label: str
    why_it_works: str = ""
    source: MotifSource = MotifSource.ai
    selected: bool = False

    def head_intervals(self) -> list[int]:
        """모티브 머리(오른손 첫 마디)의 음정열 — 모티브 일관성 지표의 기준."""
        from app.analysis.pitch import pitch_to_midi  # 지역 import: 순환 방지

        seq: list[int] = []
        for m in self.measures:
            for v in m.rh:
                for e in v.events:
                    if e.pitches:
                        seq.append(pitch_to_midi(e.pitches[-1]))
        return [b - a for a, b in zip(seq, seq[1:], strict=False)]

    def head_rhythm(self) -> list[float]:
        out: list[float] = []
        for m in self.measures:
            for v in m.rh:
                out.extend(e.dur for e in v.events)
        return out


# ── Plan ─────────────────────────────────────────────────────────────────────

MotifTreatment = Literal[
    "statement", "repeat", "sequence_up_2nd", "sequence_down_3rd", "inversion",
    "retrograde", "augmentation", "diminution", "fragment_head", "fragment_tail",
    "transpose_to_dominant", "mode_change", "texture_swap", "octave_shift",
    "rhythmic_variation",
]

MeasureRange = Annotated[list[int], Field(min_length=2, max_length=2)]

# 한 번의 Realize 호출이 만들 수 있는 최대 마디 수(CLAUDE.md 절대 규칙 9).
# 프레이즈는 2~8마디다 — 4마디로 고정하면 여섯 프레이즈가 전부 같은 길이인
# 곡만 나온다. 분절(2마디)과 확장(6마디)이 있어야 형식이 말을 한다.
MAX_PHRASE_MEASURES = 8
MIN_PHRASE_MEASURES = 2


class PhrasePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measures: MeasureRange
    motif_treatment: MotifTreatment
    texture_rh: str
    texture_lh: str
    dynamic: Dynamic = "mf"


class SectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    measures: MeasureRange
    phrases: list[PhrasePlan] = Field(min_length=1)


class HarmonyStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measure: int = Field(ge=1)
    roman: str
    bass_note: str | None = None


class Climax(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measure: int = Field(ge=1)
    how: str


class Showcase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    range: MeasureRange
    strength_used: str


class Ending(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    measures: MeasureRange


class DynamicPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measure: int = Field(ge=1)
    dyn: Dynamic


class CompositionPlan(BaseModel):
    """Stage 2 출력. 원장 승인 후에만 Realize 로 넘어간다."""

    model_config = ConfigDict(extra="forbid")

    title_candidates: list[str] = Field(default_factory=list)
    key: str
    meter: str
    tempo: int = Field(ge=30, le=240)
    total_measures: int = Field(ge=8, le=200)
    duration_est: float = Field(gt=0, description="초")
    form: list[SectionPlan] = Field(min_length=1)
    harmony: list[HarmonyStep] = Field(default_factory=list)
    climax: Climax
    showcase_measures: list[Showcase] = Field(default_factory=list)
    contrast_section: dict[str, str] | None = None
    modulations: list[str] = Field(default_factory=list)
    ending: Ending
    dynamics_curve: list[DynamicPoint] = Field(default_factory=list)
    pedal_plan: str = ""
    difficulty_target: float = Field(ge=1, le=10)

    def phrases(self) -> list[PhrasePlan]:
        return [p for s in self.form for p in s.phrases]

    def section_of(self, measure: int) -> SectionPlan | None:
        for s in self.form:
            if s.measures[0] <= measure <= s.measures[1]:
                return s
        return None
