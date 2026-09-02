from __future__ import annotations

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

    rows = [j for j in get_store().jobs.get("auto_history", []) if isinstance(j, dict) and j.get("at")]
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"pieces": 0.0, "usd": 0.0})
    for j in rows:
        month = str(j["at"])[:7]
        by_month[month]["pieces"] += 1
        by_month[month]["usd"] += float(j.get("cost_usd", 0.0) or 0.0)

    now = datetime.now(UTC)
    this_month = now.strftime("%Y-%m")
    prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    def row(month: str) -> dict:
        got = by_month.get(month, {"pieces": 0.0, "usd": 0.0})
        pieces = int(got["pieces"])
        usd = round(got["usd"], 4)
        return {
            "month": month,
            "pieces": pieces,
            "usd": usd,
            "per_piece": round(usd / pieces, 4) if pieces else 0.0,
        }

    total_usd = round(sum(v["usd"] for v in by_month.values()), 4)
    return {
        "this_month": row(this_month),
        "last_month": row(prev),
        "total_usd": total_usd,
        "total_pieces": int(sum(v["pieces"] for v in by_month.values())),
        "months": [row(m) for m in sorted(by_month, reverse=True)[:12]],
    }
