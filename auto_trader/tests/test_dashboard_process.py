"""매매 프로세스 제어 테스트 — 실제 프로세스를 띄우지 않고 경계 조건만 본다."""

from __future__ import annotations

import os
import signal

import pytest

from dashboard import process


@pytest.fixture
def dirs(tmp_path):
    (tmp_path / "logs").mkdir()
    return {"base": tmp_path, "data": tmp_path, "log": tmp_path / "logs"}


def test_start_refuses_when_already_running(dirs):
    (dirs["data"] / "trader.pid").write_text("1")  # PID 1 은 항상 존재
    result = process.start(dirs["base"], dirs["data"], dirs["log"])
    assert not result.ok and "이미 실행 중" in result.message


def test_stop_reports_when_not_running(dirs):
    result = process.stop(dirs["data"])
    assert not result.ok and "실행 중이 아닙니다" in result.message


def test_stop_sends_sigterm_and_waits(dirs, monkeypatch):
    """진행 중 사이클을 마치도록 SIGTERM 을 쓴다 — SIGKILL 이면 안 된다."""
    (dirs["data"] / "trader.pid").write_text("4242")
    sent: list[tuple[int, int]] = []
    alive = {"value": True}

    monkeypatch.setattr(process.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr(process, "is_running", lambda data_dir: alive["value"])

    class FakeLock:
        def __init__(self, path):
            self.path = path

        def read_pid(self):
            return 4242

        def is_running(self):
            alive["value"] = False  # 두 번째 확인부터 종료된 것으로
            return len(sent) == 0

    monkeypatch.setattr(process, "ProcessLock", FakeLock)
    result = process.stop(dirs["data"])

    assert sent == [(4242, signal.SIGTERM)], "SIGTERM 으로 안전 종료를 요청해야 합니다"
    assert result.ok


def test_start_reports_failure_with_log_tail(dirs, monkeypatch):
    """설정 오류로 곧바로 죽으면 최근 출력을 보여준다."""
    monkeypatch.setattr(process, "START_TIMEOUT_SEC", 0.2)
    monkeypatch.setattr(process, "POLL_SEC", 0.05)
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **kw: None)
    (dirs["log"] / "stdout.log").write_text("[설정 오류]\nKIS_APP_KEY: .env 에 반드시 설정해야 합니다\n")

    result = process.start(dirs["base"], dirs["data"], dirs["log"])
    assert not result.ok
    assert "KIS_APP_KEY" in result.message


def test_restart_starts_when_not_running(dirs, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(process, "start",
                        lambda *a: (calls.append("start"), process.ControlResult(True, "시작"))[1])

    result = process.restart(dirs["base"], dirs["data"], dirs["log"])
    assert calls == ["start"] and result.ok


def test_restart_stops_before_starting(dirs, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop",
                        lambda *a: (calls.append("stop"), process.ControlResult(True, "종료"))[1])
    monkeypatch.setattr(process, "start",
                        lambda *a: (calls.append("start"), process.ControlResult(True, "시작"))[1])

    result = process.restart(dirs["base"], dirs["data"], dirs["log"])
    assert calls == ["stop", "start"], "먼저 내리고 다시 띄워야 설정이 반영됩니다"
    assert "재시작" in result.message


def test_restart_aborts_if_stop_fails(dirs, monkeypatch):
    """종료에 실패했는데 새로 띄우면 두 프로세스가 동시에 매매한다."""
    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda *a: process.ControlResult(False, "응답 없음"))
    monkeypatch.setattr(process, "start",
                        lambda *a: (calls.append("start"), process.ControlResult(True, "시작"))[1])

    result = process.restart(dirs["base"], dirs["data"], dirs["log"])
    assert calls == [], "종료 실패 시 새로 띄우면 안 됩니다"
    assert not result.ok


def test_start_detects_process_that_dies_right_after(dirs, monkeypatch):
    """PID 만 보고 '시작 성공' 이라 하면, 키가 틀려 곧 죽어도 사용자가 모른다."""
    monkeypatch.setattr(process, "SETTLE_SEC", 0.3)
    monkeypatch.setattr(process, "START_TIMEOUT_SEC", 1)
    monkeypatch.setattr(process, "POLL_SEC", 0.05)
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **kw: None)
    (dirs["log"] / "stdout.log").write_text(
        "2026-09-08 09:00:00 [INFO    ] auto_trader.main: 기동\n"
        "2026-09-08 09:00:06 [ERROR   ] auto_trader.main: 기동 실패: 토큰 발급 실패 (HTTP 403)\n"
    )

    # 1번째 호출은 start() 첫머리의 '이미 실행 중?' 가드 → False
    # 2~3번째는 살아 있음, 그 뒤 죽는다
    calls = {"n": 0}

    def alive_then_dead(data_dir):
        calls["n"] += 1
        return 2 <= calls["n"] <= 3

    monkeypatch.setattr(process, "is_running", alive_then_dead)

    result = process.start(dirs["base"], dirs["data"], dirs["log"])
    assert not result.ok
    assert "기동 직후 종료" in result.message
    assert "403" in result.message, "실패 원인이 메시지에 담겨야 합니다"


def test_start_succeeds_when_process_stays_up(dirs, monkeypatch):
    monkeypatch.setattr(process, "SETTLE_SEC", 0.2)
    monkeypatch.setattr(process, "POLL_SEC", 0.05)
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **kw: None)

    calls = {"n": 0}

    def not_running_then_alive(data_dir):
        calls["n"] += 1
        return calls["n"] > 1  # 첫 호출은 '이미 실행 중?' 가드

    monkeypatch.setattr(process, "is_running", not_running_then_alive)

    result = process.start(dirs["base"], dirs["data"], dirs["log"])
    assert result.ok and "시작했습니다" in result.message


def test_error_line_is_extracted_from_log():
    tail = (
        "2026-09-08 09:00:00 [INFO    ] auto_trader.main: 기동\n"
        "2026-09-08 09:00:06 [ERROR   ] auto_trader.main: 기동 실패: KIS 인증 거부 (HTTP 403)\n"
        "2026-09-08 09:00:06 [INFO    ] auto_trader.runtime: 실행 락 해제\n"
    )
    assert "403" in process._first_error(tail)
    assert "[ERROR" not in process._first_error(tail), "레벨 표시는 걷어냅니다"


def test_no_error_line_returns_empty():
    assert process._first_error("정상 로그만 있음") == ""
