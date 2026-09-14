"""콘솔 + 회전 파일 로깅. 등록된 비밀값은 출력 직전에 마스킹한다."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SECRETS: set[str] = set()
_configured = False


class DailyRotatingFileHandler(RotatingFileHandler):
    """`trader_YYYYMMDD.log` 로 쓰되 **날짜가 바뀌면 새 파일로 넘어간다**.

    RotatingFileHandler 만 쓰면 파일명이 프로세스 시작 시각에 고정돼, 무인으로 며칠씩
    돌리는 동안 모든 로그가 첫날 파일에 쌓인다. 크기(10MB×5) 회전은 그대로 유지한다.
    """

    def __init__(self, log_dir: Path, **kwargs) -> None:
        self.log_dir = Path(log_dir)
        self.current_date = datetime.now(KST).strftime("%Y%m%d")
        super().__init__(self._path_for(self.current_date), **kwargs)

    def _path_for(self, date_str: str) -> str:
        return str(self.log_dir / f"trader_{date_str}.log")

    def shouldRollover(self, record: logging.LogRecord) -> int:  # noqa: N802 (표준 API)
        if datetime.now(KST).strftime("%Y%m%d") != self.current_date:
            return 1
        return super().shouldRollover(record)

    def doRollover(self) -> None:  # noqa: N802 (표준 API)
        today = datetime.now(KST).strftime("%Y%m%d")
        if today != self.current_date:
            # 날짜가 바뀐 경우: 기존 파일은 그대로 두고 새 날짜 파일로 전환한다.
            if self.stream:
                self.stream.close()
                self.stream = None  # type: ignore[assignment]
            self.current_date = today
            self.baseFilename = self._path_for(today)
            if not self.delay:
                self.stream = self._open()
            return
        super().doRollover()  # 같은 날 안에서의 크기 초과 회전


class _KstFormatter(logging.Formatter):
    """로그 시각을 항상 KST로 찍는다(naive 로컬시간 사용 금지)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        moment = datetime.fromtimestamp(record.created, tz=KST)
        return moment.strftime(datefmt or DATE_FORMAT)


class SecretFilter(logging.Filter):
    """`register_secret()`으로 등록된 값이 메시지에 섞이면 `***`로 치환한다."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not _SECRETS:
            return True
        try:
            message = record.getMessage()
        except Exception:  # 포맷 인자 오류로 로깅이 죽지 않게 한다
            return True
        redacted = message
        for secret in _SECRETS:
            if secret and secret in redacted:
                redacted = redacted.replace(secret, "***REDACTED***")
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def register_secret(*values: str | None) -> None:
    """API 키·토큰 등을 등록해 두면 이후 모든 로그에서 자동 마스킹된다."""
    for value in values:
        if value and len(value) >= 6:
            _SECRETS.add(value)


def log_file_path(log_dir: Path) -> Path:
    return log_dir / f"trader_{datetime.now(KST):%Y%m%d}.log"


def setup_logging(level: str = "INFO", log_dir: Path | str = "logs") -> logging.Logger:
    """루트 로거를 1회 구성한다. 반환값은 애플리케이션 루트 로거."""
    global _configured

    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if _configured:
        root.setLevel(level.upper())
        return logging.getLogger("auto_trader")

    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = _KstFormatter(LOG_FORMAT, DATE_FORMAT)
    secret_filter = SecretFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(secret_filter)
    root.addHandler(console)

    file_handler = DailyRotatingFileHandler(
        directory,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(secret_filter)
    root.addHandler(file_handler)

    # 외부 라이브러리 소음 억제
    for noisy in ("urllib3", "requests", "apscheduler", "httpx", "anthropic", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    return logging.getLogger("auto_trader")


def get_logger(name: str) -> logging.Logger:
    """모듈용 로거. `setup_logging()` 이전에 호출해도 안전하다."""
    return logging.getLogger(f"auto_trader.{name}")
