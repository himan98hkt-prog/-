"""상대평가 — 후보를 한꺼번에 주고 서로 비교하게 한다.

종목을 하나씩 던지고 "이거 살 만한가" 를 물으면 그건 절대평가다. 기준선이 높아
대부분의 날은 아무도 못 넘고, 답이 관망으로 쏠린다. 실제 자금은 "이 중 어디에"
로 배분되므로 후보를 함께 보여준다.
"""

from __future__ import annotations

import copy
import json

import pytest

from agents.base_agent import AgentCallError, BaseAgent, run_agents_batch
from agents.prompts import (
    BATCH_RESPONSE_JSON_SCHEMA,
    RESPONSE_JSON_SCHEMA,
    SYSTEM_PROMPT,
    batch_system_prompt,
    build_batch_user_prompt,
)
from agents.schemas import SchemaError, validate_batch_payload
from agents.usage import Usage
from config.loader import AiConfig
from tests.test_agents import SNAPSHOT

AI = AiConfig(timeout_sec=5, max_retries=2, min_confidence=0.6,
              news_max_items=5, news_lookback_hours=24, batch_timeout_sec=10)

CODES = ["005930", "000660", "035420"]


def snapshots(codes=CODES) -> list[dict]:
    result = []
    for code in codes:
        item = copy.deepcopy(SNAPSHOT)
        item["code"] = code
        result.append(item)
    return result


def pick(code, action="HOLD", confidence=0.5, weight=0):
    return {"code": code, "action": action, "confidence": confidence,
            "weight_pct": weight, "reason": f"{code} 상대 비교 결과",
            "target_price": 0, "stop_loss_price": 0}


def reply(*picks) -> str:
    return json.dumps({"picks": list(picks)}, ensure_ascii=False)


class BatchAgent(BaseAgent):
    """정해진 응답을 순서대로 돌려준다. 어떤 프롬프트를 받았는지 남긴다."""

    def __init__(self, responses, ai=AI, name="scripted"):
        super().__init__(ai)
        self.name = name
        self.model = "scripted-model"
        self.responses = list(responses)
        self.systems: list[str] = []
        self.prompts: list[str] = []
        self.schemas: list[dict | None] = []

    def _call_model(self, system_prompt, user_prompt, schema=None):
        self.systems.append(system_prompt)
        self.prompts.append(user_prompt)
        self.schemas.append(schema)
        self._last_usage = Usage(input_tokens=1000, output_tokens=301)
        response = self.responses.pop(0) if self.responses else AgentCallError("응답 소진")
        if isinstance(response, Exception):
            raise response
        return response


# --- 프롬프트가 실제로 상대평가를 요구하는가 -------------------------------- #

def test_batch_prompt_asks_for_comparison_not_a_verdict():
    text = batch_system_prompt(max_picks=3)
    assert "서로 비교" in text
    assert "최대 3종목" in text, "매수 상한이 프롬프트에 들어가야 합니다"
    assert "전부 HOLD 여도 된다" in text, "억지로 고르게 하면 아무거나 사게 됩니다"


def test_both_prompts_name_the_cost_of_not_buying():
    """안 사는 비용을 말해주지 않으면 HOLD 는 '절대 틀릴 수 없는 답' 이 된다."""
    for text in (SYSTEM_PROMPT, batch_system_prompt(3)):
        assert "현금의 수익률은 0%" in text
        assert "확신 없는 매수는" in text, "반대쪽 비용도 같이 말해야 한쪽으로 안 기웁니다"


def test_prompt_no_longer_lists_news_as_a_criterion():
    """뉴스는 수집하지 않는다 — 늘 빈 항목을 기준으로 세우면 '근거 부족' 만 쌓인다."""
    assert "뉴스 감성" not in SYSTEM_PROMPT
    assert "뉴스 감성" not in batch_system_prompt(3)


def test_batch_user_prompt_carries_every_candidate():
    text = build_batch_user_prompt(snapshots())
    for code in CODES:
        assert code in text
    assert "3종목" in text


def test_retry_prompt_says_what_was_wrong():
    text = build_batch_user_prompt(snapshots(), problem="picks 에 빠진 종목: 035420")
    assert "빠진 종목: 035420" in text
    assert "정확히 3" in text
    assert "005930, 000660, 035420" in text


def test_batch_schema_extends_the_single_one():
    item = BATCH_RESPONSE_JSON_SCHEMA["properties"]["picks"]["items"]
    assert item["required"][0] == "code"
    assert set(RESPONSE_JSON_SCHEMA["required"]) <= set(item["required"])


# --- 응답 검증 ---------------------------------------------------------------- #

def test_every_candidate_comes_back():
    decisions = validate_batch_payload(
        {"picks": [pick("005930", "BUY", 0.8, 20), pick("000660"), pick("035420")]},
        "claude", CODES)
    assert set(decisions) == set(CODES)
    assert decisions["005930"].action == "BUY" and decisions["005930"].ok


def test_a_missing_candidate_is_an_error_not_a_hold():
    """'관망했다' 와 '빠뜨렸다' 가 섞이면 합의 통계도 적중률도 못 믿는다."""
    with pytest.raises(SchemaError, match="빠진 종목"):
        validate_batch_payload({"picks": [pick("005930"), pick("000660")]}, "claude", CODES)


def test_duplicate_candidate_is_rejected():
    with pytest.raises(SchemaError, match="두 번"):
        validate_batch_payload({"picks": [pick("005930"), pick("005930")]}, "claude", ["005930"])


def test_invented_code_is_dropped_but_noted():
    decisions = validate_batch_payload(
        {"picks": [pick("005930"), pick("999999")]}, "claude", ["005930"])
    assert set(decisions) == {"005930"}
    assert "999999" in decisions["005930"].error


def test_each_decision_keeps_only_its_own_raw():
    """응답 전체를 종목 수만큼 복사하면 DB 가 비대해진다."""
    decisions = validate_batch_payload(
        {"picks": [pick("005930"), pick("000660"), pick("035420")]}, "claude", CODES)
    assert "000660" not in decisions["005930"].raw


# --- 한 번의 호출로 후보 전부 --------------------------------------------------- #

def test_one_call_covers_every_candidate():
    agent = BatchAgent([reply(pick("005930", "BUY", 0.8, 20), pick("000660"), pick("035420"))])
    decisions = agent.analyze_many(snapshots())

    assert len(agent.prompts) == 1, "종목 수만큼 부르면 상대평가가 아닙니다"
    assert set(decisions) == set(CODES)
    assert agent.schemas[0] is BATCH_RESPONSE_JSON_SCHEMA


def test_tokens_are_split_so_the_daily_total_stays_right():
    """호출은 하나인데 비용 기록은 종목별이다. 그대로 달면 합계가 부풀고,
    안 달면 그날 비용이 통째로 사라진다."""
    agent = BatchAgent([reply(pick("005930"), pick("000660"), pick("035420"))])
    decisions = agent.analyze_many(snapshots())

    assert sum(d.input_tokens for d in decisions.values()) == 1000
    assert sum(d.output_tokens for d in decisions.values()) == 301, "나눗셈에서 흘리면 안 됩니다"


def test_a_missing_candidate_triggers_a_retry():
    agent = BatchAgent([
        reply(pick("005930"), pick("000660")),                       # 035420 누락
        reply(pick("005930"), pick("000660"), pick("035420")),
    ])
    decisions = agent.analyze_many(snapshots())

    assert set(decisions) == set(CODES)
    assert "빠진 종목" in agent.prompts[1], "무엇이 틀렸는지 알려주고 다시 물어야 합니다"


def test_giving_up_returns_none_so_the_caller_can_fall_back():
    """'전원 관망' 과 '판단을 못 받았다' 는 다르다 — 값으로도 달라야 한다."""
    agent = BatchAgent([AgentCallError("500"), AgentCallError("500"), AgentCallError("500")])
    assert agent.analyze_many(snapshots()) is None


def test_empty_candidate_list_is_not_a_call():
    agent = BatchAgent([])
    assert agent.analyze_many([]) == {}
    assert agent.prompts == []


# --- 엔진 하나가 실패해도 사이클은 산다 ----------------------------------------- #

def test_a_failing_engine_falls_back_to_per_stock_calls():
    good = BatchAgent([reply(pick("005930", "BUY", 0.8, 20), pick("000660"), pick("035420"))],
                      name="gemini")
    single = json.dumps({"action": "HOLD", "confidence": 0.4, "weight_pct": 0,
                         "reason": "관망", "target_price": 0, "stop_loss_price": 0})
    # 배치는 세 번 다 실패하고, 이어지는 종목별 호출 3건은 성공한다.
    bad = BatchAgent([AgentCallError("x"), AgentCallError("x"), AgentCallError("x"),
                      single, single, single], name="claude")

    votes = run_agents_batch([good, bad], snapshots(), AI)

    assert set(votes) == set(CODES)
    assert votes["005930"]["gemini"].action == "BUY"
    assert votes["005930"]["claude"].ok, "폴백이 동작하면 판단은 살아 있어야 합니다"
    assert len(bad.prompts) == 6, "배치 3회 + 종목별 3회"


def test_engines_that_returned_nothing_still_count_as_a_vote():
    """빈 칸을 남기면 만장일치 조건이 조용히 느슨해진다."""
    silent = BatchAgent([AgentCallError("x")] * 99, name="claude")
    votes = run_agents_batch([silent], snapshots(), AI)

    for code in CODES:
        decision = votes[code]["claude"]
        assert decision.action == "HOLD" and not decision.ok


# --- 답이 길어진다 — 출력 한도가 따라가야 한다 --------------------------------- #

def test_every_engine_raises_its_output_limit_for_a_batch():
    """모자라면 JSON 이 중간에 잘리고, 폴백으로 되돌아가 비용만 두 배가 된다."""
    from agents import claude_agent, gemini_agent, openai_agent

    assert claude_agent.BATCH_MAX_TOKENS > claude_agent.MAX_TOKENS
    assert gemini_agent.BATCH_MAX_OUTPUT_TOKENS > gemini_agent.MAX_OUTPUT_TOKENS
    assert openai_agent.BATCH_MAX_OUTPUT_TOKENS > openai_agent.MAX_OUTPUT_TOKENS


def test_claude_sends_the_bigger_limit_only_for_batches():
    from unittest.mock import MagicMock

    from agents.claude_agent import BATCH_MAX_TOKENS, MAX_TOKENS, ClaudeAgent
    from tests.conftest import make_env

    agent = ClaudeAgent(make_env(), AI, client=MagicMock())
    single = agent._request_kwargs("s", "u", RESPONSE_JSON_SCHEMA, with_temperature=False)
    batch = agent._request_kwargs("s", "u", BATCH_RESPONSE_JSON_SCHEMA, with_temperature=False)

    assert single["max_tokens"] == MAX_TOKENS
    assert batch["max_tokens"] == BATCH_MAX_TOKENS


def test_batching_sends_less_data_than_asking_one_by_one():
    """상대평가가 비용까지 늘리면 받아들이기 어렵다 — 시스템 프롬프트가 한 번만 간다."""
    batch = len(batch_system_prompt(3)) + len(build_batch_user_prompt(snapshots()))
    one_by_one = sum(len(SYSTEM_PROMPT) + len(build_batch_user_prompt([s]))
                     for s in snapshots())
    assert batch < one_by_one
