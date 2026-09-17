"""인라인 SVG 차트 테스트 — 빈 데이터에서도 화면이 깨지지 않아야 한다."""

from __future__ import annotations

import re

import pytest

from dashboard.charts import cost_bars, equity_line, pnl_bars


def equity_rows(values):
    return [{"date": f"2026-09-{i + 1:02d}", "end_equity": v, "total_pnl_pct": 0.0}
            for i, v in enumerate(values)]


def pnl_rows(values):
    return [{"date": f"2026-09-{i + 1:02d}", "end_equity": 5_000_000, "total_pnl_pct": v}
            for i, v in enumerate(values)]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("render", [equity_line, pnl_bars, cost_bars])
def test_empty_data_renders_message_not_broken_svg(render):
    output = render([])
    assert "chart-empty" in output
    assert "<svg" not in output


def test_single_day_equity_shows_message():
    """점 하나로는 추세선을 그릴 수 없다."""
    assert "chart-empty" in equity_line(equity_rows([5_000_000]))


def test_all_zero_cost_shows_message():
    rows = [{"date": "2026-09-01", "cost": 0, "calls": 0}]
    assert "chart-empty" in cost_bars(rows)


# --------------------------------------------------------------------------- #
# 정상 렌더링
# --------------------------------------------------------------------------- #


def test_equity_line_draws_a_path_per_point():
    svg = equity_line(equity_rows([5_000_000, 5_100_000, 5_050_000, 5_200_000]))
    assert svg.startswith("<svg")
    assert svg.count("<circle") == 4, "각 데이터 점에 마커가 있어야 합니다"
    assert 'class="line"' in svg and 'class="area"' in svg
    assert 'role="img"' in svg and "aria-label" in svg


def test_equity_line_labels_the_latest_value():
    svg = equity_line(equity_rows([5_000_000, 5_432_100]))
    assert "5,432,100" in svg


def test_flat_equity_does_not_divide_by_zero():
    svg = equity_line(equity_rows([5_000_000, 5_000_000, 5_000_000]))
    assert svg.startswith("<svg")
    assert "nan" not in svg.lower() and "inf" not in svg.lower()


def test_pnl_bars_use_up_and_down_classes():
    svg = pnl_bars(pnl_rows([1.5, -0.8, 0.3]))
    assert 'class="bar up"' in svg and 'class="bar down"' in svg


def test_pnl_bars_label_only_extremes_and_last():
    """모든 막대에 숫자를 붙이지 않는다."""
    svg = pnl_bars(pnl_rows([0.2, 1.9, 0.4, -1.1, 0.5, 0.6]))
    labels = re.findall(r'class="value-label"', svg)
    assert len(labels) == 3, f"최댓값·최솟값·마지막만 라벨 (실제 {len(labels)})"


def test_all_marks_have_hover_titles():
    svg = pnl_bars(pnl_rows([1.0, -1.0]))
    assert svg.count("<title>") == 2, "각 막대에 툴팁이 있어야 합니다"


def test_zero_pnl_still_draws_visible_bar():
    svg = pnl_bars(pnl_rows([0.0]))
    heights = [float(h) for h in re.findall(r'height="([\d.]+)"', svg)]
    assert all(h > 0 for h in heights), "0%도 최소 두께로 보여야 합니다"


def test_cost_bars_include_call_count_in_tooltip():
    svg = cost_bars([{"date": "2026-09-01", "cost": 0.42, "calls": 120}])
    assert "$0.420" in svg and "120회" in svg


def test_html_in_data_is_escaped():
    """종목명·날짜가 그대로 들어가도 마크업이 깨지지 않아야 한다."""
    svg = cost_bars([{"date": "<script>alert(1)</script>", "cost": 1.0, "calls": 1}])
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


# --- 단순 보유 대비 벤치마크 ------------------------------------------------ #

def _seed_benchmark(db, rows, pnl=()):
    """rows: [(date, code, name, price)], pnl: [(date, start, end)]"""
    from utils.db import record_benchmark_price, session
    for date, code, name, price in rows:
        record_benchmark_price(db, date=date, code=code, name=name, price=price)
    with session(db) as conn:
        for date, start, end in pnl:
            conn.execute(
                """INSERT INTO daily_pnl (date, start_equity, end_equity, updated_at)
                   VALUES (?, ?, ?, '2026-09-17T00:00:00+09:00')
                   ON CONFLICT(date) DO UPDATE SET
                       start_equity = excluded.start_equity, end_equity = excluded.end_equity""",
                (date, start, end))


def test_benchmark_is_the_equal_weight_average(tmp_path):
    """동일비중 보유 수익률 = 종목별 수익률의 평균."""
    from dashboard.queries import benchmark_comparison
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _seed_benchmark(db, [
        ("2026-09-15", "005930", "삼성전자", 100.0),
        ("2026-09-15", "000660", "SK하이닉스", 200.0),
        ("2026-09-17", "005930", "삼성전자", 110.0),   # +10%
        ("2026-09-17", "000660", "SK하이닉스", 180.0),  # -10%
    ], pnl=[("2026-09-15", 1_000_000, 1_000_000), ("2026-09-17", 1_000_000, 1_050_000)])

    result = benchmark_comparison(db)
    assert result["ready"]
    assert result["benchmark_pct"] == 0.0        # (+10 - 10) / 2
    assert result["actual_pct"] == 5.0           # 100만 → 105만
    assert result["edge_pct"] == 5.0
    assert result["codes"] == 2


def test_stocks_added_later_are_excluded(tmp_path):
    """나중에 담은 종목을 넣으면 '오른 뒤에 산' 셈이라 벤치마크가 유리해진다."""
    from dashboard.queries import benchmark_comparison
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _seed_benchmark(db, [
        ("2026-09-15", "005930", "삼성전자", 100.0),
        ("2026-09-17", "005930", "삼성전자", 120.0),   # +20%
        ("2026-09-17", "207940", "삼성바이오", 500.0),  # 시작가 없음
    ], pnl=[("2026-09-15", 1_000_000, 1_000_000)])

    result = benchmark_comparison(db)
    assert result["codes"] == 1, "시작 가격이 없는 종목이 섞였습니다"
    assert result["benchmark_pct"] == 20.0


def test_single_day_is_not_enough(tmp_path):
    from dashboard.queries import benchmark_comparison
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _seed_benchmark(db, [("2026-09-17", "005930", "삼성전자", 100.0)])

    result = benchmark_comparison(db)
    assert not result["ready"]
    assert "2일" in result["reason"]


def test_no_records_yet(tmp_path):
    from dashboard.queries import benchmark_comparison
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    result = benchmark_comparison(db)
    assert not result["ready"]
    assert result["benchmark_pct"] == 0.0


def test_zero_price_is_not_recorded(tmp_path):
    """값을 못 읽어 0 이 들어가면 수익률이 통째로 망가진다."""
    from utils.db import connect, init_db, record_benchmark_price

    db = tmp_path / "t.db"
    init_db(db)
    record_benchmark_price(db, date="2026-09-17", code="005930", name="삼성전자", price=0.0)
    conn = connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) c FROM benchmark_prices").fetchone()["c"] == 0
    finally:
        conn.close()


def test_latest_price_of_the_day_wins(tmp_path):
    """사이클이 하루에 12번 도니 같은 날은 덮어써야 한다."""
    from utils.db import connect, init_db, record_benchmark_price

    db = tmp_path / "t.db"
    init_db(db)
    record_benchmark_price(db, date="2026-09-17", code="005930", name="삼성전자", price=100.0)
    record_benchmark_price(db, date="2026-09-17", code="005930", name="삼성전자", price=130.0)
    conn = connect(db)
    try:
        rows = list(conn.execute("SELECT price FROM benchmark_prices"))
        assert len(rows) == 1 and rows[0]["price"] == 130.0
    finally:
        conn.close()


# --- 매매 성적 --------------------------------------------------------------- #

def _order(db, code, side, qty, price, at, name="테스트"):
    from utils.db import session
    with session(db) as conn:
        conn.execute(
            """INSERT INTO orders (code, name, side, order_type, qty, price,
                                   filled_qty, filled_price, status, kis_env,
                                   created_at, updated_at)
               VALUES (?, ?, ?, 'market', ?, ?, ?, ?, 'FILLED', 'VTS', ?, ?)""",
            (code, name, side, qty, price, qty, price, at, at))


def test_round_trip_is_matched_and_costed(tmp_path):
    """수수료·세금을 빼지 않으면 성적이 실제보다 좋아 보인다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _order(db, "005930", "BUY", 10, 100_000, "2026-09-01T09:05:00+09:00")
    _order(db, "005930", "SELL", 10, 110_000, "2026-09-08T09:05:00+09:00")

    stats = trade_stats(db)
    assert stats["count"] == 1
    # 총수익 10% 에서 수수료(0.015x2)+거래세(0.15) = 0.18%p 를 뺀다
    assert stats["trades"][0]["pnl_pct"] == 9.82
    assert stats["trades"][0]["held_days"] == 7
    assert stats["fee_krw"] > 0


def test_partial_sell_consumes_lots_first_in_first_out(tmp_path):
    """부분 매도는 먼저 산 물량부터 덜어내야 한다."""
    from dashboard.queries import closed_trades
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _order(db, "005930", "BUY", 10, 100_000, "2026-09-01T09:05:00+09:00")
    _order(db, "005930", "BUY", 10, 120_000, "2026-09-02T09:05:00+09:00")
    _order(db, "005930", "SELL", 15, 130_000, "2026-09-05T09:05:00+09:00")

    trades = list(reversed(closed_trades(db)))  # 오래된 순
    assert len(trades) == 2
    assert (trades[0]["qty"], trades[0]["entry_price"]) == (10, 100_000)
    assert (trades[1]["qty"], trades[1]["entry_price"]) == (5, 120_000)


def test_breakeven_win_rate_matches_the_payoff(tmp_path):
    """손익비 2:1 이면 본전 승률은 33.3% — 이보다 낮으면 잃고 있는 것이다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    # 이익 +10%, 손실 -5% 두 건 → 손익비 약 2
    _order(db, "AAA", "BUY", 1, 100_000, "2026-09-01T09:00:00+09:00")
    _order(db, "AAA", "SELL", 1, 110_200, "2026-09-03T09:00:00+09:00")
    _order(db, "BBB", "BUY", 1, 100_000, "2026-09-01T09:00:00+09:00")
    _order(db, "BBB", "SELL", 1, 94_820, "2026-09-03T09:00:00+09:00")

    stats = trade_stats(db)
    assert stats["win_rate"] == 50.0
    # 수수료·세금이 양쪽 모두를 갉아먹으므로 총수익 기준 2:1 은 실질 1.87 이 된다.
    assert stats["payoff"] == 1.87
    # 본전 승률 = 1 / (1 + 손익비) — 이 관계가 깨지면 판단 기준이 거짓이 된다.
    # (표시용 손익비는 반올림된 값이라 소수 첫째 자리까지만 맞춘다.)
    assert stats["breakeven_win_rate"] == pytest.approx(
        1 / (1 + stats["payoff"]) * 100, abs=0.1)
    assert stats["breakeven_win_rate"] == 34.9
    assert stats["win_rate"] > stats["breakeven_win_rate"], "이 표본은 이기고 있어야 한다"


def test_unsold_position_is_not_counted(tmp_path):
    """아직 안 판 종목을 성적에 넣으면 평가손익을 실현손익으로 착각하게 된다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _order(db, "005930", "BUY", 10, 100_000, "2026-09-01T09:05:00+09:00")

    assert trade_stats(db)["count"] == 0


def test_dry_run_orders_are_excluded(tmp_path):
    """주문 미전송 기록은 체결이 아니다 — 성적에 섞이면 안 된다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db, session

    db = tmp_path / "t.db"
    init_db(db)
    with session(db) as conn:
        for side, price in (("BUY", 100_000), ("SELL", 130_000)):
            conn.execute(
                """INSERT INTO orders (code, name, side, order_type, qty, price,
                                       filled_qty, filled_price, status, kis_env,
                                       created_at, updated_at)
                   VALUES ('005930','삼성전자',?,'market',1,?,0,0,'DRY_RUN','VTS',
                           '2026-09-01T09:05:00+09:00','2026-09-01T09:05:00+09:00')""",
                (side, price))

    assert trade_stats(db)["count"] == 0


def test_positions_show_the_trailing_line(tmp_path):
    """화면의 기준선이 실제 청산 기준과 달라지면 사용자가 속는다."""
    import dataclasses

    from dashboard.queries import positions
    from logic.risk_manager import RiskManager
    from utils.db import init_db, session, sync_peaks

    from tests.test_risk_manager import RISK, SCHEDULE

    db = tmp_path / "t.db"
    init_db(db)
    with session(db) as conn:
        conn.execute(
            """INSERT INTO positions (code, name, qty, avg_price, current_price,
                                      eval_amount, pnl_amount, pnl_pct, updated_at)
               VALUES ('005930','삼성전자',10,100000,140000,1400000,400000,40.0,'x')""")
    sync_peaks(db, {"005930": 150_000})

    risk = dataclasses.replace(RISK, trailing_activate_pct=10, trailing_stop_pct=5)
    row = positions(db, risk.stop_loss_pct, risk.take_profit_pct, risk)[0]

    assert row["peak_price"] == 150_000
    assert row["trailing_stop"] == 142_500          # 150,000 x 0.95
    # 리스크 매니저가 실제로 쓰는 값과 같아야 한다
    from logic.portfolio import Position
    position = Position(code="005930", name="삼성전자", qty=10, orderable_qty=10,
                        avg_price=100_000, current_price=140_000, eval_amount=1_400_000,
                        pnl_amount=400_000, pnl_pct=40.0, peak_price=150_000)
    assert RiskManager(risk, SCHEDULE).trailing_stop_price(position) == row["trailing_stop"]


def test_positions_hide_the_trailing_line_when_off(tmp_path):
    from dashboard.queries import positions
    from utils.db import init_db, session

    from tests.test_risk_manager import RISK

    db = tmp_path / "t.db"
    init_db(db)
    with session(db) as conn:
        conn.execute(
            """INSERT INTO positions (code, name, qty, avg_price, current_price,
                                      eval_amount, pnl_amount, pnl_pct, updated_at)
               VALUES ('005930','삼성전자',10,100000,140000,1400000,400000,40.0,'x')""")

    row = positions(db, RISK.stop_loss_pct, RISK.take_profit_pct, RISK)[0]
    assert row["trailing_stop"] == 0.0


# --- 매수 사유 / 테마별 이슈 --------------------------------------------------- #

def _decision(db, code, at, final="STRONG_BUY", reason="전원 매수 합의"):
    from utils.db import session
    with session(db) as conn:
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, name, holding,
                   claude_action, claude_confidence, claude_reason,
                   gemini_action, gemini_confidence, gemini_reason,
                   final_action, final_weight_pct, final_reason, risk_passed, created_at)
               VALUES ('c', ?, '종목', 0, 'BUY', 0.7, '클로드 근거',
                       'BUY', 0.6, '제미나이 근거', ?, 18, ?, 1, ?)""",
            (code, final, reason, at))


def test_rationale_points_at_the_decision_that_bought(tmp_path):
    """살 때의 판단이어야 한다 — 그 뒤의 판단을 붙이면 사후설명이 된다."""
    from dashboard.queries import buy_rationale
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _decision(db, "005930", "2026-09-16T09:34:00+09:00", reason="매수 당시 판단")
    _order(db, "005930", "BUY", 10, 78_000, "2026-09-16T09:35:00+09:00")
    _decision(db, "005930", "2026-09-17T09:34:00+09:00", final="HOLD", reason="나중 판단")

    got = buy_rationale(db, ["005930"])["005930"]
    assert got["final_reason"] == "매수 당시 판단"
    assert got["bought_price"] == 78_000
    assert [e["name"] for e in got["engines"]] == ["Claude", "Gemini"]
    assert got["engines"][0]["reason"] == "클로드 근거"


def test_rationale_skips_codes_never_bought(tmp_path):
    from dashboard.queries import buy_rationale
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _decision(db, "005930", "2026-09-16T09:34:00+09:00")
    assert buy_rationale(db, ["005930"]) == {}


def test_theme_groups_and_averages(tmp_path):
    """테마 등락은 소속 종목의 평균이다."""
    from dashboard.queries import theme_performance
    from utils.db import init_db, record_benchmark_price

    db = tmp_path / "t.db"
    init_db(db)
    for code, p0, p1 in (("005930", 100.0, 110.0), ("000660", 100.0, 90.0),
                         ("035420", 100.0, 105.0)):
        record_benchmark_price(db, date="2026-09-16", code=code, name=code, price=p0)
        record_benchmark_price(db, date="2026-09-17", code=code, name=code, price=p1)

    themes = {"005930": "반도체", "000660": "반도체", "035420": "인터넷"}
    result = {row["theme"]: row for row in theme_performance(db, themes)}

    assert result["반도체"]["since_start"] == 0.0     # (+10 - 10) / 2
    assert result["반도체"]["codes"] == 2
    assert result["인터넷"]["since_start"] == 5.0
    # 큰 쪽이 위로 온다 — 무엇이 끌고 무엇이 미는지 바로 보이게
    assert [r["theme"] for r in theme_performance(db, themes)] == ["인터넷", "반도체"]


def test_theme_needs_two_days(tmp_path):
    from dashboard.queries import theme_performance
    from utils.db import init_db, record_benchmark_price

    db = tmp_path / "t.db"
    init_db(db)
    record_benchmark_price(db, date="2026-09-17", code="005930", name="삼성전자", price=100.0)
    assert theme_performance(db, {"005930": "반도체"}) == []


# --- 엔진별 적중률 ----------------------------------------------------------- #

def _vote(db, code, at, claude, gemini, chatgpt=None):
    from utils.db import session
    with session(db) as conn:
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, name, holding,
                   claude_action, gemini_action, chatgpt_action,
                   final_action, final_weight_pct, risk_passed, created_at)
               VALUES ('c', ?, '종목', 0, ?, ?, ?, 'HOLD', 0, 1, ?)""",
            (code, claude, gemini, chatgpt, at))


def _prices(db, code, series):
    from utils.db import record_benchmark_price
    for date, price in series:
        record_benchmark_price(db, date=date, code=code, name="종목", price=price)


DAYS = [f"2026-09-{d:02d}" for d in range(1, 10)]


def test_buy_is_correct_when_the_price_rises(tmp_path):
    from dashboard.queries import engine_accuracy
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _prices(db, "005930", [(d, 100.0 + i * 5) for i, d in enumerate(DAYS)])   # 계속 상승
    _vote(db, "005930", f"{DAYS[0]}T09:05:00+09:00", "BUY", "SELL")

    result = {e["engine"]: e for e in engine_accuracy(db, horizon_days=5)["engines"]}
    assert result["Claude"]["hit_rate"] == 100.0    # BUY + 상승 = 적중
    assert result["Gemini"]["hit_rate"] == 0.0      # SELL + 상승 = 빗나감


def test_hold_is_excluded_from_the_hit_rate(tmp_path):
    """관망만 하는 엔진이 100% 로 보이면 안 된다."""
    from dashboard.queries import engine_accuracy
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _prices(db, "005930", [(d, 100.0 + i * 5) for i, d in enumerate(DAYS)])
    _vote(db, "005930", f"{DAYS[0]}T09:05:00+09:00", "HOLD", "BUY")

    result = {e["engine"]: e for e in engine_accuracy(db, horizon_days=5)["engines"]}
    assert result["Claude"]["graded"] == 0
    assert result["Claude"]["hit_rate"] == 0.0
    assert result["Claude"]["hold_rate"] == 100.0
    assert result["Gemini"]["graded"] == 1


def test_recent_calls_without_a_future_are_not_graded(tmp_path):
    """채점할 미래가 없는 판단을 세면 성적이 표본 부족으로 흔들린다."""
    from dashboard.queries import engine_accuracy
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    _prices(db, "005930", [(d, 100.0) for d in DAYS[:3]])
    _vote(db, "005930", f"{DAYS[0]}T09:05:00+09:00", "BUY", "BUY")   # 5일 뒤가 없다

    assert engine_accuracy(db, horizon_days=5)["ready"] is False


def test_expectancy_is_the_net_average_per_trade(tmp_path):
    """기대값 = (승률 x 평균이익) - (패률 x 평균손실). 이 값이 양수여야 번다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    # 2승 2패: +10%, +10%, -5%, -5% (총수익 기준) → 비용 0.18%p 차감
    for code, sell in (("AAA", 110_000), ("BBB", 110_000),
                       ("CCC", 95_000), ("DDD", 95_000)):
        _order(db, code, "BUY", 1, 100_000, "2026-09-01T09:00:00+09:00")
        _order(db, code, "SELL", 1, sell, "2026-09-03T09:00:00+09:00")

    stats = trade_stats(db)
    assert stats["win_rate"] == 50.0
    # 평균이익 9.82, 평균손실 -5.18 → 0.5 x 9.82 + 0.5 x (-5.18) = 2.32
    assert stats["expectancy"] == pytest.approx(2.32, abs=0.01)
    assert stats["expectancy"] > 0


def test_expectancy_is_negative_when_costs_win(tmp_path):
    """승률이 높아도 이익이 작으면 비용에 먹힌다 — 그걸 숫자로 드러내야 한다."""
    from dashboard.queries import trade_stats
    from utils.db import init_db

    db = tmp_path / "t.db"
    init_db(db)
    # 3승 1패인데 이익이 잘다: +0.5% x3, -3% x1
    for code, sell in (("AAA", 100_500), ("BBB", 100_500),
                       ("CCC", 100_500), ("DDD", 97_000)):
        _order(db, code, "BUY", 1, 100_000, "2026-09-01T09:00:00+09:00")
        _order(db, code, "SELL", 1, sell, "2026-09-03T09:00:00+09:00")

    stats = trade_stats(db)
    assert stats["win_rate"] == 75.0, "승률은 높다"
    assert stats["expectancy"] < 0, "그런데도 기대값은 음수여야 한다"
