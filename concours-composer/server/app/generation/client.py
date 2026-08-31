"""Anthropic Claude 호출 래퍼.

- 모든 호출은 Structured Outputs(`messages.parse` + Pydantic) 로 강제한다.
  LLM 이 자유 텍스트나 MusicXML 을 뱉을 여지를 없앤다(절대 규칙 1).
- 곡 하나에 쓰는 비용을 누적해 `MAX_COST_PER_COMPOSITION` 을 넘으면 중단한다(§7.2).
- 모델 문자열은 Settings 를 통해서만 읽는다(절대 규칙 12).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# USD / 1M 토큰. docs.claude.com 모델 페이지 기준(2026-06). 모르는 모델은 최상위가로 가정한다.
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
_FALLBACK_PRICE = (10.00, 50.00)


class CostLimitExceeded(RuntimeError):
    """곡 하나의 비용 상한을 넘었다. 파이프라인을 중단하고 원장에게 알린다."""


@dataclass
class CallRecord:
    stage: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float


@dataclass
class CostLedger:
    """곡 한 곡에 대한 비용 원장. 파이프라인이 통째로 하나를 공유한다."""

    limit_usd: float
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return round(sum(c.cost_usd for c in self.calls), 6)

    def remaining(self) -> float:
        return max(0.0, self.limit_usd - self.total_usd)

    def add(self, rec: CallRecord) -> None:
        self.calls.append(rec)
        if self.total_usd > self.limit_usd:
            raise CostLimitExceeded(
                f"곡 1개 비용 상한 초과: ${self.total_usd:.4f} > ${self.limit_usd:.2f} "
                f"({len(self.calls)}회 호출). MAX_COST_PER_COMPOSITION 을 조정하거나 마디 수를 줄여라."
            )

    def check_before_call(self) -> None:
        if self.total_usd >= self.limit_usd:
            raise CostLimitExceeded(f"이미 상한 도달: ${self.total_usd:.4f} / ${self.limit_usd:.2f}")

    def summary(self) -> dict[str, Any]:
        by_stage: dict[str, float] = {}
        for c in self.calls:
            by_stage[c.stage] = round(by_stage.get(c.stage, 0.0) + c.cost_usd, 6)
        return {
            "total_usd": self.total_usd,
            "limit_usd": self.limit_usd,
            "calls": len(self.calls),
            "by_stage": by_stage,
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0) -> float:
    inp, out = PRICES.get(model, _FALLBACK_PRICE)
    # 캐시 읽기는 입력가의 약 1/10.
    billed_input = input_tokens + cache_read * 0.1
    return (billed_input * inp + output_tokens * out) / 1_000_000


class ClaudeClient:
    """구조화 출력 전용 얇은 래퍼. 스키마 밖 응답은 SDK 가 걸러준다."""

    def __init__(self, settings: Settings | None = None, ledger: CostLedger | None = None) -> None:
        self.settings = settings or get_settings()
        self.ledger = ledger or CostLedger(limit_usd=self.settings.max_cost_per_composition)
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return self.settings.has_api_key

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def parse(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        output_model: type[T],
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> T:
        """구조화 출력 1회 호출. 결과는 검증된 Pydantic 인스턴스."""
        if not self.available:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 가 없다. 오프라인에서는 StubComposerEngine 을 쓴다."
            )
        self.ledger.check_before_call()
        model_id = model or self.settings.composer_model

        client = self._get_client()
        response = client.messages.parse(
            model=model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_model,
        )

        usage = response.usage
        rec = CallRecord(
            stage=stage,
            model=model_id,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cost_usd=0.0,
        )
        rec.cost_usd = estimate_cost(
            model_id, rec.input_tokens, rec.output_tokens, rec.cache_read_tokens
        )
        self.ledger.add(rec)
        log.info(
            "claude %s model=%s in=%d out=%d $%.4f (누적 $%.4f)",
            stage, model_id, rec.input_tokens, rec.output_tokens, rec.cost_usd, self.ledger.total_usd,
        )

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise RuntimeError(f"{stage}: 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
        return parsed  # type: ignore[return-value]
