"""AI 호출 토큰·비용 집계.

단가는 모델마다 바뀌므로 `config/settings.yaml` 의 `ai.pricing` 으로 덮어쓴다
(설정이 있으면 그것만 쓰고, 없으면 아래 기본표를 쓴다).
어느 표에도 없는 모델은 비용 0으로 기록하고 토큰만 남긴다 — 틀린 숫자보다 '모름'이 낫다.
"""

from __future__ import annotations

from dataclasses import dataclass

# 100만 토큰당 USD (입력, 출력) — 참고용 기본값. 실제 단가는 제공사 요금표를 확인할 것.
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
}


@dataclass
class Usage:
    """한 번의 모델 호출에서 쓴 토큰."""

    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens,
                     self.output_tokens + other.output_tokens)

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


def _match_pricing(model: str, pricing: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    """정확히 일치하는 모델명을 먼저, 없으면 접두어가 가장 긴 항목을 쓴다."""
    if model in pricing:
        return pricing[model]
    candidates = [name for name in pricing if model.startswith(name)]
    if not candidates:
        return None
    return pricing[max(candidates, key=len)]


def estimate_cost(
    model: str, usage: Usage, pricing: dict[str, tuple[float, float]] | None = None
) -> float:
    """USD 추정 비용. 단가를 모르는 모델은 0.0."""
    rates = _match_pricing(model, pricing or DEFAULT_PRICING)
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    return round(
        usage.input_tokens / 1_000_000 * input_rate
        + usage.output_tokens / 1_000_000 * output_rate,
        6,
    )
