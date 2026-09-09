"""업데이트 후 대시보드 자가 재기동.

파이썬은 모듈을 한 번만 import 하므로, 코드를 갈아끼워도 돌고 있는
대시보드는 예전 화면을 계속 그린다. 프로세스를 갈아야만 새 입력칸이 보인다.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

from dashboard.restart import RESTART_EXIT_CODE, request_restart

BASE_DIR = Path(__file__).resolve().parent.parent


def test_exits_with_the_agreed_code():
    seen: list[int] = []
    done = threading.Event()

    def fake_exit():
        seen.append(RESTART_EXIT_CODE)
        done.set()

    request_restart(delay=0.01, exiter=fake_exit)
    assert done.wait(2.0)
    assert seen == [42], "start 스크립트와 약속된 값이 바뀌면 재기동이 끊깁니다"


def test_waits_before_exiting():
    """응답이 브라우저에 닿기 전에 죽으면 사용자는 빈 화면을 본다."""
    done = threading.Event()
    request_restart(delay=0.3, exiter=done.set)
    assert not done.is_set(), "즉시 종료하면 안 됩니다"
    assert done.wait(2.0)


def test_timer_is_a_daemon():
    """재기동 타이머가 종료를 막아서는 안 된다."""
    timer = request_restart(delay=5.0, exiter=lambda: None)
    assert timer.daemon
    timer.cancel()


# --- 실행 스크립트가 그 코드를 받아 다시 띄우는가 --------------------------- #


def test_start_sh_loops_on_the_restart_code():
    text = (BASE_DIR / "start.sh").read_text(encoding="utf-8")
    assert "-ne 42" in text, "start.sh 가 종료 코드 42 를 처리하지 않습니다"
    assert "while true" in text


def test_start_bat_loops_on_the_restart_code():
    text = (BASE_DIR / "start.bat").read_text(encoding="ascii")
    assert "errorlevel 42" in text, "start.bat 이 종료 코드 42 를 처리하지 않습니다"
    assert ":run_dashboard" in text
    # cmd 의 `if errorlevel N` 은 'N 이상' 이라, 43 이상을 먼저 걸러야 42 만 잡힌다.
    assert text.index("errorlevel 43") < text.index("errorlevel 42")


def test_restart_code_matches_between_python_and_scripts():
    """한쪽만 바꾸면 조용히 끊기는 연결이라 값을 직접 맞춰 본다."""
    sh = (BASE_DIR / "start.sh").read_text(encoding="utf-8")
    bat = (BASE_DIR / "start.bat").read_text(encoding="ascii")
    assert f"-ne {RESTART_EXIT_CODE}" in sh
    assert f"errorlevel {RESTART_EXIT_CODE}" in bat
