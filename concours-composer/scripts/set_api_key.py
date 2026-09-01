#!/usr/bin/env python3
"""ANTHROPIC_API_KEY 를 프로젝트 `.env` 에 안전하게 넣는다.

키를 명령줄 인자로 받지 않는다 — 인자로 받으면 셸 기록(~/.bash_history)과 프로세스
목록에 그대로 남는다. 화면에도 찍지 않고, 저장한 뒤에도 가려서만 보여 준다.

    .venv/bin/python scripts/set_api_key.py

키는 **이 파일에서만** 읽힌다(app/config.py). 시스템 환경변수는 쓰지 않는다.
`.env` 는 .gitignore 에 있으므로 커밋되지 않는다.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "ANTHROPIC_API_KEY"


def mask(key: str) -> str:
    return f"{key[:11]}…{key[-4:]}" if len(key) > 20 else "(너무 짧다)"


def looks_valid(key: str) -> str | None:
    """형식만 본다. 진짜 쓸 수 있는 키인지는 서버가 안다."""
    if not key:
        return "아무것도 입력되지 않았다"
    if key in ("sk-ant-...", "sk-ant-"):
        return "예시 문자열 그대로다 — 콘솔에서 복사한 진짜 키를 넣어라"
    if not key.startswith("sk-ant-"):
        return "Anthropic 키는 sk-ant- 로 시작한다"
    if len(key) <= 20:
        return "키가 너무 짧다 — 복사가 잘렸는지 확인하라"
    if any(c.isspace() for c in key):
        return "가운데에 공백이나 줄바꿈이 섞여 있다 — 한 줄로 복사하라"
    return None


def write_key(env: Path, key: str) -> None:
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    out, found = [], False
    for raw in lines:
        name = raw.split("=", 1)[0].strip()
        if name == NAME and not raw.lstrip().startswith("#"):
            out.append(f"{NAME}={key}")
            found = True
        else:
            out.append(raw)
    if not found:
        out.insert(0, f"{NAME}={key}")
    if env.exists():
        # with_suffix 는 이름이 `.env` 일 때 `.env.env.bak` 을 만든다 — 이름을 직접 붙인다.
        shutil.copy2(env, env.with_name(env.name + ".bak"))
    env.write_text("\n".join(out) + "\n", encoding="utf-8")
    env.chmod(0o600)          # 같은 컴퓨터의 다른 계정이 읽지 못하게


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / ".env"), help="쓸 .env 경로")
    args = ap.parse_args()
    env = Path(args.file)

    print("Anthropic 콘솔에서 만든 키를 붙여 넣어라. 화면에는 보이지 않는다.")
    print("  https://console.anthropic.com/settings/keys\n")
    try:
        key = getpass(f"{NAME}: ").strip().strip("\"'")
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
