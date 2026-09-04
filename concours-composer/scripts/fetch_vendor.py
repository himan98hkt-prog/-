#!/usr/bin/env python3
"""악보 렌더러·음원 라이브러리를 web/vendor/ 에 받아 둔다.

받아 두면 그 뒤로는 **인터넷 없이도** 정식 악보가 그려지고 피아노 음색이 난다.
받지 못해도 프로그램은 그대로 돈다 — 화면의 '간이 악보'와 내장 음원이 대신한다.
그래서 이 스크립트는 실패해도 0 으로 끝난다(설치를 막지 않는다).
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "web" / "vendor"

FILES: list[tuple[str, str]] = [
    (
        "opensheetmusicdisplay.min.js",
        "https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.7/build/opensheetmusicdisplay.min.js",
    ),
    ("Tone.js", "https://cdn.jsdelivr.net/npm/tone@14.8.49/build/Tone.js"),
]


def fetch(name: str, url: str) -> bool:
    out = VENDOR / name
    if out.exists() and out.stat().st_size > 10_000:
        print(f"  이미 있음  {name}")
        return True
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"  못 받음    {name} — {e}")
        return False
    if len(data) < 10_000:
        print(f"  이상함     {name} — {len(data)} 바이트라 버린다")
        return False
    out.write_bytes(data)
    print(f"  받음       {name} ({len(data) // 1024} KB)")
    return True


def main() -> int:
    VENDOR.mkdir(parents=True, exist_ok=True)
    print("악보 렌더러·음원 라이브러리를 web/vendor/ 에 받는다")
    got = [fetch(n, u) for n, u in FILES]
    if all(got):
        print("완료 — 이제 인터넷 없이도 정식 악보와 피아노 음색을 쓸 수 있다.")
    else:
        print("일부를 받지 못했다. 프로그램은 그대로 돈다 —")
        print("  악보: 내장 '간이 악보'로 보이고, 재생 막대도 그 위에서 움직인다.")
        print("  소리: 내장 음원으로 난다.")
        print("인터넷이 되는 곳에서 다시 실행하면 채워진다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
