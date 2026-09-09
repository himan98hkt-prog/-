"""합의 매트릭스 테스트 — 지시서 5-8 표 9칸 전부 + ok=False + 미보유 SELL."""

from __future__ import annotations

import itertools

import pytest

from agents.schemas import AgentDecision
from config.loader import AiConfig, RiskConfig
from logic.decision_maker import FinalDecision, decide

AI = AiConfig(timeout_sec=60, max_retries=2, min_confidence=0.6,
              news_max_items=5, news_lookback_hours=24)

RISK = RiskConfig(
    total_investment_cap_krw=5_000_000, max_position_pct=20, max_positions=5,
    daily_loss_limit_pct=3, stop_loss_pct=-5, take_profit_pct=10,
    min_order_krw=100_000, order_type="market", limit_slippage_pct=0.3,
)


def agent(name: str, action: str, confidence: float = 0.8, weight: int = 20, ok: bool = True):
    return AgentDecision(agent=name, action=action, confidence=confidence, weight_pct=weight,
                         reason="테스트", ok=ok)


def run(claude_action, gemini_action, holding=False, *, conf=0.8, weight=20, take_profit=False):
    return decide([agent("claude", claude_action, conf, weight), agent("gemini", gemini_action, conf, weight)], holding, RISK, AI, take_profit=take_profit)


# --------------------------------------------------------------------------- #
# 매트릭스 9칸 — 미보유
# --------------------------------------------------------------------------- #

MATRIX_NOT_HOLDING = {
    ("BUY", "BUY"): "STRONG_BUY",
    ("BUY", "HOLD"): "HOLD",
    ("BUY", "SELL"): "HOLD",
    ("HOLD", "BUY"): "HOLD",
    ("HOLD", "HOLD"): "HOLD",
    ("HOLD", "SELL"): "HOLD",
    ("SELL", "BUY"): "HOLD",
    ("SELL", "HOLD"): "HOLD",
    ("SELL", "SELL"): "HOLD",  # 미보유이므로 SELL_ALL 이 아니다
}

MATRIX_HOLDING = {
    ("BUY", "BUY"): "STRONG_BUY",
    ("BUY", "HOLD"): "HOLD",
    ("BUY", "SELL"): "REDUCE",
    ("HOLD", "BUY"): "HOLD",
    ("HOLD", "HOLD"): "HOLD",
    ("HOLD", "SELL"): "REDUCE",
    ("SELL", "BUY"): "REDUCE",
    ("SELL", "HOLD"): "REDUCE",
    ("SELL", "SELL"): "SELL_ALL",
}


@pytest.mark.parametrize("cell,expected", sorted(MATRIX_NOT_HOLDING.items()))
def test_matrix_when_not_holding(cell, expected):
    assert run(*cell, holding=False).action == expected


@pytest.mark.parametrize("cell,expected", sorted(MATRIX_HOLDING.items()))
def test_matrix_when_holding(cell, expected):
    assert run(*cell, holding=True).action == expected


def test_matrix_covers_all_nine_combinations():
    combos = set(itertools.product(["BUY", "HOLD", "SELL"], repeat=2))
    assert set(MATRIX_NOT_HOLDING) == combos and set(MATRIX_HOLDING) == combos
    assert len(combos) == 9


# --------------------------------------------------------------------------- #
# STRONG_BUY / BUY_SMALL 경계
# --------------------------------------------------------------------------- #


def test_strong_buy_requires_both_above_min_confidence():
    assert run("BUY", "BUY", conf=0.6).action == "STRONG_BUY", "임계값과 같으면 인정"
    assert run("BUY", "BUY", conf=0.59).action == "BUY_SMALL"


def test_buy_small_when_only_one_agent_is_confident():
    decision = decide([agent("claude", "BUY", 0.9, 20), agent("gemini", "BUY", 0.4, 20)], False, RISK, AI)
    assert decision.action == "BUY_SMALL", "한쪽만 확신하면 절반 비중"


def test_strong_buy_weight_is_average():
    decision = decide([agent("claude", "BUY", 0.8, 10), agent("gemini", "BUY", 0.8, 16)], False, RISK, AI)
    assert decision.action == "STRONG_BUY" and decision.weight_pct == 13


def test_buy_small_weight_is_half_of_average():
    decision = decide([agent("claude", "BUY", 0.5, 10), agent("gemini", "BUY", 0.5, 16)], False, RISK, AI)
    assert decision.action == "BUY_SMALL" and decision.weight_pct == 6


def test_weight_capped_by_max_position_pct():
    decision = decide([agent("claude", "BUY", 0.9, 100), agent("gemini", "BUY", 0.9, 100)], False, RISK, AI)
    assert decision.weight_pct == RISK.max_position_pct == 20


# --------------------------------------------------------------------------- #
# 매도 비율
# --------------------------------------------------------------------------- #


def test_sell_all_ratio_is_full():
    decision = run("SELL", "SELL", holding=True)
    assert decision.action == "SELL_ALL" and decision.sell_ratio == 1.0
    assert decision.is_sell and not decision.is_buy


def test_reduce_ratio_is_half():
    decision = run("SELL", "HOLD", holding=True)
    assert decision.action == "REDUCE" and decision.sell_ratio == 0.5


def test_buy_actions_have_no_sell_ratio():
    assert run("BUY", "BUY").sell_ratio == 0.0


# --------------------------------------------------------------------------- #
# ok=False → 무조건 HOLD
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("holding", [True, False])
@pytest.mark.parametrize(
    "claude_ok,gemini_ok", [(False, True), (True, False), (False, False)]
)
def test_any_parse_failure_forces_hold(claude_ok, gemini_ok, holding):
    decision = decide([agent("claude", "BUY", ok=claude_ok), agent("gemini", "BUY", ok=gemini_ok)], holding, RISK, AI)
    assert decision.action == "HOLD"
    assert decision.weight_pct == 0
    assert "신뢰 불가" in decision.reason


def test_parse_failure_beats_unanimous_sell():
    decision = decide([agent("claude", "SELL", ok=False), agent("gemini", "SELL")], True, RISK, AI)
    assert decision.action == "HOLD", "판단을 신뢰할 수 없으면 매도도 하지 않는다"


# --------------------------------------------------------------------------- #
# 익절 플래그
# --------------------------------------------------------------------------- #


def test_take_profit_without_ai_response_sells_half():
    decision = decide([agent("claude", "HOLD", ok=False), agent("gemini", "HOLD", ok=False)], True, RISK, AI, take_profit=True)
    assert decision.action == "REDUCE" and decision.sell_ratio == 0.5
    assert "익절선" in decision.reason


def test_take_profit_without_holding_stays_hold():
    decision = decide([agent("claude", "HOLD", ok=False), agent("gemini", "HOLD", ok=False)], False, RISK, AI, take_profit=True)
    assert decision.action == "HOLD"


def test_take_profit_follows_ai_when_they_respond():
    decision = decide([agent("claude", "BUY", 0.9), agent("gemini", "BUY", 0.9)], True, RISK, AI, take_profit=True)
    assert decision.action == "STRONG_BUY", "AI가 응답하면 그 판단을 따른다"


# --------------------------------------------------------------------------- #
# 기타
# --------------------------------------------------------------------------- #


def test_reason_mentions_both_agents():
    reason = run("BUY", "HOLD").reason
    assert "Claude BUY" in reason and "Gemini HOLD" in reason


def test_not_holding_sell_reason_explains_substitution():
    assert "미보유" in run("SELL", "SELL", holding=False).reason


def test_final_decision_flags():
    assert FinalDecision(action="STRONG_BUY").is_buy
    assert FinalDecision(action="BUY_SMALL").is_buy
    assert FinalDecision(action="REDUCE").is_sell
    assert FinalDecision(action="SELL_ALL").is_sell
    assert not FinalDecision(action="HOLD").is_buy
    assert not FinalDecision(action="HOLD").is_sell


# --------------------------------------------------------------------------- #
# ChatGPT 합류 — 3인 합의
# --------------------------------------------------------------------------- #


def run3(claude_action, gemini_action, chatgpt_action, holding=False, *,
         conf=0.8, weight=20, take_profit=False):
    return decide(
        [agent("claude", claude_action, conf, weight),
         agent("gemini", gemini_action, conf, weight),
         agent("chatgpt", chatgpt_action, conf, weight)],
        holding, RISK, AI, take_profit=take_profit,
    )


def test_all_three_buy_is_strong_buy():
    assert run3("BUY", "BUY", "BUY").action == "STRONG_BUY"


@pytest.mark.parametrize("actions", [
    ("BUY", "BUY", "HOLD"), ("BUY", "HOLD", "BUY"), ("HOLD", "BUY", "BUY"),
])
def test_two_of_three_buy_is_not_enough(actions):
    """매수는 만장일치여야 한다 — 다수결로 완화하지 않는다."""
    assert run3(*actions).action == "HOLD"


def test_one_dissenting_sell_blocks_a_buy_and_reduces():
    assert run3("BUY", "BUY", "SELL", holding=True).action == "REDUCE"


def test_all_three_sell_liquidates():
    assert run3("SELL", "SELL", "SELL", holding=True).action == "SELL_ALL"


def test_two_of_three_sell_only_reduces():
    assert run3("SELL", "SELL", "HOLD", holding=True).action == "REDUCE"


def test_single_sell_vote_reduces_when_holding():
    """매도는 한 표만으로도 반응한다 — 자산을 지키는 쪽으로 기운 비대칭."""
    assert run3("HOLD", "HOLD", "SELL", holding=True).action == "REDUCE"


def test_sell_votes_do_nothing_without_a_position():
    assert run3("SELL", "SELL", "SELL", holding=False).action == "HOLD"


def test_one_broken_agent_forces_hold_even_on_unanimous_buy():
    votes = [agent("claude", "BUY"), agent("gemini", "BUY"), agent("chatgpt", "BUY", ok=False)]
    assert decide(votes, False, RISK, AI).action == "HOLD"


def test_broken_agent_is_named_in_the_reason():
    votes = [agent("claude", "BUY"), agent("gemini", "BUY"), agent("chatgpt", "BUY", ok=False)]
    assert "ChatGPT" in decide(votes, False, RISK, AI).reason


def test_low_confidence_from_any_agent_halves_the_weight():
    strong = run3("BUY", "BUY", "BUY", conf=0.8, weight=20)
    weak = decide(
        [agent("claude", "BUY", 0.9, 20), agent("gemini", "BUY", 0.9, 20),
         agent("chatgpt", "BUY", 0.3, 20)],
        False, RISK, AI,
    )
    assert strong.action == "STRONG_BUY" and weak.action == "BUY_SMALL"
    assert weak.weight_pct < strong.weight_pct


def test_weight_averages_across_all_three():
    result = decide(
        [agent("claude", "BUY", 0.9, 9), agent("gemini", "BUY", 0.9, 12),
         agent("chatgpt", "BUY", 0.9, 15)],
        False, RISK, AI,
    )
    assert result.weight_pct == 12  # (9 + 12 + 15) / 3


def test_reason_lists_all_three_agents():
    reason = run3("BUY", "BUY", "HOLD").reason
    assert "Claude" in reason and "Gemini" in reason and "ChatGPT" in reason


def test_take_profit_with_broken_agents_still_sells_half():
    votes = [agent("claude", "HOLD", ok=False), agent("gemini", "HOLD", ok=False),
             agent("chatgpt", "HOLD", ok=False)]
    result = decide(votes, True, RISK, AI, take_profit=True)
    assert result.action == "REDUCE" and result.sell_ratio == 0.5


def test_single_agent_still_works():
    """ChatGPT 만, 혹은 한쪽이 빠진 구성에서도 합의 규칙은 그대로다."""
    assert decide([agent("chatgpt", "BUY")], False, RISK, AI).action == "STRONG_BUY"


def test_empty_decision_list_holds():
    assert decide([], False, RISK, AI).action == "HOLD"
