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
import time
import threading
from datetime import datetime, time as dt_time, timedelta
from types import FrameType
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.base_agent import BaseAgent, run_agents_batch, run_agents_parallel
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
from trading.kis_api import KisApi, KisApiError, is_unreachable
from trading.kis_auth import KisAuthError, TokenManager
from trading.market_calendar import (calendar_health, is_market_open, is_trading_day,
                                     market_state, next_trading_day, upcoming_holidays)
from trading.order_executor import OrderExecutor
from utils.db import (get_bot_state, init_db, record_ai_usage, record_benchmark_price,
                      table_names, update_bot_state)
from utils.logger import get_logger, register_secret, setup_logging
from utils.notifier import Notifier
from utils.telegram_control import TelegramControl
from utils.runtime import (AlreadyRunningError, ProcessLock, StopFlag, pid_path,
                           shutdown_path, stop_flag_path)

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("main")

CYCLE_END = dt_time(15, 0)  # 마지막 정규 사이클 시각 상한
MAX_CONSECUTIVE_FAILURES = 3  # 사이클 전체가 이만큼 연속 실패하면 중단
SHUTDOWN_POLL_SEC = 1.0  # 종료 요청 파일을 확인하는 주기


def cycle_times(first: dt_time, interval_min: int, end: dt_time = CYCLE_END) -> list[dt_time]:
    """first 부터 interval 간격으로 end 까지의 사이클 시각 목록."""
    times: list[dt_time] = []
    moment = datetime(2000, 1, 1, first.hour, first.minute)
    limit = datetime(2000, 1, 1, end.hour, end.minute)
    while moment <= limit:
        times.append(moment.time())
        moment += timedelta(minutes=interval_min)
    return times



# 일시적 실패를 이만큼 연달아 겪어야 알린다. KIS 가 한 번 느린 것까지 휴대폰을
# 울리면, 정작 매매가 멈춘 날의 알림을 그 속에서 놓친다.
NOTIFY_AFTER_FAILURES = 3

def describe_outcome(final, execution) -> str:
    """판단이 주문까지 갔는지 한 줄로. 화면의 '비고' 에 그대로 실린다.

    이게 없으면 "세 AI 가 모두 매수라는데 왜 안 샀지?" 에 답이 없다. 판단과 주문
    사이에는 리스크 검사·수량 계산·DRY_RUN·거래소 거부가 있고, 그중 어디서
    멈췄는지는 기록해 두지 않으면 나중에 알 길이 없다.
    """
    if getattr(final, "action", "HOLD") == "HOLD":
        return ""
    if execution is None:
        return ""                       # 리스크 거부 — 비고에 사유가 따로 실린다
    # 이 함수는 화면에 적을 한 줄을 만들 뿐이다. 값이 하나 비었다고 여기서
    # 터지면 매매 자체가 멈춘다 — 표시용 코드가 주문 경로를 죽이면 안 된다.
    get = lambda name, default="": getattr(execution, name, default)  # noqa: E731
    if not get("ordered", False):
        return get("reason") or "주문하지 않았습니다"

    side = "매수" if get("side") == "BUY" else "매도"
    detail = f"{side} {get('qty', 0):,}주 @{get('price', 0):,.0f}원"
    if get("dry_run", False):
        return f"{detail} — 기록만 (DRY_RUN, 실제 주문 아님)"
    status = get("status")
    if status == "FILLED":
        return f"{detail} 체결"
    if status == "REJECTED":
        return f"{detail} 거부 — {get('error') or get('reason')}"
    return f"{detail} {status or '접수'}"

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
        self._flaky: dict[str, int] = {}   # 일시적 실패의 연속 횟수

        self._cycle_lock = threading.Lock()
        self._shutting_down = False

        self.lock = ProcessLock(pid_path(settings.paths["data"]))
        self.stop_flag = StopFlag(stop_flag_path(settings.paths["data"]))
        self._loss_limit_notified = False
        self.remote: TelegramControl | None = None
        # 기동 때 _announce_calendar() 가 채운다. 그 전에 읽혀도 터지지 않게 둔다.
        self._calendar: dict[str, Any] = {"state": "ok", "next": [], "message": ""}

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

        # 잔고를 못 읽어도 프로세스를 죽이지 않는다. 장이 닫힌 뒤 띄워두면
        # KIS 조회가 막히는 경우가 있는데, 여기서 죽으면 다음 날 09:05 사이클도
        # 함께 사라진다. 사이클은 매번 다시 동기화하고 실패하면 스스로 건너뛰므로,
        # 잔고를 모르는 채 주문이 나갈 일은 없다.
        try:
            state = self.portfolio.sync()
            logger.info("보유 %d종목 / 주문가능 %s원", state.position_count, f"{state.cash:,.0f}")
        except (KisApiError, KisAuthError) as exc:
            logger.error("기동 시 잔고 동기화 실패: %s", exc)
            logger.warning("잔고 없이 대기 상태로 기동합니다 — 다음 사이클에서 다시 시도합니다")
            self.notifier.send_error(exc, context="기동 시 잔고 조회")
            update_bot_state(self.settings.paths["db"], last_error=str(exc)[:500])

        self._announce_calendar()
        self.refresh_universe()
        update_bot_state(
            self.settings.paths["db"],
            status="RUNNING", pid=os.getpid(), kis_env=env.kis_env,
            dry_run=1 if env.dry_run else 0,
            started_at=datetime.now(KST).isoformat(timespec="seconds"),
            universe_size=len(self.universe), consecutive_failures=0, last_error="",
        )
        health = self._calendar
        self.notifier.send_startup(
            len(self.universe),
            holidays=[f"{d:%m/%d}({'월화수목금토일'[d.weekday()]})" for d in health.get("next", [])],
            calendar_warning=health.get("message", ""),
        )
        self._start_remote_control()
        logger.info("=" * 60)

    def _announce_calendar(self) -> None:
        """휴장일 달력 상태를 기동 로그에 남기고, 낡았으면 따로 알린다.

        이 파일이 비어 있으면 봇은 추석에도 평소처럼 돈다 — 전날 종가를 보고
        판단하고, 주문은 거래소에 거부당하고, 그 알림이 30분마다 온다. 코드는
        멀쩡하기 때문에 아무도 눈치채지 못한다. 그래서 기동할 때마다 확인한다.
        """
        self._calendar = calendar_health()
        state = self._calendar["state"]
        upcoming = self._calendar.get("next") or []

        if not is_trading_day():
            logger.info("오늘은 휴장일입니다 — 다음 거래일 %s", next_trading_day())
        if upcoming:
            logger.info("다가오는 휴장일: %s",
                        ", ".join(f"{d:%Y-%m-%d}" for d in upcoming))

        if state == "ok":
            logger.info("휴장일 달력: %s 까지 (%d일 남음)",
                        self._calendar["covered_until"], self._calendar["days_left"])
            return

        logger.warning("휴장일 달력 확인 필요: %s", self._calendar["message"])
        # 매매를 막지는 않는다. 달력이 없어도 주말은 걸러지고, 공휴일에 나간
        # 주문은 거래소가 거부할 뿐 손실로 이어지지 않는다. 다만 조용히 두지는
        # 않는다 — 거부 알림이 쌓이기 전에 사람이 먼저 알아야 한다.
        self.notifier.send_alert(
            "📅 휴장일 달력을 채워 주세요",
            [self._calendar["message"],
             "채우지 않으면 공휴일에도 사이클이 돌고, 주문이 거부되는 알림이 반복됩니다.",
             "KRX 공지(open.krx.co.kr)의 휴장일을 config/holidays.txt 에 적어 주세요."],
            key="holiday_calendar_stale",
        )

    # -- 폰에서 쓰는 리모컨 -------------------------------------------------- #

    def _start_remote_control(self) -> None:
        """텔레그램 명령 대기. 실패해도 매매는 그대로 돈다."""
        env = self.settings.env
        if env.notifier != "telegram" or not (env.telegram_bot_token and env.telegram_chat_id):
            return
        try:
            self.remote = TelegramControl(
                env.telegram_bot_token, env.telegram_chat_id,
                {
                    "/상태": self._cmd_status, "/status": self._cmd_status,
                    "/보유": self._cmd_positions, "/positions": self._cmd_positions,
                    "/오늘": self._cmd_today, "/today": self._cmd_today,
                    "/판단": self._cmd_decisions, "/decisions": self._cmd_decisions,
                    "/주문": self._cmd_orders, "/orders": self._cmd_orders,
                    "/왜": self._cmd_why, "/why": self._cmd_why,
                    "/정지": self._cmd_stop, "/stop": self._cmd_stop,
                    "/재개": self._cmd_resume, "/resume": self._cmd_resume,
                    "/도움말": self._cmd_help, "/help": self._cmd_help,
                    "/start": self._cmd_help,
                },
            )
            self.remote.start()
        except Exception:  # 리모컨이 안 떠도 매매가 멈출 이유는 없다
            logger.exception("텔레그램 원격 조종을 시작하지 못했습니다")

    def _cmd_help(self) -> str:
        from utils.telegram_control import HELP
        return HELP

    def _cmd_status(self) -> str:
        """대시보드 상단 타일을 그대로 폰으로 옮긴다.

        폰에서 가장 자주 묻는 것은 '지금 잘 돌고 있나' 하나다. 그 답이
        한 화면에 다 들어가야 하고, 무언가 이상하면 그 줄이 먼저 보여야 한다.
        """
        from dashboard.queries import overview

        env = self.settings.env
        head = "🟥 실전(REAL)" if env.is_real else "🟦 모의투자(VTS)"
        lines = [head + ("  ⚠️ 주문 미전송(DRY_RUN)" if env.dry_run else "")]

        if self.stop_flag.is_set():
            lines.append(f"🛑 정지됨 — {self.stop_flag.reason()}")
            lines.append("손절·익절은 계속 동작합니다. /재개 로 풀 수 있습니다.")
        elif not is_trading_day():
            lines.append(f"😴 휴장일 — 다음 거래일 {next_trading_day():%m/%d}")
        else:
            lines.append(f"✅ 가동 중 · 장 {market_state()}")

        try:
            data = overview(self.settings.paths["db"])
            sign = "🔴" if data["daily_pnl_pct"] > 0 else ("🔵" if data["daily_pnl_pct"] < 0 else "⚪")
            lines.append("")
            lines.append(f"{sign} 당일 {data['daily_pnl_pct']:+.2f}%  "
                         f"({data['unrealized_pnl']:+,.0f}원)")
            lines.append(f"평가자산 {data['end_equity']:,.0f}원")
            lines.append(f"보유 {data['position_count']}종목 · "
                         f"평가 {data['eval_amount']:,.0f}원")
            order_line = f"오늘 주문 매수 {data['buy_count']} · 매도 {data['sell_count']}"
            if data["rejected_orders"]:
                order_line += f" · ⚠️거부 {data['rejected_orders']}"
            lines.append(order_line)
            lines.append(f"AI {data['ai_calls']}건 / ${data['ai_cost_usd']:.2f}"
                         + (f" · ⚠️실패 {data['ai_failures']}" if data["ai_failures"] else ""))
        except Exception:
            logger.exception("상태 조회 실패")
            lines.append("(수치를 읽지 못했습니다 — 대시보드를 확인하세요)")

        try:
            lines.append(f"주문가능 현금 {self.portfolio.state.cash:,.0f}원")
        except Exception:
            pass

        next_at = self._next_run_at()
        lines.append("")
        lines.append(f"다음 사이클 {next_at[11:16] if len(next_at) > 15 else '미정'}")
        upcoming = upcoming_holidays(limit=2)
        if upcoming:
            lines.append("휴장 " + ", ".join(f"{d:%m/%d}" for d in upcoming))
        return "\n".join(lines)

    def _cmd_positions(self) -> str:
        """보유 종목 — 손절·익절까지 얼마나 남았는지까지 같이 본다.

        폰에서 수익률만 보면 '더 둬도 되나' 를 판단할 수 없다. 기계가 언제
        자동으로 파는지를 함께 보여야 손을 댈지 말지 결정할 수 있다.
        """
        from dashboard.queries import positions as position_rows

        risk = self.settings.risk
        try:
            rows = position_rows(self.settings.paths["db"], risk.stop_loss_pct,
                                 risk.take_profit_pct, risk)
        except Exception:
            logger.exception("보유 조회 실패")
            rows = []

        if not rows:
            return "보유 종목이 없습니다."

        lines = [f"보유 {len(rows)}종목"]
        for row in rows:
            mark = "🔴" if row["pnl_pct"] > 0 else ("🔵" if row["pnl_pct"] < 0 else "⚪")
            lines.append("")
            lines.append(f"{mark} {row['name']} {row['qty']:,}주  {row['pnl_pct']:+.2f}%")
            lines.append(f"   평단 {row['avg_price']:,.0f} → 현재 {row['current_price']:,.0f}")
            lines.append(f"   평가 {row['eval_amount']:,.0f}원 ({row['pnl_amount']:+,.0f})")
            guard = (f"   손절까지 {row['to_stop_loss']:.1f}%p · "
                     f"익절까지 {row['to_take_profit']:.1f}%p")
            if row.get("trailing_stop"):
                guard += f"\n   트레일링 {row['trailing_stop']:,.0f}원"
            lines.append(guard)
        return "\n".join(lines)

    def _cmd_today(self) -> str:
        from dashboard.queries import overview, recent_risk_blocks

        report = build_daily_report(self.settings.paths["db"])
        lines = [
            "오늘 매매",
            f"· 손익 {report['total_pnl_pct']:+.2f}%",
            f"· 매수 {report['buy_count']}건 / 매도 {report['sell_count']}건",
            f"· 보유 {report['position_count']}종목 / 판단 {report['decision_count']}건",
        ]
        try:
            data = overview(self.settings.paths["db"])
            if data["rejected_orders"]:
                lines.append(f"· ⚠️ 거래소가 거부한 주문 {data['rejected_orders']}건")
            if data["dry_run_orders"]:
                lines.append(f"· 모의 기록 {data['dry_run_orders']}건 (실제 주문 아님)")
            lines.append(f"· AI 비용 ${data['ai_cost_usd']:.2f}")
        except Exception:
            logger.exception("오늘 요약 보강 실패")

        try:
            blocks = recent_risk_blocks(self.settings.paths["db"], limit=3)
        except Exception:
            blocks = []
        if blocks:
            lines.append("")
            lines.append("리스크 규칙이 막은 것")
            for block in blocks:
                lines.append(f"· {block.get('name') or block.get('code')}: "
                             f"{block.get('risk_reason', '')}")
        return "\n".join(lines)

    def _cmd_decisions(self) -> str:
        """최근 AI 판단 — '왜 안 샀지' 에 대한 답.

        이번 프로그램에서 가장 자주 나온 질문이다. 대시보드를 못 볼 때
        폰에서 바로 확인할 수 있어야 한다.
        """
        from dashboard.queries import recent_decisions

        try:
            rows = recent_decisions(self.settings.paths["db"], limit=10)
        except Exception:
            logger.exception("판단 조회 실패")
            return "판단 기록을 읽지 못했습니다."
        if not rows:
            return "아직 판단 기록이 없습니다."

        lines = [f"최근 판단 ({rows[0]['created_at'][11:16]} 기준)"]
        for row in rows:
            name = row.get("name") or row.get("code")
            text = f"· {name}: {row.get('final_action', 'HOLD')}"
            if row.get("outcome"):
                text += f" → {row['outcome']}"
            elif row.get("risk_reason"):
                text += f" → 막힘({row['risk_reason']})"
            lines.append(text)
        lines.append("")
        lines.append("매수는 세 AI 가 모두 동의해야 나갑니다.")
        return "\n".join(lines)

    def _cmd_why(self) -> str:
        """왜 안 샀는지 — 관문별로 몇 건이 죽었는지.

        "답답할 정도로 진행하는 것이 없다" 는 물음에 추측으로 답하지 않기 위한
        명령이다. 기준이 높아서인지, 리스크 규칙 때문인지, 엔진이 고장나서인지
        고치는 방법이 전혀 다르다.
        """
        from dashboard.queries import buy_funnel

        try:
            data = buy_funnel(self.settings.paths["db"])
        except Exception:
            logger.exception("깔때기 조회 실패")
            return "판단 기록을 읽지 못했습니다."
        if not data.get("ready"):
            return "아직 판단 기록이 없습니다."

        lines = [f"매수 깔때기 (최근 {data['days']}일)"]
        for stage in data["stages"]:
            lines.append(f"· {stage['label']}: {stage['count']}건 ({stage['pct']}%)")
        lines.append("")
        lines.append(f"가장 많이 잃은 곳: {data['bottleneck']}")
        if data.get("near_miss"):
            lines.append(f"한 표 모자란 건: {data['near_miss']}건")
        if data.get("blockers"):
            lines.append("")
            lines.append("리스크 규칙이 막은 것")
            for blocker in data["blockers"]:
                lines.append(f"· {blocker['rule']} {blocker['count']}건")
        return "\n".join(lines)

    def _cmd_orders(self) -> str:
        """최근 주문 — 무엇이 나갔고, 거부됐다면 거래소가 뭐라고 했는지.

        폰밖에 볼 것이 없을 때 가장 먼저 확인하고 싶은 화면이다. 상태만
        적으면 '거부' 두 글자로 끝나서, 결국 PC 를 켜야 한다.
        """
        from dashboard.queries import recent_orders

        try:
            rows = recent_orders(self.settings.paths["db"], limit=8)
        except Exception:
            logger.exception("주문 조회 실패")
            return "주문 기록을 읽지 못했습니다."
        if not rows:
            return "주문 기록이 없습니다."

        label = {"FILLED": "✅ 체결", "REJECTED": "❌ 거부", "CANCELED": "취소",
                 "PENDING": "⏳ 미체결", "PARTIAL": "◐ 일부체결", "DRY_RUN": "📝 모의",
                 "SUBMITTING": "전송 중", "UNKNOWN": "확인 안 됨"}
        lines = ["최근 주문"]
        for row in rows:
            side = "매수" if row["side"] == "BUY" else "매도"
            state = "📝 모의" if row["dry_run"] else label.get(row["status"], row["status"])
            qty = row["filled_qty"] or row["qty"]
            price = row["filled_price"] or row["price"]
            lines.append("")
            lines.append(f"{row['created_at'][11:16]} {row['name'] or row['code']} "
                         f"{side} {qty:,}주 @{price:,.0f}")
            lines.append(f"   {state}")
            if row.get("error"):
                lines.append(f"   ⚠️ {row['error']}")
            elif row.get("reason"):
                lines.append(f"   {row['reason']}")
        return "\n".join(lines)

    def _cmd_stop(self) -> str:
        self.stop_flag.set("텔레그램에서 정지")
        update_bot_state(self.settings.paths["db"], status="STOPPED")
        return ("🛑 긴급 정지했습니다.\n"
                "진행 중인 사이클을 마친 뒤 새 사이클이 돌지 않습니다.\n"
                "손절·익절은 계속 동작합니다. 재개하려면 /재개")

    def _cmd_resume(self) -> str:
        if not self.stop_flag.is_set():
            return "이미 가동 중입니다."
        self.stop_flag.clear()
        return "▶️ 정지를 해제했습니다. 다음 사이클부터 재개됩니다."

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
            self._warn_if_we_were_asleep(now)
            cycle_label = label or f"{now:%H:%M}"
            cycle_id = f"{now:%Y%m%d_%H%M%S}"
            logger.info("── 사이클 %s 시작 (cycle_id=%s) ──", cycle_label, cycle_id)

            try:
                results = self._run_cycle_body(cycle_id, cycle_label, now, holdings_only)
            except Exception as exc:  # 사이클 단위 예외
                # 서버에 닿지도 못한 것은 '고장' 이 아니라 '지금은 안 된다' 다.
                # 이걸 연속 실패로 세면 네트워크가 90분 막혔을 때(사이클 3회)
                # 봇이 스스로 내려가고, 네트워크가 돌아와도 사람이 다시 켜야 한다.
                # 회사망·공용 와이파이를 오가는 노트북에서는 충분히 일어난다.
                offline = is_unreachable(exc)
                if not offline:
                    self.consecutive_failures += 1
                logger.exception("사이클 실패 (%s%d/%d)", "네트워크 · " if offline else "",
                                 self.consecutive_failures, MAX_CONSECUTIVE_FAILURES)
                if offline:
                    # 같은 내용을 30분마다 울리지 않게 한 키로 묶는다.
                    self.notifier.send_alert(
                        "🌐 KIS 서버에 닿지 않습니다",
                        [str(exc),
                         "매매를 멈추지는 않습니다 — 다음 사이클에 다시 시도합니다.",
                         "계속되면 인터넷 연결과 방화벽(포트 29443)을 확인하세요."],
                        key="kis_unreachable",
                    )
                else:
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

    def _warn_if_we_were_asleep(self, now: datetime) -> None:
        """지난 사이클 이후 시간이 너무 벌어졌으면 알린다.

        노트북 뚜껑을 닫거나 절전에 들어가면 스케줄러는 그냥 조용히 지나간다.
        깨어나면 아무 일도 없었던 것처럼 다음 사이클을 돌기 때문에, 그 사이
        무슨 일이 있었는지 아무도 모른다. **보유 종목이 있었다면 그동안
        손절 감시도 함께 멈춰 있었다** — 그건 반드시 알아야 한다.

        어제 마지막 사이클과 오늘 첫 사이클 사이는 원래 비어 있으므로,
        같은 날 안에서 벌어진 간격만 센다.
        """
        try:
            last_raw = (get_bot_state(self.settings.paths["db"]) or {}).get("last_cycle_at") or ""
            if not last_raw:
                return
            last = datetime.fromisoformat(last_raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=KST)
            last = last.astimezone(KST)
            if last.date() != now.date():
                return  # 밤 사이 간격은 정상이다

            gap_min = (now - last).total_seconds() / 60
            limit = self.settings.schedule.cycle_interval_min * 2 + 5
            if gap_min <= limit:
                return

            held = 0
            try:
                held = len(self.portfolio.state.positions)
            except Exception:
                pass

            logger.warning("지난 사이클(%s) 이후 %.0f분이 비었습니다 — 그동안 감시가 멈춰 있었습니다",
                           last.strftime("%H:%M"), gap_min)
            lines = [
                f"{last:%H:%M} 이후 {gap_min:.0f}분 동안 사이클이 돌지 않았습니다.",
                "절전·잠자기·네트워크 끊김 중 하나입니다.",
            ]
            if held:
                lines.append(f"⚠️ 그동안 {held}종목을 들고 있었고, 손절·트레일링 감시도 함께 멈춰 있었습니다.")
                lines.append("지금 바로 보유 종목의 손익을 확인하세요.")
            lines.append("장중에는 절전으로 들어가지 않게 설정해 두세요.")
            # 하루에 몇 번이고 반복될 수 있으므로 시각을 키에 넣어 각각 알린다.
            self.notifier.send_alert("😴 사이클이 비어 있었습니다", lines,
                                     key=f"missed_cycles:{last:%H%M}")
        except Exception:  # 이 점검이 사이클을 깨뜨리면 본말전도다
            logger.debug("빈 구간 점검 실패", exc_info=True)

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

        # 1단계 — 시세를 먼저 모두 모은다. AI 에게 후보를 **함께** 보여주려면
        # 개별 처리를 시작하기 전에 전부 손에 쥐고 있어야 한다.
        snapshots: dict[str, dict[str, Any]] = {}
        failed: dict[str, dict[str, Any]] = {}
        for code in codes:
            if self._shutting_down:
                logger.info("종료 요청 — 남은 종목 처리를 중단합니다")
                break
            try:
                snapshots[code] = self._collect_snapshot(code, state, now)
            except Exception as exc:  # 종목 단위 예외 — 사이클은 계속된다
                # 따로 알리지 않는다. 이 줄은 아래 사이클 요약에 '(오류) …' 로
                # 그대로 실린다 — 같은 내용을 두 번 울리면 알림이 소음이 된다.
                logger.exception("%s 시세 수집 실패", code)
                failed[code] = {"code": code, "name": code, "error": str(exc)}

        # 2단계 — 강제 청산 판정.
        forced = {code: self.risk.check_forced_exit(state.get(code)) for code in snapshots}
        exits = [c for c in codes if forced.get(c) in ("STOP_LOSS", "TRAILING_STOP")]

        # 3단계 — 손절·트레일링을 **AI 보다 먼저** 내보낸다.
        #
        # AI 판단을 건너뛰는 것만으로는 부족하다. 뒤에 두면 후보 전부를 보는
        # 호출(최악 13분)이 끝날 때까지 손절 주문이 대기한다. 그 사이 손절 감시
        # 잡도 사이클 락에 막혀 건너뛴다 — 떨어지는 종목을 붙잡고 있게 된다.
        # 자산을 지키는 주문은 무엇보다 먼저 나가야 한다.
        done: dict[str, dict[str, Any]] = {}
        for code in exits:
            done[code] = self._run_code(code, state, cycle_id, now, snapshots[code],
                                        forced[code], None)

        # 4단계 — 남은 후보를 한꺼번에 보여주고 서로 비교하게 한다(상대평가).
        if self._shutting_down:
            logger.info("종료 요청 — AI 판단을 건너뜁니다")
            votes_by_code: dict[str, dict[str, AgentDecision]] = {}
        else:
            votes_by_code = self._collect_votes(
                [snapshots[c] for c in snapshots if c not in done])

        # 5단계 — 나머지 종목의 리스크·주문·기록. 순서대로 돌아야 앞 종목의
        # 체결이 뒤 종목의 한도 계산에 반영된다.
        for code in codes:   # 결과 순서는 입력 순서 그대로 — 보유 종목이 먼저다
            if code in failed:
                results.append(failed[code])
                continue
            if code in done:
                results.append(done[code])
                continue
            if code not in snapshots:      # 종료 요청으로 수집이 중단된 뒤쪽
                continue
            if self._shutting_down:
                logger.info("종료 요청 — 남은 종목 처리를 중단합니다")
                break
            results.append(self._run_code(code, state, cycle_id, now, snapshots[code],
                                          forced[code], votes_by_code.get(code)))
        return results

    def _run_code(self, code, state, cycle_id, now, snapshot, forced, decisions) -> dict[str, Any]:
        """한 종목 처리. 여기서 터져도 사이클은 계속된다."""
        try:
            return self._process_code(code, state, cycle_id, now, snapshot=snapshot,
                                      forced=forced, decisions=decisions)
        except Exception as exc:  # 종목 단위 예외 — 사이클은 계속된다
            logger.exception("%s 처리 실패", code)   # 요약에 실리므로 따로 알리지 않는다
            return {"code": code, "name": snapshot.get("name", code), "error": str(exc)}

    def _collect_snapshot(self, code: str, state, now: datetime) -> dict[str, Any]:
        snapshot = collect(code, self.api, self.settings, holding=None, now=now)
        position = state.get(code)
        if position:  # 보유 정보는 잔고를 진실로 삼는다
            snapshot["position"] = {"holding": True, "qty": position.qty,
                                    "avg_price": position.avg_price, "pnl_pct": position.pnl_pct}

        # 벤치마크용 관측가. 이미 받아 온 값이라 추가 조회가 없다.
        record_benchmark_price(
            self.settings.paths["db"], date=now.strftime("%Y-%m-%d"), code=code,
            name=snapshot.get("name", code),
            price=float(snapshot.get("price", {}).get("current") or 0),
        )
        return snapshot

    def _collect_votes(self, snapshots: list[dict[str, Any]]
                       ) -> dict[str, dict[str, AgentDecision]]:
        """후보 전부를 한 번에 판단시킨다. 끄면 None 을 돌려 종목별로 묻게 한다.

        후보가 하나뿐이면 비교할 것이 없으므로 예전 방식이 그대로 낫다.
        """
        if not snapshots:
            return {}
        if not self.settings.ai.compare_candidates or len(snapshots) < 2:
            return {}
        return run_agents_batch(self.agents, snapshots, self.settings.ai)

    def _process_code(self, code: str, state, cycle_id: str, now: datetime, *,
                      snapshot: dict[str, Any] | None = None,
                      forced: str | None = None,
                      decisions: dict[str, AgentDecision] | None = None) -> dict[str, Any]:
        position = state.get(code)
        if snapshot is None:
            snapshot = self._collect_snapshot(code, state, now)
        if forced is None:
            forced = self.risk.check_forced_exit(position)
        decisions = dict(decisions or {})

        if forced in ("STOP_LOSS", "TRAILING_STOP"):
            # 손절·트레일링은 AI 판단을 건너뛴다. 되묻는 사이에 더 밀린다.
            decisions = {}
            reason = ("손절선 도달(강제 청산)" if forced == "STOP_LOSS"
                      else "고점 대비 하락(트레일링 청산)")
            final = FinalDecision(action="SELL_ALL", reason=reason, sell_ratio=1.0)
        else:
            if not decisions:   # 상대평가를 끈 경우·후보가 하나인 경우
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
        elif final.is_sell and forced is None:
            # AI 가 스스로 팔자고 한 경우에만 최소 보유기간을 본다.
            # 손절·트레일링(forced)은 이 자리에 오지 않는다.
            verdict = self.risk.check_sell(position, now=now)
            risk_passed, risk_reason = verdict.allowed, verdict.reason
            if not risk_passed:
                logger.info("%s 매도 보류: %s", code, risk_reason)

        execution = None
        # 매도도 이제 자체 검사(최소 보유기간)를 받는다. 예전처럼 `or final.is_sell`
        # 을 두면 거부된 매도가 그대로 나가 규칙이 있으나 마나가 된다.
        # 손절·트레일링은 애초에 거부되지 않으므로 여기서 막히지 않는다.
        if risk_passed:
            execution = self.executor.execute(final, snapshot, state, cycle_id=cycle_id)
            if execution.ordered:
                # 같은 사이클 뒤 종목들이 갱신된 현금·보유 수를 보게 한다.
                state.apply_execution(code, snapshot.get("name", code), execution.side,
                                      execution.qty, execution.price)

        outcome = describe_outcome(final, execution)
        self.portfolio.record_decision(
            cycle_id=cycle_id, snapshot=snapshot, decisions=decisions, final=final,
            forced_exit=forced, risk_passed=risk_passed, risk_reason=risk_reason,
            outcome=outcome,
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
            # 매수 판단이 주문까지 못 간 이유. 휴대폰에서도 "왜 안 샀지" 가 풀리게.
            "outcome": outcome,
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
            results = self._run_guard_body()
        except Exception as exc:  # 감시가 죽어도 정규 사이클은 계속 돈다
            logger.exception("손절 감시 실패")
            self._report_flaky(exc, context="손절 감시", key="guard")
            return []
        else:
            self._clear_flaky("guard", context="손절 감시")
            return results
        finally:
            self._cycle_lock.release()

    def _report_flaky(self, exc: BaseException, *, context: str, key: str) -> None:
        """일시적 실패. **연달아** 반복될 때만 휴대폰을 울린다.

        KIS 가 한 번 느린 것(Read timed out)과 계좌가 막힌 것은 전혀 다른 일이다.
        전자까지 알리면 알림이 소음이 되어, 정작 봐야 할 것을 놓친다. 로그에는
        언제나 남으므로 기록이 사라지지는 않는다 — 알림만 참는다.
        """
        self._flaky[key] = self._flaky.get(key, 0) + 1
        count = self._flaky[key]
        if count < NOTIFY_AFTER_FAILURES:
            logger.warning("%s 일시 실패 %d회 — %d회 연속이면 알립니다: %s",
                           context, count, NOTIFY_AFTER_FAILURES, exc)
            return
        self.notifier.send_error(exc, context=f"{context} — {count}회 연속 실패")

    def _clear_flaky(self, key: str, *, context: str = "") -> None:
        """성공했으면 연속 실패 수를 지운다 — 띄엄띄엄 나는 실패는 알림 대상이 아니다."""
        if self._flaky.pop(key, 0) >= NOTIFY_AFTER_FAILURES:
            logger.info("%s 정상으로 돌아왔습니다", context or key)
            self.notifier.send(f"✅ {context or key} 정상으로 돌아왔습니다")

    def _run_guard_body(self) -> list[dict[str, Any]]:
        now = datetime.now(KST)
        state = self.portfolio.sync(now=now)
        # 트레일링도 여기서 본다. 30분마다만 확인하면 고점에서 밀린 뒤에야
        # 알아차려 이익을 그만큼 돌려주게 된다.
        breached = [
            (position, exit_kind)
            for position, exit_kind in (
                (p, self.risk.check_forced_exit(p)) for p in state.positions.values()
            )
            if exit_kind in ("STOP_LOSS", "TRAILING_STOP")
        ]
        if not breached:
            return []

        cycle_id = f"{now:%Y%m%d_%H%M%S}_guard"
        results: list[dict[str, Any]] = []
        for position, exit_kind in breached:
            label = "손절" if exit_kind == "STOP_LOSS" else "트레일링"
            logger.warning("%s 감시 발동: %s(%s) %+.2f%%",
                           label, position.name, position.code, position.pnl_pct)
            final = FinalDecision(action="SELL_ALL",
                                  reason=f"{label} 감시 청산", sell_ratio=1.0)
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
                forced_exit=exit_kind, risk_passed=True, risk_reason="",
                outcome=describe_outcome(final, execution),
            )
            results.append({
                "code": position.code, "name": position.name,
                "final_action": final.action, "pnl_pct": position.pnl_pct,
                "outcome": describe_outcome(final, execution),
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
        # 마지막 사이클(15:10 청산 점검)이 낸 주문은 아직 PENDING 일 수 있다.
        # 그대로 집계하면 체결되지도 않은 매도가 '매도 1건' 으로 실리고, 장 마감
        # 뒤 소멸한 주문이 영영 미체결로 남는다. 리포트 전에 한 번 확정한다.
        try:
            for change in self.portfolio.reconcile_open_orders():
                logger.info("리포트 전 미체결 정리: %s %s %s → %s",
                            change["name"], change["side"], change["before"], change["after"])
        except Exception:  # 정리에 실패해도 리포트는 나가야 한다
            logger.exception("리포트 전 미체결 정리 실패 — 집계는 그대로 진행합니다")
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

    def _watch_shutdown_request(self) -> None:
        """종료 요청 파일을 지켜본다.

        Windows 에는 SIGTERM 이 없고, 콘솔 없이 띄운 프로세스에는 Ctrl+Break 도
        닿지 않는다(WinError 87). 대시보드의 '봇 종료' 가 신호 대신 파일을
        남기므로, 그걸 보고 신호를 받은 것과 똑같은 절차로 내려간다.
        """
        path = shutdown_path(self.settings.paths["data"])
        path.unlink(missing_ok=True)  # 지난번에 남은 요청으로 곧장 죽지 않게
        # 지우는 것만으로는 부족하다. 기동에 몇 초가 걸리는 사이 예전 요청 파일이
        # 남아 있으면, 방금 뜬 프로세스가 그걸 보고 곧장 내려간다. 이 시점보다
        # 오래된 파일은 우리 얘기가 아니다.
        started = time.time()

        def watch() -> None:
            while not self._shutting_down:
                if path.exists():
                    try:
                        stale = path.stat().st_mtime < started
                    except OSError:
                        stale = False
                    if stale:
                        logger.info("기동 전에 남아 있던 종료 요청을 무시합니다")
                        path.unlink(missing_ok=True)
                        time.sleep(SHUTDOWN_POLL_SEC)
                        continue
                    path.unlink(missing_ok=True)
                    logger.info("종료 요청을 받았습니다 — 진행 중 사이클을 마치고 종료합니다")
                    self._shutting_down = True
                    self._graceful_shutdown()
                    return
                time.sleep(SHUTDOWN_POLL_SEC)

        threading.Thread(target=watch, daemon=True, name="shutdown-watch").start()

    def handle_signal(self, signum: int, frame: FrameType | None) -> None:
        name = signal.Signals(signum).name
        if self._shutting_down:
            logger.warning("%s 재수신 — 즉시 종료합니다", name)
            sys.exit(1)
        self._shutting_down = True
        logger.info("%s 수신 — 진행 중 사이클을 마치고 종료합니다", name)
        threading.Thread(target=self._graceful_shutdown, daemon=True).start()

    def _graceful_shutdown(self) -> None:
        if getattr(self, "remote", None) is not None:
            self.remote.stop()
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

        self._watch_shutdown_request()
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        # Windows 는 SIGTERM 대신 Ctrl+Break 로 정상 종료를 요청받는다.
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self.handle_signal)  # type: ignore[attr-defined]

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
