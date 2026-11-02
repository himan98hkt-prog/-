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


# 규칙 엔진(logic/rule_engine.py)을 **통과하는** 일봉.
#
# make_daily() 는 단조 상승이라 RSI 가 95를 넘는다 — 현실의 과열 종목이고,
# 규칙 엔진은 이것을 정확히 거부한다(rsi_overbought 75, rsi_sell 80). 그래서
# 매수 경로를 끝까지 보는 테스트는 '건강한 상승 추세' 데이터가 필요하다.
#
# 아래 상수는 임의로 고른 값이 아니라, 규칙 다섯 항목을 모두 충족하면서 각
# 임계치에서 가장 여유가 큰 조합을 수치 탐색으로 찾은 것이다
# (RSI 55.6 / 20일선 +0.61% / 볼린저 상단까지 -0.64% / MACD 히스토그램 +71).
# 임계치를 바꿔 e2e 테스트가 깨지면 test_healthy_daily_passes_the_rule_engine
# 이 먼저 알려 준다 — 그게 이 상수들의 존재 이유다.
HEALTHY = dict(n=60, base=70_000, drift=120, wave=3400, period=10.0, phase=5.498)


def make_healthy_daily(n: int = HEALTHY["n"], base: int = HEALTHY["base"],
                       drift: int = HEALTHY["drift"], wave: int = HEALTHY["wave"],
                       period: float = HEALTHY["period"], phase: float = HEALTHY["phase"],
                       volume: int = 1000) -> pd.DataFrame:
    """완만한 상승 + 등락이 섞인 일봉 — 규칙 엔진이 BUY 를 내는 모양."""
    import math

    dates = pd.bdate_range(end="2026-09-04", periods=n)
    closes = [round(base + drift * i + wave * math.sin(i / period + phase)) for i in range(n)]
    # 마지막 날만 거래량을 늘려 '거래량 20일평균 1.2배 이상' 가점을 만든다.
    volumes = [volume] * (n - 1) + [int(volume * 1.5)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 200 for c in closes],
            "high": [c + 300 for c in closes],
            "low": [c - 400 for c in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def healthy_quote(daily: pd.DataFrame | None = None) -> dict:
    """make_healthy_daily() 와 **앞뒤가 맞는** 현재가 응답.

    현재가를 일봉과 따로 두면 안 된다 — 76,000원처럼 볼린저 상단을 넘는 값이면
    규칙 엔진이 '상단 이탈' 로 막아 버리고, 테스트는 엉뚱한 곳에서 실패한다.
    """
    daily = make_healthy_daily() if daily is None else daily
    current = int(daily["close"].iloc[-1])
    previous = int(daily["close"].iloc[-2])
    return {
        "code": "005930", "name": "삼성전자", "current": current,
        "change_pct": round((current - previous) / previous * 100, 2),
        "change": current - previous,
        "open": current - 200, "high": current + 300, "low": current - 400,
        "volume": int(daily["volume"].iloc[-1]),
        "trade_amount": 0, "market_cap": 425_600_000_000_000, "per": 13.5, "pbr": 1.2,
        "upper_limit": 0, "lower_limit": 0,
    }


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
    snapshot = collect("005930", api, settings_obj,
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
    snapshot = collect("005930", api, settings_obj)
    assert snapshot["orderbook"] == {"bid_total": 0, "ask_total": 0, "spread_pct": 0.0}
    assert snapshot["price"]["current"] == 76000


def test_collect_includes_holding(settings_obj):
    api = StubApi()
    holding = Holding("005930", "삼성전자", 12, 12, 70000, 76000, 912000, 72000, 8.57)
    snapshot = collect("005930", api, settings_obj, holding=holding)
    assert snapshot["position"] == {"holding": True, "qty": 12, "avg_price": 70000.0, "pnl_pct": 8.57}


def test_collect_propagates_price_failure(settings_obj):
    class Broken(StubApi):
        def get_current_price(self, code):
            raise KisApiError("현재가 조회 실패")

    with pytest.raises(KisApiError):
        collect("005930", Broken(), settings_obj)


# --- 종목명이 비어 오는 경우 (모의투자에서 실제로 그렇다) -------------------- #

def test_falls_back_to_the_configured_name(settings_obj):
    """VTS 시세는 hts_kor_isnm 을 비워 보낼 때가 있다.

    그대로 두면 화면도 텔레그램도 "005930" 으로만 보여, 무엇을 샀는지 알 수 없다.
    """
    from dataclasses import replace

    from data_pipeline.market_data import collect

    api = StubApi(quote={**StubApi().quote, "name": ""})
    settings = replace(settings_obj, universe=replace(
        settings_obj.universe, names={"005930": "삼성전자"}))

    assert collect("005930", api, settings)["name"] == "삼성전자"


def test_a_real_name_always_wins(settings_obj):
    """시세가 이름을 보내 주면 그게 진실이다 — 설정이 낡았을 수 있다."""
    from dataclasses import replace

    from data_pipeline.market_data import collect

    api = StubApi(quote={**StubApi().quote, "name": "삼성전자"})
    settings = replace(settings_obj, universe=replace(
        settings_obj.universe, names={"005930": "옛이름"}))

    assert collect("005930", api, settings)["name"] == "삼성전자"


def test_an_unlisted_code_still_shows_something(settings_obj):
    from data_pipeline.market_data import collect

    api = StubApi(quote={**StubApi().quote, "name": ""})
    assert collect("999999", api, settings_obj)["name"] == "999999"


# --------------------------------------------------------------------------- #
# 규칙 엔진을 통과하는 테스트 데이터
# --------------------------------------------------------------------------- #


def test_make_daily_is_overbought_on_purpose():
    """make_daily() 는 단조 상승이라 과열이다 — 이걸로는 매수 경로를 못 본다.

    이 사실을 테스트로 적어 두는 이유: 누군가 e2e 테스트가 HOLD 로 떨어지는 걸
    보고 규칙 임계치를 의심하기 전에, 데이터가 원인이라는 걸 알게 하려는 것이다.
    """
    from logic.rule_engine import RulesConfig, evaluate

    indicators = compute_indicators(make_daily())
    assert indicators["rsi14"] > 95, "단조 상승이면 RSI 는 100에 수렴한다"

    verdict = evaluate(
        {"price": {"current": float(make_daily()["close"].iloc[-1]), "change_pct": 1.5,
                   "volume_ratio_20d": 1.0},
         "indicators": indicators, "orderbook": {"spread_pct": 0.14}},
        RulesConfig(),
    )
    assert verdict.action != "BUY", "과열 데이터인데 규칙 엔진이 매수를 냈습니다"


def test_healthy_daily_passes_the_rule_engine():
    """e2e 테스트가 쓰는 '건강한 상승 추세' 가 실제로 규칙을 통과하는지.

    tests/test_cycle_end_to_end.py 의 매수 경로 전체가 이 데이터에 기댄다.
    규칙 임계치(rules: 블록)를 바꿔서 e2e 가 깨졌다면, 이 테스트가 먼저 터져
    '임계치 때문' 이라고 알려 준다 — 그게 HEALTHY 상수를 수치 탐색으로 고정해
    둔 이유다.
    """
    from logic.rule_engine import RulesConfig, evaluate

    daily = make_healthy_daily()
    quote = healthy_quote(daily)
    indicators = compute_indicators(daily)
    verdict = evaluate(
        {"price": {"current": quote["current"], "change_pct": quote["change_pct"],
                   "volume_ratio_20d": volume_ratio_20d(daily, quote["volume"])},
         "indicators": indicators, "orderbook": {"spread_pct": 0.14}},
        RulesConfig(),
    )
    assert verdict.action == "BUY", (
        f"e2e 테스트 데이터가 규칙을 통과하지 못합니다: {verdict.reason} "
        f"(rsi={indicators['rsi14']:.1f}, 현재가={quote['current']}, "
        f"ma20={indicators['ma20']:.0f}, 볼린저상단={indicators['bb_upper']:.0f})"
    )
    assert verdict.buy_score == 5, verdict.passed
    assert not verdict.vetoes


def test_the_healthy_quote_agrees_with_its_daily_series():
    """현재가가 일봉과 어긋나면 엉뚱한 거부권(볼린저 상단 이탈)에 걸린다."""
    daily = make_healthy_daily()
    quote = healthy_quote(daily)
    assert quote["current"] == int(daily["close"].iloc[-1])
    assert quote["current"] < compute_indicators(daily)["bb_upper"]
