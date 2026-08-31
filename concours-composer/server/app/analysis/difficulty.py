"""§7.7 난이도 점수(1~10).

가중합. 각 특징을 0~1 로 정규화한 뒤 가중치를 곱해 더하고 1~10 으로 늘린다.
M8 에서 원장 라벨로 회귀 보정할 수 있도록 가중치와 특징값을 분리해 돌려준다.
부문 매핑: 유치 1~2 · 초등저 2~4 · 초등고 4~6 · 중등 6~8.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from music21 import meter as m21meter

from app.analysis.pitch import pitch_to_midi
from app.analysis.theory import count_accidentals
from app.schemas.music import Measure

# 합이 1.0
WEIGHTS: dict[str, float] = {
    "note_density": 0.16,     # 초당 음 수
    "hand_span": 0.14,        # 동시 타건 최대 폭
    "simultaneity": 0.10,     # 동시에 누르는 음 개수
    "key_signature": 0.08,    # 조표 개수
    "accidentals": 0.08,      # 임시표 비율
    "tempo": 0.12,
    "rhythm": 0.12,           # 리듬 어휘 복잡도
    "lh_texture": 0.10,       # 왼손 텍스처(알베르티·도약 반주 등)
    "hand_motion": 0.10,      # 손 이동 거리
}

_KEY_SHARPS = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": 1, "B-": 2, "E-": 3, "A-": 4, "D-": 5, "G-": 6, "C-": 7,
}


@dataclass
class DifficultyReport:
    score: float
    features: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)

    def division_hint(self) -> str:
        s = self.score
        if s < 2.5:
            return "유치부"
        if s < 4.5:
            return "초등 저학년부"
        if s < 6.5:
            return "초등 고학년부"
        if s < 8.5:
            return "중등부"
        return "고등·일반부"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def difficulty_score(
    measures: list[Measure], *, meter: str = "4/4", tempo: int = 100, key_sig: str = "C"
) -> DifficultyReport:
    if not measures:
        return DifficultyReport(score=1.0)

    bar_ql = float(m21meter.TimeSignature(meter).barDuration.quarterLength)
    seconds = max(1e-6, len(measures) * bar_ql * (60.0 / tempo))

    n_notes = 0
    max_span = 0
    simult_sum = 0
    simult_n = 0
    acc = 0
    durs: set[float] = set()
    lh_leaps: list[int] = []
    rh_motion: list[int] = []
    lh_prev: int | None = None
    rh_prev: int | None = None

    for m in measures:
        for v in m.rh:
            for e in v.events:
                if not e.pitches:
                    continue
                durs.add(e.dur)
                n_notes += len(e.pitches)
                midis = [pitch_to_midi(p) for p in e.pitches]
                max_span = max(max_span, max(midis) - min(midis))
                simult_sum += len(midis)
                simult_n += 1
                acc += count_accidentals(e.pitches, key_sig)
                top = max(midis)
                if rh_prev is not None:
                    rh_motion.append(abs(top - rh_prev))
                rh_prev = top
        for v in m.lh:
            for e in v.events:
                if not e.pitches:
                    continue
                durs.add(e.dur)
                n_notes += len(e.pitches)
                midis = [pitch_to_midi(p) for p in e.pitches]
                max_span = max(max_span, max(midis) - min(midis))
                simult_sum += len(midis)
                simult_n += 1
                acc += count_accidentals(e.pitches, key_sig)
                bot = min(midis)
                if lh_prev is not None:
                    lh_leaps.append(abs(bot - lh_prev))
                lh_prev = bot

    density = n_notes / seconds                       # 초당 음 수
    avg_simult = simult_sum / simult_n if simult_n else 1.0
    acc_ratio = acc / n_notes if n_notes else 0.0
    avg_motion = sum(rh_motion) / len(rh_motion) if rh_motion else 0.0
    avg_lh_leap = sum(lh_leaps) / len(lh_leaps) if lh_leaps else 0.0

    raw = {
        "note_density": density,
        "hand_span": float(max_span),
        "simultaneity": avg_simult,
        "key_signature": float(_KEY_SHARPS.get(key_sig, 0)),
        "accidentals": acc_ratio,
        "tempo": float(tempo),
        "rhythm": float(len(durs)),
        "lh_texture": avg_lh_leap,
        "hand_motion": avg_motion,
    }

    # 정규화 기준: 콩쿨 초·중급 레퍼토리(부르크뮐러~클레멘티) 관측 범위를 상한으로.
    features = {
        "note_density": _clamp01(density / 10.0),
        "hand_span": _clamp01(max_span / 14.0),
        "simultaneity": _clamp01((avg_simult - 1.0) / 3.0),
        "key_signature": _clamp01(_KEY_SHARPS.get(key_sig, 0) / 5.0),
        "accidentals": _clamp01(acc_ratio / 0.30),
        "tempo": _clamp01((tempo - 60) / 120.0),
        "rhythm": _clamp01((len(durs) - 1) / 6.0),
        "lh_texture": _clamp01(avg_lh_leap / 12.0),
        "hand_motion": _clamp01(avg_motion / 12.0),
    }

    weighted = sum(features[k] * WEIGHTS[k] for k in WEIGHTS)
    score = round(1.0 + weighted * 9.0, 2)
    return DifficultyReport(score=score, features=features, raw=raw)


# ── 실현 가능한 난이도 대역 ──────────────────────────────────────────────────
#
# 난이도의 일부 특징은 요청 시점에 이미 고정된다(템포·조표·학생 손 스팬·임시표 상한).
# 고정값이 극단이면 목표 난이도를 아무리 잘 써도 맞출 수 없다 — 예를 들어 60bpm·다장조로
# 난이도 9 를 요구하는 요청은 성립하지 않는다. 생성 전에 이것을 원장에게 알린다.


@dataclass
class Feasibility:
    min_score: float
    max_score: float
    fixed: dict[str, float] = field(default_factory=dict)

    def contains(self, target: float, tolerance: float = 1.0) -> bool:
        """검증기의 ±tolerance 규칙을 만족시킬 수 있는 목표인가."""
        return self.min_score - tolerance <= target <= self.max_score + tolerance

    def clamp(self, target: float) -> float:
        return max(self.min_score, min(self.max_score, target))

    def message(self, target: float) -> str:
        return (
            f"목표 난이도 {target:.1f} 은(는) 이 조건에서 만들 수 없다. "
            f"실현 가능 대역 {self.min_score:.1f}~{self.max_score:.1f} "
            f"(템포 {self.fixed.get('tempo', 0):.0f}bpm · 조표 {self.fixed.get('key_sharps', 0):.0f}개 · "
            f"손 스팬 {self.fixed.get('max_span_semitones', 0):.0f}반음 · "
            f"임시표 상한 {self.fixed.get('max_accidental_ratio', 0):.0%}). "
            "템포·조성을 바꾸거나 목표를 대역 안으로 옮겨라."
        )


def feasible_range(
    *, tempo: int, key_sig: str = "C", max_span_semitones: int = 12,
    max_accidental_ratio: float = 0.25,
) -> Feasibility:
    """고정 파라미터가 정하는 난이도 상·하한.

    자유 특징(밀도·동시음·리듬 어휘·왼손 텍스처·손 이동)은 각각 실무적으로 도달 가능한
    최소·최대를 쓴다. 실제 곡이 0 이나 1 에 닿는 일은 드물어 보수적으로 잡는다.
    """
    sharps = float(_KEY_SHARPS.get(key_sig, 0))
    fixed = {
        "tempo": _clamp01((tempo - 60) / 120.0),
        "key_signature": _clamp01(sharps / 5.0),
    }
    # 임시표는 상한까지만 쓸 수 있다(그 위는 검증기가 막는다).
    acc_max = _clamp01(max_accidental_ratio / 0.30)
    span_max = _clamp01(max_span_semitones / 14.0)

    free_min = {
        "note_density": 0.05, "hand_span": 0.0, "simultaneity": 0.0,
        "accidentals": 0.0, "rhythm": 0.0, "lh_texture": 0.0, "hand_motion": 0.05,
    }
    free_max = {
        "note_density": 1.0, "hand_span": span_max, "simultaneity": 1.0,
        "accidentals": acc_max, "rhythm": 1.0, "lh_texture": 1.0, "hand_motion": 1.0,
    }

    def score_of(free: dict[str, float]) -> float:
        total = sum(free[k] * WEIGHTS[k] for k in free)
        total += fixed["tempo"] * WEIGHTS["tempo"]
        total += fixed["key_signature"] * WEIGHTS["key_signature"]
        return round(1.0 + total * 9.0, 2)

    return Feasibility(
        min_score=score_of(free_min),
        max_score=score_of(free_max),
        fixed={
            "tempo": float(tempo),
            "key_sharps": sharps,
            "max_span_semitones": float(max_span_semitones),
            "max_accidental_ratio": max_accidental_ratio,
        },
    )
