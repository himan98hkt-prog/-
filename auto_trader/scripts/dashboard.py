#!/usr/bin/env python3
"""로컬 대시보드 실행.

    python scripts/dashboard.py            # http://127.0.0.1:8765
    python scripts/dashboard.py --port 9000

키를 입력·저장하고 매매를 정지할 수 있는 화면이므로 **127.0.0.1 에만 바인딩**한다.
원격에서 보려면 SSH 포트포워딩을 쓰세요:

    ssh -L 8765:127.0.0.1:8765 사용자@서버
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.app import create_app  # noqa: E402

HOST = "127.0.0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description="자동매매 로컬 대시보드")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true", help="개발용 자동 리로드")
    args = parser.parse_args()

    print("=" * 62)
    print(f"  대시보드: http://{HOST}:{args.port}")
    print("  · 설정 화면에서 API 키를 입력·저장하고 바로 점검할 수 있습니다")
    print("  · 외부에 노출되지 않습니다 (127.0.0.1 전용)")
    print("  · 중지: Ctrl+C")
    print("=" * 62)

    create_app().run(host=HOST, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
