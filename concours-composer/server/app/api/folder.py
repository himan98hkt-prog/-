"""**곡을 어느 폴더에 쌓을지 원장님이 정하신다.**

원장님:

    "클로드에 만들고 다운받은 곡에 대한 전체 내용들을 저장할 수 있는
     폴더 설정도 할 수 있었으면 좋겠어."

    "실질적인 작곡 작업은 집pc로 진행할 계획이니..."

두 말씀이 한 가지를 가리킨다. 지금은 곡을 꺼내면 언제나 같은 자리
(`%LOCALAPPDATA%\\ConcoursComposer\\내보낸 곡`)에 떨어진다. 그 자리는 안전하지만
**원장님이 고르신 자리가 아니다.** 집 PC 와 학원 PC 를 오가시려면 동기화 폴더
(원드라이브·구글 드라이브)나 USB 를 가리킬 수 있어야 한다.

그래서 자리를 정하실 수 있게 한다. 다만 **아무 데나는 안 된다** — 지켜야 할 선이 둘이다.

  1. **프로그램 폴더 안은 안 된다.** 새 판을 받을 때 프로그램 폴더는 덮어쓰인다.
     거기에 곡을 두면 갱신 한 번에 곡이 사라진다. 고치려던 바로 그 사고다.
  2. **쓸 수 있는 자리여야 한다.** 정해 놓고 나중에 못 쓰면, 그때는 곡을 꺼내려다
     실패한다. 정하시는 그 자리에서 **실제로 써 보고** 확인한다.

정한 자리는 `.env` 가 아니라 저장소에 둔다 — `.env` 는 API 키만 사는 곳이다.
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/folder", tags=["folder"])

# 저장소에 이 이름으로 둔다.
KEY = "export_dir"


def default_dir() -> Path:
    from app.config import resolve_data_dir

    return resolve_data_dir() / "내보낸 곡"


def chosen_dir() -> Path:
    """원장님이 정하신 자리. 안 정하셨거나 못 쓰게 됐으면 원래 자리.

    **여기서 예외를 던지면 안 된다.** 곡을 꺼내는 길 한복판에서 불리므로,
    자리가 이상하면 조용히 원래 자리로 돌아가 곡은 반드시 나오게 한다.
    """
    from app.api.deps import get_store

    raw = str(get_store().jobs.get(KEY, "") or "").strip()
    if not raw:
        return default_dir()
    d = Path(raw)
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".쓸수있나"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as e:
        log.warning("정하신 폴더를 쓸 수 없어 원래 자리로 돌아간다(%s): %s", raw, e)
        return default_dir()
    return d


def _why_not(d: Path) -> str:
    """이 자리를 못 쓰는 이유. 쓸 수 있으면 빈 문자열."""
    from app.config import ROOT

    try:
        resolved = d.expanduser().resolve()
    except OSError as e:
        return f"경로를 읽을 수 없습니다: {e}"
    if not resolved.is_absolute():
        return "전체 경로를 적어 주십시오 (예: D:\\콩쿨곡 또는 C:\\Users\\...\\Desktop\\콩쿨곡)"
    try:
        # **프로그램 폴더 안은 막는다.** 새 판을 받으면 덮어쓰이는 자리다.
        resolved.relative_to(ROOT.resolve())
    except (ValueError, OSError):
        pass
    else:
        return (
            "프로그램 폴더 안은 안 됩니다 — 새 판을 받을 때 덮어쓰이는 자리라 "
            "곡이 사라집니다. 바탕화면이나 문서 폴더처럼 프로그램 밖을 정해 주십시오."
        )
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        probe = resolved / ".쓸수있나"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as e:
        return f"이 폴더에 쓸 수 없습니다: {e}"
    return ""


def _state() -> dict:
    from app.api.deps import get_store

    raw = str(get_store().jobs.get(KEY, "") or "").strip()
    now = chosen_dir()
    count = 0
    with contextlib.suppress(OSError):
        count = sum(1 for p in now.iterdir() if p.is_dir())
    return {
        "path": str(now),
        "chosen": raw,
        "is_default": not raw,
        "default_path": str(default_dir()),
        # 정하셨는데 지금 쓰이는 자리가 다르면, 그 자리를 못 써서 물러난 것이다.
        "fell_back": bool(raw) and str(now) != str(Path(raw)),
        "pieces": count,
    }


class SetIn(BaseModel):
    path: str = Field(default="", max_length=400)


@router.get("")
def get_folder() -> dict:
    return _state()


@router.put("")
def set_folder(body: SetIn, request: Request) -> dict:
    """자리를 정한다. **정하시는 그 자리에서 실제로 써 보고** 확인한다."""
    from app.api.deps import get_store

    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 정할 수 있습니다")

    store = get_store()
    raw = body.path.strip().strip('"')
    if not raw:
        store.jobs.pop(KEY, None)
        store.save_soon()
        return _state()

    problem = _why_not(Path(raw))
    if problem:
        raise HTTPException(422, {
            "message": "이 폴더는 쓸 수 없습니다",
            "what_to_do": problem,
        })
    store.jobs[KEY] = str(Path(raw).expanduser().resolve())
    store.save_soon()
    return _state()


@router.post("/open")
def open_it(request: Request) -> dict:
    """정하신 폴더를 탐색기로 연다."""
    import subprocess
    import sys

    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 열 수 있습니다")
    target = chosen_dir()
    target.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            import os

            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except (OSError, AttributeError) as e:
        raise HTTPException(500, f"폴더를 열지 못했습니다: {e}. 경로는 {target} 입니다") from e
    return {"opened": str(target)}
