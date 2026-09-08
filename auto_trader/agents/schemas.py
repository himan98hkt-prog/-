"""AI 판단 결과 모델과 응답 검증.

AI 응답을 신뢰할 수 없으면 기본 행동은 **항상 HOLD**다(절대 규칙 4).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Action = Literal["BUY", "SELL", "HOLD"]
VALID_ACTIONS: tuple[str, ...] = ("BUY", "SELL", "HOLD")

REASON_MAX_CHARS = 200
RAW_MAX_CHARS = 4000  # DB 저장용 원문 상한


class SchemaError(ValueError):
    """AI 응답이 요구 스키마를 만족하지 않음."""


@dataclass
class AgentDecision:
    agent: str  # "claude" | "gemini"
    action: Action = "HOLD"
    confidence: float = 0.0  # 0.0 ~ 1.0
    weight_pct: int = 0  # 0~100, 매수 시 권장 비중(총액 대비)
    reason: str = ""  # 200자 이내 한국어
    target_price: int | None = None
    stop_loss_price: int | None = None
    raw: str = ""  # 원문 응답 (디버깅용)
    ok: bool = False  # 파싱 성공 여부
    error: str = "" # 실패 사유 (로그·DB용)
    elapsed_sec: float = 0.0
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def hold(cls, agent: str, error: str, raw: str = "") -> "AgentDecision":
        """파싱·호출 실패 시의 안전한 기본값."""
        return cls(agent=agent, action="HOLD", confidence=0.0, weight_pct=0,
                   reason="응답을 신뢰할 수 없어 관망합니다", raw=raw[:RAW_MAX_CHARS],
                   ok=False, error=error)

    def summary(self) -> str:
        """알림·로그용 한 줄 요약."""
        if not self.ok:
            return f"{self.agent} 실패({self.error or '알 수 없음'}) → HOLD"
        return f"{self.agent} {self.action}({self.confidence:.2f})"


def _coerce_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"{field_name}: 숫자가 아닙니다 ({value!r})") from exc


def _coerce_optional_price(value: Any, field_name: str) -> int | None:
    """0·null·음수는 '지정 안 함'(None)으로 본다."""
    if value is None or value == "":
        return None
    try:
        price = int(float(value))
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"{field_name}: 숫자가 아닙니다 ({value!r})") from exc
    return price if price > 0 else None


def validate_payload(payload: Any, agent: str, raw: str = "") -> AgentDecision:
    """파싱된 JSON → 검증된 AgentDecision.

    범위를 벗어난 값은 잘라내고(clamp), 형식이 틀리면 `SchemaError`를 던진다.
    """
    if not isinstance(payload, dict):
        raise SchemaError(f"최상위가 객체가 아닙니다 ({type(payload).__name__})")

    action = str(payload.get("action", "")).strip().upper()
    if action not in VALID_ACTIONS:
        raise SchemaError(f"action: {list(VALID_ACTIONS)} 중 하나여야 합니다 ({payload.get('action')!r})")

    confidence = _coerce_float(payload.get("confidence", 0), "confidence")
    if confidence != confidence:  # NaN
        raise SchemaError("confidence: NaN")
    confidence = min(max(confidence, 0.0), 1.0)

    weight = _coerce_float(payload.get("weight_pct", 0), "weight_pct")
    weight_pct = int(min(max(weight, 0), 100))

    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise SchemaError("reason: 비어 있습니다")
    reason = reason[:REASON_MAX_CHARS]

    return AgentDecision(
        agent=agent,
        action=action,  # type: ignore[arg-type]
        confidence=round(confidence, 4),
        weight_pct=weight_pct,
        reason=reason,
        target_price=_coerce_optional_price(payload.get("target_price"), "target_price"),
        stop_loss_price=_coerce_optional_price(payload.get("stop_loss_price"), "stop_loss_price"),
        raw=raw[:RAW_MAX_CHARS],
        ok=True,
    )
