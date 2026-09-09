"""장 운영일·운영시간 판단 (KST 기준).

휴장일은 `config/holidays.txt`(YYYY-MM-DD 한 줄씩)에서 읽는다.
파일이 없으면 주말만 제외하고 경고 로그를 남긴다.
"""

from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
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
