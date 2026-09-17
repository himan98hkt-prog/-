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
