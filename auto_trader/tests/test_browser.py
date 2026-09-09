"""브라우저 자동 열기 — 서버가 뜬 뒤에만 연다."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

from utils.browser import open_when_ready, wait_until_serving

HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _listen(port: int, *, delay: float = 0.0) -> threading.Thread:
    """delay 초 뒤에 포트를 여는 서버 흉내."""
    ready = threading.Event()

    def serve() -> None:
        if delay:
            ready.wait(delay)
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, port))
        server.listen(5)
        ready.wait(3.0)
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread


def test_waits_until_port_accepts():
    port = _free_port()
    _listen(port, delay=0.3)
    assert wait_until_serving(HOST, port, timeout=5.0, interval=0.05)


def test_gives_up_when_nothing_listens():
    port = _free_port()  # 아무도 듣지 않는 포트
    assert not wait_until_serving(HOST, port, timeout=0.4, interval=0.05)


def test_opens_only_after_server_is_up():
    port = _free_port()
    opened: list[str] = []
    _listen(port, delay=0.3)

    thread = open_when_ready(HOST, port, timeout=5.0, opener=opened.append)
    thread.join(timeout=6.0)

    assert opened == [f"http://{HOST}:{port}"]


def test_never_opens_when_server_never_comes_up():
    port = _free_port()
    opened: list[str] = []

    thread = open_when_ready(HOST, port, timeout=0.4, opener=opened.append)
    thread.join(timeout=3.0)

    assert opened == []


def test_browser_failure_does_not_raise():
    port = _free_port()
    _listen(port, delay=0.0)

    def boom(_url):
        raise RuntimeError("브라우저 없음")

    thread = open_when_ready(HOST, port, timeout=5.0, opener=boom)
    thread.join(timeout=6.0)
    assert not thread.is_alive()  # 예외를 삼키고 조용히 끝난다


# --- 시작 스크립트 자체에 대한 회귀 테스트 ---------------------------------
# cmd.exe 는 UTF-8 한글이나 LF 줄바꿈이 섞이면 if/for 블록 파싱이 깨진다.
BASE_DIR = Path(__file__).resolve().parent.parent


def test_start_bat_is_ascii_with_crlf():
    raw = (BASE_DIR / "start.bat").read_bytes()
    assert all(byte < 128 for byte in raw), "start.bat 에 비ASCII 문자가 있습니다"
    assert raw.count(b"\n") == raw.count(b"\r\n"), "start.bat 은 CRLF 여야 합니다"


def test_start_bat_never_exits_without_pause():
    """실패 경로마다 pause 가 있어야 창이 그냥 닫히지 않는다."""
    text = (BASE_DIR / "start.bat").read_text(encoding="ascii")
    for label in ("no_python", "venv_failed", "deps_failed"):
        block = text.split(f":{label}", 1)[1].split("exit /b", 1)[0]
        assert "pause" in block, f":{label} 경로에 pause 가 없습니다"


def test_start_scripts_open_browser_after_server():
    for name in ("start.sh", "start.bat"):
        text = (BASE_DIR / name).read_text(encoding="utf-8")
        assert "--open-browser" in text, f"{name} 이 --open-browser 를 넘기지 않습니다"
        assert "sleep 2" not in text, f"{name} 이 아직 sleep 으로 어림잡고 있습니다"
