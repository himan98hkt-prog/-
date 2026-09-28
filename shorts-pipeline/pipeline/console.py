"""출력 인코딩 때문에 죽지 않게 한다.

**매일 자동 업로드가 한 번도 안 돌던 이유가 여기 있었다.**

한국어 윈도우에서 파이썬의 출력을 파일로 돌리면(`>> cron.log`) 인코딩이
cp949 가 된다. cp949 에는 `—` `✓` `✗` `⚠` 가 없다. 그래서 예약 실행은
첫 로그 줄 `▶ 시드 city_01.png — 「...」` 을 찍는 순간 UnicodeEncodeError 로
죽었다. 영상을 만들기도 전에, 이력(schedule.log)에 한 줄 남기기도 전에.

작업실에서 누르면 멀쩡했던 건 작업실이 자식 프로세스에
PYTHONIOENCODING=utf-8 을 넣어주기 때문이다(ui/jobs.py). 예약 실행에는
그게 없었다.

그래서 **어디서 실행되든** 출력 인코딩 오류로는 죽지 않게 한다.
"""

from __future__ import annotations

import os
import sys

# 자식 파이썬(main.py generate 등)에도 넘길 환경. 부모만 고치면 자식이 죽는다.
UTF8_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def make_safe() -> None:
    """stdout/stderr 가 어떤 글자를 만나도 예외를 내지 않게 한다.

    파일이나 파이프로 나갈 때는 UTF-8 로 쓴다. 로그를 읽는 쪽(작업실)이
    UTF-8 로 읽기 때문이다. 콘솔에 직접 찍을 때는 인코딩은 그대로 두고
    못 그리는 글자만 `?` 로 바꾼다.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:                       # pythonw 에서는 None 이다
            continue
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """자식 프로세스용 환경변수. UTF-8 을 강제한다."""
    env = dict(os.environ)
    env.update(UTF8_ENV)
    if extra:
        env.update(extra)
    return env
