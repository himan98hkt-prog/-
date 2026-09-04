"""**받아온 곡을 들인다** — 관문은 하나도 낮추지 않고.

대화창에서 만들어 온 곡을 프로그램 안으로 들이는 자리다. 여기서 지켜야 할 선이
하나 있다.

    **밖에서 온 곡이라고 검사를 건너뛰면 안 된다.**

그러면 이 프로그램이 "검증기를 통과한 곡만 저장한다"(절대 규칙 2) 고 말할 근거가
사라진다. 원장님이 파실 곡이고, 학원 원장이 사서 아이에게 시킬 곡이다. 손이 안 닿는
화음이 하나만 있어도 그 곡은 반품이다.

그래서 들어오는 곡도 API 로 만든 곡과 **똑같은 것**을 지난다:

    검증기 · 음악성 지표 9종 · 표절 n-gram · 난이도 계산 · 모의 심사 3인

다른 점은 **비평 점수를 밖에서 받는다**는 것뿐이다. 비평은 원래도 작곡과 다른 호출로
하던 일이라(절대 규칙 10) 구조가 바뀌지 않는다. 비평가가 API 대신 대화창에 있을 뿐이다.

비용은 0 이다. 여기서 API 를 한 번도 부르지 않는다.
"""
from __future__ import annotations

import logging
from typing import Any

from app.generation.context import ComposerContext
from app.generation.engines.base import PhraseRequest
from app.generation.pipeline import CompositionPipeline, CompositionResult
from app.schemas.music import CompositionPlan, Measure, MotifCandidate, PhraseRealization
from app.schemas.quality import CriticReport

log = logging.getLogger(__name__)


class HandoffEngine:
    """작곡은 하지 않는다. **밖에서 받아 온 비평만** 돌려준다.

    파이프라인의 뒤쪽 절반(`finish_edited`)은 비평가를 한 번 부른다. 그 자리에
    이것을 끼운다 — 대화창에서 이미 받아 둔 비평을 그대로 내놓는다. 네트워크도,
    돈도 쓰지 않는다.

    앞쪽 절반(모티브·설계·프레이즈)은 애초에 부르지 않는다. 그 일은 대화창에서
    이미 끝났다. 실수로 불리면 조용히 넘어가지 않고 **소리 내어 막는다** —
    여기서 곡을 만들기 시작하면 그것은 다른 곡이다.
    """

    name = "handoff"

    def __init__(self, critic: CriticReport) -> None:
        self._critic = critic
        self.ledger = None      # 돈을 쓰지 않으므로 적을 원장도 없다

    def critique(
        self,
        ctx: ComposerContext,           # noqa: ARG002 - ComposerEngine Protocol 시그니처를 지킨다
        measures: list[Measure],        # noqa: ARG002
        plan: CompositionPlan,          # noqa: ARG002
        motif: MotifCandidate,          # noqa: ARG002
        musicality: dict,               # noqa: ARG002
        warnings: list[str] | None = None,   # noqa: ARG002
    ) -> CriticReport:
        return self._critic

    # ── 아래는 부르면 안 되는 것들 ────────────────────────────────────────
    def motifs(
        self,
        ctx: ComposerContext,           # noqa: ARG002
        n: int,                         # noqa: ARG002
        feedback: str = "",             # noqa: ARG002
    ) -> list[MotifCandidate]:
        raise RuntimeError("받아온 곡을 들이는 중에는 작곡하지 않는다")

    def plan(
        self,
        ctx: ComposerContext,           # noqa: ARG002
        motif: MotifCandidate,          # noqa: ARG002
    ) -> CompositionPlan:
        raise RuntimeError("받아온 곡을 들이는 중에는 설계하지 않는다")

    def realize_phrase(
        self,
        ctx: ComposerContext,           # noqa: ARG002
        req: PhraseRequest,             # noqa: ARG002
    ) -> PhraseRealization:
        raise RuntimeError("받아온 곡을 들이는 중에는 프레이즈를 만들지 않는다")


def take_in(
    ctx: ComposerContext,
    *,
    measures: list[Measure],
    plan: CompositionPlan,
    motif: MotifCandidate,
    critic: CriticReport,
    title: str = "",
    corpus_ngrams: set[tuple[int, ...]] | None = None,
) -> CompositionResult:
    """받아온 마디를 **API 로 만든 곡과 똑같이** 채점·검증해 결과로 만든다.

    `finish_edited` 를 그대로 쓴다 — 원장님이 악보에서 음표를 직접 고치셨을 때
    지나는 길과 **같은 길**이다. 손으로 고친 곡에 쓰던 문을 그대로 쓰는 것이므로
    새 문을 뚫는 것이 아니다.
    """
    pipeline = CompositionPipeline(HandoffEngine(critic), progress=lambda *_: None)
    return pipeline.finish_edited(
        ctx, measures, plan, motif,
        rounds=0,
        notes=["대화창에서 작곡해 들여온 곡입니다 — API 비용 $0."],
        corpus_ngrams=corpus_ngrams,
        title=title,
    )


def numbering_problems(measures: list[Measure], plan: CompositionPlan) -> list[str]:
    """들이기 전에 **눈으로 보이는 것부터** 잡는다.

    검증기는 음악을 본다. 그 앞에서 걸러야 할 것이 따로 있다 — 마디 번호가 빠졌거나
    겹쳤거나, 설계도가 말한 마디 수와 실제가 다른 것. 이런 것을 검증기 오류로
    돌려주면 원장님은 무엇이 문제인지 알 수 없다.
    """
    out: list[str] = []
    if not measures:
        return ["마디가 하나도 없습니다"]
    nums = [m.number for m in measures]
    if len(set(nums)) != len(nums):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        out.append(f"마디 번호가 겹칩니다: {dup[:8]}")
    want = list(range(1, len(measures) + 1))
    if sorted(nums) != want:
        missing = sorted(set(want) - set(nums))
        if missing:
            out.append(f"마디 번호가 빠졌습니다(1부터 이어져야 합니다): {missing[:8]}")
    if plan.total_measures and plan.total_measures != len(measures):
        out.append(
            f"설계도는 {plan.total_measures}마디라고 하는데 실제로는 {len(measures)}마디입니다"
        )
    return out


def summarize(res: CompositionResult) -> dict[str, Any]:
    """화면에 그대로 보여 줄 요약."""
    return {
        "title": res.plan.title_candidates[0] if res.plan.title_candidates else "무제",
        "measures": len(res.measures),
        "key": res.plan.key,
        "meter": res.plan.meter,
        "tempo": res.plan.tempo,
        "difficulty": res.difficulty,
        "musicality": float(res.quality.musicality["score_10"]),
        "combined_score": res.quality.combined_score,
        "savable": res.savable,
        "draft": res.shown_as_draft,
    }
