"""참고 악보를 **화면에서** 넣고 확인하는 길.

원장님이 이렇게 말씀하셨다:

    "참고할수 있는 악보들을 업로드 하려고 했는데
     업로드 하는곳이나 폴더를 확인하는곳이 없던데."

맞는 말씀이었다. 서버는 처음부터 업로드를 받을 수 있었고 폴더를 탐색기로 열 수도
있었는데, **화면에 그 단추가 하나도 없었다.** 있는 기능도 누를 데가 없으면 없는
기능이다. 원장님은 폴더 경로를 글로 읽고, 탐색기를 열고, 거기까지 찾아 들어가고,
파일을 넣고, **프로그램을 껐다 켜야** 했다. 컴맹 원장님께 원터치로 판다면서
그렇게 만들어 둔 것은 앞뒤가 맞지 않는다.

여기서 하는 일은 셋이다.

  1. **올린다** — 파일을 고르면 참고 악보 폴더에 저장하고 그 자리에서 읽는다.
     껐다 켜지 않아도 된다.
  2. **다시 읽는다** — 탐색기로 직접 넣으신 분을 위해. 폴더만 다시 훑는다.
  3. **치운다** — 잘못 올린 것을 뺀다. 파일은 지우지 않고 '지운 악보' 로 옮긴다.
     원장님이 모아 두신 악보를 우리가 없앨 수는 없다.

저작권은 기본이 안전한 쪽이다 — 표시가 없으면 저작권곡으로 보고 통계만 쓴다
(CLAUDE.md 절대 규칙 3).
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.corpus import get_corpus
from app.ingest.corpus import Corpus

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/references", tags=["references"])

# 읽을 수 있는 악보 파일. 이 밖의 것은 받아도 읽지 못하므로 미리 거절한다.
# PDF 는 받되 **통계만** 쓴다 — 그림에서 음표를 알아낼 수는 없다.
SUFFIXES = {".musicxml", ".xml", ".mxl", ".mid", ".midi", ".pdf"}
# 사람이 고른 저작권 상태. 화면의 드롭다운과 같은 목록이다.
STATUSES = {"public_domain", "own", "licensed", "copyrighted"}


def _scripts_on_path() -> None:
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))


def _score_dir() -> Path:
    """폴더를 정하는 자리는 **하나뿐이어야 한다.**

    여기서 따로 계산하면 '저장한 폴더' 와 '훑는 폴더' 가 언젠가 어긋난다 —
    저장은 됐는데 읽히지 않는, 원인을 짐작하기 어려운 고장이 바로 그것이었다.
    """
    _scripts_on_path()
    from import_scores import score_dir

    return score_dir()


def _sync(corpus: Corpus) -> dict[str, int]:
    """폴더를 훑어 새 악보만 코퍼스에 넣는다. 시작할 때 쓰는 것과 같은 함수다."""
    _scripts_on_path()
    from import_scores import sync as sync_scores

    result: dict[str, int] = sync_scores(corpus, quiet=True)
    return result


class Where(BaseModel):
    folder: str
    exists: bool
    files: int
    loaded: int


@router.get("/where", response_model=Where)
def where(corpus: Corpus = Depends(get_corpus)) -> Where:
    """폴더가 어디이고, 파일이 몇 개 있고, 그중 몇 개를 읽었는지.

    "넣긴 넣었는데 반영이 된 건가?" 를 알 수 없으면 아무도 폴더를 쓰지 않는다.
    파일 수와 읽은 수가 다르면 그 자체가 무언가 잘못됐다는 신호다.
    """
    d = _score_dir()
    files = (
        len([p for p in d.rglob("*") if p.suffix.lower() in SUFFIXES]) if d.exists() else 0
    )
    loaded = len([s for s in corpus.scores.values() if not getattr(s, "generated", False)])
    return Where(folder=str(d), exists=d.exists(), files=files, loaded=loaded)


class Added(BaseModel):
    saved: list[str]
    rejected: list[str]
    added: int
    skipped: int
    failed: int


@router.post("/upload", response_model=Added)
async def upload(
    files: list[UploadFile] = File(...),
    copyright_status: str = Form("copyrighted"),
    corpus: Corpus = Depends(get_corpus),
) -> Added:
    """고른 악보 파일들을 폴더에 저장하고 **그 자리에서** 읽는다.

    파일을 폴더에 실제로 두는 것이 중요하다. 메모리에만 넣으면 프로그램을 껐다 켠
    순간 사라진다 — 원장님은 올렸다고 알고 계신데 없어지는 것이다.
    """
    if copyright_status not in STATUSES:
        raise HTTPException(422, f"알 수 없는 저작권 상태: {copyright_status}")

    d = _score_dir()
    d.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    rejected: list[str] = []

    for f in files:
        name = Path(f.filename or "").name
        if not name:
            continue
        if Path(name).suffix.lower() not in SUFFIXES:
            rejected.append(
                f"{name} — 읽을 수 없는 형식입니다"
                "(MusicXML · MXL · MIDI · PDF 만 됩니다)"
            )
            continue
        data = await f.read()
        if not data:
            rejected.append(f"{name} — 파일이 비어 있습니다")
            continue

        # 같은 이름이 있으면 덮어쓰지 않는다. 원장님이 먼저 넣어 두신 것이 우선이다.
        target = d / name
        n = 2
        while target.exists():
            target = d / f"{Path(name).stem} ({n}){Path(name).suffix}"
            n += 1
        target.write_bytes(data)

        # 저작권 표시를 옆에 적어 둔다. 없으면 저작권곡으로 취급되므로,
        # 보호 기간이 끝난 곡을 고르셨다면 이 파일이 있어야 선율까지 참고한다.
        target.with_suffix(".json").write_text(
            json.dumps({"copyright_status": copyright_status}, ensure_ascii=False),
            encoding="utf-8",
        )
        saved.append(target.name)

    r = _sync(corpus) if saved else {"added": 0, "skipped": 0, "failed": 0}
    log.info("참고 악보 업로드: 저장 %d · %s", len(saved), r)
    return Added(
        saved=saved, rejected=rejected,
        added=r["added"], skipped=r["skipped"], failed=r["failed"],
    )


@router.post("/rescan", response_model=Added)
def rescan(corpus: Corpus = Depends(get_corpus)) -> Added:
    """탐색기로 직접 넣으신 악보를 지금 읽는다 — 껐다 켤 필요 없이."""
    r = _sync(corpus)
    return Added(saved=[], rejected=[], added=r["added"], skipped=r["skipped"], failed=r["failed"])


class Removed(BaseModel):
    removed: str
    moved_to: str = ""


@router.delete("/{score_id}", response_model=Removed)
def remove(
    score_id: str, request: Request, corpus: Corpus = Depends(get_corpus)
) -> Removed:
    """참고 목록에서 뺀다. **파일은 지우지 않고** '지운 악보' 로 옮긴다.

    원장님이 모아 두신 악보다. 잘못 눌렀다고 우리가 없애 버릴 수는 없다.
    """
    # 이 PC 에서만. 파일을 옮기는 일이므로 원격에서 부르게 둘 수 없다
    # — 폴더 여는 기능과 같은 기준이다.
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 치울 수 있습니다")

    entry = corpus.scores.get(score_id)
    if entry is None:
        raise HTTPException(404, f"그런 참고 악보가 없습니다: {score_id}")

    title = getattr(entry, "title", score_id)
    source = str(getattr(entry, "source", "") or "")
    corpus.remove(score_id) if hasattr(corpus, "remove") else corpus.scores.pop(score_id, None)
    corpus._ngrams.pop(score_id, None)

    moved = ""
    d = _score_dir()
    candidate = (d / Path(source).name) if source else None
    if candidate and candidate.exists() and candidate.is_relative_to(d):
        trash = d / "_지운 악보"
        trash.mkdir(parents=True, exist_ok=True)
        dest = trash / candidate.name
        n = 2
        while dest.exists():
            dest = trash / f"{candidate.stem} ({n}){candidate.suffix}"
            n += 1
        shutil.move(str(candidate), str(dest))
        side = candidate.with_suffix(".json")
        if side.exists():
            shutil.move(str(side), str(dest.with_suffix(".json")))
        moved = str(dest)

    # 기록에서도 빼야 '다시 읽기' 가 방금 치운 것을 되살리지 않는다.
    _forget(source or title)
    return Removed(removed=title, moved_to=moved)


def _forget(source: str) -> None:
    """적재 기록에서 이 파일을 지운다 — 안 지우면 다시 읽어도 건너뛴다."""
    _scripts_on_path()
    from import_scores import ledger_path

    path = ledger_path()
    if not path.exists():
        return
    try:
        ledger: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    name = Path(source).name
    for key in [k for k in ledger if Path(k).name == name]:
        ledger.pop(key, None)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
