"""스케줄러 조립 테스트 — 잡 등록, 휴장일 스킵, 연속 실패 중단, 시그널 처리."""

from __future__ import annotations

import signal
import threading
from datetime import date, datetime, time as dt_time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import main as main_module
from logic.decision_maker import FinalDecision
from main import MAX_CONSECUTIVE_FAILURES, TradingBot, cycle_times
from trading.kis_api import KisApiError

KST = ZoneInfo("Asia/Seoul")


# --------------------------------------------------------------------------- #
# 사이클 시각 계산
# --------------------------------------------------------------------------- #


def test_cycle_times_from_first_cycle_to_three_pm():
    times = cycle_times(dt_time(9, 5), 30)
    assert times[0] == dt_time(9, 5)
    assert times[-1] == dt_time(14, 35), "15:00 을 넘는 시각은 포함하지 않습니다"
    assert len(times) == 12


def test_cycle_times_includes_boundary():
    assert cycle_times(dt_time(9, 0), 60)[-1] == dt_time(15, 0), "정확히 15:00 은 포함"


def test_cycle_times_with_short_interval():
    times = cycle_times(dt_time(14, 0), 15)
    assert times == [dt_time(14, 0), dt_time(14, 15), dt_time(14, 30),
                     dt_time(14, 45), dt_time(15, 0)]


# --------------------------------------------------------------------------- #
# 테스트용 봇
# --------------------------------------------------------------------------- #


@pytest.fixture
def bot(settings_obj, tmp_path, monkeypatch):
    """외부 연동을 전부 대역으로 바꾼 TradingBot."""
    monkeypatch.setattr(main_module, "TokenManager", lambda env, path: SimpleNamespace(
        get_access_token=lambda **kw: "TOKEN"))
    monkeypatch.setattr(main_module, "KisApi", lambda env, auth: SimpleNamespace())
    monkeypatch.setattr(main_module, "ClaudeAgent", lambda env, ai: SimpleNamespace(name="claude"))
    monkeypatch.setattr(main_module, "GeminiAgent", lambda env, ai: SimpleNamespace(name="gemini"))

    sent: list[str] = []
    monkeypatch.setattr(main_module, "Notifier", lambda env: SimpleNamespace(
        send=lambda text: sent.append(text) or True,
        send_startup=lambda n: sent.append(f"startup:{n}") or True,
        send_cycle_summary=lambda label, rows: sent.append(f"summary:{label}:{len(list(rows))}") or True,
        send_error=lambda exc, context="": sent.append(f"error:{context}:{exc}") or True,
        send_fatal=lambda message: sent.append(f"fatal:{message}") or True,
        send_daily_report=lambda report, **kw: sent.append(f"report:{report.get('total_pnl_pct')}") or True,
        send_alert=lambda title, lines, **kw: sent.append(f"alert:{title}") or True,
    ))

    synced: list[datetime] = []
    state = SimpleNamespace(positions={}, position_count=0, cash=5_000_000, daily_pnl_pct=0.0,
                            get=lambda code: None, holds=lambda code: False,
                            apply_execution=lambda *a, **kw: None)
    monkeypatch.setattr(main_module, "Portfolio", lambda settings, api, db_path=None: SimpleNamespace(
        sync=lambda now=None: (synced.append(now), state)[1],
        record_decision=lambda **kw: 1,
        reconcile_open_orders=lambda now=None: [],
        db_path=tmp_path / "trader.db",
    ))
    monkeypatch.setattr(main_module, "OrderExecutor",
                        lambda settings, api, portfolio, risk, notifier: SimpleNamespace(
                            execute=lambda *a, **kw: SimpleNamespace(ordered=False, side="", qty=0, price=0)))

    instance = TradingBot(settings_obj)
    instance.sent = sent
    instance.synced = synced
    instance.state = state
    return instance


def stub_processing(bot, monkeypatch, *, action="HOLD", raises=None):
    """_process_code 를 단순화한다."""

    def fake_process(code, state, cycle_id, now):
        if raises:
            raise raises
        return {"code": code, "name": code, "final_action": action, "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)


# --------------------------------------------------------------------------- #
# 휴장일
# --------------------------------------------------------------------------- #


def test_cycle_skipped_on_holiday(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: False)
    assert bot.run_cycle() == []
    assert bot.synced == [], "휴장일에는 잔고 조회조차 하지 않습니다"


def test_universe_refresh_skipped_on_holiday(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: False)
    before = list(bot.universe)
    assert bot.refresh_universe() == before


def test_daily_report_skipped_on_holiday(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: False)
    assert bot.daily_report() == {}


# --------------------------------------------------------------------------- #
# 사이클 진행
# --------------------------------------------------------------------------- #


def test_cycle_processes_universe_and_sends_summary(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    stub_processing(bot, monkeypatch)
    bot.universe = ["005930", "000660"]

    results = bot.run_cycle(label="10:05")
    assert [row["code"] for row in results] == ["005930", "000660"]
    assert "summary:10:05:2" in bot.sent


def test_one_code_failure_does_not_stop_cycle(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    bot.universe = ["005930", "000660"]

    def fake_process(code, state, cycle_id, now):
        if code == "005930":
            raise KisApiError("시세 조회 실패")
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)

    results = bot.run_cycle()
    assert len(results) == 2
    assert results[0]["error"] and results[1]["final_action"] == "HOLD"
    assert any(text.startswith("error:") for text in bot.sent)
    assert bot.consecutive_failures == 0, "종목 단위 실패는 사이클 실패가 아닙니다"


def test_eod_review_targets_holdings_only(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    processed: list[str] = []

    def fake_process(code, state, cycle_id, now):
        processed.append(code)
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)
    bot.universe = ["005930", "000660", "035420"]
    bot.state.positions = {"000660": object()}

    bot.eod_review()
    assert processed == ["000660"], "보유 종목만 재판단합니다"


def test_eod_review_without_holdings_is_noop(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    stub_processing(bot, monkeypatch)
    bot.state.positions = {}
    assert bot.eod_review() == []


# --------------------------------------------------------------------------- #
# 연속 실패 → 중단
# --------------------------------------------------------------------------- #


def test_three_consecutive_failures_stop_the_scheduler(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    shutdowns: list[bool] = []
    bot.scheduler = SimpleNamespace(shutdown=lambda wait=True: shutdowns.append(True),
                                    get_jobs=lambda: [])

    def failing_sync(now=None):
        raise KisApiError("잔고 조회 실패")

    bot.portfolio.sync = failing_sync

    for expected in range(1, MAX_CONSECUTIVE_FAILURES + 1):
        bot.run_cycle()
        assert bot.consecutive_failures == expected

    assert shutdowns == [True], "3회 연속 실패 시 스케줄러를 중단합니다"
    assert any(text.startswith("fatal:") for text in bot.sent)


def test_failure_counter_resets_after_success(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    stub_processing(bot, monkeypatch)
    bot.universe = ["005930"]

    original_sync = bot.portfolio.sync
    bot.portfolio.sync = lambda now=None: (_ for _ in ()).throw(KisApiError("일시 실패"))
    bot.run_cycle()
    assert bot.consecutive_failures == 1

    bot.portfolio.sync = original_sync
    bot.run_cycle()
    assert bot.consecutive_failures == 0


# --------------------------------------------------------------------------- #
# 시그널 처리
# --------------------------------------------------------------------------- #


def test_signal_waits_for_running_cycle(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    shutdowns: list[bool] = []
    bot.scheduler = SimpleNamespace(shutdown=lambda wait=True: shutdowns.append(True),
                                    get_jobs=lambda: [])

    cycle_entered = threading.Event()
    allow_finish = threading.Event()

    def slow_process(code, state, cycle_id, now):
        cycle_entered.set()
        allow_finish.wait(2)
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", slow_process)
    bot.universe = ["005930"]

    worker = threading.Thread(target=bot.run_cycle)
    worker.start()
    assert cycle_entered.wait(2)

    bot.handle_signal(signal.SIGTERM, None)
    assert bot._shutting_down is True
    assert shutdowns == [], "사이클이 끝나기 전에 종료하면 안 됩니다"

    allow_finish.set()
    worker.join(3)
    for _ in range(50):  # 종료 스레드가 락을 얻을 때까지
        if shutdowns:
            break
        threading.Event().wait(0.05)
    assert shutdowns == [True]
    assert any("종료합니다" in text for text in bot.sent)


def test_new_cycle_is_refused_while_shutting_down(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    stub_processing(bot, monkeypatch)
    bot._shutting_down = True
    assert bot.run_cycle() == []


def test_second_signal_exits_immediately(bot):
    bot._shutting_down = True
    with pytest.raises(SystemExit):
        bot.handle_signal(signal.SIGINT, None)


# --------------------------------------------------------------------------- #
# 스케줄 등록
# --------------------------------------------------------------------------- #


def test_scheduler_registers_all_jobs(bot):
    scheduler = bot.build_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}

    assert "universe_refresh" in job_ids
    assert "eod_review" in job_ids
    assert "daily_report" in job_ids
    cycles = {job_id for job_id in job_ids if job_id.startswith("cycle_")}
    assert len(cycles) == 12
    assert "cycle_0905" in cycles and "cycle_1435" in cycles


def test_cycle_jobs_do_not_overlap(bot):
    scheduler = bot.build_scheduler()
    for job in scheduler.get_jobs():
        if job.id.startswith("cycle_") or job.id == "eod_review":
            assert job.max_instances == 1, "사이클이 겹쳐 실행되면 안 됩니다"
            assert job.coalesce is True


def test_jobs_are_weekday_only_in_kst(bot):
    scheduler = bot.build_scheduler()
    trigger = next(job.trigger for job in scheduler.get_jobs() if job.id == "cycle_0905")
    assert str(trigger.timezone) == "Asia/Seoul"
    assert "day_of_week='mon-fri'" in str(trigger)


# --------------------------------------------------------------------------- #
# 일간 리포트
# --------------------------------------------------------------------------- #


def test_daily_report_uses_db_and_notifies(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    monkeypatch.setattr(main_module, "build_daily_report",
                        lambda db_path: {"total_pnl_pct": 1.5, "buy_count": 2,
                                         "sell_count": 1, "position_count": 3})
    report = bot.daily_report()
    assert report["total_pnl_pct"] == 1.5
    assert "report:1.5" in bot.sent


# --------------------------------------------------------------------------- #
# 리뷰 지적 사항 회귀 테스트
# --------------------------------------------------------------------------- #


def test_holdings_are_always_processed_first(bot, monkeypatch):
    """유니버스에 없는 보유 종목도 매 사이클 손절 판단을 받아야 한다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    processed: list[str] = []

    def fake_process(code, state, cycle_id, now):
        processed.append(code)
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)
    bot.universe = ["005930", "000660"]
    bot.state.positions = {"068270": object()}  # 유니버스 밖 보유 종목

    bot.run_cycle()
    assert processed[0] == "068270", "보유 종목을 먼저 봐야 합니다"
    assert processed == ["068270", "005930", "000660"]


def test_held_code_in_universe_is_not_duplicated(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    processed: list[str] = []
    monkeypatch.setattr(bot, "_process_code", lambda code, *a: (
        processed.append(code), {"code": code, "name": code, "final_action": "HOLD", "ordered": False})[1])
    bot.universe = ["005930", "000660"]
    bot.state.positions = {"005930": object()}

    bot.run_cycle()
    assert processed == ["005930", "000660"]


def test_executed_order_updates_state_within_cycle(settings_obj, bot, monkeypatch):
    """앞 종목 매수로 줄어든 현금을 뒤 종목의 리스크 검사가 봐야 한다."""
    from logic.portfolio import PortfolioState

    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)

    real_state = PortfolioState(positions={}, cash=1_000_000, deposit=1_000_000)
    bot.portfolio.sync = lambda now=None: real_state
    bot.universe = ["005930", "000660"]

    seen_cash: list[float] = []

    def fake_process(code, state, cycle_id, now):
        seen_cash.append(state.cash)
        state.apply_execution(code, code, "BUY", 10, 70_000)
        return {"code": code, "name": code, "final_action": "STRONG_BUY", "ordered": True}

    monkeypatch.setattr(bot, "_process_code", fake_process)
    bot.run_cycle()

    assert seen_cash == [1_000_000, 300_000], "두 번째 종목은 줄어든 현금을 봐야 합니다"


def test_universe_refresh_passes_balance(bot, monkeypatch):
    """유니버스 갱신이 실제 잔고를 넘겨 보유 종목을 포함시켜야 한다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    sentinel = object()
    bot.api.get_balance = lambda: sentinel
    captured: dict = {}

    def fake_build(api, settings, balance=None):
        captured["balance"] = balance
        return ["005930"]

    monkeypatch.setattr(main_module, "build_universe", fake_build)
    bot.refresh_universe()
    assert captured["balance"] is sentinel


def test_universe_refresh_survives_balance_failure(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    bot.api.get_balance = lambda: (_ for _ in ()).throw(KisApiError("잔고 조회 실패"))
    monkeypatch.setattr(main_module, "build_universe", lambda api, settings, balance=None: ["005930"])

    assert bot.refresh_universe() == ["005930"]


# --------------------------------------------------------------------------- #
# 손절 감시 (guard_cycle) — 정규 사이클 사이의 급락을 잡는다
# --------------------------------------------------------------------------- #


def _position(code="005930", *, pnl_pct=-8.0, qty=10, price=70_000):
    from logic.portfolio import Position

    return Position(
        code=code, name=f"종목{code}", qty=qty, orderable_qty=qty,
        avg_price=price / (1 + pnl_pct / 100), current_price=price,
        eval_amount=qty * price, pnl_amount=qty * price * pnl_pct / 100, pnl_pct=pnl_pct,
    )


@pytest.fixture
def guard_bot(bot, monkeypatch):
    """장중이고, 주문은 성공한다고 가정."""
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: True)
    orders: list[tuple] = []

    def execute(final, snapshot, state, cycle_id=""):
        orders.append((snapshot["code"], final.action, final.reason))
        return SimpleNamespace(ordered=True, side="SELL", qty=10,
                               price=snapshot["price"]["current"])

    bot.executor.execute = execute
    bot.orders = orders
    return bot


def _hold(bot, *positions):
    bot.state.positions = {p.code: p for p in positions}


def test_guard_sells_position_below_stop_loss(guard_bot):
    _hold(guard_bot, _position(pnl_pct=-8.0))  # 손절선 -5%
    results = guard_bot.guard_cycle()

    assert len(results) == 1 and results[0]["ordered"]
    assert guard_bot.orders == [("005930", "SELL_ALL", "손절선 도달(감시 청산)")]
    assert any(text.startswith("alert:🛑") for text in guard_bot.sent)


def test_guard_leaves_healthy_positions_alone(guard_bot):
    _hold(guard_bot, _position(pnl_pct=-2.0), _position("000660", pnl_pct=7.0))
    assert guard_bot.guard_cycle() == []
    assert guard_bot.orders == []


def test_guard_does_not_act_on_take_profit(guard_bot):
    """익절은 AI 재판단이 필요하다 — 감시는 손절만 본다."""
    _hold(guard_bot, _position(pnl_pct=15.0))  # 익절선 10% 초과
    assert guard_bot.guard_cycle() == []
    assert guard_bot.orders == []


def test_guard_sells_only_the_breached_position(guard_bot):
    _hold(guard_bot, _position(pnl_pct=-9.0), _position("000660", pnl_pct=1.0))
    guard_bot.guard_cycle()
    assert [code for code, _, _ in guard_bot.orders] == ["005930"]


def test_guard_skipped_outside_market_hours(guard_bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: False)
    _hold(guard_bot, _position(pnl_pct=-20.0))
    assert guard_bot.guard_cycle() == []
    assert guard_bot.synced == [], "장이 닫혀 있으면 잔고 조회조차 하지 않습니다"


def test_guard_skipped_while_stopped(guard_bot):
    guard_bot.stop_flag.set("수동 정지")
    _hold(guard_bot, _position(pnl_pct=-20.0))
    assert guard_bot.guard_cycle() == []
    assert guard_bot.orders == []


def test_guard_skipped_when_regular_cycle_is_running(guard_bot):
    """정규 사이클과 겹쳐 같은 종목에 매도를 두 번 내면 안 된다."""
    _hold(guard_bot, _position(pnl_pct=-20.0))
    guard_bot._cycle_lock.acquire()
    try:
        assert guard_bot.guard_cycle() == []
        assert guard_bot.orders == []
    finally:
        guard_bot._cycle_lock.release()


def test_guard_releases_lock_after_running(guard_bot):
    _hold(guard_bot, _position(pnl_pct=-8.0))
    guard_bot.guard_cycle()
    assert guard_bot._cycle_lock.acquire(blocking=False), "락이 반납되지 않았습니다"
    guard_bot._cycle_lock.release()


def test_guard_survives_sync_failure(guard_bot, monkeypatch):
    def boom(now=None):
        raise KisApiError("잔고 조회 실패")

    guard_bot.portfolio.sync = boom
    assert guard_bot.guard_cycle() == []  # 예외가 새어 나가면 스케줄러가 죽는다
    assert guard_bot._cycle_lock.acquire(blocking=False)
    guard_bot._cycle_lock.release()


def test_guard_reports_failed_order(guard_bot):
    guard_bot.executor.execute = lambda *a, **kw: SimpleNamespace(
        ordered=False, side="SELL", qty=0, price=0)
    _hold(guard_bot, _position(pnl_pct=-8.0))
    results = guard_bot.guard_cycle()
    assert results and not results[0]["ordered"]
    assert any(text.startswith("alert:🛑") for text in guard_bot.sent)


def test_guard_job_registered_on_scheduler(bot):
    scheduler = bot.build_scheduler()
    job = scheduler.get_job("guard_cycle")
    assert job is not None, "손절 감시 잡이 등록되지 않았습니다"
    assert job.max_instances == 1


def test_guard_job_excluded_from_next_cycle_display(bot):
    """'다음 사이클' 표시는 정규 사이클만 센다."""
    bot.build_scheduler()
    assert "guard" not in bot._next_run_at()
