#!/usr/bin/env python3
"""업데이트 뒤 대시보드를 새 코드로 다시 띄운다.

업데이트는 start.bat 자체도 바꾼다. 그런데 지금 돌고 있는 건 **옛** start.bat
이라, 거기 없는 기능(재기동 루프)에 기대면 대시보드가 그냥 죽어 버린다.
그래서 대시보드가 **스스로** 새 프로세스를 띄우고 빠진다. 런처 버전과 무관하다.

이 스크립트는 옛 프로세스가 포트를 놓을 때까지 기다렸다가 대시보드를 켠다.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
WAIT_TIMEOUT_SEC = 40.0
POLL_SEC = 0.3

# 대시보드가 이 코드로 끝나면 "나를 다시 띄워 달라" 는 뜻이다.
# 원본은 dashboard/restart.py 의 RESTART_EXIT_CODE — 테스트가 두 값을 맞춰 둔다.
# (여기서 import 하지 않는 이유: 이 스크립트는 업데이트 도중에도 떠야 한다.)
RESTART_EXIT_CODE = 42
MAX_RELAUNCHES = 3


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
        return _stop(f"포트 {args.port} 를 예전 대시보드가 계속 쓰고 있습니다.",
                     "작업 관리자에서 python.exe 를 끝낸 뒤 다시 시도하세요.")

    dashboard = BASE_DIR / "scripts" / "dashboard.py"
    if not dashboard.exists():
        return _stop(f"대시보드 파일을 찾을 수 없습니다: {dashboard}")

    # execv 로 갈아 끼우지 않는다. 그러면 새 대시보드가 기동 중에 죽었을 때
    # 창이 그대로 닫혀 이유를 볼 수 없다 — 사용자에게는 '연결할 수 없음' 만 남는다.
    # 자식으로 띄우고 지켜보다가, 실패하면 창을 붙잡고 원인을 보여준다.
    for _ in range(MAX_RELAUNCHES):
        code = subprocess.call([sys.executable, str(dashboard),
                                "--port", str(args.port), "--open-browser"])
        if code == 0:
            return 0
        if code == RESTART_EXIT_CODE:
            # 대시보드가 "나를 다시 띄워 달라" 고 한 것이다(업데이트 직후).
            # 이걸 오류로 보고 창을 붙잡으면 대시보드가 영영 돌아오지 않는다.
            print(f"\n  대시보드가 재기동을 요청했습니다 — 다시 띄웁니다 (포트 {args.port})",
                  file=sys.stderr)
            if not wait_for_port(args.port):
                return _stop(f"포트 {args.port} 가 풀리지 않습니다.",
                             "작업 관리자에서 python.exe 를 끝낸 뒤 다시 시도하세요.")
            continue
        return _stop(
            f"대시보드가 코드 {code} 로 종료됐습니다.",
            "위에 찍힌 오류가 원인입니다. logs 폴더의 dashboard_*.log 에도 남아 있습니다.",
        )
    return _stop(f"대시보드가 {MAX_RELAUNCHES}번 연속 재기동을 요청했습니다.",
                 "무한 반복을 막기 위해 멈췄습니다. 로그를 확인해 주세요.")


def _log(lines: tuple[str, ...]) -> None:
    """창을 닫아 버려도 진단 화면에서 볼 수 있게 파일에도 남긴다."""
    try:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now()
        path = log_dir / f"dashboard_{stamp.strftime('%Y%m%d')}.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[{stamp.isoformat(timespec='seconds')}] 재기동 실패\n")
            for line in lines:
                handle.write(f"  {line}\n")
    except OSError:
        pass                 # 로그를 못 써도 화면에는 아래에서 찍는다


def _stop(*lines: str) -> int:
    """창을 닫지 않고 이유를 남긴다."""
    _log(lines)
    print("\n" + "=" * 62, file=sys.stderr)
    for line in lines:
        print("  " + line, file=sys.stderr)
    print("=" * 62, file=sys.stderr)
    print("\n  start.bat 을 다시 실행하면 대시보드가 올라옵니다.", file=sys.stderr)
    try:
        input("\n  Enter 를 누르면 이 창을 닫습니다... ")
    except (EOFError, KeyboardInterrupt, OSError):
        pass          # 콘솔이 없는 환경(서비스·테스트)에서는 그냥 빠진다
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
