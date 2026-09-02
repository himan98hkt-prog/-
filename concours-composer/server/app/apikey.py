"""API 키를 받아 `.env` 에 넣는 한 곳.

키를 넣는 길이 둘이다 — 명령창(scripts/set_api_key.py)과 프로그램 화면. 규칙이
갈라지면 한쪽에서만 통과하는 키가 생기므로 검사·저장·가리기를 여기 모아 둔다.

키는 **프로젝트 .env 에서만** 읽고 시스템 환경변수에는 절대 넣지 않는다(원장 지시).
그래서 여기서도 파일에만 쓴다.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

NAME = "ANTHROPIC_API_KEY"
PREFIX = "sk-ant-"


def mask(key: str) -> str:
    return f"{key[:11]}…{key[-4:]}" if len(key) > 20 else "(너무 짧다)"


def looks_valid(key: str) -> str | None:
    """형식만 본다. 진짜 쓸 수 있는 키인지는 서버가 안다.

    맨 앞에서 **보이지 않는 글자**부터 잡는다. 윈도우 PowerShell 의 숨김 입력에서
    Ctrl+V 를 누르면 붙여넣기가 되지 않고 `\\x16` 한 글자가 들어간다. 화면에는
    아무것도 안 보이므로, "sk-ant- 로 시작해야 한다"고만 말하면 원장은 분명히
    키를 복사했는데 왜 틀렸다는지 알 길이 없다. 실제로 이 자리에서 막혔다.
    """
    if not key:
        return "아무것도 입력되지 않았다"
    if any(ord(c) < 32 for c in key):
        return (
            "붙여넣기가 되지 않았다 — 이 창에서는 Ctrl+V 가 듣지 않는다. "
            "마우스 오른쪽 버튼을 한 번 누르면 붙여넣어진다"
        )
    if key in ("sk-ant-...", PREFIX):
        return "예시 문자열 그대로다 — 콘솔에서 복사한 진짜 키를 넣어라"
    if not key.startswith(PREFIX):
        return f"Anthropic 키는 {PREFIX} 로 시작한다"
    if len(key) <= 20:
        return "키가 너무 짧다 — 복사가 잘렸는지 확인하라"
    if any(c.isspace() for c in key):
        return "가운데에 공백이나 줄바꿈이 섞여 있다 — 한 줄로 복사하라"
    return None


def clean(raw: str) -> str:
    """입력에서 군더더기만 떼어 낸다. 안쪽은 건드리지 않는다 — 검사가 봐야 한다."""
    return raw.strip().strip("\"'")


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
    # 같은 컴퓨터의 다른 계정이 읽지 못하게. 윈도우 파일 시스템에 따라 안 먹을 수
    # 있는데, 그렇다고 저장 자체를 막으면 본말이 뒤집힌다.
    with contextlib.suppress(OSError):
        env.chmod(0o600)
