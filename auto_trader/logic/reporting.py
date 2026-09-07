"""일간 리포트 집계 — `decisions`·`orders`·`daily_pnl` 테이블에서 뽑아 쓴다."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from utils.db import connect
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("reporting")


def build_daily_report(db_path: Path | str, target: date | datetime | None = None) -> dict[str, Any]:
    """당일 손익·주문 내역·보유 종목 요약."""
    day = (target or datetime.now(KST)).strftime("%Y-%m-%d")

    conn = connect(db_path)
    try:
        pnl = conn.execute("SELECT * FROM daily_pnl WHERE date = ?", (day,)).fetchone()
        # substr 비교: SQLite date() 는 '+09:00' 오프셋을 UTC 로 환산해 날짜를 앞당긴다.
        orders = conn.execute(
            """SELECT side, status, dry_run, code, name, qty, filled_qty, filled_price, price
               FROM orders WHERE substr(created_at, 1, 10) = ? ORDER BY id""",
            (day,),
        ).fetchall()
        positions = conn.execute(
            "SELECT code, name, qty, avg_price, current_price, pnl_pct FROM positions ORDER BY code"
        ).fetchall()
        decision_count = conn.execute(
            "SELECT COUNT(*) c FROM decisions WHERE substr(created_at, 1, 10) = ?", (day,)
        ).fetchone()["c"]
    finally:
        conn.close()

    buys = [row for row in orders if row["side"] == "BUY"]
    sells = [row for row in orders if row["side"] == "SELL"]

    return {
        "date": day,
        "start_equity": float(pnl["start_equity"]) if pnl else 0.0,
        "end_equity": float(pnl["end_equity"]) if pnl else 0.0,
        "total_pnl_pct": float(pnl["total_pnl_pct"]) if pnl else 0.0,
        "unrealized_pnl": float(pnl["unrealized_pnl"]) if pnl else 0.0,
        "buy_count": len(buys),
        "sell_count": len(sells),
        "decision_count": decision_count,
        "position_count": len(positions),
        "positions": [dict(row) for row in positions],
        "orders": [dict(row) for row in orders],
    }


def export_csv(
    db_path: Path | str,
    out_dir: Path | str,
    *,
    since: str = "",
    until: str = "",
    tables: tuple[str, ...] = ("decisions", "orders", "daily_pnl"),
) -> list[Path]:
    """지정 테이블을 CSV로 내보낸다 (Step 7 리포트용)."""
    import csv

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    conn = connect(db_path)
    try:
        for table in tables:
            date_column = "date" if table == "daily_pnl" else "created_at"
            where, params = _period_clause(since, until, column=date_column,
                                           raw_date=table == "daily_pnl")
            order_by = " ORDER BY date" if table == "daily_pnl" else " ORDER BY id"
            rows = conn.execute(f"SELECT * FROM {table}{where}{order_by}", params).fetchall()
            target = out_path / f"{table}.csv"
            with target.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                if rows:
                    writer.writerow(rows[0].keys())
                    writer.writerows([tuple(row) for row in rows])
            written.append(target)
            logger.info("%s → %s (%d행)", table, target, len(rows))
    finally:
        conn.close()
    return written


def build_period_summary(
    db_path: Path | str, *, since: str = "", until: str = ""
) -> dict[str, Any]:
    """기간 집계 — Step 7 무인 운영 리포트용.

    Args:
        since / until: `YYYY-MM-DD`. 비우면 제한 없음.
    """
    where, params = _period_clause(since, until)

    conn = connect(db_path)
    try:
        decisions = conn.execute(f"SELECT * FROM decisions{where} ORDER BY id", params).fetchall()
        orders = conn.execute(f"SELECT * FROM orders{where} ORDER BY id", params).fetchall()
        pnl_where, pnl_params = _period_clause(since, until, column="date", raw_date=True)
        daily = conn.execute(
            f"SELECT * FROM daily_pnl{pnl_where} ORDER BY date", pnl_params
        ).fetchall()
    finally:
        conn.close()

    def distribution(rows, column: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            key = row[column] or "-"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: -item[1]))

    agent_failures = {
        agent: sum(1 for row in decisions if row[f"{agent}_ok"] == 0 and row[f"{agent}_action"] is not None)
        for agent in ("claude", "gemini")
    }
    agent_calls = {
        agent: sum(1 for row in decisions if row[f"{agent}_action"] is not None)
        for agent in ("claude", "gemini")
    }

    rejected = [row for row in decisions if row["risk_passed"] == 0 and row["risk_reason"]]
    filled = [row for row in orders if row["status"] == "FILLED"]

    return {
        "since": since or (decisions[0]["created_at"][:10] if decisions else ""),
        "until": until or (decisions[-1]["created_at"][:10] if decisions else ""),
        "trading_days": len({row["created_at"][:10] for row in decisions}),
        "cycles": len({row["cycle_id"] for row in decisions}),
        "decision_count": len(decisions),
        "codes": len({row["code"] for row in decisions}),
        "claude_actions": distribution(decisions, "claude_action"),
        "gemini_actions": distribution(decisions, "gemini_action"),
        "final_actions": distribution(decisions, "final_action"),
        "agent_calls": agent_calls,
        "agent_failures": agent_failures,
        "parse_failure_pct": {
            agent: round(agent_failures[agent] / agent_calls[agent] * 100, 2) if agent_calls[agent] else 0.0
            for agent in ("claude", "gemini")
        },
        "forced_exits": distribution([row for row in decisions if row["forced_exit"]], "forced_exit"),
        "risk_rejections": len(rejected),
        "risk_reasons": distribution(rejected, "risk_reason"),
        "order_count": len(orders),
        "buy_count": sum(1 for row in orders if row["side"] == "BUY"),
        "sell_count": sum(1 for row in orders if row["side"] == "SELL"),
        "order_statuses": distribution(orders, "status"),
        "dry_run_count": sum(1 for row in orders if row["dry_run"] == 1),
        "filled_amount": sum(float(row["filled_qty"] or 0) * float(row["filled_price"] or 0)
                             for row in filled),
        "daily_pnl": [dict(row) for row in daily],
    }


def _period_clause(
    since: str, until: str, *, column: str = "created_at", raw_date: bool = False
) -> tuple[str, tuple]:
    """기간 필터 SQL 조각. substr 비교로 타임존 환산을 피한다."""
    expression = column if raw_date else f"substr({column}, 1, 10)"
    clauses: list[str] = []
    params: list[str] = []
    if since:
        clauses.append(f"{expression} >= ?")
        params.append(since)
    if until:
        clauses.append(f"{expression} <= ?")
        params.append(until)
    return (f" WHERE {' AND '.join(clauses)}" if clauses else "", tuple(params))
