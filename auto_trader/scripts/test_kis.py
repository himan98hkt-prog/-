#!/usr/bin/env python3
"""Step 2 검증 스크립트 — 실제 KIS 모의투자 계좌로 끝까지 확인한다.

  1) 토큰 발급 → 즉시 재요청해 **재발급되지 않음**(캐시 사용) 확인
  2) 삼성전자 현재가 / 일봉 60일 / 호가 조회
  3) 잔고 조회
  4) 모의투자 1주 시장가 매수 → 체결 확인 → 1주 매도

사용법:
    python scripts/test_kis.py              # 전체(주문 포함)
    python scripts/test_kis.py --no-order   # 조회만
    python scripts/test_kis.py --code 000660

실전(KIS_ENV=REAL)에서는 주문 단계를 실행하지 않는다(--allow-real 로만 해제).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigError, load  # noqa: E402
from trading.kis_api import KisApi, KisApiError  # noqa: E402
from trading.kis_auth import KisAuthError, TokenManager  # noqa: E402
from trading.market_calendar import market_state  # noqa: E402
from utils.logger import get_logger, register_secret, setup_logging  # noqa: E402

logger = get_logger("test_kis")

FILL_POLL_SECONDS = 5
FILL_TIMEOUT_SECONDS = 30


def step(title: str) -> None:
    logger.info("")
    logger.info("─" * 60)
    logger.info("▶ %s", title)
    logger.info("─" * 60)


def check_token(auth: TokenManager) -> bool:
    """두 번째 호출에서 토큰이 재발급되지 않아야 한다."""
    step("1. 토큰 발급 · 캐시 확인")
    first = auth.get_access_token()
    logger.info("1차 토큰 확보 (길이 %d)", len(first))

    issued_at_1 = auth.token_path.read_text(encoding="utf-8")
    fresh = TokenManager(auth.env, auth.token_path)  # 새 프로세스처럼 다시 로드
    second = fresh.get_access_token()
    issued_at_2 = auth.token_path.read_text(encoding="utf-8")

    reused = first == second and issued_at_1 == issued_at_2
    logger.info("2차 호출 결과: %s", "캐시 재사용 ✅" if reused else "재발급됨 ❌")
    return reused


def check_quotes(api: KisApi, code: str) -> bool:
    step(f"2. 시세 조회 ({code})")
    quote = api.get_current_price(code)
    logger.info(
        "현재가: %s %s원 (%+.2f%%) 거래량 %s / PER %.2f PBR %.2f",
        quote["name"], f"{quote['current']:,}", quote["change_pct"],
        f"{quote['volume']:,}", quote["per"], quote["pbr"],
    )

    df = api.get_daily_ohlcv(code, days=60)
    logger.info(
        "일봉 %d건 (%s ~ %s), 최근 종가 %s원",
        len(df),
        df.iloc[0]["date"].date(),
        df.iloc[-1]["date"].date(),
        f"{int(df.iloc[-1]['close']):,}",
    )

    book = api.get_orderbook(code)
    logger.info(
        "호가: 매도1 %s / 매수1 %s (스프레드 %.3f%%), 총잔량 매도 %s · 매수 %s",
        f"{book['best_ask']:,}", f"{book['best_bid']:,}", book["spread_pct"],
        f"{book['ask_total']:,}", f"{book['bid_total']:,}",
    )
    return quote["current"] > 0 and len(df) > 0 and book["best_ask"] > 0


def check_balance(api: KisApi) -> bool:
    step("3. 잔고 조회")
    balance = api.get_balance()
    logger.info("예수금 %s원 / 주문가능(D+2) %s원 / 순자산 %s원",
                f"{balance.deposit:,.0f}", f"{balance.orderable_cash:,.0f}", f"{balance.net_asset:,.0f}")
    if balance.holdings:
        for holding in balance.holdings:
            logger.info(
                "  · %s(%s) %d주 @%s원 → %s원 (%+.2f%%)",
                holding.name, holding.code, holding.qty,
                f"{holding.avg_price:,.0f}", f"{holding.current_price:,.0f}", holding.pnl_pct,
            )
    else:
        logger.info("  보유 종목 없음")
    return True


def wait_for_fill(api: KisApi, order_no: str) -> bool:
    """최대 30초 동안 5초 간격으로 체결을 확인한다."""
    for _ in range(max(FILL_TIMEOUT_SECONDS // FILL_POLL_SECONDS, 1)):
        time.sleep(FILL_POLL_SECONDS)
        status = api.get_order_status(order_no)
        if status is None:
            logger.info("  체결내역에 아직 없음 — 재조회")
            continue
        logger.info("  상태: %s (%d/%d주 체결, 평균 %s원)",
                    status.status or "-", status.filled_qty, status.order_qty,
                    f"{status.filled_price:,.0f}")
        if status.is_filled:
            return True
    logger.warning("  %d초 내 전량 체결되지 않았습니다", FILL_TIMEOUT_SECONDS)
    return False


def check_order_roundtrip(api: KisApi, code: str) -> bool:
    step(f"4. 모의투자 1주 매수 → 체결 확인 → 1주 매도 ({code})")
    state = market_state()
    if state != "OPEN":
        logger.warning("현재 장 상태가 %s 입니다 — 주문이 거부될 수 있습니다", state)

    buy = api.place_order(code, 1, "BUY")
    logger.info("매수 주문번호 %s (조직 %s, %s)", buy.order_no, buy.org_no, buy.order_time)
    bought = wait_for_fill(api, buy.order_no)
    if not bought:
        logger.error("매수 미체결 — 매도 단계를 건너뜁니다")
        return False

    sell = api.place_order(code, 1, "SELL")
    logger.info("매도 주문번호 %s", sell.order_no)
    sold = wait_for_fill(api, sell.order_no)
    if not sold:
        logger.error("매도 미체결")
    return bought and sold


def main() -> int:
    parser = argparse.ArgumentParser(description="KIS 연동 검증 (Step 2)")
    parser.add_argument("--code", default="005930", help="검증할 종목코드 (기본: 삼성전자)")
    parser.add_argument("--no-order", action="store_true", help="주문 단계를 건너뛰고 조회만 수행")
    parser.add_argument("--allow-real", action="store_true", help="실전 계좌에서도 주문 단계를 실행(위험)")
    args = parser.parse_args()

    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    register_secret(env.kis_app_key, env.kis_app_secret)
    setup_logging(env.log_level, settings.paths["logs"])
    logger.info("KIS 연동 검증 시작 — 환경 %s (%s)", env.kis_env, env.base_url)

    auth = TokenManager(env, settings.paths["token"])
    api = KisApi(env, auth)

    results: dict[str, bool] = {}
    try:
        results["토큰 캐시"] = check_token(auth)
        results["시세 조회"] = check_quotes(api, args.code)
        results["잔고 조회"] = check_balance(api)

        if args.no_order:
            logger.info("--no-order 지정 — 주문 단계를 건너뜁니다")
        elif env.is_real and not args.allow_real:
            logger.warning("실전(REAL) 환경입니다 — 주문 단계를 건너뜁니다 (--allow-real 로 해제)")
        else:
            results["주문 왕복"] = check_order_roundtrip(api, args.code)
    except (KisApiError, KisAuthError) as exc:
        logger.error("검증 중단: %s", exc)
        return 1

    step("결과 요약")
    for name, passed in results.items():
        logger.info("  %s %s", "✅" if passed else "❌", name)
    failed = [name for name, passed in results.items() if not passed]
    if failed:
        logger.error("실패 항목: %s", ", ".join(failed))
        return 1
    logger.info("모든 항목 통과 — Step 2 완료 조건 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
