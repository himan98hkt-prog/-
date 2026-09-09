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
