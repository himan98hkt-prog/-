"""Claude 판단 엔진 (anthropic SDK).

Structured Outputs(`output_config.format`)로 JSON 형식을 API 차원에서 강제하고,
그래도 형식이 어긋나면 base_agent 의 재요청·HOLD 폴백이 받아낸다.
"""

from __future__ import annotations

import anthropic

from agents.base_agent import AgentCallError, BaseAgent
from agents.prompts import RESPONSE_JSON_SCHEMA
from agents.usage import Usage
from config.loader import AiConfig, EnvConfig
from utils.logger import get_logger, register_secret

logger = get_logger("claude_agent")

# 응답 JSON 자체는 짧지만, 최신 모델은 사고(thinking) 토큰도 max_tokens 를 함께 쓴다.
MAX_TOKENS = 8000
SDK_MAX_RETRIES = 1  # 429/5xx 재시도. 나머지 재시도는 base_agent 가 담당한다.


class ClaudeAgent(BaseAgent):
    name = "claude"

    def __init__(self, env: EnvConfig, ai: AiConfig, client: anthropic.Anthropic | None = None) -> None:
        super().__init__(ai)
        self.pricing = dict(ai.pricing) or None
        self.model = env.claude_model
        self.temperature = env.claude_temperature
        self.effort = env.claude_effort
        register_secret(env.anthropic_api_key)
        self.client = client or anthropic.Anthropic(
            api_key=env.anthropic_api_key,
            timeout=float(ai.timeout_sec),
            max_retries=SDK_MAX_RETRIES,
        )

    def _request_kwargs(self, system_prompt: str, user_prompt: str, *, with_temperature: bool) -> dict:
        output_config: dict = {"format": {"type": "json_schema", "schema": RESPONSE_JSON_SCHEMA}}
        if self.effort:
            output_config["effort"] = self.effort

        kwargs: dict = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "output_config": output_config,
        }
        if with_temperature and self.temperature is not None:
            kwargs["temperature"] = self.temperature
        return kwargs

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        send_temperature = self.temperature is not None
        for _ in range(2):  # temperature 거부 시 한 번만 제외하고 재시도
            try:
                response = self.client.messages.create(
                    **self._request_kwargs(system_prompt, user_prompt, with_temperature=send_temperature)
                )
            except anthropic.BadRequestError as exc:
                if send_temperature and "temperature" in str(exc).lower():
                    logger.warning(
                        "%s 모델은 temperature 를 지원하지 않습니다 — 이후 호출에서 제외합니다", self.model
                    )
                    self.temperature = None
                    send_temperature = False
                    continue
                raise AgentCallError(f"요청 거부: {exc}") from exc
            except anthropic.APITimeoutError as exc:
                raise AgentCallError(f"타임아웃: {exc}") from exc
            except anthropic.APIStatusError as exc:
                raise AgentCallError(f"API 오류(HTTP {exc.status_code}): {exc}") from exc
            except anthropic.APIConnectionError as exc:
                raise AgentCallError(f"연결 실패: {exc}") from exc

            self._last_usage = _extract_usage(response)

            if getattr(response, "stop_reason", None) == "refusal":
                raise AgentCallError("모델이 응답을 거부했습니다(refusal)")

            text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
            if not text.strip():
                raise AgentCallError("빈 응답")
            return text

        raise AgentCallError("요청 파라미터를 조정했지만 호출에 실패했습니다")


def _extract_usage(response: object) -> Usage:
    """`response.usage` 에서 토큰 수를 꺼낸다 (없으면 0)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )
