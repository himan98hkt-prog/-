"""리스크 규칙 테스트 — 지시서 5-9의 7개 규칙 각각 거부 케이스."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from config.loader import RiskConfig, ScheduleConfig
from logic.portfolio import PortfolioState, Position
from logic.risk_manager import RiskManager

KST = ZoneInfo("Asia/Seoul")
MIDDAY = datetime(2026, 9, 8, 10, 30, tzinfo=KST)

RISK = RiskConfig(
    total_investment_cap_krw=5_000_000, max_position_pct=20, max_positions=5,
    daily_loss_limit_pct=3, stop_loss_pct=-5, take_profit_pct=10,
    min_order_krw=100_000, order_type="market", limit_slippage_pct=0.3,
)
SCHEDULE = ScheduleConfig(
    universe_refresh=time(8, 30), first_cycle=time(9, 5), cycle_interval_min=30,
    last_new_buy=time(14, 30), eod_review=time(15, 10), daily_report=time(15, 40),
)


@pytest.fixture
def manager():
    return RiskManager(RISK, SCHEDULE)


def position(code="005930", qty=10, avg_price=70_000, pnl_pct=0.0):
    return Position(code=code, name=f"종목{code}", qty=qty, orderable_qty=qty,
                    avg_price=avg_price, current_price=avg_price * (1 + pnl_pct / 100),
                    eval_amount=qty * avg_price * (1 + pnl_pct / 100),
                    pnl_amount=qty * avg_price * pnl_pct / 100, pnl_pct=pnl_pct)


def state(positions=(), cash=5_000_000, daily_pnl_pct=0.0, bought_today=()):
    return PortfolioState(
        positions={p.code: p for p in positions},
        cash=cash, deposit=cash, daily_pnl_pct=daily_pnl_pct,
        bought_today=set(bought_today), synced_at=MIDDAY,
    )


# --------------------------------------------------------------------------- #
# 통과 케이스
# --------------------------------------------------------------------------- #


def test_clean_buy_is_allowed(manager):
    verdict = manager.check_buy("005930", 500_000, state(), now=MIDDAY)
    assert verdict.allowed and bool(verdict) is True
    allowed, reason = manager.check_buy("005930", 500_000, state(), now=MIDDAY)
    assert allowed and "통과" in reason


# --------------------------------------------------------------------------- #
# 규칙 1 — 총 투자액 한도
# --------------------------------------------------------------------------- #


def test_rule1_total_investment_cap(manager):
    held = [position("000660", qty=60, avg_price=80_000)]  # 4,800,000원
    verdict = manager.check_buy("005930", 300_000, state(held), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "total_investment_cap_krw"
    assert "총 투자액 한도" in verdict.reason


def test_rule1_exactly_at_cap_is_allowed(manager):
    held = [position("000660", qty=50, avg_price=80_000)]  # 4,000,000원
    assert manager.check_buy("005930", 1_000_000, state(held), now=MIDDAY).allowed


# --------------------------------------------------------------------------- #
# 규칙 2 — 종목당 비중
# --------------------------------------------------------------------------- #


def test_rule2_position_size_cap(manager):
    verdict = manager.check_buy("005930", 1_100_000, state(), now=MIDDAY)  # 한도 1,000,000
    assert not verdict.allowed and verdict.rule == "max_position_pct"
    assert "종목당 비중" in verdict.reason


def test_rule2_counts_existing_holding_on_additional_buy(manager):
    held = [position("005930", qty=10, avg_price=70_000)]  # 700,000원
    verdict = manager.check_buy("005930", 400_000, state(held), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "max_position_pct"

    assert manager.check_buy("005930", 300_000, state(held), now=MIDDAY).allowed


# --------------------------------------------------------------------------- #
# 규칙 3 — 동시 보유 종목 수
# --------------------------------------------------------------------------- #


def test_rule3_max_positions_blocks_new_code(manager):
    held = [position(f"00000{i}", qty=1, avg_price=10_000) for i in range(5)]
    verdict = manager.check_buy("005930", 500_000, state(held), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "max_positions"


def test_rule3_additional_buy_of_held_code_is_allowed(manager):
    held = [position(f"00000{i}", qty=1, avg_price=10_000) for i in range(4)]
    held.append(position("005930", qty=1, avg_price=10_000))
    assert len(held) == RISK.max_positions
    assert manager.check_buy("005930", 500_000, state(held), now=MIDDAY).allowed, \
        "이미 보유 중인 종목의 추가매수는 허용"


# --------------------------------------------------------------------------- #
# 규칙 4 — 당일 손실 한도
# --------------------------------------------------------------------------- #


def test_rule4_daily_loss_limit(manager):
    verdict = manager.check_buy("005930", 500_000, state(daily_pnl_pct=-3.0), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "daily_loss_limit_pct"
    assert "당일 손실 한도" in verdict.reason


def test_rule4_small_loss_is_allowed(manager):
    assert manager.check_buy("005930", 500_000, state(daily_pnl_pct=-2.9), now=MIDDAY).allowed


# --------------------------------------------------------------------------- #
# 규칙 5 — 신규 매수 마감 시각
# --------------------------------------------------------------------------- #


def test_rule5_after_last_new_buy(manager):
    late = datetime(2026, 9, 8, 14, 31, tzinfo=KST)
    verdict = manager.check_buy("005930", 500_000, state(), now=late)
    assert not verdict.allowed and verdict.rule == "last_new_buy"


def test_rule5_exactly_at_deadline_is_allowed(manager):
    deadline = datetime(2026, 9, 8, 14, 30, tzinfo=KST)
    assert manager.check_buy("005930", 500_000, state(), now=deadline).allowed


# --------------------------------------------------------------------------- #
# 규칙 6 — 최소 주문 금액
# --------------------------------------------------------------------------- #


def test_rule6_min_order_amount(manager):
    verdict = manager.check_buy("005930", 99_999, state(), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "min_order_krw"


def test_rule6_exact_minimum_is_allowed(manager):
    assert manager.check_buy("005930", 100_000, state(), now=MIDDAY).allowed


# --------------------------------------------------------------------------- #
# 규칙 7 — 동일 종목 당일 1회
# --------------------------------------------------------------------------- #


def test_rule7_one_buy_per_day(manager):
    verdict = manager.check_buy("005930", 500_000, state(bought_today=["005930"]), now=MIDDAY)
    assert not verdict.allowed and verdict.rule == "one_buy_per_day"


def test_rule7_other_code_unaffected(manager):
    assert manager.check_buy("000660", 500_000, state(bought_today=["005930"]), now=MIDDAY).allowed


# --------------------------------------------------------------------------- #
# 강제 청산
# --------------------------------------------------------------------------- #


def test_stop_loss_triggers_at_threshold(manager):
    assert manager.check_forced_exit(position(pnl_pct=-5.0)) == "STOP_LOSS"
    assert manager.check_forced_exit(position(pnl_pct=-7.2)) == "STOP_LOSS"


def test_take_profit_triggers_at_threshold(manager):
    assert manager.check_forced_exit(position(pnl_pct=10.0)) == "TAKE_PROFIT"
    assert manager.check_forced_exit(position(pnl_pct=15.0)) == "TAKE_PROFIT"


def test_no_forced_exit_inside_band(manager):
    assert manager.check_forced_exit(position(pnl_pct=-4.9)) is None
    assert manager.check_forced_exit(position(pnl_pct=9.9)) is None
    assert manager.check_forced_exit(position(pnl_pct=0)) is None


def test_no_forced_exit_without_position(manager):
    assert manager.check_forced_exit(None) is None
    assert manager.check_forced_exit(position(qty=0, pnl_pct=-20)) is None


# --------------------------------------------------------------------------- #
# 주문 금액·수량 계산
# --------------------------------------------------------------------------- #


def test_buy_amount_is_capped_by_weight_and_cash(manager):
    assert manager.buy_amount(20, state(cash=5_000_000)) == 1_000_000
    assert manager.buy_amount(20, state(cash=400_000)) == 400_000, "가용현금이 우선"
    assert manager.buy_amount(50, state()) == 1_000_000, "종목당 비중 상한 적용"


def test_buy_quantity_floors(manager):
    assert manager.buy_quantity(1_000_000, 71_300) == 14
    assert manager.buy_quantity(50_000, 71_300) == 0
    assert manager.buy_quantity(1_000_000, 0) == 0


def test_first_failing_rule_is_reported(manager):
    """여러 규칙을 동시에 위반해도 최소 주문 금액이 먼저 걸린다."""
    verdict = manager.check_buy("005930", 1_000, state(daily_pnl_pct=-10), now=MIDDAY)
    assert verdict.rule == "min_order_krw"


# --- 트레일링 스톱 ----------------------------------------------------------- #

import dataclasses  # noqa: E402

TRAILING = dataclasses.replace(RISK, trailing_activate_pct=10, trailing_stop_pct=5)


@pytest.fixture
def trailing():
    return RiskManager(TRAILING, SCHEDULE)


def _held(peak, current, avg=100_000):
    """고점 peak 를 찍고 지금 current 인 보유 종목."""
    return Position(
        code="005930", name="삼성전자", qty=10, orderable_qty=10,
        avg_price=avg, current_price=current, eval_amount=10 * current,
        pnl_amount=10 * (current - avg), pnl_pct=(current / avg - 1) * 100,
        peak_price=peak,
    )


def test_trailing_is_dormant_before_the_activation_level(trailing):
    """+10% 를 밟은 적이 없으면 트레일링은 아직 없는 규칙이다."""
    position = _held(peak=108_000, current=104_000)
    assert trailing.trailing_stop_price(position) == 0.0
    assert trailing.check_forced_exit(position) is None


def test_trailing_arms_at_the_activation_level(trailing):
    """딱 +10% 를 밟으면 켜지고, 기준선은 +10% 가격이다."""
    position = _held(peak=110_000, current=110_000)
    assert trailing.trailing_stop_price(position) == 110_000


def test_trailing_never_falls_below_the_activation_level(trailing):
    """+10% 에 켜진 트레일링이 +4% 에 팔아치우면 고정 익절선보다 나쁘다."""
    position = _held(peak=112_000, current=111_000)
    # 고점 대비 5% 는 106,400 이지만 활성화 가격 110,000 이 바닥이다
    assert trailing.trailing_stop_price(position) == 110_000


def test_trailing_follows_the_peak_up(trailing):
    """고점이 오르면 기준선도 따라 오른다 — 승자를 더 태우는 부분."""
    position = _held(peak=150_000, current=145_000)
    assert trailing.trailing_stop_price(position) == 142_500   # 150,000 x 0.95
    # 기준선 위라면 팔지 않는다. 예전 익절 경로도 끼어들면 안 된다 — 끼어들면
    # +10% 넘은 종목마다 AI 재판단이 걸려 트레일링이 무의미해진다.
    assert trailing.check_forced_exit(position) is None


def test_trailing_sells_everything_when_breached(trailing):
    position = _held(peak=150_000, current=142_000)            # 기준 142,500 밑
    assert trailing.check_forced_exit(position) == "TRAILING_STOP"


def test_hard_stop_loss_still_wins(trailing):
    """트레일링이 켜져도 -5% 손절은 그대로 최우선이다."""
    position = _held(peak=150_000, current=94_000)             # -6%
    assert trailing.check_forced_exit(position) == "STOP_LOSS"


def test_trailing_off_keeps_the_old_take_profit(manager):
    """기능을 끄면(기본값) 예전대로 +10% 에서 AI 재판단을 요청한다."""
    position = _held(peak=150_000, current=130_000)
    assert manager.trailing_stop_price(position) == 0.0
    assert manager.check_forced_exit(position) == "TAKE_PROFIT"


def test_arming_alone_does_not_sell(trailing):
    """활성화되는 순간 현재가와 기준선이 같다 — 여기서 팔면 고정 익절선과 똑같다."""
    position = _held(peak=110_000, current=110_000)
    assert trailing.trailing_stop_price(position) == 110_000
    assert trailing.check_forced_exit(position) is None, "켜지자마자 팔았습니다"


def test_worst_case_is_never_worse_than_the_fixed_take_profit(trailing):
    """올랐다가 곧바로 되밀려도 활성화 가격(+10%) 아래로는 팔지 않는다."""
    # +10% 를 찍자마자 반락 — 기준선은 여전히 110,000
    position = _held(peak=110_000, current=109_000)
    assert trailing.check_forced_exit(position) == "TRAILING_STOP"
    assert trailing.trailing_stop_price(position) == 110_000


def test_a_full_price_path(trailing):
    """매수 → 상승 → 고점 → 되밀림까지 한 줄기로 확인한다."""
    path = [(103_000, None), (110_000, None), (125_000, None),
            (140_000, None), (133_000, None), (132_900, "TRAILING_STOP")]
    peak = 0.0
    for price, expected in path:
        peak = max(peak, price)                      # sync_peaks 와 같은 규칙
        position = _held(peak=peak, current=price)
        assert trailing.check_forced_exit(position) == expected, f"{price:,}원에서 어긋남"


# --- 최소 보유기간 ------------------------------------------------------------ #

HOLD_DAYS = dataclasses.replace(RISK, min_holding_days=1,
                                trailing_activate_pct=10, trailing_stop_pct=5)


@pytest.fixture
def holder():
    return RiskManager(HOLD_DAYS, SCHEDULE)


def _bought(at, pnl_pct=2.0, avg=100_000):
    price = avg * (1 + pnl_pct / 100)
    return Position(code="005930", name="삼성전자", qty=10, orderable_qty=10,
                    avg_price=avg, current_price=price, eval_amount=10 * price,
                    pnl_amount=10 * (price - avg), pnl_pct=pnl_pct,
                    first_bought_at=at)


def test_same_day_sell_is_held_back(holder):
    """하루 회전은 왕복 비용만 내고 남는 게 없다."""
    verdict = holder.check_sell(_bought("2026-09-08T09:35:00+09:00"), now=MIDDAY)
    assert not verdict.allowed
    assert verdict.rule == "min_holding_days"


def test_next_day_sell_is_allowed(holder):
    verdict = holder.check_sell(_bought("2026-09-07T09:35:00+09:00"), now=MIDDAY)
    assert verdict.allowed


def test_stop_loss_ignores_the_holding_period(holder):
    """자산을 지키는 쪽은 언제나 통과해야 한다 — check_sell 을 거치지 않는다."""
    position = _bought("2026-09-08T09:35:00+09:00", pnl_pct=-6.0)
    assert holder.check_forced_exit(position) == "STOP_LOSS"


def test_trailing_ignores_the_holding_period(holder):
    position = _bought("2026-09-08T09:35:00+09:00", pnl_pct=12.0)
    position.peak_price = 150_000          # 고점 대비 크게 밀림
    assert holder.check_forced_exit(position) == "TRAILING_STOP"


def test_disabled_by_default(manager):
    """설정하지 않으면 예전대로 언제든 팔 수 있다."""
    assert manager.check_sell(_bought("2026-09-08T09:35:00+09:00"), now=MIDDAY).allowed


def test_broken_entry_date_does_not_block(holder):
    """값이 깨졌다고 매도를 막으면 위험을 붙들게 된다."""
    assert holder.check_sell(_bought("이상한값"), now=MIDDAY).allowed
    assert holder.check_sell(_bought(""), now=MIDDAY).allowed
