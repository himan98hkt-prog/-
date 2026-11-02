#!/usr/bin/env python3
"""성적이 나쁠 때 **왜** 나빴는지 판정한다.

"-10%" 라는 숫자 하나로는 아무것도 결정할 수 없다. 같은 -10% 가
전혀 다른 네 가지를 뜻할 수 있기 때문이다.

* 거래를 5번밖에 안 했다 → 운이 나빴던 구간이다. 아무 결론도 내면 안 된다.
* 시장이 -15% 였다 → 전략은 오히려 시장을 이겼다. 바꾸면 더 나빠진다.
* 승률은 높은데 손익비가 나쁘다 → 이익을 너무 일찍 자르고 손실을 오래 끈다.
  익절·손절 폭의 문제지 AI 판단의 문제가 아니다.
* 승률 자체가 낮다 → 종목 선택이 틀리고 있다. 이때만 AI 쪽을 손볼 가치가 있다.

원인을 모르는 채 모델을 올리는 것은 진단이 아니다. 같은 이유로 또 진다.
이 스크립트는 DB 에 이미 쌓인 기록만 읽고, 주문도 AI 호출도 하지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigError, load  # noqa: E402
from dashboard import queries  # noqa: E402

LINE = "─" * 66

# 이보다 거래가 적으면 승률·손익비가 전부 우연의 범위다. 20~30건은 되어야
# 방향을 말할 수 있고, 그 전에는 "표본 부족" 이 유일하게 정직한 결론이다.
MIN_TRADES_FOR_A_VERDICT = 20


def _pct(value: float) -> str:
    return f"{value:+.2f}%"


def _section(title: str) -> None:
    print()
    print(title)
    print(LINE)


def _sample(stats: dict) -> list[str]:
    _section("1. 표본 — 결론을 내도 되는 양인가")
    count = stats["count"]
    print(f"  종료된 거래      {count}건")
    print(f"  평균 보유일      {stats['avg_days']}일")
    if count == 0:
        print("\n  → 종료된 거래가 없습니다. 평가손익만으로는 전략을 판단할 수 없습니다.")
        return ["표본 없음"]
    if count < MIN_TRADES_FOR_A_VERDICT:
        print(f"\n  ⚠ {MIN_TRADES_FOR_A_VERDICT}건 미만입니다. 아래 승률·손익비는 "
              "우연의 범위라 방향을 말할 수 없습니다.")
        print("    이 단계에서 모델이나 전략을 바꾸면, 바꾼 효과인지 운인지 "
              "영영 구분하지 못합니다.")
        return [f"표본 부족({count}건)"]
    return []


def _market(db) -> list[str]:
    _section("2. 시장 대비 — 전략 탓인가 장 탓인가")
    bench = queries.benchmark_comparison(db)
    if not bench.get("ready"):
        print(f"  비교 불가: {bench.get('reason') or '기록 부족'}")
        return []
    actual, base = bench["actual_pct"], bench["benchmark_pct"]
    print(f"  자동매매        {_pct(actual)}")
    print(f"  그냥 들고 있기   {_pct(base)}   (감시 종목 동일비중, {bench['codes']}종목)")
    print(f"  차이            {_pct(bench['edge_pct'])}")
    if bench["edge_pct"] > 0:
        print("\n  → 시장보다 **덜 잃었습니다.** 손실의 주원인은 전략이 아니라 장세입니다.")
        print("    이 상태에서 AI 모델을 올려도 장이 빠지면 또 잃습니다.")
        return ["시장 하락이 주원인(전략은 시장을 이김)"]
    print("\n  → 그냥 들고 있는 것보다 **못했습니다.** 매매 자체가 가치를 깎고 있습니다.")
    return ["단순 보유보다 못함"]


def _expectancy(stats: dict) -> list[str]:
    _section("3. 기대값 — 이 시스템이 돈을 버는가")
    found: list[str] = []
    expectancy = stats.get("expectancy", 0.0)
    win, payoff = stats["win_rate"], stats["payoff"]
    breakeven = stats["breakeven_win_rate"]

    print(f"  기대값          {expectancy:+.3f}%/거래   ← 양수여야 계좌가 는다")
    print(f"  승률            {win}%")
    print(f"  본전 승률       {breakeven}%        ← 손익비로 정해지는 최소 승률")
    print(f"  평균 이익       {stats['avg_win']:+.2f}%")
    print(f"  평균 손실       {stats['avg_loss']:+.2f}%")
    print(f"  손익비          {payoff}         ← 평균이익 ÷ 평균손실")
    print(f"  실현 손익       {stats['realized_krw']:,}원 "
          f"(수수료·세금 {stats['fee_krw']:,}원 포함)")

    if expectancy > 0:
        print("\n  → 기대값은 양수입니다. 거래 하나하나는 유리한 쪽이고, "
              "지금 손실은 표본이 적거나 미실현 평가손 때문입니다.")
        return found

    print("\n  → 기대값이 음수입니다. 거래할수록 계좌가 줄어드는 상태입니다.")
    # 음수일 때, 승률이 문제인지 손익비가 문제인지를 가른다. 처방이 정반대다.
    if win < breakeven and payoff >= 1.5:
        print("    손익비(%.2f)는 나쁘지 않은데 **승률이 본전선에 못 미칩니다.**" % payoff)
        print("    → 종목 선택의 문제입니다. 여기서만 AI 판단을 손볼 값어치가 있습니다.")
        found.append("승률 부족(종목 선택 문제)")
    elif payoff < 1.0:
        print("    승률보다 **손익비가 문제입니다**(%.2f < 1.0)." % payoff)
        print("    이익은 작게 자르고 손실은 크게 안고 있다는 뜻입니다.")
        print("    → 익절·손절 폭(risk.take_profit_pct / stop_loss_pct)의 문제지,")
        print("      AI 모델을 올려서 해결되는 문제가 아닙니다.")
        found.append("손익비 불량(익절·손절 폭 문제)")
    else:
        print("    승률과 손익비가 함께 모자랍니다.")
        found.append("승률·손익비 동시 부족")
    return found


def _stops(stats: dict, risk) -> list[str]:
    _section("4. 손절이 설계대로 작동했는가")
    found: list[str] = []
    limit = abs(float(getattr(risk, "stop_loss_pct", 0) or 0))
    avg_loss = abs(stats["avg_loss"])
    print(f"  설정된 손절선    -{limit:.1f}%")
    print(f"  실제 평균 손실   -{avg_loss:.2f}%")

    trades = stats.get("trades") or []
    deep = [t for t in trades if t["pnl_pct"] < -limit * 1.5] if limit else []
    if limit and avg_loss > limit * 1.2:
        print(f"\n  ⚠ 평균 손실이 손절선보다 큽니다. 손절이 늦게 걸리고 있습니다.")
        print("    갭하락이면 설정값에 못 잡히는 것이 정상이지만, 반복된다면")
        print("    guard_interval_min 을 줄이거나 손절선을 올려야 합니다.")
        found.append("손절선 초과 손실")
    elif limit:
        print("\n  → 손절은 설계 범위에서 작동했습니다.")

    if deep:
        print(f"\n  손절선의 1.5배를 넘긴 거래 {len(deep)}건:")
        for t in deep[:5]:
            print(f"    {t.get('name') or t.get('code')}  {t['pnl_pct']:+.2f}%  "
                  f"({t.get('held_days', 0)}일 보유)")
    return found


def _worst(stats: dict) -> None:
    _section("5. 가장 크게 깨진 거래")
    trades = sorted(stats.get("trades") or [], key=lambda t: t["pnl_pct"])[:5]
    if not trades:
        print("  기록 없음")
        return
    for t in trades:
        print(f"  {str(t.get('name') or t.get('code')):<12} {t['pnl_pct']:+7.2f}%  "
              f"{t.get('held_days', 0):>2}일  "
              f"{t.get('pnl_amount', 0):>10,.0f}원")
    print("\n  이 종목들을 왜 샀는지는 대시보드 '최근 AI 판단' 의 사유에서 볼 수 있습니다.")


def _engines(db) -> None:
    _section("6. 엔진별 적중률 — 어느 판단이 맞았나")
    acc = queries.engine_accuracy(db)
    if not acc.get("ready") or not acc.get("engines"):
        print("  아직 집계할 기록이 부족합니다.")
        return
    print(f"  (매수 판단 {acc['horizon_days']}일 뒤 주가로 채점)")
    for row in acc["engines"]:
        print(f"  {str(row.get('engine', '?')):<10} 적중 {row.get('hit_rate', 0):>5.1f}%  "
              f"채점 {row.get('graded', 0):>3}건 / 호출 {row.get('calls', 0)}건  "
              f"관망 {row.get('hold_rate', 0):.0f}%")
    print("\n  관망 비율이 높으면 '틀려서' 가 아니라 '안 사서' 기회를 놓친 것입니다.")


def main() -> int:
    try:
        settings = load()
    except ConfigError as exc:
        print(f"[X] 설정을 읽지 못했습니다:\n{exc}")
        return 1

    db = settings.paths["db"]
    print(LINE)
    print("  자동매매 진단 — 성적이 나쁜 '원인' 을 가린다")
    print(LINE)
    print(f"  DB: {db}")

    stats = queries.trade_stats(db)
    findings: list[str] = []
    findings += _sample(stats)

    if stats["count"]:
        findings += _market(db)
        findings += _expectancy(stats)
        findings += _stops(stats, settings.risk)
        _worst(stats)
        _engines(db)
    else:
        findings += _market(db)

    _section("판정")
    if not findings:
        print("  뚜렷한 결함이 보이지 않습니다. 표본을 더 쌓고 다시 보세요.")
    else:
        for item in findings:
            print(f"  · {item}")

    print()
    print("  처방은 원인마다 다릅니다:")
    print("    표본 부족        → 아무것도 바꾸지 말고 더 돌린다")
    print("    시장 하락이 원인 → 전략은 유지. 바꾸면 더 나빠질 수 있다")
    print("    손익비 불량      → settings.yaml 의 익절·손절 폭을 조정")
    print("    승률 부족        → 이때만 CLAUDE_MODEL 을 올릴 값어치가 있다")
    print(LINE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
