"""장 운영일·운영시간 판단 (KST 기준).

휴장일은 `config/holidays.txt`(YYYY-MM-DD 한 줄씩)에서 읽는다.
파일이 없으면 주말만 제외하고 경고 로그를 남긴다.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config.loader import HOLIDAYS_PATH
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("market_calendar")

MARKET_OPEN = time(9, 0, 0)
MARKET_CLOSE = time(15, 30, 0)

DEFAULT_HOLIDAYS_PATH = HOLIDAYS_PATH
_warned_missing = False


def now_kst() -> datetime:
    """항상 tz-aware한 현재 시각 (naive datetime 사용 금지)."""
    return datetime.now(KST)


@lru_cache(maxsize=8)
def _read_holidays(path_str: str, mtime: float) -> frozenset[date]:
    """휴장일 파일 파싱 (mtime을 캐시 키에 포함해 수정 시 자동 갱신)."""
    holidays: set[date] = set()
    for lineno, raw in enumerate(Path(path_str).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            holidays.add(datetime.strptime(line, "%Y-%m-%d").date())
        except ValueError:
            logger.warning("휴장일 파일 %s:%d 형식 오류(무시): %r", path_str, lineno, raw.strip())
    return frozenset(holidays)


def load_holidays(path: Path | str = DEFAULT_HOLIDAYS_PATH) -> frozenset[date]:
    """휴장일 집합. 파일이 없으면 한 번만 경고하고 빈 집합을 반환한다."""
    global _warned_missing
    holidays_path = Path(path)
    if not holidays_path.exists():
        if not _warned_missing:
            logger.warning(
                "휴장일 파일이 없습니다 (%s) — 주말만 제외합니다. "
                "KRX 휴장일을 YYYY-MM-DD 한 줄씩 적어 두세요.",
                holidays_path,
            )
            _warned_missing = True
        return frozenset()
    return _read_holidays(str(holidays_path), holidays_path.stat().st_mtime)


def is_trading_day(target: date | datetime | None = None, holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> bool:
    """주말·휴장일이 아니면 True."""
    if target is None:
        target = now_kst()
    day = target.date() if isinstance(target, datetime) else target
    if day.weekday() >= 5:  # 5=토, 6=일
        return False
    return day not in load_holidays(holidays_path)


def is_market_open(now: datetime | None = None, holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> bool:
    """정규장(09:00:00~15:30:00 KST) 운영 중이면 True."""
    moment = now or now_kst()
    if moment.tzinfo is None:
        raise ValueError("naive datetime 은 사용할 수 없습니다 (Asia/Seoul tz 필요)")
    moment = moment.astimezone(KST)
    if not is_trading_day(moment, holidays_path):
        return False
    return MARKET_OPEN <= moment.time() <= MARKET_CLOSE


def is_before(limit: time, now: datetime | None = None) -> bool:
    """현재 시각이 `limit` 이전인지 (신규 매수 마감 시각 판단용)."""
    moment = (now or now_kst()).astimezone(KST)
    return moment.time() <= limit


def market_state(now: datetime | None = None, holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> str:
    """'HOLIDAY' | 'PRE_OPEN' | 'OPEN' | 'CLOSED' — 로그·알림 표기용."""
    moment = (now or now_kst()).astimezone(KST)
    if not is_trading_day(moment, holidays_path):
        return "HOLIDAY"
    if moment.time() < MARKET_OPEN:
        return "PRE_OPEN"
    if moment.time() > MARKET_CLOSE:
        return "CLOSED"
    return "OPEN"


# -- 달력이 낡았는지 --------------------------------------------------------- #
#
# 휴장일 파일은 해마다 사람이 채워 넣어야 한다. 비어 있어도 코드는 멀쩡히 돌기
# 때문에, 아무도 모르는 채 휴장일에 주문을 내고 거부 알림만 쌓이게 된다.
# 그래서 달력이 바닥나기 전에 **먼저 말하게** 한다.

COVERAGE_WARN_DAYS = 30  # 남은 휴장일 범위가 이보다 짧으면 경고한다


def next_trading_day(after: date | datetime | None = None,
                     holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> date:
    """`after` **다음**의 첫 거래일. 최대 30일까지만 찾는다(그 이상은 달력 문제)."""
    start = after or now_kst()
    day = start.date() if isinstance(start, datetime) else start
    for _ in range(30):
        day += timedelta(days=1)
        if is_trading_day(day, holidays_path):
            return day
    return day


def upcoming_holidays(limit: int = 3, now: datetime | None = None,
                      holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> list[date]:
    """오늘 이후로 다가오는 휴장일 (주말 제외, 가까운 순)."""
    today = (now or now_kst()).date()
    future = sorted(d for d in load_holidays(holidays_path)
                    if d > today and d.weekday() < 5)
    return future[:limit]


def calendar_health(now: datetime | None = None,
                    holidays_path: Path | str = DEFAULT_HOLIDAYS_PATH) -> dict[str, Any]:
    """휴장일 달력이 아직 쓸 만한지.

    Returns:
        ``ok``      — 아직 여유가 있다
        ``stale``   — 달력이 곧 바닥난다(또는 이미 바닥났다). 채워야 한다
        ``missing`` — 파일 자체가 없다
    """
    today = (now or now_kst()).date()
    path = Path(holidays_path)
    if not path.exists():
        return {"state": "missing", "covered_until": None, "days_left": 0, "next": [],
                "message": f"휴장일 파일이 없습니다 ({path}) — 주말만 제외하고 돕니다."}

    holidays = load_holidays(holidays_path)
    future = sorted(d for d in holidays if d >= today)
    covered_until = max(holidays) if holidays else None
    days_left = (covered_until - today).days if covered_until else 0

    if not holidays:
        return {"state": "stale", "covered_until": None, "days_left": 0, "next": [],
                "message": "휴장일이 하나도 없습니다 — 공휴일에도 주문을 시도합니다. "
                           "KRX 공지를 보고 config/holidays.txt 를 채워 주세요."}
    if days_left < COVERAGE_WARN_DAYS:
        tail = f"{covered_until:%Y-%m-%d}" if covered_until else "?"
        detail = (f"달력이 {tail} 까지뿐입니다"
                  if future else f"남은 휴장일이 없습니다 (마지막 {tail})")
        return {"state": "stale", "covered_until": covered_until, "days_left": days_left,
                "next": future[:3],
                "message": f"{detail} — 다음 해 휴장일을 config/holidays.txt 에 추가해 주세요."}

    return {"state": "ok", "covered_until": covered_until, "days_left": days_left,
            "next": future[:3], "message": ""}
