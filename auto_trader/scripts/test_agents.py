#!/usr/bin/env python3
"""Step 4 검증 스크립트 — 실제 Claude/Gemini API로 스냅샷을 분석한다.

  1) `data/snapshots/` 의 최신 스냅샷을 읽거나(기본), `--collect` 로 새로 수집
  2) 두 에이전트를 병렬 호출해 AgentDecision 출력
  3) 파싱 성공 여부·소요 시간·원문 일부를 함께 표시

사용법:
    python scripts/test_agents.py                      # 최신 스냅샷 2건 분석
    python scripts/test_agents.py --collect 005930 000660   # KIS에서 새로 수집해 분석
    python scripts/test_agents.py --agent claude       # 한쪽만 호출
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_agent import BaseAgent, run_agents_parallel  # noqa: E402
from agents.claude_agent import ClaudeAgent  # noqa: E402
from agents.gemini_agent import GeminiAgent  # noqa: E402
from config.loader import ConfigError, Settings, load  # noqa: E402
from utils.logger import get_logger, register_secret, setup_logging  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("test_agents")


def load_recent_snapshots(snapshot_dir: Path, limit: int) -> list[dict]:
    """가장 최근에 저장된 스냅샷 JSON 을 종목당 1건씩 읽는다."""
    files = sorted(snapshot_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    snapshots: list[dict] = []
    seen: set[str] = set()
    for path in files:
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("스냅샷 읽기 실패 %s: %s", path.name, exc)
            continue
        code = snapshot.get("code")
        if not code or code in seen:
            continue
        seen.add(code)
        snapshots.append(snapshot)
        logger.info("스냅샷 로드: %s (%s)", path.name, snapshot.get("name"))
        if len(snapshots) >= limit:
            break
    return snapshots


def collect_snapshots(codes: list[str], settings: Settings) -> list[dict]:
    """KIS에서 새로 수집한다(Step 3 파이프라인 사용)."""
    from data_pipeline.market_data import collect
    from trading.kis_api import KisApi
    from trading.kis_auth import TokenManager

    auth = TokenManager(settings.env, settings.paths["token"])
    api = KisApi(settings.env, auth)
    balance = api.get_balance()
    now = datetime.now(KST)
    return [collect(code, api, settings, holding=balance.by_code(code), now=now) for code in codes]


def report(code: str, name: str, decisions: dict) -> bool:
    logger.info("")
    logger.info("─" * 60)
    logger.info("▶ %s (%s)", name, code)
    logger.info("─" * 60)
    all_ok = True
    for agent_name, decision in decisions.items():
        if decision.ok:
            logger.info(
                "  [%s] %s / confidence %.2f / weight %d%% / %.1fs",
                agent_name, decision.action, decision.confidence, decision.weight_pct, decision.elapsed_sec,
            )
            logger.info("      근거: %s", decision.reason)
            if decision.target_price or decision.stop_loss_price:
                logger.info("      목표가 %s / 손절가 %s",
                            f"{decision.target_price:,}" if decision.target_price else "-",
                            f"{decision.stop_loss_price:,}" if decision.stop_loss_price else "-")
        else:
            all_ok = False
            logger.error("  [%s] 실패 → HOLD: %s", agent_name, decision.error)
            if decision.raw:
                logger.error("      원문(앞 200자): %s", decision.raw[:200].replace("\n", " "))
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 에이전트 검증 (Step 4)")
    parser.add_argument("--collect", nargs="*", metavar="CODE",
                        help="KIS에서 해당 종목을 새로 수집해 분석 (예: --collect 005930 000660)")
    parser.add_argument("--limit", type=int, default=2, help="분석할 스냅샷 수 (기본 2)")
    parser.add_argument("--agent", choices=["claude", "gemini"], help="한쪽 에이전트만 호출")
    args = parser.parse_args()

    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}", file=sys.stderr)
        return 1

    env = settings.env
    register_secret(env.anthropic_api_key, env.gemini_api_key, env.kis_app_key, env.kis_app_secret)
    setup_logging(env.log_level, settings.paths["logs"])
    logger.info("AI 에이전트 검증 시작 — claude=%s / gemini=%s (timeout %ds, 재시도 %d회)",
                env.claude_model, env.gemini_model, settings.ai.timeout_sec, settings.ai.max_retries)

    if args.collect is not None:
        codes = args.collect or settings.universe.watchlist[: args.limit]
        logger.info("KIS에서 새로 수집: %s", ", ".join(codes))
        snapshots = collect_snapshots(codes, settings)
    else:
        snapshots = load_recent_snapshots(settings.paths["snapshots"], args.limit)
        if not snapshots:
            logger.error("스냅샷이 없습니다 — 먼저 `python scripts/test_pipeline.py` 를 실행하거나 "
                         "`--collect 005930` 로 새로 수집하세요")
            return 1

    agents: list[BaseAgent] = []
    if args.agent in (None, "claude"):
        agents.append(ClaudeAgent(env, settings.ai))
    if args.agent in (None, "gemini"):
        agents.append(GeminiAgent(env, settings.ai))

    failures = 0
    for snapshot in snapshots:
        decisions = run_agents_parallel(agents, snapshot, settings.ai)
        if not report(snapshot.get("code", "?"), snapshot.get("name", "?"), decisions):
            failures += 1

    logger.info("")
    logger.info("분석 %d종목 / 전원 파싱 성공 %d종목", len(snapshots), len(snapshots) - failures)
    if failures:
        logger.error("일부 에이전트가 응답 파싱에 실패했습니다 (HOLD 폴백은 정상 동작)")
        return 1
    logger.info("모든 에이전트 응답 파싱 성공 — Step 4 완료 조건 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
