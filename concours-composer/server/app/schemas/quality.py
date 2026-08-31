"""비평·심사 결과 스키마 (§7.5, §6.13).

비평가와 작곡가는 서로 다른 프롬프트·별도 호출이며(절대 규칙 10), 비평 결과는
반드시 '마디 범위 + 구체적 지시' 형태여야 Stage 3 의 구간 재생성으로 되먹일 수 있다.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

MeasureRange = Annotated[list[int], Field(min_length=2, max_length=2)]

# §7.5 루브릭 10항목. 키 순서가 곧 리포트 표시 순서다.
RUBRIC: dict[str, str] = {
    "motif_development": "모티브의 기억성과 전개 — 단순 반복이 아닌 '발전'이 있는가",
    "form_clarity": "형식의 명료성 — 섹션 구분이 귀로 들리는가",
    "harmony": "화성 진행의 자연스러움과 종지의 확신",
    "voice_leading": "성부 진행 — 병행 5·8도 남발, 어색한 도약, 반주와 멜로디 충돌",
    "phrasing": "프레이즈 호흡과 균형",
    "climax_ending": "클라이맥스의 설득력과 마무리",
    "student_fit": "난이도 적절성·학생 강점 노출 — 이 학생이 돋보이는가",
    "competition_effect": "콩쿨 효과 — 첫 8마디 인상, 청중 관점의 재미",
    "notation": "기보 정합 — 임시표·이명동음·성부 배치가 읽기 좋은가",
    "originality": "독창성 — 참고 스타일을 닮되 특정 곡을 베낀 느낌이 없는가",
}


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measures: MeasureRange = Field(description="고칠 마디 범위 [시작, 끝]")
    issue: str = Field(description="무엇이 문제인가")
    instruction: str = Field(description="어떻게 고칠 것인가 — 작곡가가 그대로 실행할 수 있게")

    @model_validator(mode="after")
    def _ordered(self) -> RevisionRequest:
        if self.measures[1] < self.measures[0]:
            raise ValueError(f"마디 범위가 뒤집혔다: {self.measures}")
        return self


class RubricScores(BaseModel):
    """§7.5 루브릭 10항목. Structured Outputs 로 강제하려면 필드가 명시적이어야 한다
    (자유 키 dict 는 JSON Schema 로 고정할 수 없어 모델이 항목을 빠뜨린다)."""

    model_config = ConfigDict(extra="forbid")

    motif_development: float = Field(ge=0, le=10)
    form_clarity: float = Field(ge=0, le=10)
    harmony: float = Field(ge=0, le=10)
    voice_leading: float = Field(ge=0, le=10)
    phrasing: float = Field(ge=0, le=10)
    climax_ending: float = Field(ge=0, le=10)
    student_fit: float = Field(ge=0, le=10)
    competition_effect: float = Field(ge=0, le=10)
    notation: float = Field(ge=0, le=10)
    originality: float = Field(ge=0, le=10)

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.model_dump().items()}


class CriticReport(BaseModel):
    """§7.5 비평가 출력."""

    model_config = ConfigDict(extra="forbid")

    scores: RubricScores
    strengths: list[str] = Field(default_factory=list, max_length=4)
    revision_requests: list[RevisionRequest] = Field(default_factory=list)
    overall_comment: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> float:
        """10점 만점 평균. 문턱(기본 7.0)과 비교하는 값. 직렬화에도 포함된다 — 화면이 이 값을 쓴다."""
        d = self.scores.as_dict()
        return round(sum(d.values()) / len(d), 2)

    def weakest(self, n: int = 3) -> list[tuple[str, float]]:
        return sorted(self.scores.as_dict().items(), key=lambda kv: kv[1])[:n]


class JudgeVerdict(BaseModel):
    """모의 심사위원 1인의 채점(§6.13)."""

    model_config = ConfigDict(extra="forbid")

    persona: str
    accuracy: float = Field(ge=0, le=10, description="정확성 — 기보·연주 가능성")
    expression: float = Field(ge=0, le=10, description="표현")
    structure: float = Field(ge=0, le=10, description="구조·형식")
    difficulty_fit: float = Field(ge=0, le=10, description="난이도 적절성")
    impression: float = Field(ge=0, le=10, description="인상")
    comment: str = ""
    fix_in_score: list[str] = Field(default_factory=list, description="곡에서 고칠 점")
    fix_in_practice: list[str] = Field(default_factory=list, description="연습에서 보완할 점")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> float:
        return round(
            (self.accuracy + self.expression + self.structure + self.difficulty_fit + self.impression) / 5,
            2,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def persona_label(self) -> str:
        return {
            "technique": "테크닉 중시", "musicality": "음악성 중시", "structure": "구조·형식 중시",
        }.get(self.persona, self.persona)


class JudgePanel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdicts: list[JudgeVerdict] = Field(min_length=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average(self) -> float:
        return round(sum(v.total for v in self.verdicts) / len(self.verdicts), 2)

    def consensus_fixes(self) -> list[str]:
        """둘 이상의 심사위원이 같은 취지로 지적한 것 — 우선 고칠 것."""
        seen: dict[str, int] = {}
        for v in self.verdicts:
            for f in v.fix_in_score:
                key = f.strip()[:40]
                seen[key] = seen.get(key, 0) + 1
        return [k for k, n in sorted(seen.items(), key=lambda kv: -kv[1]) if n >= 2]


class QualityReport(BaseModel):
    """음악성 지표 + 비평 결과를 묶은 저장 단위(quality_reports 테이블)."""

    model_config = ConfigDict(extra="forbid")

    musicality: dict = Field(default_factory=dict)
    critic: dict | None = None
    revision_round: int = 0
    passed: bool = False
    threshold: float = 7.0
    combined_score: float = 0.0
    notes: list[str] = Field(default_factory=list)
