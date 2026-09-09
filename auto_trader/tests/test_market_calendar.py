"""장 운영일·운영시간 판단 테스트."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from trading import market_calendar as mc

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def holidays_file(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("2026-09-07   # 임시 휴장일\n\n# 주석만 있는 줄\nbad-line\n", encoding="utf-8")
    return path


def test_weekend_is_not_trading_day(holidays_file):
    assert mc.is_trading_day(date(2026, 9, 5), holidays_file) is False  # 토
    assert mc.is_trading_day(date(2026, 9, 6), holidays_file) is False  # 일


def test_holiday_from_file(holidays_file):
    assert mc.is_trading_day(date(2026, 9, 7), holidays_file) is False  # 파일에 있는 휴장일
    assert mc.is_trading_day(date(2026, 9, 8), holidays_file) is True


def test_missing_holiday_file_excludes_weekend_only(tmp_path):
    missing = tmp_path / "nope.txt"
    assert mc.load_holidays(missing) == frozenset()
    assert mc.is_trading_day(date(2026, 9, 7), missing) is True
    assert mc.is_trading_day(date(2026, 9, 5), missing) is False


@pytest.mark.parametrize(
    "moment,expected",
    [
        (datetime(2026, 9, 8, 8, 59, 59, tzinfo=KST), False),
        (datetime(2026, 9, 8, 9, 0, 0, tzinfo=KST), True),
        (datetime(2026, 9, 8, 12, 30, 0, tzinfo=KST), True),
        (datetime(2026, 9, 8, 15, 30, 0, tzinfo=KST), True),
        (datetime(2026, 9, 8, 15, 30, 1, tzinfo=KST), False),
    ],
)
def test_market_hours(moment, expected, holidays_file):
    assert mc.is_market_open(moment, holidays_file) is expected


def test_market_closed_on_holiday(holidays_file):
    assert mc.is_market_open(datetime(2026, 9, 7, 10, 0, tzinfo=KST), holidays_file) is False


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        mc.is_market_open(datetime(2026, 9, 8, 10, 0))


def test_market_state(holidays_file):
    assert mc.market_state(datetime(2026, 9, 7, 10, 0, tzinfo=KST), holidays_file) == "HOLIDAY"
    assert mc.market_state(datetime(2026, 9, 8, 8, 0, tzinfo=KST), holidays_file) == "PRE_OPEN"
    assert mc.market_state(datetime(2026, 9, 8, 10, 0, tzinfo=KST), holidays_file) == "OPEN"
    assert mc.market_state(datetime(2026, 9, 8, 16, 0, tzinfo=KST), holidays_file) == "CLOSED"


def test_is_before_last_new_buy():
    from datetime import time

    assert mc.is_before(time(14, 30), datetime(2026, 9, 8, 14, 0, tzinfo=KST)) is True
    assert mc.is_before(time(14, 30), datetime(2026, 9, 8, 14, 31, tzinfo=KST)) is False
