from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "composer_model": s.composer_model,
        "writer_model": s.writer_model,
        "engine": "claude" if s.has_api_key else "stub-rule-based",
        "quality_threshold": s.quality_threshold,
        "max_revision_rounds": s.max_revision_rounds,
        "max_cost_per_composition": s.max_cost_per_composition,
        "model_problems": getattr(request.app.state, "model_problems", []),
    }


@router.post("/api/shutdown")
def shutdown(request: Request) -> dict:
    """프로그램을 끈다 — 화면의 '프로그램 끄기' 버튼이 부른다.

    바탕화면 아이콘으로 켜면 명령창이 없어서 Ctrl+C 를 누를 곳이 없다. 그래서
    끄는 길을 화면 안에 둔다. 실행기(scripts/launch.py)가 서버 손잡이를
    `app.state.server` 에 올려 둘 때만 동작한다 — 개발용으로 uvicorn 을 직접
    띄운 경우에는 끄지 않고 그렇게 알린다.
    """
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 끌 수 있다")
    server = getattr(request.app.state, "server", None)
    if server is None:
        raise HTTPException(409, "명령창에서 띄운 서버다 — 그 창에서 Ctrl+C 로 끄십시오")
    server.should_exit = True
    return {"status": "shutting_down"}


@router.get("/api/backups")
def backups() -> dict:
    """백업 상태 — 언제 몇 개가 어디에 있는지.

    되돌리기는 프로그램이 하지 않는다. 잘못 되돌리면 지금 것까지 잃기 때문이다.
    어느 파일을 어떻게 되돌리는지 글로 알려 주고, 판단은 사람이 한다.
    """
    from app.api.deps import get_store

    keeper = get_store().backups
    if keeper is None:
        return {
            "enabled": False,
            "why": "저장을 파일에 하지 않는 모드로 켜져 있습니다(STORE_PERSIST=0)",
        }
    out = dict(keeper.summary())
    out["enabled"] = True
    out["how_to_restore"] = [
        "1. 오른쪽 위 '끄기' 로 프로그램을 끕니다",
        f"2. {out['folder']} 폴더에서 되돌리고 싶은 시각의 파일을 복사합니다",
        "3. data 폴더의 store.sqlite3 를 그 파일로 덮어씁니다(원본은 이름을 바꿔 남겨 두십시오)",
        "4. 바탕화면 아이콘으로 다시 켭니다",
    ]
    return out


@router.post("/api/backups")
def make_backup() -> dict:
    """지금 곧바로 사본을 뜬다 — 큰 편집을 하기 전에 눌러 두라고."""
    from app.api.deps import get_store

    keeper = get_store().backups
    if keeper is None:
        raise HTTPException(409, "저장을 파일에 하지 않는 모드입니다(STORE_PERSIST=0)")
    get_store().save()
    made = keeper.maybe_backup(force=True)
    if made is None:
        raise HTTPException(500, "사본을 뜨지 못했습니다")
    return {"created": made.name, **keeper.summary()}


@router.get("/api/spending")
def spending() -> dict:
    """이번 달·지난 달 API 비용.

    키를 넣고 쓰기 시작하면 "이번 달 얼마 썼나" 가 보여야 한다. 곡 하나당 얼마인지만
    알면 달이 끝나고 나서야 총액을 안다.

    곡을 만들 때 남긴 기록(auto_history)을 달별로 더한다. 규칙 기반(무료)으로 만든
    곡은 0원이므로 자연히 빠진다.
    """
    from collections import defaultdict
    from datetime import UTC, datetime

    from app.api.deps import get_store

    store = get_store()

    # **성공한 곡만 세면 날린 돈이 안 보인다.**
    # 원장님이 "내가 비용을 도대체 얼마나 사용한건지" 라고 물으신 것이 이것이다 —
    # 곡이 안 나온 시도에 쓴 돈이야말로 가장 알고 싶은 돈인데 그것만 빠져 있었다.
    # spend_log 는 성공·실패를 가리지 않고 적는다.
    log_rows = [
        j for j in store.jobs.get("spend_log", [])
        if isinstance(j, dict) and j.get("at")
    ]
    by_month: dict[str, dict[str, float]] = defaultdict(
        lambda: {"pieces": 0.0, "usd": 0.0, "failed": 0.0, "wasted_usd": 0.0}
    )
    if log_rows:
        for j in log_rows:
            month = str(j["at"])[:7]
            usd = float(j.get("usd", 0.0) or 0.0)
            by_month[month]["usd"] += usd
            if j.get("ok"):
                by_month[month]["pieces"] += 1
            else:
                by_month[month]["failed"] += 1
                by_month[month]["wasted_usd"] += usd
    else:
        # 옛 기록만 있는 원장님 PC 도 있다. 그때는 지금까지 하던 대로 센다.
        for j in store.jobs.get("auto_history", []):
            if not (isinstance(j, dict) and j.get("at")):
                continue
            month = str(j["at"])[:7]
            by_month[month]["pieces"] += 1
            by_month[month]["usd"] += float(j.get("cost_usd", 0.0) or 0.0)

    now = datetime.now(UTC)
    this_month = now.strftime("%Y-%m")
    prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    def row(month: str) -> dict:
        got = by_month.get(month) or {"pieces": 0.0, "usd": 0.0, "failed": 0.0, "wasted_usd": 0.0}
        pieces = int(got["pieces"])
        usd = round(got["usd"], 4)
        return {
            "month": month,
            "pieces": pieces,
            "usd": usd,
            "per_piece": round(usd / pieces, 4) if pieces else 0.0,
            # 곡을 못 얻고 나간 돈. 이것을 보셔야 등급을 바꾸든 성격을 바꾸든 하신다.
            "failed": int(got.get("failed", 0.0)),
            "wasted_usd": round(float(got.get("wasted_usd", 0.0)), 4),
        }

    total_usd = round(sum(v["usd"] for v in by_month.values()), 4)
    recent = [
        {"at": j["at"], "usd": round(float(j.get("usd", 0.0) or 0.0), 4),
         "ok": bool(j.get("ok")), "what": str(j.get("what", ""))}
        for j in sorted(log_rows, key=lambda x: str(x["at"]), reverse=True)[:12]
    ]
    return {
        "this_month": row(this_month),
        "last_month": row(prev),
        "total_usd": total_usd,
        "total_pieces": int(sum(v["pieces"] for v in by_month.values())),
        "total_wasted_usd": round(sum(v.get("wasted_usd", 0.0) for v in by_month.values()), 4),
        "total_failed": int(sum(v.get("failed", 0.0) for v in by_month.values())),
        "months": [row(m) for m in sorted(by_month, reverse=True)[:12]],
        # 최근 시도 낱낱. "이번에 얼마 나갔나" 를 곧바로 보시라고.
        "recent": recent,
    }


@router.get("/api/progress/{job_id}")
def progress(job_id: str) -> dict:
    """곡이 만들어지는 동안 어디까지 왔는지.

    화면이 0.7초마다 물어본다. 아직 시작 전이거나 기록이 지워졌으면 그렇게 알린다 —
    없는 것을 있는 척하지 않는다.
    """
    from app.progress import tracker

    got = tracker().get(job_id)
    if got is None:
        return {"known": False, "pct": 0.0, "stage": "", "stage_ko": "", "message": "", "steps": []}
    return {"known": True, **got}


@router.get("/api/storage")
def storage() -> dict:
    """만든 곡이 **어디에** 저장되는지.

    원장이 "저장은 도대체 어디에 있는가" 에서 막혔다. 곡이 프로그램 폴더 안에
    저장되던 탓에, 새 판을 받으려고 폴더를 지우자 만든 곡이 함께 사라졌기 때문이다.
    지금은 프로그램 폴더 바깥에 저장하지만, 그 사실이 화면에 보이지 않으면
    원장은 여전히 알 수 없다. 그래서 자리를 숨기지 않고 그대로 알려 준다.
    """
    from app.api.deps import get_store
    from app.config import ROOT, data_dir_warning, get_settings, resolve_data_dir

    s = get_settings()
    data_dir = resolve_data_dir()
    store_file = s.resolved_store_path()
    try:
        size_mb = round(store_file.stat().st_size / 1_048_576, 2) if store_file.exists() else 0.0
    except OSError:
        size_mb = 0.0

    import contextlib

    inside = False
    with contextlib.suppress(OSError, ValueError):
        inside = data_dir.resolve().is_relative_to(ROOT.resolve())

    return {
        "persist": s.store_persist,
        "data_dir": str(data_dir),
        "store_file": str(store_file),
        "exists": store_file.exists(),
        "size_mb": size_mb,
        "pieces": len(get_store().compositions),
        "books": len(get_store().books),
        # 프로그램 폴더 안에 저장되고 있으면 **새 판을 받을 때 곡이 지워진다**.
        # 그 위험은 원장이 알아야 한다.
        "inside_program_folder": inside,
        "warning": (
            "만든 곡이 프로그램 폴더 안에 저장되고 있습니다. "
            "새 판을 받으려고 이 폴더를 지우면 곡도 함께 사라집니다. "
            ".env 의 DATA_DIR 줄을 지우고 프로그램을 다시 켜면 안전한 자리로 옮깁니다."
            if inside
            # 백신·회사 PC 정책·디스크 부족으로 제자리에 못 잡고 옮겨 앉은 경우.
            # 곡은 정상으로 만들어지지만 어디에 쌓이는지는 반드시 보여야 한다.
            else data_dir_warning()
        ),
    }


@router.post("/api/open-folder")
def open_folder(request: Request, which: str = "data") -> dict:
    """만든 것이 있는 폴더를 탐색기로 연다.

    원장이 "저장은 도대체 어디에 있는가" 에서 막혔다. 경로를 글로 적어 주는 것만으로는
    부족하다 — 탐색기 주소창에 붙여넣는 것도 배워야 하는 일이다. 눌러서 열리게 한다.

    이 PC 에서만 연다. 원격에서 남의 폴더를 열게 할 수는 없다.
    """
    import subprocess
    import sys

    from app.config import ROOT, resolve_data_dir

    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 열 수 있다")

    places = {
        "data": resolve_data_dir(),
        "exports": resolve_data_dir() / "내보낸 곡",
        "references": resolve_data_dir() / "reference_scores",
        "program": ROOT,
    }
    target = places.get(which)
    if target is None:
        raise HTTPException(404, f"그런 폴더는 없다: {which}")
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
        # 열지 못해도 경로는 알려 준다 — 그것만으로도 손으로 찾아갈 수 있다.
        raise HTTPException(500, f"폴더를 열지 못했습니다: {e}. 경로는 {target} 입니다") from e
    return {"opened": str(target)}


@router.post("/api/export-all")
def export_all(request: Request) -> dict:
    """만든 곡을 **파일로** 한꺼번에 꺼내 둔다.

    지금 만든 곡은 저장 파일 하나 안에 들어 있다. 프로그램을 켜야만 보인다는 뜻이다.
    원장은 탐색기에서 곡을 눈으로 찾고 싶어 한다 — 악보를 남에게 보내거나, 백업을
    따로 두거나, 그냥 "내 곡이 여기 있구나" 를 확인하려고.

    그래서 한 번 눌러 곡마다 폴더를 만들어 준다. 이미 있는 것은 다시 만들지 않는다.
    """
    from app.api.compositions import package_input
    from app.api.deps import get_store
    from app.config import resolve_data_dir
    from app.export.package import _safe, write_piece

    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 내보낼 수 있다")

    store = get_store()
    if not store.compositions:
        raise HTTPException(409, "아직 만든 곡이 없습니다")

    root = resolve_data_dir() / "내보낸 곡"
    root.mkdir(parents=True, exist_ok=True)

    made, skipped = [], []
    for cid in list(store.compositions):
        title = _safe(store.title_of(cid)) or cid
        folder = root / f"{title} ({cid})"
        if folder.exists() and any(folder.iterdir()):
            skipped.append(title)
            continue
        try:
            data = package_input(store, cid)
        except (OSError, ValueError, KeyError) as e:
            logging.getLogger(__name__).warning("%s 를 내보내지 못했다: %s", cid, e)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        # ZIP 과 같은 함수로 담는다 — 갈라지면 한쪽에만 파일이 빠진다.
        import zipfile

        tmp = folder / "_tmp.zip"
        with zipfile.ZipFile(tmp, "w") as z:
            write_piece(z, "x", data)
            for info in z.infolist():
                out = folder / info.filename.split("/", 1)[1]
                out.write_bytes(z.read(info))
        tmp.unlink(missing_ok=True)
        made.append(title)

    return {
        "folder": str(root),
        "made": made,
        "skipped": skipped,
        "total": len(store.compositions),
    }


@router.get("/api/quality-modes")
def quality_modes() -> dict:
    """곡 하나에 얼마를 쓸지 원장이 고를 수 있는 등급들.

    원장님이 토카타를 만들다 상한에 걸려 멈췄고, 그때 화면은 '.env 를 고쳐라' 고 했다.
    컴맹 원장에게 설정 파일을 열라는 것은 답이 아니다 — 화면에서 고르게 한다.
    """
    from app.config import get_settings
    from app.generation.budget import CUSTOM, DEFAULT_MODE, MODES, PICKABLE_MODELS, as_dict

    return {
        "modes": [as_dict(m) for m in (*MODES, CUSTOM)],
        "models": list(PICKABLE_MODELS),
        "default": DEFAULT_MODE,
        "has_api_key": get_settings().has_api_key,
    }


# 새 판이 나왔는지 화면이 알려 준다.
#
# 업데이트 스크립트를 만들어 놓아도 **언제 눌러야 하는지** 모르면 소용이 없다.
# 그렇다고 켤 때마다 인터넷에 물어보면 느려지므로, 한 번 물어본 답은 잠시 들고 있는다.
_VERSION_ASKED_AT = [0.0]
_VERSION_ANSWER: list[dict[str, object]] = []
_VERSION_TTL = 1800.0        # 30분. 새 판이 그보다 자주 나오지는 않는다.


@router.get("/api/version")
def version(check: bool = True) -> dict:
    """지금 판과 새 판. 물어보지 못해도 화면은 그대로 뜬다."""
    import contextlib
    import time
    import urllib.error
    import urllib.request

    from app.config import ROOT

    stamp = ROOT / "설치버전.txt"
    here = ""
    with contextlib.suppress(OSError):
        here = stamp.read_text(encoding="utf-8").strip()

    out: dict = {"installed": here[:7], "latest": "", "update_available": False, "asked": False}
    if not check:
        return out

    now = time.monotonic()
    if _VERSION_ANSWER and now - _VERSION_ASKED_AT[0] < _VERSION_TTL:
        return {**out, **_VERSION_ANSWER[0]}

    url = "https://api.github.com/repos/himan98hkt-prog/-/commits/claude/program-development-yi0956"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ConcoursComposer"})
        with urllib.request.urlopen(req, timeout=6) as r:
            import json as _json

            latest = str(_json.loads(r.read()).get("sha", ""))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        # 인터넷이 없어도 프로그램은 그대로 돈다 — 조용히 넘어간다.
        return out

    fresh = {
        "latest": latest[:7],
        # 판 번호를 모르면(옛 설치) 비교할 수 없다 — 있다고 우기지 않는다.
        "update_available": bool(here and latest and not latest.startswith(here)),
        "asked": True,
    }
    _VERSION_ASKED_AT[0] = now
    _VERSION_ANSWER.clear()
    _VERSION_ANSWER.append(fresh)
    return {**out, **fresh}


@router.post("/api/update")
def run_update(request: Request) -> dict:
    """새 판으로 올리기 — **화면의 버튼으로** 시작한다.

    원장님 PC 에서 '업데이트.bat' 을 두 번 눌렀더니 메모장이 열렸다. 윈도우에서 .bat
    파일 연결이 메모장으로 바뀌어 있으면 그렇게 된다. 파일을 두 번 누르게 하는 방식은
    원장 손에 달린 것이 아니라 **그 PC 설정에 달려 있다** — 원터치라고 할 수 없다.

    그래서 프로그램이 직접 시작한다. 여기서 하는 일은 갱신 스크립트를 **떼어 내서**
    띄우는 것뿐이다. 그 스크립트가 이 프로그램을 끄고, 파일을 바꾸고, 다시 켠다.
    떼어 내지 않으면 이 프로그램이 꺼질 때 갱신도 같이 죽는다.
    """
    import subprocess
    import sys

    from app.config import ROOT

    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "이 PC 에서만 올릴 수 있다")

    script = ROOT / "update.ps1"
    if not script.exists():
        raise HTTPException(
            404,
            {
                "message": "갱신 파일이 없습니다",
                "what_to_do": "이 판에는 아직 갱신 기능이 없습니다. "
                "새 압축파일을 한 번만 받아 설치해 주시면 그다음부터는 이 버튼으로 됩니다.",
            },
        )
    if sys.platform != "win32":
        raise HTTPException(400, "지금은 윈도우에서만 됩니다")

    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — 이 프로그램이 꺼져도 살아남는다.
    flags = 0x00000008 | 0x00000200
    try:
        subprocess.Popen(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script),
            ],
            cwd=str(ROOT),
            creationflags=flags,
            close_fds=True,
        )
    except OSError as e:
        raise HTTPException(500, f"갱신을 시작하지 못했습니다: {e}") from e

    return {
        "started": True,
        "note": "새 판을 받는 중입니다. 잠시 뒤 프로그램이 꺼졌다가 다시 켜집니다.",
    }
