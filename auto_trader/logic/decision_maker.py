"""합의 엔진 — AI 판단과 규칙 엔진 판정을 하나의 최종 행동으로 합친다.

구조는 **성격이 다른 두 검증**이다. AI(Claude)가 정성 판단을 하고, 규칙 엔진
(`logic/rule_engine.py`)이 정량 게이트를 맡는다. LLM 을 여럿 두는 합의보다
이쪽이 강한 이유는 rule_engine 모듈 문서에 적어 두었다 — 요점은 LLM 들끼리는
**틀리는 방식이 비슷해서** 서로를 걸러내지 못한다는 것이다.

| 상황 | 결과 |
|---|---|
| AI 가 하나라도 `ok=False` | HOLD. 단 보유 중 + (익절선 도달 또는 규칙 SELL) → REDUCE |
| **전원 BUY** + 규칙 거부권 | HOLD (거부권이 가점을 이긴다) |
| **전원 BUY** + 규칙 SELL | HOLD (정면 충돌 — 늘리지도 줄이지도 않는다) |
| **전원 BUY** + 전원 confidence ≥ 임계 + 규칙 BUY | STRONG_BUY |
| **전원 BUY** + (확신 부족 또는 규칙 중립) | BUY_SMALL (비중 절반) |
| **전원 SELL** | SELL_ALL (보유 시) |
| SELL 이 하나라도 섞임 | REDUCE (보유 시) / 미보유면 HOLD |
| AI 관망 + 규칙 SELL | REDUCE (보유 시) |
| 그 밖의 모든 조합 | HOLD |

두 가지 비대칭이 의도된 설계다.

**매수는 양쪽 동의, 매도는 한쪽만으로 성립.** 자산을 지키는 쪽으로 기울였다.

**규칙 엔진은 단독으로 매수하지 못한다.** 규칙이 BUY 라도 AI 가 동의하지 않으면
관망이다. 반대로 규칙은 단독으로 **매도**할 수 있다 — 보호 동작이 LLM 의 가용성에
묶여 있으면, 키가 거부되거나 쿼터가 소진된 날 손실을 그냥 안고 있게 된다.

`rules` 를 주지 않으면(=None) 규칙 게이트 없이 예전처럼 AI 합의만으로 판단한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from agents.schemas import AgentDecision
from config.loader import AiConfig, RiskConfig
from logic.rule_engine import RuleVerdict
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
    rules: RuleVerdict | None = None,
) -> FinalDecision:
    """참여한 AgentDecision 들 + 규칙 판정 → FinalDecision.

    Args:
        decisions: 이번 사이클에 참여한 AI 판단들. 최소 하나는 있어야 한다.
        holding: 현재 보유 중인지. 미보유면 매도 계열은 HOLD로 치환된다.
        take_profit: 익절선 도달 플래그. AI가 응답하지 않으면 절반 매도한다.
        rules: 규칙 엔진 판정. None 이면 규칙 게이트 없이 AI 합의만 본다.
    """
    decisions = list(decisions)
    if not decisions:
        # 판단 근거가 하나도 없으면 아무것도 하지 않는다.
        return _hold("판단 결과 없음 → 관망")

    # 규칙 엔진을 껐거나(evaluated=False) 주지 않았으면 게이트를 적용하지 않는다.
    gate = rules if (rules is not None and rules.evaluated) else None

    failed = [d.agent for d in decisions if not d.ok]
    if failed:
        names = ", ".join(LABELS.get(name, name) for name in failed)
        if take_profit and holding:
            logger.info("익절선 도달 + AI 미응답 → 절반 매도")
            return FinalDecision(
                action="REDUCE", weight_pct=0,
                reason="익절선 도달, AI 미응답 → 절반 매도", sell_ratio=REDUCE_RATIO,
            )
        # AI 가 죽어도 보호 동작은 계속되어야 한다. 규칙 엔진은 API 를 쓰지 않으므로
        # 키 거부·쿼터 소진과 무관하게 살아 있다 — 이탈 신호가 서 있으면 줄인다.
        if gate is not None and gate.action == "SELL" and holding:
            logger.info("AI 미응답 + 규칙 이탈 신호 → 절반 매도")
            return FinalDecision(
                action="REDUCE", weight_pct=0,
                reason=f"{names} 응답 불가, 규칙 이탈 신호({gate.reason}) → 절반 매도",
                sell_ratio=REDUCE_RATIO,
            )
        return _hold(f"{names} 응답 신뢰 불가 → 관망")

    actions = [d.action for d in decisions]
    summary = _summarize(decisions)
    count = len(decisions)

    # --- 전원 BUY --------------------------------------------------------- #
    if all(action == "BUY" for action in actions):
        # 규칙 거부권은 점수로 상쇄되지 않는다. AI 가 아무리 확신해도 과열·급등
        # 추격·유동성 부족 자리에는 들어가지 않는다.
        if gate is not None and gate.blocks_buy:
            return _hold(f"{summary} → 매수 합의이나 규칙 차단: {', '.join(gate.vetoes)}")
        if gate is not None and gate.action == "SELL":
            # 정면 충돌. 늘리지도 줄이지도 않는다 — 매수 신호를 근거로 팔지는 않는다.
            return _hold(f"{summary} → 매수 합의이나 규칙은 이탈 신호({gate.reason}) → 관망")

        average = sum(d.weight_pct for d in decisions) / count
        all_confident = min(d.confidence for d in decisions) >= ai.min_confidence
        rules_agree = gate is None or gate.action == "BUY"
        if all_confident and rules_agree:
            note = f" + {gate.reason}" if gate is not None else ""
            return FinalDecision(
                action="STRONG_BUY", weight_pct=int(min(average, risk.max_position_pct)),
                reason=f"{summary} → 매수 합의 (confidence ≥ {ai.min_confidence}){note}",
            )
        if not all_confident:
            short = f"확신 부족 (< {ai.min_confidence})"
        else:
            short = f"규칙 중립({gate.reason})" if gate is not None else "확신 부족"
        return FinalDecision(
            action="BUY_SMALL", weight_pct=int(min(average / 2, risk.max_position_pct)),
            reason=f"{summary} → 매수 합의이나 {short} → 절반 비중",
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

    # --- AI 는 관망이지만 규칙이 이탈 신호 --------------------------------- #
    # 규칙은 단독으로 매수하지 못하지만 단독으로 매도할 수는 있다. 최소 보유기간
    # 확인은 호출부(risk.check_sell)가 맡으므로 여기서 매 사이클 되팔릴 일은 없다.
    #
    # 단, BUY 표가 하나라도 섞여 있으면 줄이지 않는다. 전원 BUY + 규칙 SELL 을
    # '정면 충돌 → 관망' 으로 두면서 일부 BUY 는 매도하는 것은 기준이 어긋난다.
    # 매수 의견을 근거로 파는 셈이 되기 때문이다.
    if gate is not None and gate.action == "SELL" and holding and "BUY" not in actions:
        return FinalDecision(
            action="REDUCE", weight_pct=0,
            reason=f"{summary} → AI 관망이나 규칙 이탈 신호({gate.reason}) → 비중 축소",
            sell_ratio=REDUCE_RATIO,
        )

    # --- 나머지 (BUY/HOLD 혼재, 전원 HOLD) --------------------------------- #
    tail = f" / {gate.summary()}" if gate is not None else ""
    return _hold(f"{summary} → 합의 없음 → 관망{tail}")
