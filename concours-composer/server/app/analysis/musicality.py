"""§7.4 규칙 기반 음악성 지표.

"이상한 곡"을 사람이 듣기 전에 코드가 먼저 잡아내는 층이다(§7.9 4원칙).
각 지표는 0~1 로 정규화하고, 목표 문턱과 함께 돌려준다. 가중합이 musicality_score.
가중치는 M8 에서 원장 평가 데이터로 보정할 수 있도록 상수로 분리해 둔다.

지표 근거는 analysis/README.md 참조.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean, pstdev

from app.analysis.pitch import pitch_to_midi
from app.analysis.theory import is_minor
from app.schemas.music import CompositionPlan, Measure, MotifCandidate, ScoreEvent

WEIGHTS: dict[str, float] = {
    "motif_consistency": 0.20,   # 가장 무겁다 — 모티브가 곡을 하나로 묶는다
    "repetition_balance": 0.10,
    "melodic_contour": 0.11,
    "harmonic_consistency": 0.13,
    "phrase_balance": 0.11,
    "dynamic_curve": 0.09,
    "texture_contrast": 0.09,
    "playability": 0.07,
    "expressive_variety": 0.10,  # 나머지 지표가 못 재는 것 — 밋밋함
}

TARGETS: dict[str, float] = {
    "motif_consistency": 0.70,
    "repetition_balance": 0.60,
    "melodic_contour": 0.60,
    "harmonic_consistency": 0.85,
    "phrase_balance": 0.80,
    "dynamic_curve": 0.70,
    "texture_contrast": 0.50,
    "playability": 0.70,
    "expressive_variety": 0.65,
}

DEFAULT_THRESHOLD = 0.70


@dataclass
class Metric:
    key: str
    value: float
    target: float
    detail: str = ""

    @property
    def met(self) -> bool:
        return self.value >= self.target


@dataclass
class MusicalityReport:
    metrics: dict[str, Metric] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return round(sum(m.value * WEIGHTS[k] for k, m in self.metrics.items()), 4)

    @property
    def score_10(self) -> float:
        return round(self.score * 10, 2)

    def unmet(self) -> list[Metric]:
        return [m for m in self.metrics.values() if not m.met]

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "score_10": self.score_10,
            "metrics": {
                k: {"value": m.value, "target": m.target, "met": m.met, "detail": m.detail}
                for k, m in self.metrics.items()
            },
            "unmet": [m.key for m in self.unmet()],
        }


# ── 공용 추출기 ──────────────────────────────────────────────────────────────


def _rh_events(m: Measure) -> list[ScoreEvent]:
    return [e for v in m.rh for e in v.events]


def _melody(measures: list[Measure]) -> list[tuple[int, int, float]]:
    """(마디번호, 최고음 midi, 길이). 오른손 상성부를 선율로 본다."""
    out: list[tuple[int, int, float]] = []
    for m in sorted(measures, key=lambda x: x.number):
        for e in _rh_events(m):
            if e.pitches:
                out.append((m.number, max(pitch_to_midi(p) for p in e.pitches), e.dur))
    return out


def _measure_signature(m: Measure) -> tuple[tuple[float, tuple[int, ...]], ...]:
    """마디를 이조 불변이 아닌 '정확 반복' 판정용 서명으로."""
    sig: list[tuple[float, tuple[int, ...]]] = []
    for v in (*m.rh, *m.lh):
        for e in v.events:
            sig.append((e.dur, tuple(sorted(pitch_to_midi(p) for p in e.pitches))))
    return tuple(sig)


def _phrase_ranges(plan: CompositionPlan | None, measures: list[Measure]) -> list[tuple[int, int]]:
    if plan is not None:
        return [(p.measures[0], p.measures[1]) for p in plan.phrases()]
    nums = sorted(m.number for m in measures)
    if not nums:
        return []
    lo, hi = nums[0], nums[-1]
    return [(s, min(s + 3, hi)) for s in range(lo, hi + 1, 4)]


# ── 1. 모티브 일관성 ─────────────────────────────────────────────────────────


def _transforms(head: list[int]) -> list[tuple[str, list[int]]]:
    """허용하는 모티브 변형. 음정열이므로 이조는 이미 불변이다."""
    out = [("statement", head), ("inversion", [-i for i in head]), ("retrograde", head[::-1])]
    if len(head) >= 3:
        out.append(("fragment_head", head[: max(2, len(head) // 2)]))
        out.append(("fragment_tail", head[-max(2, len(head) // 2) :]))
    return out


def _matches(window: list[int], pattern: list[int], tol: int = 1) -> bool:
    """음정열 근사 일치. 각 음정 오차 ≤ tol 반음이면 '변형된 등장'으로 센다.

    tol=1 은 장/단 2도, 장/단 3도 같은 조성 안의 자연스러운 변형을 허용한다.
    """
    if len(window) != len(pattern) or not pattern:
        return False
    return all(abs(a - b) <= tol for a, b in zip(window, pattern, strict=True))


def motif_consistency(
    measures: list[Measure], motif: MotifCandidate | None, plan: CompositionPlan | None
) -> Metric:
    """모티브 머리가 프레이즈 몇 %에 (변형 포함) 등장하는가. 목표 ≥ 0.70."""
    if motif is None:
        return Metric("motif_consistency", 0.0, TARGETS["motif_consistency"], "모티브가 잠기지 않았다")

    head = motif.head_intervals()
    if len(head) < 2:
        return Metric("motif_consistency", 0.0, TARGETS["motif_consistency"], "모티브 머리가 너무 짧다")

    variants = _transforms(head)
    phrases = _phrase_ranges(plan, measures)
    if not phrases:
        return Metric("motif_consistency", 0.0, TARGETS["motif_consistency"], "프레이즈 구획 없음")

    line = _melody(measures)
    hits = 0
    found: list[str] = []
    for lo, hi in phrases:
        seq = [p for mn, p, _ in line if lo <= mn <= hi]
        ivs = [b - a for a, b in zip(seq, seq[1:], strict=False)]
        matched: str | None = None
        for name, pat in variants:
            n = len(pat)
            if n < 2 or len(ivs) < n:
                continue
            if any(_matches(ivs[i : i + n], pat) for i in range(len(ivs) - n + 1)):
                matched = name
                break
        if matched:
            hits += 1
            found.append(f"{lo}-{hi}:{matched}")
    value = hits / len(phrases)
    return Metric(
        "motif_consistency", round(value, 4), TARGETS["motif_consistency"],
        f"{hits}/{len(phrases)} 프레이즈에 등장 · {', '.join(found[:6])}",
    )


# ── 2. 반복/변화 균형 ────────────────────────────────────────────────────────


def repetition_balance(measures: list[Measure]) -> Metric:
    """정확 반복 비율이 20~45% 대역 안이면 1.0, 멀어질수록 선형 감점."""
    ms = sorted(measures, key=lambda m: m.number)
    if len(ms) < 2:
        return Metric("repetition_balance", 0.0, TARGETS["repetition_balance"], "마디가 너무 적다")
    sigs = [_measure_signature(m) for m in ms]
    seen: dict[tuple, int] = {}
    exact = 0
    for s in sigs:
        if s in seen:
            exact += 1
        seen[s] = seen.get(s, 0) + 1
    ratio = exact / len(sigs)
    lo, hi = 0.20, 0.45
    if lo <= ratio <= hi:
        value = 1.0
    elif ratio < lo:
        value = max(0.0, 1.0 - (lo - ratio) / lo)          # 반복이 없으면 산만하다
    else:
        value = max(0.0, 1.0 - (ratio - hi) / (1.0 - hi))  # 너무 반복하면 지루하다
    return Metric(
        "repetition_balance", round(value, 4), TARGETS["repetition_balance"],
        f"정확 반복 {ratio:.0%} (권장 20~45%)",
    )


# ── 3. 선율 윤곽 ─────────────────────────────────────────────────────────────


def melodic_contour(measures: list[Measure], plan: CompositionPlan | None) -> Metric:
    line = _melody(measures)
    if len(line) < 3:
        return Metric("melodic_contour", 0.0, TARGETS["melodic_contour"], "선율이 너무 짧다")
    ivs = [b - a for (_, a, _), (_, b, _) in zip(line, line[1:], strict=False)]
    leaps = sum(1 for i in ivs if abs(i) >= 5)   # 4도(5반음) 이상을 도약으로
    leap_ratio = leaps / len(ivs)
    lo, hi = 0.15, 0.35
    if lo <= leap_ratio <= hi:
        leap_score = 1.0
    elif leap_ratio < lo:
        leap_score = max(0.0, 1.0 - (lo - leap_ratio) / lo)
    else:
        leap_score = max(0.0, 1.0 - (leap_ratio - hi) / (1.0 - hi))

    peak_measure = max(line, key=lambda t: t[1])[0]
    if plan is not None:
        peak_score = 1.0 if abs(peak_measure - plan.climax.measure) <= 2 else 0.0
        detail_peak = f"최고음 {peak_measure}마디 / 클라이맥스 {plan.climax.measure}마디"
    else:
        peak_score = 1.0
        detail_peak = f"최고음 {peak_measure}마디 (Plan 없음)"

    value = 0.6 * leap_score + 0.4 * peak_score
    return Metric(
        "melodic_contour", round(value, 4), TARGETS["melodic_contour"],
        f"도약 {leap_ratio:.0%} (권장 15~35%) · {detail_peak}",
    )


# ── 4. 화성 리듬 일관성 ──────────────────────────────────────────────────────

_ROMAN_DEGREE = {
    "I": 0, "i": 0, "II": 2, "ii": 2, "III": 4, "iii": 4, "IV": 5, "iv": 5,
    "V": 7, "v": 7, "VI": 9, "vi": 9, "VII": 11, "vii": 11,
}
# 단조에서는 III·VI·VII 이 이미 내려간 음도를 뜻한다 — c단조의 VI 는 A♭장3화음이지
# A장3화음이 아니다. 장조 음도표로만 읽으면 단조 곡의 화음이 전부 '이탈' 로 잡힌다.
_ROMAN_DEGREE_MINOR = {**_ROMAN_DEGREE, "III": 3, "iii": 3, "VI": 8, "vi": 8,
                       "VII": 10, "vii": 10}


def _roman_chord_tones(roman: str, tonic_midi: int, key_is_minor: bool = False) -> set[int]:
    """로마숫자 → 화음 구성음 pitch class 집합. 7화음·전위 표기는 삼화음으로 축약한다."""
    core = roman.split("/", maxsplit=1)[0].strip()
    body = "".join(ch for ch in core if ch.isalpha() or ch in "#b")
    body = body.replace("o", "").replace("°", "").replace("ø", "")
    deg_key = "".join(ch for ch in body if ch in "IViv")
    table = _ROMAN_DEGREE_MINOR if key_is_minor else _ROMAN_DEGREE
    if deg_key not in table:
        return set()
    root = (tonic_midi + table[deg_key]) % 12
    minor = deg_key.islower()
    third = (root + (3 if minor else 4)) % 12
    fifth = (root + 7) % 12
    tones = {root, third, fifth}
    if "7" in core:
        tones.add((root + (10 if not core.startswith(("I", "IV")) else 11)) % 12)
    return tones


def harmonic_consistency(measures: list[Measure], plan: CompositionPlan | None) -> Metric:
    if plan is None or not plan.harmony:
        return Metric("harmonic_consistency", 0.0, TARGETS["harmonic_consistency"], "Plan 화성 없음")
    try:
        tonic = pitch_to_midi(plan.key.split()[0] + "4") % 12
    except ValueError:
        tonic = 0

    minor_key = is_minor(plan.key)
    by_measure = {h.measure: h.roman for h in plan.harmony}
    total = 0
    chordal = 0
    misses: list[int] = []
    for m in sorted(measures, key=lambda x: x.number):
        roman = by_measure.get(m.number)
        if not roman:
            continue
        tones = _roman_chord_tones(roman, tonic, minor_key)
        if not tones:
            continue
        m_total = m_chordal = 0
        for p in m.all_pitches():
            m_total += 1
            if pitch_to_midi(p) % 12 in tones:
                m_chordal += 1
        total += m_total
        chordal += m_chordal
        if m_total and m_chordal / m_total < 0.5:
            misses.append(m.number)
    if not total:
        return Metric("harmonic_consistency", 0.0, TARGETS["harmonic_consistency"], "대조할 음이 없다")
    value = chordal / total
    detail = f"코드톤 비율 {value:.0%}"
    if misses:
        detail += f" · 이탈 마디 {misses[:6]}"
    return Metric("harmonic_consistency", round(value, 4), TARGETS["harmonic_consistency"], detail)


# ── 5. 프레이즈 균형 ─────────────────────────────────────────────────────────


def phrase_balance(measures: list[Measure], plan: CompositionPlan | None) -> Metric:
    """프레이즈 끝에 긴 음이나 쉼표(호흡)가 있는가. 목표 ≥ 0.80."""
    phrases = _phrase_ranges(plan, measures)
    if not phrases:
        return Metric("phrase_balance", 0.0, TARGETS["phrase_balance"], "프레이즈 구획 없음")
    by_number = {m.number: m for m in measures}
    good = 0
    bad: list[int] = []
    for _lo, hi in phrases:
        m = by_number.get(hi)
        if m is None:
            continue
        evs = _rh_events(m)
        if not evs:
            continue
        tail = evs[-1]
        if tail.is_rest or tail.dur >= 1.5:
            good += 1
        else:
            bad.append(hi)
    value = good / len(phrases)
    detail = f"{good}/{len(phrases)} 프레이즈가 호흡으로 끝난다"
    if bad:
        detail += f" · 숨 못 쉬는 마디 {bad[:6]}"
    return Metric("phrase_balance", round(value, 4), TARGETS["phrase_balance"], detail)


# ── 6. 다이내믹 곡선 ─────────────────────────────────────────────────────────

_DYN_LEVEL = {"ppp": 0, "pp": 1, "p": 2, "mp": 3, "mf": 4, "f": 5, "ff": 6, "fff": 7}


def dynamic_curve(measures: list[Measure], plan: CompositionPlan | None) -> Metric:
    if plan is None or not plan.dynamics_curve:
        return Metric("dynamic_curve", 0.0, TARGETS["dynamic_curve"], "Plan 다이내믹 곡선 없음")
    planned = {d.measure: _DYN_LEVEL[d.dyn] for d in plan.dynamics_curve}
    actual = {m.number: _DYN_LEVEL[m.dynamics] for m in measures if m.dynamics}
    common = sorted(set(planned) & set(actual))
    if len(common) < 2:
        return Metric("dynamic_curve", 0.0, TARGETS["dynamic_curve"],
                      f"Plan 과 악보가 겹치는 다이내믹 지점 {len(common)}개 — 표기가 빠졌다")
    xs = [planned[m] for m in common]
    ys = [actual[m] for m in common]
    sx, sy = pstdev(xs), pstdev(ys)
    if sx == 0 or sy == 0:
        value = 1.0 if xs == ys else 0.0
        return Metric("dynamic_curve", value, TARGETS["dynamic_curve"], "다이내믹 변화가 없다")
    mx, my = fmean(xs), fmean(ys)
    cov = fmean([(a - mx) * (b - my) for a, b in zip(xs, ys, strict=True)])
    corr = cov / (sx * sy)
    value = max(0.0, min(1.0, (corr + 1) / 2)) if corr < 0 else corr
    return Metric("dynamic_curve", round(value, 4), TARGETS["dynamic_curve"],
                  f"Plan 대비 상관 {corr:.2f} ({len(common)}개 지점)")


# ── 7. 텍스처 대비 ───────────────────────────────────────────────────────────


def _lh_texture_fingerprint(measures: list[Measure]) -> tuple[float, float, float]:
    """왼손 텍스처를 (평균 동시음 수, 평균 음역 중심, 평균 음 길이) 로 요약."""
    simult: list[int] = []
    centers: list[float] = []
    durs: list[float] = []
    for m in measures:
        for v in m.lh:
            for e in v.events:
                if not e.pitches:
                    continue
                midis = [pitch_to_midi(p) for p in e.pitches]
                simult.append(len(midis))
                centers.append(sum(midis) / len(midis))
                durs.append(e.dur)
    if not simult:
        return (0.0, 0.0, 0.0)
    return (fmean(simult), fmean(centers), fmean(durs))


def texture_contrast(measures: list[Measure], plan: CompositionPlan | None) -> Metric:
    """섹션 사이에 왼손 텍스처·음역 변화가 있는가. B 섹션에 최소 1개."""
    if plan is None or len(plan.form) < 2:
        return Metric("texture_contrast", 0.0, TARGETS["texture_contrast"], "섹션이 하나뿐이다")
    by_number = {m.number: m for m in measures}
    prints: list[tuple[str, tuple[float, float, float]]] = []
    for s in plan.form:
        sec = [by_number[n] for n in range(s.measures[0], s.measures[1] + 1) if n in by_number]
        if sec:
            prints.append((s.label, _lh_texture_fingerprint(sec)))
    if len(prints) < 2:
        return Metric("texture_contrast", 0.0, TARGETS["texture_contrast"], "비교할 섹션이 없다")

    changes = 0
    notes: list[str] = []
    for (l1, f1), (l2, f2) in zip(prints, prints[1:], strict=False):
        if l1 == l2:
            continue
        diffs = []
        if abs(f1[0] - f2[0]) >= 0.5:
            diffs.append("동시음")
        if abs(f1[1] - f2[1]) >= 3.0:
            diffs.append("음역")
        if abs(f1[2] - f2[2]) >= 0.5:
            diffs.append("리듬")
        if diffs:
            changes += 1
            notes.append(f"{l1}→{l2}: {'·'.join(diffs)}")
    boundaries = max(1, sum(1 for (l1, _), (l2, _) in zip(prints, prints[1:], strict=False) if l1 != l2))
    value = min(1.0, changes / boundaries)
    return Metric("texture_contrast", round(value, 4), TARGETS["texture_contrast"],
                  "; ".join(notes) if notes else "섹션이 바뀌어도 왼손이 그대로다")


# ── 8. 연주 편의 ─────────────────────────────────────────────────────────────


def playability(measures: list[Measure], max_span_semitones: int) -> Metric:
    """스팬·연속 도약·손 이동 거리. 난이도 검증기와 같은 재료를 쓴다.

    이동 거리는 **손마다 따로** 센다. 두 손을 이어 붙여 세면 오른손 마지막 음에서
    왼손 첫 음으로 건너뛰는 것이 매 마디 거대한 '이동' 으로 잡혀, 두 손이 각자
    편하게 움직이는 곡도 연주가 어렵다고 나온다.
    """
    spans: list[int] = []
    motions: list[int] = []
    worst_run = 0

    for hand in ("rh", "lh"):
        prev_top: int | None = None
        consecutive_leaps = 0
        for m in sorted(measures, key=lambda x: x.number):
            for v in (m.rh if hand == "rh" else m.lh):
                for e in v.events:
                    if not e.pitches:
                        continue
                    midis = [pitch_to_midi(p) for p in e.pitches]
                    spans.append(max(midis) - min(midis))
                    top = max(midis)
                    if prev_top is not None:
                        d = abs(top - prev_top)
                        motions.append(d)
                        consecutive_leaps = consecutive_leaps + 1 if d >= 9 else 0
                        worst_run = max(worst_run, consecutive_leaps)
                    prev_top = top

    if not spans:
        return Metric("playability", 0.0, TARGETS["playability"], "음이 없다")

    over = sum(1 for s in spans if s > max_span_semitones)
    span_score = 1.0 - over / len(spans)
    avg_motion = fmean(motions) if motions else 0.0
    motion_score = max(0.0, 1.0 - max(0.0, avg_motion - 5.0) / 10.0)
    leap_score = max(0.0, 1.0 - worst_run / 4.0)
    value = 0.5 * span_score + 0.3 * motion_score + 0.2 * leap_score
    return Metric(
        "playability", round(value, 4), TARGETS["playability"],
        f"스팬 초과 {over}회 · 평균 이동 {avg_motion:.1f}반음 · 연속 도약 최대 {worst_run}회",
    )


# ── 9. 표현 다양성 ───────────────────────────────────────────────────────────
#
# 앞의 여덟 지표는 **곡이 옳은가**를 잰다 — 모티브를 지키는가, 화성을 벗어나지
# 않는가, 손에 무리가 없는가. 옳은 곡은 밋밋해도 만점이 나온다. 실제로 4분음표만
# 쓰고 6도 안에서만 움직이는 유치부 곡이 종합 9.79 로 가장 높은 점수를 받았는데,
# 들어보면 다섯 곡 중 가장 심심했다.
#
# 그래서 '심심함' 을 따로 잰다. 다만 **난이도 목표에 상대적으로** 재야 한다.
# 유치부 곡에 16분음표와 2옥타브를 요구하면 그건 지표가 아니라 고장이다.


def _expected(base: float, per_level: float, difficulty: float, cap: float) -> float:
    return min(cap, base + per_level * max(1.0, difficulty))


def _rhythm_signature(m: Measure) -> tuple[float, ...]:
    return tuple(e.dur for v in m.rh for e in v.events)


def expressive_variety(measures: list[Measure], difficulty_target: float) -> Metric:
    """난이도 대비 표현의 폭. 목표 ≥ 0.65.

    네 갈래로 나눠 본다 — 리듬 어휘, 선율 음역, 마디 리듬의 중복, 표현 기호.
    각각 '이 난이도라면 이만큼은 나와야 한다' 는 기대치로 나눈다.

    **이 지표는 순위가 아니라 바닥이다.** 제대로 쓴 곡들은 0.85~1.00 에 몰려 있어
    서로를 가려주지 못한다. 대신 4분음표만 쓰고 6도 안에서만 움직이고 다이내믹이
    하나뿐인 곡은 0.25 부근으로 떨어진다 — 잡아야 할 것이 그것이다.
    '흥미로운가' 는 사람이 듣고 판단한다.
    """
    if not measures:
        return Metric("expressive_variety", 0.0, TARGETS["expressive_variety"], "마디가 없다")

    # 1) 리듬 어휘 — 쓰는 음길이가 몇 가지인가
    durs = {e.dur for m in measures for v in (*m.rh, *m.lh) for e in v.events}
    want_durs = _expected(3.0, 0.40, difficulty_target, 7.0)
    rhythm_score = min(1.0, len(durs) / want_durs)

    # 2) 선율 음역 — 오른손 선율이 몇 반음 안에서 움직이는가
    line = [p for _, p, _ in _melody(measures)]
    span = (max(line) - min(line)) if len(line) >= 2 else 0
    want_span = _expected(12.0, 1.2, difficulty_target, 26.0)
    range_score = min(1.0, span / want_span)

    # 3) 마디 리듬 중복 — 같은 리듬형이 곡을 뒤덮고 있는가
    sigs = [_rhythm_signature(m) for m in measures if any(m.rh)]
    if sigs:
        top = max(sigs.count(x) for x in set(sigs)) / len(sigs)
        # 반주형이 일정한 곡은 오른손 리듬도 40%대에서 겹친다 — 정상이다.
        # 곡 전체가 한 가지 리듬형일 때만 0 으로 떨어진다.
        sameness_score = 1.0 if top <= 0.45 else max(0.0, 1.0 - (top - 0.45) / 0.55)
    else:
        top, sameness_score = 0.0, 0.0

    # 4) 표현 기호 — 다이내믹이 변하는가, 아티큘레이션·이음줄이 있는가
    dyns = {m.dynamics for m in measures if m.dynamics}
    articulated = any(
        e.artic != "none" or e.slur is not None
        for m in measures for v in (*m.rh, *m.lh) for e in v.events
    )
    mark_score = 0.6 * min(1.0, max(0, len(dyns) - 1) / 2.0) + 0.4 * (1.0 if articulated else 0.0)

    value = 0.30 * rhythm_score + 0.30 * range_score + 0.25 * sameness_score + 0.15 * mark_score
    return Metric(
        "expressive_variety", round(value, 4), TARGETS["expressive_variety"],
        f"난이도 {difficulty_target:.1f} 기준 · 리듬 어휘 {len(durs)}종(기대 {want_durs:.1f}) · "
        f"선율 음역 {span}반음(기대 {want_span:.0f}) · "
        f"같은 리듬형 {top:.0%} · 다이내믹 {len(dyns)}종"
        f"{' · 아티큘레이션 없음' if not articulated else ''}",
    )


# ── 진입점 ───────────────────────────────────────────────────────────────────


def evaluate(
    measures: list[Measure],
    *,
    motif: MotifCandidate | None = None,
    plan: CompositionPlan | None = None,
    max_span_semitones: int = 12,
    difficulty_target: float | None = None,
) -> MusicalityReport:
    if difficulty_target is None:
        difficulty_target = plan.difficulty_target if plan is not None else 5.0
    r = MusicalityReport()
    for m in (
        motif_consistency(measures, motif, plan),
        repetition_balance(measures),
        melodic_contour(measures, plan),
        harmonic_consistency(measures, plan),
        phrase_balance(measures, plan),
        dynamic_curve(measures, plan),
        texture_contrast(measures, plan),
        playability(measures, max_span_semitones),
        expressive_variety(measures, difficulty_target),
    ):
        r.metrics[m.key] = m
    return r
