#!/usr/bin/env python3
"""터미널에서 API 키를 입력해 `.env` 를 만든다.

브라우저를 쓸 수 없을 때(SSH 접속 등) 쓰는 입력 방법입니다. 브라우저가 되면
`./start.sh` 로 대시보드 설정 화면을 쓰는 편이 편합니다.

    python scripts/setup_keys.py            # 전체 항목을 순서대로 묻는다
    python scripts/setup_keys.py --missing  # 아직 안 채운 필수 항목만 묻는다
    python scripts/setup_keys.py --check    # 저장 후 키 점검까지 이어서 실행

비밀값은 화면에 찍히지 않고(getpass), 저장된 `.env` 는 권한 0600 으로 좁혀집니다.
이미 값이 있는 칸은 그냥 Enter 를 치면 유지되고, 지우려면 `-` 를 입력하세요.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.env_file import (  # noqa: E402
    DEFAULTS,
    GROUPS,
    missing_required,
    read_env,
    required_keys,
    write_env,
)
from config.loader import mask  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

CLEAR_TOKEN = "-"  # 사용자가 값을 지우겠다고 표시하는 입력
LINE = "─" * 66


def _current_display(key: str, secret: bool, env: dict[str, str]) -> str:
    """지금 저장돼 있는 값을 사람이 볼 수 있는 형태로."""
    value = env.get(key, "")
    if not value:
        return "(비어 있음)"
    return mask(value) if secret else value


def _prompt_once(meta, env: dict[str, str], required: bool) -> str | None:
    """항목 하나를 묻는다. Enter(유지) 면 None.

    `required` 는 meta.required 가 아니라 **지금 값 기준**으로 계산한다.
    알림 채널을 telegram 으로 고르면 봇 토큰이 필수가 되는 식이다.
    """
    current = _current_display(meta.key, meta.secret, env)
    print(f"\n  {meta.label}  [{meta.key}]")
    if meta.help:
        print(f"    · {meta.help}")
    if meta.choices:
        allowed = ", ".join(c or "(비움)" for c in meta.choices)
        print(f"    · 선택: {allowed}")
    if meta.placeholder:
        print(f"    · 예시: {meta.placeholder}")
    print(f"    · 현재: {current}")

    suffix = " (Enter=유지)" if env.get(meta.key) else ""
    prompt = f"    입력{suffix}> "

    while True:
        raw = getpass.getpass(prompt) if meta.secret else input(prompt)
        value = raw.strip().strip('"').strip("'")

        if not value:
            if env.get(meta.key) or not required:
                return None
            default = DEFAULTS.get(meta.key)
            if default:
                print(f"    → 기본값 {default} 을 씁니다")
                return default
            print("    ! 필수 항목입니다. 값을 입력하세요.")
            continue

        if value == CLEAR_TOKEN:
            if required:
                print("    ! 필수 항목이라 비울 수 없습니다.")
                continue
            return "__CLEAR__"

        if meta.choices and value not in meta.choices:
            print(f"    ! {', '.join(c for c in meta.choices if c)} 중에서 골라 주세요.")
            continue

        return value


def _should_ask(meta, env: dict[str, str], missing_only: bool) -> bool:
    if not missing_only:
        return True
    return meta.key in set(required_keys(env)) and not env.get(meta.key)


def main() -> int:
    parser = argparse.ArgumentParser(description="터미널에서 API 키 입력")
    parser.add_argument("--missing", action="store_true", help="비어 있는 필수 항목만 묻는다")
    parser.add_argument("--check", action="store_true", help="저장 후 키 점검을 이어서 실행")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("❌ 대화형 터미널이 아닙니다. 키를 파이프로 넘기지 마세요.")
        print("   브라우저에서 입력하려면: ./start.sh")
        return 1

    print(LINE)
    print("  API 키 입력 — 저장 위치:", ENV_PATH)
    print("  · Enter = 기존 값 유지 / `-` 입력 = 값 지우기 / Ctrl+C = 취소")
    print("  · 비밀값은 화면에 표시되지 않습니다")
    print(LINE)

    env = read_env(ENV_PATH)
    updates: dict[str, str] = {}

    try:
        for group in GROUPS:
            fields = [f for f in group.fields if _should_ask(f, env, args.missing)]
            if not fields:
                continue
            print(f"\n[{group.title}]")
            if group.description:
                print(f"  {group.description}")
            for meta in fields:
                # NOTIFIER 를 방금 고쳤다면 그 값 기준으로 이어지는 항목을 판단한다.
                answer = _prompt_once(meta, env, meta.key in set(required_keys(env)))
                if answer is not None:
                    updates[meta.key] = answer
                    env_value = "" if answer == "__CLEAR__" else answer
                    env = {**env, meta.key: env_value}
    except (KeyboardInterrupt, EOFError):
        print("\n\n취소했습니다. `.env` 는 그대로 둡니다.")
        return 130

    if not updates:
        print("\n바뀐 값이 없습니다.")
    else:
        changed = write_env(ENV_PATH, updates)
        print(f"\n✅ 저장했습니다 — {len(changed)}개 항목 변경: {', '.join(changed)}")
        print(f"   {ENV_PATH} (권한 0600)")

    still_missing = missing_required(ENV_PATH)
    if still_missing:
        print(f"\n⚠️  아직 비어 있는 필수 항목: {', '.join(still_missing)}")
        print("   `python scripts/setup_keys.py --missing` 으로 마저 채우세요.")
        return 1

    print("\n필수 항목이 모두 채워졌습니다.")
    if args.check:
        print()
        from utils.key_check import run_all, summarize  # 지연 import — 네트워크 의존

        results = run_all(read_env(ENV_PATH))
        for result in results:
            print(result.line())
        if summarize(results)["fail"]:
            return 1
    else:
        print("다음: python scripts/check_keys.py   (키가 실제로 동작하는지 확인)")
        print("      ./start.sh                     (대시보드에서 자동매매 시작)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
