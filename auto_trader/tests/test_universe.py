"""유니버스 생성 테스트."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from data_pipeline.universe import build_universe, is_excluded
from trading.kis_api import Balance, Holding, KisApiError

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 7, 8, 30, tzinfo=KST)

KEYWORDS = ["스팩", "우", "ETN", "ETF"]


class StubApi:
    def __init__(self, ranked=None, error: bool = False):
        self.ranked = ranked or []
        self.error = error
        self.calls = 0

    def get_volume_rank(self, top_n):
        self.calls += 1
        if self.error:
            raise KisApiError("모의투자에서는 지원되지 않습니다")
        return self.ranked[:top_n]


def holding(code: str, qty: int = 10) -> Holding:
    return Holding(code, f"종목{code}", qty, qty, 70000, 71000, 710000, 10000, 1.4)


# --------------------------------------------------------------------------- #
# 제외 키워드
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name,expected",
    [
        ("삼성전자", False),
        ("삼성전자우", True),          # 우선주
        ("현대차2우B", True),
        ("우리금융지주", False),        # '우'로 시작할 뿐 우선주가 아님
        ("교보7호스팩", True),
        ("KODEX 200 ETF", True),
        ("TIGER 원유선물 ETN", True),
        ("", False),
    ],
)
def test_is_excluded(name, expected):
    assert is_excluded(name, KEYWORDS) is expected


# --------------------------------------------------------------------------- #
# watchlist 모드
# --------------------------------------------------------------------------- #


def test_watchlist_mode_uses_yaml_list(settings_obj, tmp_path):
    codes = build_universe(StubApi(), settings_obj, now=NOW)
    assert codes == settings_obj.universe.watchlist
    saved = json.loads((tmp_path / "universe_20260907.json").read_text(encoding="utf-8"))
    assert saved["source"] == "watchlist"
    assert saved["codes"] == codes


def test_holdings_always_included_and_first(settings_obj):
    balance = Balance(holdings=[holding("068270"), holding("005930")])
    codes = build_universe(StubApi(), settings_obj, balance=balance, save=False, now=NOW)

    assert codes[0] == "068270", "보유 종목이 앞에 와야 합니다"
    assert "005930" in codes
    assert codes.count("005930") == 1, "중복되면 안 됩니다"
    assert set(settings_obj.universe.watchlist) <= set(codes)


def test_zero_quantity_holding_is_not_included(settings_obj):
    balance = Balance(holdings=[holding("068270", qty=0)])
    codes = build_universe(StubApi(), settings_obj, balance=balance, save=False, now=NOW)
    assert "068270" not in codes


def test_candidate_cap_applies_to_candidates_only(settings_obj):
    settings_obj.universe.watchlist.extend(["068270", "051910", "006400", "105560", "055550", "012330"])
    object.__setattr__(settings_obj.universe, "max_candidates_per_cycle", 3)
    balance = Balance(holdings=[holding("373220")])

    codes = build_universe(StubApi(), settings_obj, balance=balance, save=False, now=NOW)
    assert codes[0] == "373220"
    assert len(codes) == 4, "보유 1 + 후보 상한 3"


# --------------------------------------------------------------------------- #
# volume_rank 모드
# --------------------------------------------------------------------------- #


def _ranked_rows():
    return [
        {"code": "005930", "name": "삼성전자", "price": 71300, "volume": 100, "rank": 1, "change_pct": 1.0},
        {"code": "005935", "name": "삼성전자우", "price": 60000, "volume": 90, "rank": 2, "change_pct": 0.5},
        {"code": "069500", "name": "KODEX 200 ETF", "price": 40000, "volume": 80, "rank": 3, "change_pct": 0.2},
        {"code": "900110", "name": "동전주식", "price": 800, "volume": 70, "rank": 4, "change_pct": 5.0},
        {"code": "000660", "name": "SK하이닉스", "price": 170000, "volume": 60, "rank": 5, "change_pct": -1.0},
    ]


def test_volume_rank_filters_keywords_and_penny_stocks(settings_obj):
    object.__setattr__(settings_obj.universe, "mode", "volume_rank")
    codes = build_universe(StubApi(_ranked_rows()), settings_obj, save=False, now=NOW)
    assert codes == ["005930", "000660"], "우선주·ETF·동전주 제외"


def test_volume_rank_falls_back_to_watchlist_on_vts(settings_obj, tmp_path):
    object.__setattr__(settings_obj.universe, "mode", "volume_rank")
    api = StubApi(error=True)  # 모의투자에서 미지원
    codes = build_universe(api, settings_obj, now=NOW)

    assert api.calls == 1
    assert codes == settings_obj.universe.watchlist
    saved = json.loads((tmp_path / "universe_20260907.json").read_text(encoding="utf-8"))
    assert saved["source"] == "watchlist(fallback)"


def test_universe_file_records_holdings(settings_obj, tmp_path):
    balance = Balance(holdings=[holding("068270")])
    build_universe(StubApi(), settings_obj, balance=balance, now=NOW)
    saved = json.loads((tmp_path / "universe_20260907.json").read_text(encoding="utf-8"))
    assert saved["holdings"] == ["068270"]
    assert saved["generated_at"].startswith("2026-09-07T08:30")
