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


def export_csv(db_path: Path | str, out_dir: Path | str, *, since: str = "") -> list[Path]:
    """`decisions`·`orders` 테이블을 CSV로 내보낸다 (Step 7 리포트용)."""
    import csv

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    conn = connect(db_path)
    try:
        for table in ("decisions", "orders"):
            query = f"SELECT * FROM {table}"
            params: tuple = ()
            if since:
                query += " WHERE substr(created_at, 1, 10) >= ?"
                params = (since,)
            rows = conn.execute(query + " ORDER BY id", params).fetchall()
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
