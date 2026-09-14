"""종목별 시세·지표·뉴스를 모아 AI에 넘길 스냅샷(고정 스키마)을 만든다.

지표는 전부 `ta` 라이브러리로 계산한다(직접 구현 금지).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

from config.loader import Settings
from trading.kis_api import Holding, KisApi, KisApiError
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("market_data")

DAILY_LOOKBACK_DAYS = 60
RECENT_CLOSES = 20
VOLUME_AVG_WINDOW = 20


def _round(value: Any, digits: int = 2) -> float:
    """NaN·None을 0.0으로 접어 JSON 직렬화가 항상 되게 한다."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return round(number, digits)


def compute_indicators(df: pd.DataFrame) -> dict[str, float]:
    """일봉 DataFrame → 지표 딕셔너리.

    데이터가 지표 기간보다 짧으면 해당 지표는 0.0으로 남는다(에러 없이).
    """
    close = pd.Series(df["close"], dtype="float64")
    indicators: dict[str, float] = {
        "ma5": 0.0, "ma20": 0.0, "ma60": 0.0, "rsi14": 0.0,
        "macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
        "bb_upper": 0.0, "bb_lower": 0.0,
    }
    if close.empty:
        return indicators

    for window in (5, 20, 60):
        if len(close) >= window:
            sma = SMAIndicator(close=close, window=window, fillna=False).sma_indicator()
            indicators[f"ma{window}"] = _round(sma.iloc[-1])

    if len(close) >= 15:
        indicators["rsi14"] = _round(RSIIndicator(close=close, window=14, fillna=False).rsi().iloc[-1])

    if len(close) >= 26:
        macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9, fillna=False)
        indicators["macd"] = _round(macd.macd().iloc[-1], 3)
        indicators["macd_signal"] = _round(macd.macd_signal().iloc[-1], 3)
        indicators["macd_hist"] = _round(macd.macd_diff().iloc[-1], 3)

    if len(close) >= 20:
        bands = BollingerBands(close=close, window=20, window_dev=2, fillna=False)
        indicators["bb_upper"] = _round(bands.bollinger_hband().iloc[-1])
        indicators["bb_lower"] = _round(bands.bollinger_lband().iloc[-1])

    return indicators


def volume_ratio_20d(df: pd.DataFrame, current_volume: int) -> float:
    """당일 거래량 / 최근 20일 평균 거래량 (배)."""
    volumes = pd.Series(df["volume"], dtype="float64")
    # 당일 봉이 이미 들어 있으면 제외하고 평균을 낸다.
    history = volumes.iloc[-(VOLUME_AVG_WINDOW + 1) : -1] if len(volumes) > VOLUME_AVG_WINDOW else volumes.iloc[:-1]
    if history.empty:
        return 0.0
    average = float(history.mean())
    if average <= 0:
        return 0.0
    return _round(current_volume / average)


def build_position(holding: Holding | None, current_price: int) -> dict[str, Any]:
    """보유 정보 블록. 미보유면 holding=False."""
    if holding is None or holding.qty <= 0:
        return {"holding": False, "qty": 0, "avg_price": 0, "pnl_pct": 0}
    pnl_pct = holding.pnl_pct
    if not pnl_pct and holding.avg_price > 0 and current_price > 0:
        pnl_pct = (current_price - holding.avg_price) / holding.avg_price * 100
    return {
        "holding": True,
        "qty": holding.qty,
        "avg_price": _round(holding.avg_price, 0),
        "pnl_pct": _round(pnl_pct),
    }


def collect(
    code: str,
    api: KisApi,
    settings: Settings,
    *,
    holding: Holding | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """한 종목의 현재가·일봉·호가·지표·뉴스를 모아 스냅샷을 만든다.

    호가와 뉴스는 실패해도 기본값으로 채우고 진행한다(매매 판단을 막지 않는다).
    현재가·일봉 실패는 `KisApiError`로 전파한다 — 판단 근거가 없기 때문.
    """
    timestamp = now or datetime.now(KST)

    quote = api.get_current_price(code)
    daily = api.get_daily_ohlcv(code, days=DAILY_LOOKBACK_DAYS)

    try:
        book = api.get_orderbook(code)
    except KisApiError as exc:
        logger.warning("%s 호가 조회 실패(%s) — 기본값으로 진행합니다", code, exc)
        book = {"bid_total": 0, "ask_total": 0, "spread_pct": 0.0}

    name = quote["name"] or code
    # 뉴스는 수집하지 않는다. 유일한 출처였던 네이버 검색 API 가 2026-07-31 부로
    # 신규 발급을 닫았고, 2026-09-07 시행 약관이 결과를 AI 에 입력하는 것을
    # 금지한다. 판단은 기술적 지표만으로 한다.
    news: list[dict[str, Any]] = []

    closes = [int(value) for value in daily["close"].tail(RECENT_CLOSES).tolist()]

    return {
        "code": code,
        "name": name,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "price": {
            "current": quote["current"],
            "change_pct": _round(quote["change_pct"]),
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "volume": quote["volume"],
            "volume_ratio_20d": volume_ratio_20d(daily, quote["volume"]),
        },
        "valuation": {
            "market_cap": quote["market_cap"],
            "per": _round(quote["per"]),
            "pbr": _round(quote["pbr"]),
        },
        "indicators": compute_indicators(daily),
        "orderbook": {
            "bid_total": book.get("bid_total", 0),
            "ask_total": book.get("ask_total", 0),
            "spread_pct": _round(book.get("spread_pct", 0.0), 4),
        },
        "recent_closes_20d": closes,
        "position": build_position(holding, quote["current"]),
        "news": news,
    }
