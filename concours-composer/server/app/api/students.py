"""학생 · 콩쿨 프로필 CRUD (§6.2, §6.13)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Store, get_store
from app.schemas.student import CompetitionProfile, Student

router = APIRouter(prefix="/api", tags=["students"])


@router.post("/students", response_model=Student)
def create_student(student: Student, store: Store = Depends(get_store)) -> Student:
    sid = student.id or store.next_id("student", store.students)
    saved = student.model_copy(update={"id": sid})
    store.students[sid] = saved
    return saved


@router.get("/students", response_model=list[Student])
def list_students(store: Store = Depends(get_store)) -> list[Student]:
    return list(store.students.values())


@router.get("/students/{student_id}", response_model=Student)
def get_student(student_id: str, store: Store = Depends(get_store)) -> Student:
    if student_id not in store.students:
        raise HTTPException(404, f"학생을 찾을 수 없다: {student_id}")
    return store.students[student_id]


@router.post("/competition-profiles", response_model=CompetitionProfile)
def create_competition(
    profile: CompetitionProfile, store: Store = Depends(get_store)
) -> CompetitionProfile:
    cid = profile.id or store.next_id("comp", store.competitions)
    saved = profile.model_copy(update={"id": cid})
    store.competitions[cid] = saved
    return saved


@router.get("/competition-profiles", response_model=list[CompetitionProfile])
def list_competitions(store: Store = Depends(get_store)) -> list[CompetitionProfile]:
    return list(store.competitions.values())
