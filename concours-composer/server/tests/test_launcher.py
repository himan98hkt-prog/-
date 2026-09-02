"""바탕화면 아이콘이 실제로 프로그램을 띄우는가.

원장이 아이콘을 눌렀는데 **아무 일도 일어나지 않았다**. 고장인지, 느린 건지,
잘못 누른 건지 알 방법이 없었다.

원인은 아이콘이 `pythonw.exe` 로 뜬다는 데 있었다. 검은 창을 없애려고 그렇게 만든
것인데, `pythonw` 에서는 **표준 출력과 표준 오류가 아예 없다(None)**. uvicorn 은
로그를 stderr 로 내보내도록 설정하므로 그 설정이

    ValueError: Unable to configure formatter 'default'

로 죽는다. 창이 없으니 죽는 것도 안 보인다 — 화면에는 아무 변화가 없다.

그래서 이 검사는 **별도 프로세스**에서 그 상태를 그대로 만들고 실행기를 돌린다.
pytest 안에서 흉내 내면 pytest 가 출력을 가로채고 있어 조건이 달라진다 —
그러면 정작 원장 PC 에서만 나는 결함을 못 잡는다. 리눅스에서도 `sys.stdout = None`
은 똑같이 재현되므로 윈도우가 없어도 회귀를 잡는다.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCH = ROOT / "scripts" / "launch.py"

# pythonw.exe 로 띄운 것과 같은 상태를 만드는 껍데기.
HEADLESS = textwrap.dedent(
    """
    import runpy, sys
    sys.stdout = None
    sys.stderr = None
    runpy.run_path({path!r}, run_name="__main__")
    """
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _get(url: str, timeout: float = 1.0):
    return urllib.request.urlopen(url, timeout=timeout)


def _wait_for(url: str, deadline: float) -> int | None:
    while time.time() < deadline:
        try:
            with _get(url) as r:
                return int(r.status)
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.3)
    return None


def test_the_icon_actually_starts_the_program(tmp_path: Path) -> None:
    """창 없이(pythonw 처럼) 띄워도 서버가 응답해야 한다.

    고치기 전에는 여기서 프로세스가 조용히 죽었다 — 원장 화면의 '아무 변화 없음'.
    """
    port = _free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        "STORE_PERSIST": "0",  # 진짜 저장 파일을 건드리지 않는다
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", HEADLESS.format(path=str(LAUNCH))],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        status = _wait_for(f"http://127.0.0.1:{port}/health", time.time() + 90)
        assert status == 200, (
            "아이콘을 눌러도 프로그램이 뜨지 않는다. "
            f"프로세스는 {'이미 죽었다' if proc.poll() is not None else '살아는 있다'}."
        )
    finally:
        with contextlib.suppress(urllib.error.URLError, TimeoutError, OSError):
            urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST"),
                timeout=3,
            )
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_the_launcher_leaves_a_record(tmp_path: Path) -> None:
    """무슨 일이 있었는지 파일로 남아야 한다 — 기록이 없으면 물어볼 것도 없다."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("launch_for_test", LAUNCH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.LOG = tmp_path / "실행기록.txt"
    mod.note("시험 기록")
    assert "시험 기록" in (tmp_path / "실행기록.txt").read_text(encoding="utf-8")


def test_a_working_console_is_left_alone() -> None:
    """명령창에서 띄웠을 때는 손대지 않는다 — 화면에 그대로 나와야 한다."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("launch_for_test2", LAUNCH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    before_out, before_err = sys.stdout, sys.stderr
    mod.ensure_streams()
    assert sys.stdout is before_out and sys.stderr is before_err
