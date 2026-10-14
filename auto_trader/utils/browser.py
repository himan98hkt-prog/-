"""대시보드가 실제로 뜬 뒤에 브라우저를 연다.

서버가 준비되기 전에 브라우저를 열면 "연결할 수 없음" 페이지가 뜬다.
쉘 스크립트에서 `sleep` 으로 어림잡는 대신, `/health` 가 응답할 때까지
기다렸다가 연다.
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

WAIT_TIMEOUT_SEC = 40.0  # 첫 실행은 Flask 기동에 몇 초 걸린다
POLL_INTERVAL_SEC = 0.25


def wait_until_serving(
    host: str,
    port: int,
    *,
    timeout: float = WAIT_TIMEOUT_SEC,
    interval: float = POLL_INTERVAL_SEC,
) -> bool:
    """포트가 연결을 받아줄 때까지 기다린다. 시간 안에 못 뜨면 False."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def open_when_ready(
    host: str,
    port: int,
    *,
    timeout: float = WAIT_TIMEOUT_SEC,
    opener=webbrowser.open,
) -> threading.Thread:
    """백그라운드로 기다렸다가 브라우저를 연다.

    브라우저를 못 열어도(서버 없는 환경 등) 대시보드 기동을 막지 않는다.
    """

    def run() -> None:
        if not wait_until_serving(host, port, timeout=timeout):
            return
        try:
            opener(f"http://{host}:{port}")
        except Exception:  # 브라우저가 없거나 실행이 막힌 환경
            pass

    thread = threading.Thread(target=run, name="open-browser", daemon=True)
    thread.start()
    return thread
