"""규칙 엔진 — AI 판단을 교차검증하는 **결정론적** 정량 게이트.

왜 LLM 을 하나 더 두지 않고 규칙을 쓰는가:

여러 LLM 의 합의는 생각보다 약한 검증이다. 모델들은 같은 종류의 입력(가격·뉴스·
지표를 서술한 텍스트)을 받고 같은 종류의 편향을 공유한다 — 최근성 편향, 설득력
있는 서술에 끌리는 성향, 강세 쪽으로 기우는 경향. 오류가 **서로 상관**되어 있어
셋이 동의하고 셋이 같이 틀릴 수 있다. 대신 만장일치 요구는 매수 기회를 극단적으로
깎아낸다.

규칙 엔진은 LLM 과 **틀리는 방식이 다르다.** 숫자만 보고, 뉴스에 설득되지 않으며,
같은 입력에 늘 같은 답을 낸다. 그리고 API 호출이 없으므로:

* 비용이 0이다.
* 쿼터·인증·네트워크 때문에 죽지 않는다 — 지금까지 매매를 멈춰 세운 장애
  (Gemini 429, Claude 401, 연결 타임아웃)가 이 경로에는 존재하지 않는다.
* 왜 막혔는지 로그로 정확히 재현할 수 있다.

구조는 두 층이다.

**거부권(veto)** — 하나라도 걸리면 그 종목은 매수 대상에서 빠진다. 과열·급등 추격·
유동성 부족·장기추세 이탈처럼 "들어가면 안 되는 자리" 를 막는다. 점수로 상쇄되지
않는다 — 가점이 아무리 높아도 거부권이 이긴다.

**점수(score)** — 추세·모멘텀·거래량이 매수에 우호적인지 센다. 매수 쪽 가점과
매도 쪽 감점을 따로 세고, 각각 임계치를 넘으면 BUY / SELL 을 낸다.

지표가 0.0 이면 **데이터 부족**이다(data_pipeline 이 NaN 을 0.0 으로 접는다).
0.0 을 실제 값으로 읽으면 `현재가 > ma20` 이 늘 참이 되어 규칙이 거꾸로 돈다.
그래서 모든 비교는 0보다 큰지를 먼저 확인하고, 핵심 지표가 없으면 매수를 막는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RuleAction = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class RulesConfig:
    """규칙 임계치. settings.yaml 의 `rules:` 블록으로 덮어쓸 수 있다."""

    enabled: bool = True

    # --- 거부권 --------------------------------------------------------- #
    rsi_overbought: float = 75.0     # 이 이상이면 과열 → 매수 금지
    max_chase_pct: float = 8.0       # 당일 상승률이 이 이상이면 추격매수 금지
    max_spread_pct: float = 1.0      # 호가 스프레드가 이 이상이면 유동성 부족
    trend_break_pct: float = 5.0     # ma60 을 이 %만큼 밑돌면 장기추세 이탈
    block_above_band: bool = True    # 볼린저 상단 이탈 시 매수 금지

    # --- 매수 가점 ------------------------------------------------------ #
    rsi_buy_low: float = 40.0        # 건강한 RSI 구간 하한
    rsi_buy_high: float = 65.0       # 건강한 RSI 구간 상한
    vol_surge: float = 1.2           # 20일 평균 대비 거래량 배수
    buy_score_min: int = 3           # BUY 를 내기 위한 최소 가점 (만점 5)

    # --- 매도 감점 ------------------------------------------------------ #
    rsi_sell: float = 80.0           # 이 이상이면 단독으로 매도 신호
    sell_score_min: int = 2          # SELL 을 내기 위한 최소 감점 (만점 3)


@dataclass
class RuleVerdict:
    """규칙 엔진의 판정. AgentDecision 과 **별개 타입**이다.

    합의 로직에서 AI 판단과 섞이지 않게 하려고 일부러 다른 모양을 쓴다 —
    같은 타입이면 "AI 가 둘" 로 세어져 비대칭 설계가 무너진다.
    """

    action: RuleAction = "HOLD"
    buy_score: int = 0
    sell_score: int = 0
    vetoes: list[str] = field(default_factory=list)   # 매수를 막은 사유(사람이 읽는 문장)
    passed: list[str] = field(default_factory=list)   # 충족한 매수 가점
    negatives: list[str] = field(default_factory=list)  # 충족한 매도 감점
    reason: str = ""
    evaluated: bool = True   # False = 규칙 엔진을 끈 상태(교차검증 없음)

    @property
    def blocks_buy(self) -> bool:
        """거부권이 하나라도 있으면 매수를 막는다."""
        return bool(self.vetoes)

    @property
    def score(self) -> int:
        """화면 표시용 순점수."""
        return self.buy_score - self.sell_score

    def summary(self) -> str:
        if not self.evaluated:
            return "규칙 OFF"
        # 매도 판정이 거부권보다 먼저다. RSI 85 처럼 '과열 거부권' 과 '극단 과열
        # 매도 신호' 가 동시에 서는 자리가 있는데, 거부권을 먼저 보고하면 실제로는
        # 팔고 있는데 화면에는 "매수 차단" 이라고 적힌다.
        if self.action == "SELL":
            head = self.negatives[0] if self.negatives else self.reason
            return f"규칙 SELL: {head}"
        if self.vetoes:
            return f"규칙 차단({len(self.vetoes)}): {self.vetoes[0]}"
        return f"규칙 {self.action}({self.score:+d})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "score": self.score,
            "vetoes": list(self.vetoes),
            "passed": list(self.passed),
            "negatives": list(self.negatives),
            "reason": self.reason,
            "evaluated": self.evaluated,
        }


def _number(source: Any, key: str) -> float:
    """dict 에서 숫자를 꺼낸다. 없거나 숫자가 아니면 0.0."""
    if not isinstance(source, dict):
        return 0.0
    try:
        value = float(source.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if value != value else value   # NaN 차단


def _known(value: float) -> bool:
    """지표가 실제로 계산된 값인지. 0.0 은 '데이터 부족' 이다."""
    return value > 0.0


def evaluate(snapshot: dict[str, Any], config: RulesConfig | None = None) -> RuleVerdict:
    """종목 스냅샷 → 규칙 판정.

    Args:
        snapshot: data_pipeline.market_data.collect() 가 만든 딕셔너리.
        config: 임계치. None 이면 기본값.
    """
    config = config or RulesConfig()
    if not config.enabled:
        return RuleVerdict(action="HOLD", reason="규칙 엔진이 꺼져 있습니다", evaluated=False)

    price = snapshot.get("price") if isinstance(snapshot, dict) else None
    indicators = snapshot.get("indicators") if isinstance(snapshot, dict) else None
    book = snapshot.get("orderbook") if isinstance(snapshot, dict) else None

    current = _number(price, "current")
    change_pct = _number(price, "change_pct")
    # 거래량은 절대값이 아니라 20일 평균 대비 배수로 본다 — 종목마다 규모가 달라
    # 절대값으로는 비교가 되지 않는다. data_pipeline 이 이미 계산해 둔다.
    volume_ratio = _number(price, "volume_ratio_20d")

    ma5 = _number(indicators, "ma5")
    ma20 = _number(indicators, "ma20")
    ma60 = _number(indicators, "ma60")
    rsi = _number(indicators, "rsi14")
    macd_hist = _number(indicators, "macd_hist")
    bb_upper = _number(indicators, "bb_upper")

    spread_pct = _number(book, "spread_pct")

    vetoes: list[str] = []
    passed: list[str] = []
    negatives: list[str] = []

    # ------------------------------------------------------------------ #
    # 거부권 — 매수하면 안 되는 자리
    # ------------------------------------------------------------------ #
    if not _known(current):
        vetoes.append("현재가를 읽지 못했습니다")
    if not _known(ma20) or not _known(rsi):
        # 지표 없이 매수하면 교차검증이 통째로 사라진다. AI 혼자 판단하게 두지 않는다.
        vetoes.append("지표 데이터 부족(ma20·RSI 미계산)")

    if _known(rsi) and rsi >= config.rsi_overbought:
        vetoes.append(f"RSI {rsi:.0f} 과열(≥{config.rsi_overbought:.0f})")

    if change_pct >= config.max_chase_pct:
        vetoes.append(f"당일 +{change_pct:.1f}% 급등 추격(≥{config.max_chase_pct:.0f}%)")

    if spread_pct >= config.max_spread_pct:
        vetoes.append(f"호가 스프레드 {spread_pct:.2f}% 과대(≥{config.max_spread_pct:.1f}%)")

    if config.block_above_band and _known(bb_upper) and _known(current) and current > bb_upper:
        vetoes.append(f"볼린저 상단 이탈({current:,.0f} > {bb_upper:,.0f})")

    if _known(ma60) and _known(current):
        floor_price = ma60 * (1 - config.trend_break_pct / 100)
        if current < floor_price:
            vetoes.append(
                f"60일선 {config.trend_break_pct:.0f}% 이상 하회(장기추세 이탈)")

    # ------------------------------------------------------------------ #
    # 매수 가점 (만점 5)
    # ------------------------------------------------------------------ #
    if _known(ma20) and _known(current) and current > ma20:
        passed.append("20일선 상회")
    if _known(ma5) and _known(ma20) and ma5 > ma20:
        passed.append("5일선 > 20일선")
    if macd_hist > 0:
        passed.append("MACD 히스토그램 양전")
    if _known(rsi) and config.rsi_buy_low <= rsi <= config.rsi_buy_high:
        passed.append(f"RSI {rsi:.0f} 건강구간")
    if _known(volume_ratio) and volume_ratio >= config.vol_surge:
        passed.append(f"거래량 20일평균 {volume_ratio:.1f}배")

    # ------------------------------------------------------------------ #
    # 매도 감점 (만점 3)
    # ------------------------------------------------------------------ #
    # 극단 과열은 그 자체로 이탈 신호다 — 점수를 채우는 대신 따로 표시해
    # 단독 성립시킨다. 가짜 감점을 끼워 넣으면 사유 문장과 점수가 둘 다 더럽혀진다.
    strong_sell = _known(rsi) and rsi >= config.rsi_sell
    if strong_sell:
        negatives.append(f"RSI {rsi:.0f} 극단 과열(≥{config.rsi_sell:.0f})")
    if _known(ma20) and _known(current) and current < ma20:
        negatives.append("20일선 하회")
    if macd_hist < 0:
        negatives.append("MACD 히스토그램 음전")

    buy_score = len(passed)
    sell_score = len(negatives)

    # ------------------------------------------------------------------ #
    # 판정 — 매도를 먼저 본다(자산을 지키는 쪽으로 기운 비대칭)
    # ------------------------------------------------------------------ #
    if strong_sell or sell_score >= config.sell_score_min:
        reason = f"이탈 신호 {sell_score}개: {', '.join(negatives)}"
        action: RuleAction = "SELL"
    elif vetoes:
        reason = f"매수 차단: {', '.join(vetoes)}"
        action = "HOLD"
    elif buy_score >= config.buy_score_min:
        reason = f"매수 우호 {buy_score}/5: {', '.join(passed)}"
        action = "BUY"
    else:
        shortfall = config.buy_score_min - buy_score
        detail = ", ".join(passed) if passed else "충족 항목 없음"
        reason = f"매수 근거 부족 {buy_score}/{config.buy_score_min} ({detail}) — {shortfall}개 부족"
        action = "HOLD"

    return RuleVerdict(
        action=action,
        buy_score=buy_score,
        sell_score=sell_score,
        vetoes=vetoes,
        passed=passed,
        negatives=negatives,
        reason=reason,
    )
