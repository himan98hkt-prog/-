"""업데이트 후 대시보드 자가 교체.

업데이트는 start.bat 자체도 바꾼다. 돌고 있는 건 옛 start.bat 이라 거기 없는
기능에 기대면 안 된다 — 대시보드가 스스로 새 프로세스를 띄우고 빠져야 한다.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

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


# --- 새 대시보드가 기동 중에 죽었을 때 ------------------------------------- #
#
# 예전에는 os.execv 로 자기 자신을 갈아 끼웠다. 그러면 새 대시보드가 곧바로
# 죽었을 때 창까지 같이 닫혀, 사용자에게는 브라우저의 '연결할 수 없음' 만
# 남고 이유를 볼 방법이 없었다. 이제는 자식으로 띄우고 지켜본다.

def _run_main(monkeypatch, tmp_path, exit_code, *, port=8765):
    import scripts.relaunch as relaunch

    seen: list[list[str]] = []
    monkeypatch.setattr(relaunch, "BASE_DIR", tmp_path)   # 진짜 logs/ 를 건드리지 않게
    monkeypatch.setattr(relaunch, "wait_for_port", lambda p, **kw: True)
    monkeypatch.setattr(relaunch.subprocess, "call",
                        lambda cmd, *a, **kw: seen.append(cmd) or exit_code)
    monkeypatch.setattr(relaunch.sys, "argv", ["relaunch.py", "--port", str(port)])
    return relaunch.main(), seen


def test_successful_dashboard_returns_zero(monkeypatch, tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "dashboard.py").write_text("", encoding="utf-8")
    code, seen = _run_main(monkeypatch, tmp_path, 0)
    assert code == 0
    assert len(seen) == 1, "대시보드를 정확히 한 번 띄워야 합니다"
    assert "--port" in seen[0] and "8765" in seen[0]


def test_crash_holds_the_window_and_reports_the_code(monkeypatch, tmp_path, capsys):
    """창이 닫히면 원인이 사라진다 — 붙잡고 이유를 찍어야 한다."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "dashboard.py").write_text("", encoding="utf-8")
    code, _ = _run_main(monkeypatch, tmp_path, 3)
    assert code == 1
    message = capsys.readouterr().err
    assert "코드 3" in message, "몇 번으로 죽었는지 알려 줘야 합니다"
    assert "dashboard_" in message, "로그 위치를 알려 줘야 합니다"
    assert "start.bat" in message, "복구 방법을 알려 줘야 합니다"


def test_crash_is_also_written_to_the_log(monkeypatch, tmp_path):
    """창을 닫아 버려도 진단 화면에서 이유를 꺼낼 수 있어야 한다."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "dashboard.py").write_text("", encoding="utf-8")
    _run_main(monkeypatch, tmp_path, 3)

    logs = list((tmp_path / "logs").glob("dashboard_*.log"))
    assert logs, "재기동 실패가 로그에 남아야 합니다"
    assert "코드 3" in logs[0].read_text(encoding="utf-8")


def test_busy_port_explains_itself(monkeypatch, tmp_path, capsys):
    import scripts.relaunch as relaunch

    monkeypatch.setattr(relaunch, "BASE_DIR", tmp_path)
    monkeypatch.setattr(relaunch, "wait_for_port", lambda p, **kw: False)
    monkeypatch.setattr(relaunch.subprocess, "call",
                        lambda *a, **kw: pytest.fail("포트가 막혔는데 띄우면 안 됩니다"))
    monkeypatch.setattr(relaunch.sys, "argv", ["relaunch.py"])
    assert relaunch.main() == 1
    assert "포트" in capsys.readouterr().err


def test_relaunch_never_replaces_itself():
    """execv 로 돌아가면 다시 원인을 못 보게 된다 — 소스에서 막아 둔다."""
    source = (BASE_DIR / "scripts" / "relaunch.py").read_text(encoding="utf-8")
    assert "os.execv" not in source


# --- 기동 단계에서 죽었을 때 단서 남기기 ------------------------------------ #

def test_import_failure_is_written_to_the_log(tmp_path):
    """임포트가 터지면 setup_logging 이 아직 없다 — 그래도 파일에 남아야 한다."""
    import scripts.dashboard as launcher

    try:
        raise RuntimeError("설정 항목이 없습니다")
    except RuntimeError:
        written = launcher.record_early_failure(tmp_path / "logs")

    assert written is not None and written.exists()
    text = written.read_text(encoding="utf-8")
    assert "설정 항목이 없습니다" in text, "무엇 때문에 죽었는지 남아야 합니다"
    assert "RuntimeError" in text


def test_early_failure_log_never_raises(tmp_path):
    """로그를 못 써도 기동 실패 처리 자체가 또 터지면 안 된다."""
    import scripts.dashboard as launcher

    blocked = tmp_path / "file"
    blocked.write_text("", encoding="utf-8")
    try:
        raise RuntimeError("x")
    except RuntimeError:
        assert launcher.record_early_failure(blocked / "logs") is None


def test_app_creation_is_inside_the_guard():
    """create_app() 이 밖에 있으면 그 traceback 이 파일에 안 남는다."""
    source = (BASE_DIR / "scripts" / "dashboard.py").read_text(encoding="utf-8")
    body = source.split("    try:\n", 1)[1]
    assert "create_app()" in body.split("    except KeyboardInterrupt", 1)[0]
