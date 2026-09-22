"""스케줄러 조립 테스트 — 잡 등록, 휴장일 스킵, 연속 실패 중단, 시그널 처리."""

from __future__ import annotations

import signal
import threading
from datetime import date, datetime, time as dt_time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import main as main_module
from agents.schemas import AgentDecision
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
        send_startup=lambda n, **kw: sent.append(f"startup:{n}") or True,
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
    # 사이클은 이제 시세를 **먼저 전부** 모은 뒤 종목별 처리로 넘어간다(상대평가).
    # 여기 테스트들은 그 뒤의 흐름을 보므로 수집은 대역으로 둔다.
    instance._collect_snapshot = lambda code, state, now: {
        "code": code, "name": code, "price": {"current": 70_000}}
    return instance


def stub_processing(bot, monkeypatch, *, action="HOLD", raises=None):
    """_process_code 를 단순화한다. AI 호출도 함께 막는다."""
    monkeypatch.setattr(main_module, "run_agents_batch", lambda agents, snaps, ai: {})

    def fake_process(code, state, cycle_id, now, **_):
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

    def fake_process(code, state, cycle_id, now, **_):
        if code == "005930":
            raise KisApiError("시세 조회 실패")
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)

    results = bot.run_cycle()
    assert len(results) == 2
    assert results[0]["error"] and results[1]["final_action"] == "HOLD"
    # 사이클 요약에 '(오류) …' 로 실리므로 따로 울리지 않는다 — 같은 내용을
    # 두 번 보내면 알림이 소음이 되어 정작 봐야 할 것을 놓친다.
    assert not any(text.startswith("error:") for text in bot.sent)
    assert any(text.startswith("summary:") for text in bot.sent)
    assert bot.consecutive_failures == 0, "종목 단위 실패는 사이클 실패가 아닙니다"


def test_eod_review_targets_holdings_only(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    processed: list[str] = []

    def fake_process(code, state, cycle_id, now, **_):
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

    def slow_process(code, state, cycle_id, now, **_):
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

    def fake_process(code, state, cycle_id, now, **_):
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
    monkeypatch.setattr(bot, "_process_code", lambda code, *a, **kw: (
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

    def fake_process(code, state, cycle_id, now, **_):
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
    assert guard_bot.orders == [("005930", "SELL_ALL", "손절 감시 청산")]
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


# --------------------------------------------------------------------------- #
# 텔레그램 리모컨 명령
# --------------------------------------------------------------------------- #


def test_stop_command_sets_the_flag(bot):
    reply = bot._cmd_stop()
    assert bot.stop_flag.is_set()
    assert "긴급 정지" in reply and "손절" in reply


def test_resume_command_clears_the_flag(bot):
    bot.stop_flag.set("테스트")
    reply = bot._cmd_resume()
    assert not bot.stop_flag.is_set() and "해제" in reply


def test_resume_when_already_running(bot):
    assert "이미 가동 중" in bot._cmd_resume()


def test_status_command_reports_the_mode(bot):
    reply = bot._cmd_status()
    assert "모의투자(VTS)" in reply or "실전(REAL)" in reply


# --- 폰에서 보는 화면 ----------------------------------------------------------- #
#
# 대시보드는 PC 에만 있다. 장중에 자리를 비우면 '지금 잘 돌고 있나' 를 확인할
# 길이 텔레그램뿐이므로, 상단 타일이 답하는 것은 여기서도 답해야 한다.

def test_status_answers_the_questions_the_dashboard_tiles_answer(bot):
    reply = bot._cmd_status()
    for expected in ("당일", "평가자산", "보유", "오늘 주문", "AI", "다음 사이클"):
        assert expected in reply, f"{expected} 가 빠졌습니다"


def test_status_says_loudly_when_orders_are_not_being_sent(bot):
    """DRY_RUN 은 화면이 평소와 똑같이 돌아서, 말해 주지 않으면 모른다."""
    assert "DRY_RUN" in bot._cmd_status()


def test_status_leads_with_the_stop_when_stopped(bot):
    bot.stop_flag.set("테스트 정지")
    try:
        reply = bot._cmd_status()
        assert "정지됨" in reply and "테스트 정지" in reply
        assert "손절·익절은 계속 동작합니다" in reply
    finally:
        bot.stop_flag.clear()


def test_positions_shows_how_far_the_machine_will_let_it_run(bot, monkeypatch):
    """수익률만 보면 '더 둬도 되나' 를 판단할 수 없다."""
    monkeypatch.setattr(
        "dashboard.queries.positions",
        lambda *a, **k: [{"name": "삼성전자", "code": "005930", "qty": 3,
                          "avg_price": 269_500, "current_price": 274_500,
                          "eval_amount": 823_500, "pnl_amount": 15_000, "pnl_pct": 1.86,
                          "to_stop_loss": 6.86, "to_take_profit": 8.14,
                          "trailing_stop": 0}])
    reply = bot._cmd_positions()
    assert "삼성전자" in reply and "+1.86%" in reply
    assert "손절까지 6.9%p" in reply and "익절까지 8.1%p" in reply
    assert "269,500" in reply and "274,500" in reply


def test_positions_is_plain_when_there_is_nothing(bot, monkeypatch):
    monkeypatch.setattr("dashboard.queries.positions", lambda *a, **k: [])
    assert bot._cmd_positions() == "보유 종목이 없습니다."


def test_decisions_answers_why_nothing_was_bought(bot, monkeypatch):
    """이번 프로그램에서 가장 자주 나온 질문이다."""
    monkeypatch.setattr(
        "dashboard.queries.recent_decisions",
        lambda *a, **k: [
            {"name": "삼성전자", "code": "005930", "final_action": "BUY_SMALL",
             "outcome": "매수 3주 @269,500", "created_at": "2026-09-21T13:05:00+09:00"},
            {"name": "SK하이닉스", "code": "000660", "final_action": "BUY_SMALL",
             "risk_reason": "당일 이미 매수한 종목", "outcome": "",
             "created_at": "2026-09-21T13:05:00+09:00"},
        ])
    reply = bot._cmd_decisions()
    assert "삼성전자: BUY_SMALL → 매수 3주" in reply
    assert "막힘(당일 이미 매수한 종목)" in reply
    assert "세 AI 가 모두 동의해야" in reply


def test_a_broken_query_does_not_take_the_command_down(bot, monkeypatch):
    """폰 명령 하나가 터져도 매매는 계속 돌아야 한다."""
    def boom(*a, **k):
        raise RuntimeError("DB 잠김")

    monkeypatch.setattr("dashboard.queries.overview", boom)
    monkeypatch.setattr("dashboard.queries.positions", boom)
    monkeypatch.setattr("dashboard.queries.recent_decisions", boom)

    assert "모의투자(VTS)" in bot._cmd_status()      # 앞부분은 그대로 나온다
    assert bot._cmd_positions() == "보유 종목이 없습니다."
    assert "읽지 못했습니다" in bot._cmd_decisions()


def test_no_command_can_place_an_order(bot):
    """폰으로 할 수 있는 것은 보기와 멈추기뿐이다."""
    import inspect

    handlers = [name for name in dir(bot) if name.startswith("_cmd_")]
    assert set(handlers) == {"_cmd_status", "_cmd_positions", "_cmd_today",
                             "_cmd_decisions", "_cmd_orders", "_cmd_stop",
                             "_cmd_resume", "_cmd_help"}
    for name in handlers:
        source = inspect.getsource(getattr(bot, name))
        assert "place_order" not in source and "execute" not in source


def test_status_never_leaks_keys(bot):
    reply = bot._cmd_status()
    for secret in (bot.settings.env.kis_app_secret, bot.settings.env.anthropic_api_key):
        if secret:
            assert secret not in reply


def test_startup_survives_balance_failure(bot, monkeypatch):
    """장 마감 뒤 잔고 조회가 막혀도 프로세스는 살아 있어야 한다.

    여기서 죽으면 다음 날 09:05 사이클까지 함께 사라진다.
    """
    from trading.kis_api import KisApiError

    boom = KisApiError("balance 서버 오류 (HTTP 500) [40310000] 모의투자 미신청 계좌입니다")
    monkeypatch.setattr(bot.portfolio, "sync", lambda now=None: (_ for _ in ()).throw(boom))
    monkeypatch.setattr(bot, "refresh_universe", lambda: [])

    bot.startup()  # 예외가 새어 나오면 실패다

    from utils.db import get_bot_state

    assert get_bot_state(bot.settings.paths["db"])["status"] == "RUNNING"
    assert any("기동 시 잔고 조회" in line for line in bot.sent)
    bot.lock.release()


def test_cycle_skips_when_balance_is_unreadable(bot, monkeypatch):
    """잔고를 모르면 주문은 한 건도 나가면 안 된다."""
    from trading.kis_api import KisApiError

    monkeypatch.setattr(bot.portfolio, "sync",
                        lambda now=None: (_ for _ in ()).throw(KisApiError("balance 서버 오류")))
    called: list[str] = []
    monkeypatch.setattr(bot, "_process_code",
                        lambda *a, **kw: called.append("x") or {})

    assert bot.run_cycle(label="테스트") == []
    assert not called, "잔고를 모르는 채 종목을 처리했습니다"


def test_bot_shuts_down_on_request_file(bot, monkeypatch, tmp_path):
    """대시보드의 '봇 종료' 는 신호가 아니라 파일로 부탁한다."""
    import time as _time

    from utils.runtime import shutdown_path

    monkeypatch.setattr(main_module, "SHUTDOWN_POLL_SEC", 0.01)
    done: list[str] = []
    monkeypatch.setattr(bot, "_graceful_shutdown", lambda: done.append("stopped"))

    bot._watch_shutdown_request()
    request = shutdown_path(bot.settings.paths["data"])
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text("dashboard", encoding="utf-8")

    deadline = _time.monotonic() + 3
    while _time.monotonic() < deadline and not done:
        _time.sleep(0.01)

    assert done == ["stopped"], "종료 요청 파일을 보고도 내려가지 않았습니다"
    assert not request.exists(), "처리한 요청 파일은 지워야 합니다"


def test_stale_request_file_does_not_kill_a_fresh_start(bot, monkeypatch):
    """지난번에 남은 요청으로 방금 뜬 봇이 죽으면 안 된다."""
    import time as _time

    from utils.runtime import shutdown_path

    monkeypatch.setattr(main_module, "SHUTDOWN_POLL_SEC", 0.01)
    request = shutdown_path(bot.settings.paths["data"])
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text("stale", encoding="utf-8")

    done: list[str] = []
    monkeypatch.setattr(bot, "_graceful_shutdown", lambda: done.append("stopped"))

    bot._watch_shutdown_request()
    _time.sleep(0.2)
    assert not done, "묵은 요청 파일을 보고 내려갔습니다"


def test_shutdown_request_from_before_startup_is_ignored(bot, monkeypatch):
    """기동에 몇 초 걸리는 사이 남아 있던 옛 요청으로 죽으면 안 된다."""
    import os
    import time as _time

    from utils.runtime import shutdown_path

    monkeypatch.setattr(main_module, "SHUTDOWN_POLL_SEC", 0.01)
    request = shutdown_path(bot.settings.paths["data"])
    request.parent.mkdir(parents=True, exist_ok=True)

    done: list[str] = []
    monkeypatch.setattr(bot, "_graceful_shutdown", lambda: done.append("stopped"))
    bot._watch_shutdown_request()

    # 감시가 시작된 '뒤' 에 만들되, 시각은 그 이전으로 돌려 둔다.
    request.write_text("stale", encoding="utf-8")
    old = _time.time() - 600
    os.utime(request, (old, old))

    _time.sleep(0.2)
    assert not done, "기동 전에 남은 요청으로 내려갔습니다"
    assert not request.exists(), "묵은 요청 파일을 치우지 않았습니다"


# --- 상대평가: 후보를 한꺼번에 본다 ------------------------------------------ #

def _with_ai(bot, **changes):
    from dataclasses import replace
    bot.settings = replace(bot.settings, ai=replace(bot.settings.ai, **changes))


def test_cycle_shows_every_candidate_at_once(bot, monkeypatch):
    """종목별로 따로 물으면 절대평가가 된다 — 한 번에 보여줘야 비교가 된다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    seen: list[list[str]] = []
    stub_processing(bot, monkeypatch)        # run_agents_batch 도 덮으므로 먼저 부른다
    monkeypatch.setattr(main_module, "run_agents_batch",
                        lambda agents, snaps, ai: seen.append([s["code"] for s in snaps]) or {})
    bot.universe = ["005930", "000660", "035420"]

    bot.run_cycle()
    assert seen == [["005930", "000660", "035420"]]


def test_forced_exits_are_not_sent_to_the_ai(bot, monkeypatch):
    """손절·트레일링은 되묻는 사이에 더 밀린다. 물어볼 후보에서 빠져야 한다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    seen: list[list[str]] = []
    stub_processing(bot, monkeypatch)        # run_agents_batch 도 덮으므로 먼저 부른다
    monkeypatch.setattr(main_module, "run_agents_batch",
                        lambda agents, snaps, ai: seen.append([s["code"] for s in snaps]) or {})
    monkeypatch.setattr(bot.risk, "check_forced_exit",
                        lambda position: "STOP_LOSS" if position == "hit" else None)
    bot.state.get = lambda code: "hit" if code == "005930" else None
    bot.universe = ["005930", "000660", "035420"]

    bot.run_cycle()
    assert seen == [["000660", "035420"]], "손절 대상까지 물으면 토큰만 쓰고 늦어집니다"


def test_a_single_candidate_skips_the_comparison(bot, monkeypatch):
    """비교할 상대가 없으면 예전 방식이 그대로 낫다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    called: list[int] = []
    monkeypatch.setattr(main_module, "run_agents_batch",
                        lambda agents, snaps, ai: called.append(1) or {})
    stub_processing(bot, monkeypatch)
    bot.universe = ["005930"]

    bot.run_cycle()
    assert not called


def test_comparison_can_be_turned_off(bot, monkeypatch):
    """매매 방식을 바꾸는 설정이다 — 코드를 고치지 않고 되돌릴 수 있어야 한다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    called: list[int] = []
    monkeypatch.setattr(main_module, "run_agents_batch",
                        lambda agents, snaps, ai: called.append(1) or {})
    _with_ai(bot, compare_candidates=False)
    stub_processing(bot, monkeypatch)
    bot.universe = ["005930", "000660", "035420"]

    bot.run_cycle()
    assert not called


def test_batch_votes_reach_the_per_code_step(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    votes = {"005930": {"claude": AgentDecision.hold("claude", "")},
             "000660": {"claude": AgentDecision.hold("claude", "")}}
    monkeypatch.setattr(main_module, "run_agents_batch", lambda agents, snaps, ai: votes)

    got: list[dict | None] = []

    def fake_process(code, state, cycle_id, now, **kw):
        got.append(kw.get("decisions"))
        return {"code": code, "name": code, "final_action": "HOLD", "ordered": False}

    monkeypatch.setattr(bot, "_process_code", fake_process)
    bot.universe = ["005930", "000660"]

    bot.run_cycle()
    assert got == [votes["005930"], votes["000660"]]


def test_per_code_call_is_not_repeated_when_batch_answered(bot, monkeypatch):
    """배치가 답했는데 종목별로 또 부르면 비용이 두 배가 된다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    called: list[str] = []
    monkeypatch.setattr(main_module, "run_agents_parallel",
                        lambda agents, snapshot, ai: called.append(snapshot["code"]) or {})
    monkeypatch.setattr(bot, "_collect_snapshot",
                        lambda code, state, now: {"code": code, "name": code,
                                                  "price": {"current": 70_000}})
    vote = {"claude": AgentDecision.hold("claude", "")}
    bot._process_code("005930", bot.state, "c1", datetime.now(KST),
                      snapshot={"code": "005930", "name": "005930"},
                      forced=None, decisions=vote)
    assert not called

    bot._process_code("005930", bot.state, "c1", datetime.now(KST),
                      snapshot={"code": "005930", "name": "005930"},
                      forced=None, decisions=None)
    assert called == ["005930"], "판단이 없으면 종목별로 되물어야 합니다"


# --- 판단이 주문까지 갔는지 남긴다 ------------------------------------------- #

def _execution(**kw):
    base = {"ordered": True, "side": "BUY", "qty": 5, "price": 188500.0,
            "status": "FILLED", "dry_run": False, "reason": "", "error": ""}
    return SimpleNamespace(**{**base, **kw})


def test_hold_leaves_no_outcome():
    from main import describe_outcome

    assert describe_outcome(FinalDecision(action="HOLD", reason="관망"), None) == ""


def test_dry_run_says_no_real_order_went_out():
    """'세 AI 가 모두 매수였는데 왜 안 샀지?' 의 가장 흔한 답이다."""
    from main import describe_outcome

    text = describe_outcome(FinalDecision(action="STRONG_BUY", weight_pct=20),
                            _execution(dry_run=True, status="DRY_RUN"))
    assert "5주" in text and "DRY_RUN" in text and "실제 주문 아님" in text


def test_filled_order_is_stated_plainly():
    from main import describe_outcome

    text = describe_outcome(FinalDecision(action="STRONG_BUY", weight_pct=20), _execution())
    assert "매수 5주 @188,500원 체결" == text


def test_rejected_order_carries_the_reason():
    from main import describe_outcome

    text = describe_outcome(FinalDecision(action="STRONG_BUY"),
                            _execution(status="REJECTED", error="주문가능금액 부족"))
    assert "거부" in text and "주문가능금액 부족" in text


def test_skipped_order_explains_itself():
    """수량이 0주라 넘어간 경우가 여기 걸린다 — 없으면 화면에 아무 흔적이 없다."""
    from main import describe_outcome

    text = describe_outcome(FinalDecision(action="STRONG_BUY"),
                            _execution(ordered=False, status="SKIPPED",
                                       reason="매수 수량 0주 (가용현금 12,000원)"))
    assert text == "매수 수량 0주 (가용현금 12,000원)"


def test_outcome_reaches_the_record(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    saved: list[str] = []
    bot.portfolio.record_decision = lambda **kw: saved.append(kw.get("outcome")) or 1
    bot.executor.execute = lambda *a, **kw: _execution(dry_run=True, status="DRY_RUN")
    monkeypatch.setattr(main_module, "run_agents_parallel", lambda agents, snapshot, ai: {})
    monkeypatch.setattr(main_module, "decide",
                        lambda *a, **kw: FinalDecision(action="STRONG_BUY", weight_pct=20,
                                                       reason="전원 매수 합의"))
    monkeypatch.setattr(bot.risk, "check_buy",
                        lambda *a, **kw: SimpleNamespace(allowed=True, reason=""))

    bot._process_code("000660", bot.state, "c1", datetime.now(KST),
                      snapshot={"code": "000660", "name": "SK하이닉스",
                                "price": {"current": 188500}},
                      forced=None, decisions={})
    assert saved and "DRY_RUN" in saved[0]


# --- 알림이 소음이 되지 않게 --------------------------------------------- #

def test_one_slow_kis_response_does_not_ring_the_phone(bot, monkeypatch):
    """Read timed out 한 번은 다음 감시에서 대개 저절로 풀린다."""
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: True)
    monkeypatch.setattr(bot, "_run_guard_body",
                        lambda: (_ for _ in ()).throw(KisApiError("balance 요청 실패: Read timed out")))

    bot.guard_cycle()
    bot.guard_cycle()
    assert not any(t.startswith("error:") for t in bot.sent), "두 번까지는 참아야 합니다"


def test_a_stuck_guard_does_ring_the_phone(bot, monkeypatch):
    """계속 막혀 있으면 손절 감시가 죽은 것이다 — 이건 알려야 한다."""
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: True)
    monkeypatch.setattr(bot, "_run_guard_body",
                        lambda: (_ for _ in ()).throw(KisApiError("balance 요청 실패")))

    for _ in range(main_module.NOTIFY_AFTER_FAILURES):
        bot.guard_cycle()
    assert any("연속 실패" in t for t in bot.sent)


def test_recovery_resets_the_counter_and_says_so(bot, monkeypatch):
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: True)
    failing = True

    def body():
        if failing:
            raise KisApiError("balance 요청 실패")
        return []

    monkeypatch.setattr(bot, "_run_guard_body", body)
    for _ in range(main_module.NOTIFY_AFTER_FAILURES):
        bot.guard_cycle()
    assert any("연속 실패" in t for t in bot.sent)

    failing = False
    bot.sent.clear()
    bot.guard_cycle()
    assert any("정상으로 돌아왔습니다" in t for t in bot.sent)

    # 회복을 알린 뒤에는 처음부터 다시 센다 — 한 번 더 실패했다고 또 울리면 안 된다.
    failing = True
    bot.sent.clear()
    bot.guard_cycle()
    assert not any(t.startswith("error:") for t in bot.sent)


def test_quiet_recovery_after_a_single_hiccup(bot, monkeypatch):
    """한 번 실패하고 곧 회복한 것은 알릴 일이 아니다 — 그것까지 울리면 소음이다."""
    monkeypatch.setattr(main_module, "is_market_open", lambda *a, **kw: True)
    monkeypatch.setattr(bot, "_run_guard_body",
                        lambda: (_ for _ in ()).throw(KisApiError("일시 실패")))
    bot.guard_cycle()

    monkeypatch.setattr(bot, "_run_guard_body", lambda: [])
    bot.sent.clear()
    bot.guard_cycle()
    assert bot.sent == []


# --- 휴장일 달력이 낡았을 때 ---------------------------------------------------- #
#
# 달력이 비어 있어도 코드는 멀쩡히 돈다 — 공휴일에 전날 종가를 보고 판단하고,
# 주문은 거래소에 거부당하고, 그 알림이 30분마다 온다. 조용히 두면 안 된다.

def test_startup_warns_when_the_holiday_calendar_is_stale(bot, monkeypatch):
    monkeypatch.setattr(main_module, "calendar_health",
                        lambda *a, **k: {"state": "stale", "next": [], "covered_until": None,
                                         "days_left": 0, "message": "달력이 바닥났습니다"})
    bot._announce_calendar()
    assert any("휴장일 달력을 채워 주세요" in line for line in bot.sent)


def test_startup_is_quiet_when_the_calendar_is_fine(bot, monkeypatch):
    monkeypatch.setattr(main_module, "calendar_health",
                        lambda *a, **k: {"state": "ok", "next": [], "covered_until": None,
                                         "days_left": 200, "message": ""})
    bot._announce_calendar()
    assert not any("휴장일 달력" in line for line in bot.sent)


def test_startup_notice_carries_the_upcoming_holidays(bot, monkeypatch):
    """기동 알림에 다가오는 휴장일이 실려야 목요일 아침에 놀라지 않는다."""
    from datetime import date

    captured: dict = {}
    bot.notifier.send_startup = lambda n, **kw: captured.update(kw) or True
    monkeypatch.setattr(main_module, "calendar_health",
                        lambda *a, **k: {"state": "ok", "next": [date(2026, 9, 24)],
                                         "covered_until": None, "days_left": 100, "message": ""})
    bot._announce_calendar()
    health = bot._calendar
    bot.notifier.send_startup(
        len(bot.universe),
        holidays=[f"{d:%m/%d}({'월화수목금토일'[d.weekday()]})" for d in health.get("next", [])],
        calendar_warning=health.get("message", ""),
    )
    assert captured["holidays"] == ["09/24(목)"]


# --- 리포트 전에 미체결을 확정하는가 -------------------------------------------- #

_REPORT = {"total_pnl_pct": 0.0, "buy_count": 0, "sell_count": 0, "position_count": 0}


def test_daily_report_settles_open_orders_first(bot, monkeypatch):
    """15:10 청산 점검이 낸 주문이 PENDING 인 채로 집계되면 매도 건수가 틀린다."""
    order = []
    bot.portfolio.reconcile_open_orders = lambda now=None: (
        order.append("reconciled") or [])
    monkeypatch.setattr(main_module, "build_daily_report",
                        lambda db: order.append("report") or _REPORT)
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **k: True)

    bot.daily_report()

    assert order == ["reconciled", "report"]


def test_daily_report_still_goes_out_if_settling_fails(bot, monkeypatch):
    """미체결 정리가 실패했다고 그날 리포트를 통째로 잃을 이유는 없다."""
    def boom(now=None):
        raise RuntimeError("KIS 응답 없음")

    bot.portfolio.reconcile_open_orders = boom
    monkeypatch.setattr(main_module, "build_daily_report", lambda db: {**_REPORT, "total_pnl_pct": 1.5})
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **k: True)

    assert bot.daily_report()["total_pnl_pct"] == 1.5
    assert any("report:1.5" in line for line in bot.sent)


# --- 노트북이 잠들었을 때 (회사 노트북에서 돌리는 경우) -------------------------- #
#
# 뚜껑을 닫거나 절전에 들어가면 스케줄러는 조용히 지나간다. 깨어나면 아무 일도
# 없었던 것처럼 다음 사이클을 도니, 그 사이 손절 감시가 멈춰 있었다는 사실을
# 알 방법이 없다. 보유 종목이 있었다면 그건 반드시 알아야 한다.

def _seed_last_cycle(bot, when):
    from utils.db import update_bot_state
    update_bot_state(bot.settings.paths["db"],
                     last_cycle_at=when.isoformat(timespec="seconds"))


def test_a_long_gap_during_the_day_is_reported(bot):
    now = datetime(2026, 9, 22, 13, 5, tzinfo=KST)
    _seed_last_cycle(bot, datetime(2026, 9, 22, 10, 5, tzinfo=KST))   # 3시간 비었다

    bot._warn_if_we_were_asleep(now)

    assert any("사이클이 비어 있었습니다" in line for line in bot.sent)


def test_the_gap_warning_names_the_real_risk_when_holding(bot):
    now = datetime(2026, 9, 22, 13, 5, tzinfo=KST)
    _seed_last_cycle(bot, datetime(2026, 9, 22, 10, 5, tzinfo=KST))
    bot.state.positions = {"005930": object()}
    bot.portfolio.state = bot.state       # 실제 Portfolio 는 .state 를 들고 있다
    captured = []
    bot.notifier.send_alert = lambda title, lines, **kw: captured.extend(lines) or True

    bot._warn_if_we_were_asleep(now)

    joined = " ".join(captured)
    assert "손절" in joined and "멈춰" in joined
    assert "1종목" in joined


def test_a_normal_gap_is_not_reported(bot):
    now = datetime(2026, 9, 22, 13, 5, tzinfo=KST)
    _seed_last_cycle(bot, datetime(2026, 9, 22, 12, 35, tzinfo=KST))   # 30분 = 정상
    bot._warn_if_we_were_asleep(now)
    assert not any("비어 있었습니다" in line for line in bot.sent)


def test_overnight_gap_is_not_reported(bot):
    """어제 15:00 → 오늘 09:05 는 원래 비어 있다. 그걸 알리면 매일 아침 울린다."""
    now = datetime(2026, 9, 22, 9, 5, tzinfo=KST)
    _seed_last_cycle(bot, datetime(2026, 9, 21, 15, 0, tzinfo=KST))
    bot._warn_if_we_were_asleep(now)
    assert not any("비어 있었습니다" in line for line in bot.sent)


def test_the_first_cycle_ever_is_not_reported(bot):
    """기록이 없으면 비교할 대상도 없다."""
    bot._warn_if_we_were_asleep(datetime(2026, 9, 22, 9, 5, tzinfo=KST))
    assert not any("비어 있었습니다" in line for line in bot.sent)


def test_a_broken_gap_check_does_not_kill_the_cycle(bot, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("DB 잠김")

    monkeypatch.setattr(main_module, "get_bot_state", boom)
    bot._warn_if_we_were_asleep(datetime(2026, 9, 22, 13, 5, tzinfo=KST))   # 터지지 않는다


# --- /주문 ---------------------------------------------------------------------- #

def test_orders_command_shows_what_the_exchange_said(bot, monkeypatch):
    """'거부' 두 글자만 오면 결국 PC 를 켜야 한다."""
    monkeypatch.setattr(
        "dashboard.queries.recent_orders",
        lambda *a, **k: [
            {"created_at": "2026-09-22T09:06:00+09:00", "name": "삼성전자", "code": "005930",
             "side": "BUY", "qty": 3, "filled_qty": 3, "price": 269500, "filled_price": 269500,
             "status": "FILLED", "dry_run": 0, "reason": "세 AI 합의", "error": ""},
            {"created_at": "2026-09-22T09:06:00+09:00", "name": "KB금융", "code": "105560",
             "side": "BUY", "qty": 3, "filled_qty": 0, "price": 177431, "filled_price": 0,
             "status": "REJECTED", "dry_run": 0, "reason": "", "error": "[40310000] 호가단위 오류"},
        ])
    reply = bot._cmd_orders()
    assert "삼성전자 매수 3주 @269,500" in reply and "✅ 체결" in reply
    assert "❌ 거부" in reply
    assert "[40310000] 호가단위 오류" in reply, "거래소가 한 말이 그대로 있어야 한다"


def test_orders_command_marks_dry_run(bot, monkeypatch):
    monkeypatch.setattr(
        "dashboard.queries.recent_orders",
        lambda *a, **k: [
            {"created_at": "2026-09-22T09:06:00+09:00", "name": "삼성전자", "code": "005930",
             "side": "BUY", "qty": 3, "filled_qty": 0, "price": 269500, "filled_price": 0,
             "status": "DRY_RUN", "dry_run": 1, "reason": "", "error": ""},
        ])
    assert "모의" in bot._cmd_orders()


def test_orders_command_is_plain_when_empty(bot, monkeypatch):
    monkeypatch.setattr("dashboard.queries.recent_orders", lambda *a, **k: [])
    assert bot._cmd_orders() == "주문 기록이 없습니다."


# --- 네트워크가 끊겼을 때 봇이 스스로 죽지 않는가 (2026-09-22) ------------------- #
#
# 회사망으로 옮기거나 와이파이가 바뀌면 KIS(포트 29443)가 막히는 일이 있다.
# 예전에는 이걸 보통 실패로 세어, 90분(사이클 3회)이면 치명적 오류로 판단하고
# 스스로 내려갔다. 그러고 나면 네트워크가 돌아와도 사람이 다시 켜야 했다.

def _offline(bot, monkeypatch):
    from trading.kis_api import KisUnreachableError

    def boom(now=None):
        raise KisUnreachableError("KIS 서버에 연결되지 않습니다 — 방화벽을 확인하세요")

    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    bot.portfolio.sync = boom


def test_a_network_outage_does_not_count_toward_the_fatal_limit(bot, monkeypatch):
    _offline(bot, monkeypatch)

    for _ in range(MAX_CONSECUTIVE_FAILURES + 3):
        bot.run_cycle()

    assert bot.consecutive_failures == 0, "네트워크 문제는 '고장' 이 아니다"
    assert not any("fatal:" in line for line in bot.sent), "스스로 내려가면 안 된다"
    assert not bot._shutting_down


def test_the_outage_is_reported_but_only_once(bot, monkeypatch):
    """30분마다 같은 내용을 울리면 알림이 소음이 된다."""
    _offline(bot, monkeypatch)
    keys = []
    bot.notifier.send_alert = lambda title, lines, **kw: keys.append(kw.get("key")) or True

    bot.run_cycle()
    bot.run_cycle()

    assert keys == ["kis_unreachable", "kis_unreachable"], "같은 키로 묶여 중복이 억제된다"


def test_a_real_failure_still_stops_the_bot(bot, monkeypatch):
    """네트워크가 아닌 진짜 고장까지 눈감으면 안전장치가 사라진다."""
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)

    def boom(now=None):
        raise KisApiError("balance 실패 [40310000] 모의투자 미신청 계좌입니다")

    bot.portfolio.sync = boom

    for _ in range(MAX_CONSECUTIVE_FAILURES):
        bot.run_cycle()

    assert bot.consecutive_failures >= MAX_CONSECUTIVE_FAILURES
    assert any("fatal:" in line for line in bot.sent)
