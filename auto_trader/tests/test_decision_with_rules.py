"""합의 로직 — AI 판단 + 규칙 게이트.

설계의 두 비대칭을 여기서 지킨다.

1. **매수는 양쪽 동의, 매도는 한쪽만으로 성립.**
2. **규칙은 단독으로 매수하지 못하고, 단독으로 매도할 수 있다.**
   보호 동작이 LLM 가용성에 묶이면 키가 거부된 날 손실을 그냥 안고 있게 된다.
"""

from __future__ import annotations

import pytest

from agents.schemas import AgentDecision
from logic.decision_maker import decide
from logic.rule_engine import RuleVerdict


# 설정 객체는 기존 합의 테스트와 같은 것을 쓴다. 여기서 따로 만들면 필드가
# 늘어날 때마다 두 곳을 고쳐야 하고, 한쪽만 고치면 조용히 어긋난다.
from tests.test_decision_maker import AI, RISK


@pytest.fixture
def ai():
    return AI


@pytest.fixture
def risk():
    return RISK


def buy(agent="claude", confidence=0.8, weight=20):
    return AgentDecision(agent=agent, action="BUY", confidence=confidence,
                         weight_pct=weight, reason="상대적 우위", ok=True)


def sell(agent="claude"):
    return AgentDecision(agent=agent, action="SELL", confidence=0.8,
                         weight_pct=0, reason="이탈", ok=True)


def hold(agent="claude"):
    return AgentDecision(agent=agent, action="HOLD", confidence=0.5,
                         weight_pct=0, reason="관망", ok=True)


def dead(agent="claude", kind="auth"):
    return AgentDecision.hold(agent, "키가 거부됐습니다", kind=kind)


def rules(action="BUY", vetoes=(), buy_score=5, sell_score=0, evaluated=True):
    return RuleVerdict(action=action, buy_score=buy_score, sell_score=sell_score,
                       vetoes=list(vetoes), reason="테스트", evaluated=evaluated)


# --- 매수: 양쪽이 동의해야 한다 -------------------------------------------- #

def test_ai_buy_plus_rule_buy_is_a_strong_buy(risk, ai):
    final = decide([buy()], holding=False, risk=risk, ai=ai, rules=rules("BUY"))
    assert final.action == "STRONG_BUY"
    assert final.is_buy


def test_a_rule_veto_blocks_a_confident_ai_buy(risk, ai):
    """거부권은 confidence 로 상쇄되지 않는다."""
    final = decide([buy(confidence=0.99)], holding=False, risk=risk, ai=ai,
                   rules=rules("HOLD", vetoes=["RSI 78 과열(≥75)"]))
    assert final.action == "HOLD"
    assert "규칙 차단" in final.reason
    assert "과열" in final.reason, "무엇이 막았는지 사유에 남아야 한다"


def test_a_neutral_rule_halves_the_position(risk, ai):
    """규칙이 중립이면 산다 — 다만 절반만. 거부권이 아닌 '근거 부족'이므로."""
    final = decide([buy()], holding=False, risk=risk, ai=ai, rules=rules("HOLD"))
    assert final.action == "BUY_SMALL"
    assert 0 < final.weight_pct < 20


def test_rules_never_buy_on_their_own(risk, ai):
    """규칙이 BUY 라도 AI 가 동의하지 않으면 매수하지 않는다."""
    for vote in (hold(), dead()):
        final = decide([vote], holding=False, risk=risk, ai=ai, rules=rules("BUY"))
        assert not final.is_buy, f"{vote.action}/{vote.ok} 인데 매수했습니다"


def test_ai_buy_against_a_rule_sell_does_nothing(risk, ai):
    """정면 충돌 — 늘리지도 줄이지도 않는다. 매수 신호를 근거로 팔지 않는다."""
    final = decide([buy()], holding=True, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "HOLD"
    assert not final.is_sell


# --- 매도: 한쪽만으로 성립한다 --------------------------------------------- #

def test_rules_can_sell_on_their_own_while_ai_watches(risk, ai):
    final = decide([hold()], holding=True, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "REDUCE"
    assert final.sell_ratio == pytest.approx(0.5)


def test_a_rule_sell_does_nothing_when_not_holding(risk, ai):
    final = decide([hold()], holding=False, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "HOLD"


def test_protection_survives_a_dead_engine(risk, ai):
    """핵심 — 키가 거부돼도 규칙의 이탈 신호로 줄일 수 있어야 한다.

    예전에는 엔진이 하나라도 죽으면 무조건 HOLD 였다. 그러면 Gemini 쿼터가
    소진되거나 Claude 키가 401 을 받은 날, 떨어지는 종목을 그대로 안고 있었다.
    규칙 엔진은 API 를 쓰지 않으므로 그날도 살아 있다.
    """
    final = decide([dead()], holding=True, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "REDUCE"
    assert "응답 불가" in final.reason
    assert "규칙 이탈 신호" in final.reason


def test_a_dead_engine_still_cannot_buy(risk, ai):
    final = decide([dead()], holding=False, risk=risk, ai=ai, rules=rules("BUY"))
    assert final.action == "HOLD"
    assert not final.is_buy


def test_take_profit_still_wins_over_a_rule_sell(risk, ai):
    """익절선 도달은 기존 경로를 그대로 쓴다 — 사유가 바뀌면 안 된다."""
    final = decide([dead()], holding=True, risk=risk, ai=ai, take_profit=True,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "REDUCE"
    assert "익절선" in final.reason


# --- 규칙 엔진을 끈 경우 --------------------------------------------------- #

def test_disabled_rules_do_not_gate_anything(risk, ai):
    """`enabled: false` 는 '중립' 이 아니라 '검증 없음' — 예전 동작으로 돌아간다."""
    off = rules("HOLD", evaluated=False)
    final = decide([buy()], holding=False, risk=risk, ai=ai, rules=off)
    assert final.action == "STRONG_BUY", "검증이 없으면 AI 합의만으로 판단한다"


def test_no_rules_argument_keeps_the_old_behaviour(risk, ai):
    """하위 호환 — rules 를 주지 않으면 기존 합의 로직 그대로."""
    assert decide([buy()], holding=False, risk=risk,
                  ai=ai).action == "STRONG_BUY"
    assert decide([hold()], holding=True, risk=risk, ai=ai).action == "HOLD"


# --- 여러 엔진을 쓰는 구성에서도 게이트가 유지되는지 ----------------------- #

def test_the_gate_still_applies_with_several_engines(risk, ai):
    votes = [buy("claude"), buy("gemini"), buy("chatgpt")]
    assert decide(votes, holding=False, risk=risk, ai=ai,
                  rules=rules("BUY")).action == "STRONG_BUY"
    blocked = decide(votes, holding=False, risk=risk, ai=ai,
                     rules=rules("HOLD", vetoes=["볼린저 상단 이탈"]))
    assert blocked.action == "HOLD"


def test_one_sell_vote_among_buys_still_reduces(risk, ai):
    """기존 비대칭이 규칙 도입으로 느슨해지지 않았는지."""
    votes = [buy("claude"), sell("gemini")]
    final = decide(votes, holding=True, risk=risk, ai=ai, rules=rules("BUY"))
    assert final.action == "REDUCE"


def test_a_mixed_buy_is_not_sold_on_a_rule_sell(risk, ai):
    """BUY 표가 섞여 있으면 규칙 SELL 로도 줄이지 않는다.

    전원 BUY + 규칙 SELL 을 '정면 충돌 → 관망' 으로 두면서 일부 BUY 는 매도하면
    기준이 어긋난다 — 매수 의견을 근거로 파는 셈이 된다.
    """
    votes = [buy("claude"), hold("gemini")]
    final = decide(votes, holding=True, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "HOLD"
    assert not final.is_sell


def test_all_hold_with_a_rule_sell_still_reduces(risk, ai):
    """반대로 BUY 표가 전혀 없으면 규칙 단독으로 줄인다."""
    votes = [hold("claude"), hold("gemini")]
    final = decide(votes, holding=True, risk=risk, ai=ai,
                   rules=rules("SELL", sell_score=2))
    assert final.action == "REDUCE"
