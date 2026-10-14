"""재시도 데코레이터 테스트."""

from __future__ import annotations

import pytest

from utils.retry import RetryExhausted, retry


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("utils.retry.time.sleep", lambda *_: None)


def test_succeeds_after_transient_failures():
    attempts = {"n": 0}

    @retry(max_attempts=3, backoff=2)
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("일시 오류")
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 3


def test_raises_retry_exhausted():
    @retry(max_attempts=2, backoff=2)
    def always_fails():
        raise ValueError("영구 오류")

    with pytest.raises(RetryExhausted) as exc_info:
        always_fails()
    assert exc_info.value.attempts == 2
    assert isinstance(exc_info.value.last_error, ValueError)


def test_give_up_on_skips_retry():
    attempts = {"n": 0}

    class Fatal(Exception):
        pass

    @retry(max_attempts=5, backoff=2, exceptions=(Exception,), give_up_on=(Fatal,))
    def fatal():
        attempts["n"] += 1
        raise Fatal("재시도 불가")

    with pytest.raises(Fatal):
        fatal()
    assert attempts["n"] == 1


def test_unlisted_exception_propagates_immediately():
    attempts = {"n": 0}

    @retry(max_attempts=3, exceptions=(ConnectionError,))
    def wrong_error():
        attempts["n"] += 1
        raise TypeError("대상 아님")

    with pytest.raises(TypeError):
        wrong_error()
    assert attempts["n"] == 1
