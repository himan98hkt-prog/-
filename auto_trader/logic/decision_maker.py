"""합의 엔진 — 참여한 AI들의 판단을 하나의 최종 행동으로 합친다.

지시서 5-8 합의 매트릭스를 **참여 인원수와 무관하게** 성립하는 형태로 옮겼다.
Claude·Gemini 둘일 때는 원래 매트릭스와 결과가 완전히 같고, ChatGPT 를 더해
셋이 되면 매수 조건이 그만큼 엄격해진다(만장일치가 어려워지므로).

| 상황 | 결과 |
|---|---|
| 하나라도 `ok=False` | HOLD (절대 규칙 4) |
| **전원 BUY** + 전원 confidence ≥ 임계 | STRONG_BUY |
| **전원 BUY** (확신 부족) | BUY_SMALL (비중 절반) |
| **전원 SELL** | SELL_ALL (보유 시) |
| SELL 이 하나라도 섞임 | REDUCE (보유 시) / 미보유면 HOLD |
| 그 밖의 모든 조합 | HOLD |

매수는 만장일치를 요구하고 매도는 한 표만으로도 반응한다 — 자산을 지키는
쪽으로 기운 비대칭이 의도한 설계다.
"""

from __future__ import annotations

from collections.abc import Sequence
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


LABELS = {"claude": "Claude", "gemini": "Gemini", "chatgpt": "ChatGPT"}


def _summarize(decisions: Sequence[AgentDecision]) -> str:
    return " / ".join(
        f"{LABELS.get(d.agent, d.agent)} {d.action}({d.confidence:.2f})" for d in decisions
    )


def decide(
    decisions: Sequence[AgentDecision],
    holding: bool,
    risk: RiskConfig,
    ai: AiConfig,
    *,
    take_profit: bool = False,
) -> FinalDecision:
    """참여한 AgentDecision 들 → FinalDecision.

    Args:
        decisions: 이번 사이클에 참여한 판단들. 최소 하나는 있어야 한다.
        holding: 현재 보유 중인지. 미보유면 매도 계열은 HOLD로 치환된다.
        take_profit: 익절선 도달 플래그. AI가 응답하지 않으면 절반 매도한다.
    """
    decisions = list(decisions)
    if not decisions:
        # 판단 근거가 하나도 없으면 아무것도 하지 않는다.
        return _hold("판단 결과 없음 → 관망")

    failed = [d.agent for d in decisions if not d.ok]
    if failed:
        if take_profit and holding:
            logger.info("익절선 도달 + AI 미응답 → 절반 매도")
            return FinalDecision(
                action="REDUCE", weight_pct=0,
                reason="익절선 도달, AI 미응답 → 절반 매도", sell_ratio=REDUCE_RATIO,
            )
        names = ", ".join(LABELS.get(name, name) for name in failed)
        return _hold(f"{names} 응답 신뢰 불가 → 관망")

    actions = [d.action for d in decisions]
    summary = _summarize(decisions)
    count = len(decisions)

    # --- 전원 BUY --------------------------------------------------------- #
    if all(action == "BUY" for action in actions):
        average = sum(d.weight_pct for d in decisions) / count
        all_confident = min(d.confidence for d in decisions) >= ai.min_confidence
        if all_confident:
            return FinalDecision(
                action="STRONG_BUY", weight_pct=int(min(average, risk.max_position_pct)),
                reason=f"{summary} → 전원 매수 합의 (confidence ≥ {ai.min_confidence})",
            )
        return FinalDecision(
            action="BUY_SMALL", weight_pct=int(min(average / 2, risk.max_position_pct)),
            reason=f"{summary} → 매수 합의이나 확신 부족 (< {ai.min_confidence}) → 절반 비중",
        )

    # --- 전원 SELL -------------------------------------------------------- #
    if all(action == "SELL" for action in actions):
        if not holding:
            return _hold(f"{summary} → 전원 매도이나 미보유 → 관망")
        return FinalDecision(
            action="SELL_ALL", weight_pct=0,
            reason=f"{summary} → 전원 매도 합의 → 전량 매도", sell_ratio=1.0,
        )

    # --- SELL 이 섞임 (의견 불일치) ---------------------------------------- #
    if "SELL" in actions:
        return _reduce_or_hold(holding, f"{summary} → 매도 의견 존재 → 비중 축소")

    # --- 나머지 (BUY/HOLD 혼재, 전원 HOLD) --------------------------------- #
    return _hold(f"{summary} → 합의 없음 → 관망")
