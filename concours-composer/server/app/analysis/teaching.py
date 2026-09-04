"""지도용 표기 — 원장이 이 악보로 **가르칠 수 있게** 만든다.

연주용 악보는 음표만 있으면 된다. 그런데 이 곡을 사 가는 사람은 학원 원장이고,
그는 곡을 치는 게 아니라 **아이에게 가르친다**. 처음 보는 악보를 받아 든 선생이
알고 싶은 것은 정해져 있다.

- 여기서 손가락을 어떻게 짚나
- 어디가 아이가 걸리는 자리인가
- 이 구간은 무엇을 말하려는 대목인가

앞의 둘은 악보에서 **계산할 수 있다**. 도약이 몇 도인지, 화음이 몇 도로 벌어지는지,
임시표가 어디에 몰렸는지는 의견이 아니라 사실이다. 그래서 여기서는 그것만 낸다.
셋째는 설계도(Plan)와 연주법 해설이 이미 들고 있으므로 그것을 끌어다 붙인다.

손가락 번호는 **제안**이다. 규칙 기반이라 사람 손과 곡에 따라 더 나은 운지가 있다.
화면과 악보에 그렇게 적어 두고, 원장이 고쳐 쓰라고 만든다 — 없는 것보다 훨씬 낫고,
있다고 속이지도 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.analysis.pitch import pitch_to_midi
from app.schemas.music import CompositionPlan, Measure

Hand = Literal["rh", "lh"]
SpotKind = Literal["leap", "stretch", "accidentals", "climax", "rhythm_change", "hand_cross", "peak"]

# 이 정도 벌어지면 아이 손에는 먼 자리다(반음).
WIDE_LEAP = 8  # 단6도 이상 도약
WIDE_CHORD = 9  # 장6도 이상 벌어지는 화음
BUSY_ACCIDENTALS = 3  # 한 마디에 임시표가 이만큼이면 눈이 바쁘다


@dataclass(frozen=True)
class Spot:
    """아이가 걸릴 만한 자리 하나."""

    measure: int
    hand: Hand | None
    kind: SpotKind
    note_id: str
    message: str


@dataclass
class TeachingMarks:
    """지도용 악보에 얹는 것 전부."""

    fingering: dict[str, int] = field(default_factory=dict)  # 음표 id → 손가락
    spots: list[Spot] = field(default_factory=list)
    section_notes: list[tuple[int, str]] = field(default_factory=list)  # (마디, 글)
    caution: str = "손가락 번호는 제안입니다 — 아이 손에 맞게 고쳐 쓰십시오."


def note_id(measure_number: int, hand: str, voice: int, index: int) -> str:
    """assemble.note_id 와 같은 규칙. 두 곳이 어긋나면 표기가 엉뚱한 음에 붙는다."""
    return f"m{measure_number}-{hand}{voice}-{index}"


# ── 손가락 ───────────────────────────────────────────────────────────────────


def _chord_fingers(midis: list[int], hand: Hand) -> list[int]:
    """화음 하나의 손가락. 아래에서 위로 벌어진 만큼 손가락을 벌린다."""
    if not midis:
        return []
    low = midis[0]
    fingers: list[int] = []
    for m in midis:
        gap = m - low
        # 반음 간격 → 손가락 간격. 2도면 옆 손가락, 5도면 1-5 로 벌린다.
        step = 1 if gap <= 2 else 2 if gap <= 5 else 3 if gap <= 9 else 4
        fingers.append(min(5, 1 + step))
    fingers[0] = 1
    out = sorted(set(fingers))
    if len(out) == len(midis):
        picked = out
    else:
        picked = [min(5, 1 + i * max(1, 4 // max(1, len(midis) - 1))) for i in range(len(midis))]
    if hand == "lh":
        picked = [6 - f for f in picked][::-1]  # 왼손은 5가 아래쪽이다
        picked = sorted(picked, reverse=True)
    return [max(1, min(5, f)) for f in picked]


def _next_finger(prev: int, semitones: int, hand: Hand) -> int:
    """앞 음에서 이만큼 움직였을 때 다음 손가락.

    오른손 기준으로 계산하고 왼손은 뒤집는다 — 왼손은 올라갈 때 손가락이 줄어든다.
    """
    up = semitones > 0 if hand == "rh" else semitones < 0
    dist = abs(semitones)

    if dist == 0:
        return prev  # 같은 음은 같은 손가락으로
    if dist >= 7:
        # 큰 도약은 손 위치를 옮긴다. 옮긴 뒤 다시 뻗을 자리를 남겨 둔다.
        return 2 if up else 4
    span = 1 if dist <= 2 else 2 if dist <= 4 else 3
    nxt = prev + span if up else prev - span
    if nxt > 5:
        return 1  # 엄지를 넣는다(thumb under)
    if nxt < 1:
        return 3 if dist <= 2 else 4  # 손을 넘긴다(cross over)
    return nxt


def suggest_fingering(measures: list[Measure]) -> dict[str, int]:
    """음표 id → 손가락 번호. 성부마다 이어서 계산한다.

    화음은 벌어진 폭으로, 선율은 앞 음에서 움직인 폭으로 정한다.
    """
    out: dict[str, int] = {}
    # 성부는 마디를 넘어 이어진다 — (손, 성부번호) 별로 앞 손가락을 기억한다.
    last: dict[tuple[str, int], tuple[int, int]] = {}  # → (손가락, midi)

    for m in sorted(measures, key=lambda x: x.number):
        for hand, voices in (("rh", m.rh), ("lh", m.lh)):
            for v in voices:
                key = (hand, v.voice)
                for i, ev in enumerate(v.events):
                    if not ev.pitches:
                        continue
                    nid = note_id(m.number, hand, v.voice, i)
                    midis = sorted(pitch_to_midi(p) for p in ev.pitches)
                    if len(midis) > 1:
                        fingers = _chord_fingers(midis, hand)  # type: ignore[arg-type]
                        out[nid] = fingers[0] if hand == "rh" else fingers[-1]
                        anchor = midis[0] if hand == "rh" else midis[-1]
                        last[key] = (out[nid], anchor)
                        continue
                    midi = midis[0]
                    prev = last.get(key)
                    if prev is None:
                        finger = 1 if hand == "rh" else 5
                    else:
                        finger = _next_finger(prev[0], midi - prev[1], hand)  # type: ignore[arg-type]
                    out[nid] = finger
                    last[key] = (finger, midi)
    return out


# ── 걸리는 자리 ──────────────────────────────────────────────────────────────


def _melody_line(measures: list[Measure], hand: Hand) -> list[tuple[int, str, list[int]]]:
    """(마디, 음표 id, 울리는 음들) 을 시간 순으로."""
    out: list[tuple[int, str, list[int]]] = []
    for m in sorted(measures, key=lambda x: x.number):
        voices = m.rh if hand == "rh" else m.lh
        for v in voices:
            for i, ev in enumerate(v.events):
                if ev.pitches:
                    out.append(
                        (
                            m.number,
                            note_id(m.number, hand, v.voice, i),
                            sorted(pitch_to_midi(p) for p in ev.pitches),
                        )
                    )
    return out


def find_spots(measures: list[Measure], plan: CompositionPlan | None = None) -> list[Spot]:
    """아이가 걸릴 만한 자리. 의견이 아니라 악보에서 센 것만 낸다."""
    spots: list[Spot] = []
    seen: set[tuple[int, str, str]] = set()

    def add(spot: Spot) -> None:
        key = (spot.measure, spot.kind, spot.hand or "")
        if key not in seen:
            seen.add(key)
            spots.append(spot)

    for hand in ("rh", "lh"):
        line = _melody_line(measures, hand)  # type: ignore[arg-type]
        for idx, (num, nid, midis) in enumerate(line):
            span = midis[-1] - midis[0]
            if span >= WIDE_CHORD:
                add(
                    Spot(
                        num,
                        hand,
                        "stretch",
                        nid,  # type: ignore[arg-type]
                        f"{'오른손' if hand == 'rh' else '왼손'} 화음이 {span}반음으로 벌어집니다 — "
                        "손이 작으면 아래 음을 먼저 짚고 굴리게 하십시오",
                    )
                )
            if idx == 0:
                continue
            prev = line[idx - 1][2]
            top_move = midis[-1] - prev[-1]
            if abs(top_move) >= WIDE_LEAP:
                add(
                    Spot(
                        num,
                        hand,
                        "leap",
                        nid,  # type: ignore[arg-type]
                        f"{'오른손' if hand == 'rh' else '왼손'}이 {abs(top_move)}반음 "
                        f"{'올라갑니다' if top_move > 0 else '내려갑니다'} — "
                        "눈이 먼저 도착하도록 미리 보기를 시키십시오",
                    )
                )

    for m in measures:
        accidentals = sum(
            1 for v in (*m.rh, *m.lh) for ev in v.events for p in ev.pitches if "#" in p or "-" in p
        )
        if accidentals >= BUSY_ACCIDENTALS:
            add(
                Spot(
                    m.number,
                    None,
                    "accidentals",
                    "",
                    f"임시표가 {accidentals}개 몰려 있습니다 — 느리게 짚어 소리로 익히게 하십시오",
                )
            )

    # 리듬이 처음 바뀌는 자리. 새 음길이가 나오면 아이는 대개 거기서 흔들린다.
    known: set[float] = set()
    for m in sorted(measures, key=lambda x: x.number):
        fresh = {ev.dur for v in (*m.rh, *m.lh) for ev in v.events if ev.pitches} - known
        if known and fresh:
            add(
                Spot(
                    m.number,
                    None,
                    "rhythm_change",
                    "",
                    "새로운 길이의 음이 처음 나옵니다 — 손뼉으로 리듬을 먼저 맞춰 보십시오",
                )
            )
        known |= fresh

    if plan is not None and plan.climax:
        add(
            Spot(
                plan.climax.measure,
                None,
                "climax",
                "",
                f"클라이맥스입니다 — {plan.climax.how}. 여기까지 힘을 아끼게 하십시오",
            )
        )

    highest = 0
    peak_measure = 0
    for m in measures:
        for v in m.rh:
            for ev in v.events:
                for p in ev.pitches:
                    midi = pitch_to_midi(p)
                    if midi > highest:
                        highest, peak_measure = midi, m.number
    if peak_measure:
        add(
            Spot(
                peak_measure,
                "rh",
                "peak",
                "",
                "곡 전체의 최고음입니다 — 팔 무게로 내려놓게 하고 손목을 굳히지 않게 하십시오",
            )
        )

    return sorted(spots, key=lambda s: (s.measure, s.kind))


# ── 구간 안내 ────────────────────────────────────────────────────────────────


def section_notes(plan: CompositionPlan | None, guide: object | None = None) -> list[tuple[int, str]]:
    """구간이 시작하는 마디에 붙일 한 줄.

    연주법 해설이 있으면 그 요점을, 없으면 설계도의 구간 이름을 쓴다.
    """
    out: list[tuple[int, str]] = []
    sections = getattr(guide, "sections", None)
    if sections:
        for s in sections:
            point = s.points[0] if s.points else s.title
            out.append((s.measures[0], f"{s.title} — {point}"))
        return out
    if plan is not None:
        for f in plan.form:
            out.append((f.measures[0], f"{f.label} 구간"))
    return out


def teaching_marks(
    measures: list[Measure], plan: CompositionPlan | None = None, guide: object | None = None
) -> TeachingMarks:
    """지도용 악보에 얹을 것을 한 번에."""
    return TeachingMarks(
        fingering=suggest_fingering(measures),
        spots=find_spots(measures, plan),
        section_notes=section_notes(plan, guide),
    )
