"""AI 에이전트 테스트 — 파싱 실패 시 항상 HOLD 로 떨어지는지가 핵심.

외부 API는 전부 mock한다.
"""

from __future__ import annotations

import json
import time

import pytest

from agents.base_agent import AgentCallError, BaseAgent, extract_json, run_agents_parallel
from agents.prompts import RESPONSE_JSON_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from agents.schemas import AgentDecision, SchemaError, validate_payload
from config.loader import AiConfig

AI = AiConfig(timeout_sec=5, max_retries=2, min_confidence=0.6,
              news_max_items=5, news_lookback_hours=24)

VALID_JSON = {
    "action": "BUY", "confidence": 0.8, "weight_pct": 15,
    "reason": "20일선 돌파와 거래량 증가", "target_price": 78000, "stop_loss_price": 71000,
}

SNAPSHOT = {
    "code": "005930", "name": "삼성전자", "timestamp": "2026-09-07T09:35:00+09:00",
    "price": {"current": 76000, "change_pct": 1.5, "open": 75000, "high": 76500,
              "low": 74800, "volume": 3000, "volume_ratio_20d": 3.0},
    "valuation": {"market_cap": 425_600_000_000_000, "per": 13.5, "pbr": 1.2},
    "indicators": {"ma5": 75700, "ma20": 74950, "ma60": 72950, "rsi14": 68.2,
                   "macd": 686.7, "macd_signal": 680.5, "macd_hist": 6.2,
                   "bb_upper": 76103, "bb_lower": 73797},
    "orderbook": {"bid_total": 100, "ask_total": 50, "spread_pct": 0.14},
    "recent_closes_20d": [74000 + i * 100 for i in range(20)],
    "position": {"holding": False, "qty": 0, "avg_price": 0, "pnl_pct": 0},
    "news": [],
}


class ScriptedAgent(BaseAgent):
    """미리 정한 응답(또는 예외)을 순서대로 돌려주는 에이전트."""

    name = "scripted"

    def __init__(self, responses, ai=AI, name="scripted", delay: float = 0.0):
        super().__init__(ai)
        self.responses = list(responses)
        self.name = name
        self.delay = delay
        self.prompts: list[str] = []

    def _call_model(self, system_prompt: str, user_prompt: str, schema=None) -> str:
        self.prompts.append(user_prompt)
        if self.delay:
            time.sleep(self.delay)
        response = self.responses.pop(0) if self.responses else AgentCallError("응답 소진")
        if isinstance(response, Exception):
            raise response
        return response


# --------------------------------------------------------------------------- #
# JSON 추출 — 지시서 5-7 파싱 규칙
# --------------------------------------------------------------------------- #


def test_extract_json_from_plain_object():
    assert extract_json(json.dumps(VALID_JSON))["action"] == "BUY"


def test_extract_json_from_markdown_code_block():
    raw = f"```json\n{json.dumps(VALID_JSON, ensure_ascii=False)}\n```"
    assert extract_json(raw)["confidence"] == 0.8


def test_extract_json_with_surrounding_prose():
    raw = (
        "분석 결과를 알려드리겠습니다.\n\n"
        f"{json.dumps(VALID_JSON, ensure_ascii=False)}\n\n"
        "추가로 유의할 점은 없습니다."
    )
    assert extract_json(raw)["weight_pct"] == 15


@pytest.mark.parametrize("raw", ["", "   ", "JSON을 드릴 수 없습니다", "{ 깨진 json", "}{"])
def test_extract_json_failures_raise(raw):
    with pytest.raises(SchemaError):
        extract_json(raw)


# --------------------------------------------------------------------------- #
# 스키마 검증
# --------------------------------------------------------------------------- #


def test_validate_payload_success():
    decision = validate_payload(VALID_JSON, "claude", raw="원문")
    assert decision.ok and decision.action == "BUY"
    assert decision.confidence == 0.8 and decision.weight_pct == 15
    assert decision.target_price == 78000 and decision.stop_loss_price == 71000


def test_validate_payload_normalizes_case_and_whitespace():
    decision = validate_payload({**VALID_JSON, "action": " buy "}, "claude")
    assert decision.action == "BUY"


@pytest.mark.parametrize("action", ["MAYBE", "", None, "매수", 3])
def test_invalid_action_rejected(action):
    with pytest.raises(SchemaError):
        validate_payload({**VALID_JSON, "action": action}, "claude")


def test_out_of_range_values_are_clamped():
    decision = validate_payload({**VALID_JSON, "confidence": 1.7, "weight_pct": 250}, "claude")
    assert decision.confidence == 1.0 and decision.weight_pct == 100

    decision = validate_payload({**VALID_JSON, "confidence": -0.5, "weight_pct": -20}, "claude")
    assert decision.confidence == 0.0 and decision.weight_pct == 0


def test_zero_prices_become_none():
    decision = validate_payload({**VALID_JSON, "target_price": 0, "stop_loss_price": None}, "claude")
    assert decision.target_price is None and decision.stop_loss_price is None


def test_empty_reason_rejected():
    with pytest.raises(SchemaError):
        validate_payload({**VALID_JSON, "reason": "   "}, "claude")


def test_long_reason_truncated_to_200_chars():
    decision = validate_payload({**VALID_JSON, "reason": "가" * 500}, "claude")
    assert len(decision.reason) == 200


def test_non_dict_payload_rejected():
    with pytest.raises(SchemaError):
        validate_payload([VALID_JSON], "claude")


def test_non_numeric_confidence_rejected():
    with pytest.raises(SchemaError):
        validate_payload({**VALID_JSON, "confidence": "높음"}, "claude")


# --------------------------------------------------------------------------- #
# analyze() — 재요청과 HOLD 폴백
# --------------------------------------------------------------------------- #


def test_analyze_succeeds_on_first_try():
    agent = ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)])
    decision = agent.analyze(SNAPSHOT)
    assert decision.ok and decision.action == "BUY"
    assert len(agent.prompts) == 1
    assert decision.elapsed_sec >= 0


def test_markdown_response_is_parsed_without_retry():
    agent = ScriptedAgent([f"```json\n{json.dumps(VALID_JSON, ensure_ascii=False)}\n```"])
    decision = agent.analyze(SNAPSHOT)
    assert decision.ok and len(agent.prompts) == 1


def test_retry_on_unparseable_then_success():
    agent = ScriptedAgent(["죄송합니다, JSON을 드릴 수 없습니다.", json.dumps(VALID_JSON, ensure_ascii=False)])
    decision = agent.analyze(SNAPSHOT)

    assert decision.ok and decision.action == "BUY"
    assert len(agent.prompts) == 2
    assert "[재요청]" in agent.prompts[1], "재요청 프롬프트에 JSON 강조가 들어가야 합니다"
    assert "[재요청]" not in agent.prompts[0]


def test_all_retries_fail_returns_hold():
    agent = ScriptedAgent(["설명문뿐", "여전히 설명문", "끝까지 설명문"])
    decision = agent.analyze(SNAPSHOT)

    assert decision.ok is False
    assert decision.action == "HOLD"
    assert decision.confidence == 0.0
    assert decision.weight_pct == 0
    assert len(agent.prompts) == AI.max_retries + 1
    assert decision.raw  # 원문은 사후 검증용으로 남긴다


def test_call_error_falls_back_to_hold():
    agent = ScriptedAgent([AgentCallError("타임아웃"), AgentCallError("타임아웃"), AgentCallError("타임아웃")])
    decision = agent.analyze(SNAPSHOT)
    assert decision.action == "HOLD" and decision.ok is False
    assert "타임아웃" in decision.error


def test_invalid_schema_value_triggers_retry():
    bad = json.dumps({**VALID_JSON, "action": "STRONG_BUY"}, ensure_ascii=False)
    agent = ScriptedAgent([bad, json.dumps(VALID_JSON, ensure_ascii=False)])
    decision = agent.analyze(SNAPSHOT)
    assert decision.ok and len(agent.prompts) == 2


# --------------------------------------------------------------------------- #
# 병렬 실행
# --------------------------------------------------------------------------- #


def test_run_agents_parallel_collects_both():
    claude = ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)], name="claude")
    gemini = ScriptedAgent([json.dumps({**VALID_JSON, "action": "HOLD"}, ensure_ascii=False)], name="gemini")

    results = run_agents_parallel([claude, gemini], SNAPSHOT, AI)
    assert set(results) == {"claude", "gemini"}
    assert results["claude"].action == "BUY"
    assert results["gemini"].action == "HOLD"


def test_timeout_yields_hold_for_that_agent_only():
    fast = ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)], name="claude")
    slow = ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)], name="gemini", delay=1.5)
    ai = AiConfig(timeout_sec=1, max_retries=0, min_confidence=0.6,
                  news_max_items=5, news_lookback_hours=24)

    started = time.monotonic()
    results = run_agents_parallel([fast, slow], SNAPSHOT, ai)
    elapsed = time.monotonic() - started

    assert results["claude"].ok is True
    assert results["gemini"].ok is False
    assert results["gemini"].action == "HOLD"
    assert "타임아웃" in results["gemini"].error
    assert elapsed < 3, "타임아웃이 병렬로 적용되어야 합니다"


def test_unexpected_exception_becomes_hold():
    class Exploding(BaseAgent):
        name = "gemini"

        def _call_model(self, system_prompt, user_prompt, schema=None):
            raise RuntimeError("예기치 못한 오류")

    results = run_agents_parallel([Exploding(AI)], SNAPSHOT, AI)
    assert results["gemini"].action == "HOLD" and results["gemini"].ok is False


def test_agents_run_concurrently_not_sequentially():
    agents = [
        ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)], name="claude", delay=0.4),
        ScriptedAgent([json.dumps(VALID_JSON, ensure_ascii=False)], name="gemini", delay=0.4),
    ]
    started = time.monotonic()
    results = run_agents_parallel(agents, SNAPSHOT, AI)
    elapsed = time.monotonic() - started

    assert all(decision.ok for decision in results.values())
    assert elapsed < 0.75, f"병렬이면 0.4초 남짓이어야 합니다 (실측 {elapsed:.2f}s)"


# --------------------------------------------------------------------------- #
# 프롬프트
# --------------------------------------------------------------------------- #


def test_user_prompt_embeds_snapshot_json():
    prompt = build_user_prompt(SNAPSHOT)
    assert '"code": "005930"' in prompt
    assert '"rsi14": 68.2' in prompt


def test_system_prompt_forbids_markdown():
    assert "마크다운 코드블록" in SYSTEM_PROMPT
    assert "JSON 객체 **하나만**" in SYSTEM_PROMPT


def test_response_schema_matches_required_fields():
    assert RESPONSE_JSON_SCHEMA["required"] == [
        "action", "confidence", "weight_pct", "reason", "target_price", "stop_loss_price"
    ]
    assert RESPONSE_JSON_SCHEMA["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]
    assert RESPONSE_JSON_SCHEMA["additionalProperties"] is False


def test_hold_helper_is_safe_default():
    decision = AgentDecision.hold("claude", "타임아웃")
    assert (decision.action, decision.confidence, decision.weight_pct, decision.ok) == ("HOLD", 0.0, 0, False)
    assert "claude 실패" in decision.summary()


# --- Gemini 스키마 변환 ------------------------------------------------------ #

def test_gemini_schema_drops_keys_gemini_does_not_know():
    """additionalProperties 가 섞이면 요청 전체가 400 으로 거절된다."""
    from agents.gemini_agent import to_gemini_schema
    from agents.prompts import RESPONSE_JSON_SCHEMA

    converted = to_gemini_schema(RESPONSE_JSON_SCHEMA)

    def walk(node):
        if isinstance(node, dict):
            assert "additionalProperties" not in node, f"남아 있음: {node}"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(converted)


def test_gemini_schema_keeps_the_fields_we_need():
    """필드 이름은 스키마 키워드가 아니다 — 걸러내면 응답이 무의미해진다."""
    from agents.gemini_agent import to_gemini_schema
    from agents.prompts import RESPONSE_JSON_SCHEMA

    converted = to_gemini_schema(RESPONSE_JSON_SCHEMA)

    assert set(converted["properties"]) == set(RESPONSE_JSON_SCHEMA["properties"])
    assert converted["required"] == RESPONSE_JSON_SCHEMA["required"]
    assert converted["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]
    assert converted["properties"]["confidence"]["type"] == "number"


def test_failed_call_waits_before_retrying(monkeypatch):
    """즉시 재요청하면 요청량 제한을 더 밀어붙여 셋 다 실패한다."""
    from agents import base_agent

    slept: list[float] = []
    monkeypatch.setattr(base_agent.time, "sleep", lambda s: slept.append(s))

    base_agent._pause_before_retry(0)
    base_agent._pause_before_retry(1)
    base_agent._pause_before_retry(2)   # 마지막 시도 뒤에는 기다릴 이유가 없다

    assert slept == [1.0, 3.0], f"대기가 늘어나지 않습니다: {slept}"


# --- 요청량 한도 (2026-09-22, Gemini 무료 등급 하루 20회) ------------------------ #
#
# 한도에 걸린 엔진을 보통 실패처럼 다루면 최악의 일이 벌어진다. 재요청 2회를
# 더 하고, 그래도 실패하니 종목별 폴백으로 10종목 × 3회를 또 부른다 — 한
# 사이클에 최대 33번. 하루 20회짜리 한도는 두 번째 사이클에 바닥나고, 그 뒤로는
# 매 사이클이 33번씩 헛수고를 반복한다. 한도 오류는 '그만 부르라' 는 뜻이다.

from agents.base_agent import AgentQuotaError, looks_like_quota, quota_details, short_error

GEMINI_429 = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your "
    "current quota, please check your plan and billing details. * Quota exceeded for "
    "metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
    "limit: 20, model: gemini-3.5-flash Please retry in 12.489307345s.', 'status': "
    "'RESOURCE_EXHAUSTED', 'details': [{'quotaId': "
    "'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}}"
)


def test_a_quota_message_is_recognised():
    assert looks_like_quota(GEMINI_429)
    wait, daily = quota_details(GEMINI_429)
    assert round(wait) == 12
    assert daily is True, "PerDay 한도는 오늘 내내 유효하다"


def test_a_quota_message_becomes_one_short_line():
    """원문은 JSON 수십 줄이다. 종목 10개면 알림이 200줄이 된다."""
    line = short_error(GEMINI_429)
    assert "\n" not in line and len(line) < 80
    assert "일일" in line


def test_an_ordinary_error_keeps_its_text():
    assert short_error("연결 실패: timed out") == "연결 실패: timed out"


def test_a_very_long_ordinary_error_is_cut():
    line = short_error("x" * 500)
    assert len(line) <= 110 and line.endswith("…")


class _QuotaAgent(BaseAgent):
    """첫 호출부터 한도를 돌려주는 엔진."""

    name = "quota"

    def __init__(self, ai=AI, *, daily=True):
        super().__init__(ai)
        self.calls = 0
        self._daily = daily

    def _call_model(self, system_prompt, user_prompt, schema=None):
        self.calls += 1
        raise AgentQuotaError(short_error(GEMINI_429), retry_after=12.0, daily=self._daily)


def test_a_quota_error_is_not_retried():
    """재요청은 한도를 더 축낼 뿐이다."""
    agent = _QuotaAgent(AI)
    decision = agent.analyze({"code": "005930"})

    assert not decision.ok and decision.action == "HOLD"
    assert agent.calls == 1, f"한도 오류로 {agent.calls}번 불렀습니다"


def test_batch_quota_does_not_trigger_the_per_code_fallback():
    """None 을 주면 호출자가 10종목을 하나씩 다시 부른다 — 가장 나쁜 선택이다."""
    agent = _QuotaAgent(AI)
    snapshots = [{"code": f"00{i}", "name": f"종목{i}"} for i in range(10)]

    result = agent.analyze_many(snapshots)

    assert result is not None, "None 은 종목별 폴백을 부른다"
    assert len(result) == 10 and all(not d.ok for d in result.values())
    assert agent.calls == 1


def test_an_exhausted_engine_is_skipped_until_it_resets():
    """한 번 걸렸으면 그 뒤로는 부르지도 않는다."""
    agent = _QuotaAgent(AI)
    agent.analyze({"code": "005930"})
    before = agent.calls

    for _ in range(5):
        agent.analyze({"code": "005930"})
        agent.analyze_many([{"code": "000660"}])

    assert agent.calls == before, f"건너뛰어야 하는데 {agent.calls - before}번 더 불렀습니다"


def test_a_short_cooldown_expires(monkeypatch):
    """분당 한도는 잠깐 쉬었다가 다시 시도해야 한다 — 하루를 버리면 안 된다."""
    agent = _QuotaAgent(AI, daily=False)
    agent.analyze({"code": "005930"})
    assert agent._quota_blocked()

    clock = [agent._quota_until + 1]
    monkeypatch.setattr("agents.base_agent.time.monotonic", lambda: clock[0])
    assert not agent._quota_blocked(), "대기 시간이 지나면 다시 부를 수 있어야 한다"


def test_an_ordinary_failure_still_retries():
    """한도가 아닌 실패까지 한 번에 포기하면 사소한 오류에 사이클을 잃는다."""
    from agents.base_agent import AgentCallError

    class _Flaky(BaseAgent):
        name = "flaky"

        def __init__(self, ai=AI):
            super().__init__(ai)
            self.calls = 0

        def _call_model(self, system_prompt, user_prompt, schema=None):
            self.calls += 1
            raise AgentCallError("연결 실패: timed out")

    agent = _Flaky(AI)
    agent.analyze({"code": "005930"})
    assert agent.calls == AI.max_retries + 1
