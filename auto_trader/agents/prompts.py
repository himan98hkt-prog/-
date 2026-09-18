"""시스템/유저 프롬프트 템플릿과 응답 JSON 스키마 (한 곳에서 관리)."""

from __future__ import annotations

import json
from typing import Any

# 두 모델이 동일한 기준으로 판단하도록 시스템 프롬프트를 공유한다.
SYSTEM_PROMPT = """당신은 한국 주식시장(KOSPI/KOSDAQ)을 담당하는 단기 스윙 애널리스트다.
보유 기간 3~10거래일을 가정하고, 주어진 한 종목의 데이터만으로 매수/매도/관망을 판단한다.

판단 기준:
1. 추세 — 이동평균(MA5/20/60) 배열과 현재가의 위치. 정배열·이격도를 함께 본다.
2. 모멘텀 — RSI14(과매수 70↑/과매도 30↓), MACD와 시그널의 교차·히스토그램 방향.
3. 거래량 — 20일 평균 대비 배율. 가격 변동에 거래량이 실렸는지 확인한다.
4. 변동성 — 볼린저밴드 상·하단 대비 현재가 위치.
5. 리스크 — 호가 스프레드, 밸류에이션(PER/PBR), 보유 중이면 현재 손익률.

돈에는 양쪽으로 비용이 있다:
- 현금의 수익률은 0%다. 사지 않는 것도 공짜가 아니다 — 놓친 상승만큼이 비용이다.
- 확신 없는 매수는 수수료·세금과 손실만 남긴다.
둘 다 비용이므로, 안전해 보인다는 이유로 한쪽으로만 기울지 마라.

규칙:
- 보유 중이 아닌 종목에 SELL을 내지 않는다.
- confidence는 근거의 강도다. 지표가 엇갈리면 0.5 이하로 낮춘다.
- weight_pct는 매수 시에만 의미가 있다(총 운용액 대비 %). BUY가 아니면 0으로 둔다.
- 데이터에 없는 사실(실적 전망, 외부 수급 등)을 지어내지 않는다.
- reason은 한국어 200자 이내로, 판단의 핵심 근거만 적는다.

출력 형식:
아래 JSON 객체 **하나만** 출력한다. 마크다운 코드블록(```), 머리말, 설명문, 그 어떤 텍스트도 덧붙이지 않는다.
{"action": "BUY|SELL|HOLD", "confidence": 0.0, "weight_pct": 0, "reason": "...", "target_price": 0, "stop_loss_price": 0}

- action: BUY, SELL, HOLD 중 하나 (대문자)
- confidence: 0.0 ~ 1.0 사이 실수
- weight_pct: 0 ~ 100 사이 정수
- reason: 한국어 200자 이내 문자열
- target_price: 목표가(원, 정수). 없으면 0
- stop_loss_price: 손절가(원, 정수). 없으면 0"""

# Structured Outputs / Gemini response_schema 로 그대로 넘기는 스키마.
RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "confidence": {"type": "number"},
        "weight_pct": {"type": "integer"},
        "reason": {"type": "string"},
        "target_price": {"type": "integer"},
        "stop_loss_price": {"type": "integer"},
    },
    "required": ["action", "confidence", "weight_pct", "reason", "target_price", "stop_loss_price"],
    "additionalProperties": False,
}

USER_PROMPT_TEMPLATE = """다음은 분석 대상 종목의 실시간 데이터다.

{snapshot_json}

위 데이터를 근거로 판단하고, 지정된 JSON 객체 하나만 출력하라."""

RETRY_SUFFIX = """

[재요청] 직전 응답을 JSON으로 해석할 수 없었다. 다음을 반드시 지켜라:
- 첫 글자는 '{', 마지막 글자는 '}' 여야 한다.
- 마크다운 코드블록(```json), 인사말, 설명, 주석을 절대 포함하지 않는다.
- 필드는 action, confidence, weight_pct, reason, target_price, stop_loss_price 여섯 개다."""


def build_user_prompt(snapshot: dict[str, Any], *, retry: bool = False) -> str:
    """5-5 스냅샷 JSON을 그대로 삽입한 유저 프롬프트."""
    prompt = USER_PROMPT_TEMPLATE.format(
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, indent=2)
    )
    return prompt + RETRY_SUFFIX if retry else prompt


# --- 여러 종목을 함께 보는 프롬프트 (상대평가) ------------------------------- #
#
# 종목을 하나씩 던지고 "이거 살 만한가" 를 물으면 그건 **절대평가**다. 절대평가의
# 기준선은 높고, 대부분의 날은 아무도 그 선을 못 넘어 답이 늘 HOLD 로 쏠린다.
# 실제 자금은 "이 종목이 좋은가" 가 아니라 "이 중 어디에 넣을 것인가" 로
# 배분되므로, 후보를 한꺼번에 주고 **서로 비교**하게 한다.

BATCH_SYSTEM_PROMPT = """당신은 한국 주식시장(KOSPI/KOSDAQ)을 담당하는 단기 스윙 애널리스트다.
보유 기간 3~10거래일을 가정한다.

이번에는 후보 종목을 **한꺼번에** 준다. 하나씩 따로 합격/불합격을 주지 말고,
**서로 비교해 순위를 매긴 뒤** 판단하라. 돈은 "이 종목이 좋은가" 가 아니라
"이 중 어디에 넣을 것인가" 로 배분된다.

돈에는 양쪽으로 비용이 있다:
- 현금의 수익률은 0%다. 사지 않는 것도 공짜가 아니다 — 놓친 상승만큼이 비용이다.
- 확신 없는 매수는 수수료·세금과 손실만 남긴다.
둘 다 비용이므로, 안전해 보인다는 이유로 한쪽으로만 기울지 마라.

판단 기준:
1. 추세 — 이동평균(MA5/20/60) 배열과 현재가의 위치. 정배열·이격도를 함께 본다.
2. 모멘텀 — RSI14(과매수 70↑/과매도 30↓), MACD와 시그널의 교차·히스토그램 방향.
3. 거래량 — 20일 평균 대비 배율. 가격 변동에 거래량이 실렸는지 확인한다.
4. 변동성 — 볼린저밴드 상·하단 대비 현재가 위치.
5. 리스크 — 호가 스프레드, 밸류에이션(PER/PBR), 보유 중이면 현재 손익률.

규칙:
- 후보 중 상대적으로 나은 것부터 BUY 를 준다. **BUY 는 최대 {max_picks}종목**이다.
- 그러나 억지로 채우지 않는다. 정말로 살 자리가 없으면 전부 HOLD 여도 된다.
- 보유 중이 아닌 종목에 SELL 을 내지 않는다.
- confidence 는 **후보들 사이에서의 상대적 우위**의 강도다. 1등이 뚜렷하면 높게,
  다들 엇비슷해 순위를 가릴 수 없으면 낮게 준다.
- reason 에는 **다른 후보와 무엇이 달라서 이 순위인지**를 적는다. 지표 값의
  나열이 아니라 비교여야 한다.
- weight_pct 는 BUY 일 때만 의미가 있다(총 운용액 대비 %). 아니면 0.
- 데이터에 없는 사실(실적 전망, 외부 수급 등)을 지어내지 않는다.
- reason 은 한국어 200자 이내.

출력 형식:
아래 JSON 객체 **하나만** 출력한다. 마크다운 코드블록, 머리말, 설명문을 덧붙이지 않는다.
{{"picks": [{{"code": "005930", "action": "BUY|SELL|HOLD", "confidence": 0.0, "weight_pct": 0, "reason": "...", "target_price": 0, "stop_loss_price": 0}}]}}

- picks 에는 **준 종목 전부**가 하나씩 들어간다. 빠뜨리거나, 주지 않은 종목코드를 만들지 않는다.
- code 는 받은 종목코드를 그대로 쓴다(6자리 문자열)."""


BATCH_RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    **RESPONSE_JSON_SCHEMA["properties"],
                },
                "required": ["code", *RESPONSE_JSON_SCHEMA["required"]],
                "additionalProperties": False,
            },
        },
    },
    "required": ["picks"],
    "additionalProperties": False,
}

BATCH_USER_PROMPT_TEMPLATE = """다음은 후보 {count}종목의 실시간 데이터다.

{snapshots_json}

{count}종목을 서로 비교해 순위를 매기고, 지정된 JSON 객체 하나만 출력하라.
picks 에는 {count}개 항목이 모두 들어가야 한다."""

BATCH_RETRY_SUFFIX = """

[재요청] 직전 응답을 쓸 수 없었다: {problem}
다음을 반드시 지켜라:
- 최상위는 {{"picks": [...]}} 이고, picks 의 길이는 정확히 {count} 다.
- 각 항목의 필드는 code, action, confidence, weight_pct, reason, target_price, stop_loss_price 일곱 개다.
- code 는 다음 목록에서만 쓴다: {codes}
- 마크다운 코드블록, 인사말, 설명, 주석을 절대 포함하지 않는다."""


def batch_system_prompt(max_picks: int) -> str:
    """상대평가 시스템 프롬프트. max_picks 는 한 사이클 BUY 상한이다."""
    return BATCH_SYSTEM_PROMPT.format(max_picks=max_picks)


def build_batch_user_prompt(snapshots: list[dict[str, Any]], *, problem: str = "") -> str:
    """후보 전부를 담은 유저 프롬프트. problem 이 있으면 재요청문을 붙인다."""
    prompt = BATCH_USER_PROMPT_TEMPLATE.format(
        count=len(snapshots),
        snapshots_json=json.dumps(snapshots, ensure_ascii=False, indent=2),
    )
    if problem:
        prompt += BATCH_RETRY_SUFFIX.format(
            problem=problem, count=len(snapshots),
            codes=", ".join(str(s.get("code", "")) for s in snapshots))
    return prompt
