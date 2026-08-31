"""원장 피드백 (§8 teacher_feedback).

지금은 **모으기만** 한다. 가중치 보정(§7.4 WEIGHTS, §7.7 난이도 회귀)은 데이터가
쌓인 뒤 M8 에서 한다 — 표본 몇 개로 가중치를 흔들면 오히려 나빠진다.

그래서 이 스키마의 목적은 하나다: **나중에 회귀에 쓸 수 있는 형태로 남기는 것**.
- `thumbs` 만으로는 왜 좋은지 모른다 → `reason_tags` 를 지표 이름과 맞춰 둔다.
- 어느 버전에 대한 평가인지 모르면 쓸모없다 → `composition_id` 를 반드시 받는다.
- 그때의 지표·비평 점수를 함께 스냅샷해 둬야 나중에 상관을 계산할 수 있다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Thumbs = Literal["up", "down"]

# 이유 태그는 음악성 지표(§7.4)·비평 루브릭(§7.5) 이름과 **일부러** 겹쳐 둔다.
# 나중에 "원장이 down 을 준 곡은 어떤 지표가 낮았나" 를 바로 대조할 수 있다.
REASON_TAGS: dict[str, str] = {
    "motif": "모티브가 약하다 / 좋다",
    "form": "형식이 안 들린다 / 잘 들린다",
    "harmony": "화성이 어색하다 / 자연스럽다",
    "phrasing": "프레이즈 호흡이 이상하다 / 좋다",
    "climax": "클라이맥스가 밋밋하다 / 설득력 있다",
    "difficulty_too_hard": "학생에게 어렵다",
    "difficulty_too_easy": "학생에게 쉽다",
    "student_fit": "학생 강점이 안 드러난다 / 잘 드러난다",
    "competition_fit": "콩쿨에서 안 통한다 / 통한다",
    "notation": "읽기 불편하다 / 편하다",
    "length": "길이가 안 맞는다",
    "boring": "밋밋하다",
    "disjointed": "앞뒤가 따로 논다",
}


class TeacherFeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    composition_id: str
    thumbs: Thumbs
    reason_tags: list[str] = Field(default_factory=list)
    comment: str = ""
    would_use_without_edit: bool | None = Field(
        default=None,
        description="수정 없이 바로 쓸 수 있는가. SPEC §1.2 의 핵심 지표(v1 60%, v2 80%)",
    )
    edited_measures: list[int] = Field(
        default_factory=list, description="실제로 손댄 마디. 어디가 약한지 가장 정직한 신호다"
    )


class TeacherFeedback(TeacherFeedbackIn):
    """저장 형태. 평가 시점의 지표를 함께 얼려 둔다."""

    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # 평가 당시의 점수 스냅샷 — 나중에 회귀할 때 이것이 없으면 대조가 불가능하다.
    musicality_snapshot: dict = Field(default_factory=dict)
    critic_snapshot: dict = Field(default_factory=dict)
    difficulty_snapshot: float | None = None
    difficulty_target: float | None = None
    engine: str = ""


class FeedbackStats(BaseModel):
    """M8 가중치 보정에 들어갈 재료. 지금은 보여 주기만 한다."""

    model_config = ConfigDict(extra="forbid")

    total: int = 0
    up: int = 0
    down: int = 0
    usable_without_edit: int = 0
    usable_rate: float | None = Field(
        default=None, description="SPEC §1.2 '수정 없이 사용' 비율. 목표 v1 60%"
    )
    tag_counts: dict[str, int] = Field(default_factory=dict)
    ready_for_recalibration: bool = Field(
        default=False, description="가중치 보정을 시작해도 되는 표본 수에 도달했는가"
    )
    min_samples: int = 30
    note: str = ""
