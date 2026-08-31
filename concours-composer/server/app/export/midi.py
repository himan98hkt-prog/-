"""MIDI 내보내기 — 미리듣기와 외부 편집기 연동.

§7.3 Stage 1 은 "각 후보는 즉시 음원 합성(미리듣기)" 이 전제다. 원장이 들어보지 않고
모티브를 고르면 공동 작곡의 첫 단추가 어긋난다.

music21 을 거치지 않고 표준 MIDI 파일을 직접 쓴다 — 의존성이 줄고, NoteEvents(초 단위)를
그대로 실을 수 있어 재생과 악보가 어긋날 여지가 없다.
"""
from __future__ import annotations

import struct

from app.schemas.music import Measure, NoteEvents

TICKS_PER_BEAT = 480


def _vlq(value: int) -> bytes:
    """MIDI 가변 길이 수치."""
    if value < 0:
        raise ValueError(f"음수 델타타임: {value}")
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)


def _chunk(tag: bytes, body: bytes) -> bytes:
    return tag + struct.pack(">I", len(body)) + body


def note_events_to_midi(events: NoteEvents, *, tempo_bpm: float | None = None) -> bytes:
    """NoteEvents(초 단위) → 표준 MIDI 파일 바이트.

    손 정보가 있으면 오른손/왼손을 별도 트랙으로 나눈다 — 손 분리 재생에 그대로 쓴다.
    """
    bpm = tempo_bpm or events.tempo_bpm or 100.0
    sec_per_tick = 60.0 / bpm / TICKS_PER_BEAT

    def to_ticks(seconds: float) -> int:
        return max(0, round(seconds / sec_per_tick))

    groups: dict[str, list] = {"R": [], "L": [], "?": []}
    for n in events.sorted_notes():
        groups[n.hand or "?"].append(n)
    tracks = [(name, notes) for name, notes in groups.items() if notes]
    if not tracks:
        tracks = [("?", [])]

    # 트랙 0 은 템포 맵
    micros = round(60_000_000 / bpm)
    tempo_body = (
        _vlq(0) + b"\xff\x51\x03" + micros.to_bytes(3, "big") + _vlq(0) + b"\xff\x2f\x00"
    )
    chunks = [_chunk(b"MTrk", tempo_body)]

    for name, notes in tracks:
        msgs: list[tuple[int, int, int, int]] = []   # (tick, status, data1, data2)
        channel = {"R": 0, "L": 1}.get(name, 0)
        for n in notes:
            msgs.append((to_ticks(n.onset), 0x90 | channel, n.pitch, n.velocity))
            msgs.append((to_ticks(n.offset), 0x80 | channel, n.pitch, 0))
        # note off 를 note on 보다 먼저 처리해 같은 음의 겹침을 막는다
        msgs.sort(key=lambda m: (m[0], 0 if (m[1] & 0xF0) == 0x80 else 1, m[2]))

        body = bytearray()
        label = {"R": b"Right Hand", "L": b"Left Hand"}.get(name, b"Piano")
        body += _vlq(0) + b"\xff\x03" + _vlq(len(label)) + label
        prev = 0
        for tick, status, d1, d2 in msgs:
            body += _vlq(tick - prev) + bytes([status, d1, d2])
            prev = tick
        body += _vlq(0) + b"\xff\x2f\x00"
        chunks.append(_chunk(b"MTrk", bytes(body)))

    header = _chunk(b"MThd", struct.pack(">HHH", 1, len(chunks), TICKS_PER_BEAT))
    return header + b"".join(chunks)


def measures_to_midi(measures: list[Measure], tempo_bpm: int, meter: str = "4/4") -> bytes:
    from app.generation.assemble import measures_to_note_events

    return note_events_to_midi(
        measures_to_note_events(measures, tempo_bpm, meter), tempo_bpm=tempo_bpm
    )
