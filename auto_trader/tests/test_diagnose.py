"""진단 스크립트 — 같은 손실을 **다른 원인**으로 가려내는지.

"-10%" 라는 숫자 하나는 네 가지 전혀 다른 상황을 뜻할 수 있고, 처방이 각각
정반대다. 표본이 모자라면 아무것도 바꾸면 안 되고, 시장이 더 빠졌으면 전략을
건드리면 오히려 나빠지고, 손익비가 문제면 익절·손절 폭을 고쳐야 하며, 승률이
문제일 때만 AI 쪽을 손볼 값어치가 있다.

그래서 이 테스트는 출력 문구가 아니라 **판정이 갈리는지**를 본다.
"""

from __future__ import annotations

import pytest

from scripts import diagnose


def trade(pnl_pct: float, *, code="005930", name="삼성전자", days=3,
          qty=10, entry=70_000):
    exit_price = entry * (1 + pnl_pct / 100)
    return {
        "code": code, "name": name, "qty": qty,
        "entry_price": entry, "exit_price": exit_price,
        "entry_at": "2026-10-01 10:00:00", "exit_at": "2026-10-04 10:00:00",
        "pnl_pct": pnl_pct,
        "pnl_amount": (exit_price - entry) * qty,
        "held_days": days,
    }


def stats(trades, **over):
    """trade_stats() 와 같은 모양을 만든다 (계산식은 실제 구현을 그대로 쓴다)."""
    wins = [t["pnl_pct"] for t in trades if t["pnl_pct"] > 0]
    losses = [t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    payoff = (avg_win / abs(avg_loss)) if avg_loss else 0.0
    breakeven = (1 / (1 + payoff) * 100) if payoff else 0.0
    win_ratio = len(wins) / len(trades) if trades else 0.0
    base = {
        "ready": bool(trades), "count": len(trades),
        "expectancy": win_ratio * avg_win + (1 - win_ratio) * avg_loss,
        "win_rate": round(win_ratio * 100, 1),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "payoff": round(payoff, 2), "breakeven_win_rate": round(breakeven, 1),
        "avg_days": 3.0, "realized_krw": 0, "fee_krw": 0, "trades": trades,
    }
    return {**base, **over}


class Risk:
    stop_loss_pct = -5.0


# --- 표본 ------------------------------------------------------------------ #

def test_a_small_sample_refuses_to_draw_a_conclusion(capsys):
    """거래 5건으로 전략을 판단하면 운을 실력으로 착각한다."""
    found = diagnose._sample(stats([trade(-2.0)] * 5))
    assert any("표본 부족" in f for f in found)
    out = capsys.readouterr().out
    assert "우연의 범위" in out
    assert "운인지" in out, "왜 바꾸면 안 되는지까지 말해야 한다"


def test_no_closed_trades_says_so(capsys):
    found = diagnose._sample(stats([]))
    assert found == ["표본 없음"]
    assert "평가손익만으로는" in capsys.readouterr().out


def test_a_large_sample_raises_no_objection():
    assert diagnose._sample(stats([trade(-2.0)] * 25)) == []


# --- 기대값: 같은 손실, 다른 원인 ------------------------------------------- #

def test_bad_payoff_is_not_blamed_on_the_model(capsys):
    """승률은 높은데 이익을 일찍 자르고 손실을 끄는 경우.

    이건 익절·손절 폭의 문제다. 여기서 모델을 올리면 돈만 더 쓰고 그대로다.
    """
    trades = [trade(1.0)] * 14 + [trade(-6.0)] * 6   # 승률 70%, 손익비 0.17
    found = diagnose._expectancy(stats(trades))
    out = capsys.readouterr().out
    assert any("손익비" in f for f in found), found
    assert "AI 모델을 올려서 해결되는 문제가 아닙니다" in out


def test_low_win_rate_is_the_one_case_that_points_at_the_model(capsys):
    """손익비는 괜찮은데 승률이 본전선에 못 미치는 경우 → 종목 선택 문제."""
    trades = [trade(9.0)] * 5 + [trade(-4.0)] * 15   # 승률 25%, 손익비 2.25, 본전 30.8%
    result = stats(trades)
    assert result["payoff"] >= 1.5 and result["win_rate"] < result["breakeven_win_rate"]
    found = diagnose._expectancy(result)
    assert any("승률 부족" in f for f in found), found
    assert "AI 판단을 손볼 값어치가 있습니다" in capsys.readouterr().out


def test_a_positive_expectancy_is_not_reported_as_a_fault(capsys):
    trades = [trade(5.0)] * 12 + [trade(-3.0)] * 8
    found = diagnose._expectancy(stats(trades))
    assert found == []
    assert "기대값은 양수입니다" in capsys.readouterr().out


# --- 손절 ------------------------------------------------------------------ #

def test_losses_beyond_the_stop_are_flagged(capsys):
    found = diagnose._stops(stats([trade(-12.0)] * 10), Risk())
    out = capsys.readouterr().out
    assert any("손절선 초과" in f for f in found), found
    assert "손절이 늦게" in out


def test_losses_within_the_stop_are_not_flagged(capsys):
    assert diagnose._stops(stats([trade(-4.0)] * 10), Risk()) == []
    assert "설계 범위에서 작동" in capsys.readouterr().out


# --- 시장 대비 --------------------------------------------------------------- #

def test_a_worse_market_clears_the_strategy(capsys, monkeypatch):
    """시장이 더 빠졌으면 전략은 시장을 이긴 것이다 — 바꾸면 더 나빠진다."""
    monkeypatch.setattr(diagnose.queries, "benchmark_comparison", lambda db: {
        "ready": True, "actual_pct": -10.0, "benchmark_pct": -15.0,
        "edge_pct": 5.0, "codes": 10})
    found = diagnose._market("db")
    out = capsys.readouterr().out
    assert any("시장 하락이 주원인" in f for f in found), found
    assert "AI 모델을 올려도" in out


def test_underperforming_buy_and_hold_is_called_out(capsys):
    import types
    queries_stub = types.SimpleNamespace(benchmark_comparison=lambda db: {
        "ready": True, "actual_pct": -10.0, "benchmark_pct": 2.0,
        "edge_pct": -12.0, "codes": 10})
    original = diagnose.queries
    diagnose.queries = queries_stub
    try:
        found = diagnose._market("db")
    finally:
        diagnose.queries = original
    assert any("단순 보유보다 못함" in f for f in found), found
    assert "매매 자체가 가치를 깎고" in capsys.readouterr().out


def test_missing_benchmark_does_not_crash(monkeypatch):
    monkeypatch.setattr(diagnose.queries, "benchmark_comparison",
                        lambda db: {"ready": False, "reason": "기록 부족"})
    assert diagnose._market("db") == []


# --- 출력 전반 --------------------------------------------------------------- #

def test_worst_trades_do_not_crash_on_empty():
    diagnose._worst(stats([]))


@pytest.mark.parametrize("acc", [
    {"ready": False, "engines": []},
    {"ready": True, "horizon_days": 5,
     "engines": [{"engine": "claude", "hit_rate": 55.0, "graded": 20,
                  "calls": 40, "hold_rate": 50.0}]},
])
def test_engine_section_handles_both_states(acc, monkeypatch, capsys):
    monkeypatch.setattr(diagnose.queries, "engine_accuracy", lambda db: acc)
    diagnose._engines("db")
    assert capsys.readouterr().out.strip()
