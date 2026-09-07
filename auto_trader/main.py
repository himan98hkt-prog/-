"""진입점.

Step 1 범위: 설정 로드·검증 → 로깅 구성 → SQLite 스키마 생성 → 구성 요약 출력.
스케줄러 등록(apscheduler)과 매매 사이클은 Step 6에서 이 파일에 이어 붙인다.

사용법:
    python main.py            # 부트스트랩 점검
    python main.py --check    # 동일 (명시적)
"""

from __future__ import annotations

import sys

from config.loader import ConfigError, Settings, load
from utils.db import init_db, table_names
from utils.logger import get_logger, register_secret, setup_logging

logger = get_logger("main")


def bootstrap() -> Settings:
    """설정 → 로깅 → DB 순으로 준비하고 Settings를 반환한다."""
    settings = load()

    # 로거 구성 전에 비밀값을 등록해 두면 이후 모든 로그에서 자동 마스킹된다.
    register_secret(
        settings.env.kis_app_key,
        settings.env.kis_app_secret,
        settings.env.anthropic_api_key,
        settings.env.gemini_api_key,
        settings.env.telegram_bot_token,
        settings.env.discord_webhook_url,
        settings.env.naver_client_secret,
    )
    setup_logging(settings.env.log_level, settings.paths["logs"])

    init_db(settings.paths["db"])
    return settings


def main() -> int:
    try:
        settings = bootstrap()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    logger.info("=" * 60)
    logger.info("Multi-Agent 자동매매 부트스트랩 완료")
    logger.info("모드: %s (%s) / DRY_RUN: %s", env.kis_env, env.base_url, "on" if env.dry_run else "off")
    logger.info("계좌: %s-%s", "*" * 4 + env.kis_account_no[-4:], env.kis_account_product_cd)
    logger.info("AI: claude=%s / gemini=%s", env.claude_model, env.gemini_model)
    logger.info("알림: %s / 뉴스 수집: %s", env.notifier, "on" if env.news_enabled else "off(키 미설정)")
    logger.info("유니버스: %s (%d종목) / 사이클 %d분", settings.universe.mode, len(settings.universe.watchlist), settings.schedule.cycle_interval_min)
    logger.info(
        "리스크: 총액 %s원 / 종목당 %.0f%% / 최대 %d종목 / 손절 %.1f%% / 익절 %.1f%%",
        f"{settings.risk.total_investment_cap_krw:,}",
        settings.risk.max_position_pct,
        settings.risk.max_positions,
        settings.risk.stop_loss_pct,
        settings.risk.take_profit_pct,
    )
    logger.info("DB 테이블: %s", ", ".join(table_names(settings.paths["db"])))
    if env.is_real:
        logger.warning("⚠ 실전(REAL) 모드입니다. 기동 알림은 Step 6에서 텔레그램으로도 전송됩니다.")
    logger.info("=" * 60)
    logger.info("Step 1 완료 — 매매 로직은 Step 2 이후 단계에서 연결됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
