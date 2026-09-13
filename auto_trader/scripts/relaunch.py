#!/usr/bin/env python3
"""업데이트 뒤 대시보드를 새 코드로 다시 띄운다.

업데이트는 start.bat 자체도 바꾼다. 그런데 지금 돌고 있는 건 **옛** start.bat
이라, 거기 없는 기능(재기동 루프)에 기대면 대시보드가 그냥 죽어 버린다.
그래서 대시보드가 **스스로** 새 프로세스를 띄우고 빠진다. 런처 버전과 무관하다.

이 스크립트는 옛 프로세스가 포트를 놓을 때까지 기다렸다가 대시보드를 켠다.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
WAIT_TIMEOUT_SEC = 40.0
POLL_SEC = 0.3


def port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
            return True
        except OSError:
            return False


def wait_for_port(port: int, *, timeout: float = WAIT_TIMEOUT_SEC) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_free(port):
            return True
        time.sleep(POLL_SEC)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="대시보드 재기동")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not wait_for_port(args.port):
        print(f"포트 {args.port} 가 계속 사용 중입니다 — 재기동을 포기합니다", file=sys.stderr)
        return 1

    dashboard = BASE_DIR / "scripts" / "dashboard.py"
    # execv 로 이 프로세스를 대시보드로 갈아 끼운다 — 중간 프로세스가 남지 않는다.
    os.execv(sys.executable, [sys.executable, str(dashboard),
                              "--port", str(args.port), "--open-browser"])
    return 0  # execv 가 성공하면 여기 오지 않는다


if __name__ == "__main__":
    raise SystemExit(main())
