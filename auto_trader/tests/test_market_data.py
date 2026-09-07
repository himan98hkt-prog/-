"""지표 계산·스냅샷 스키마 테스트 (KIS 호출은 mock)."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from data_pipeline.market_data import (
    build_position,
    collect,
    compute_indicators,
    volume_ratio_20d,
)
from trading.kis_api import Holding, KisApiError

KST = ZoneInfo("Asia/Seoul")


def make_daily(n: int = 60, start: int = 70000, step: int = 100, volume: int = 1000) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-09-04", periods=n)
    closes = [start + step * i for i in range(n)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 200 for c in closes],
            "high": [c + 300 for c in closes],
            "low": [c - 400 for c in closes],
            "close": closes,
            "volume": [volume] * n,
        }
    )


class StubApi:
    """KisApi 대역 — 지정한 응답만 돌려준다."""

    def __init__(self, quote=None, daily=None, book=None, book_error=False):
        self.quote = quote or {
            "code": "005930", "name": "삼성전자", "current": 76000, "change_pct": 1.5,
            "change": 1100, "open": 75000, "high": 76500, "low": 74800, "volume": 3000,
            "trade_amount": 0, "market_cap": 425_600_000_000_000, "per": 13.5, "pbr": 1.2,
            "upper_limit": 0, "lower_limit": 0,
        }
        self.daily = make_daily() if daily is None else daily
        self.book = book or {"bid_total": 100, "ask_total": 50, "spread_pct": 0.14,
                             "best_ask": 76100, "best_bid": 76000, "asks": [], "bids": []}
        self.book_error = book_error

    def get_current_price(self, code):
        return {**self.quote, "code": code}

    def get_daily_ohlcv(self, code, days=60):
        return self.daily.tail(days).reset_index(drop=True)

    def get_orderbook(self, code):
        if self.book_error:
            raise KisApiError("호가 조회 실패")
        return self.book


# --------------------------------------------------------------------------- #
# 지표
# --------------------------------------------------------------------------- #


def test_indicators_match_reference_values():
    """상승 추세 데이터에서 ta 라이브러리 결과와 직접 계산이 일치해야 한다."""
    df = make_daily(n=60)
    indicators = compute_indicators(df)
    closes = pd.Series(df["close"], dtype="float64")

    assert indicators["ma5"] == pytest.approx(closes.tail(5).mean(), abs=0.01)
    assert indicators["ma20"] == pytest.approx(closes.tail(20).mean(), abs=0.01)
    assert indicators["ma60"] == pytest.approx(closes.tail(60).mean(), abs=0.01)
    # 단조 상승이면 RSI는 100에 수렴하고 MACD 히스토그램은 양수
    assert indicators["rsi14"] > 95
    assert indicators["macd"] > 0
    assert indicators["bb_upper"] > indicators["bb_lower"] > 0


def test_indicators_on_short_history_are_zero_not_error():
    df = make_daily(n=8)
    indicators = compute_indicators(df)
    assert indicators["ma5"] > 0, "5일선은 계산 가능"
    assert indicators["ma20"] == 0.0
    assert indicators["ma60"] == 0.0
    assert indicators["rsi14"] == 0.0
    assert indicators["macd"] == 0.0


def test_indicators_on_empty_dataframe():
    empty = pd.DataFrame({"close": pd.Series(dtype="float64"), "volume": pd.Series(dtype="float64")})
    indicators = compute_indicators(empty)
    assert set(indicators) == {"ma5", "ma20", "ma60", "rsi14", "macd", "macd_signal",
                               "macd_hist", "bb_upper", "bb_lower"}
    assert all(value == 0.0 for value in indicators.values())


def test_nan_indicator_becomes_zero():
    """RSI 계산이 NaN을 내도 JSON 직렬화가 되도록 0.0으로 접힌다."""
    df = make_daily(n=30, step=0)  # 변동 없음 → RSI NaN 가능
    indicators = compute_indicators(df)
    assert json.dumps(indicators)  # 직렬화 성공
    assert indicators["rsi14"] == indicators["rsi14"]  # NaN 아님


def test_volume_ratio_uses_previous_20_days():
    df = make_daily(n=40, volume=1000)
    assert volume_ratio_20d(df, 2000) == pytest.approx(2.0)
    assert volume_ratio_20d(df, 500) == pytest.approx(0.5)


def test_volume_ratio_handles_no_history():
    df = make_daily(n=1)
    assert volume_ratio_20d(df, 1000) == 0.0


# --------------------------------------------------------------------------- #
# 포지션
# --------------------------------------------------------------------------- #


def test_build_position_when_not_holding():
    assert build_position(None, 70000) == {"holding": False, "qty": 0, "avg_price": 0, "pnl_pct": 0}


def test_build_position_uses_broker_pnl():
    holding = Holding("005930", "삼성전자", 10, 10, 70000, 71400, 714000, 14000, 2.0)
    position = build_position(holding, 71400)
    assert position == {"holding": True, "qty": 10, "avg_price": 70000.0, "pnl_pct": 2.0}


def test_build_position_computes_pnl_when_missing():
    holding = Holding("005930", "삼성전자", 10, 10, 70000, 0, 0, 0, 0.0)
    position = build_position(holding, 77000)
    assert position["pnl_pct"] == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# 스냅샷
# --------------------------------------------------------------------------- #


def test_collect_matches_fixed_schema(settings_obj):
    api = StubApi()
    snapshot = collect("005930", api, settings_obj, with_news=False,
                       now=datetime(2026, 9, 7, 9, 35, tzinfo=KST))

    assert snapshot["code"] == "005930"
    assert snapshot["name"] == "삼성전자"
    assert snapshot["timestamp"] == "2026-09-07T09:35:00+09:00"
    assert snapshot["price"]["current"] == 76000
    assert snapshot["price"]["volume_ratio_20d"] == pytest.approx(3.0)
    assert snapshot["valuation"]["per"] == 13.5
    assert snapshot["orderbook"]["bid_total"] == 100
    assert len(snapshot["recent_closes_20d"]) == 20
    assert snapshot["position"]["holding"] is False
    assert snapshot["news"] == []
    assert json.dumps(snapshot, ensure_ascii=False)  # AI 프롬프트에 그대로 들어가야 함


def test_collect_survives_orderbook_failure(settings_obj):
    api = StubApi(book_error=True)
    snapshot = collect("005930", api, settings_obj, with_news=False)
    assert snapshot["orderbook"] == {"bid_total": 0, "ask_total": 0, "spread_pct": 0.0}
    assert snapshot["price"]["current"] == 76000


def test_collect_includes_holding(settings_obj):
    api = StubApi()
    holding = Holding("005930", "삼성전자", 12, 12, 70000, 76000, 912000, 72000, 8.57)
    snapshot = collect("005930", api, settings_obj, holding=holding, with_news=False)
    assert snapshot["position"] == {"holding": True, "qty": 12, "avg_price": 70000.0, "pnl_pct": 8.57}


def test_collect_propagates_price_failure(settings_obj):
    class Broken(StubApi):
        def get_current_price(self, code):
            raise KisApiError("현재가 조회 실패")

    with pytest.raises(KisApiError):
        collect("005930", Broken(), settings_obj, with_news=False)
