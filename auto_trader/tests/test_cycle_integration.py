"""사이클 end-to-end 통합 테스트 (KIS·AI 전부 mock).

수집 → AI 합의 → 리스크 → 주문(DRY_RUN) → DB 기록 → 알림 요약까지 한 번에 검증한다.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from agents.base_agent import BaseAgent, run_agents_parallel
from agents.schemas import AgentDecision
from config.loader import ScheduleConfig
from logic.decision_maker import decide
from logic.portfolio import Portfolio
from logic.risk_manager import RiskManager
from tests.conftest import FakeResponse
from tests.test_market_data import StubApi as MarketStubApi
from trading.kis_api import Balance, Holding
from trading.order_executor import OrderExecutor
from utils.db import connect
from utils.notifier import Notifier

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 8, 10, 5, tzinfo=KST)

SCHEDULE = ScheduleConfig(
    universe_refresh=time(8, 30), first_cycle=time(9, 5), cycle_interval_min=30,
    last_new_buy=time(14, 30), eod_review=time(15, 10), daily_report=time(15, 40),
)


class CycleApi(MarketStubApi):
    """시세는 MarketStubApi, 잔고·주문은 여기서 대역."""

    def __init__(self, holdings=(), cash=5_000_000):
        super().__init__()
        self.holdings = list(holdings)
        self.cash = cash
        self.orders: list[dict] = []

    def get_balance(self):
        return Balance(holdings=self.holdings, deposit=self.cash, orderable_cash=self.cash)

    def place_order(self, *args, **kwargs):
        raise AssertionError("DRY_RUN 에서는 주문 API가 호출되면 안 됩니다")


class FixedAgent(BaseAgent):
    def __init__(self, name, action, ai, confidence=0.8, weight=20, ok=True):
        super().__init__(ai)
        self.name = name
        self._decision = AgentDecision(agent=name, action=action, confidence=confidence,
                                       weight_pct=weight, reason=f"{name} 판단", ok=ok)

    def analyze(self, payload):
        return self._decision

    def _call_model(self, system_prompt, user_prompt):  # 사용되지 않음
        raise NotImplementedError


class StubSession:
    def __init__(self):
        self.posts: list[dict] = []

    def post(self, url, json=None, timeout=None):
        self.posts.append(json)
        return FakeResponse({"ok": True})


@pytest.fixture
def cycle(settings_obj, tmp_path, monkeypatch):
    monkeypatch.setattr("logic.portfolio.time.sleep", lambda *_: None)

    def build(*, holdings=(), cash=5_000_000, actions=("BUY", "BUY"), ok=(True, True)):
        api = CycleApi(holdings=holdings, cash=cash)
        portfolio = Portfolio(settings_obj, api, db_path=tmp_path / "trader.db")
        risk = RiskManager(settings_obj.risk, SCHEDULE)
        session = StubSession()
        notifier = Notifier(settings_obj.env, session=session)
        executor = OrderExecutor(settings_obj, api, portfolio, risk, notifier)
        agents = [
            FixedAgent("claude", actions[0], settings_obj.ai, ok=ok[0]),
            FixedAgent("gemini", actions[1], settings_obj.ai, ok=ok[1]),
        ]
        return {"api": api, "portfolio": portfolio, "risk": risk, "executor": executor,
                "notifier": notifier, "session": session, "agents": agents,
                "settings": settings_obj}

    return build


def run_cycle(ctx, code="005930"):
    """scripts/test_cycle.py 와 동일한 순서로 한 종목을 처리한다."""
    from data_pipeline.market_data import collect

    settings = ctx["settings"]
    state = ctx["portfolio"].sync(now=NOW)
    position = state.get(code)
    snapshot = collect(code, ctx["api"], settings, holding=position, with_news=False, now=NOW)

    forced = ctx["risk"].check_forced_exit(position)
    decisions = run_agents_parallel(ctx["agents"], snapshot, settings.ai)
    final = decide(decisions["claude"], decisions["gemini"], state.holds(code),
                   settings.risk, settings.ai, take_profit=forced == "TAKE_PROFIT")

    risk_passed, risk_reason = True, ""
    if final.is_buy:
        amount = ctx["risk"].buy_amount(final.weight_pct, state)
        verdict = ctx["risk"].check_buy(code, amount, state, now=NOW)
        risk_passed, risk_reason = verdict.allowed, verdict.reason

    execution = None
    if risk_passed or final.is_sell:
        execution = ctx["executor"].execute(final, snapshot, state, cycle_id="c1")

    ctx["portfolio"].record_decision(cycle_id="c1", snapshot=snapshot, decisions=decisions,
                                     final=final, forced_exit=forced,
                                     risk_passed=risk_passed, risk_reason=risk_reason)
    ctx["notifier"].send_cycle_summary("10:05", [{
        "code": code, "name": snapshot["name"],
        "agents": " / ".join(d.summary() for d in decisions.values()),
        "final_action": final.action, "weight_pct": final.weight_pct,
        "risk_blocked": not risk_passed, "risk_reason": risk_reason,
        "ordered": bool(execution and execution.ordered),
        "side": execution.side if execution else "",
        "qty": execution.qty if execution else 0,
        "price": execution.price if execution else 0,
    }])
    return {"final": final, "execution": execution, "forced": forced,
            "risk_passed": risk_passed, "risk_reason": risk_reason}


def holding(code="005930", qty=12, avg=70_000, pnl_pct=1.86):
    return Holding(code=code, name="삼성전자", qty=qty, orderable_qty=qty, avg_price=avg,
                   current_price=76_000, eval_amount=qty * 76_000,
                   pnl_amount=qty * (76_000 - avg), pnl_pct=pnl_pct)


# --------------------------------------------------------------------------- #


def test_full_buy_cycle_in_dry_run(cycle):
    ctx = cycle(actions=("BUY", "BUY"))
    result = run_cycle(ctx)

    assert result["final"].action == "STRONG_BUY"
    assert result["risk_passed"]
    assert result["execution"].ordered and result["execution"].status == "DRY_RUN"
    assert result["execution"].qty == 13  # floor(1,000,000 / 76,000)

    conn = connect(ctx["portfolio"].db_path)
    order = conn.execute("SELECT * FROM orders").fetchone()
    decision = conn.execute("SELECT * FROM decisions").fetchone()
    conn.close()
    assert order["dry_run"] == 1 and order["side"] == "BUY" and order["qty"] == 13
    assert decision["final_action"] == "STRONG_BUY" and decision["risk_passed"] == 1
    assert decision["claude_action"] == "BUY" and decision["gemini_action"] == "BUY"

    summary = ctx["session"].posts[-1]["text"]
    assert "대상 1종목 / 주문 1건" in summary
    assert "STRONG_BUY" in summary and "매수 13주" in summary


def test_parse_failure_blocks_order(cycle):
    ctx = cycle(actions=("BUY", "BUY"), ok=(True, False))
    result = run_cycle(ctx)

    assert result["final"].action == "HOLD"
    assert result["execution"].ordered is False

    conn = connect(ctx["portfolio"].db_path)
    assert conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 0
    assert conn.execute("SELECT gemini_ok FROM decisions").fetchone()["gemini_ok"] == 0
    conn.close()


def test_risk_rejection_blocks_buy_and_is_reported(cycle):
    """가용현금은 충분하지만 당일 이미 매수한 종목이면 거부된다."""
    ctx = cycle(actions=("BUY", "BUY"))
    ctx["portfolio"].record_order(cycle_id="c0", code="005930", name="삼성전자", side="BUY",
                                  order_type="market", qty=1, price=76_000, status="DRY_RUN")
    # 기록 시각을 사이클 날짜에 맞춘다
    conn = connect(ctx["portfolio"].db_path)
    conn.execute("UPDATE orders SET created_at = ?", (NOW.isoformat(timespec="seconds"),))
    conn.close()

    result = run_cycle(ctx)

    assert result["final"].action == "STRONG_BUY", "AI는 매수를 원했지만"
    assert not result["risk_passed"], "리스크 규칙이 상위다"
    assert result["execution"] is None

    conn = connect(ctx["portfolio"].db_path)
    orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    decision = conn.execute("SELECT risk_passed, risk_reason FROM decisions").fetchone()
    conn.close()
    assert orders == 1, "새 주문은 기록되지 않아야 합니다"
    assert decision["risk_passed"] == 0 and "당일 이미 매수" in decision["risk_reason"]
    assert "리스크 거부" in ctx["session"].posts[-1]["text"]


def test_stop_loss_position_is_detected(cycle):
    ctx = cycle(holdings=[holding(pnl_pct=-6.5)], actions=("HOLD", "HOLD"))
    result = run_cycle(ctx)
    assert result["forced"] == "STOP_LOSS"


def test_take_profit_with_broken_ai_sells_half(cycle):
    ctx = cycle(holdings=[holding(qty=12, pnl_pct=12.0)], actions=("HOLD", "HOLD"), ok=(False, False))
    result = run_cycle(ctx)

    assert result["forced"] == "TAKE_PROFIT"
    assert result["final"].action == "REDUCE"
    assert result["execution"].qty == 6, "보유 12주의 절반"


def test_unanimous_sell_liquidates_holding(cycle):
    ctx = cycle(holdings=[holding(qty=12)], actions=("SELL", "SELL"))
    result = run_cycle(ctx)

    assert result["final"].action == "SELL_ALL"
    assert result["execution"].side == "SELL" and result["execution"].qty == 12

    conn = connect(ctx["portfolio"].db_path)
    order = conn.execute("SELECT side, qty, dry_run FROM orders").fetchone()
    conn.close()
    assert order["side"] == "SELL" and order["qty"] == 12 and order["dry_run"] == 1


def test_sell_signal_without_holding_does_nothing(cycle):
    ctx = cycle(actions=("SELL", "SELL"))
    result = run_cycle(ctx)

    assert result["final"].action == "HOLD"
    conn = connect(ctx["portfolio"].db_path)
    assert conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"] == 0
    conn.close()


def test_position_state_reaches_snapshot_and_db(cycle):
    ctx = cycle(holdings=[holding(qty=12)], actions=("HOLD", "HOLD"))
    run_cycle(ctx)

    conn = connect(ctx["portfolio"].db_path)
    decision = conn.execute("SELECT holding, snapshot_json FROM decisions").fetchone()
    position = conn.execute("SELECT qty, avg_price FROM positions").fetchone()
    conn.close()
    assert decision["holding"] == 1
    assert '"holding": true' in decision["snapshot_json"]
    assert position["qty"] == 12 and position["avg_price"] == 70_000
