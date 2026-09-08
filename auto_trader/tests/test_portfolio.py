"""포트폴리오 동기화·기록 테스트 — DB가 아니라 KIS 잔고가 진실이다."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from agents.schemas import AgentDecision
from logic.decision_maker import FinalDecision
from logic.portfolio import Portfolio
from trading.kis_api import Balance, Holding, KisApiError, OrderStatus
from utils.db import connect

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 8, 9, 10, tzinfo=KST)


def holding(code="005930", qty=12, avg=70_000, price=71_300, pnl_pct=1.86):
    return Holding(code=code, name=f"종목{code}", qty=qty, orderable_qty=qty, avg_price=avg,
                   current_price=price, eval_amount=qty * price,
                   pnl_amount=qty * (price - avg), pnl_pct=pnl_pct)


class StubApi:
    def __init__(self, balances, statuses=None):
        self.balances = list(balances)
        self.statuses = list(statuses or [])
        self.cancels: list[str] = []

    def get_balance(self):
        return self.balances.pop(0) if len(self.balances) > 1 else self.balances[0]

    def get_order_status(self, order_no, date=None):
        if not self.statuses:
            return None
        result = self.statuses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def cancel_order(self, order_no, code, qty, org_no=""):
        self.cancels.append(order_no)
        return True


@pytest.fixture
def make_portfolio(settings_obj, tmp_path, monkeypatch):
    monkeypatch.setattr("logic.portfolio.time.sleep", lambda *_: None)

    def build(balances, statuses=None):
        api = StubApi(balances, statuses)
        return Portfolio(settings_obj, api, db_path=tmp_path / "trader.db"), api

    return build


# --------------------------------------------------------------------------- #
# 동기화
# --------------------------------------------------------------------------- #


def test_sync_loads_positions_and_cash(make_portfolio):
    portfolio, _ = make_portfolio([Balance(holdings=[holding()], deposit=4_000_000,
                                           orderable_cash=3_800_000)])
    state = portfolio.sync(now=NOW)

    assert state.position_count == 1
    assert state.cash == 3_800_000
    assert state.holds("005930") and not state.holds("000660")
    assert state.total_invested == 12 * 70_000


def test_sync_removes_liquidated_positions(make_portfolio):
    balances = [
        Balance(holdings=[holding("005930"), holding("000660")], deposit=1_000, orderable_cash=1_000),
        Balance(holdings=[holding("005930")], deposit=1_000, orderable_cash=1_000),
    ]
    portfolio, _ = make_portfolio(balances)
    portfolio.sync(now=NOW)
    state = portfolio.sync(now=NOW + timedelta(minutes=30))

    assert set(state.positions) == {"005930"}
    conn = connect(portfolio.db_path)
    codes = {row["code"] for row in conn.execute("SELECT code FROM positions")}
    conn.close()
    assert codes == {"005930"}, "청산된 종목은 DB에서도 사라져야 합니다"


def test_zero_orderable_cash_is_not_replaced_by_deposit(make_portfolio):
    """주문가능현금 0 은 '주문할 수 없다'는 뜻 — 예수금으로 덮어쓰면 안 된다."""
    portfolio, _ = make_portfolio([Balance(holdings=[], deposit=2_500_000, orderable_cash=0)])
    assert portfolio.sync(now=NOW).cash == 0


# --------------------------------------------------------------------------- #
# 당일 손익
# --------------------------------------------------------------------------- #


def test_daily_pnl_starts_at_zero_and_tracks_equity(make_portfolio):
    start = Balance(holdings=[holding(qty=10, price=70_000)], deposit=0, orderable_cash=1_000_000)
    later = Balance(holdings=[holding(qty=10, price=77_000)], deposit=0, orderable_cash=1_000_000)
    portfolio, _ = make_portfolio([start, later])

    assert portfolio.sync(now=NOW).daily_pnl_pct == 0.0, "첫 동기화는 기준점"

    state = portfolio.sync(now=NOW + timedelta(hours=1))
    # 시작 1,700,000 → 현재 1,770,000
    assert state.daily_pnl_pct == pytest.approx(4.1176, abs=0.001)


def test_daily_pnl_row_is_per_date(make_portfolio):
    balance = Balance(holdings=[], deposit=1_000_000, orderable_cash=1_000_000)
    portfolio, _ = make_portfolio([balance])
    portfolio.sync(now=NOW)
    portfolio.sync(now=NOW + timedelta(days=1))

    conn = connect(portfolio.db_path)
    dates = [row["date"] for row in conn.execute("SELECT date FROM daily_pnl ORDER BY date")]
    conn.close()
    assert dates == ["2026-09-08", "2026-09-09"]


# --------------------------------------------------------------------------- #
# 당일 매수 기록
# --------------------------------------------------------------------------- #


def test_bought_today_reflects_recorded_orders(make_portfolio, monkeypatch):
    monkeypatch.setattr("logic.portfolio.now_kst_iso", lambda: NOW.isoformat(timespec="seconds"))
    balance = Balance(holdings=[], deposit=1_000_000, orderable_cash=1_000_000)
    portfolio, _ = make_portfolio([balance])
    portfolio.record_order(cycle_id="c1", code="005930", name="삼성전자", side="BUY",
                           order_type="market", qty=1, price=71_300, status="DRY_RUN")
    portfolio.record_order(cycle_id="c1", code="000660", name="SK하이닉스", side="SELL",
                           order_type="market", qty=1, price=170_000, status="FILLED")
    portfolio.record_order(cycle_id="c1", code="035420", name="NAVER", side="BUY",
                           order_type="market", qty=1, price=200_000, status="REJECTED")

    state = portfolio.sync(now=NOW)
    assert "005930" in state.bought_today, "DRY_RUN 매수도 1일 1회 제한 대상"
    assert "000660" not in state.bought_today, "매도는 제외"
    assert "035420" not in state.bought_today, "거부된 주문은 제외"


# --------------------------------------------------------------------------- #
# 결정 기록
# --------------------------------------------------------------------------- #


def test_record_decision_saves_raw_ai_responses(make_portfolio):
    portfolio, _ = make_portfolio([Balance()])
    snapshot = {"code": "005930", "name": "삼성전자", "position": {"holding": True}}
    decisions = {
        "claude": AgentDecision(agent="claude", action="BUY", confidence=0.8, weight_pct=15,
                                reason="추세 양호", raw='{"action":"BUY"}', ok=True),
        "gemini": AgentDecision(agent="gemini", action="HOLD", confidence=0.0, weight_pct=0,
                                reason="", raw="설명문", ok=False),
    }
    final = FinalDecision(action="HOLD", weight_pct=0, reason="합의 없음")

    portfolio.record_decision(cycle_id="c1", snapshot=snapshot, decisions=decisions, final=final,
                              forced_exit=None, risk_passed=False, risk_reason="관망")

    conn = connect(portfolio.db_path)
    row = conn.execute("SELECT * FROM decisions").fetchone()
    conn.close()
    assert row["claude_action"] == "BUY" and row["claude_ok"] == 1
    assert row["gemini_ok"] == 0 and row["gemini_raw"] == "설명문"
    assert row["final_action"] == "HOLD" and row["holding"] == 1
    assert "005930" in row["snapshot_json"]


# --------------------------------------------------------------------------- #
# 체결 대기
# --------------------------------------------------------------------------- #


def filled(qty=10, ordered=10):
    return OrderStatus(order_no="ODNO1", code="005930", name="삼성전자", side="BUY",
                       order_qty=ordered, filled_qty=qty, remain_qty=ordered - qty,
                       filled_price=71_300, filled_amount=qty * 71_300, status="체결")


def test_wait_for_fill_returns_filled(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled()])
    state, status = portfolio.wait_for_fill("ODNO1", "market", "005930", 10)
    assert state == "FILLED" and status.filled_qty == 10


def test_wait_for_fill_polls_until_filled(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled(0), filled(0), filled(10)])
    state, _ = portfolio.wait_for_fill("ODNO1", "market", "005930", 10)
    assert state == "FILLED"


def test_unfilled_limit_order_is_canceled(make_portfolio):
    portfolio, api = make_portfolio([Balance()], statuses=[filled(0) for _ in range(6)])
    state, _ = portfolio.wait_for_fill("ODNO1", "limit", "005930", 10)
    assert state == "CANCELED" and api.cancels == ["ODNO1"]


def test_unfilled_market_order_stays_pending(make_portfolio):
    portfolio, api = make_portfolio([Balance()], statuses=[filled(0) for _ in range(6)])
    state, _ = portfolio.wait_for_fill("ODNO1", "market", "005930", 10)
    assert state == "PENDING" and api.cancels == []


def test_partial_market_fill(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled(4) for _ in range(6)])
    state, status = portfolio.wait_for_fill("ODNO1", "market", "005930", 10)
    assert state == "PARTIAL" and status.filled_qty == 4


def test_status_lookup_errors_do_not_raise(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[KisApiError("조회 실패")] * 6)
    state, status = portfolio.wait_for_fill("ODNO1", "market", "005930", 10)
    assert state == "UNKNOWN" and status is None


def test_cancel_failure_leaves_order_pending(make_portfolio):
    portfolio, api = make_portfolio([Balance()], statuses=[filled(0) for _ in range(6)])
    api.cancel_order = lambda *a, **kw: (_ for _ in ()).throw(KisApiError("취소 실패"))
    state, _ = portfolio.wait_for_fill("ODNO1", "limit", "005930", 10)
    assert state == "PENDING"


def test_bought_today_is_timezone_safe_before_market_open(make_portfolio, monkeypatch):
    """08:30 KST 기록도 같은 날로 잡혀야 한다.

    SQLite 의 date() 는 '+09:00' 오프셋을 UTC 로 환산해 하루를 앞당긴다.
    """
    early = datetime(2026, 9, 8, 8, 30, tzinfo=KST)
    monkeypatch.setattr("logic.portfolio.now_kst_iso", lambda: early.isoformat(timespec="seconds"))
    portfolio, _ = make_portfolio([Balance(holdings=[], deposit=1, orderable_cash=1)])
    portfolio.record_order(cycle_id="c1", code="005930", name="삼성전자", side="BUY",
                           order_type="market", qty=1, price=71_300, status="DRY_RUN")

    assert "005930" in portfolio.sync(now=early).bought_today


# --------------------------------------------------------------------------- #
# 사이클 내 상태 갱신 (apply_execution)
# --------------------------------------------------------------------------- #


def state_with(cash=5_000_000, positions=()):
    from logic.portfolio import PortfolioState, Position

    return PortfolioState(
        positions={p.code: p for p in positions}, cash=cash, deposit=cash,
        daily_pnl_pct=0.0, bought_today=set(), synced_at=NOW,
    )


def position_obj(code="005930", qty=10, avg=70_000, orderable=None):
    from logic.portfolio import Position

    return Position(code=code, name=f"종목{code}", qty=qty,
                    orderable_qty=qty if orderable is None else orderable,
                    avg_price=avg, current_price=avg, eval_amount=qty * avg,
                    pnl_amount=0.0, pnl_pct=0.0)


def test_buy_reduces_cash_and_adds_position():
    state = state_with(cash=1_000_000)
    state.apply_execution("005930", "삼성전자", "BUY", 10, 70_000)

    assert state.cash == 300_000
    assert state.position_count == 1
    assert state.holds("005930")
    assert state.total_invested == 700_000
    assert "005930" in state.bought_today, "당일 1회 제한이 같은 사이클에서 바로 걸려야 합니다"


def test_additional_buy_updates_average_price():
    state = state_with(cash=1_000_000, positions=[position_obj(qty=10, avg=70_000)])
    state.apply_execution("005930", "삼성전자", "BUY", 10, 80_000)

    position = state.get("005930")
    assert position.qty == 20
    assert position.avg_price == 75_000
    assert state.total_invested == 1_500_000


def test_sell_returns_cash_and_shrinks_position():
    state = state_with(cash=0, positions=[position_obj(qty=10, avg=70_000)])
    state.apply_execution("005930", "삼성전자", "SELL", 4, 75_000)

    assert state.cash == 300_000
    assert state.get("005930").qty == 6
    assert state.get("005930").orderable_qty == 6


def test_full_sell_removes_position():
    state = state_with(cash=0, positions=[position_obj(qty=10)])
    state.apply_execution("005930", "삼성전자", "SELL", 10, 70_000)

    assert state.position_count == 0 and not state.holds("005930")


def test_apply_execution_ignores_zero_quantity():
    state = state_with(cash=1_000_000)
    state.apply_execution("005930", "삼성전자", "BUY", 0, 70_000)
    assert state.cash == 1_000_000 and state.position_count == 0


def test_cash_never_goes_negative():
    state = state_with(cash=100_000)
    state.apply_execution("005930", "삼성전자", "BUY", 10, 70_000)
    assert state.cash == 0


# --------------------------------------------------------------------------- #
# 미체결 주문 재확인 (reconcile)
# --------------------------------------------------------------------------- #


def _insert_order(portfolio, *, order_no="ODNO1", status="PENDING", dry_run=0,
                  created="2026-09-08T09:35:00+09:00", side="BUY"):
    conn = connect(portfolio.db_path)
    conn.execute(
        """INSERT INTO orders (cycle_id, order_no, code, name, side, order_type, qty, price,
                               filled_qty, filled_price, status, dry_run, kis_env,
                               created_at, updated_at)
           VALUES ('c1', ?, '005930', '삼성전자', ?, 'market', 10, 71300, 0, 0, ?, ?, 'VTS', ?, ?)""",
        (order_no, side, status, dry_run, created, created),
    )
    conn.close()


def test_reconcile_marks_filled_orders(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled(qty=10, ordered=10)])
    _insert_order(portfolio)

    changes = portfolio.reconcile_open_orders(now=NOW)

    assert len(changes) == 1 and changes[0]["after"] == "FILLED"
    conn = connect(portfolio.db_path)
    row = conn.execute("SELECT status, filled_qty FROM orders").fetchone()
    conn.close()
    assert row["status"] == "FILLED" and row["filled_qty"] == 10


def test_reconcile_marks_partial(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled(qty=4, ordered=10)])
    _insert_order(portfolio)
    changes = portfolio.reconcile_open_orders(now=NOW)
    assert changes[0]["after"] == "PARTIAL"


def test_reconcile_skips_dry_run_orders(make_portfolio):
    portfolio, api = make_portfolio([Balance()], statuses=[filled()])
    _insert_order(portfolio, dry_run=1, status="DRY_RUN")
    assert portfolio.reconcile_open_orders(now=NOW) == []
    assert api.statuses, "DRY_RUN 주문은 조회조차 하지 않습니다"


def test_reconcile_skips_already_settled(make_portfolio):
    portfolio, api = make_portfolio([Balance()], statuses=[filled()])
    _insert_order(portfolio, status="FILLED")
    assert portfolio.reconcile_open_orders(now=NOW) == []
    assert api.statuses


def test_reconcile_ignores_other_days(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[filled()])
    _insert_order(portfolio, created="2026-09-01T09:35:00+09:00")
    assert portfolio.reconcile_open_orders(now=NOW) == []


def test_reconcile_survives_lookup_failure(make_portfolio):
    portfolio, _ = make_portfolio([Balance()], statuses=[KisApiError("조회 실패")])
    _insert_order(portfolio)
    assert portfolio.reconcile_open_orders(now=NOW) == []  # 예외를 올리지 않는다

    conn = connect(portfolio.db_path)
    assert conn.execute("SELECT status FROM orders").fetchone()["status"] == "PENDING"
    conn.close()


def test_reconcile_handles_vanished_order(make_portfolio):
    """장 마감으로 소멸한 주문(체결 0, 잔량 0)은 CANCELED 로 확정한다."""
    vanished = OrderStatus(order_no="ODNO1", code="005930", name="삼성전자", side="BUY",
                           order_qty=10, filled_qty=0, remain_qty=0, filled_price=0,
                           filled_amount=0, status="취소")
    portfolio, _ = make_portfolio([Balance()], statuses=[vanished])
    _insert_order(portfolio)
    assert portfolio.reconcile_open_orders(now=NOW)[0]["after"] == "CANCELED"
