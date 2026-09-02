"""API 키를 프로그램 화면에서 넣는다.

명령창에 키를 붙여넣게 하는 것은 원터치가 아니다. 게다가 윈도우 PowerShell 의
숨김 입력에서는 Ctrl+V 가 듣지 않아, 분명히 복사했는데 "sk-ant- 로 시작해야
한다"는 말만 나온다. 브라우저 입력칸에서는 Ctrl+V 가 늘 된다.

키는 이 PC 에서만 넣을 수 있고, 저장은 프로젝트 `.env` 파일에만 한다.
화면으로 돌려줄 때는 언제나 가려서 준다 — 넣은 키를 다시 읽어 갈 길은 없다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.apikey import clean, looks_valid, mask, write_key
from app.config import ENV_FILE, get_settings, read_api_key_from_env_file

router = APIRouter(prefix="/api/api-key", tags=["api-key"])


class KeyIn(BaseModel):
    key: str = Field(min_length=1, max_length=500)


def _only_here(request: Request) -> None:
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 넣을 수 있다")


def _state() -> dict:
    """지금 .env 에 쓸 수 있는 키가 있는가.

    "글자가 들어 있는가" 로 보면 안 된다. `.env.example` 을 복사해 만들기 때문에
    처음에는 예시 문자열 `sk-ant-...` 가 들어 있고, 그것을 키로 세면 화면은
    "클로드가 작곡합니다" 라고 말해 놓고 첫 호출에서 인증 오류로 죽는다.
    쓸 수 있는 형식인지까지 봐야 화면의 말과 실제가 어긋나지 않는다.
    """
    key = read_api_key_from_env_file()
    usable = bool(key) and looks_valid(key) is None
    return {
        "present": usable,
        "masked": mask(key) if usable else "",
        "file": str(ENV_FILE),
        "engine": "claude" if usable else "stub-rule-based",
    }


@router.get("")
def status() -> dict:
    """키가 들어 있는지, 가린 모양은 어떤지. 키 자체는 절대 돌려주지 않는다."""
    return _state()


@router.put("")
def put_key(body: KeyIn, request: Request) -> dict:
    _only_here(request)
    key = clean(body.key)
    problem = looks_valid(key)
    if problem:
        raise HTTPException(400, problem)
    write_key(ENV_FILE, key)
    get_settings.cache_clear()
    return {**_state(), "saved": True, "note": "이전 파일은 .env.bak 로 남겼습니다"}


@router.delete("")
def clear_key(request: Request) -> dict:
    """키를 지우고 무료 스텁으로 되돌린다 — PC 를 넘기거나 팔 때 쓴다."""
    _only_here(request)
    write_key(ENV_FILE, "")
    get_settings.cache_clear()
    return {**_state(), "saved": True}
