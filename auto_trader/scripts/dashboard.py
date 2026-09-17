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
import logging
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import LOG_DIR  # noqa: E402
from dashboard.app import create_app  # noqa: E402
from utils.browser import open_when_ready  # noqa: E402
from utils.logger import setup_logging  # noqa: E402

HOST = "127.0.0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description="자동매매 로컬 대시보드")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true", help="개발용 자동 리로드")
    parser.add_argument(
        "--open-browser", action="store_true",
        help="서버가 뜬 뒤 브라우저를 연다 (start.sh / start.bat 이 사용)",
    )
    args = parser.parse_args()

    # 로깅을 먼저 세운다. 이유가 둘이다.
    #  1) 출력이 UTF-8 이 된다 — Windows 한글 기본값 cp949 에는 em-dash(—)가 없어서,
    #     그 문자가 섞인 한 줄에 출력이 터진다(매매 프로세스가 실제로 그랬다).
    #  2) 화면에 뜨는 것이 파일에도 남는다. 창이 닫혀 버리면 그동안은 아무 단서도
    #     남지 않아, 무엇 때문에 죽었는지 알 길이 없었다.
    setup_logging("INFO", LOG_DIR, prefix="dashboard")

    print("=" * 62)
    print(f"  대시보드: http://{HOST}:{args.port}")
    print("  · 설정 화면에서 API 키를 입력·저장하고 바로 점검할 수 있습니다")
    print("  · 외부에 노출되지 않습니다 (127.0.0.1 전용)")
    print("  · 중지: Ctrl+C")
    print("=" * 62)

    if args.open_browser:
        # 서버가 준비된 뒤에 연다 — 먼저 열면 "연결할 수 없음" 이 뜬다.
        open_when_ready(HOST, args.port)

    app = create_app()
    app.config["PORT"] = args.port  # 업데이트 후 같은 포트로 다시 띄우기 위함
    try:
        app.run(host=HOST, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n중지했습니다.")
    except Exception:
        # 창이 그냥 사라지면 원인을 볼 수 없다. 로그에 남기고 화면에도 띄운다.
        logging.getLogger("dashboard").exception("대시보드가 예기치 않게 종료됐습니다")
        print("\n" + "=" * 62)
        print("  대시보드가 멈췄습니다. 아래 내용을 그대로 전달해 주세요.")
        print("=" * 62)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
