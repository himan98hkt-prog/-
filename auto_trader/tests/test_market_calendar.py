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


# --- 휴장일 달력이 낡았는지 ---------------------------------------------------- #
#
# 이 파일은 해마다 사람이 채워 넣어야 하는데, 비어 있어도 코드는 멀쩡히 돈다.
# 그래서 아무도 모르는 채 추석에 주문을 내고 거부 알림만 쌓였다. 여기서 그걸 잡는다.

def test_next_trading_day_jumps_the_chuseok_break(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("2026-09-24\n2026-09-25\n", encoding="utf-8")
    # 9/23(수) 다음 거래일은 목·금이 추석이고 토·일이 주말이라 9/28(월)이다.
    assert mc.next_trading_day(date(2026, 9, 23), path) == date(2026, 9, 28)


def test_next_trading_day_skips_the_weekend(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("", encoding="utf-8")
    assert mc.next_trading_day(date(2026, 9, 18), path) == date(2026, 9, 21)  # 금 → 월


def test_upcoming_holidays_ignores_weekend_ones(tmp_path):
    """토요일 휴장일을 알려 봐야 소용없다 — 어차피 주말이라 쉰다."""
    path = tmp_path / "holidays.txt"
    path.write_text("2026-10-03\n2026-10-05\n2026-10-09\n", encoding="utf-8")
    now = datetime(2026, 10, 1, 9, 0, tzinfo=KST)
    assert mc.upcoming_holidays(now=now, holidays_path=path) == [
        date(2026, 10, 5), date(2026, 10, 9),
    ]


def test_calendar_with_room_left_is_ok(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("2026-12-25\n2026-12-31\n", encoding="utf-8")
    health = mc.calendar_health(now=datetime(2026, 9, 20, tzinfo=KST), holidays_path=path)
    assert health["state"] == "ok"
    assert health["covered_until"] == date(2026, 12, 31)
    assert health["message"] == ""


def test_calendar_running_out_says_so(tmp_path):
    """연말에 다음 해를 안 채우면 1월 1일에 조용히 틀린다 — 미리 말해야 한다."""
    path = tmp_path / "holidays.txt"
    path.write_text("2026-12-25\n2026-12-31\n", encoding="utf-8")
    health = mc.calendar_health(now=datetime(2026, 12, 20, tzinfo=KST), holidays_path=path)
    assert health["state"] == "stale"
    assert "config/holidays.txt" in health["message"]


def test_empty_calendar_is_stale_not_ok(tmp_path):
    path = tmp_path / "holidays.txt"
    path.write_text("# 주석뿐\n", encoding="utf-8")
    health = mc.calendar_health(now=datetime(2026, 9, 20, tzinfo=KST), holidays_path=path)
    assert health["state"] == "stale"


def test_missing_calendar_file_is_reported(tmp_path):
    health = mc.calendar_health(now=datetime(2026, 9, 20, tzinfo=KST),
                                holidays_path=tmp_path / "nope.txt")
    assert health["state"] == "missing"


# --- 우리가 실제로 내려주는 달력 ---------------------------------------------- #

def test_shipped_calendar_knows_this_years_holidays():
    """봇이 실제로 쓰는 config/holidays.txt 가 비어 있으면 안 된다."""
    from config.loader import HOLIDAYS_PATH

    holidays = mc.load_holidays(HOLIDAYS_PATH)
    # 2026년 KRX 휴장일은 주말을 뺀 17일이다.
    assert len([d for d in holidays if d.year == 2026]) == 17
    for expected in (date(2026, 9, 24), date(2026, 9, 25),   # 추석
                     date(2026, 10, 5), date(2026, 10, 9),   # 개천절 대체·한글날
                     date(2026, 12, 25), date(2026, 12, 31)):  # 성탄절·연말 휴장
        assert expected in holidays, f"{expected} 가 휴장일 목록에 없습니다"


def test_chuseok_is_not_a_trading_day():
    from config.loader import HOLIDAYS_PATH

    assert mc.is_trading_day(date(2026, 9, 25), HOLIDAYS_PATH) is False
    assert mc.is_trading_day(date(2026, 9, 23), HOLIDAYS_PATH) is True
