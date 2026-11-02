#!/usr/bin/env python3
"""부팅 직후 자동매매를 다시 띄운다 (boot.bat 이 호출한다).

재부팅으로 매매가 멈춰 있는 시간을 줄이는 것이 목적이다. 설정이 온전하지
않거나 이미 돌고 있으면 아무것도 하지 않는다 — 중복 실행은 PID 락이 막지만
여기서 먼저 확인해 로그를 깔끔하게 남긴다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import process  # noqa: E402
from dashboard.env_file import missing_required  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
ENV_PATH = BASE_DIR / ".env"


def main() -> int:
    if not ENV_PATH.exists():
        print("· .env 가 없습니다 — 자동 시작을 건너뜁니다")
        return 0

    missing = missing_required(ENV_PATH)
    if missing:
        print(f"· 설정이 덜 됐습니다({', '.join(missing)}) — 자동 시작을 건너뜁니다")
        return 0

    if process.is_running(DATA_DIR):
        print("· 이미 실행 중입니다")
        return 0

    result = process.start(BASE_DIR, DATA_DIR, LOG_DIR)
    print(("✅ " if result.ok else "❌ ") + result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
