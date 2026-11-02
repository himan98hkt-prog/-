#!/usr/bin/env python3
"""Step 7 리포트 — 무인 운영 기간의 판단·주문 내역을 CSV로 내보내고 요약을 출력한다.

사용법:
    python scripts/export_report.py                      # 최근 5거래일
    python scripts/export_report.py --days 10
    python scripts/export_report.py --since 2026-09-01 --until 2026-09-05
    python scripts/export_report.py --out reports/week1  # 저장 위치 지정
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigError, load  # noqa: E402
from logic.reporting import build_period_summary, export_csv  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("export_report")


def print_summary(summary: dict) -> None:
    def block(title: str) -> None:
        logger.info("")
        logger.info("─ %s %s", title, "─" * max(50 - len(title), 0))

    logger.info("=" * 60)
    logger.info("운영 리포트 %s ~ %s", summary["since"] or "-", summary["until"] or "-")
    logger.info("=" * 60)

    block("운영 규모")
    logger.info("  거래일 %d일 / 사이클 %d회 / 판단 %d건 / 종목 %d개",
                summary["trading_days"], summary["cycles"],
                summary["decision_count"], summary["codes"])

    block("AI 판단 분포")
    for agent in ("claude", "gemini"):
        actions = summary[f"{agent}_actions"]
        spread = " ".join(f"{k} {v}" for k, v in actions.items() if k != "-") or "없음"
        logger.info("  %-7s %s", agent, spread)
        logger.info("          호출 %d건 중 파싱 실패 %d건 (%.2f%%)",
                    summary["agent_calls"][agent], summary["agent_failures"][agent],
                    summary["parse_failure_pct"][agent])

    block("최종 결정")
    for action, count in summary["final_actions"].items():
        logger.info("  %-12s %d건", action, count)

    if summary["forced_exits"]:
        block("강제 청산")
        for kind, count in summary["forced_exits"].items():
            logger.info("  %-12s %d건", kind, count)

    block("리스크 거부")
    logger.info("  총 %d건", summary["risk_rejections"])
    for reason, count in list(summary["risk_reasons"].items())[:5]:
        logger.info("    · %s — %d건", reason[:60], count)

    block("주문")
    logger.info("  총 %d건 (매수 %d / 매도 %d), DRY_RUN %d건",
                summary["order_count"], summary["buy_count"],
                summary["sell_count"], summary["dry_run_count"])
    for status, count in summary["order_statuses"].items():
        logger.info("    · %-10s %d건", status, count)
    logger.info("  체결 금액 합계 %s원", f"{summary['filled_amount']:,.0f}")

    block("일자별 손익")
    if not summary["daily_pnl"]:
        logger.info("  기록 없음")
    for row in summary["daily_pnl"]:
        logger.info("  %s  시작 %12s → 종료 %12s  (%+.2f%%)",
                    row["date"], f"{row['start_equity']:,.0f}",
                    f"{row['end_equity']:,.0f}", row["total_pnl_pct"])
    logger.info("")


def main() -> int:
    parser = argparse.ArgumentParser(description="운영 리포트 내보내기 (Step 7)")
    parser.add_argument("--since", help="시작일 YYYY-MM-DD")
    parser.add_argument("--until", help="종료일 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=5, help="--since 미지정 시 최근 N일 (기본 5)")
    parser.add_argument("--out", help="CSV 저장 디렉터리 (기본: data/reports/<날짜>)")
    args = parser.parse_args()

    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    setup_logging(settings.env.log_level, settings.paths["logs"])

    today = datetime.now(KST).date()
    since = args.since or (today - timedelta(days=args.days - 1)).strftime("%Y-%m-%d")
    until = args.until or today.strftime("%Y-%m-%d")

    db_path = settings.paths["db"]
    if not Path(db_path).exists():
        logger.error("DB가 없습니다: %s — 먼저 운영을 시작하세요", db_path)
        return 1

    summary = build_period_summary(db_path, since=since, until=until)
    print_summary(summary)

    out_dir = Path(args.out) if args.out else Path(settings.paths["data"]) / "reports" / f"{since}_{until}"
    files = export_csv(db_path, out_dir, since=since, until=until)
    logger.info("CSV 저장 완료:")
    for path in files:
        logger.info("  · %s", path)

    if summary["decision_count"] == 0:
        logger.warning("해당 기간에 판단 기록이 없습니다 — 기간을 확인하세요")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
