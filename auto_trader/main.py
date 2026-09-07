"""진입점 — 스케줄러 등록 + 기동/종료 처리.

스케줄:
  universe_refresh  유니버스 갱신
  first_cycle 부터 cycle_interval_min 간격으로 15:00 까지  run_cycle()
  eod_review        보유 종목만 대상으로 청산 여부 재판단
  daily_report      일간 손익·주문 내역 리포트

사용법:
    python main.py              # 스케줄러 기동 (장 시간 동안 상주)
    python main.py --check      # 설정·DB 부트스트랩만 점검하고 종료
    python main.py --once       # 지금 즉시 1사이클만 실행하고 종료
    python main.py --report     # 오늘 일간 리포트만 전송하고 종료
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from datetime import datetime, time as dt_time, timedelta
from types import FrameType
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.base_agent import BaseAgent, run_agents_parallel
from agents.claude_agent import ClaudeAgent
from agents.gemini_agent import GeminiAgent
from agents.schemas import AgentDecision
from config.loader import ConfigError, Settings, load
from data_pipeline.market_data import collect
from data_pipeline.universe import build_universe
from logic.decision_maker import FinalDecision, decide
from logic.portfolio import Portfolio
from logic.reporting import build_daily_report
from logic.risk_manager import RiskManager
from trading.kis_api import KisApi, KisApiError
from trading.kis_auth import KisAuthError, TokenManager
from trading.market_calendar import is_trading_day, market_state
from trading.order_executor import OrderExecutor
from utils.db import init_db, table_names
from utils.logger import get_logger, register_secret, setup_logging
from utils.notifier import Notifier

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("main")

CYCLE_END = dt_time(15, 0)  # 마지막 정규 사이클 시각 상한
MAX_CONSECUTIVE_FAILURES = 3  # 사이클 전체가 이만큼 연속 실패하면 중단


def cycle_times(first: dt_time, interval_min: int, end: dt_time = CYCLE_END) -> list[dt_time]:
    """first 부터 interval 간격으로 end 까지의 사이클 시각 목록."""
    times: list[dt_time] = []
    moment = datetime(2000, 1, 1, first.hour, first.minute)
    limit = datetime(2000, 1, 1, end.hour, end.minute)
    while moment <= limit:
        times.append(moment.time())
        moment += timedelta(minutes=interval_min)
    return times


class TradingBot:
    """사이클 실행과 스케줄 관리를 묶은 애플리케이션 객체."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        env = settings.env

        self.auth = TokenManager(env, settings.paths["token"])
        self.api = KisApi(env, self.auth)
        self.notifier = Notifier(env)
        self.portfolio = Portfolio(settings, self.api, db_path=settings.paths["db"])
        self.risk = RiskManager(settings.risk, settings.schedule)
        self.executor = OrderExecutor(settings, self.api, self.portfolio, self.risk, self.notifier)
        self.agents: list[BaseAgent] = [ClaudeAgent(env, settings.ai), GeminiAgent(env, settings.ai)]

        self.universe: list[str] = list(settings.universe.watchlist)
        self.scheduler: BlockingScheduler | None = None
        self.consecutive_failures = 0

        self._cycle_lock = threading.Lock()
        self._shutting_down = False

    # -- 기동 -------------------------------------------------------------- #

    def startup(self) -> None:
        """토큰 확인 → 잔고 동기화 → 유니버스 구성 → 기동 알림."""
        env = self.settings.env
        logger.info("=" * 60)
        logger.info("모드: %s (%s) / DRY_RUN: %s", env.kis_env, env.base_url,
                    "on" if env.dry_run else "off")
        logger.info("AI: %s + %s / 알림: %s", env.claude_model, env.gemini_model, env.notifier)
        logger.info("장 상태: %s", market_state())

        self.auth.get_access_token()  # 토큰 캐시 확인(없으면 여기서 1회 발급)
        logger.info("접근토큰 확보 완료")

        try:
            state = self.portfolio.sync()
            logger.info("보유 %d종목 / 주문가능 %s원", state.position_count, f"{state.cash:,.0f}")
        except (KisApiError, KisAuthError) as exc:
            logger.error("기동 시 잔고 동기화 실패: %s", exc)
            raise

        self.refresh_universe()
        self.notifier.send_startup(len(self.universe))
        logger.info("=" * 60)

    # -- 잡 ---------------------------------------------------------------- #

    def refresh_universe(self) -> list[str]:
        if not is_trading_day():
            logger.info("휴장일 — 유니버스 갱신을 건너뜁니다")
            return self.universe
        try:
            self.universe = build_universe(self.api, self.settings, balance=None) or self.universe
        except (KisApiError, KisAuthError) as exc:
            logger.error("유니버스 갱신 실패(%s) — 기존 목록을 유지합니다", exc)
        return self.universe

    def run_cycle(self, label: str | None = None, *, holdings_only: bool = False) -> list[dict[str, Any]]:
        """한 사이클: 종목별 수집 → AI 합의 → 리스크 → 주문 → 기록."""
        if not is_trading_day():
            logger.info("휴장일 — 사이클을 건너뜁니다")
            return []
        if self._shutting_down:
            logger.info("종료 중 — 새 사이클을 시작하지 않습니다")
            return []

        with self._cycle_lock:
            now = datetime.now(KST)
            cycle_label = label or f"{now:%H:%M}"
            cycle_id = f"{now:%Y%m%d_%H%M%S}"
            logger.info("── 사이클 %s 시작 (cycle_id=%s) ──", cycle_label, cycle_id)

            try:
                results = self._run_cycle_body(cycle_id, cycle_label, now, holdings_only)
            except Exception as exc:  # 사이클 단위 예외
                self.consecutive_failures += 1
                logger.exception("사이클 실패 (%d/%d)", self.consecutive_failures, MAX_CONSECUTIVE_FAILURES)
                self.notifier.send_error(exc, context=f"{cycle_label} 사이클")
                if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self._fatal(f"사이클이 {MAX_CONSECUTIVE_FAILURES}회 연속 실패했습니다: {exc}")
                return []

            self.consecutive_failures = 0
            self.notifier.send_cycle_summary(cycle_label, results)
            logger.info("── 사이클 %s 완료: %d종목, 주문 %d건 ──", cycle_label, len(results),
                        sum(1 for row in results if row.get("ordered")))
            return results

    def _run_cycle_body(
        self, cycle_id: str, cycle_label: str, now: datetime, holdings_only: bool
    ) -> list[dict[str, Any]]:
        state = self.portfolio.sync(now=now)
        codes = list(state.positions) if holdings_only else self.universe
        if holdings_only and not codes:
            logger.info("보유 종목이 없어 청산 점검을 건너뜁니다")
            return []

        results: list[dict[str, Any]] = []
        for code in codes:
            if self._shutting_down:
                logger.info("종료 요청 — 남은 종목 처리를 중단합니다")
                break
            try:
                results.append(self._process_code(code, state, cycle_id, now))
            except Exception as exc:  # 종목 단위 예외 — 사이클은 계속된다
                logger.exception("%s 처리 실패", code)
                self.notifier.send_error(exc, context=f"{cycle_label} 사이클 / {code}")
                results.append({"code": code, "name": code, "error": str(exc)})
        return results

    def _process_code(self, code: str, state, cycle_id: str, now: datetime) -> dict[str, Any]:
        position = state.get(code)
        snapshot = collect(code, self.api, self.settings, holding=None, now=now)
        if position:  # 보유 정보는 잔고를 진실로 삼는다
            snapshot["position"] = {"holding": True, "qty": position.qty,
                                    "avg_price": position.avg_price, "pnl_pct": position.pnl_pct}

        forced = self.risk.check_forced_exit(position)
        decisions: dict[str, AgentDecision] = {}

        if forced == "STOP_LOSS":
            # 손절은 AI 판단을 건너뛴다.
            final = FinalDecision(action="SELL_ALL", reason="손절선 도달(강제 청산)", sell_ratio=1.0)
        else:
            decisions = run_agents_parallel(self.agents, snapshot, self.settings.ai)
            claude = decisions.get("claude") or AgentDecision.hold("claude", "호출 없음")
            gemini = decisions.get("gemini") or AgentDecision.hold("gemini", "호출 없음")
            final = decide(claude, gemini, state.holds(code), self.settings.risk, self.settings.ai,
                           take_profit=forced == "TAKE_PROFIT")

        risk_passed, risk_reason = True, ""
        if final.is_buy:
            amount = self.risk.buy_amount(final.weight_pct, state)
            verdict = self.risk.check_buy(code, amount, state, now=now)
            risk_passed, risk_reason = verdict.allowed, verdict.reason
            if not risk_passed:
                logger.info("%s 리스크 거부: %s", code, risk_reason)

        execution = None
        if risk_passed or final.is_sell:
            execution = self.executor.execute(final, snapshot, state, cycle_id=cycle_id)

        self.portfolio.record_decision(
            cycle_id=cycle_id, snapshot=snapshot, decisions=decisions, final=final,
            forced_exit=forced, risk_passed=risk_passed, risk_reason=risk_reason,
        )

        return {
            "code": code, "name": snapshot.get("name", code),
            "agents": " / ".join(d.summary() for d in decisions.values()),
            "final_action": final.action, "weight_pct": final.weight_pct,
            "risk_blocked": not risk_passed, "risk_reason": risk_reason,
            "ordered": bool(execution and execution.ordered),
            "side": execution.side if execution else "",
            "qty": execution.qty if execution else 0,
            "price": execution.price if execution else 0,
        }

    def eod_review(self) -> list[dict[str, Any]]:
        """장 마감 전 보유 종목만 재판단(신규 매수는 리스크 규칙 5가 이미 막는다)."""
        logger.info("장 마감 전 청산 점검")
        return self.run_cycle(label="EOD", holdings_only=True)

    def daily_report(self) -> dict[str, Any]:
        if not is_trading_day():
            logger.info("휴장일 — 일간 리포트를 건너뜁니다")
            return {}
        report = build_daily_report(self.settings.paths["db"])
        logger.info("일간 리포트: 손익 %+.2f%% / 매수 %d건 / 매도 %d건 / 보유 %d종목",
                    report["total_pnl_pct"], report["buy_count"],
                    report["sell_count"], report["position_count"])
        self.notifier.send_daily_report(report)
        return report

    # -- 종료 -------------------------------------------------------------- #

    def _fatal(self, message: str) -> None:
        logger.critical("치명적 오류: %s", message)
        self.notifier.send_fatal(message)
        self._shutting_down = True
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)

    def handle_signal(self, signum: int, frame: FrameType | None) -> None:
        name = signal.Signals(signum).name
        if self._shutting_down:
            logger.warning("%s 재수신 — 즉시 종료합니다", name)
            sys.exit(1)
        self._shutting_down = True
        logger.info("%s 수신 — 진행 중 사이클을 마치고 종료합니다", name)
        threading.Thread(target=self._graceful_shutdown, daemon=True).start()

    def _graceful_shutdown(self) -> None:
        with self._cycle_lock:  # 진행 중 사이클이 끝날 때까지 대기
            pass
        self.notifier.send("🛑 자동매매를 종료합니다 (진행 중 사이클 완료)")
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)

    # -- 스케줄 등록 -------------------------------------------------------- #

    def build_scheduler(self) -> BlockingScheduler:
        schedule = self.settings.schedule
        scheduler = BlockingScheduler(timezone=KST)
        weekdays = "mon-fri"  # 휴장일은 각 잡에서 다시 확인한다

        scheduler.add_job(
            self.refresh_universe, CronTrigger(
                day_of_week=weekdays, hour=schedule.universe_refresh.hour,
                minute=schedule.universe_refresh.minute, timezone=KST),
            id="universe_refresh", name="유니버스 갱신",
        )

        for moment in cycle_times(schedule.first_cycle, schedule.cycle_interval_min):
            scheduler.add_job(
                self.run_cycle,
                CronTrigger(day_of_week=weekdays, hour=moment.hour, minute=moment.minute, timezone=KST),
                id=f"cycle_{moment:%H%M}", name=f"{moment:%H:%M} 사이클",
                misfire_grace_time=300, coalesce=True, max_instances=1,
            )

        scheduler.add_job(
            self.eod_review, CronTrigger(
                day_of_week=weekdays, hour=schedule.eod_review.hour,
                minute=schedule.eod_review.minute, timezone=KST),
            id="eod_review", name="장 마감 전 청산 점검",
            misfire_grace_time=300, coalesce=True, max_instances=1,
        )

        scheduler.add_job(
            self.daily_report, CronTrigger(
                day_of_week=weekdays, hour=schedule.daily_report.hour,
                minute=schedule.daily_report.minute, timezone=KST),
            id="daily_report", name="일간 리포트",
        )

        self.scheduler = scheduler
        return scheduler

    def run_forever(self) -> int:
        scheduler = self.build_scheduler()
        for job in scheduler.get_jobs():
            logger.info("잡 등록: %-24s %s", job.name, job.trigger)

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        logger.info("스케줄러 시작 — Ctrl+C 로 안전 종료")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        logger.info("스케줄러 종료")
        return 0


def bootstrap(settings: Settings) -> Settings:
    """로깅 구성 + 비밀값 등록 + DB 스키마 생성."""
    env = settings.env
    register_secret(env.kis_app_key, env.kis_app_secret, env.anthropic_api_key,
                    env.gemini_api_key, env.telegram_bot_token, env.discord_webhook_url,
                    env.naver_client_secret)
    setup_logging(env.log_level, settings.paths["logs"])
    init_db(settings.paths["db"])
    return settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-Agent 주식 자동매매")
    parser.add_argument("--check", action="store_true", help="설정·DB 점검만 하고 종료")
    parser.add_argument("--once", action="store_true", help="지금 즉시 1사이클 실행 후 종료")
    parser.add_argument("--report", action="store_true", help="오늘 일간 리포트만 전송하고 종료")
    args = parser.parse_args(argv)

    try:
        settings = bootstrap(load())
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    if args.check:
        logger.info("설정 검증 완료 — 모드 %s / DRY_RUN %s", env.kis_env, "on" if env.dry_run else "off")
        logger.info("DB 테이블: %s", ", ".join(table_names(settings.paths["db"])))
        logger.info("사이클 시각: %s", ", ".join(
            f"{t:%H:%M}" for t in cycle_times(settings.schedule.first_cycle,
                                              settings.schedule.cycle_interval_min)))
        return 0

    if env.is_real:
        logger.warning("⚠ 실전(REAL) 모드입니다 — 실제 자금이 사용됩니다")
    if not env.dry_run:
        logger.warning("⚠ DRY_RUN=false — 실제 주문이 전송됩니다")

    bot = TradingBot(settings)
    try:
        if args.report:
            bot.daily_report()
            return 0
        bot.startup()
    except (KisApiError, KisAuthError) as exc:
        logger.error("기동 실패: %s", exc)
        bot.notifier.send_error(exc, context="기동")
        return 1

    if args.once:
        bot.run_cycle(label="수동")
        return 0

    return bot.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
