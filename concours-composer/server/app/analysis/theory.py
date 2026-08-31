"""조성·화성 헬퍼. 규칙 기반 작곡과 음악성 지표가 공유한다."""
from __future__ import annotations

from app.analysis.pitch import midi_to_pitch, pitch_to_midi

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]          # 자연단음계
HARMONIC_MINOR = [0, 2, 3, 5, 7, 8, 11]

DEGREE = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6}

# 조표별 이명동음 선택. 플랫 조에서는 플랫으로 적어야 학생이 읽기 좋다.
FLAT_KEYS = {"F", "B-", "E-", "A-", "D-", "G-", "d", "g", "c", "f", "b-", "e-"}
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_NAMES = ["C", "D-", "D", "E-", "E", "F", "G-", "G", "A-", "A", "B-", "B"]


def key_tonic(key: str) -> int:
    """'A' / 'a minor' / 'B-' → tonic pitch class."""
    token = key.strip().split()[0]
    return pitch_to_midi(token[0].upper() + token[1:] + "4") % 12


def is_minor(key: str) -> bool:
    token = key.strip()
    return token.split()[0][0].islower() or "min" in token.lower()


def scale_pitch_classes(key: str) -> list[int]:
    tonic = key_tonic(key)
    steps = MINOR if is_minor(key) else MAJOR
    return [(tonic + s) % 12 for s in steps]


def spell(midi: int, key: str) -> str:
    """조표에 맞춰 음이름을 고른다(이명동음 정리 — 비평 루브릭 9 '기보 정합')."""
    names = _FLAT_NAMES if key.strip().split()[0] in FLAT_KEYS else _SHARP_NAMES
    return f"{names[midi % 12]}{midi // 12 - 1}"


def _degree_index(roman: str) -> tuple[int, bool, bool]:
    """로마숫자 → (음계도 인덱스 0~6, 단화음 여부, 7화음 여부)."""
    core = roman.split("/", maxsplit=1)[0].strip()
    letters = "".join(ch for ch in core if ch in "IViv")
    if not letters:
        return 0, False, False
    minor_chord = letters.islower()
    idx = DEGREE.get(letters.upper(), 0)
    return idx, minor_chord, "7" in core


def chord_pitch_classes(roman: str, key: str) -> list[int]:
    """로마숫자 화음의 구성음 pitch class. 화성 진행을 음표로 옮길 때 쓴다."""
    scale = scale_pitch_classes(key)
    idx, minor_chord, seventh = _degree_index(roman)
    root = scale[idx % 7]
    # 음계 위에 3도씩 쌓는 것이 기본이되, 로마숫자의 대소문자가 우선한다.
    third = (root + (3 if minor_chord else 4)) % 12
    fifth = (root + 7) % 12
    tones = [root, third, fifth]
    if seventh:
        tones.append((root + (11 if idx == 0 else 10)) % 12)
    return tones


def nearest_chord_tone(midi: int, roman: str, key: str) -> int:
    """가장 가까운 코드톤으로 스냅. 규칙 기반 실현이 화성을 벗어나지 않게 한다."""
    tones = chord_pitch_classes(roman, key)
    best = midi
    best_d = 99
    for delta in range(-6, 7):
        cand = midi + delta
        if cand % 12 in tones and abs(delta) < best_d:
            best, best_d = cand, abs(delta)
    return best


def nearest_scale_tone(midi: int, key: str) -> int:
    scale = scale_pitch_classes(key)
    for delta in (0, -1, 1, -2, 2):
        if (midi + delta) % 12 in scale:
            return midi + delta
    return midi


def triad_above(root_midi: int, roman: str, key: str) -> list[int]:
    tones = chord_pitch_classes(roman, key)
    root_pc = tones[0]
    base = root_midi - (root_midi % 12) + root_pc
    if base > root_midi:
        base -= 12
    out = [base]
    for pc in tones[1:]:
        n = base + ((pc - root_pc) % 12)
        out.append(n)
    return out


def transpose_name(name: str, semitones: int, key: str) -> str:
    return spell(pitch_to_midi(name) + semitones, key)


__all__ = [
    "chord_pitch_classes", "count_accidentals", "in_key_pitch_classes", "is_accidental",
    "is_minor", "key_tonic", "midi_to_pitch", "nearest_chord_tone",
    "nearest_scale_tone", "scale_pitch_classes", "spell", "transpose_name", "triad_above",
]


def in_key_pitch_classes(key: str) -> set[int]:
    """읽기 부담 없이 나오는 음들.

    단조는 화성적·가락적 단음계의 올림 7음(과 올림 6음)이 관용이다 — c단조의 B natural 을
    임시표로 세면 V-i 종지가 있는 곡이 전부 '읽기 어려움' 으로 걸린다.
    """
    base = set(scale_pitch_classes(key))
    if is_minor(key):
        tonic = key_tonic(key)
        base.add((tonic + 11) % 12)   # 화성적 단음계의 이끔음
        base.add((tonic + 9) % 12)    # 가락적 단음계의 올림 6음
    return base


def is_accidental(pitch_name: str, key: str) -> bool:
    """조표에 없는 음인가.

    조표 안의 샤프·플랫은 임시표가 아니다 — A장조의 F#/C#/G# 는 학생이 조표로 읽는다.
    음이름에 `#` 이 있는지로 세면 샤프 조의 곡이 전부 '읽기 어려움' 으로 잘못 걸린다.
    """
    return pitch_to_midi(pitch_name) % 12 not in in_key_pitch_classes(key)


def count_accidentals(pitch_names: list[str], key: str) -> int:
    return sum(1 for p in pitch_names if is_accidental(p, key))
