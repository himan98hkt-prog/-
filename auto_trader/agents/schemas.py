"""AI 판단 결과 모델과 응답 검증.

AI 응답을 신뢰할 수 없으면 기본 행동은 **항상 HOLD**다(절대 규칙 4).
"""

from __future__ import annotations

import json
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


def validate_batch_payload(payload: Any, agent: str, codes: list[str],
                           raw: str = "") -> dict[str, AgentDecision]:
    """상대평가 응답 `{"picks": [...]}` → 종목코드별 AgentDecision.

    빠진 종목이 하나라도 있으면 `SchemaError` 다. 조용히 HOLD 로 채우면
    "모델이 관망했다" 와 "모델이 빠뜨렸다" 가 구분되지 않는다 — 전자는 판단이고
    후자는 고장이다. 섞이면 합의 통계도, 엔진 적중률도 믿을 수 없게 된다.
    """
    if not isinstance(payload, dict):
        raise SchemaError(f"최상위가 객체가 아닙니다 ({type(payload).__name__})")

    picks = payload.get("picks")
    if not isinstance(picks, list):
        raise SchemaError("picks: 배열이 아닙니다")

    wanted = list(dict.fromkeys(codes))          # 순서 유지, 중복 제거
    decisions: dict[str, AgentDecision] = {}
    unknown: list[str] = []

    for index, item in enumerate(picks):
        if not isinstance(item, dict):
            raise SchemaError(f"picks[{index}]: 객체가 아닙니다")
        code = str(item.get("code", "")).strip()
        if not code:
            raise SchemaError(f"picks[{index}]: code 가 비어 있습니다")
        if code not in wanted:
            unknown.append(code)                 # 주지 않은 종목은 버린다
            continue
        if code in decisions:
            raise SchemaError(f"picks: {code} 가 두 번 나옵니다")
        # 항목 원문만 담는다 — 응답 전체를 종목 수만큼 복사하면 DB 가 비대해진다.
        decisions[code] = validate_payload(item, agent, json.dumps(item, ensure_ascii=False))

    missing = [code for code in wanted if code not in decisions]
    if missing:
        raise SchemaError(f"picks 에 빠진 종목: {', '.join(missing)}")
    if unknown:
        # 버리고 계속한다 — 요청한 종목이 다 왔다면 판단 자체는 쓸 수 있다.
        for decision in decisions.values():
            decision.error = f"목록에 없는 종목코드 무시: {', '.join(unknown)}"
    return decisions
