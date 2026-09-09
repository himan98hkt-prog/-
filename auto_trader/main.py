"""진입점 — 스케줄러 등록 + 기동/종료 처리.

스케줄:
  universe_refresh  유니버스 갱신
  first_cycle 부터 cycle_interval_min 간격으로 15:00 까지  run_cycle()
  guard_cycle       손절 감시 — guard_interval_min 마다 보유 종목만 (AI 호출 없음)
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
import os
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
from agents.openai_agent import OpenAiAgent
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
from trading.market_calendar import is_market_open, is_trading_day, market_state
from trading.order_executor import OrderExecutor
from utils.db import init_db, record_ai_usage, table_names, update_bot_state
from utils.logger import get_logger, register_secret, setup_logging
from utils.notifier import Notifier
from utils.runtime import AlreadyRunningError, ProcessLock, StopFlag, pid_path, stop_flag_path

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
        init_db(settings.paths["db"])  # bot_state 갱신이 언제든 가능하도록 먼저 보장

        self.auth = TokenManager(env, settings.paths["token"])
        self.api = KisApi(env, self.auth)
        self.notifier = Notifier(env)
        self.portfolio = Portfolio(settings, self.api, db_path=settings.paths["db"])
        self.risk = RiskManager(settings.risk, settings.schedule)
        self.executor = OrderExecutor(settings, self.api, self.portfolio, self.risk, self.notifier)
        self.agents: list[BaseAgent] = [ClaudeAgent(env, settings.ai), GeminiAgent(env, settings.ai)]
        if env.chatgpt_enabled:  # OPENAI_API_KEY 가 있을 때만 세 번째로 합류한다
            self.agents.append(OpenAiAgent(env, settings.ai))

        self.universe: list[str] = list(settings.universe.watchlist)
        self.scheduler: BlockingScheduler | None = None
        self.consecutive_failures = 0

        self._cycle_lock = threading.Lock()
        self._shutting_down = False

        self.lock = ProcessLock(pid_path(settings.paths["data"]))
        self.stop_flag = StopFlag(stop_flag_path(settings.paths["data"]))
        self._loss_limit_notified = False

    # -- 기동 -------------------------------------------------------------- #

    def startup(self) -> None:
        """토큰 확인 → 잔고 동기화 → 유니버스 구성 → 기동 알림."""
        env = self.settings.env
        self.lock.acquire()  # 같은 계좌에 두 프로세스가 붙으면 이중 주문이 난다
        if self.stop_flag.is_set():
            logger.warning("긴급 정지 플래그가 설정돼 있습니다: %s", self.stop_flag.reason())
            logger.warning("해제하려면 %s 를 지우거나 대시보드에서 재개를 누르세요", self.stop_flag.path)

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
        update_bot_state(
            self.settings.paths["db"],
            status="RUNNING", pid=os.getpid(), kis_env=env.kis_env,
            dry_run=1 if env.dry_run else 0,
            started_at=datetime.now(KST).isoformat(timespec="seconds"),
            universe_size=len(self.universe), consecutive_failures=0, last_error="",
        )
        self.notifier.send_startup(len(self.universe))
        logger.info("=" * 60)

    # -- 잡 ---------------------------------------------------------------- #

    def refresh_universe(self) -> list[str]:
        if not is_trading_day():
            logger.info("휴장일 — 유니버스 갱신을 건너뜁니다")
            return self.universe
        try:
            balance = self.api.get_balance()  # 보유 종목을 유니버스에 포함시키기 위해 조회
        except (KisApiError, KisAuthError) as exc:
            logger.warning("잔고 조회 실패(%s) — 보유 종목 없이 유니버스를 구성합니다", exc)
            balance = None
        try:
            self.universe = build_universe(self.api, self.settings, balance=balance) or self.universe
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
        if self.stop_flag.is_set():
            logger.warning("긴급 정지 상태 — 사이클을 건너뜁니다 (%s)", self.stop_flag.reason())
            update_bot_state(self.settings.paths["db"], status="STOPPED")
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
                update_bot_state(self.settings.paths["db"], status="ERROR",
                                 consecutive_failures=self.consecutive_failures,
                                 last_error=str(exc)[:500])
                if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self._fatal(f"사이클이 {MAX_CONSECUTIVE_FAILURES}회 연속 실패했습니다: {exc}")
                return []

            self.consecutive_failures = 0
            update_bot_state(
                self.settings.paths["db"], status="RUNNING", consecutive_failures=0, last_error="",
                last_cycle_at=now.isoformat(timespec="seconds"), last_cycle_label=cycle_label,
                last_cycle_codes=len(results),
                last_cycle_orders=sum(1 for row in results if row.get("ordered")),
                next_cycle_at=self._next_run_at(),
            )
            self.notifier.send_cycle_summary(cycle_label, results)
            logger.info("── 사이클 %s 완료: %d종목, 주문 %d건 ──", cycle_label, len(results),
                        sum(1 for row in results if row.get("ordered")))
            return results

    def _run_cycle_body(
        self, cycle_id: str, cycle_label: str, now: datetime, holdings_only: bool
    ) -> list[dict[str, Any]]:
        # 지난 사이클에서 미체결로 남은 실주문부터 상태를 확정한다.
        for change in self.portfolio.reconcile_open_orders(now=now):
            logger.info("미체결 정리: %s %s %s → %s",
                        change["name"], change["side"], change["before"], change["after"])

        state = self.portfolio.sync(now=now)
        self._check_daily_loss_limit(state)
        # 보유 종목은 유니버스와 무관하게 항상, 그리고 먼저 본다(손절 판단이 늦으면 안 된다).
        held = list(state.positions)
        codes = held if holdings_only else held + [c for c in self.universe if c not in state.positions]
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
            # 호출조차 못 한 엔진도 '판단 없음' 으로 세어야 만장일치가 느슨해지지 않는다.
            votes = [
                decisions.get(agent.name) or AgentDecision.hold(agent.name, "호출 없음")
                for agent in self.agents
            ]
            final = decide(votes, state.holds(code), self.settings.risk, self.settings.ai,
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
            if execution.ordered:
                # 같은 사이클 뒤 종목들이 갱신된 현금·보유 수를 보게 한다.
                state.apply_execution(code, snapshot.get("name", code), execution.side,
                                      execution.qty, execution.price)

        self.portfolio.record_decision(
            cycle_id=cycle_id, snapshot=snapshot, decisions=decisions, final=final,
            forced_exit=forced, risk_passed=risk_passed, risk_reason=risk_reason,
        )
        for decision in decisions.values():
            record_ai_usage(
                self.settings.paths["db"], cycle_id=cycle_id, code=code,
                agent=decision.agent, model=decision.model,
                input_tokens=decision.input_tokens, output_tokens=decision.output_tokens,
                cost_usd=decision.cost_usd, ok=decision.ok, elapsed_sec=decision.elapsed_sec,
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

    def _check_daily_loss_limit(self, state) -> None:
        """당일 손실 한도에 처음 도달했을 때 한 번 알린다."""
        limit = self.settings.risk.daily_loss_limit_pct
        if state.daily_pnl_pct <= -limit:
            if not self._loss_limit_notified:
                self._loss_limit_notified = True
                logger.warning("당일 손실 한도 도달 (%.2f%%) — 신규 매수를 중단합니다", state.daily_pnl_pct)
                self.notifier.send_alert(
                    "🚨 당일 손실 한도 도달",
                    [f"당일 손익 {state.daily_pnl_pct:+.2f}% (한도 -{limit}%)",
                     "신규 매수를 중단합니다. 보유 종목의 손절·익절은 계속 동작합니다."],
                    key="daily_loss_limit",
                )
        elif self._loss_limit_notified and state.daily_pnl_pct > -limit:
            self._loss_limit_notified = False  # 회복되면 다음 도달 때 다시 알린다

    def _next_run_at(self) -> str:
        """스케줄러에 등록된 사이클 잡 중 가장 이른 다음 실행 시각.

        표시용 정보이므로 어떤 이유로든 실패해도 사이클을 깨뜨리지 않는다.
        """
        if self.scheduler is None:
            return ""
        try:
            upcoming = [
                job.next_run_time for job in self.scheduler.get_jobs()
                if job.id.startswith("cycle_") and job.next_run_time
            ]
        except Exception:  # 스케줄러 상태를 읽지 못해도 매매는 계속된다
            logger.debug("다음 실행 시각을 읽지 못했습니다", exc_info=True)
            return ""
        return min(upcoming).isoformat(timespec="seconds") if upcoming else ""

    def guard_cycle(self) -> list[dict[str, Any]]:
        """손절 감시 — 정규 사이클 사이의 급락을 잡는다.

        정규 사이클은 30분 간격이라, 그 사이에 손절선을 크게 밑돌아도 다음 사이클까지
        방치된다. 이 잡은 몇 분마다 돌면서 **보유 종목의 손절선만** 본다.
        AI 를 호출하지 않고 잔고 조회 1회로 끝나므로 비용이 사실상 없다.

        익절은 여기서 처리하지 않는다 — 지시서상 AI 재판단이 필요하고, 익절을
        놓쳐서 생기는 손해는 자산을 깎지 않기 때문이다.
        """
        if self._shutting_down or self.stop_flag.is_set() or not is_market_open():
            return []

        # 정규 사이클이 도는 중이면 건너뛴다. 잔고를 두 번 읽어 서로 다른 판단을
        # 하거나 같은 종목에 매도를 두 번 낼 이유가 없다.
        if not self._cycle_lock.acquire(blocking=False):
            logger.debug("정규 사이클 진행 중 — 손절 감시를 건너뜁니다")
            return []
        try:
            return self._run_guard_body()
        except Exception as exc:  # 감시가 죽어도 정규 사이클은 계속 돈다
            logger.exception("손절 감시 실패")
            self.notifier.send_error(exc, context="손절 감시")
            return []
        finally:
            self._cycle_lock.release()

    def _run_guard_body(self) -> list[dict[str, Any]]:
        now = datetime.now(KST)
        state = self.portfolio.sync(now=now)
        breached = [
            position for position in state.positions.values()
            if self.risk.check_forced_exit(position) == "STOP_LOSS"
        ]
        if not breached:
            return []

        cycle_id = f"{now:%Y%m%d_%H%M%S}_guard"
        results: list[dict[str, Any]] = []
        for position in breached:
            logger.warning("손절 감시 발동: %s(%s) %+.2f%%",
                           position.name, position.code, position.pnl_pct)
            final = FinalDecision(action="SELL_ALL", reason="손절선 도달(감시 청산)", sell_ratio=1.0)
            snapshot = {
                "code": position.code,
                "name": position.name,
                # 잔고의 현재가를 그대로 쓴다 — 시세를 다시 부르며 지체할 이유가 없다.
                "price": {"current": position.current_price},
            }
            execution = self.executor.execute(final, snapshot, state, cycle_id=cycle_id)
            if execution.ordered:
                state.apply_execution(position.code, position.name, execution.side,
                                      execution.qty, execution.price)
            self.portfolio.record_decision(
                cycle_id=cycle_id, snapshot=snapshot, decisions={}, final=final,
                forced_exit="STOP_LOSS", risk_passed=True, risk_reason="",
            )
            results.append({
                "code": position.code, "name": position.name,
                "final_action": final.action, "pnl_pct": position.pnl_pct,
                "ordered": bool(execution and execution.ordered),
                "side": execution.side if execution else "",
                "qty": execution.qty if execution else 0,
                "price": execution.price if execution else 0,
            })

        self.notifier.send_alert(
            "🛑 손절 감시 청산",
            [f"{row['name']}({row['code']}) {row['pnl_pct']:+.2f}% → "
             f"{'매도 ' + format(row['qty'], ',') + '주' if row['ordered'] else '주문 실패'}"
             for row in results],
        )
        return results

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
        update_bot_state(self.settings.paths["db"], status="FATAL", last_error=message[:500])
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
        update_bot_state(self.settings.paths["db"], status="STOPPED", next_cycle_at="")
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

        guard_min = self.settings.risk.guard_interval_min
        scheduler.add_job(
            self.guard_cycle,
            CronTrigger(day_of_week=weekdays, hour="9-15", minute=f"*/{guard_min}", timezone=KST),
            id="guard_cycle", name=f"손절 감시 ({guard_min}분)",
            # 밀린 감시를 몰아서 실행할 이유가 없다 — 가장 최근 것 하나만 돌린다.
            misfire_grace_time=60, coalesce=True, max_instances=1,
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
        update_bot_state(self.settings.paths["db"], status="STOPPED", next_cycle_at="")
        return 0


def bootstrap(settings: Settings) -> Settings:
    """로깅 구성 + 비밀값 등록 + DB 스키마 생성."""
    env = settings.env
    register_secret(env.kis_app_key, env.kis_app_secret, env.anthropic_api_key,
                    env.gemini_api_key, env.telegram_bot_token, env.discord_webhook_url)
    setup_logging(env.log_level, settings.paths["logs"])
    init_db(settings.paths["db"])
    return settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-Agent 주식 자동매매")
    parser.add_argument("--check", action="store_true", help="설정·DB 점검만 하고 종료")
    parser.add_argument("--once", action="store_true", help="지금 즉시 1사이클 실행 후 종료")
    parser.add_argument("--report", action="store_true", help="오늘 일간 리포트만 전송하고 종료")
    parser.add_argument("--stop", action="store_true", help="긴급 정지 플래그를 설정하고 종료")
    parser.add_argument("--resume", action="store_true", help="긴급 정지 플래그를 해제하고 종료")
    parser.add_argument("--status", action="store_true", help="현재 봇 상태를 출력하고 종료")
    args = parser.parse_args(argv)

    try:
        settings = bootstrap(load())
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env

    if args.stop:
        StopFlag(stop_flag_path(settings.paths["data"])).set("CLI 수동 정지")
        print("🛑 긴급 정지 플래그를 설정했습니다. 진행 중 사이클 이후 새 사이클이 실행되지 않습니다.")
        print("   재개: python main.py --resume")
        return 0

    if args.resume:
        StopFlag(stop_flag_path(settings.paths["data"])).clear()
        print("▶️  긴급 정지를 해제했습니다.")
        return 0

    if args.status:
        from utils.db import get_bot_state

        state = get_bot_state(settings.paths["db"])
        lock = ProcessLock(pid_path(settings.paths["data"]))
        flag = StopFlag(stop_flag_path(settings.paths["data"]))
        print(f"프로세스   : {'실행 중 (PID ' + str(lock.read_pid()) + ')' if lock.is_running() else '실행 안 함'}")
        print(f"긴급 정지  : {'설정됨 — ' + flag.reason() if flag.is_set() else '해제'}")
        print(f"상태       : {state.get('status') or '-'}")
        print(f"마지막 사이클: {state.get('last_cycle_at') or '-'} ({state.get('last_cycle_label') or '-'})")
        print(f"다음 사이클  : {state.get('next_cycle_at') or '-'}")
        if state.get("last_error"):
            print(f"마지막 오류 : {state['last_error']}")
        return 0

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
    except AlreadyRunningError as exc:
        # 두 프로세스가 같은 계좌에 붙으면 이중 주문이 난다 — 조용히 죽지 않고 이유를 알린다.
        print(f"\n🛑 {exc}\n", file=sys.stderr)
        logger.error("중복 실행 차단: %s", exc)
        return 1
    except (KisApiError, KisAuthError) as exc:
        logger.error("기동 실패: %s", exc)
        bot.notifier.send_error(exc, context="기동")
        bot.lock.release()
        return 1

    # 어느 경로로 끝나든 PID 락은 반드시 푼다(남으면 다음 기동이 막힌다).
    try:
        if args.once:
            bot.run_cycle(label="수동")
            return 0
        return bot.run_forever()
    finally:
        bot.lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
