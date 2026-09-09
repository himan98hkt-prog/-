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
