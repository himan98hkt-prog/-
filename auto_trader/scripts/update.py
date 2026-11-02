#!/usr/bin/env python3
"""최신 코드를 받아 제자리에 적용한다.

    python scripts/update.py            # 새 버전이 있으면 적용
    python scripts/update.py --check    # 확인만 하고 적용하지 않는다
    python scripts/update.py --force    # 최신이어도 다시 받아 덮어쓴다

`.env`(키), `data/`(DB), `logs/` 는 건드리지 않습니다. 몇 번을 업데이트해도
키를 다시 입력할 일이 없습니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import process  # noqa: E402
from utils import updater  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LINE = "─" * 62


def main() -> int:
    parser = argparse.ArgumentParser(description="최신 버전으로 업데이트")
    parser.add_argument("--check", action="store_true", help="확인만 하고 적용하지 않는다")
    parser.add_argument("--force", action="store_true", help="최신이어도 다시 받는다")
    args = parser.parse_args()

    print(LINE)
    print("  업데이트 확인")
    print(LINE)

    try:
        available, current, latest = updater.check(BASE_DIR)
    except updater.UpdateError as exc:
        print(f"❌ {exc}")
        return 1

    print(f"  현재: {current.short}  {current.message or ''}")
    print(f"  최신: {latest.short}  {latest.message or ''}")

    if not available and not args.force:
        print("\n✅ 이미 최신 버전입니다.")
        return 0
    if args.check:
        print("\n⬆️  새 버전이 있습니다. `python scripts/update.py` 로 적용하세요.")
        return 0

    if process.is_running(DATA_DIR):
        print("\n❌ 자동매매가 실행 중입니다.")
        print("   대시보드에서 '봇 종료' 를 누른 뒤 다시 시도하거나,")
        print("   대시보드의 '⬆️ 업데이트' 버튼을 쓰세요 (알아서 멈췄다 다시 띄웁니다).")
        return 1

    print("\n· 내려받는 중...")
    try:
        result = updater.apply_update(BASE_DIR)
    except updater.UpdateError as exc:
        print(f"❌ {exc}")
        print("   기존 설치는 그대로입니다.")
        return 1

    print(f"\n✅ {result.version.short} 로 업데이트했습니다 — {result.version.message}")
    print(f"   갱신한 항목 {len(result.changed)}개")
    print("   API 키와 매매 기록은 그대로입니다.")
    for note in result.notes:
        print(f"   · {note}")
    if result.deps_changed:
        print("\n   start.bat (또는 ./start.sh) 을 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
