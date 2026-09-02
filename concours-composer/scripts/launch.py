#!/usr/bin/env python3
"""바탕화면 아이콘이 부르는 실행기.

원장이 하는 일은 아이콘을 한 번 누르는 것뿐이어야 한다. 검은 명령창도, 주소를
외워 치는 일도 없어야 한다. 그래서 이 파일이 대신 한다.

    이미 켜져 있나  →  브라우저만 연다 (서버를 두 개 띄우지 않는다)
    꺼져 있나       →  서버를 띄우고, 뜬 것을 확인한 뒤 브라우저를 연다

끄는 것은 화면 안의 '프로그램 끄기' 버튼이다(POST /api/shutdown). 명령창이 없으니
Ctrl+C 를 누를 곳도 없기 때문이다.

윈도우 바로가기는 `pythonw.exe` 로 이 파일을 부른다 — 그래야 검은 창이 안 뜬다.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_PORT = 8000
HOST = "127.0.0.1"


def already_running(port: int) -> bool:
    """이 포트에서 우리 프로그램이 이미 돌고 있는가.

    아무 서버나 잡으면 안 된다 — /health 가 우리 응답을 돌려줄 때만 참이다.
    """
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=1.5) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def port_taken(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def pick_port(start: int = DEFAULT_PORT) -> int:
    """기본 포트를 남이 쓰고 있으면 옆 칸으로 비켜난다."""
    for port in range(start, start + 12):
        if already_running(port) or not port_taken(port):
            return port
    return start


def open_when_ready(url: str, timeout: float = 40.0) -> None:
    """서버가 응답하기 시작하면 그때 브라우저를 연다 — 빈 화면을 보여 주지 않는다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "health", timeout=1.0) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    webbrowser.open(url + "app/")


def main() -> int:
    port = pick_port()
    url = f"http://{HOST}:{port}/"

    if already_running(port):
        webbrowser.open(url + "app/")
        return 0

    import uvicorn
    from app.main import app

    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # 화면의 '프로그램 끄기' 버튼이 이 손잡이를 잡는다.
    app.state.server = server

    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
