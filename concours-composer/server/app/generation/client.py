"""Anthropic Claude 호출 래퍼.

- 모든 호출은 Structured Outputs(`messages.parse` + Pydantic) 로 강제한다.
  LLM 이 자유 텍스트나 MusicXML 을 뱉을 여지를 없앤다(절대 규칙 1).
- 곡 하나에 쓰는 비용을 누적해 `MAX_COST_PER_COMPOSITION` 을 넘으면 중단한다(§7.2).
- 모델 문자열은 Settings 를 통해서만 읽는다(절대 규칙 12).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.generation.apierrors import reraise_friendly

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
    cache_write_tokens: int = 0
    latency_ms: int = 0
    batched: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": self.latency_ms,
            "batched": self.batched,
        }


@dataclass
class CostLedger:
    """곡 한 곡에 대한 비용 원장. 파이프라인이 통째로 하나를 공유한다.

    세션 엔진(API 미호출)으로 작곡할 때도 **토큰만 세어** 같은 원장에 남긴다.
    나중에 실제 API 로 전환할 때 곡당 비용을 그대로 계산할 수 있어야 하기 때문이다.
    """

    limit_usd: float
    calls: list[CallRecord] = field(default_factory=list)
    composition_id: str = ""
    engine: str = ""

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

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    def summary(self) -> dict[str, Any]:
        by_stage: dict[str, dict[str, Any]] = {}
        for c in self.calls:
            row = by_stage.setdefault(
                c.stage.split("[")[0],
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            )
            row["calls"] += 1
            row["input_tokens"] += c.input_tokens
            row["output_tokens"] += c.output_tokens
            row["cost_usd"] = round(row["cost_usd"] + c.cost_usd, 6)
        return {
            "composition_id": self.composition_id,
            "engine": self.engine,
            "total_usd": self.total_usd,
            "limit_usd": self.limit_usd,
            "calls": len(self.calls),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cache_read_tokens": sum(c.cache_read_tokens for c in self.calls),
            "cache_write_tokens": sum(c.cache_write_tokens for c in self.calls),
            "by_stage": by_stage,
        }

    def projected_cost(self, model: str) -> dict[str, Any]:
        """이 곡을 지정 모델로 실제 호출했다면 얼마였을지.

        세션 엔진으로 만든 곡의 토큰 수를 그대로 넣어 API 전환 비용을 미리 본다.
        캐시 적중을 감안한 낙관치도 함께 낸다(고정 컨텍스트가 반복되므로 실제로는
        입력의 상당 부분이 캐시에서 읽힌다).
        """
        inp, out = PRICES.get(model, _FALLBACK_PRICE)
        raw = (self.total_input_tokens * inp + self.total_output_tokens * out) / 1_000_000
        # 첫 호출만 전체가 입력, 이후는 고정 컨텍스트가 캐시에서 읽힌다고 가정(입력의 70%)
        cached_input = self.total_input_tokens * 0.30 + self.total_input_tokens * 0.70 * 0.1
        cached = (cached_input * inp + self.total_output_tokens * out) / 1_000_000
        return {
            "model": model,
            "calls": len(self.calls),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd_no_cache": round(raw, 4),
            "cost_usd_with_cache": round(cached, 4),
        }

    def write(self, path: Path, *, model: str | None = None) -> None:
        """곡당 비용 로그를 파일로 남긴다(§ 원장 지시 5)."""
        payload: dict[str, Any] = {
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "summary": self.summary(),
            "calls": [c.as_dict() for c in self.calls],
        }
        if model:
            payload["projection"] = self.projected_cost(model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def estimate_cost(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0) -> float:
    inp, out = PRICES.get(model, _FALLBACK_PRICE)
    # 캐시 읽기는 입력가의 약 1/10.
    billed_input = input_tokens + cache_read * 0.1
    return (billed_input * inp + output_tokens * out) / 1_000_000


class ClaudeClient:
    """구조화 출력 전용 얇은 래퍼. 스키마 밖 응답은 SDK 가 걸러준다.

    프롬프트 캐싱: 한 곡을 만드는 동안 시스템 프롬프트와 고정 컨텍스트(학생 프로필·
    콩쿨 규정·코퍼스 요약)는 **한 글자도 바뀌지 않는다**. 프레이즈마다 그것을 다시 과금할
    이유가 없으므로 `cache_control` 로 캐싱한다. 캐싱은 접두사 일치라서 순서가 중요하다 —
    system → 고정 컨텍스트 → 가변 요청 순으로 쌓고, 캐시 경계는 고정 컨텍스트 끝에 둔다.
    """

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

    @staticmethod
    def _system_blocks(system: str, fixed_context: str = "") -> list[dict[str, Any]]:
        """system 프롬프트 + 고정 컨텍스트를 캐시 대상으로 만든다.

        마지막 블록에만 `cache_control` 을 단다 — 그 지점까지가 캐시 접두사다.
        가변 내용(이번 프레이즈의 요청)은 user 메시지로 가므로 캐시를 깨지 않는다.
        """
        blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
        if fixed_context:
            blocks.append({"type": "text", "text": fixed_context})
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
        return blocks

    def _record(
        self, stage: str, model_id: str, usage: Any, started: float, *, batched: bool = False
    ) -> CallRecord:
        rec = CallRecord(
            stage=stage,
            model=model_id,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            batched=batched,
        )
        rec.cost_usd = estimate_cost(
            model_id, rec.input_tokens, rec.output_tokens, rec.cache_read_tokens
        )
        # 캐시 쓰기는 입력가의 약 1.25배로 한 번 더 과금된다.
        inp, _ = PRICES.get(model_id, _FALLBACK_PRICE)
        rec.cost_usd += rec.cache_write_tokens * inp * 1.25 / 1_000_000
        self.ledger.add(rec)
        log.info(
            "claude %s model=%s in=%d out=%d cache(r=%d,w=%d) %dms $%.4f (누적 $%.4f)",
            stage, model_id, rec.input_tokens, rec.output_tokens,
            rec.cache_read_tokens, rec.cache_write_tokens, rec.latency_ms,
            rec.cost_usd, self.ledger.total_usd,
        )
        return rec

    def parse(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        output_model: type[T],
        model: str | None = None,
        max_tokens: int = 16000,
        fixed_context: str = "",
    ) -> T:
        """구조화 출력 1회 호출. 결과는 검증된 Pydantic 인스턴스.

        `fixed_context` 는 곡 하나 동안 바뀌지 않는 내용(학생 프로필·콩쿨 규정·코퍼스 요약)이다.
        여기에 넣으면 캐시되어 프레이즈마다 다시 과금되지 않는다.
        """
        if not self.available:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 가 없다(프로젝트 .env 에서만 읽는다). "
                "오프라인에서는 StubComposerEngine 또는 SessionComposerEngine 을 쓴다."
            )
        self.ledger.check_before_call()
        model_id = model or self.settings.composer_model

        client = self._get_client()
        started = time.monotonic()
        try:
            response = client.messages.parse(
                model=model_id,
                max_tokens=max_tokens,
                system=self._system_blocks(system, fixed_context),
                messages=[{"role": "user", "content": user}],
                output_format=output_model,
            )
        except Exception as e:  # 키·잔액·네트워크 문제를 원장이 읽을 수 있는 말로 바꾼다
            reraise_friendly(e)
            raise
        self._record(stage, model_id, response.usage, started)

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise RuntimeError(f"{stage}: 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
        return parsed  # type: ignore[return-value]

    # ── Batch API ────────────────────────────────────────────────────────
    #
    # 연주회 일괄 생성(§6.14)처럼 **지금 당장 답이 필요 없는** 요청은 배치로 보내면
    # 절반 값이다. 반대로 작곡 파이프라인의 프레이즈 실현은 앞 프레이즈의 실제 음표를
    # 문맥으로 받아야 하므로 배치로 묶을 수 없다 — 순서가 곧 품질이기 때문이다.
    # 그래서 배치는 "서로 독립인 요청 여러 개" 에만 쓴다: 모티브 후보, 여러 학생의 Plan,
    # 해설·제목 같은 후처리.

    def parse_batch(
        self,
        items: list[tuple[str, str, str, type[BaseModel]]],
        *,
        model: str | None = None,
        max_tokens: int = 16000,
        fixed_context: str = "",
        poll_seconds: int = 20,
        timeout_seconds: int = 3600,
    ) -> dict[str, BaseModel]:
        """서로 독립인 구조화 출력 요청들을 Batch API 로 한 번에.

        items: (custom_id, system, user, output_model)
        결과는 custom_id → 파싱된 모델. 순서는 보장되지 않으므로 반드시 id 로 찾는다.
        """
        if not self.available:
            raise RuntimeError("ANTHROPIC_API_KEY 가 없다(프로젝트 .env 에서만 읽는다).")
        if not items:
            return {}
        self.ledger.check_before_call()

        model_id = model or self.settings.composer_model
        client = self._get_client()
        started = time.monotonic()

        requests = [
            {
                "custom_id": cid,
                "params": {
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "system": self._system_blocks(system, fixed_context),
                    "messages": [{"role": "user", "content": user}],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "schema": _strict_schema(out_model),
                        }
                    },
                },
            }
            for cid, system, user, out_model in items
        ]
        models = {cid: m for cid, _, _, m in items}

        try:
            batch = client.messages.batches.create(requests=requests)
            deadline = time.monotonic() + timeout_seconds
            while True:
                batch = client.messages.batches.retrieve(batch.id)
                if batch.processing_status == "ended":
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"배치 {batch.id} 가 {timeout_seconds}초 안에 끝나지 않았다")
                time.sleep(poll_seconds)
            results = list(client.messages.batches.results(batch.id))
        except Exception as e:  # 배치도 같은 이유로 실패한다 — 같은 말로 바꾼다
            reraise_friendly(e)
            raise

        out: dict[str, BaseModel] = {}
        for result in results:
            cid = result.custom_id
            if result.result.type != "succeeded":
                log.warning("배치 항목 실패 %s: %s", cid, result.result.type)
                continue
            message = result.result.message
            self._record(f"batch[{cid}]", model_id, message.usage, started, batched=True)
            text = next((b.text for b in message.content if b.type == "text"), "")
            out[cid] = models[cid].model_validate_json(text)
        return out


def _strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic 모델 → Structured Outputs 용 JSON Schema.

    `extra="forbid"` 로 선언한 모델은 additionalProperties=false 가 이미 들어간다.
    중첩 정의($defs)를 그대로 쓰되, 최상위에 누락된 경우만 채운다.
    """
    schema = model.model_json_schema()
    schema.setdefault("additionalProperties", False)
    return schema
