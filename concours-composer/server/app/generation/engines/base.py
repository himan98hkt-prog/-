"""작곡 엔진 인터페이스.

§7.8 의 `SymbolicEngine` 확장 지점이기도 하다. 파이프라인은 이 Protocol 만 알고,
Claude 엔진인지 규칙 기반 스텁인지 신경 쓰지 않는다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.generation.context import ComposerContext
from app.schemas.music import CompositionPlan, Measure, MotifCandidate, PhraseRealization
from app.schemas.quality import CriticReport


class PhraseRequest:
    """Stage 3 한 번의 호출 입력. 프레이즈 하나 분량만 담는다."""

    def __init__(
        self,
        *,
        motif: MotifCandidate,
        plan: CompositionPlan,
        phrase_index: int,
        previous_measures: list[Measure],
        instruction: str = "",
    ) -> None:
        self.motif = motif
        self.plan = plan
        self.phrase_index = phrase_index
        self.previous_measures = previous_measures
        self.instruction = instruction

    @property
    def phrase(self):
        return self.plan.phrases()[self.phrase_index]

    @property
    def measure_range(self) -> tuple[int, int]:
        p = self.phrase
        return p.measures[0], p.measures[1]

    def harmony_for_range(self) -> list[tuple[int, str]]:
        lo, hi = self.measure_range
        return [(h.measure, h.roman) for h in self.plan.harmony if lo <= h.measure <= hi]

    def next_harmony(self) -> str | None:
        _lo, hi = self.measure_range
        after = [h for h in self.plan.harmony if h.measure == hi + 1]
        return after[0].roman if after else None


@runtime_checkable
class ComposerEngine(Protocol):
    name: str

    def motifs(self, ctx: ComposerContext, n: int, feedback: str = "") -> list[MotifCandidate]:
        """Stage 1 — 모티브 후보."""
        ...

    def plan(self, ctx: ComposerContext, motif: MotifCandidate) -> CompositionPlan:
        """Stage 2 — 설계도."""
        ...

    def realize_phrase(self, ctx: ComposerContext, req: PhraseRequest) -> PhraseRealization:
        """Stage 3 — 프레이즈 하나. 32마디를 한 번에 만들면 안 된다(절대 규칙 9)."""
        ...

    def critique(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, musicality: dict, warnings: list[str] | None = None,
    ) -> CriticReport:
        """Stage 5 — 비평. 작곡과 별도 호출·별도 프롬프트(절대 규칙 10).

        `warnings` 는 검증기의 소프트 규칙 위반(병행 5·8도, 첫 8마디, 종지)이다.
        코드가 잡아냈지만 저장을 막지는 않는 것들이라, 비평가가 보고 고치라고 해야
        실제로 고쳐진다.
        """
        ...
