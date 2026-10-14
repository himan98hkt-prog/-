"""로깅 테스트 — 비밀값 마스킹과 날짜 전환 회전."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from utils import logger as logger_module
from utils.logger import DailyRotatingFileHandler, SecretFilter, register_secret

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def handler(tmp_path):
    instance = DailyRotatingFileHandler(tmp_path, maxBytes=200, backupCount=3, encoding="utf-8")
    yield instance
    instance.close()


def record(message: str) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, message, None, None)


def test_filename_uses_today(handler, tmp_path):
    today = datetime.now(KST).strftime("%Y%m%d")
    assert handler.baseFilename == str(tmp_path / f"trader_{today}.log")


def test_rolls_to_new_file_when_date_changes(handler, tmp_path, monkeypatch):
    """무인 운영 중 자정을 넘겨도 첫날 파일에 계속 쓰면 안 된다."""
    handler.emit(record("첫날 로그"))
    first_file = handler.baseFilename

    tomorrow = datetime.now(KST) + timedelta(days=1)
    monkeypatch.setattr(logger_module, "datetime",
                        type("D", (datetime,), {"now": staticmethod(lambda tz=None: tomorrow)}))

    handler.emit(record("다음날 로그"))
    assert handler.baseFilename != first_file
    assert handler.baseFilename.endswith(f"trader_{tomorrow:%Y%m%d}.log")
    assert "첫날 로그" in open(first_file, encoding="utf-8").read()
    assert "다음날 로그" in open(handler.baseFilename, encoding="utf-8").read()


def test_size_rotation_still_works_within_a_day(handler, tmp_path):
    for i in range(50):
        handler.emit(record(f"{i} " + "가" * 50))
    files = sorted(path.name for path in tmp_path.iterdir())
    assert len(files) > 1, "10MB 회전 규칙(테스트에선 200B)이 유지되어야 합니다"
    assert any(name.endswith(".log.1") for name in files)


def test_secret_filter_redacts_registered_values():
    register_secret("SUPER-SECRET-TOKEN-VALUE")
    entry = record("authorization=Bearer SUPER-SECRET-TOKEN-VALUE")
    assert SecretFilter().filter(entry) is True
    assert "SUPER-SECRET-TOKEN-VALUE" not in entry.getMessage()
    assert "***REDACTED***" in entry.getMessage()


def test_short_values_are_not_registered():
    from utils.logger import _SECRETS

    register_secret("abc")  # 6자 미만은 오탐이 많아 등록하지 않는다
    assert "abc" not in _SECRETS


# --- Windows 콘솔 인코딩 ------------------------------------------------------ #

def test_log_messages_survive_a_cp949_console(tmp_path, monkeypatch):
    """cp949 에 없는 문자(—, →) 때문에 로그 한 줄이 프로그램을 죽이면 안 된다."""
    import io
    import sys

    import utils.logger as logger_module

    # Windows 한글 기본 출력(cp949)을 흉내 낸다.
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp949", errors="strict", line_buffering=True)
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(logger_module, "_configured", False)

    log = logger_module.setup_logging("INFO", tmp_path)
    log.info("종료 요청을 받았습니다 — 진행 중 사이클을 마치고 종료합니다")
    log.info("손절선 도달 → 전량 매도")

    text = raw.getvalue().decode("utf-8", errors="replace")
    assert "종료 요청을 받았습니다" in text
    assert "손절선 도달" in text


def test_force_utf8_never_raises():
    """표준 출력이 무엇이든 로깅 설정이 터지면 안 된다."""
    from utils.logger import _force_utf8

    class Awkward:
        def reconfigure(self, **kwargs):
            raise OSError("이 스트림은 바꿀 수 없습니다")

    _force_utf8(Awkward())
    _force_utf8(object())      # reconfigure 자체가 없는 경우
    _force_utf8(None)
