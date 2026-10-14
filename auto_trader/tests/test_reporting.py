"""일간 리포트 집계·CSV 내보내기 테스트."""

from __future__ import annotations

import csv
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from logic.reporting import build_daily_report, export_csv
from utils.db import connect, init_db

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 9, 8, 15, 40, tzinfo=KST)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "trader.db"
    init_db(path)
    conn = connect(path)
    conn.execute(
        """INSERT INTO daily_pnl (date, start_equity, end_equity, realized_pnl,
                                  unrealized_pnl, total_pnl_pct, updated_at)
           VALUES ('2026-09-08', 5000000, 5061500, 0, 61500, 1.23, '2026-09-08T15:40:00+09:00')"""
    )
    rows = [
        ("BUY", "FILLED", 0, "005930", "삼성전자", 12, "2026-09-08T09:35:00+09:00"),
        ("BUY", "DRY_RUN", 1, "000660", "SK하이닉스", 3, "2026-09-08T08:30:00+09:00"),
        ("SELL", "FILLED", 0, "035420", "NAVER", 5, "2026-09-08T14:05:00+09:00"),
        ("BUY", "FILLED", 0, "051910", "LG화학", 1, "2026-09-07T10:00:00+09:00"),  # 전일
    ]
    for side, status, dry, code, name, qty, created in rows:
        conn.execute(
            """INSERT INTO orders (cycle_id, order_no, code, name, side, order_type, qty, price,
                                   filled_qty, filled_price, status, dry_run, kis_env,
                                   created_at, updated_at)
               VALUES ('c1', 'O1', ?, ?, ?, 'market', ?, 70000, ?, 70000, ?, ?, 'VTS', ?, ?)""",
            (code, name, side, qty, qty, status, dry, created, created),
        )
    conn.execute(
        """INSERT INTO positions (code, name, qty, avg_price, current_price, eval_amount,
                                  pnl_amount, pnl_pct, first_bought_at, updated_at)
           VALUES ('005930', '삼성전자', 12, 70000, 71300, 855600, 15600, 1.86,
                   '2026-09-08T09:35:00+09:00', '2026-09-08T15:40:00+09:00')"""
    )
    conn.execute(
        """INSERT INTO decisions (cycle_id, code, holding, final_action, final_weight_pct,
                                  created_at)
           VALUES ('c1', '005930', 1, 'STRONG_BUY', 15, '2026-09-08T09:35:00+09:00')"""
    )
    conn.close()
    return path


def test_report_aggregates_today_only(db):
    report = build_daily_report(db, DAY)

    assert report["date"] == "2026-09-08"
    assert report["total_pnl_pct"] == pytest.approx(1.23)
    assert report["end_equity"] == 5_061_500
    assert report["buy_count"] == 2, "전일 매수는 제외"
    assert report["sell_count"] == 1
    assert report["decision_count"] == 1


def test_report_counts_premarket_orders_same_day(db):
    """08:30 기록도 당일로 잡혀야 한다 (SQLite date() 의 UTC 환산 회피)."""
    report = build_daily_report(db, DAY)
    codes = {order["code"] for order in report["orders"]}
    assert "000660" in codes


def test_report_includes_positions(db):
    report = build_daily_report(db, DAY)
    assert report["position_count"] == 1
    assert report["positions"][0]["name"] == "삼성전자"
    assert report["positions"][0]["pnl_pct"] == pytest.approx(1.86)


def test_report_on_empty_day(tmp_path):
    path = tmp_path / "empty.db"
    init_db(path)
    report = build_daily_report(path, DAY)
    assert report["total_pnl_pct"] == 0.0
    assert report["buy_count"] == report["sell_count"] == report["position_count"] == 0


def test_export_csv_writes_all_tables(db, tmp_path):
    out = tmp_path / "export"
    files = export_csv(db, out)

    assert {path.name for path in files} == {"decisions.csv", "orders.csv", "daily_pnl.csv"}
    with (out / "orders.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][0] == "id" and len(rows) == 5  # 헤더 + 4건


def test_export_csv_respects_since(db, tmp_path):
    out = tmp_path / "export"
    export_csv(db, out, since="2026-09-08")
    with (out / "orders.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 4, "전일 주문은 제외 (헤더 + 3건)"


def test_export_csv_respects_until(db, tmp_path):
    out = tmp_path / "export"
    export_csv(db, out, until="2026-09-07")
    with (out / "orders.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 2, "당일 주문은 제외 (헤더 + 전일 1건)"


def test_export_csv_daily_pnl_uses_date_column(db, tmp_path):
    out = tmp_path / "export"
    export_csv(db, out, since="2026-09-08", tables=("daily_pnl",))
    with (out / "daily_pnl.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 2 and rows[1][0] == "2026-09-08"


# --------------------------------------------------------------------------- #
# 기간 집계
# --------------------------------------------------------------------------- #


def test_period_summary_counts_and_distributions(db):
    from logic.reporting import build_period_summary

    summary = build_period_summary(db)
    assert summary["order_count"] == 4
    assert summary["buy_count"] == 3 and summary["sell_count"] == 1
    assert summary["dry_run_count"] == 1
    assert summary["decision_count"] == 1
    assert summary["final_actions"] == {"STRONG_BUY": 1}
    assert summary["order_statuses"]["FILLED"] == 3


def test_period_summary_filters_by_date(db):
    from logic.reporting import build_period_summary

    summary = build_period_summary(db, since="2026-09-08")
    assert summary["order_count"] == 3, "전일 주문 제외"
    assert len(summary["daily_pnl"]) == 1


def test_period_summary_reports_parse_failure_rate(tmp_path):
    from logic.reporting import build_period_summary

    path = tmp_path / "t.db"
    init_db(path)
    conn = connect(path)
    rows = [
        ("BUY", 1, "HOLD", 0, "HOLD"),   # gemini 파싱 실패
        ("BUY", 1, "BUY", 1, "STRONG_BUY"),
        ("HOLD", 0, "HOLD", 1, "HOLD"),  # claude 파싱 실패
    ]
    for claude_action, claude_ok, gemini_action, gemini_ok, final in rows:
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, holding, claude_action, claude_ok,
                                      gemini_action, gemini_ok, final_action, final_weight_pct,
                                      risk_passed, created_at)
               VALUES ('c1', '005930', 0, ?, ?, ?, ?, ?, 0, 1, '2026-09-08T09:35:00+09:00')""",
            (claude_action, claude_ok, gemini_action, gemini_ok, final),
        )
    conn.close()

    summary = build_period_summary(path)
    assert summary["agent_calls"] == {"claude": 3, "gemini": 3}
    assert summary["agent_failures"] == {"claude": 1, "gemini": 1}
    assert summary["parse_failure_pct"]["claude"] == pytest.approx(33.33)
    assert summary["cycles"] == 1 and summary["trading_days"] == 1


def test_period_summary_on_empty_db(tmp_path):
    from logic.reporting import build_period_summary

    path = tmp_path / "empty.db"
    init_db(path)
    summary = build_period_summary(path)
    assert summary["decision_count"] == 0 and summary["order_count"] == 0
    assert summary["parse_failure_pct"] == {"claude": 0.0, "gemini": 0.0}
