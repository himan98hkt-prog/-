"""대시보드가 읽는 조회 함수 모음 (전부 읽기 전용)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from utils.db import connect, get_bot_state

KST = ZoneInfo("Asia/Seoul")


def _rows(db_path: Path | str, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def overview(db_path: Path | str, *, now: datetime | None = None) -> dict[str, Any]:
    """상단 요약 타일 값."""
    moment = now or datetime.now(KST)
    today = moment.strftime("%Y-%m-%d")

    positions = _rows(db_path, "SELECT * FROM positions ORDER BY pnl_pct DESC")
    pnl = _rows(db_path, "SELECT * FROM daily_pnl WHERE date = ?", (today,))
    state = get_bot_state(db_path)

    # 거부된 주문은 '오늘 주문' 에 세지 않는다 — 체결되지도, 접수되지도 않았다.
    orders_today = _rows(
        db_path,
        """SELECT side, status, dry_run FROM orders
           WHERE substr(created_at, 1, 10) = ? AND status != 'REJECTED'""",
        (today,),
    )
    rejected_today = _rows(
        db_path,
        """SELECT COUNT(*) n FROM orders
           WHERE substr(created_at, 1, 10) = ? AND status = 'REJECTED'""",
        (today,),
    )[0]["n"]
    cost = _rows(
        db_path,
        """SELECT COALESCE(SUM(cost_usd), 0) total, COALESCE(SUM(input_tokens), 0) input,
                  COALESCE(SUM(output_tokens), 0) output, COUNT(*) calls,
                  COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) failures
           FROM ai_usage WHERE substr(created_at, 1, 10) = ?""",
        (today,),
    )[0]

    eval_amount = sum(float(p["eval_amount"] or 0) for p in positions)
    pnl_amount = sum(float(p["pnl_amount"] or 0) for p in positions)

    return {
        "date": today,
        "state": state,
        "position_count": len(positions),
        "eval_amount": eval_amount,
        "unrealized_pnl": pnl_amount,
        "end_equity": float(pnl[0]["end_equity"]) if pnl else 0.0,
        "start_equity": float(pnl[0]["start_equity"]) if pnl else 0.0,
        "daily_pnl_pct": float(pnl[0]["total_pnl_pct"]) if pnl else 0.0,
        "buy_count": sum(1 for o in orders_today if o["side"] == "BUY"),
        "sell_count": sum(1 for o in orders_today if o["side"] == "SELL"),
        "dry_run_orders": sum(1 for o in orders_today if o["dry_run"] == 1),
        "rejected_orders": int(rejected_today),
        "ai_cost_usd": float(cost["total"]),
        "ai_calls": int(cost["calls"]),
        "ai_failures": int(cost["failures"]),
        "ai_tokens": int(cost["input"]) + int(cost["output"]),
    }


def positions(db_path: Path | str, stop_loss_pct: float, take_profit_pct: float) -> list[dict[str, Any]]:
    """보유 종목 + 손절·익절선까지 남은 거리."""
    result = []
    for row in _rows(db_path, "SELECT * FROM positions ORDER BY pnl_pct DESC"):
        pnl_pct = float(row["pnl_pct"] or 0)
        row["to_stop_loss"] = round(pnl_pct - stop_loss_pct, 2)
        row["to_take_profit"] = round(take_profit_pct - pnl_pct, 2)
        row["danger"] = pnl_pct <= stop_loss_pct + 1.0  # 손절선 1%p 이내
        result.append(row)
    return result


def recent_decisions(db_path: Path | str, limit: int = 30) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT cycle_id, code, name, holding, claude_action, claude_confidence, claude_ok,
                  gemini_action, gemini_confidence, gemini_ok,
                  chatgpt_action, chatgpt_confidence, chatgpt_ok,
                  final_action, final_weight_pct,
                  final_reason, forced_exit, risk_passed, risk_reason, created_at
           FROM decisions ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def recent_orders(db_path: Path | str, limit: int = 20) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT code, name, side, order_type, qty, price, filled_qty, filled_price,
                  status, dry_run, reason, error, created_at
           FROM orders ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def equity_series(db_path: Path | str, days: int = 30) -> list[dict[str, Any]]:
    """일자별 자산·손익률 (차트용, 오래된 순)."""
    rows = _rows(
        db_path,
        """SELECT date, start_equity, end_equity, total_pnl_pct
           FROM daily_pnl ORDER BY date DESC LIMIT ?""",
        (days,),
    )
    return list(reversed(rows))


def ai_cost_series(db_path: Path | str, days: int = 14) -> list[dict[str, Any]]:
    return list(reversed(_rows(
        db_path,
        """SELECT substr(created_at, 1, 10) date, SUM(cost_usd) cost, COUNT(*) calls
           FROM ai_usage GROUP BY 1 ORDER BY 1 DESC LIMIT ?""",
        (days,),
    )))


def decision_mix(db_path: Path | str, *, now: datetime | None = None) -> dict[str, int]:
    """당일 최종 결정 분포."""
    today = (now or datetime.now(KST)).strftime("%Y-%m-%d")
    rows = _rows(
        db_path,
        """SELECT final_action, COUNT(*) n FROM decisions
           WHERE substr(created_at, 1, 10) = ? GROUP BY 1 ORDER BY n DESC""",
        (today,),
    )
    return {row["final_action"]: row["n"] for row in rows}


def recent_risk_blocks(db_path: Path | str, limit: int = 8) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT code, name, risk_reason, created_at FROM decisions
           WHERE risk_passed = 0 AND risk_reason != '' ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def log_tail(log_dir: Path | str, lines: int = 40) -> list[str]:
    """오늘 로그의 마지막 N줄."""
    path = Path(log_dir) / f"trader_{datetime.now(KST):%Y%m%d}.log"
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-lines:]


def benchmark_comparison(db_path: Path | str) -> dict[str, Any]:
    """자동매매 성적 vs 감시 종목을 그냥 사서 들고만 있었을 때.

    벤치마크는 **첫날 관측된 종목들에 똑같이 나눠 담고 그대로 둔** 포트폴리오다.
    동일 비중이므로 수익률은 종목별 수익률의 평균과 같아, 주식 수를 따로
    들고 있을 필요가 없다. 나중에 감시 목록에 추가된 종목은 시작 가격이 없어
    제외한다 — 넣으면 '오른 뒤에 담은' 셈이 되어 벤치마크가 유리해진다.
    """
    empty = {"ready": False, "reason": "", "start_date": "", "days": 0,
             "codes": 0, "benchmark_pct": 0.0, "actual_pct": 0.0, "edge_pct": 0.0,
             "legs": []}
    conn = connect(db_path)
    try:
        dates = [row["date"] for row in conn.execute(
            "SELECT DISTINCT date FROM benchmark_prices ORDER BY date")]
        if not dates:
            empty["reason"] = "아직 기록이 없습니다 — 첫 사이클이 돌면 쌓입니다"
            return empty
        first, last = dates[0], dates[-1]
        if first == last:
            empty["reason"] = "거래일 2일치가 쌓이면 비교가 표시됩니다"
            empty["start_date"] = first
            return empty

        start = {row["code"]: row for row in conn.execute(
            "SELECT code, name, price FROM benchmark_prices WHERE date = ?", (first,))}
        end = {row["code"]: row["price"] for row in conn.execute(
            "SELECT code, price FROM benchmark_prices WHERE date = ?", (last,))}

        legs = []
        for code, row in start.items():
            if code not in end or not row["price"]:
                continue  # 마지막 날 값이 없으면 비교가 성립하지 않는다
            change = (end[code] / row["price"] - 1) * 100
            legs.append({"code": code, "name": row["name"] or code,
                         "pct": round(change, 2)})
        if not legs:
            empty["reason"] = "비교할 종목이 없습니다"
            empty["start_date"] = first
            return empty
        legs.sort(key=lambda leg: leg["pct"], reverse=True)
        benchmark_pct = sum(leg["pct"] for leg in legs) / len(legs)

        # 실제 성적: 첫날 시작 자산 대비 마지막으로 기록된 평가 자산.
        rows = list(conn.execute(
            """SELECT date, start_equity, end_equity FROM daily_pnl
               WHERE date >= ? ORDER BY date""", (first,)))
    finally:
        conn.close()

    opening = next((float(r["start_equity"]) for r in rows if r["start_equity"]), 0.0)
    closing = next((float(r["end_equity"]) for r in reversed(rows) if r["end_equity"]), 0.0)
    actual_pct = ((closing / opening - 1) * 100) if opening > 0 else 0.0

    return {
        "ready": True, "reason": "", "start_date": first, "end_date": last,
        "days": len(dates), "codes": len(legs),
        "benchmark_pct": round(benchmark_pct, 2),
        "actual_pct": round(actual_pct, 2),
        "edge_pct": round(actual_pct - benchmark_pct, 2),
        "legs": legs,
    }
