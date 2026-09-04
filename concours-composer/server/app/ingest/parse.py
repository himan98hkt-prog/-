"""§6.1 코퍼스 입력 파싱 — MusicXML/MIDI → 내부 Measure 표현.

작곡 축과 **같은 스키마**로 정규화해야 StyleProfile 추출·난이도·표절 검사가
생성곡과 코퍼스에 똑같이 적용된다.
"""
from __future__ import annotations

import logging
from pathlib import Path

from music21 import chord as m21chord
from music21 import converter, stream
from music21 import note as m21note

from app.analysis.pitch import midi_to_pitch
from app.schemas.music import Measure, ScoreEvent, Voice
from app.validate.validator import NOTATABLE_QL

log = logging.getLogger(__name__)

SUPPORTED = {".xml", ".musicxml", ".mxl", ".mid", ".midi", ".krn", ".abc"}


class UnsupportedScore(ValueError):
    pass


def _snap(ql: float) -> float:
    """기보 가능한 길이로 스냅. 코퍼스에는 셋잇단·불규칙 길이가 흔하다."""
    ql = round(float(ql), 6)
    if ql in NOTATABLE_QL:
        return ql
    candidates = [x for x in NOTATABLE_QL if x <= ql] or [min(NOTATABLE_QL)]
    return max(candidates)


def _events_from_measure(m21m: stream.Measure) -> list[ScoreEvent]:
    events: list[ScoreEvent] = []
    for el in m21m.recurse().notesAndRests:
        ql = _snap(el.quarterLength)
        if ql <= 0:
            continue
        if isinstance(el, m21note.Rest):
            events.append(ScoreEvent(dur=ql, pitches=[]))
        elif isinstance(el, m21chord.Chord):
            events.append(ScoreEvent(dur=ql, pitches=[midi_to_pitch(p.midi) for p in el.pitches]))
        elif isinstance(el, m21note.Note):
            events.append(ScoreEvent(dur=ql, pitches=[midi_to_pitch(el.pitch.midi)]))
    return events


def _pad_to_bar(events: list[ScoreEvent], bar_ql: float) -> list[ScoreEvent]:
    """마디 길이를 맞춘다. 안 맞으면 검증기가 그 곡을 통째로 막는다."""
    total = round(sum(e.dur for e in events), 6)
    if abs(total - bar_ql) < 1e-6:
        return events
    if total > bar_ql:
        out: list[ScoreEvent] = []
        acc = 0.0
        for e in events:
            room = round(bar_ql - acc, 6)
            if room <= 0:
                break
            take = _snap(min(e.dur, room))
            out.append(e.model_copy(update={"dur": take}))
            acc = round(acc + take, 6)
        events = out
        total = round(sum(e.dur for e in events), 6)
    guard = 0
    while total < bar_ql - 1e-9 and guard < 32:
        fill = _snap(round(bar_ql - total, 6))
        events.append(ScoreEvent(dur=fill, pitches=[]))
        total = round(total + fill, 6)
        guard += 1
    return events


def parse_score(path: str | Path) -> tuple[list[Measure], dict[str, object]]:
    """악보 파일 → (마디 리스트, 메타). 2단 보표를 오른손/왼손으로 나눈다.

    3단 이상이거나 피아노가 아닌 편성은 첫 두 파트만 쓴다 — v1 은 피아노 전용이다.
    """
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED:
        raise UnsupportedScore(f"지원하지 않는 형식: {p.suffix} (지원: {sorted(SUPPORTED)})")

    score = converter.parse(str(p))
    parts = list(score.parts) if hasattr(score, "parts") and score.parts else [score]
    if not parts:
        raise UnsupportedScore("파트를 찾을 수 없다")

    # 평균 음고가 높은 파트를 오른손으로 본다(파트 순서를 믿을 수 없는 파일이 많다).
    def avg_pitch(part) -> float:
        ps = [n.pitch.midi for n in part.recurse().notes if isinstance(n, m21note.Note)]
        ps += [
            p2.midi for c in part.recurse().notes if isinstance(c, m21chord.Chord)
            for p2 in c.pitches
        ]
        return sum(ps) / len(ps) if ps else 0.0

    if len(parts) >= 2:
        ordered = sorted(parts[:2], key=avg_pitch, reverse=True)
        rh_part, lh_part = ordered[0], ordered[1]
    else:
        rh_part, lh_part = parts[0], None

    ts = score.recurse().getElementsByClass("TimeSignature")
    meter_str = ts[0].ratioString if ts else "4/4"
    bar_ql = float(ts[0].barDuration.quarterLength) if ts else 4.0

    keys = score.recurse().getElementsByClass("Key")
    key_str = "C"
    if keys:
        k = keys[0]
        key_str = k.tonic.name.replace("-", "-") if k.mode == "major" else k.tonic.name.lower()

    marks = score.recurse().getElementsByClass("MetronomeMark")
    tempo = int(marks[0].number) if marks and marks[0].number else 100

    rh_measures = list(rh_part.getElementsByClass(stream.Measure))
    lh_measures = list(lh_part.getElementsByClass(stream.Measure)) if lh_part is not None else []

    out: list[Measure] = []
    for i, m21m in enumerate(rh_measures):
        number = i + 1
        rh_events = _pad_to_bar(_events_from_measure(m21m), bar_ql)
        lh_events: list[ScoreEvent] = []
        if i < len(lh_measures):
            lh_events = _pad_to_bar(_events_from_measure(lh_measures[i]), bar_ql)
        measure = Measure(
            number=number,
            rh=[Voice(events=rh_events)] if rh_events else [],
            lh=[Voice(events=lh_events)] if lh_events else [],
        )
        if measure.rh or measure.lh:
            out.append(measure)

    meta = {
        "key": key_str,
        "meter": meter_str,
        "tempo": tempo,
        "measures": len(out),
        "title": (score.metadata.title if score.metadata else None) or p.stem,
        "composer": (score.metadata.composer if score.metadata else None) or "",
        "parts_seen": len(parts),
    }
    return out, meta
