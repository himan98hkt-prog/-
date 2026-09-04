"""넣어 둔 돈 · 쓴 돈 · 남은 돈.

원장님이 이렇게 물으셨다:

    "지금까지 얼마가 소진되었고 얼마가 남아 있는지도 확인할 수 있게 만들어줘."

**먼저 못 하는 것부터 밝힌다.** 앤트로픽 계정에 실제로 남아 있는 잔액은 이
프로그램이 읽을 수 없다. 사용량·비용을 읽는 창구(Admin API)는 `sk-ant-admin...`
으로 시작하는 **관리자 키** 만 받는다. 원장님이 넣으신 보통 키(`sk-ant-api...`)
로는 거절당한다. 그러니 잔액을 지어내서 보여 드리면 그건 거짓말이다.

**대신 할 수 있는 것은 정확히 한다.** 원장님이 "얼마를 충전했다" 를 한 번
적어 두시면,

  * 쓴 돈  — 이 프로그램이 실제로 치른 값(성공·실패 모두)을 1원 단위로 더한다.
  * 남은 돈 — 넣은 돈 − (넣기 시작한 뒤 쓴 돈).

여기서 "쓴 돈" 은 추측이 아니다. 곡을 만들 때마다 남기는 `spend_log` 그대로다.
다만 **이 프로그램 밖에서 쓴 돈은 알 수 없다** — 다른 프로그램이 같은 키를
썼다면 실제 잔액은 여기 숫자보다 적다. 그래서 화면에도 그렇게 적는다.

충전 기록은 지우지 않고 쌓는다. 잘못 적으셨으면 마지막 것을 무를 수 있다.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# 원장님이 실수로 0 을 몇 개 더 붙이는 일을 막는다. 한 번에 이보다 크게 충전하는
# 학원은 없다 — 정말 그러셨다면 두 번 나눠 적으시면 된다.
MAX_TOPUP_USD = 5000.0

# 이 아래로 남으면 붉게 알린다. 곡 하나가 비싸야 $0.6 안팎이니 $5 면 몇 곡 못 만든다.
LOW_USD = 5.0


class TopUp(BaseModel):
    usd: float = Field(gt=0, le=MAX_TOPUP_USD, description="충전한 금액(달러)")
    note: str = Field("", max_length=100)


def _rows(store: object) -> list[dict]:
    jobs = getattr(store, "jobs", {})
    got = jobs.get("topups", [])
    return [r for r in got if isinstance(r, dict) and r.get("usd")]


def _spend_rows(store: object) -> list[dict]:
    jobs = getattr(store, "jobs", {})
    return [
        j for j in jobs.get("spend_log", [])
        if isinstance(j, dict) and j.get("at")
    ]


def summary(store: object) -> dict:
    """넣은 돈 · 쓴 돈 · 남은 돈. **모르는 것은 모른다고 돌려준다.**"""
    tops = _rows(store)
    charged = round(sum(float(r.get("usd", 0.0) or 0.0) for r in tops), 4)
    since = min((str(r.get("at", "")) for r in tops), default="")

    spends = _spend_rows(store)
    # 충전을 적기 전에 쓴 돈은 그 충전금에서 나간 돈이 아니다. 그것까지 빼면
    # 남은 돈이 실제보다 적게 나온다.
    spent_since = round(
        sum(
            float(j.get("usd", 0.0) or 0.0)
            for j in spends
            if not since or str(j.get("at", "")) >= since
        ),
        4,
    )
    spent_all = round(sum(float(j.get("usd", 0.0) or 0.0) for j in spends), 4)

    known = bool(tops)
    remaining = round(charged - spent_since, 4) if known else 0.0
    return {
        # 원장님이 적어 두신 충전 총액. 안 적으셨으면 known=False.
        "known": known,
        "charged_usd": charged,
        "spent_usd": spent_since,
        "spent_all_usd": spent_all,
        "remaining_usd": remaining,
        "pct_used": round(min(1.0, spent_since / charged), 4) if charged > 0 else 0.0,
        "low": known and remaining <= LOW_USD,
        "empty": known and remaining <= 0,
        "since": since,
        "topups": sorted(tops, key=lambda r: str(r.get("at", "")), reverse=True)[:20],
        # 화면이 이 문장을 그대로 보여 준다. 잔액을 우리가 안다고 하면 안 된다.
        "truth": (
            "이 숫자는 이 프로그램이 쓴 돈만 셉니다. "
            "앤트로픽 계정의 진짜 잔액은 console.anthropic.com 의 Billing 에서 보십시오."
        ),
    }


@router.get("")
def get_wallet() -> dict:
    from app.api.deps import get_store

    return summary(get_store())


@router.post("/topup")
def add_topup(body: TopUp) -> dict:
    """"이만큼 충전했다" 를 적는다. 돈을 옮기는 것이 아니라 적어 두는 것뿐이다."""
    from app.api.deps import get_store

    store = get_store()
    store.jobs.setdefault("topups", []).append({
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "usd": round(float(body.usd), 4),
        "note": body.note.strip(),
    })
    store.save_soon()
    return summary(store)


@router.post("/undo")
def undo_topup() -> dict:
    """마지막에 적은 충전을 무른다 — 0 을 하나 더 붙이셨을 때."""
    from app.api.deps import get_store

    store = get_store()
    tops = store.jobs.get("topups") or []
    if not tops:
        raise HTTPException(404, "무를 충전 기록이 없습니다")
    tops.pop()
    store.save_soon()
    return summary(store)
