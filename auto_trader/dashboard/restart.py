"""업데이트 후 대시보드 자신을 다시 띄우기 위한 장치.

파이썬은 모듈을 **처음 import 할 때 한 번만** 읽는다. 업데이트가 디스크의
`dashboard/env_file.py` 를 바꿔도, 이미 돌고 있는 대시보드는 예전 화면을 계속
그린다(새 입력칸이 안 생긴다). 그래서 업데이트가 끝나면 대시보드 프로세스를
통째로 교체해야 한다.

방법은 '약속된 종료 코드로 죽고, 실행 스크립트가 다시 띄운다' 이다.
start.bat / start.sh 가 이 코드를 보면 루프를 한 번 더 돈다.
"""

from __future__ import annotations

import os
import threading

from utils.logger import get_logger

logger = get_logger("restart")

# start.bat / start.sh 와 약속된 값. 바꾸려면 양쪽을 같이 고쳐야 한다.
RESTART_EXIT_CODE = 42

# 응답이 브라우저에 도착할 시간을 준 뒤에 죽는다.
GRACE_SEC = 1.5


def request_restart(*, delay: float = GRACE_SEC, exiter=None) -> threading.Timer:
    """응답을 보낸 뒤 대시보드를 재기동한다.

    `os._exit` 를 쓰는 이유: Flask 개발 서버는 요청 처리 스레드 안에서 깔끔히
    멈출 방법이 마땅치 않고, 여기서 정리해야 할 상태도 없다. 매매 프로세스는
    별개라 이 종료에 영향받지 않는다.
    """
    logger.info("업데이트 완료 — %.1f초 뒤 대시보드를 다시 띄웁니다", delay)
    quit_now = exiter or (lambda: os._exit(RESTART_EXIT_CODE))
    timer = threading.Timer(delay, quit_now)
    timer.daemon = True
    timer.start()
    return timer
