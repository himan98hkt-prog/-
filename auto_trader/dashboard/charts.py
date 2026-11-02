"""인라인 SVG 차트 (외부 라이브러리 없음).

색 역할은 CSS 변수로 두고 값은 템플릿의 :root 에서 라이트/다크로 스왑한다.
등락 색은 **한국 시장 관행(상승=빨강, 하락=파랑)** 을 따른다 — 검증된 발산 쌍
(blue ↔ red)을 그 방향으로 매핑한 것이다.
"""

from __future__ import annotations

from html import escape
from typing import Any, Sequence

# viewBox 좌표계 (실제 크기는 CSS 가 정한다)
WIDTH, HEIGHT = 720, 220
PAD_L, PAD_R, PAD_T, PAD_B = 56, 12, 16, 28


def _fmt_money(value: float) -> str:
    return f"{value:,.0f}"


def _nice_bounds(values: Sequence[float]) -> tuple[float, float]:
    """0을 포함하지 않는 축은 데이터 범위에 5% 여백만 준다."""
    if not values:
        return 0.0, 1.0
    low, high = min(values), max(values)
    if low == high:
        span = abs(low) * 0.05 or 1.0
        return low - span, high + span
    margin = (high - low) * 0.08
    return low - margin, high + margin


def _empty(message: str) -> str:
    return (
        f'<div class="chart-empty" role="status">{escape(message)}</div>'
    )


def equity_line(rows: list[dict[str, Any]]) -> str:
    """일자별 종료 자산 추이 — 단일 계열이라 범례가 필요 없다(제목이 계열명)."""
    points = [(row["date"], float(row["end_equity"] or 0)) for row in rows if row.get("end_equity")]
    if len(points) < 2:
        return _empty("자산 추이는 거래일 2일치가 쌓이면 표시됩니다")

    values = [value for _, value in points]
    low, high = _nice_bounds(values)
    span = high - low or 1.0
    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B

    def x_at(index: int) -> float:
        return PAD_L + (plot_w * index / (len(points) - 1))

    def y_at(value: float) -> float:
        return PAD_T + plot_h * (1 - (value - low) / span)

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x_at(i):.1f},{y_at(v):.1f}" for i, (_, v) in enumerate(points)
    )
    area = f"{path} L{x_at(len(points) - 1):.1f},{PAD_T + plot_h:.1f} L{PAD_L:.1f},{PAD_T + plot_h:.1f} Z"

    grid, labels = [], []
    for fraction in (0, 0.5, 1):
        y = PAD_T + plot_h * fraction
        value = high - span * fraction
        grid.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{WIDTH - PAD_R}" y2="{y:.1f}"/>')
        labels.append(
            f'<text class="axis" x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end">{_fmt_money(value)}</text>'
        )

    markers = []
    for i, (date, value) in enumerate(points):
        # 마커는 8px 이상 — 끝점만 눈에 띄게, 나머지는 히트 영역으로만
        radius = 4.5 if i in (0, len(points) - 1) else 3
        markers.append(
            f'<circle class="marker" cx="{x_at(i):.1f}" cy="{y_at(value):.1f}" r="{radius}">'
            f"<title>{escape(date)} · {_fmt_money(value)}원</title></circle>"
        )

    first_date, last_date = points[0][0], points[-1][0]
    last_value = points[-1][1]
    return f"""<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
     aria-label="일자별 종료 자산 추이">
  {''.join(grid)}
  <path class="area" d="{area}"/>
  <path class="line" d="{path}"/>
  {''.join(markers)}
  <text class="axis" x="{PAD_L}" y="{HEIGHT - 8}">{escape(first_date)}</text>
  <text class="axis" x="{WIDTH - PAD_R}" y="{HEIGHT - 8}" text-anchor="end">{escape(last_date)}</text>
  <text class="value-label" x="{x_at(len(points) - 1) - 6:.1f}" y="{y_at(last_value) - 12:.1f}"
        text-anchor="end">{_fmt_money(last_value)}원</text>
</svg>"""


def pnl_bars(rows: list[dict[str, Any]]) -> str:
    """일별 손익률 — 부호가 의미를 나르는 발산 막대 (상승 빨강 / 하락 파랑)."""
    points = [(row["date"], float(row["total_pnl_pct"] or 0)) for row in rows]
    if not points:
        return _empty("손익 기록이 아직 없습니다")

    magnitude = max((abs(v) for _, v in points), default=1.0) or 1.0
    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B
    zero_y = PAD_T + plot_h / 2
    slot = plot_w / len(points)
    bar_w = max(min(slot - 6, 34), 4)  # 막대 사이 2px 이상 간격 유지

    bars, labels = [], []
    for i, (date, value) in enumerate(points):
        height = abs(value) / magnitude * (plot_h / 2 - 6)
        x = PAD_L + slot * i + (slot - bar_w) / 2
        y = zero_y - height if value >= 0 else zero_y
        sign = "up" if value >= 0 else "down"
        bars.append(
            f'<rect class="bar {sign}" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
            f'height="{max(height, 1.5):.1f}" rx="3">'
            f"<title>{escape(date)} · {value:+.2f}%</title></rect>"
        )
        # 직접 라벨은 최댓값·최솟값·마지막만 (모든 점에 숫자를 붙이지 않는다)
        if value == max(v for _, v in points) or value == min(v for _, v in points) or i == len(points) - 1:
            label_y = y - 5 if value >= 0 else y + height + 13
            labels.append(
                f'<text class="value-label" x="{x + bar_w / 2:.1f}" y="{label_y:.1f}" '
                f'text-anchor="middle">{value:+.1f}%</text>'
            )

    return f"""<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
     aria-label="일별 손익률. 양수는 빨강, 음수는 파랑">
  <line class="grid zero" x1="{PAD_L}" y1="{zero_y:.1f}" x2="{WIDTH - PAD_R}" y2="{zero_y:.1f}"/>
  {''.join(bars)}
  {''.join(labels)}
  <text class="axis" x="{PAD_L}" y="{HEIGHT - 8}">{escape(points[0][0])}</text>
  <text class="axis" x="{WIDTH - PAD_R}" y="{HEIGHT - 8}" text-anchor="end">{escape(points[-1][0])}</text>
</svg>"""


def cost_bars(rows: list[dict[str, Any]]) -> str:
    """일별 AI 비용 — 크기 비교이므로 단일 색 막대."""
    points = [(row["date"], float(row["cost"] or 0)) for row in rows]
    if not points or all(value == 0 for _, value in points):
        return _empty("AI 호출 기록이 아직 없습니다")

    height_px = 120
    top = max(value for _, value in points) or 1.0
    plot_w = WIDTH - PAD_L - PAD_R
    slot = plot_w / len(points)
    bar_w = max(min(slot - 6, 34), 4)
    base_y = height_px - 26

    bars = []
    for i, (date, value) in enumerate(points):
        bar_h = max(value / top * (base_y - 14), 1.5)
        x = PAD_L + slot * i + (slot - bar_w) / 2
        bars.append(
            f'<rect class="bar cost" x="{x:.1f}" y="{base_y - bar_h:.1f}" width="{bar_w:.1f}" '
            f'height="{bar_h:.1f}" rx="3"><title>{escape(date)} · ${value:.3f} '
            f'({row_calls(rows, date)}회)</title></rect>'
        )

    return f"""<svg class="chart short" viewBox="0 0 {WIDTH} {height_px}" role="img"
     aria-label="일별 AI 호출 비용">
  <line class="grid" x1="{PAD_L}" y1="{base_y:.1f}" x2="{WIDTH - PAD_R}" y2="{base_y:.1f}"/>
  <text class="axis" x="{PAD_L - 8}" y="{base_y - (base_y - 14):.1f}" text-anchor="end">${top:.2f}</text>
  {''.join(bars)}
  <text class="axis" x="{PAD_L}" y="{height_px - 6}">{escape(points[0][0])}</text>
  <text class="axis" x="{WIDTH - PAD_R}" y="{height_px - 6}" text-anchor="end">{escape(points[-1][0])}</text>
</svg>"""


def row_calls(rows: list[dict[str, Any]], date: str) -> int:
    for row in rows:
        if row["date"] == date:
            return int(row.get("calls") or 0)
    return 0
