#!/usr/bin/env python3
"""Step 3 검증 스크립트 — 유니버스 → 스냅샷 수집 → JSON 저장.

  1) 잔고 조회 후 유니버스 생성 (보유 종목 포함)
  2) 각 종목의 현재가·일봉·호가·지표·뉴스를 모아 스냅샷 생성
  3) `data/snapshots/YYYYMMDD_HHMMSS_<코드>.json` 저장 + 스키마 검증

사용법:
    python scripts/test_pipeline.py                  # 유니버스 전체
    python scripts/test_pipeline.py --code 005930    # 한 종목만
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigError, load  # noqa: E402
from data_pipeline.market_data import collect  # noqa: E402
from data_pipeline.universe import build_universe  # noqa: E402
from trading.kis_api import Balance, KisApi, KisApiError  # noqa: E402
from trading.kis_auth import KisAuthError, TokenManager  # noqa: E402
from utils.logger import get_logger, register_secret, setup_logging  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("test_pipeline")

# 5-5 고정 스키마 — 키가 빠지면 AI 프롬프트가 깨지므로 여기서 잡는다.
REQUIRED_SCHEMA: dict[str, tuple[str, ...]] = {
    "": ("code", "name", "timestamp", "price", "valuation", "indicators",
         "orderbook", "recent_closes_20d", "position", "news"),
    "price": ("current", "change_pct", "open", "high", "low", "volume", "volume_ratio_20d"),
    "valuation": ("market_cap", "per", "pbr"),
    "indicators": ("ma5", "ma20", "ma60", "rsi14", "macd", "macd_signal",
                   "macd_hist", "bb_upper", "bb_lower"),
    "orderbook": ("bid_total", "ask_total", "spread_pct"),
    "position": ("holding", "qty", "avg_price", "pnl_pct"),
}


def validate_schema(snapshot: dict) -> list[str]:
    """누락된 키 목록을 반환한다(빈 리스트면 통과)."""
    missing: list[str] = []
    for section, keys in REQUIRED_SCHEMA.items():
        target = snapshot if section == "" else snapshot.get(section, {})
        if not isinstance(target, dict):
            missing.append(f"{section}: 딕셔너리가 아님")
            continue
        missing.extend(f"{section}.{key}".lstrip(".") for key in keys if key not in target)
    return missing


def save_snapshot(snapshot: dict, snapshot_dir: Path, timestamp: datetime) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{timestamp:%Y%m%d_%H%M%S}_{snapshot['code']}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def summarize(snapshot: dict) -> None:
    price, indicators, position = snapshot["price"], snapshot["indicators"], snapshot["position"]
    logger.info(
        "  %s(%s) %s원 (%+.2f%%) 거래량 %.1f배 / RSI %.1f / MA5 %s·MA20 %s / MACD %.2f",
        snapshot["name"], snapshot["code"], f"{price['current']:,}", price["change_pct"],
        price["volume_ratio_20d"], indicators["rsi14"],
        f"{indicators['ma5']:,.0f}", f"{indicators['ma20']:,.0f}", indicators["macd"],
    )
    if position["holding"]:
        logger.info("    보유 %d주 @%s원 (%+.2f%%)",
                    position["qty"], f"{position['avg_price']:,.0f}", position["pnl_pct"])
    logger.info("    뉴스 %d건 / 최근 종가 %d개", len(snapshot["news"]), len(snapshot["recent_closes_20d"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="데이터 파이프라인 검증 (Step 3)")
    parser.add_argument("--code", help="이 종목만 수집 (지정 시 유니버스 생성 생략)")
    args = parser.parse_args()

    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    register_secret(env.kis_app_key, env.kis_app_secret)
    setup_logging(env.log_level, settings.paths["logs"])
    logger.info("데이터 파이프라인 검증 시작 — %s", env.kis_env)

    auth = TokenManager(env, settings.paths["token"])
    api = KisApi(env, auth)
    timestamp = datetime.now(KST)

    try:
        balance: Balance | None = None
        if args.code:
            codes = [args.code]
        else:
            balance = api.get_balance()
            codes = build_universe(api, settings, balance=balance, now=timestamp)
        if not codes:
            logger.error("유니버스가 비어 있습니다 — settings.yaml 의 watchlist 를 확인하세요")
            return 1

        logger.info("수집 대상 %d종목: %s", len(codes), ", ".join(codes))
        failures: list[str] = []
        for code in codes:
            try:
                holding = balance.by_code(code) if balance else None
                snapshot = collect(code, api, settings, holding=holding, now=timestamp)
                missing = validate_schema(snapshot)
                if missing:
                    logger.error("  %s 스키마 누락: %s", code, ", ".join(missing))
                    failures.append(code)
                    continue
                path = save_snapshot(snapshot, settings.paths["snapshots"], timestamp)
                summarize(snapshot)
                logger.info("    저장: %s", path)
            except KisApiError as exc:
                logger.error("  %s 수집 실패: %s", code, exc)
                failures.append(code)
    except (KisApiError, KisAuthError) as exc:
        logger.error("검증 중단: %s", exc)
        return 1

    if failures:
        logger.error("실패 종목: %s", ", ".join(failures))
        return 1
    logger.info("전 종목 수집·스키마 검증 통과 — Step 3 완료 조건 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
