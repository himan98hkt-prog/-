"""저장소 뿌리를 찾아 `server` 를 import 경로에 넣는다.

세션 작곡 도구는 서버 코드(검증기·지표·스키마)를 그대로 쓴다. 설치 없이 돌리기 위해
경로만 맞춰 준다 — 이 파일이 `tools/notation/` 안에 있다는 것만 가정한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "golden"

for _p in (ROOT / "server", ROOT / "server" / "tests" / "golden", Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
