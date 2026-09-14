"""업데이트 후 대시보드를 새 코드로 갈아 끼운다.

파이썬은 모듈을 처음 import 할 때 한 번만 읽는다. 업데이트가 디스크의 파일을
바꿔도 돌고 있는 대시보드는 예전 화면을 계속 그린다(새 입력칸이 안 생긴다).

**런처(start.bat)에 기대지 않는다.** 업데이트는 start.bat 자체도 바꾸는데 지금
돌고 있는 건 옛 start.bat 이라, 거기 없는 재기동 기능에 기대면 대시보드가 그냥
죽어 버린다. 그래서 여기서 직접 새 프로세스를 띄우고 빠진다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("restart")

# 새 프로세스를 못 띄웠을 때만 쓰는 폴백. 최신 start 스크립트는 이 코드를 보면
# 대시보드를 다시 띄운다(옛 스크립트는 그냥 종료된다).
RESTART_EXIT_CODE = 42

GRACE_SEC = 1.5  # 응답이 브라우저에 닿을 시간


def _spawn(base_dir: Path | str, port: int) -> bool:
    """새 대시보드를 부모와 분리해 띄운다. 성공하면 True."""
    relaunch = Path(base_dir) / "scripts" / "relaunch.py"
    if not relaunch.exists():
        logger.error("relaunch.py 가 없습니다: %s", relaunch)
        return False

    command = [sys.executable, str(relaunch), "--port", str(port)]
    kwargs: dict = {"cwd": str(base_dir), "close_fds": True}
    if os.name == "nt":
        # 부모가 죽어도 살아남고, 콘솔 창을 새로 갖는다.
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(command, **kwargs)
    except OSError as exc:
        logger.error("대시보드 재기동 프로세스를 띄우지 못했습니다: %s", exc)
        return False
    logger.info("새 대시보드를 띄웠습니다 (포트 %d)", port)
    return True


def request_restart(
    base_dir: Path | str,
    port: int,
    *,
    delay: float = GRACE_SEC,
    spawner=None,
    exiter=None,
) -> threading.Timer:
    """응답을 보낸 뒤 대시보드를 새 코드로 교체한다.

    새 프로세스를 띄웠으면 종료 코드 0 으로 조용히 빠지고, 못 띄웠으면
    RESTART_EXIT_CODE 로 죽어 최신 런처가 대신 띄워 주기를 기대한다.
    """
    spawn = spawner or _spawn
    started = spawn(base_dir, port)
    code = 0 if started else RESTART_EXIT_CODE
    logger.info("%.1f초 뒤 이 대시보드를 종료합니다 (코드 %d)", delay, code)

    quit_now = (lambda: exiter(code)) if exiter else (lambda: os._exit(code))
    timer = threading.Timer(delay, quit_now)
    timer.daemon = True
    timer.start()
    return timer
