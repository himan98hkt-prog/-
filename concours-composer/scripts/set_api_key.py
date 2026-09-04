#!/usr/bin/env python3
"""ANTHROPIC_API_KEY 를 프로젝트 `.env` 에 안전하게 넣는다.

키를 명령줄 인자로 받지 않는다 — 인자로 받으면 셸 기록(~/.bash_history)과 프로세스
목록에 그대로 남는다. 화면에도 찍지 않고, 저장한 뒤에도 가려서만 보여 준다.

    .venv/bin/python scripts/set_api_key.py

키는 **이 파일에서만** 읽힌다(app/config.py). 시스템 환경변수는 쓰지 않는다.
`.env` 는 .gitignore 에 있으므로 커밋되지 않는다.

검사·저장 규칙은 `app/apikey.py` 한 곳에 있다 — 화면에서 넣는 길과 규칙이
갈라지면 한쪽에서만 통과하는 키가 생기기 때문이다.
"""

from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.apikey import NAME, clean, looks_valid, mask, write_key  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / ".env"), help="쓸 .env 경로")
    args = ap.parse_args()
    env = Path(args.file)

    print("Anthropic 콘솔에서 만든 키를 붙여 넣어라. 화면에는 보이지 않는다.")
    print("  https://console.anthropic.com/settings/keys")
    # 윈도우 PowerShell 의 숨김 입력에서는 Ctrl+V 가 듣지 않는다. 미리 말해 주지
    # 않으면 반드시 한 번 막힌다 — 실제로 막혔다.
    print("  붙여넣기는 마우스 오른쪽 버튼 한 번. (Ctrl+V 는 이 창에서 듣지 않는다)")
    print("  프로그램 화면 오른쪽 위 '설정' 에서 넣는 편이 더 쉽다.\n")
    try:
        key = clean(getpass(f"{NAME}: "))
    except (EOFError, KeyboardInterrupt):
        print("\n취소했다 — 아무것도 바꾸지 않았다")
        return 1

    problem = looks_valid(key)
    if problem:
        print(f"\n넣지 않았다: {problem}", file=sys.stderr)
        return 2

    write_key(env, key)
    print(f"\n{env} 에 저장했다 · {mask(key)}")
    print("이전 파일은 .env.bak 로 남겼다. 서버를 다시 시작하면 적용된다.")
    print("확인:  .venv/bin/python scripts/self_check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
