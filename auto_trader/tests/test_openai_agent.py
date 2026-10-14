"""ChatGPT 판단 엔진 — 요청 구성과 응답 처리."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agents.openai_agent import OpenAiAgent
from config.loader import AiConfig

AI = AiConfig(timeout_sec=30, max_retries=1, min_confidence=0.6,
              news_max_items=5, news_lookback_hours=24)

PAYLOAD = {"action": "BUY", "confidence": 0.8, "weight_pct": 15,
           "reason": "이동평균 정배열", "target_price": 80000, "stop_loss_price": 66000}


class StubClient:
    """chat.completions.create 를 흉내낸다."""

    def __init__(self, *, content=None, refusal=None, usage=None, error=None, finish="stop"):
        self.calls: list[dict] = []
        self._content = json.dumps(PAYLOAD) if content is None else content
        self._refusal = refusal
        self._usage = usage
        self._error = error
        self._finish = finish
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        message = SimpleNamespace(content=self._content, refusal=self._refusal)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=self._finish)],
            usage=self._usage,
        )


def make(env_obj, **kwargs):
    client = StubClient(**kwargs)
    return OpenAiAgent(env_obj, AI, client=client), client


@pytest.fixture
def env(settings_obj):
    obj = settings_obj.env
    object.__setattr__(obj, "openai_api_key", "sk-test")
    object.__setattr__(obj, "openai_model", "gpt-5.1")
    object.__setattr__(obj, "openai_temperature", None)
    return obj


def test_returns_a_parsed_decision(env):
    agent, _ = make(env)
    decision = agent.analyze({"code": "005930", "name": "삼성전자"})
    assert decision.ok and decision.action == "BUY" and decision.weight_pct == 15
    assert decision.agent == "chatgpt"


def test_requests_structured_output(env):
    agent, client = make(env)
    agent.analyze({"code": "005930"})
    fmt = client.calls[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]


def test_uses_max_completion_tokens_not_max_tokens(env):
    """추론 모델은 max_tokens 를 거부한다."""
    agent, client = make(env)
    agent.analyze({"code": "005930"})
    assert "max_completion_tokens" in client.calls[0]
    assert "max_tokens" not in client.calls[0]


def test_temperature_is_omitted_by_default(env):
    """최신 추론 모델은 temperature 를 400 으로 거부한다."""
    agent, client = make(env)
    agent.analyze({"code": "005930"})
    assert "temperature" not in client.calls[0]


def test_temperature_is_sent_when_configured(env):
    object.__setattr__(env, "openai_temperature", 0.3)
    agent, client = make(env)
    agent.analyze({"code": "005930"})
    assert client.calls[0]["temperature"] == 0.3


def test_refusal_falls_back_to_hold(env):
    agent, _ = make(env, content="", refusal="정책상 답변할 수 없습니다")
    decision = agent.analyze({"code": "005930"})
    assert not decision.ok and decision.action == "HOLD"


def test_empty_response_falls_back_to_hold(env):
    agent, _ = make(env, content="")
    assert agent.analyze({"code": "005930"}).action == "HOLD"


def test_api_error_falls_back_to_hold(env):
    agent, _ = make(env, error=RuntimeError("rate limit"))
    decision = agent.analyze({"code": "005930"})
    assert not decision.ok and decision.action == "HOLD"


def test_malformed_json_falls_back_to_hold(env):
    agent, _ = make(env, content="음... 사는 게 좋겠습니다")
    assert not agent.analyze({"code": "005930"}).ok


def test_usage_tokens_are_recorded(env):
    usage = SimpleNamespace(prompt_tokens=1200, completion_tokens=340)
    agent, _ = make(env, usage=usage)
    decision = agent.analyze({"code": "005930"})
    assert decision.input_tokens == 1200 and decision.output_tokens == 340


def test_missing_usage_is_tolerated(env):
    agent, _ = make(env, usage=None)
    decision = agent.analyze({"code": "005930"})
    assert decision.input_tokens == 0 and decision.output_tokens == 0


def test_json_wrapped_in_prose_is_recovered(env):
    agent, _ = make(env, content=f"```json\n{json.dumps(PAYLOAD)}\n```")
    assert agent.analyze({"code": "005930"}).action == "BUY"
