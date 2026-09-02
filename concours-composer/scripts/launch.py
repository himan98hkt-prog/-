#!/usr/bin/env python3
"""바탕화면 아이콘이 부르는 실행기.

원장이 하는 일은 아이콘을 한 번 누르는 것뿐이어야 한다. 검은 명령창도, 주소를
외워 치는 일도 없어야 한다. 그래서 이 파일이 대신 한다.

    이미 켜져 있나  →  브라우저만 연다 (서버를 두 개 띄우지 않는다)
    꺼져 있나       →  서버를 띄우고, 뜬 것을 확인한 뒤 브라우저를 연다

끄는 것은 화면 안의 '프로그램 끄기' 버튼이다(POST /api/shutdown). 명령창이 없으니
Ctrl+C 를 누를 곳도 없기 때문이다.

윈도우 바로가기는 `pythonw.exe` 로 이 파일을 부른다 — 그래야 검은 창이 안 뜬다.
다만 검은 창이 없다는 것은 **오류도 안 보인다**는 뜻이다. 아이콘을 눌렀는데 아무 일도
일어나지 않으면 원장은 무엇을 해야 할지 알 수 없다. 그래서 여기서 일어난 일을
`실행기록.txt` 에 적고, 실패하면 **창을 띄워** 무엇이 잘못됐는지 보여 준다.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_PORT = 8000
HOST = "127.0.0.1"
LOG = ROOT / "실행기록.txt"


def note(line: str) -> None:
    """무슨 일이 있었는지 파일에 남긴다. 기록이 없으면 물어볼 것도 없다."""
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {line}\n")
    except OSError:
        pass  # 기록을 못 남긴다고 실행을 막지 않는다


def tell(title: str, body: str) -> None:
    """원장에게 보이게 말한다.

    pythonw 로 띄우면 print 는 아무 데도 안 나온다 — 아이콘을 눌렀는데 아무 일도
    없는 것처럼 보이는 이유가 이것이다. 윈도우면 안내창을 띄우고, 아니면 화면에 찍는다.
    """
    note(f"[알림] {title} / {body}")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, body, title, 0x40)  # 0x40 = 정보 아이콘
            return
        except Exception:  # 안내창을 못 띄워도 아래로 내려가 찍는다
            pass
    print(f"{title}\n{body}")


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
    note("아이콘을 눌렀다 — 실행을 시작한다")
    port = pick_port()
    url = f"http://{HOST}:{port}/"

    if already_running(port):
        note(f"이미 켜져 있다 — 브라우저만 연다 ({url})")
        webbrowser.open(url + "app/")
        return 0

    import uvicorn
    from app.main import app

    note(f"서버를 띄운다 ({url})")

    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # 화면의 '프로그램 끄기' 버튼이 이 손잡이를 잡는다.
    app.state.server = server

    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    server.run()
    return 0


def guarded() -> int:
    """실패해도 조용히 사라지지 않게 감싼다.

    아이콘을 눌렀는데 아무 일도 일어나지 않는 것이 원장에게는 가장 나쁘다 —
    고장인지, 느린 건지, 자기가 잘못 누른 건지 알 수가 없다.
    """
    try:
        return main()
    except ImportError as e:
        tell(
            "콩쿨 작곡기 — 부품이 빠졌습니다",
            f"프로그램에 필요한 부품이 설치되지 않았습니다.\n\n"
            f"    {e}\n\n"
            f"이 폴더의 '설치.bat' 을 두 번 눌러 설치를 다시 하십시오.\n"
            f"설치가 끝나면 이 아이콘이 정상으로 돌아갑니다.\n\n"
            f"자세한 기록: {LOG}",
        )
        return 1
    except OSError as e:
        tell(
            "콩쿨 작곡기 — 켜지 못했습니다",
            f"{e}\n\n"
            f"다른 프로그램이 같은 자리를 쓰고 있을 수 있습니다.\n"
            f"컴퓨터를 다시 켠 뒤 아이콘을 다시 눌러 보십시오.\n\n"
            f"자세한 기록: {LOG}",
        )
        return 1
    except Exception:  # 무엇이 됐든 원장에게는 보여야 한다
        note(traceback.format_exc())
        tell(
            "콩쿨 작곡기 — 뜻밖의 오류",
            f"프로그램을 켜는 중에 문제가 생겼습니다.\n\n"
            f"{traceback.format_exc(limit=1).strip()}\n\n"
            f"이 폴더의 '실행기록.txt' 를 보내 주시면 원인을 찾을 수 있습니다.\n"
            f"    {LOG}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(guarded())
