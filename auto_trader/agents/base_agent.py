"""에이전트 추상 클래스: 호출 → JSON 추출 → 검증 → (실패 시) 재요청 → HOLD 폴백."""

from __future__ import annotations

import json
import threading
import re
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


class AgentQuotaError(AgentCallError):
    """요청량 한도에 걸렸다(429). **다시 부르면 상황이 나빠지기만 한다.**

    예전에는 이걸 보통 실패와 똑같이 다뤘다. 그래서 한도에 걸리면 재요청을
    2번 더 하고, 그래도 실패하니 종목별 폴백으로 10종목 × 3회를 또 불렀다.
    한 사이클에 최대 33번. 하루 20회짜리 무료 한도는 두 번째 사이클에
    바닥나고, 그 뒤로는 매 사이클이 33번씩 헛수고를 반복했다.

    Args:
        retry_after: 제공사가 알려준 재시도 대기 시간(초). 모르면 0.
        daily:       일일 한도인가. 그렇다면 오늘은 더 부르지 않는다.
    """

    def __init__(self, message: str, *, retry_after: float = 0.0, daily: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.daily = daily


# 한도 메시지에서 짧은 한 줄만 남긴다. 제공사가 돌려주는 원문은 JSON 수십 줄이라,
# 그대로 알림에 실으면 종목 10개 × 20줄이 되어 정작 볼 것을 덮어 버린다.
_QUOTA_HINTS = ("quota", "rate limit", "rate_limit", "resource_exhausted",
                "too many requests", "429")


def looks_like_quota(message: str) -> bool:
    lowered = (message or "").lower()
    return any(hint in lowered for hint in _QUOTA_HINTS)


def quota_details(message: str) -> tuple[float, bool]:
    """(재시도 대기 초, 일일 한도인가). 읽어내지 못하면 (0, False)."""
    daily = bool(re.search(r"per\s*day|perday|daily", message or "", re.I))
    match = re.search(r"retry[ _]?(?:in|after|delay)['\"]?[:=\s]*['\"]?([0-9.]+)\s*s",
                      message or "", re.I)
    try:
        return (float(match.group(1)) if match else 0.0), daily
    except (TypeError, ValueError):
        return 0.0, daily


def short_error(message: str, limit: int = 110) -> str:
    """알림에 실을 한 줄. 줄바꿈을 없애고 길면 자른다."""
    text = " ".join((message or "").split())
    if looks_like_quota(text):
        wait, daily = quota_details(text)
        if daily:
            return "요청량 한도 초과(일일) — 오늘은 이 엔진을 건너뜁니다"
        if wait:
            return f"요청량 한도 초과 — {wait:.0f}초 뒤 재개"
        return "요청량 한도 초과"
    return text if len(text) <= limit else text[:limit - 1] + "…"


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
        # 한도에 걸린 엔진은 이 시각까지 아예 부르지 않는다. 일일 한도면
        # 자정(태평양시 기준으로 리셋되지만, 우리는 우리 날짜로 충분하다)까지.
        self._quota_until: float = 0.0
        self._quota_note: str = ""

    def _note_quota(self, exc: "AgentQuotaError") -> None:
        if exc.daily:
            # 남은 오늘 내내 건너뛴다. 정확한 리셋 시각을 몰라도, 다시 불러서
            # 얻을 것이 없다는 점은 같다.
            wait = 24 * 3600.0
            self._quota_note = "일일 한도 소진 — 오늘은 건너뜁니다"
        else:
            wait = max(exc.retry_after, 60.0)
            self._quota_note = f"요청량 한도 — {wait:.0f}초 쉽니다"
        self._quota_until = time.monotonic() + wait
        logger.error("[%s] %s", self.name, self._quota_note)

    def _quota_blocked(self) -> str:
        """지금 부르면 안 되는 상태면 그 이유를, 아니면 빈 문자열."""
        if self._quota_until and time.monotonic() < self._quota_until:
            return self._quota_note or "요청량 한도"
        self._quota_until = 0.0
        return ""

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
        blocked = self._quota_blocked()
        if blocked:   # 부르지 않는다. 부를수록 나빠지기만 한다.
            return AgentDecision.hold(self.name, blocked)
        total_usage = Usage()  # 재요청까지 포함한 누적 토큰

        # 첫 호출 + max_retries 회의 재요청
        for attempt in range(self.ai.max_retries + 1):
            user_prompt = build_user_prompt(payload, retry=attempt > 0)
            self._last_usage = Usage()
            try:
                raw = self._call_model(SYSTEM_PROMPT, user_prompt, RESPONSE_JSON_SCHEMA)
            except AgentQuotaError as exc:
                # 한도에 걸린 상태에서 다시 부르는 것은 한도만 더 축낸다.
                total_usage += self._last_usage
                self._note_quota(exc)
                last_error = str(exc)
                last_raw = ""
                break
            except AgentCallError as exc:
                total_usage += self._last_usage
                last_error = str(exc)
                last_raw = ""
                logger.warning("[%s] %s 호출 실패 (%d/%d): %s",
                               self.name, code, attempt + 1, self.ai.max_retries + 1, exc)
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
        blocked = self._quota_blocked()
        if blocked:
            # None 을 주면 호출자가 종목별 폴백을 돈다 — 그건 더 많이 부른다는 뜻이다.
            return {code: AgentDecision.hold(self.name, blocked) for code in codes}
        system = batch_system_prompt(self.ai.max_buy_picks)
        started = time.monotonic()
        problem = ""
        total_usage = Usage()

        for attempt in range(self.ai.max_retries + 1):
            user_prompt = build_batch_user_prompt(snapshots, problem=problem)
            self._last_usage = Usage()
            try:
                raw = self._call_model(system, user_prompt, BATCH_RESPONSE_JSON_SCHEMA)
            except AgentQuotaError as exc:
                self._note_quota(exc)
                total_usage += self._last_usage
                # None 이 아니라 '전원 관망' 을 돌려준다. None 은 호출자에게
                # 종목별 폴백을 돌리라는 뜻인데, 한도에 걸린 상태에서 그것만큼
                # 나쁜 선택이 없다 — 10종목 × 3회를 더 부른다.
                return {code: AgentDecision.hold(self.name, str(exc)) for code in codes}
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


def _fallback_per_code(agent: BaseAgent, snapshots: list[dict[str, Any]],
                       deadline: float) -> dict[str, AgentDecision]:
    """상대평가가 실패한 엔진만 예전 방식(종목별)으로 되돌린다.

    한 번의 응답이 깨졌다고 후보 전부를 관망으로 밀어버리면, 모델의 사소한
    형식 실수 하나가 그 사이클의 매수를 통째로 막는다. 비용은 더 들지만
    사이클을 살린다.

    **마감시각을 스스로 지킨다.** 밖에서 future 를 포기해도 이 스레드는 멈추지
    않는다(cancel 은 실행 중인 스레드를 못 막는다). 그대로 두면 아무도 안 쓸
    답을 받으려고 유료 API 를 계속 두드리고, 그 비용이 다음 사이클까지 겹친다.
    """
    results: dict[str, AgentDecision] = {}
    for snapshot in snapshots:
        code = str(snapshot.get("code", ""))
        if time.monotonic() >= deadline:
            logger.warning("[%s] 시간이 다 되어 %s 이후는 건너뜁니다", agent.name, code)
            results[code] = AgentDecision.hold(agent.name, "시간 초과로 건너뜀")
            continue
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

    # 폴백까지 감안한 마감시각. 종목별로 되돌면 호출이 종목 수만큼 늘어난다.
    budget = ai.batch_timeout_sec + ai.timeout_sec * len(snapshots)
    deadline = time.monotonic() + budget

    def work(agent: BaseAgent) -> dict[str, AgentDecision]:
        decisions = agent.analyze_many(snapshots)
        if decisions is None:                       # 상대평가 실패 → 종목별로
            return _fallback_per_code(agent, snapshots, deadline)
        return decisions

    executor = ThreadPoolExecutor(max_workers=max(len(agents), 1), thread_name_prefix="agent")
    try:
        futures = {executor.submit(work, agent): agent for agent in agents}
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
