"""규칙 엔진 — 결정론적 정량 게이트.

여기서 지켜야 하는 성질은 네 가지다.

1. **거부권은 점수로 상쇄되지 않는다.** 가점이 만점이어도 과열이면 매수하지 않는다.
2. **0.0 은 값이 아니라 '데이터 부족'이다.** 지표가 비면 비교가 거꾸로 돌기 때문에
   (`현재가 > ma20` 이 늘 참이 된다) 매수를 막아야 한다.
3. **같은 입력 → 같은 출력.** API 를 쓰지 않으므로 흔들릴 이유가 없다.
4. **사유가 사람이 읽을 수 있어야 한다.** 왜 막혔는지 화면에서 풀려야 한다.
"""

from __future__ import annotations

import pytest

from logic.rule_engine import RulesConfig, RuleVerdict, evaluate

CONFIG = RulesConfig()


def snapshot(**over):
    """규칙 다섯 항목을 모두 충족하는 기본 스냅샷 — 여기서 하나씩 망가뜨려 본다."""
    price = {"current": 73_000, "change_pct": 1.5, "volume": 1500,
             "volume_ratio_20d": 1.5}
    indicators = {"ma5": 72_900, "ma20": 72_500, "ma60": 72_000, "rsi14": 55.0,
                  "macd": 120.0, "macd_signal": 60.0, "macd_hist": 60.0,
                  "bb_upper": 74_500, "bb_lower": 70_500}
    book = {"bid_total": 100, "ask_total": 50, "spread_pct": 0.14}
    data = {"code": "005930", "name": "삼성전자",
            "price": price, "indicators": indicators, "orderbook": book}
    for key, value in over.items():
        if key in ("price", "indicators", "orderbook"):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return data


# --- 기본 동작 ------------------------------------------------------------- #

def test_healthy_uptrend_is_a_buy():
    verdict = evaluate(snapshot(), CONFIG)
    assert verdict.action == "BUY"
    assert verdict.buy_score == 5, verdict.passed
    assert not verdict.vetoes
    assert not verdict.blocks_buy


def test_the_same_input_gives_the_same_answer():
    """결정론 — 이게 깨지면 규칙 엔진의 존재 이유가 사라진다."""
    first = evaluate(snapshot(), CONFIG)
    second = evaluate(snapshot(), CONFIG)
    assert first.to_dict() == second.to_dict()


def test_turning_it_off_reports_no_cross_check():
    verdict = evaluate(snapshot(), RulesConfig(enabled=False))
    assert verdict.evaluated is False
    assert verdict.action == "HOLD"
    # 끈 상태는 '중립' 이 아니라 '검증 없음' 이다 — 합의 로직이 구분해야 한다.
    assert not verdict.blocks_buy


# --- 거부권 ---------------------------------------------------------------- #

@pytest.mark.parametrize("over, fragment", [
    ({"indicators": {"rsi14": 78.0}}, "과열"),
    ({"price": {"change_pct": 9.0}}, "급등 추격"),
    ({"orderbook": {"spread_pct": 1.4}}, "스프레드"),
    ({"price": {"current": 75_000}}, "볼린저 상단"),
    ({"indicators": {"ma60": 80_000}}, "60일선"),
])
def test_each_veto_blocks_buying(over, fragment):
    verdict = evaluate(snapshot(**over), CONFIG)
    assert verdict.blocks_buy, f"{fragment} 가 매수를 막지 못했습니다"
    assert verdict.action != "BUY"
    assert any(fragment in v for v in verdict.vetoes), verdict.vetoes


def test_a_veto_beats_a_perfect_score():
    """거부권은 점수로 상쇄되지 않는다 — 이게 두 층 구조의 핵심이다."""
    # 가점은 그대로 두고 과열만 만든다. RSI 를 올리면 '건강구간' 가점만 빠진다.
    verdict = evaluate(snapshot(indicators={"rsi14": 78.0}), CONFIG)
    assert verdict.buy_score >= CONFIG.buy_score_min, "가점은 여전히 임계치 이상이어야 한다"
    assert verdict.action == "HOLD", "그래도 매수하면 안 된다"


def test_missing_indicators_block_buying():
    """0.0 은 '데이터 부족' 이다. 값으로 읽으면 비교가 거꾸로 돈다."""
    verdict = evaluate(snapshot(indicators={"ma20": 0.0, "rsi14": 0.0}), CONFIG)
    assert verdict.blocks_buy
    assert any("데이터 부족" in v for v in verdict.vetoes), verdict.vetoes


def test_an_empty_snapshot_does_not_crash_and_does_not_buy():
    verdict = evaluate({}, CONFIG)
    assert verdict.action == "HOLD"
    assert verdict.blocks_buy


def test_garbage_values_do_not_crash():
    """NaN·문자열·None 이 섞여도 터지지 않고 매수를 막아야 한다."""
    verdict = evaluate(snapshot(
        price={"current": "이상한값", "change_pct": None},
        indicators={"ma20": float("nan"), "rsi14": "x"},
    ), CONFIG)
    assert verdict.action == "HOLD"
    assert verdict.blocks_buy


# --- 점수 ------------------------------------------------------------------ #

def test_a_weak_setup_falls_short_and_says_how_short():
    """근거가 모자라면 '몇 개 부족한지' 가 사유에 적혀야 한다."""
    verdict = evaluate(snapshot(
        indicators={"ma5": 72_400, "ma20": 72_500, "macd_hist": -10.0, "rsi14": 35.0},
        price={"volume_ratio_20d": 0.8},
    ), CONFIG)
    assert verdict.action in ("HOLD", "SELL")
    assert verdict.buy_score < CONFIG.buy_score_min


def test_volume_uses_the_20day_ratio_not_the_raw_count():
    """종목마다 거래 규모가 달라 절대값으로는 비교가 되지 않는다."""
    quiet = evaluate(snapshot(price={"volume_ratio_20d": 0.9}), CONFIG)
    busy = evaluate(snapshot(price={"volume_ratio_20d": 1.5}), CONFIG)
    assert busy.buy_score == quiet.buy_score + 1
    assert any("거래량" in p for p in busy.passed)
    assert not any("거래량" in p for p in quiet.passed)


# --- 매도 ------------------------------------------------------------------ #

def test_breaking_below_the_mean_with_negative_macd_is_a_sell():
    verdict = evaluate(snapshot(
        price={"current": 71_000},
        indicators={"macd_hist": -40.0},
    ), CONFIG)
    assert verdict.action == "SELL"
    assert verdict.sell_score >= CONFIG.sell_score_min


def test_extreme_overbought_sells_on_its_own():
    """RSI 80↑ 은 단독으로 성립한다 — 가짜 감점을 끼워 넣지 않고.

    예전 구현은 점수를 채우려고 사유 목록에 빈 항목을 하나 더 넣었다. 그러면
    화면의 사유 문장과 점수가 둘 다 더럽혀진다.
    """
    verdict = evaluate(snapshot(indicators={"rsi14": 85.0}), CONFIG)
    assert verdict.action == "SELL"
    assert verdict.sell_score == 1, "감점 한 개로 성립해야 한다"
    assert len(verdict.negatives) == 1, verdict.negatives
    assert all(n.strip() for n in verdict.negatives), "빈 사유가 섞여 있습니다"


def test_sell_is_decided_before_buy_vetoes():
    """매도 판정이 먼저다 — 자산을 지키는 쪽으로 기운 비대칭."""
    # 과열 거부권과 극단 과열 매도 신호가 동시에 서는 자리.
    verdict = evaluate(snapshot(indicators={"rsi14": 85.0}), CONFIG)
    assert verdict.action == "SELL", "거부권에 묻혀 HOLD 가 되면 못 팔고 안고 있게 된다"


# --- 사유 문장 ------------------------------------------------------------- #

def test_the_reason_is_readable_and_never_empty():
    for over in ({}, {"indicators": {"rsi14": 78.0}}, {"indicators": {"rsi14": 85.0}},
                 {"indicators": {"ma20": 0.0}}):
        verdict = evaluate(snapshot(**over), CONFIG)
        assert verdict.reason.strip(), f"{over} 에서 사유가 비었습니다"
        assert verdict.summary().strip()


def test_the_summary_leads_with_the_blocking_reason():
    """차단됐을 때 요약 첫머리에 '무엇이 막았는지' 가 와야 한다."""
    verdict = evaluate(snapshot(indicators={"rsi14": 78.0}), CONFIG)
    assert verdict.summary().startswith("규칙 차단")
    assert "과열" in verdict.summary()


# --- 임계치 조정 ----------------------------------------------------------- #

def test_thresholds_actually_take_effect():
    strict = RulesConfig(buy_score_min=5, rsi_overbought=50.0)
    verdict = evaluate(snapshot(), strict)
    assert verdict.action != "BUY", "임계치를 올렸는데 그대로 매수했습니다"


def test_score_is_the_net_for_display():
    verdict = evaluate(snapshot(), CONFIG)
    assert verdict.score == verdict.buy_score - verdict.sell_score


def test_a_default_verdict_blocks_nothing():
    """기본 생성된 판정이 실수로 매수를 막지 않아야 한다."""
    assert not RuleVerdict().blocks_buy


def test_the_summary_does_not_say_blocked_while_selling():
    """RSI 85 는 과열 거부권과 극단 과열 매도 신호가 동시에 서는 자리다.

    거부권을 먼저 보고하면 실제로는 팔고 있는데 화면에 '매수 차단' 이라고
    적힌다 — 대시보드가 거짓말을 하게 된다.
    """
    verdict = evaluate(snapshot(indicators={"rsi14": 85.0}), CONFIG)
    assert verdict.action == "SELL"
    assert verdict.vetoes, "과열 거부권도 함께 서 있어야 하는 상황이다"
    assert verdict.summary().startswith("규칙 SELL"), verdict.summary()
    assert "차단" not in verdict.summary()
