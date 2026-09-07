"""합의 엔진 — 두 AI의 판단을 하나의 최종 행동으로 합친다.

지시서 5-8 합의 매트릭스를 그대로 구현한다.

| Claude \\ Gemini | BUY                              | HOLD              | SELL              |
|---|---|---|---|
| **BUY**  | STRONG_BUY (둘 다 confidence ≥ 임계) / 아니면 BUY_SMALL | HOLD | HOLD (보유 시 REDUCE) |
| **HOLD** | HOLD                             | HOLD              | HOLD (보유 시 REDUCE) |
| **SELL** | HOLD (보유 시 REDUCE)             | HOLD (보유 시 REDUCE) | SELL_ALL (보유 시) |

- 한쪽이라도 `ok=False` 면 무조건 HOLD (절대 규칙 4).
- 미보유 종목의 SELL/REDUCE는 HOLD로 치환한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.schemas import AgentDecision
from config.loader import AiConfig, RiskConfig
from utils.logger import get_logger

logger = get_logger("decision_maker")

FinalAction = Literal["STRONG_BUY", "BUY_SMALL", "HOLD", "REDUCE", "SELL_ALL"]

BUY_ACTIONS: frozenset[str] = frozenset({"STRONG_BUY", "BUY_SMALL"})
SELL_ACTIONS: frozenset[str] = frozenset({"REDUCE", "SELL_ALL"})

REDUCE_RATIO = 0.5  # REDUCE = 보유수량의 50% 매도


@dataclass
class FinalDecision:
    action: FinalAction
    weight_pct: int = 0  # 매수 시 총액 대비 목표 비중
    reason: str = ""
    sell_ratio: float = 0.0  # 매도 시 보유수량 대비 비율 (REDUCE 0.5 / SELL_ALL 1.0)

    @property
    def is_buy(self) -> bool:
        return self.action in BUY_ACTIONS

    @property
    def is_sell(self) -> bool:
        return self.action in SELL_ACTIONS


def _hold(reason: str) -> FinalDecision:
    return FinalDecision(action="HOLD", weight_pct=0, reason=reason, sell_ratio=0.0)


def _reduce_or_hold(holding: bool, reason: str) -> FinalDecision:
    """매도 성향이지만 합의에 이르지 못한 경우 — 보유 중이면 절반 축소."""
    if not holding:
        return _hold(f"{reason} (미보유 → 관망)")
    return FinalDecision(action="REDUCE", weight_pct=0, reason=reason, sell_ratio=REDUCE_RATIO)


def decide(
    claude: AgentDecision,
    gemini: AgentDecision,
    holding: bool,
    risk: RiskConfig,
    ai: AiConfig,
    *,
    take_profit: bool = False,
) -> FinalDecision:
    """두 AgentDecision → FinalDecision.

    Args:
        holding: 현재 보유 중인지. 미보유면 매도 계열은 HOLD로 치환된다.
        take_profit: 익절선 도달 플래그. AI가 응답하지 않으면 절반 매도한다.
    """
    if not claude.ok or not gemini.ok:
        failed = [d.agent for d in (claude, gemini) if not d.ok]
        reason = f"{', '.join(failed)} 응답 신뢰 불가 → 관망"
        if take_profit and holding:
            logger.info("익절선 도달 + AI 미응답 → 절반 매도")
            return FinalDecision(
                action="REDUCE", weight_pct=0,
                reason="익절선 도달, AI 미응답 → 절반 매도", sell_ratio=REDUCE_RATIO,
            )
        return _hold(reason)

    verdict = (claude.action, gemini.action)
    summary = f"Claude {claude.action}({claude.confidence:.2f}) / Gemini {gemini.action}({gemini.confidence:.2f})"

    # --- 양쪽 BUY --------------------------------------------------------- #
    if verdict == ("BUY", "BUY"):
        average = (claude.weight_pct + gemini.weight_pct) / 2
        both_confident = min(claude.confidence, gemini.confidence) >= ai.min_confidence
        if both_confident:
            weight = min(average, risk.max_position_pct)
            return FinalDecision(
                action="STRONG_BUY", weight_pct=int(weight),
                reason=f"{summary} → 양쪽 매수 합의 (confidence ≥ {ai.min_confidence})",
            )
        weight = min(average / 2, risk.max_position_pct)
        return FinalDecision(
            action="BUY_SMALL", weight_pct=int(weight),
            reason=f"{summary} → 매수 합의이나 확신 부족 (< {ai.min_confidence}) → 절반 비중",
        )

    # --- 양쪽 SELL -------------------------------------------------------- #
    if verdict == ("SELL", "SELL"):
        if not holding:
            return _hold(f"{summary} → 양쪽 매도이나 미보유 → 관망")
        return FinalDecision(
            action="SELL_ALL", weight_pct=0,
            reason=f"{summary} → 양쪽 매도 합의 → 전량 매도", sell_ratio=1.0,
        )

    # --- 한쪽만 SELL (의견 불일치) ----------------------------------------- #
    if "SELL" in verdict:
        return _reduce_or_hold(holding, f"{summary} → 매도 의견 존재 → 비중 축소")

    # --- 나머지 (BUY/HOLD, HOLD/BUY, HOLD/HOLD) ---------------------------- #
    return _hold(f"{summary} → 합의 없음 → 관망")
