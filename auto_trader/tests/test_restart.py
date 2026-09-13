"""업데이트 후 대시보드 자가 교체.

업데이트는 start.bat 자체도 바꾼다. 돌고 있는 건 옛 start.bat 이라 거기 없는
기능에 기대면 안 된다 — 대시보드가 스스로 새 프로세스를 띄우고 빠져야 한다.
"""

from __future__ import annotations

import threading
from pathlib import Path

from dashboard.restart import RESTART_EXIT_CODE, request_restart

BASE_DIR = Path(__file__).resolve().parent.parent


def _run(spawn_ok: bool, *, delay: float = 0.01):
    codes: list[int] = []
    done = threading.Event()

    def exiter(code):
        codes.append(code)
        done.set()

    request_restart(BASE_DIR, 8765, delay=delay,
                    spawner=lambda base, port: spawn_ok, exiter=exiter)
    assert done.wait(3.0), "종료가 예약되지 않았습니다"
    return codes


def test_exits_quietly_after_spawning_the_new_dashboard():
    assert _run(True) == [0], "새 프로세스를 띄웠으면 런처를 부를 이유가 없습니다"


def test_falls_back_to_the_launcher_when_spawn_fails():
    assert _run(False) == [RESTART_EXIT_CODE]


def test_spawner_receives_base_dir_and_port():
    seen: list[tuple] = []
    done = threading.Event()

    def spawner(base, port):
        seen.append((Path(base), port))
        return True

    request_restart(BASE_DIR, 9999, delay=0.01,
                    spawner=spawner, exiter=lambda code: done.set())
    assert done.wait(3.0)
    assert seen == [(BASE_DIR, 9999)]


def test_waits_before_exiting():
    done = threading.Event()
    request_restart(BASE_DIR, 8765, delay=0.3,
                    spawner=lambda b, p: True, exiter=lambda code: done.set())
    assert not done.is_set(), "즉시 종료하면 응답이 브라우저에 닿지 못합니다"
    assert done.wait(2.0)


def test_timer_is_a_daemon():
    timer = request_restart(BASE_DIR, 8765, delay=5.0,
                            spawner=lambda b, p: True, exiter=lambda code: None)
    assert timer.daemon
    timer.cancel()


def test_relaunch_helper_exists():
    """대시보드가 띄울 스크립트가 실제로 있어야 한다."""
    assert (BASE_DIR / "scripts" / "relaunch.py").exists()


def test_relaunch_waits_for_the_port_to_free_up():
    import socket

    from scripts.relaunch import port_is_free, wait_for_port

    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        assert not port_is_free(port)
        assert not wait_for_port(port, timeout=0.4)

    assert port_is_free(port), "포트가 풀리면 바로 잡아야 합니다"


def test_start_scripts_still_understand_the_fallback_code():
    sh = (BASE_DIR / "start.sh").read_text(encoding="utf-8")
    bat = (BASE_DIR / "start.bat").read_text(encoding="ascii")
    assert f"-ne {RESTART_EXIT_CODE}" in sh
    assert f"errorlevel {RESTART_EXIT_CODE}" in bat
