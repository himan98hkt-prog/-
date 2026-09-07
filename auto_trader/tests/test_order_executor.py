"""주문 실행 테스트 — DRY_RUN 차단과 주문 무재시도가 핵심."""

from __future__ import annotations

from datetime import time

import pytest

from config.loader import RiskConfig, ScheduleConfig
from logic.decision_maker import FinalDecision
from logic.portfolio import Portfolio, PortfolioState, Position
from logic.risk_manager import RiskManager
from tests.conftest import make_env
from trading.kis_api import KisApiError, OrderResult, OrderStatus
from trading.order_executor import OrderExecutor

SCHEDULE = ScheduleConfig(
    universe_refresh=time(8, 30), first_cycle=time(9, 5), cycle_interval_min=30,
    last_new_buy=time(14, 30), eod_review=time(15, 10), daily_report=time(15, 40),
)

SNAPSHOT = {
    "code": "005930", "name": "삼성전자",
    "price": {"current": 71_300}, "position": {"holding": False},
}


class StubApi:
    """주문 API 대역 — 호출 횟수를 기록한다."""

    def __init__(self, fill_qty: int | None = None, error: Exception | None = None):
        self.orders: list[dict] = []
        self.fill_qty = fill_qty
        self.error = error
        self.cancels: list[str] = []

    def place_order(self, code, qty, side, price=0, order_type="market"):
        self.orders.append({"code": code, "qty": qty, "side": side,
                            "price": price, "order_type": order_type})
        if self.error:
            raise self.error
        return OrderResult(order_no="ODNO1", org_no="91252", order_time="100000",
                           code=code, side=side, qty=qty, price=price, order_type=order_type)

    def get_order_status(self, order_no, date=None):
        filled = self.fill_qty if self.fill_qty is not None else self.orders[-1]["qty"]
        ordered = self.orders[-1]["qty"]
        return OrderStatus(order_no=order_no, code="005930", name="삼성전자", side="BUY",
                           order_qty=ordered, filled_qty=filled,
                           remain_qty=ordered - filled, filled_price=71_300,
                           filled_amount=filled * 71_300, status="체결")

    def cancel_order(self, order_no, code, qty, org_no=""):
        self.cancels.append(order_no)
        return True

    def get_balance(self):  # Portfolio.sync 용 (여기서는 쓰지 않음)
        raise NotImplementedError


@pytest.fixture
def make_executor(settings_obj, tmp_path, monkeypatch):
    monkeypatch.setattr("logic.portfolio.time.sleep", lambda *_: None)

    def build(*, dry_run=True, api=None, order_type="market"):
        object.__setattr__(settings_obj.env, "dry_run", dry_run)
        object.__setattr__(settings_obj.risk, "order_type", order_type)
        stub = api or StubApi()
        portfolio = Portfolio(settings_obj, stub, db_path=tmp_path / "trader.db")
        risk = RiskManager(settings_obj.risk, SCHEDULE)
        return OrderExecutor(settings_obj, stub, portfolio, risk), stub, portfolio

    return build


def state(positions=(), cash=5_000_000):
    return PortfolioState(positions={p.code: p for p in positions}, cash=cash, deposit=cash)


def position(code="005930", qty=10, avg_price=70_000):
    return Position(code=code, name="삼성전자", qty=qty, orderable_qty=qty, avg_price=avg_price,
                    current_price=71_300, eval_amount=qty * 71_300,
                    pnl_amount=0, pnl_pct=1.8)


# --------------------------------------------------------------------------- #
# DRY_RUN
# --------------------------------------------------------------------------- #


def test_dry_run_never_calls_order_api(make_executor):
    executor, api, portfolio = make_executor(dry_run=True)
    final = FinalDecision(action="STRONG_BUY", weight_pct=20, reason="합의")

    result = executor.execute(final, SNAPSHOT, state(), cycle_id="c1")

    assert api.orders == [], "DRY_RUN 에서는 주문 API를 호출하면 안 됩니다"
    assert result.ordered and result.status == "DRY_RUN" and result.dry_run
    assert result.qty == 14  # floor(1,000,000 / 71,300)


def test_dry_run_order_is_recorded_in_db(make_executor):
    executor, _, portfolio = make_executor(dry_run=True)
    executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state(), cycle_id="c1")

    from utils.db import connect

    conn = connect(portfolio.db_path)
    rows = conn.execute("SELECT code, side, qty, dry_run, status FROM orders").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["dry_run"] == 1 and rows[0]["side"] == "BUY" and rows[0]["status"] == "DRY_RUN"


# --------------------------------------------------------------------------- #
# 수량 계산
# --------------------------------------------------------------------------- #


def test_hold_is_skipped(make_executor):
    executor, api, _ = make_executor()
    result = executor.execute(FinalDecision(action="HOLD"), SNAPSHOT, state())
    assert not result.ordered and result.status == "SKIPPED"
    assert api.orders == []


def test_zero_quantity_is_skipped(make_executor):
    executor, api, _ = make_executor()
    result = executor.execute(FinalDecision(action="BUY_SMALL", weight_pct=20),
                              SNAPSHOT, state(cash=10_000))
    assert not result.ordered and "0주" in result.reason
    assert api.orders == []


def test_sell_all_uses_full_orderable_quantity(make_executor):
    executor, api, _ = make_executor(dry_run=False)
    final = FinalDecision(action="SELL_ALL", sell_ratio=1.0)
    result = executor.execute(final, SNAPSHOT, state([position(qty=12)]))
    assert result.side == "SELL" and api.orders[0]["qty"] == 12


def test_reduce_sells_half(make_executor):
    executor, api, _ = make_executor(dry_run=False)
    final = FinalDecision(action="REDUCE", sell_ratio=0.5)
    executor.execute(final, SNAPSHOT, state([position(qty=11)]))
    assert api.orders[0]["qty"] == 5, "11주의 50% → 5주(내림)"


def test_reduce_of_single_share_sells_one(make_executor):
    executor, api, _ = make_executor(dry_run=False)
    executor.execute(FinalDecision(action="REDUCE", sell_ratio=0.5), SNAPSHOT, state([position(qty=1)]))
    assert api.orders[0]["qty"] == 1


def test_sell_without_position_is_skipped(make_executor):
    executor, api, _ = make_executor(dry_run=False)
    result = executor.execute(FinalDecision(action="SELL_ALL", sell_ratio=1.0), SNAPSHOT, state())
    assert not result.ordered and api.orders == []


def test_unknown_price_is_skipped(make_executor):
    executor, api, _ = make_executor()
    snapshot = {**SNAPSHOT, "price": {"current": 0}}
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), snapshot, state())
    assert not result.ordered and api.orders == []


# --------------------------------------------------------------------------- #
# 실주문
# --------------------------------------------------------------------------- #


def test_market_order_sends_zero_price(make_executor):
    executor, api, _ = make_executor(dry_run=False, order_type="market")
    executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state())
    assert api.orders[0]["price"] == 0 and api.orders[0]["order_type"] == "market"


def test_limit_buy_price_adds_slippage(make_executor):
    executor, api, _ = make_executor(dry_run=False, order_type="limit")
    executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state())
    assert api.orders[0]["price"] == round(71_300 * 1.003), "매수는 현재가 + 슬리피지"


def test_limit_sell_price_subtracts_slippage(make_executor):
    executor, api, _ = make_executor(dry_run=False, order_type="limit")
    executor.execute(FinalDecision(action="SELL_ALL", sell_ratio=1.0), SNAPSHOT, state([position()]))
    assert api.orders[0]["price"] == round(71_300 * 0.997)


def test_order_failure_is_not_retried(make_executor):
    executor, api, portfolio = make_executor(dry_run=False, api=StubApi(error=KisApiError("장운영시간 아님")))
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state(),
                              cycle_id="c1")

    assert len(api.orders) == 1, "주문 실패는 재시도하지 않습니다"
    assert not result.ordered and result.status == "REJECTED"
    assert "장운영시간" in result.error

    from utils.db import connect

    conn = connect(portfolio.db_path)
    row = conn.execute("SELECT status FROM orders").fetchone()
    conn.close()
    assert row["status"] == "REJECTED"


def test_filled_order_updates_db(make_executor):
    executor, api, portfolio = make_executor(dry_run=False)
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state(),
                              cycle_id="c1")

    assert result.status == "FILLED" and result.qty == 14

    from utils.db import connect

    conn = connect(portfolio.db_path)
    row = conn.execute("SELECT filled_qty, filled_price, status, dry_run FROM orders").fetchone()
    conn.close()
    assert row["filled_qty"] == 14 and row["status"] == "FILLED" and row["dry_run"] == 0


def test_unfilled_limit_order_is_canceled(make_executor):
    executor, api, _ = make_executor(dry_run=False, api=StubApi(fill_qty=0), order_type="limit")
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state())
    assert result.status == "CANCELED"
    assert api.cancels == ["ODNO1"], "지정가 미체결은 취소한다"


def test_unfilled_market_order_stays_pending(make_executor):
    executor, api, _ = make_executor(dry_run=False, api=StubApi(fill_qty=0), order_type="market")
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state())
    assert result.status == "PENDING"
    assert api.cancels == [], "시장가는 취소하지 않고 다음 사이클에 재조회한다"


def test_partial_fill_is_reported(make_executor):
    executor, _, _ = make_executor(dry_run=False, api=StubApi(fill_qty=6))
    result = executor.execute(FinalDecision(action="STRONG_BUY", weight_pct=20), SNAPSHOT, state())
    assert result.status == "PARTIAL" and result.qty == 6
