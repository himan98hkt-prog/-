"""Gemini 판단 엔진 (google-genai 신규 SDK).

`response_mime_type="application/json"` + `response_schema` 로 JSON 형식을 강제하고,
그래도 어긋나면 base_agent 의 재요청·HOLD 폴백이 받아낸다.
"""

from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from agents.base_agent import (AgentCallError, AgentQuotaError, BaseAgent,
                               looks_like_quota, quota_details, short_error)
from agents.prompts import BATCH_RESPONSE_JSON_SCHEMA, RESPONSE_JSON_SCHEMA
from agents.usage import Usage
from config.loader import AiConfig, EnvConfig
from utils.logger import get_logger, register_secret

logger = get_logger("gemini_agent")

MAX_OUTPUT_TOKENS = 4096
# 후보 전부를 한 번에 볼 때는 답이 종목 수만큼 길어진다. 게다가 Gemini 는 사고
# 토큰도 이 한도를 함께 쓴다 — 모자라면 JSON 이 중간에 잘려 파싱 실패로 떨어지고,
# 그러면 종목별 호출로 되돌아가 비용만 두 배가 된다.
BATCH_MAX_OUTPUT_TOKENS = 16384

# Gemini 의 response_schema 는 OpenAPI 3.0 스키마의 **부분집합**만 받는다.
# 모르는 키가 하나라도 있으면 요청 전체를 400 INVALID_ARGUMENT 로 거절한다
# ("Invalid JSON payload received. Unknown name ..."). 공용 스키마에는
# Claude·ChatGPT 가 요구하는 additionalProperties 가 들어 있어서 그대로 보내면
# Gemini 만 매번 실패하고, 한 엔진이 빠지면 합의가 늘 관망이 된다.
GEMINI_SCHEMA_KEYS = frozenset({
    "type", "format", "description", "nullable", "enum",
    "items", "properties", "required", "propertyOrdering",
    "minItems", "maxItems",
})


def to_gemini_schema(schema: object) -> object:
    """Gemini 가 아는 키만 남긴다(중첩 포함).

    `properties` 안쪽은 스키마 키워드가 아니라 **필드 이름**이라 걸러내면 안 된다.
    """
    if isinstance(schema, dict):
        cleaned: dict[str, object] = {}
        for key, value in schema.items():
            if key not in GEMINI_SCHEMA_KEYS:
                continue
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {name: to_gemini_schema(sub) for name, sub in value.items()}
            elif key in ("enum", "required"):
                cleaned[key] = value  # 값 목록 그대로
            else:
                cleaned[key] = to_gemini_schema(value)
        return cleaned
    if isinstance(schema, list):
        return [to_gemini_schema(item) for item in schema]
    return schema


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
            http_options=types.HttpOptions(timeout=ai.client_timeout_sec * 1000),  # ms
        )

    def _config(self, system_prompt: str, schema: dict) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=to_gemini_schema(schema),
            temperature=self.temperature,
            max_output_tokens=(BATCH_MAX_OUTPUT_TOKENS if _is_batch(schema)
                               else MAX_OUTPUT_TOKENS),
        )

    def _call_model(self, system_prompt: str, user_prompt: str,
                    schema: dict | None = None) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self._config(system_prompt, schema or RESPONSE_JSON_SCHEMA),
            )
        except genai_errors.APIError as exc:
            text = str(exc)
            if getattr(exc, "code", None) == 429 or looks_like_quota(text):
                wait, daily = quota_details(text)
                raise AgentQuotaError(short_error(text), retry_after=wait,
                                      daily=daily) from exc
            raise AgentCallError(f"API 오류: {short_error(text)}") from exc
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


def _is_batch(schema: object) -> bool:
    """후보 전부를 한 번에 보는 요청인가."""
    return schema is BATCH_RESPONSE_JSON_SCHEMA
