"""§6.14 연주회 프로그램 — 순서 제안 · 대비 검사 · 총 러닝타임.

대비 검사가 핵심이다. 같은 조성·비슷한 템포의 곡이 연달아 나오면 청중은 지루하고,
학생도 손해다. 연속하는 곡의 조성·템포·분위기 중복을 100% 잡아낸다(M8 Acceptance).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from music21 import meter as m21meter

# 등퇴장 시간(초). SPEC §6.14.
STAGE_CHANGE_SEC = 45

# 템포가 이 이내로 비슷하면 '대비 없음' 으로 본다.
TEMPO_SIMILAR_BPM = 8


@dataclass
class ContrastWarning:
    position: int
    kind: str
    message: str


@dataclass
class ProgramItem:
    position: int
    student_id: str
    student_name: str
    title: str
    key: str
    tempo: int
    difficulty: float
    duration_sec: float
    composition_id: str | None = None


@dataclass
class Program:
    items: list[ProgramItem] = field(default_factory=list)
    warnings: list[ContrastWarning] = field(default_factory=list)
    total_sec: float = 0.0
    target_sec: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [vars(i) for i in self.items],
            "warnings": [vars(w) for w in self.warnings],
            "total_sec": round(self.total_sec, 1),
            "total_minutes": round(self.total_sec / 60, 1),
            "target_sec": self.target_sec,
            "over_target": self.total_sec > self.target_sec,
        }


def _duration(res: Any) -> float:
    bar_ql = float(m21meter.TimeSignature(res.plan.meter).barDuration.quarterLength)
    return len(res.measures) * bar_ql * (60.0 / res.plan.tempo)


def check_contrast(items: list[ProgramItem]) -> list[ContrastWarning]:
    """연속한 두 곡의 조성·템포 중복을 경고한다."""
    out: list[ContrastWarning] = []
    for a, b in zip(items, items[1:], strict=False):
        if a.key == b.key:
            out.append(ContrastWarning(
                b.position, "key",
                f"{a.position}번({a.title})과 {b.position}번({b.title})이 같은 조성 {a.key} — "
                "사이에 다른 조성의 곡을 넣어라",
            ))
        if abs(a.tempo - b.tempo) <= TEMPO_SIMILAR_BPM:
            out.append(ContrastWarning(
                b.position, "tempo",
                f"{a.position}번({a.tempo}bpm)과 {b.position}번({b.tempo}bpm)의 템포가 거의 같다 — "
                "빠른 곡과 느린 곡을 번갈아 배치하라",
            ))
    return out


def build_program(
    entries: list[tuple[str, Any]],
    *,
    order_rule: str = "difficulty",
    target_duration_sec: int = 3600,
    students: dict[str, Any] | None = None,
) -> dict[str, Any]:
    students = students or {}
    rows: list[ProgramItem] = []
    for student_id, res in entries:
        if res is None:
            continue
        student = students.get(student_id)
        # 이름 표기는 동의 설정을 따른다 — 프로그램북은 외부로 나가는 인쇄물이다.
        name = student.display_name() if student is not None else student_id
        rows.append(ProgramItem(
            position=0, student_id=student_id, student_name=name,
            title=(res.plan.title_candidates or ["무제"])[0],
            key=res.plan.key, tempo=res.plan.tempo,
            difficulty=res.difficulty, duration_sec=round(_duration(res), 1),
        ))

    if order_rule == "difficulty":
        rows.sort(key=lambda r: r.difficulty)
    elif order_rule == "duration":
        rows.sort(key=lambda r: r.duration_sec)
    elif order_rule == "contrast":
        rows = _interleave_for_contrast(rows)

    for i, r in enumerate(rows, start=1):
        r.position = i

    program = Program(
        items=rows,
        warnings=check_contrast(rows),
        total_sec=sum(r.duration_sec for r in rows) + STAGE_CHANGE_SEC * max(0, len(rows)),
        target_sec=target_duration_sec,
    )
    return program.as_dict()


def _interleave_for_contrast(rows: list[ProgramItem]) -> list[ProgramItem]:
    """빠른 곡과 느린 곡을 번갈아 놓아 연속 중복을 줄인다."""
    ordered = sorted(rows, key=lambda r: r.tempo)
    slow = ordered[: len(ordered) // 2]
    fast = ordered[len(ordered) // 2 :]
    out: list[ProgramItem] = []
    while slow or fast:
        if fast:
            out.append(fast.pop(0))
        if slow:
            out.append(slow.pop())
    return out
