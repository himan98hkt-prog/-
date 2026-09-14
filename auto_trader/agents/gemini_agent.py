"""Gemini 판단 엔진 (google-genai 신규 SDK).

`response_mime_type="application/json"` + `response_schema` 로 JSON 형식을 강제하고,
그래도 어긋나면 base_agent 의 재요청·HOLD 폴백이 받아낸다.
"""

from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from agents.base_agent import AgentCallError, BaseAgent
from agents.prompts import RESPONSE_JSON_SCHEMA
from agents.usage import Usage
from config.loader import AiConfig, EnvConfig
from utils.logger import get_logger, register_secret

logger = get_logger("gemini_agent")

MAX_OUTPUT_TOKENS = 4096


class GeminiAgent(BaseAgent):
    name = "gemini"

    def __init__(self, env: EnvConfig, ai: AiConfig, client: genai.Client | None = None) -> None:
        super().__init__(ai)
        self.pricing = dict(ai.pricing) or None
        self.model = env.gemini_model
        self.temperature = env.gemini_temperature
        register_secret(env.gemini_api_key)
        self.client = client or genai.Client(
            api_key=env.gemini_api_key,
            http_options=types.HttpOptions(timeout=ai.timeout_sec * 1000),  # ms
        )

    def _config(self, system_prompt: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=RESPONSE_JSON_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self._config(system_prompt),
            )
        except genai_errors.APIError as exc:
            raise AgentCallError(f"API 오류: {exc}") from exc
        except Exception as exc:  # 네트워크·타임아웃 등 SDK 외 예외
            raise AgentCallError(f"{type(exc).__name__}: {exc}") from exc

        self._last_usage = _extract_usage(response)

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            # 안전 필터 등으로 후보가 비는 경우가 있다.
            reason = getattr(response, "prompt_feedback", None)
            raise AgentCallError(f"빈 응답{f' ({reason})' if reason else ''}")
        return text


def _extract_usage(response: object) -> Usage:
    """`response.usage_metadata` 에서 토큰 수를 꺼낸다 (없으면 0)."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return Usage()
    output = int(getattr(meta, "candidates_token_count", 0) or 0)
    # 사고(thinking) 토큰도 과금 대상이므로 출력에 합산한다.
    output += int(getattr(meta, "thoughts_token_count", 0) or 0)
    return Usage(
        input_tokens=int(getattr(meta, "prompt_token_count", 0) or 0),
        output_tokens=output,
    )
