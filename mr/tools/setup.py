#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""집 PC 에 반주 프로그램을 앉히고 띄운다.

두 번 눌러 실행하는 설치기다. 원장님은 이 파일을 직접 부르지 않는다 —
`install-windows.bat` 나 `install-mac.command` 가 부른다.

**표준 라이브러리만 쓴다.** 아무것도 안 깔린 PC 에서 제일 먼저 도는 코드라
`pip install` 이 필요한 것은 하나도 못 쓴다.

## 무엇을 깔고 무엇을 안 까는가

깔아야 하는 것은 **파이썬 하나뿐**이다. fluidsynth·SoundFont·ffmpeg 는
**안 깐다** — 실측으로 확인했다. 그 셋을 PATH 에서 숨기고 돌려도

    카탈로그 20곡 생성 · 꾸러미 133 KB · 브라우저 11항목 통과 · 재생 RMS 0.3638

가 그대로 나온다. 반주를 만들고 브라우저에서 듣는 데에는 필요가 없다.
그 셋은 **mp3·wav 로 구워 낼 때만** 쓰인다 (`piano_mr/render.py` 의
`require_tools` 가 그때만 불린다). 안 쓸 기능 때문에 설치에서 막히게 하는
것이 제일 나쁘다.

## 왜 venv 를 만드는가

시스템 파이썬에 직접 깔면 (1) 관리자 권한을 물을 수 있고 (2) 원장님 PC 의
다른 프로그램과 버전이 부딪칠 수 있다. `mr/.venv` 안에 따로 두면 지울 때도
폴더 하나만 지우면 된다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
import webbrowser

# 한글이 깨지지 않게. 윈도 콘솔은 기본이 UTF-8 이 아니다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

MR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(MR, '.venv')
CATALOG = os.path.join(MR, 'catalog')
PORT = 8765

# music21 9 가 요구하는 최소. 이보다 낮으면 pip 단계에서 알 수 없는 말로
# 실패하므로 여기서 먼저 잡고 사람이 읽을 수 있게 말한다.
MIN_PY = (3, 10)


def say(*a):
    print(*a, flush=True)


def line(ch='─', n=58):
    say(ch * n)


def venv_python() -> str:
    if os.name == 'nt':
        return os.path.join(VENV, 'Scripts', 'python.exe')
    return os.path.join(VENV, 'bin', 'python')


def run(argv, **kw) -> int:
    """하위 명령을 돌린다. 실패하면 그대로 돌려준다 (죽이지 않는다)."""
    return subprocess.call(argv, cwd=MR, **kw)


def check_python() -> bool:
    if sys.version_info >= MIN_PY:
        return True
    have = '.'.join(str(x) for x in sys.version_info[:3])
    need = '.'.join(str(x) for x in MIN_PY)
    say(f'파이썬이 너무 낮습니다 — 지금 {have}, {need} 이상이 필요합니다.')
    say('')
    if os.name == 'nt':
        say('  python.org 에서 최신판을 받아 설치하세요.')
        say('  설치 첫 화면의 **「Add python.exe to PATH」를 꼭 체크**하셔야 합니다.')
    else:
        say('  python.org 에서 최신판을 받거나, Homebrew 가 있으면')
        say('    brew install python')
    return False


def make_venv() -> bool:
    py = venv_python()
    if os.path.exists(py):
        return True
    say('① 프로그램이 쓸 자리를 만듭니다 … (한 번만 합니다)')
    try:
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    except Exception as e:
        say(f'   실패했습니다: {e}')
        return False
    return os.path.exists(py)


# 이게 다 import 되면 더 받을 게 없다. `pip install` 은 다 깔려 있어도
# 매번 인터넷을 두드리므로, 인터넷이 없는 날 여기서 한참 붙들린다.
NEEDED = ('music21', 'mido', 'fastapi', 'uvicorn')

# `python-multipart` 는 import 이름을 바꾸는 중이다 — 옛 판은 `multipart`,
# 새 판은 `python_multipart` 이고 옛 이름은 경고를 내며 사라질 예정이다.
# **둘 중 하나만 되면 깔려 있는 것**이다. 하나로 못 박으면 반대쪽 판이
# 깔린 PC 에서 매번 다시 받게 된다.
NEEDED_EITHER = (('python_multipart', 'multipart'),)


def _probe_code() -> str:
    lines = [f'import {m}' for m in NEEDED]
    for names in NEEDED_EITHER:
        # 하나씩 해 보고 다 실패하면 ImportError 로 떨어진다
        body = ' or '.join(f'_try({n!r})' for n in names)
        lines.append(f'assert {body}')
    return ('def _try(n):\n'
            ' try:\n'
            '  __import__(n); return True\n'
            ' except Exception:\n'
            '  return False\n'
            + '\n'.join(lines))


def deps_ok() -> bool:
    py = venv_python()
    if not os.path.exists(py):
        return False
    return run([py, '-c', _probe_code()],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def install_deps() -> bool:
    if deps_ok():
        return True                       # 두 번째부터는 조용히 지나간다
    py = venv_python()
    req = os.path.join(MR, 'requirements.txt')
    say('② 필요한 것들을 내려받습니다 … (인터넷이 필요하고 1~3분 걸립니다)')
    run([py, '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'])
    code = run([py, '-m', 'pip', 'install', '--quiet', '-r', req])
    if code != 0:
        say('')
        say('   내려받기에 실패했습니다. 인터넷 연결을 확인하고 다시 눌러 주세요.')
        say('   회사망이나 백신이 막는 경우도 있습니다.')
        return False
    return True


def seed() -> bool:
    """처음이면 연습곡 20곡을 넣어 둔다 — 빈 화면으로 시작하지 않게."""
    if os.path.exists(os.path.join(CATALOG, 'catalog.json')):
        return True
    say('③ 연습곡을 넣습니다 … (처음 한 번, 30초쯤)')
    # 인터넷에서 받아오는 코퍼스 곡은 건너뛴다. 없어도 20곡으로 충분하고,
    # 그 곡들은 입력본 출처가 확인 안 돼 어차피 판매용에서 빠진다.
    code = run([venv_python(), 'seed_catalog.py', '--catalog', CATALOG,
                '--skip-corpus'], stdout=subprocess.DEVNULL)
    if code != 0:
        say('   연습곡을 못 넣었습니다. 그래도 프로그램은 뜹니다 — 곡을 직접 넣으시면 됩니다.')
    return True


def serve():
    py = venv_python()
    url = f'http://127.0.0.1:{PORT}/'
    line()
    say('  준비됐습니다.')
    say('')
    say(f'  곡 목록·반주 만들기   {url}')
    say(f'  아이가 연습하는 화면   {url}static/player/')
    say(f'  발표회 운영 화면       {url}static/program.html')
    say('')
    say('  ※ 이 검은 창을 닫으면 프로그램도 꺼집니다. 쓰시는 동안 열어 두세요.')
    line()
    say('')
    try:
        webbrowser.open(url)
    except Exception:
        pass
    run([py, 'serve.py', '--catalog', CATALOG, '--port', str(PORT)])


def main() -> int:
    line('═')
    say('  피아노 학원 반주 프로그램')
    line('═')
    say('')
    if not check_python():
        return 1
    if not make_venv():
        return 1
    if not install_deps():
        return 1
    seed()
    serve()
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except KeyboardInterrupt:
        say('')
        say('  껐습니다.')
        code = 0
    if code != 0:
        say('')
        try:
            input('  엔터를 누르면 창이 닫힙니다. ')
        except Exception:
            pass
    sys.exit(code)
