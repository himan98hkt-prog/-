"""음이름 ↔ MIDI 번호 변환. music21 없이 동작하는 순수 함수(핫 패스에서 자주 쓴다)."""
from __future__ import annotations

import re

_STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAME = ["C", "C#", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B"]
_RE = re.compile(r"^([A-Ga-g])([#b\-x]*)(-?\d+)$")


def pitch_to_midi(name: str) -> int:
    """'C4' → 60, 'B-3' → 58, 'F#5' → 78. music21 표기(`-` = 플랫)와 `b` 둘 다 받는다."""
    m = _RE.match(name.strip())
    if not m:
        raise ValueError(f"음이름을 해석할 수 없다: {name!r}")
    step, accs, octave = m.group(1).upper(), m.group(2), int(m.group(3))
    alter = 0
    for ch in accs:
        alter += {"#": 1, "b": -1, "-": -1, "x": 2}[ch]
    midi = (octave + 1) * 12 + _STEP[step] + alter
    if not 0 <= midi <= 127:
        raise ValueError(f"MIDI 범위를 벗어난다: {name!r} → {midi}")
    return midi


def midi_to_pitch(midi: int) -> str:
    """60 → 'C4'. 이명동음은 조표 문맥이 없으므로 샤프/플랫 기본 표기를 쓴다."""
    if not 0 <= midi <= 127:
        raise ValueError(f"MIDI 범위를 벗어난다: {midi}")
    return f"{_NAME[midi % 12]}{midi // 12 - 1}"


def interval(a: str, b: str) -> int:
    return pitch_to_midi(b) - pitch_to_midi(a)
