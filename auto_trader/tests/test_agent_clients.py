"""Claude/Gemini SDK 래퍼 테스트 — 요청 파라미터와 오류 변환 확인."""

from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import pytest
from google.genai import errors as genai_errors

from agents.base_agent import AgentCallError
from agents.claude_agent import ClaudeAgent
from agents.gemini_agent import GeminiAgent
from config.loader import AiConfig
from tests.conftest import make_env

AI = AiConfig(timeout_sec=30, max_retries=1, min_confidence=0.6,
              news_max_items=5, news_lookback_hours=24)

VALID = json.dumps({"action": "HOLD", "confidence": 0.4, "weight_pct": 0,
                    "reason": "지표 혼조", "target_price": 0, "stop_loss_price": 0},
                   ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #


class FakeMessages:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeAnthropic:
    def __init__(self, results):
        self.messages = FakeMessages(results)


def text_response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason
    )


def bad_request(message: str) -> anthropic.BadRequestError:
    request = SimpleNamespace(url="https://api.anthropic.com/v1/messages")
    response = SimpleNamespace(status_code=400, headers={}, request=request)
    return anthropic.BadRequestError(message, response=response, body=None)


def test_claude_sends_structured_output_schema():
    client = FakeAnthropic([text_response(VALID)])
    agent = ClaudeAgent(make_env(), AI, client=client)
    decision = agent.analyze({"code": "005930"})

    assert decision.ok and decision.action == "HOLD"
    request = client.messages.calls[0]
    assert request["model"] == "claude-sonnet-5"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert request["output_config"]["format"]["schema"]["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]
    assert "temperature" not in request, "최신 모델은 temperature 를 거부하므로 기본은 미전송"
    assert request["messages"][0]["role"] == "user"


def test_claude_sends_temperature_and_effort_when_configured():
    env = make_env(claude_temperature=0.2, claude_effort="low")
    client = FakeAnthropic([text_response(VALID)])
    ClaudeAgent(env, AI, client=client).analyze({"code": "005930"})

    request = client.messages.calls[0]
    assert request["temperature"] == 0.2
    assert request["output_config"]["effort"] == "low"


def test_claude_drops_temperature_when_model_rejects_it():
    """구형 모델용 설정을 최신 모델에 쓴 경우, 한 번 벗겨내고 재시도한다."""
    env = make_env(claude_temperature=0.2)
    client = FakeAnthropic([
        bad_request("temperature: Extra inputs are not permitted"),
        text_response(VALID),
    ])
    agent = ClaudeAgent(env, AI, client=client)
    decision = agent.analyze({"code": "005930"})

    assert decision.ok
    assert "temperature" in client.messages.calls[0]
    assert "temperature" not in client.messages.calls[1]
    assert agent.temperature is None, "이후 호출에서도 제외되어야 합니다"


def test_claude_other_bad_request_becomes_hold():
    client = FakeAnthropic([bad_request("model: unknown model") for _ in range(AI.max_retries + 1)])
    decision = ClaudeAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and decision.ok is False
    assert "요청 거부" in decision.error


def test_claude_refusal_becomes_hold():
    client = FakeAnthropic([text_response("", "refusal") for _ in range(AI.max_retries + 1)])
    decision = ClaudeAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD"
    assert "거부" in decision.error


def test_claude_empty_response_becomes_hold():
    client = FakeAnthropic([text_response("   ") for _ in range(AI.max_retries + 1)])
    decision = ClaudeAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and "빈 응답" in decision.error


def test_claude_timeout_becomes_hold():
    error = anthropic.APITimeoutError(request=SimpleNamespace(url="x"))
    client = FakeAnthropic([error for _ in range(AI.max_retries + 1)])
    decision = ClaudeAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and "타임아웃" in decision.error


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #


class FakeModels:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeGenai:
    def __init__(self, results):
        self.models = FakeModels(results)


def test_gemini_requests_json_mime_and_schema():
    client = FakeGenai([SimpleNamespace(text=VALID)])
    decision = GeminiAgent(make_env(), AI, client=client).analyze({"code": "005930"})

    assert decision.ok and decision.agent == "gemini"
    request = client.models.calls[0]
    assert request["model"] == "gemini-2.5-pro"
    config = request["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]
    assert config.temperature == 0.2, "Gemini 는 temperature 를 지원한다"
    assert "단기 스윙 애널리스트" in config.system_instruction


def test_gemini_custom_temperature():
    client = FakeGenai([SimpleNamespace(text=VALID)])
    GeminiAgent(make_env(gemini_temperature=0.7), AI, client=client).analyze({"code": "005930"})
    assert client.models.calls[0]["config"].temperature == 0.7


def test_gemini_api_error_becomes_hold():
    error = genai_errors.APIError(429, {"message": "quota exceeded"})
    client = FakeGenai([error for _ in range(AI.max_retries + 1)])
    decision = GeminiAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and decision.ok is False


def test_gemini_blocked_empty_response_becomes_hold():
    blocked = SimpleNamespace(text=None, prompt_feedback="SAFETY")
    client = FakeGenai([blocked for _ in range(AI.max_retries + 1)])
    decision = GeminiAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and "빈 응답" in decision.error


def test_gemini_unexpected_exception_becomes_hold():
    client = FakeGenai([OSError("connection reset") for _ in range(AI.max_retries + 1)])
    decision = GeminiAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.action == "HOLD" and "OSError" in decision.error


def test_gemini_markdown_wrapped_json_still_parsed():
    client = FakeGenai([SimpleNamespace(text=f"```json\n{VALID}\n```")])
    decision = GeminiAgent(make_env(), AI, client=client).analyze({"code": "005930"})
    assert decision.ok and decision.action == "HOLD"
