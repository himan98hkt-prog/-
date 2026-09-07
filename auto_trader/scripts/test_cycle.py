#!/usr/bin/env python3
"""Step 5 검증 스크립트 — 한 종목 end-to-end (DRY_RUN 권장).

  잔고 동기화 → 스냅샷 수집 → 강제청산 검사 → AI 병렬 분석 → 합의 →
  리스크 검사 → 주문(DRY_RUN이면 미전송) → DB 기록 → 텔레그램 사이클 요약

사용법:
    python scripts/test_cycle.py                    # watchlist 첫 종목
    python scripts/test_cycle.py --code 005930 000660
    python scripts/test_cycle.py --no-ai            # AI 호출 없이 배관만 점검
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_agent import BaseAgent, run_agents_parallel  # noqa: E402
from agents.claude_agent import ClaudeAgent  # noqa: E402
from agents.gemini_agent import GeminiAgent  # noqa: E402
from agents.schemas import AgentDecision  # noqa: E402
from config.loader import ConfigError, load  # noqa: E402
from data_pipeline.market_data import collect  # noqa: E402
from logic.decision_maker import FinalDecision, decide  # noqa: E402
from logic.portfolio import Portfolio  # noqa: E402
from logic.risk_manager import RiskManager  # noqa: E402
from trading.kis_api import KisApi, KisApiError  # noqa: E402
from trading.kis_auth import KisAuthError, TokenManager  # noqa: E402
from trading.order_executor import OrderExecutor  # noqa: E402
from utils.logger import get_logger, register_secret, setup_logging  # noqa: E402
from utils.notifier import Notifier  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("test_cycle")


def main() -> int:
    parser = argparse.ArgumentParser(description="사이클 end-to-end 검증 (Step 5)")
    parser.add_argument("--code", nargs="*", help="대상 종목코드 (기본: watchlist 첫 종목)")
    parser.add_argument("--no-ai", action="store_true", help="AI 호출 없이 HOLD 로 진행")
    args = parser.parse_args()

    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    register_secret(env.kis_app_key, env.kis_app_secret, env.anthropic_api_key,
                    env.gemini_api_key, env.telegram_bot_token)
    setup_logging(env.log_level, settings.paths["logs"])

    now = datetime.now(KST)
    cycle_id = f"{now:%Y%m%d_%H%M%S}"
    logger.info("사이클 검증 시작 — %s / DRY_RUN %s / cycle_id=%s",
                env.kis_env, "on" if env.dry_run else "off", cycle_id)
    if not env.dry_run:
        logger.warning("⚠ DRY_RUN=false 입니다 — 실제 주문이 전송됩니다")

    auth = TokenManager(env, settings.paths["token"])
    api = KisApi(env, auth)
    notifier = Notifier(env)
    portfolio = Portfolio(settings, api)
    risk = RiskManager(settings.risk, settings.schedule)
    executor = OrderExecutor(settings, api, portfolio, risk, notifier)

    agents: list[BaseAgent] = []
    if not args.no_ai:
        agents = [ClaudeAgent(env, settings.ai), GeminiAgent(env, settings.ai)]

    try:
        state = portfolio.sync(now=now)
    except (KisApiError, KisAuthError) as exc:
        logger.error("잔고 동기화 실패: %s", exc)
        return 1

    codes = args.code or settings.universe.watchlist[:1]
    results: list[dict] = []

    for code in codes:
        try:
            position = state.get(code)
            snapshot = collect(code, api, settings, holding=None, now=now)
            if position:  # 보유 정보는 잔고 기준으로 덮어쓴다
                snapshot["position"] = {"holding": True, "qty": position.qty,
                                        "avg_price": position.avg_price, "pnl_pct": position.pnl_pct}

            forced = risk.check_forced_exit(position)
            if forced == "STOP_LOSS":
                logger.warning("%s 손절선 도달 — AI 판단 없이 전량 매도", code)
                final = FinalDecision(action="SELL_ALL", reason="손절선 도달(강제)", sell_ratio=1.0)
                decisions: dict[str, AgentDecision] = {}
            else:
                decisions = (run_agents_parallel(agents, snapshot, settings.ai) if agents else {})
                claude = decisions.get("claude") or AgentDecision.hold("claude", "AI 미사용")
                gemini = decisions.get("gemini") or AgentDecision.hold("gemini", "AI 미사용")
                final = decide(claude, gemini, state.holds(code), settings.risk, settings.ai,
                               take_profit=forced == "TAKE_PROFIT")

            logger.info("%s 최종 결정: %s (%s)", code, final.action, final.reason)

            risk_passed, risk_reason = True, ""
            if final.is_buy:
                amount = risk.buy_amount(final.weight_pct, state)
                verdict = risk.check_buy(code, amount, state, now=now)
                risk_passed, risk_reason = verdict.allowed, verdict.reason
                if not risk_passed:
                    logger.warning("%s 리스크 거부: %s", code, risk_reason)

            execution = (executor.execute(final, snapshot, state, cycle_id=cycle_id)
                         if (risk_passed or final.is_sell) else None)

            portfolio.record_decision(
                cycle_id=cycle_id, snapshot=snapshot, decisions=decisions, final=final,
                forced_exit=forced, risk_passed=risk_passed, risk_reason=risk_reason,
            )

            agent_summary = " / ".join(d.summary() for d in decisions.values())
            results.append({
                "code": code, "name": snapshot.get("name", code),
                "agents": agent_summary, "final_action": final.action,
                "weight_pct": final.weight_pct,
                "risk_blocked": not risk_passed, "risk_reason": risk_reason,
                "ordered": bool(execution and execution.ordered),
                "side": execution.side if execution else "",
                "qty": execution.qty if execution else 0,
                "price": execution.price if execution else 0,
            })
        except Exception as exc:  # 종목 하나가 실패해도 사이클은 계속된다
            logger.exception("%s 처리 실패", code)
            notifier.send_error(exc, context=f"{code} 사이클")
            results.append({"code": code, "name": code, "error": str(exc)})

    notifier.send_cycle_summary(f"{now:%H:%M}", results)
    logger.info("사이클 완료 — %d종목 처리, 주문 %d건",
                len(results), sum(1 for r in results if r.get("ordered")))
    logger.info("DB 확인: sqlite3 %s 'SELECT * FROM decisions ORDER BY id DESC LIMIT 3;'",
                settings.paths["db"])
    return 0 if not any(r.get("error") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
