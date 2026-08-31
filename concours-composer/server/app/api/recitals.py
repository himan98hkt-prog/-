"""§6.14 연주회 프로그램 빌더."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import Store, get_store
from app.recital.program import ContrastWarning, build_program

router = APIRouter(prefix="/api", tags=["recitals"])


class RecitalItemIn(BaseModel):
    student_id: str
    composition_id: str | None = None


class RecitalIn(BaseModel):
    name: str
    date: str = ""
    target_duration_sec: int = Field(default=3600, gt=0)
    order_rule: str = "difficulty"
    items: list[RecitalItemIn]


@router.post("/recitals")
def create_recital(payload: RecitalIn, store: Store = Depends(get_store)) -> dict:
    missing = [
        i.composition_id for i in payload.items
        if i.composition_id and i.composition_id not in store.compositions
    ]
    if missing:
        raise HTTPException(404, f"곡을 찾을 수 없다: {missing}")

    program = build_program(
        [(i.student_id, store.compositions.get(i.composition_id or "")) for i in payload.items],
        order_rule=payload.order_rule,
        target_duration_sec=payload.target_duration_sec,
        students=store.students,
    )
    rid = store.next_id("recital", store.recitals)
    store.recitals[rid] = {"payload": payload.model_dump(), "program": program}
    return {"recital_id": rid, **program}


@router.get("/recitals/{recital_id}")
def get_recital(recital_id: str, store: Store = Depends(get_store)) -> dict:
    if recital_id not in store.recitals:
        raise HTTPException(404, f"연주회를 찾을 수 없다: {recital_id}")
    return store.recitals[recital_id]
