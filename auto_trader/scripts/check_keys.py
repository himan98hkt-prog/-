#!/usr/bin/env python3
"""발급받은 키가 실제로 동작하는지 하나씩 확인한다.

`.env` 를 채운 직후 가장 먼저 실행하세요. 각 항목을 **독립적으로** 검사하므로
일부 키만 넣은 상태에서도 돌릴 수 있고, 실패한 항목의 원인을 그대로 보여줍니다.

    python scripts/check_keys.py
    python scripts/check_keys.py --telegram-test   # 텔레그램 테스트 메시지 발송
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values  # noqa: E402

from utils.key_check import FAIL, run_all, summarize  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def main() -> int:
    parser = argparse.ArgumentParser(description="발급받은 키 동작 확인")
    parser.add_argument("--telegram-test", action="store_true", help="텔레그램 테스트 메시지 실제 발송")
    args = parser.parse_args()

    if not ENV_PATH.exists():
        print(f"❌ .env 가 없습니다: {ENV_PATH}")
        print("   먼저 `cp .env.example .env` 후 키를 입력하세요.")
        print("   또는 `python scripts/dashboard.py` 를 띄워 브라우저에서 입력할 수 있습니다.")
        return 1

    env = dotenv_values(ENV_PATH)
    polluted = [key for key, value in env.items() if value and value.strip().startswith("#")]
    if polluted:
        print(f"❌ 값 자리에 주석이 들어간 항목: {', '.join(polluted)}")
        print("   `KEY=값` 뒤에 주석을 달지 마세요. 설명은 윗줄에 둡니다.")
        return 1

    print("=" * 70)
    print(f"키 점검 — {ENV_PATH}")
    print(f"모드: KIS_ENV={env.get('KIS_ENV') or 'VTS'} / DRY_RUN={env.get('DRY_RUN') or 'true'}")
    print("=" * 70)

    results = run_all(env, telegram_test=args.telegram_test)
    for result in results:
        print(result.line())

    counts = summarize(results)
    print("-" * 70)
    if counts["fail"]:
        print(f"❌ {counts['fail']}개 항목이 실패했습니다. 위 메시지를 확인해 .env 를 고친 뒤 다시 실행하세요.")
        return 1
    if counts["required_missing"]:
        print(f"⏭️  {counts['required_missing']}개 항목이 미입력 상태입니다. 전부 채워야 프로그램이 기동합니다.")
        return 1
    print("✅ 모든 키가 정상입니다. 다음: python main.py --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
