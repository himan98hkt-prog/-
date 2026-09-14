"""ChatGPT(OpenAI) 판단 엔진.

Chat Completions + Structured Outputs(`response_format` 의 json_schema, strict)로
JSON 형식을 강제한다. 그래도 어긋나면 base_agent 의 재요청·HOLD 폴백이 받아낸다.

이 엔진은 **선택**이다. `OPENAI_API_KEY` 가 없으면 Claude·Gemini 둘로만 돌아간다.
"""

from __future__ import annotations

from agents.base_agent import AgentCallError, BaseAgent
from agents.prompts import RESPONSE_JSON_SCHEMA
from agents.usage import Usage
from config.loader import AiConfig, EnvConfig
from utils.logger import get_logger, register_secret

logger = get_logger("openai_agent")

MAX_OUTPUT_TOKENS = 4096
SCHEMA_NAME = "trading_decision"


class OpenAiAgent(BaseAgent):
    name = "chatgpt"

    def __init__(self, env: EnvConfig, ai: AiConfig, client=None) -> None:
        super().__init__(ai)
        self.pricing = dict(ai.pricing) or None
        self.model = env.openai_model
        self.temperature = env.openai_temperature
        register_secret(env.openai_api_key)
        if client is not None:
            self.client = client
        else:
            from openai import OpenAI

            self.client = OpenAI(api_key=env.openai_api_key, timeout=ai.timeout_sec, max_retries=0)

    def _request_kwargs(self, system_prompt: str, user_prompt: str) -> dict:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": SCHEMA_NAME,
                    "schema": RESPONSE_JSON_SCHEMA,
                    "strict": True,
                },
            },
            # 추론 모델은 max_tokens 대신 이 이름을 쓴다.
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
        }
        # 최신 추론 모델은 temperature 를 거부한다 — 비워 두면 아예 보내지 않는다.
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        return kwargs

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                **self._request_kwargs(system_prompt, user_prompt)
            )
        except Exception as exc:  # SDK 예외 종류가 많아 통째로 잡아 원문을 남긴다
            raise AgentCallError(f"{type(exc).__name__}: {exc}") from exc

        self._last_usage = _extract_usage(response)

        choices = getattr(response, "choices", None) or []
        if not choices:
            raise AgentCallError("빈 응답 (choices 없음)")

        message = choices[0].message
        # 안전 필터에 걸리면 refusal 이 채워지고 content 가 빈다.
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AgentCallError(f"모델이 응답을 거부했습니다: {refusal}")

        text = (getattr(message, "content", None) or "").strip()
        if not text:
            finish = getattr(choices[0], "finish_reason", "")
            raise AgentCallError(f"빈 응답{f' (finish_reason={finish})' if finish else ''}")
        return text


def _extract_usage(response: object) -> Usage:
    """`response.usage` 에서 토큰 수를 꺼낸다 (없으면 0).

    추론 토큰은 completion_tokens 에 이미 포함돼 있으므로 따로 더하지 않는다.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )
