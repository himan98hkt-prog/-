"""에이전트 추상 클래스: 호출 → JSON 추출 → 검증 → (실패 시) 재요청 → HOLD 폴백."""

from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from agents.prompts import (
    BATCH_RESPONSE_JSON_SCHEMA,
    RESPONSE_JSON_SCHEMA,
    batch_system_prompt,
    build_batch_user_prompt,
    build_user_prompt,
)
from agents.schemas import (
    AgentDecision,
    SchemaError,
    validate_batch_payload,
    validate_payload,
)
from agents.usage import Usage, estimate_cost
from config.loader import AiConfig
from utils.logger import get_logger

logger = get_logger("agent")

# 재요청 전 대기. 호출 실패의 상당수가 요청량 제한이라, 곧바로 다시 부르면
# 제한을 더 밀어붙이는 꼴이 된다. 사이클 하나가 통째로 늦어지지 않도록 짧게 둔다.
RETRY_DELAYS = (1.0, 3.0)


def _pause_before_retry(attempt: int) -> None:
    if attempt < len(RETRY_DELAYS):
        time.sleep(RETRY_DELAYS[attempt])



class AgentCallError(Exception):
    """모델 호출 자체가 실패(네트워크·인증·타임아웃)."""


def extract_json(text: str) -> Any:
    """응답에서 첫 '{' ~ 마지막 '}' 만 잘라 파싱한다.

    마크다운 코드블록이나 앞뒤 설명문이 섞여 있어도 본문 JSON을 건져낸다.
    """
    if not text:
        raise SchemaError("응답이 비어 있습니다")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise SchemaError("JSON 객체를 찾을 수 없습니다")
    fragment = text[start : end + 1]
    try:
        return json.loads(fragment)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"JSON 파싱 실패: {exc.msg}") from exc


class BaseAgent(ABC):
    """모든 판단 엔진의 공통 골격.

    구현체는 `_call_model()` 하나만 채우면 된다.
    """

    name: str = "base"
    model: str = ""

    def __init__(self, ai: AiConfig) -> None:
        self.ai = ai
        self.pricing: dict[str, tuple[float, float]] | None = None
        # 타임아웃된 호출의 스레드가 뒤늦게 값을 써도 다음 종목의 집계를 오염시키지
        # 않도록 스레드별로 분리해 둔다(future.cancel() 은 실행 중 스레드를 못 멈춘다).
        self._usage_store = threading.local()

    @property
    def _last_usage(self) -> Usage:
        return getattr(self._usage_store, "usage", Usage())

    @_last_usage.setter
    def _last_usage(self, value: Usage) -> None:
        self._usage_store.usage = value

    @abstractmethod
    def _call_model(self, system_prompt: str, user_prompt: str,
                    schema: dict[str, Any] | None = None) -> str:
        """모델을 호출해 응답 텍스트를 반환. 실패 시 `AgentCallError`.

        schema 는 구조화 출력에 강제할 JSON 스키마다(기본: 단일 종목 스키마).
        호출한 토큰은 `self._last_usage` 에 담아두면 결과에 함께 실린다.
        """

    def analyze(self, payload: dict[str, Any]) -> AgentDecision:
        """스냅샷 → AgentDecision. 어떤 이유로든 실패하면 ok=False, HOLD."""
        from agents.prompts import SYSTEM_PROMPT

        started = time.monotonic()
        last_error = "알 수 없는 오류"
        last_raw = ""
        code = payload.get("code", "?")
        total_usage = Usage()  # 재요청까지 포함한 누적 토큰

        # 첫 호출 + max_retries 회의 재요청
        for attempt in range(self.ai.max_retries + 1):
            user_prompt = build_user_prompt(payload, retry=attempt > 0)
            self._last_usage = Usage()
            try:
                raw = self._call_model(SYSTEM_PROMPT, user_prompt, RESPONSE_JSON_SCHEMA)
            except AgentCallError as exc:
                total_usage += self._last_usage
                last_error = str(exc)
                last_raw = ""
                logger.warning("[%s] %s 호출 실패 (%d/%d): %s",
                               self.name, code, attempt + 1, self.ai.max_retries + 1, exc)
                # 곧바로 다시 부르지 않는다. 호출 실패의 상당수는 요청량 제한(429)인데,
                # 즉시 재요청하면 제한을 더 밀어붙여 셋 다 실패하고 한도만 축낸다.
                _pause_before_retry(attempt)
                continue

            total_usage += self._last_usage
            last_raw = raw
            try:
                decision = validate_payload(extract_json(raw), self.name, raw)
            except SchemaError as exc:
                last_error = str(exc)
                logger.warning("[%s] %s 응답 파싱 실패 (%d/%d): %s",
                               self.name, code, attempt + 1, self.ai.max_retries + 1, exc)
                _pause_before_retry(attempt)
                continue

            decision.elapsed_sec = round(time.monotonic() - started, 2)
            self._attach_usage(decision, total_usage)
            logger.info("[%s] %s → %s (confidence %.2f, %.1fs, %d토큰)",
                        self.name, code, decision.action, decision.confidence,
                        decision.elapsed_sec, total_usage.total)
            return decision

        logger.error("[%s] %s 최종 실패 → HOLD: %s", self.name, code, last_error)
        decision = AgentDecision.hold(self.name, last_error, last_raw)
        decision.elapsed_sec = round(time.monotonic() - started, 2)
        self._attach_usage(decision, total_usage)
        return decision

    def analyze_many(self, snapshots: list[dict[str, Any]]) -> dict[str, AgentDecision] | None:
        """후보 전부를 **한 번에** 판단한다 (상대평가).

        종목을 하나씩 물으면 "이거 살 만한가" 라는 절대평가가 되어 답이 관망
        쪽으로 쏠린다. 후보를 함께 주면 "이 중 어디에" 라는 상대평가가 된다.

        Returns:
            종목코드 → AgentDecision. 끝내 실패하면 **None** — 호출자가 종목별
            호출로 되돌릴 수 있도록, "전원 관망" 과 구분되는 값을 돌려준다.
        """
        if not snapshots:
            return {}

        codes = [str(s.get("code", "")) for s in snapshots]
        system = batch_system_prompt(self.ai.max_buy_picks)
        started = time.monotonic()
        problem = ""
        total_usage = Usage()

        for attempt in range(self.ai.max_retries + 1):
            user_prompt = build_batch_user_prompt(snapshots, problem=problem)
            self._last_usage = Usage()
            try:
                raw = self._call_model(system, user_prompt, BATCH_RESPONSE_JSON_SCHEMA)
            except AgentCallError as exc:
                total_usage += self._last_usage
                problem = str(exc)
                logger.warning("[%s] 후보 %d종목 호출 실패 (%d/%d): %s", self.name,
                               len(codes), attempt + 1, self.ai.max_retries + 1, exc)
                _pause_before_retry(attempt)
                continue

            total_usage += self._last_usage
            try:
                decisions = validate_batch_payload(extract_json(raw), self.name, codes, raw)
            except SchemaError as exc:
                problem = str(exc)
                logger.warning("[%s] 후보 %d종목 응답 파싱 실패 (%d/%d): %s", self.name,
                               len(codes), attempt + 1, self.ai.max_retries + 1, exc)
                _pause_before_retry(attempt)
                continue

            elapsed = round(time.monotonic() - started, 2)
            for decision in decisions.values():
                decision.elapsed_sec = elapsed
            self._spread_usage(decisions, total_usage)
            buys = sum(1 for d in decisions.values() if d.action == "BUY")
            logger.info("[%s] 후보 %d종목 → 매수 제안 %d개 (%.1fs, %d토큰)",
                        self.name, len(decisions), buys, elapsed, total_usage.total)
            return decisions

        logger.error("[%s] 후보 %d종목 최종 실패 → 종목별 호출로 되돌립니다: %s",
                     self.name, len(codes), problem)
        return None

    def _spread_usage(self, decisions: dict[str, AgentDecision], usage: Usage) -> None:
        """한 번의 호출로 쓴 토큰을 종목들에 고르게 나눠 단다.

        비용 기록은 (사이클, 종목, 엔진)별이다. 호출은 하나인데 종목이 여럿이라
        그대로 달면 합계가 종목 수만큼 부풀고, 아무 데도 안 달면 그날 비용이
        통째로 사라진다. 나눠서 단다 — 합계는 실제 호출 비용과 같아진다.
        """
        count = max(len(decisions), 1)
        total_cost = estimate_cost(self.model, usage, self.pricing)
        items = list(decisions.values())
        for index, decision in enumerate(items):
            decision.model = self.model
            # 나머지는 첫 종목이 진다 — 나눗셈에서 흘리는 토큰이 없도록.
            extra = 1 if index == 0 else 0
            decision.input_tokens = usage.input_tokens // count + (
                usage.input_tokens % count if extra else 0)
            decision.output_tokens = usage.output_tokens // count + (
                usage.output_tokens % count if extra else 0)
            decision.cost_usd = round(total_cost / count, 8)

    def _attach_usage(self, decision: AgentDecision, usage: Usage) -> None:
        decision.model = self.model
        decision.input_tokens = usage.input_tokens
        decision.output_tokens = usage.output_tokens
        decision.cost_usd = estimate_cost(self.model, usage, self.pricing)


def run_agents_parallel(
    agents: list[BaseAgent],
    payload: dict[str, Any],
    ai: AiConfig,
) -> dict[str, AgentDecision]:
    """에이전트들을 병렬 호출하고 각각 `timeout_sec`을 적용한다.

    타임아웃·예외는 해당 에이전트만 HOLD로 처리하고 나머지는 살린다.
    """
    results: dict[str, AgentDecision] = {}
    # 타임아웃이 걸린 작업은 백그라운드에 남을 수 있으므로 executor 는 대기 없이 닫는다.
    executor = ThreadPoolExecutor(max_workers=max(len(agents), 1), thread_name_prefix="agent")
    try:
        futures = {executor.submit(agent.analyze, payload): agent for agent in agents}
        # 병렬 실행이므로 시작 시점 기준 공통 마감시각 = 각자에게 timeout_sec 을 준 것과 같다.
        deadline = time.monotonic() + ai.timeout_sec
        for future, agent in futures.items():
            try:
                results[agent.name] = future.result(timeout=max(deadline - time.monotonic(), 0))
            except FuturesTimeout:
                future.cancel()
                logger.error("[%s] %s 타임아웃(%ds) → HOLD",
                             agent.name, payload.get("code", "?"), ai.timeout_sec)
                results[agent.name] = AgentDecision.hold(agent.name, f"타임아웃 {ai.timeout_sec}초")
            except Exception as exc:  # 에이전트 하나가 죽어도 사이클은 계속된다
                logger.exception("[%s] %s 예기치 못한 오류 → HOLD", agent.name, payload.get("code", "?"))
                results[agent.name] = AgentDecision.hold(agent.name, f"{type(exc).__name__}: {exc}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return results


def _fallback_per_code(agent: BaseAgent, snapshots: list[dict[str, Any]]
                       ) -> dict[str, AgentDecision]:
    """상대평가가 실패한 엔진만 예전 방식(종목별)으로 되돌린다.

    한 번의 응답이 깨졌다고 후보 전부를 관망으로 밀어버리면, 모델의 사소한
    형식 실수 하나가 그 사이클의 매수를 통째로 막는다. 비용은 더 들지만
    사이클을 살린다.
    """
    results: dict[str, AgentDecision] = {}
    for snapshot in snapshots:
        code = str(snapshot.get("code", ""))
        try:
            results[code] = agent.analyze(snapshot)
        except Exception as exc:  # noqa: BLE001 — 한 종목이 죽어도 나머지는 살린다
            logger.exception("[%s] %s 종목별 폴백 실패", agent.name, code)
            results[code] = AgentDecision.hold(agent.name, f"{type(exc).__name__}: {exc}")
    return results


def run_agents_batch(
    agents: list[BaseAgent],
    snapshots: list[dict[str, Any]],
    ai: AiConfig,
) -> dict[str, dict[str, AgentDecision]]:
    """후보 전부를 엔진별로 한 번씩 판단시킨다 (상대평가).

    Returns:
        종목코드 → {엔진이름: AgentDecision}. 어떤 이유로든 판단이 없는 칸은
        ok=False 인 HOLD 로 채운다 — 합의가 느슨해지지 않게.
    """
    codes = [str(s.get("code", "")) for s in snapshots]
    per_agent: dict[str, dict[str, AgentDecision]] = {}
    if not snapshots:
        return {}

    def work(agent: BaseAgent) -> dict[str, AgentDecision]:
        decisions = agent.analyze_many(snapshots)
        if decisions is None:                       # 상대평가 실패 → 종목별로
            return _fallback_per_code(agent, snapshots)
        return decisions

    executor = ThreadPoolExecutor(max_workers=max(len(agents), 1), thread_name_prefix="agent")
    try:
        futures = {executor.submit(work, agent): agent for agent in agents}
        # 폴백까지 감안한 마감시각. 종목별로 되돌면 호출이 종목 수만큼 늘어난다.
        budget = ai.batch_timeout_sec + ai.timeout_sec * len(snapshots)
        deadline = time.monotonic() + budget
        for future, agent in futures.items():
            try:
                per_agent[agent.name] = future.result(
                    timeout=max(deadline - time.monotonic(), 0))
            except FuturesTimeout:
                future.cancel()
                logger.error("[%s] 후보 판단 타임아웃(%ds) → 전원 HOLD", agent.name, budget)
                per_agent[agent.name] = {}
            except Exception as exc:  # 엔진 하나가 죽어도 사이클은 계속된다
                logger.exception("[%s] 후보 판단 중 예기치 못한 오류 → 전원 HOLD", agent.name)
                per_agent[agent.name] = {
                    code: AgentDecision.hold(agent.name, f"{type(exc).__name__}: {exc}")
                    for code in codes
                }
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return {
        code: {
            agent.name: per_agent.get(agent.name, {}).get(code)
            or AgentDecision.hold(agent.name, "판단 없음")
            for agent in agents
        }
        for code in codes
    }
