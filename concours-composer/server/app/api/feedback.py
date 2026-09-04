"""§8 teacher_feedback — 원장 피드백 수집.

가중치 보정은 여기서 하지 않는다(M8). 지금은 나중에 회귀에 쓸 수 있는 형태로
정확히 남기는 것까지가 일이다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Store, get_store
from app.schemas.feedback import (
    REASON_TAGS,
    FeedbackStats,
    TeacherFeedback,
    TeacherFeedbackIn,
)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MIN_SAMPLES_FOR_RECALIBRATION = 30


def _bucket(store: Store) -> list[TeacherFeedback]:
    return store.jobs.setdefault("teacher_feedback", [])


@router.get("/reason-tags")
def reason_tags() -> dict[str, str]:
    """화면이 보여 줄 이유 태그. 지표·루브릭 이름과 일부러 겹쳐 둔다."""
    return REASON_TAGS


@router.post("", response_model=TeacherFeedback)
def create_feedback(
    payload: TeacherFeedbackIn, store: Store = Depends(get_store)
) -> TeacherFeedback:
    if payload.composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {payload.composition_id}")
    unknown = [t for t in payload.reason_tags if t not in REASON_TAGS]
    if unknown:
        raise HTTPException(422, f"알 수 없는 이유 태그: {unknown}")

    res = store.compositions[payload.composition_id]
    bucket = _bucket(store)
    saved = TeacherFeedback(
        id=f"fb-{len(bucket) + 1:04d}",
        **payload.model_dump(),
        # 평가 당시의 점수를 얼려 둔다. 곡을 나중에 고치면 대조가 불가능해지기 때문.
        musicality_snapshot=res.quality.musicality,
        critic_snapshot=res.quality.critic or {},
        difficulty_snapshot=res.difficulty,
        difficulty_target=res.plan.difficulty_target,
        engine=res.engine,
    )
    bucket.append(saved)
    return saved


@router.get("", response_model=list[TeacherFeedback])
def list_feedback(store: Store = Depends(get_store)) -> list[TeacherFeedback]:
    return _bucket(store)


@router.get("/stats", response_model=FeedbackStats)
def stats(store: Store = Depends(get_store)) -> FeedbackStats:
    rows = _bucket(store)
    if not rows:
        return FeedbackStats(
            min_samples=MIN_SAMPLES_FOR_RECALIBRATION,
            note="아직 평가가 없다. 곡을 만들고 👍/👎 를 남기면 여기 쌓인다.",
        )

    tag_counts: dict[str, int] = {}
    for r in rows:
        for t in r.reason_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    judged = [r for r in rows if r.would_use_without_edit is not None]
    usable = sum(1 for r in judged if r.would_use_without_edit)
    ready = len(rows) >= MIN_SAMPLES_FOR_RECALIBRATION

    return FeedbackStats(
        total=len(rows),
        up=sum(1 for r in rows if r.thumbs == "up"),
        down=sum(1 for r in rows if r.thumbs == "down"),
        usable_without_edit=usable,
        usable_rate=round(usable / len(judged), 3) if judged else None,
        tag_counts=dict(sorted(tag_counts.items(), key=lambda kv: -kv[1])),
        ready_for_recalibration=ready,
        min_samples=MIN_SAMPLES_FOR_RECALIBRATION,
        note=(
            f"표본 {len(rows)}건. {MIN_SAMPLES_FOR_RECALIBRATION}건이 모이면 "
            "§7.4 음악성 가중치와 §7.7 난이도 회귀 보정을 시작한다(M8)."
            if not ready
            else f"표본 {len(rows)}건 — 가중치 보정을 시작할 수 있다(M8)."
        ),
    )
