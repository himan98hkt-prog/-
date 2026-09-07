"""에이전트 추상 클래스: 호출 → JSON 추출 → 검증 → (실패 시) 재요청 → HOLD 폴백."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from agents.prompts import build_user_prompt
from agents.schemas import AgentDecision, SchemaError, validate_payload
from config.loader import AiConfig
from utils.logger import get_logger

logger = get_logger("agent")


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

    def __init__(self, ai: AiConfig) -> None:
        self.ai = ai

    @abstractmethod
    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        """모델을 호출해 응답 텍스트를 반환. 실패 시 `AgentCallError`."""

    def analyze(self, payload: dict[str, Any]) -> AgentDecision:
        """스냅샷 → AgentDecision. 어떤 이유로든 실패하면 ok=False, HOLD."""
        from agents.prompts import SYSTEM_PROMPT

        started = time.monotonic()
        last_error = "알 수 없는 오류"
        last_raw = ""
        code = payload.get("code", "?")

        # 첫 호출 + max_retries 회의 재요청
        for attempt in range(self.ai.max_retries + 1):
            user_prompt = build_user_prompt(payload, retry=attempt > 0)
            try:
                raw = self._call_model(SYSTEM_PROMPT, user_prompt)
            except AgentCallError as exc:
                last_error = str(exc)
                last_raw = ""
                logger.warning("[%s] %s 호출 실패 (%d/%d): %s",
                               self.name, code, attempt + 1, self.ai.max_retries + 1, exc)
                continue

            last_raw = raw
            try:
                decision = validate_payload(extract_json(raw), self.name, raw)
            except SchemaError as exc:
                last_error = str(exc)
                logger.warning("[%s] %s 응답 파싱 실패 (%d/%d): %s",
                               self.name, code, attempt + 1, self.ai.max_retries + 1, exc)
                continue

            decision.elapsed_sec = round(time.monotonic() - started, 2)
            logger.info("[%s] %s → %s (confidence %.2f, %.1fs)",
                        self.name, code, decision.action, decision.confidence, decision.elapsed_sec)
            return decision

        logger.error("[%s] %s 최종 실패 → HOLD: %s", self.name, code, last_error)
        decision = AgentDecision.hold(self.name, last_error, last_raw)
        decision.elapsed_sec = round(time.monotonic() - started, 2)
        return decision


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
