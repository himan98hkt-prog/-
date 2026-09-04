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

# 조표에 붙는 기호 개수. 단조는 나란한장조와 같은 조표를 쓴다 —
# 소문자(c단조)를 빠뜨리면 조표 3개짜리 곡이 다장조처럼 0으로 세어진다.
_KEY_SHARPS = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": 1, "B-": 2, "E-": 3, "A-": 4, "D-": 5, "G-": 6, "C-": 7,
    "a": 0, "e": 1, "b": 2, "f#": 3, "c#": 4, "g#": 5, "d#": 6, "a#": 7,
    "d": 1, "g": 2, "c": 3, "f": 4, "b-": 5, "e-": 6, "a-": 7,
}


# 정규화 상한(=1.0 이 되는 원값). 콩쿨 초·중급 레퍼토리(부르크뮐러~클레멘티) 관측 범위.
# 이 값을 넘어서면 특징이 1.0 에서 잘리므로, 아무리 더 어렵게 써도 점수가 오르지 않는다.
CAPS: dict[str, tuple[float, str]] = {
    "note_density": (10.0, "초당 음 수"),
    "hand_span": (14.0, "동시 타건 최대 폭(반음)"),
    "simultaneity": (4.0, "평균 동시음 수"),
    "key_signature": (5.0, "조표 개수"),
    "accidentals": (0.30, "임시표 비율"),
    "tempo": (180.0, "bpm"),
    "rhythm": (7.0, "쓰인 음길이 종류"),
    "lh_texture": (12.0, "왼손 저음 평균 도약(반음)"),
    "hand_motion": (12.0, "오른손 최고음 평균 이동(반음)"),
}


@dataclass
class DifficultyReport:
    score: float
    features: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)

    def saturated(self) -> dict[str, str]:
        """상한에 걸려 1.0 으로 잘린 특징 — 여기를 더 밀어도 점수는 오르지 않는다.

        난이도 9 를 겨냥한 곡에서 밀도가 21.96(상한 10)인데 점수가 7.9 에서 멈춘 일이
        있었다. 화면에 이것이 보이지 않으면 "더 어렵게 썼는데 왜 안 오르나" 가 된다.
        """
        out: dict[str, str] = {}
        for k, v in self.features.items():
            cap, unit = CAPS[k]
            raw = self.raw.get(k, 0.0)
            if v >= 1.0 and raw > cap:
                out[k] = f"{raw:.2f} / 상한 {cap:g} ({unit}) — {raw / cap:.1f}배"
        return out

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

    # 정규화 기준은 CAPS. 동시음·템포·리듬은 바닥이 0 이 아니라 1·60·1 이라 따로 뺀다.
    features = {
        "note_density": _clamp01(density / CAPS["note_density"][0]),
        "hand_span": _clamp01(max_span / CAPS["hand_span"][0]),
        "simultaneity": _clamp01((avg_simult - 1.0) / (CAPS["simultaneity"][0] - 1.0)),
        "key_signature": _clamp01(_KEY_SHARPS.get(key_sig, 0) / CAPS["key_signature"][0]),
        "accidentals": _clamp01(acc_ratio / CAPS["accidentals"][0]),
        "tempo": _clamp01((tempo - 60) / (CAPS["tempo"][0] - 60)),
        "rhythm": _clamp01((len(durs) - 1) / (CAPS["rhythm"][0] - 1)),
        "lh_texture": _clamp01(avg_lh_leap / CAPS["lh_texture"][0]),
        "hand_motion": _clamp01(avg_motion / CAPS["hand_motion"][0]),
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


# 조표 개수 → 그 개수를 쓰는 조성 예. 원장에게 "몇 개짜리로 잡아라" 만 말하면 막막하다.
_KEYS_BY_SHARPS: dict[int, str] = {
    0: "다장조·가단조", 1: "사장조·바장조·마단조·라단조", 2: "라장조·내림나장조·나단조·사단조",
    3: "가장조·내림마장조·올림바단조·다단조", 4: "마장조·내림가장조·올림다단조·바단조",
    5: "나장조·내림라장조·올림사단조·내림나단조", 6: "올림바장조·내림사장조",
    7: "올림다장조·내림다장조",
}

# 실무 상한. 이론적 상한(자유 특징이 전부 1.0)은 실제 곡에서 나오지 않는다 —
# 임시표·동시음·손 이동이 동시에 1.0 에 닿으려면 곡이 아니라 연습 자료가 된다.
# 아래 값은 난이도 8 이상을 겨냥해 실제로 쓴 곡들에서 관측한 상한이다.
_PRACTICAL_CEILING: dict[str, float] = {
    "note_density": 1.0, "simultaneity": 0.85, "accidentals": 0.55,
    "rhythm": 1.0, "lh_texture": 1.0, "hand_motion": 0.55,
}


def _practical_max(
    sharps: float, tempo: int, max_span_semitones: int, max_accidental_ratio: float
) -> float:
    """이 조표·템포·손 크기로 **실제 곡이** 닿을 수 있는 난이도 상한."""
    free = dict(_PRACTICAL_CEILING)
    free["hand_span"] = _clamp01(max_span_semitones / 14.0)
    free["accidentals"] = min(free["accidentals"], _clamp01(max_accidental_ratio / 0.30))
    total = sum(free[k] * WEIGHTS[k] for k in free)
    total += _clamp01((tempo - 60) / 120.0) * WEIGHTS["tempo"]
    total += _clamp01(sharps / 5.0) * WEIGHTS["key_signature"]
    return round(1.0 + total * 9.0, 2)


def key_signature_advice(
    *, target: float, tempo: int, key_sig: str = "C",
    max_span_semitones: int = 12, max_accidental_ratio: float = 0.25,
) -> str | None:
    """목표 난이도를 지금 조표로 맞출 수 있는가. 못 맞추면 조표 몇 개가 필요한지.

    곡을 96마디 다 쓰고 나서 "밀도·스팬·리듬이 전부 상한에 붙었는데도 모자란다" 를
    발견하는 일을 없앤다 — 그때 남는 손잡이는 조표뿐인데, 조성은 Plan 단계에서 정해진다.
    """
    now = int(_KEY_SHARPS.get(key_sig, 0))
    here = _practical_max(now, tempo, max_span_semitones, max_accidental_ratio)
    if here >= target:
        return None
    for n in range(now + 1, 8):
        if _practical_max(n, tempo, max_span_semitones, max_accidental_ratio) >= target:
            return (
                f"목표 난이도 {target:.1f} 은 조표 {now}개짜리 {key_sig} 로는 실무적으로 "
                f"{here:.1f} 까지가 한계다 — 밀도·손 스팬·리듬 어휘를 다 올려도 그렇다. "
                f"조표 {n}개 이상({_KEYS_BY_SHARPS[n]})으로 잡아라."
            )
    top = _practical_max(7, tempo, max_span_semitones, max_accidental_ratio)
    return (
        f"목표 난이도 {target:.1f} 은 조표를 7개까지 올려도 {top:.1f} 가 한계다 "
        f"(템포 {tempo}bpm · 손 스팬 {max_span_semitones}반음). "
        "템포를 올리거나 목표를 낮춰야 한다 — 조성만으로는 닿지 않는다."
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


# 난이도 특징을 '작곡가가 실행할 수 있는 지시' 로 옮기는 표.
# 값을 올리려면 왼쪽, 내리려면 오른쪽.
_LEVERS: dict[str, tuple[str, str]] = {
    "note_density": (
        "오른손 음을 더 잘게 쪼개라(4분→8분, 8분→16분)",
        "오른손 음을 합쳐라(8분 둘을 4분 하나로)",
    ),
    "simultaneity": (
        "강박에 3도·6도를 겹쳐 오른손을 두껍게 하라",
        "화음을 단음으로 풀어라",
    ),
    "hand_span": (
        "왼손 베이스를 옥타브로 잡아라",
        "동시 타건 폭을 좁혀라(옥타브를 5도로)",
    ),
    "rhythm": (
        "붙점·당김음·쉼표 뒤 진입 중 안 쓴 것을 하나 넣어라",
        "쓰는 음길이 종류를 줄여라",
    ),
    "lh_texture": (
        "왼손을 지속음에서 분산화음이나 도약 반주로 바꿔라",
        "왼손을 지속 화음으로 단순화하라",
    ),
    "hand_motion": (
        "선율에 옥타브 자리바꿈을 넣어 손이 크게 움직이게 하라",
        "선율을 한 자리 안에서 움직이게 하라",
    ),
}


def difficulty_advice(report: DifficultyReport, target: float, top: int = 3) -> list[str]:
    """목표 난이도에 맞추려면 무엇을 만져야 하는가.

    난이도 점수만 알려 주면 작곡가가 할 수 있는 일이 없다. 어느 특징이 얼마나
    모자란지와 **그 특징을 움직이는 손잡이**를 함께 줘야 다음 라운드가 의미를 갖는다.
    """
    gap = target - report.score
    if abs(gap) < 1e-9:
        return []
    up = gap > 0
    # 올려야 하면 낮은 특징부터, 내려야 하면 높은 특징부터 만진다.
    # 리포트에 실제로 있는 특징만 본다 — 없는 축을 0 으로 치면 늘 그것부터 만지게 된다.
    # 올릴 때는 **이미 상한에 붙은 특징을 손잡이로 내밀지 않는다** — 밀어도 점수가 안 오른다.
    usable = {
        k: v for k, v in report.features.items()
        if k in _LEVERS and not (up and v >= 1.0)
    }
    ranked = sorted(usable.items(), key=lambda kv: kv[1], reverse=not up)
    out = [
        f"난이도 {report.score:.2f} → 목표 {target:.1f} "
        f"({'올려야' if up else '내려야'} 한다, 차이 {abs(gap):.2f})"
    ]
    sat = report.saturated()
    if up and sat:
        out.append(
            "이미 상한에 걸린 특징(더 밀어도 점수가 오르지 않는다): "
            + ", ".join(f"{k} {d}" for k, d in sat.items())
        )
    out += [
        f"{k} {v:.2f} — {_LEVERS[k][0 if up else 1]}"
        for k, v in ranked[:top]
    ]
    if up and not ranked:
        out.append("자유 특징이 전부 상한이다 — 조표나 템포를 바꾸지 않으면 목표에 닿지 않는다")
    return out
