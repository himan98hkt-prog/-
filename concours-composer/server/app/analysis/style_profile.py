"""§7.1 StyleProfile — 곡 하나의 스타일·난이도 지문.

코퍼스 곡(참고 악보), 생성곡, 원장이 올린 교재에 **같은 분석**을 적용한다.
이 프로필이 세 곳에 쓰인다.
1. Stage 0 컨텍스트 — "이런 어법으로 써라" 를 통계로 전달한다(저작권곡도 통계는 안전하다).
2. 검색 — 요청과 비슷한 참고곡을 고르는 특징 벡터.
3. 난이도 보정 — 원장이 매긴 난이도와 대조한다.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from music21 import meter as m21meter

from app.analysis.difficulty import difficulty_score
from app.analysis.pitch import pitch_to_midi
from app.analysis.theory import count_accidentals
from app.schemas.music import Measure


@dataclass
class HandProfile:
    lowest: int = 0
    highest: int = 0
    max_interval: int = 0        # 동시 타건 최대 폭(반음)
    density: float = 0.0         # 마디당 음 수
    scale_run_ratio: float = 0.0  # 순차진행 비율
    leap_ratio: float = 0.0


@dataclass
class StyleProfile:
    """§7.1 의 필드 구성. 저작권곡도 여기까지는 프롬프트에 넣어도 된다."""

    key: str = "C"
    mode: str = "major"
    meter: str = "4/4"
    tempo: int = 100
    measures: int = 0
    duration_est: float = 0.0
    rh: HandProfile = field(default_factory=HandProfile)
    lh: HandProfile = field(default_factory=HandProfile)
    rhythm_vocab: list[float] = field(default_factory=list)
    harmonic_rhythm: float = 0.0      # 마디당 화성 변화 횟수(근사)
    accidental_ratio: float = 0.0
    dynamics_range: list[str] = field(default_factory=list)
    articulation: list[str] = field(default_factory=list)
    motif_head_intervals: list[int] = field(default_factory=list)
    motif_head_rhythm: list[float] = field(default_factory=list)
    difficulty_score: float = 1.0
    difficulty_features: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    # 검색용 특징 벡터. 순서가 곧 차원 의미이므로 바꾸면 인덱스를 다시 만들어야 한다.
    VECTOR_KEYS = (
        "difficulty", "tempo", "rh_density", "lh_density", "rh_leap", "rh_span",
        "lh_span", "accidentals", "rhythm_variety", "harmonic_rhythm", "range_width",
    )

    def vector(self) -> list[float]:
        """0~1 정규화 특징 벡터. pgvector 로 옮길 때 이 함수만 재사용하면 된다."""
        rng = max(1, (self.rh.highest - self.lh.lowest))
        return [
            _n(self.difficulty_score, 1, 10),
            _n(self.tempo, 40, 200),
            _n(self.rh.density, 0, 16),
            _n(self.lh.density, 0, 16),
            _n(self.rh.leap_ratio, 0, 1),
            _n(self.rh.max_interval, 0, 14),
            _n(self.lh.max_interval, 0, 14),
            _n(self.accidental_ratio, 0, 0.3),
            _n(len(self.rhythm_vocab), 0, 8),
            _n(self.harmonic_rhythm, 0, 4),
            _n(rng, 12, 60),
        ]


def _n(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"차원이 다르다: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _hand_profile(measures: list[Measure], hand: str) -> HandProfile:
    midis: list[int] = []
    spans: list[int] = []
    steps: list[int] = []
    count = 0
    prev_top: int | None = None
    for m in measures:
        voices = m.rh if hand == "rh" else m.lh
        for v in voices:
            for e in v.events:
                if not e.pitches:
                    continue
                ms = [pitch_to_midi(p) for p in e.pitches]
                midis.extend(ms)
                spans.append(max(ms) - min(ms))
                count += len(ms)
                top = max(ms)
                if prev_top is not None:
                    steps.append(abs(top - prev_top))
                prev_top = top
    if not midis:
        return HandProfile()
    scalar = sum(1 for s in steps if s <= 2)
    leaps = sum(1 for s in steps if s >= 5)
    return HandProfile(
        lowest=min(midis), highest=max(midis),
        max_interval=max(spans) if spans else 0,
        density=round(count / max(1, len(measures)), 3),
        scale_run_ratio=round(scalar / len(steps), 3) if steps else 0.0,
        leap_ratio=round(leaps / len(steps), 3) if steps else 0.0,
    )


def extract(
    measures: list[Measure], *, key: str = "C", meter: str = "4/4", tempo: int = 100
) -> StyleProfile:
    """마디 리스트에서 StyleProfile 을 뽑는다. 코퍼스·생성곡에 같은 함수를 쓴다."""
    if not measures:
        return StyleProfile(key=key, meter=meter, tempo=tempo)

    measures = sorted(measures, key=lambda m: m.number)
    bar_ql = float(m21meter.TimeSignature(meter).barDuration.quarterLength)

    durs = Counter(
        e.dur for m in measures for v in (*m.rh, *m.lh) for e in v.events if e.pitches
    )
    all_pitches = [p for m in measures for p in m.all_pitches()]
    acc = count_accidentals(all_pitches, key) / len(all_pitches) if all_pitches else 0.0

    dynamics: list[str] = [str(d) for d in dict.fromkeys(m.dynamics for m in measures if m.dynamics)]
    artics: list[str] = [
        str(a) for a in dict.fromkeys(
            e.artic for m in measures for v in (*m.rh, *m.lh) for e in v.events
            if e.artic != "none"
        )
    ]

    # 화성 리듬: 왼손 최저음이 바뀌는 빈도로 근사한다(코드 분석 없이도 쓸 만하다).
    bass: list[int] = []
    for m in measures:
        low = [pitch_to_midi(p) for v in m.lh for e in v.events for p in e.pitches]
        if low:
            bass.append(min(low))
    changes = sum(1 for a, b in zip(bass, bass[1:], strict=False) if a % 12 != b % 12)

    # 모티브 머리: 첫 마디 오른손
    head_ivs: list[int] = []
    head_rhythm: list[float] = []
    first = measures[0]
    seq = [
        max(pitch_to_midi(p) for p in e.pitches)
        for v in first.rh for e in v.events if e.pitches
    ]
    head_ivs = [b - a for a, b in zip(seq, seq[1:], strict=False)]
    head_rhythm = [e.dur for v in first.rh for e in v.events]

    diff = difficulty_score(measures, meter=meter, tempo=tempo, key_sig=key)

    return StyleProfile(
        key=key,
        mode="minor" if key[:1].islower() else "major",
        meter=meter,
        tempo=tempo,
        measures=len(measures),
        duration_est=round(len(measures) * bar_ql * (60.0 / tempo), 1),
        rh=_hand_profile(measures, "rh"),
        lh=_hand_profile(measures, "lh"),
        rhythm_vocab=sorted(durs),
        harmonic_rhythm=round(changes / max(1, len(measures)), 3),
        accidental_ratio=round(acc, 3),
        dynamics_range=dynamics,
        articulation=artics,
        motif_head_intervals=head_ivs[:8],
        motif_head_rhythm=head_rhythm[:8],
        difficulty_score=diff.score,
        difficulty_features=diff.features,
    )
