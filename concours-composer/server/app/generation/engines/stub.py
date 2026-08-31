"""규칙 기반 오프라인 작곡 엔진.

용도는 셋이다.
1. API 키 없이 파이프라인 전체(모티브→Plan→Realize→검증→비평 루프)를 돌려 테스트한다.
2. 골든 회귀에서 '파이프라인 자체의 결함'과 '모델 출력의 편차'를 분리한다.
3. Claude 호출이 실패했을 때의 최후 폴백.

음악적 야심은 없다. 다만 **문법적으로 옳고, 모티브를 실제로 전개하고, 화성을 따르는**
악보를 결정적으로 만든다 — 검증기와 음악성 지표가 무엇을 잡아내는지 확인할 수 있을 만큼은.
난수를 쓰지 않으므로 같은 입력이면 항상 같은 곡이 나온다.
"""
from __future__ import annotations

from typing import ClassVar

from music21 import meter as m21meter

from app.analysis import theory
from app.analysis.pitch import pitch_to_midi
from app.generation.context import ComposerContext, estimate_measures
from app.generation.engines.base import PhraseRequest
from app.schemas.music import (
    Climax,
    CompositionPlan,
    DynamicPoint,
    Ending,
    Measure,
    MotifCandidate,
    MotifSource,
    PhrasePlan,
    PhraseRealization,
    ScoreEvent,
    SectionPlan,
    Showcase,
    Voice,
)
from app.schemas.quality import CriticReport, RevisionRequest, RubricScores

# 모티브 원형: (음정열, 리듬, 성격). 음정열은 으뜸음에서 출발하는 상대 음정.
ARCHETYPES: list[tuple[list[int], list[float], str]] = [
    ([2, 2, 1, -5], [0.5, 0.5, 1.0, 2.0], "씩씩한 행진"),
    ([4, -2, -2, 3], [1.0, 0.5, 0.5, 2.0], "물음표 같은"),
    ([7, -2, -1, -2], [1.5, 0.5, 1.0, 1.0], "높이 뛰어올라"),
    ([1, 2, -3, 2], [0.5, 0.5, 0.5, 2.5], "속삭이는"),
    ([5, -5, 2, 2], [1.0, 1.0, 1.0, 1.0], "물음과 대답"),
]

# 섹션별 화성 진행 원형(장조 기준). 4마디 단위로 순환시킨다.
PROGRESSIONS: dict[str, list[str]] = {
    "A": ["I", "IV", "V", "I", "I", "vi", "ii", "V"],
    "B": ["vi", "iii", "IV", "V", "vi", "ii", "V7", "I"],
    "A'": ["I", "IV", "V7", "I", "IV", "I", "V7", "I"],
}


# 검증기와 같은 기보 가능 길이 집합을 쓴다.
_NOTATABLE = frozenset(
    {0.125, 0.1875, 0.25, 0.375, 0.4375, 0.5, 0.75, 0.875, 1.0, 1.5, 1.75, 2.0, 3.0, 3.5, 4.0, 6.0, 7.0, 8.0}
)


class TextureLevel:
    """목표 난이도를 실제 텍스처 손잡이로 바꾼다.

    난이도 점수(§7.7)는 밀도·동시음·손 이동·리듬 어휘의 가중합이므로,
    엔진이 목표 난이도를 맞추려면 그 손잡이들을 직접 움직여야 한다.
    """

    def __init__(self, target: float, tempo: int = 100) -> None:
        self.target = target
        self.tempo = tempo
        # 리듬 세분화 배수 — 밀도를 지배한다.
        self.subdivide = 1 if target < 3.0 else (2 if target < 5.5 else (3 if target < 7.5 else 4))
        # 밀도는 '초당 음 수' 다. 느린 곡에서 같은 밀도를 내려면 더 잘게 쪼개야 한다
        # (느린 템포 + 빠른 음형 = 어려운 곡이라는 실제 감각과도 맞는다).
        if tempo < 84 and target >= 5.5:
            self.subdivide = min(4, self.subdivide + 1)
        # 반대로 빠른 곡에서 쉬운 난이도를 내려면 덜 쪼갠다.
        if tempo > 120 and target < 4.0:
            self.subdivide = 1
        # 아주 쉬운 곡은 오히려 리듬을 합쳐 성기게 만든다.
        self.coarsen = target < 3.0
        # 오른손 화음 두께
        self.rh_voices = 1 if target < 5.5 else (2 if target < 8.0 else 3)
        # 왼손 패턴: 지속음 → 알베르티 → 옥타브 도약 → 넓은 분산화음
        self.lh_style = (
            "sustain" if target < 3.0
            else "alberti" if target < 5.5
            else "leaping" if target < 7.5
            else "wide"
        )
        # 리듬 어휘 가짓수(난이도 특징 rhythm)
        self.rhythm_variety = 2 if target < 3.0 else (3 if target < 5.5 else (5 if target < 7.5 else 6))
        # 화음을 얹는 주기(음 몇 개마다). 1 이면 모든 음이 화음 — 동시음 특징을 지배한다.
        self.chord_every = 0 if self.rh_voices <= 1 else (2 if target >= 8.0 else 3)
        # 옥타브 도약 주기. 손 이동 거리(난이도 특징 hand_motion)를 만든다.
        self.leap_every = 0 if target < 6.0 else (4 if target < 8.0 else 3)

    # 2등분만 반복해 쪼갠다 — 3등분은 셋잇단 표기가 필요해 MusicXML 로 못 적는다.
    _SPLITS: ClassVar[dict[int, tuple[int, int]]] = {1: (1, 1), 2: (2, 1), 3: (2, 4), 4: (4, 2)}

    def coarsen_rhythm(self, durs: list[float], bar: float) -> list[float]:
        """이웃한 짧은 음을 합쳐 성기게 만든다 — 유치·초등 저학년 난이도를 위해."""
        out: list[float] = []
        i = 0
        while i < len(durs):
            if i + 1 < len(durs) and durs[i] < 1.0 and durs[i + 1] < 1.0:
                out.append(_snap_notatable(durs[i] + durs[i + 1]))
                i += 2
            else:
                out.append(durs[i])
                i += 1
        return _fit_rhythm(out, bar)

    def shape_rhythm(self, durs: list[float], bar: float) -> list[float]:
        return self.coarsen_rhythm(durs, bar) if self.coarsen else self.subdivide_rhythm(durs, bar)

    def subdivide_rhythm(self, durs: list[float], bar: float) -> list[float]:
        """durs 를 잘게 쪼갠다. 마디 길이와 '기보 가능한 길이'를 함께 지킨다."""
        if self.subdivide <= 1:
            return durs
        even, odd = self._SPLITS[self.subdivide]
        out: list[float] = []
        for i, d in enumerate(durs):
            # 전부 같은 값으로 쪼개면 리듬 어휘가 하나로 줄어든다 — 번갈아 쪼갠다.
            n = even if i % 2 == 0 else odd
            piece = d / n
            if n == 1 or piece < 0.25 or round(piece, 6) not in _NOTATABLE:
                out.append(d)
                continue
            out.extend([round(piece, 6)] * n)
        return _fit_rhythm(out, bar)


def _climax_measure(total: int) -> int:
    """클라이맥스를 전체의 60~80% 안에 놓되 프레이즈 시작에 맞춘다.

    프레이즈 경계로만 반올림하면 짧은 곡(16마디)에서 대역 밖으로 밀린다 —
    먼저 프레이즈 시작 후보를 모으고, 그중 대역 안에 있는 것을 고른다.
    """
    lo, hi = total * 0.60, total * 0.80
    starts = [m for m in range(1, total + 1, 4) if lo <= m <= hi]
    if starts:
        # 대역 안 후보 중 72% 지점에 가장 가까운 것
        return min(starts, key=lambda m: abs(m - total * 0.72))
    # 프레이즈 시작이 대역에 하나도 없으면(아주 짧은 곡) 마디 단위로 맞춘다.
    return max(1, min(total - 1, round(total * 0.70)))


def _bar_ql(meter: str) -> float:
    return float(m21meter.TimeSignature(meter).barDuration.quarterLength)


def _snap_notatable(d: float) -> float:
    """가장 가까운 기보 가능한 길이로 내린다."""
    candidates = sorted(x for x in _NOTATABLE if x <= d + 1e-9)
    return candidates[-1] if candidates else min(_NOTATABLE)


def _fit_rhythm(rhythm: list[float], bar: float) -> list[float]:
    """리듬 패턴을 마디 길이에 정확히 맞춘다.

    남으면 기보 가능한 길이로 채우고, 넘치면 자른다. 결과의 모든 값은 기보 가능해야 한다
    (§7.6 notatable_duration 하드 규칙).
    """
    out: list[float] = []
    total = 0.0
    for raw in rhythm:
        d = _snap_notatable(round(raw, 6))
        if total + d >= bar - 1e-9:
            rest = round(bar - total, 6)
            if rest > 1e-9:
                out.append(_snap_notatable(rest))
            break
        out.append(d)
        total += d

    total = round(sum(out), 6)
    # 모자란 만큼을 기보 가능한 조각으로 채운다.
    guard = 0
    while total < bar - 1e-9 and guard < 32:
        piece = _snap_notatable(round(bar - total, 6))
        out.append(piece)
        total = round(total + piece, 6)
        guard += 1
    return [d for d in out if d > 0]


class StubComposerEngine:
    """결정적 규칙 기반 엔진."""

    name = "stub-rule-based"

    # ── Stage 1 ──────────────────────────────────────────────────────────
    def motifs(self, ctx: ComposerContext, n: int, feedback: str = "") -> list[MotifCandidate]:
        key = (ctx.request.key_preference or ["C"])[0]
        meter = ctx.request.meter
        bar = _bar_ql(meter)
        tempo = min(ctx.request.tempo, ctx.student.tempo_comfort_max_bpm)
        # 피드백이 오면 원형 목록을 회전시켜 다른 성격이 앞으로 오게 한다.
        offset = len(feedback) % len(ARCHETYPES)

        out: list[MotifCandidate] = []
        for i in range(min(n, len(ARCHETYPES))):
            ivs, rhythm, label = ARCHETYPES[(i + offset) % len(ARCHETYPES)]
            start = self._comfortable_start(ctx, key)
            durs = _fit_rhythm(rhythm, bar)

            midi = start
            events: list[ScoreEvent] = []
            for j, d in enumerate(durs):
                if j > 0:
                    midi = theory.nearest_scale_tone(midi + ivs[(j - 1) % len(ivs)], key)
                midi = max(ctx.hard.lowest_midi, min(ctx.hard.highest_midi, midi))
                events.append(
                    ScoreEvent(
                        dur=d,
                        pitches=[theory.spell(midi, key)],
                        slur="start" if j == 0 else ("stop" if j == len(durs) - 1 else None),
                    )
                )
            # 두 번째 마디: 같은 윤곽을 한 음 아래에서 — 모티브가 '문답' 을 이룬다.
            events2: list[ScoreEvent] = []
            midi2 = theory.nearest_scale_tone(start - 2, key)
            for j, d in enumerate(durs):
                if j > 0:
                    midi2 = theory.nearest_scale_tone(midi2 + ivs[(j - 1) % len(ivs)], key)
                midi2 = max(ctx.hard.lowest_midi, min(ctx.hard.highest_midi, midi2))
                events2.append(ScoreEvent(dur=d, pitches=[theory.spell(midi2, key)]))
            # 프레이즈 호흡: 둘째 마디 끝을 길게
            events2[-1] = ScoreEvent(dur=events2[-1].dur, pitches=events2[-1].pitches)

            lh1 = self._simple_lh("I", key, bar, ctx)
            lh2 = self._simple_lh("V", key, bar, ctx)

            out.append(
                MotifCandidate(
                    id=f"motif-{i + 1}",
                    measures=[
                        Measure(number=1, rh=[Voice(events=events)], lh=[Voice(events=lh1)], dynamics="mf"),
                        Measure(number=2, rh=[Voice(events=events2)], lh=[Voice(events=lh2)]),
                    ],
                    key=key,
                    meter=meter,
                    tempo=tempo,
                    character_label=label,
                    why_it_works=(
                        f"머리 음정열 {ivs[:3]} 이 순차와 도약을 섞어 기억에 남고, "
                        "둘째 마디에서 한 음 아래로 답하므로 동형진행·전위로 그대로 늘릴 수 있다."
                    ),
                    source=MotifSource.ai,
                )
            )
        return out

    def _comfortable_start(self, ctx: ComposerContext, key: str) -> int:
        """학생 음역 가운데쯤에서 으뜸음 근처를 고른다."""
        center = (ctx.hard.lowest_midi + ctx.hard.highest_midi) // 2
        center = max(center, 60)
        tonic = theory.key_tonic(key)
        cand = center - (center % 12) + tonic
        if cand < center - 6:
            cand += 12
        return max(ctx.hard.lowest_midi, min(ctx.hard.highest_midi - 12, cand))

    def _simple_lh(self, roman: str, key: str, bar: float, ctx: ComposerContext) -> list[ScoreEvent]:
        """모티브를 방해하지 않는 최소 반주 — 5도 베이스 지속음."""
        tones = theory.chord_pitch_classes(roman, key)
        root = 48 + ((tones[0] - 48) % 12)
        while root < ctx.hard.lowest_midi:
            root += 12
        fifth = root + 7
        if fifth - root > ctx.hard.max_span_semitones:
            fifth = root
        pitches = [theory.spell(root, key)]
        if fifth != root:
            pitches.append(theory.spell(fifth, key))
        return [ScoreEvent(dur=bar, pitches=pitches)]

    # ── Stage 2 ──────────────────────────────────────────────────────────
    def plan(self, ctx: ComposerContext, motif: MotifCandidate) -> CompositionPlan:
        key, meter, tempo = motif.key, motif.meter, motif.tempo
        total = estimate_measures(ctx.request, meter, tempo)
        total = max(16, (total // 4) * 4)
        bar = _bar_ql(meter)
        duration = total * bar * (60.0 / tempo)

        # ABA' 를 기본으로, 마디 수에 맞춰 섹션 길이를 나눈다.
        n_phrases = total // 4
        a_ph = max(2, n_phrases // 3)
        b_ph = max(1, n_phrases // 3)
        a2_ph = n_phrases - a_ph - b_ph

        treatments_a = ["statement", "sequence_up_2nd", "repeat", "fragment_head",
                        "rhythmic_variation", "sequence_down_3rd"]
        treatments_b = ["mode_change", "inversion", "texture_swap", "augmentation",
                        "fragment_tail", "octave_shift"]
        treatments_a2 = ["statement", "transpose_to_dominant", "diminution", "sequence_up_2nd",
                         "fragment_head", "repeat"]

        sections: list[SectionPlan] = []
        harmony_list = []
        m = 1

        def add_section(label: str, n_ph: int, treatments: list[str], texture_lh: str) -> None:
            nonlocal m
            start = m
            phrases: list[PhrasePlan] = []
            prog = PROGRESSIONS.get(label, PROGRESSIONS["A"])
            for i in range(n_ph):
                lo = m
                hi = m + 3
                dyn = ["mp", "mf", "f", "mf"][i % 4] if label != "B" else ["p", "mp", "mf", "mp"][i % 4]
                phrases.append(
                    PhrasePlan(
                        measures=[lo, hi],
                        motif_treatment=treatments[i % len(treatments)],  # type: ignore[arg-type]
                        texture_rh="8분음표 순차 선율, 프레이즈 끝 2박 길게",
                        texture_lh=texture_lh,
                        dynamic=dyn,  # type: ignore[arg-type]
                    )
                )
                for k in range(4):
                    harmony_list.append((m + k, prog[(i * 4 + k) % len(prog)]))
                m += 4
            sections.append(SectionPlan(label=label, measures=[start, m - 1], phrases=phrases))

        add_section("A", a_ph, treatments_a, "분산화음 반주(알베르티), 4분음표 단위")
        add_section("B", b_ph, treatments_b, "지속 화음 + 저음역 이동, 온음표 단위")
        add_section("A'", a2_ph, treatments_a2, "분산화음 반주, 마지막 4마디는 화음 두껍게")

        from app.schemas.music import HarmonyStep

        harmony = [HarmonyStep(measure=n, roman=r) for n, r in harmony_list if n <= total]
        # 마지막 두 마디는 확실한 종지로 덮어쓴다(§6.13 마무리 규칙).
        for h in harmony:
            if h.measure == total - 1:
                h.roman = "V7"
            elif h.measure == total:
                h.roman = "I"

        climax_measure = _climax_measure(total)

        showcase: list[Showcase] = []
        if ctx.student.strengths:
            lo = min(total - 3, climax_measure - 4) if climax_measure > 5 else 5
            showcase.append(
                Showcase(range=[max(1, lo), max(1, lo) + 3], strength_used=ctx.student.strengths[0])
            )

        dyn_curve = [
            DynamicPoint(measure=1, dyn="mp"),
            DynamicPoint(measure=5, dyn="mf"),
            DynamicPoint(measure=max(6, sections[1].measures[0]), dyn="p"),
            DynamicPoint(measure=climax_measure, dyn="f"),
            DynamicPoint(measure=total - 3, dyn="mf"),
        ]
        # 같은 마디에 두 번 표기하지 않는다.
        deduped: dict[int, DynamicPoint] = {}
        for d in sorted(dyn_curve, key=lambda x: x.measure):
            if d.measure <= total:
                deduped.setdefault(d.measure, d)
        dyn_curve = list(deduped.values())

        return CompositionPlan(
            title_candidates=["작은 행진", "봄날의 문답", "노래하는 손"],
            key=key,
            meter=meter,
            tempo=tempo,
            total_measures=total,
            duration_est=round(duration, 1),
            form=sections,
            harmony=harmony,
            climax=Climax(measure=climax_measure, how="최고음역 + f + 왼손 텍스처 두껍게"),
            showcase_measures=showcase,
            contrast_section={"label": "B", "how": "나란한조 + 레가토 칸타빌레 + 왼손 지속화음"},
            modulations=[],
            ending=Ending(type="완전종지 + 마무리 화음", measures=[total - 3, total]),
            dynamics_curve=dyn_curve,
            pedal_plan="A 섹션은 마디마다, B 섹션은 2마디 단위로 밟는다",
            difficulty_target=ctx.request.target_difficulty,
        )

    # ── Stage 3 ──────────────────────────────────────────────────────────
    def realize_phrase(self, ctx: ComposerContext, req: PhraseRequest) -> PhraseRealization:
        plan, motif = req.plan, req.motif
        key, meter = plan.key, plan.meter
        bar = _bar_ql(meter)
        lo, hi = req.measure_range
        harmony = dict(req.harmony_for_range())
        phrase = req.phrase

        level = TextureLevel(ctx.hard.target_difficulty, plan.tempo)
        head_ivs = motif.head_intervals() or [2, 2, -1]
        head_rhythm = motif.head_rhythm() or [1.0, 1.0, 1.0, 1.0]
        ivs, rhythm = self._apply_treatment(phrase.motif_treatment, head_ivs, head_rhythm)

        # 직전 마디 마지막 음에서 이어받는다.
        start = self._continue_from(req.previous_measures, motif, ctx)

        measures: list[Measure] = []
        cur = start
        prev_frame = self._frame_of(req.previous_measures)
        for offset, number in enumerate(range(lo, hi + 1)):
            roman = harmony.get(number, "I")
            durs = _fit_rhythm(list(rhythm), bar)
            # 마지막 마디는 호흡을 위해 그대로 두고, 나머지를 난이도만큼 세분화한다.
            if number != hi:
                durs = level.shape_rhythm(durs, bar)
            is_last = number == hi

            events: list[ScoreEvent] = []
            for j, d in enumerate(durs):
                if j > 0 or offset > 0:
                    step = ivs[(j + offset) % len(ivs)]
                    cur = cur + step
                cur = theory.nearest_scale_tone(cur, key)
                # 강박(첫 음)은 코드톤으로 — 화성이 들리게 한다.
                if j == 0:
                    cur = theory.nearest_chord_tone(cur, roman, key)
                cur = self._keep_in_range(cur, ctx)
                if level.leap_every and j and j % level.leap_every == 0:
                    # 옥타브 자리바꿈 — 손이 실제로 크게 움직인다.
                    leaped = cur + (12 if j % (level.leap_every * 2) else -12)
                    cur = self._keep_in_range(leaped, ctx)
                strong = (j % level.chord_every == 0) if level.chord_every else (j == 0)
                pitches = self._rh_pitches(cur, roman, key, level, ctx, strong=strong)
                events.append(
                    ScoreEvent(
                        dur=d,
                        pitches=pitches,
                        artic="staccato" if phrase.motif_treatment == "diminution" and j % 2 == 0 else "none",
                        slur="start" if j == 0 else ("stop" if j == len(durs) - 1 else None),
                    )
                )
            if is_last:
                # 프레이즈 호흡: 마지막 마디를 긴 음 하나로 정리한다(검증기 소프트 규칙).
                last = theory.nearest_chord_tone(cur, roman, key)
                last = self._keep_in_range(last, ctx)
                events = [ScoreEvent(dur=bar, pitches=[theory.spell(last, key)], slur="stop")]
                cur = last

            rh_min = min(
                (pitch_to_midi(p) for e in events for p in e.pitches),
                default=cur,
            )
            # 검증기와 같은 기준: 이 마디 오른손 '첫 음' 의 최고음
            first_rh = next((e for e in events if e.pitches), None)
            rh_first_top = (
                max(pitch_to_midi(p) for p in first_rh.pitches) if first_rh else cur
            )
            lh = self._realize_lh(
                roman, key, bar, phrase.texture_lh, ctx, rh_min, level, prev_frame, rh_first_top
            )
            made = Measure(
                number=number,
                rh=[Voice(events=events)],
                lh=[Voice(events=lh)],
                dynamics=phrase.dynamic if offset == 0 else None,
                pedal=True,
            )
            measures.append(made)
            prev_frame = self._first_note_frame(made) or prev_frame
        return PhraseRealization(measures=measures)

    def _rh_pitches(
        self, top: int, roman: str, key: str, level: TextureLevel,
        ctx: ComposerContext, *, strong: bool,
    ) -> list[str]:
        """난이도가 높으면 강박에 3도·6도를 겹쳐 오른손을 두껍게 한다."""
        if level.rh_voices <= 1 or not strong:
            return [theory.spell(top, key)]
        tones = theory.chord_pitch_classes(roman, key)
        picked = [top]
        # 3도·6도 겹침을 먼저 찾고, 없으면 스케일음으로 채운다 — 두께가 난이도를 만든다.
        for interval in (3, 4, 8, 9, 7, 5, 12):
            if len(picked) >= level.rh_voices:
                break
            cand = top - interval
            if cand < max(48, ctx.hard.lowest_midi):
                continue
            if top - cand > ctx.hard.max_span_semitones:
                continue
            if cand % 12 in tones:
                picked.append(cand)
        for interval in (3, 4, 5, 7):
            if len(picked) >= level.rh_voices:
                break
            cand = theory.nearest_scale_tone(top - interval, key)
            if cand >= max(48, ctx.hard.lowest_midi) and top - cand <= ctx.hard.max_span_semitones:
                picked.append(cand)
        return [theory.spell(p, key) for p in sorted(set(picked))]

    def _apply_treatment(
        self, treatment: str, ivs: list[int], rhythm: list[float]
    ) -> tuple[list[int], list[float]]:
        """motif_treatment 를 음정열·리듬에 실제로 적용한다."""
        if treatment == "inversion":
            return [-i for i in ivs], rhythm
        if treatment == "retrograde":
            return ivs[::-1], rhythm[::-1]
        if treatment == "augmentation":
            return ivs, [d * 2 for d in rhythm]
        if treatment == "diminution":
            return ivs, [max(0.25, d / 2) for d in rhythm]
        if treatment == "sequence_up_2nd":
            return [ivs[0] + 2, *ivs[1:]], rhythm
        if treatment == "sequence_down_3rd":
            return [ivs[0] - 3, *ivs[1:]], rhythm
        if treatment == "fragment_head":
            n = max(2, len(ivs) // 2)
            return ivs[:n], rhythm[:n] or rhythm
        if treatment == "fragment_tail":
            n = max(2, len(ivs) // 2)
            return ivs[-n:], rhythm[-n:] or rhythm
        if treatment == "transpose_to_dominant":
            return [ivs[0] + 7, *ivs[1:]], rhythm
        if treatment == "octave_shift":
            return [ivs[0] + 12, *ivs[1:]], rhythm
        if treatment == "rhythmic_variation":
            return ivs, [*rhythm[1:], rhythm[0]]
        if treatment == "mode_change":
            return [i - 1 if i > 0 else i for i in ivs], rhythm
        return ivs, rhythm

    def _continue_from(
        self, previous: list[Measure], motif: MotifCandidate, ctx: ComposerContext
    ) -> int:
        for m in sorted(previous, key=lambda x: -x.number):
            for v in reversed(m.rh):
                for e in reversed(v.events):
                    if e.pitches:
                        return self._keep_in_range(pitch_to_midi(e.pitches[-1]), ctx)
        for m in motif.measures:
            for v in m.rh:
                for e in v.events:
                    if e.pitches:
                        return self._keep_in_range(pitch_to_midi(e.pitches[0]), ctx)
        return 72

    @staticmethod
    def _first_note_frame(m: Measure) -> tuple[int, int] | None:
        """한 마디의 골격 = (왼손 첫 음의 최저음, 오른손 첫 음의 최고음).

        검증기(§7.6 `_check_parallels`)가 보는 것과 **정확히 같은 두 음**이다.
        생성기가 다른 음으로 병행을 피하면 경고는 그대로 남는다.
        """
        tops = [max(pitch_to_midi(p) for p in e.pitches)
                for v in m.rh for e in v.events if e.pitches]
        bots = [min(pitch_to_midi(p) for p in e.pitches)
                for v in m.lh for e in v.events if e.pitches]
        if tops and bots:
            return (bots[0], tops[0])
        return None

    @classmethod
    def _frame_of(cls, measures: list[Measure]) -> tuple[int, int] | None:
        for m in sorted(measures, key=lambda x: -x.number):
            frame = cls._first_note_frame(m)
            if frame is not None:
                return frame
        return None

    @staticmethod
    def _is_parallel(prev: tuple[int, int] | None, bass: int, top: int) -> bool:
        """직전 골격에서 이 골격으로 갈 때 병행 5도·8도가 생기는가.

        검증기(§7.6 소프트 규칙)와 같은 판정을 쓴다 — 생성기가 검증기와 다른 기준으로
        피하면 경고는 그대로 남는다.
        """
        if prev is None:
            return False
        p_bass, p_top = prev
        if p_top == top or p_bass == bass:
            return False
        if (top - p_top) * (bass - p_bass) <= 0:      # 반진행·사진행은 병행이 아니다
            return False
        return (p_top - p_bass) % 12 == (top - bass) % 12 and (top - bass) % 12 in (0, 7)

    def _choose_bass(
        self, roman: str, key: str, ctx: ComposerContext, rh_lowest: int,
        prev_frame: tuple[int, int] | None, rh_top: int,
    ) -> int:
        """병행 5·8도를 만들지 않는 베이스를 고른다.

        화음 구성음(근음·3음·5음)을 옥타브별로 훑어 첫 번째로 병행이 나지 않는 것을 쓴다.
        전부 병행이면 근음을 쓴다 — 화성을 깨느니 경고 하나를 남기는 편이 낫다.
        """
        tones = theory.chord_pitch_classes(roman, key)
        candidates: list[int] = []
        for pc in tones:                       # 근음 우선, 그다음 3음·5음(자리바꿈)
            for octave_base in (36, 48, 24):
                n = octave_base + ((pc - octave_base) % 12)
                while n >= min(rh_lowest, rh_top) - 2:
                    n -= 12
                if n >= ctx.hard.lowest_midi:
                    candidates.append(n)
        ordered = list(dict.fromkeys(candidates))
        for cand in ordered:
            if not self._is_parallel(prev_frame, cand, rh_top):
                return cand
        return ordered[0] if ordered else max(ctx.hard.lowest_midi, 36)

    def _keep_in_range(self, midi: int, ctx: ComposerContext) -> int:
        lo = max(ctx.hard.lowest_midi, 60)      # 오른손은 중앙 도 위에서
        hi = min(ctx.hard.highest_midi, 96)
        while midi > hi:
            midi -= 12
        while midi < lo:
            midi += 12
        return midi

    @staticmethod
    def _clamp_lh(midis: list[int], ctx: ComposerContext, rh_lowest: int) -> list[int]:
        """왼손 음을 학생 음역 안에 가둔다.

        자리바꿈을 고르다 보면 저음이 학생 음역 아래로 새기 쉽다. 음역 이탈은 하드 규칙이라
        (§7.6) 프레이즈가 통째로 폐기되므로, 만들어낸 직후 여기서 반드시 걸러야 한다.
        """
        out: list[int] = []
        ceiling = max(ctx.hard.lowest_midi, rh_lowest - 1)
        for m in midis:
            n = m
            while n < ctx.hard.lowest_midi:
                n += 12
            while n > ceiling and n - 12 >= ctx.hard.lowest_midi:
                n -= 12
            out.append(max(ctx.hard.lowest_midi, min(n, ceiling)))
        return out

    def _fit_below(self, midis: list[int], rh_lowest: int, ctx: ComposerContext) -> list[int]:
        """왼손 음들을 통째로 옥타브 내려 오른손 최저음 아래에 둔다(손 교차 금지)."""
        if not midis:
            return midis
        shift = 0
        while (
            max(m + shift for m in midis) >= rh_lowest
            and min(m + shift for m in midis) - 12 >= ctx.hard.lowest_midi
        ):
            shift -= 12
        out = [m + shift for m in midis]
        # 그래도 걸리면 개별 음을 내린다.
        return [m if m < rh_lowest else max(ctx.hard.lowest_midi, m - 12) for m in out]

    def _realize_lh(
        self, roman: str, key: str, bar: float, texture: str, ctx: ComposerContext,
        rh_lowest: int, level: TextureLevel | None = None,
        prev_frame: tuple[int, int] | None = None, rh_top: int | None = None,
    ) -> list[ScoreEvent]:
        """왼손. 오른손 최저음 아래로 유지해 손 교차를 만들지 않고, 병행 5·8도를 피한다."""
        level = level or TextureLevel(4.0)
        if rh_top is not None:
            root = self._choose_bass(roman, key, ctx, rh_lowest, prev_frame, rh_top)
        else:
            tones = theory.chord_pitch_classes(roman, key)
            root = 48 + ((tones[0] - 48) % 12)
            while root >= min(rh_lowest - 4, 60):
                root -= 12
            while root < ctx.hard.lowest_midi:
                root += 12
        span = ctx.hard.max_span_semitones

        def names(midis: list[int]) -> list[str]:
            clamped = self._clamp_lh(midis, ctx, rh_lowest)
            return [theory.spell(p, key) for p in dict.fromkeys(sorted(clamped))]

        if "지속" in texture or "온음표" in texture:
            notes = self._clamp_lh(self._fit_below([root, root + 7], rh_lowest, ctx), ctx, rh_lowest)
            if len(notes) > 1 and notes[1] - notes[0] > span:
                notes = notes[:1]
            return [ScoreEvent(dur=bar, pitches=names(notes))]

        if "두껍" in texture:
            triad = self._clamp_lh(
                self._fit_below(theory.triad_above(root, roman, key), rh_lowest, ctx),
                ctx, rh_lowest,
            )
            triad = [p for p in triad if p - min(triad) <= span] or [min(triad)]
            half = bar / 2
            chord = names(triad)
            return [ScoreEvent(dur=half, pitches=chord), ScoreEvent(dur=half, pitches=chord)]

        triad = self._clamp_lh(
            self._fit_below(theory.triad_above(root, roman, key), rh_lowest, ctx), ctx, rh_lowest
        )
        step = bar / 4

        if level.lh_style == "sustain":
            return [ScoreEvent(dur=bar, pitches=names([triad[0]]))]

        if level.lh_style == "leaping":
            # 저음 근음 ↔ 위쪽 화음 — 손 이동 거리를 키운다(난이도 특징 lh_texture).
            low = max(ctx.hard.lowest_midi, triad[0] - 12)
            seq = [low, triad[2], triad[1], triad[2]]
        elif level.lh_style == "wide":
            low = max(ctx.hard.lowest_midi, triad[0] - 12)
            high = min(rh_lowest - 1, triad[0] + 7)
            seq = [low, high, triad[1], high]
        else:
            # 기본: 알베르티 저음 (근음-5도-3도-5도)
            seq = [triad[0], triad[2], triad[1], triad[2]]

        seq = self._clamp_lh(seq, ctx, rh_lowest)
        # 병행을 피하려고 고른 베이스가 반드시 첫 음이어야 판정이 맞는다.
        if seq:
            seq[0] = self._clamp_lh([root], ctx, rh_lowest)[0]
        return [ScoreEvent(dur=step, pitches=[theory.spell(p, key)]) for p in seq]

    # ── Stage 5 ──────────────────────────────────────────────────────────
    def critique(
        self,
        ctx: ComposerContext,  # noqa: ARG002 - ComposerEngine Protocol 시그니처를 지킨다
        measures: list[Measure],  # noqa: ARG002
        plan: CompositionPlan,
        motif: MotifCandidate,  # noqa: ARG002
        musicality: dict,
        warnings: list[str] | None = None,
    ) -> CriticReport:
        """규칙 지표를 루브릭 점수로 옮긴다. 실제 비평가(Claude)의 대역."""
        met = musicality.get("metrics", {})

        def val(key: str) -> float:
            return float(met.get(key, {}).get("value", 0.0))

        scores = {
            "motif_development": round(2.0 + 8.0 * val("motif_consistency"), 2),
            "form_clarity": round(3.0 + 7.0 * val("texture_contrast"), 2),
            "harmony": round(2.0 + 8.0 * val("harmonic_consistency"), 2),
            "voice_leading": round(4.0 + 6.0 * val("playability"), 2),
            "phrasing": round(2.0 + 8.0 * val("phrase_balance"), 2),
            "climax_ending": round(3.0 + 7.0 * val("melodic_contour"), 2),
            "student_fit": round(3.0 + 7.0 * val("playability"), 2),
            "competition_effect": round(3.0 + 7.0 * val("dynamic_curve"), 2),
            "notation": 7.5,
            "originality": round(4.0 + 6.0 * val("repetition_balance"), 2),
        }
        scores = {k: max(0.0, min(10.0, v)) for k, v in scores.items()}

        requests: list[RevisionRequest] = []
        total = plan.total_measures
        for key, m in met.items():
            if m.get("met", True):
                continue
            rng, issue, how = self._revision_for(key, plan, total)
            requests.append(RevisionRequest(measures=rng, issue=issue, instruction=how))

        # 검증기의 소프트 경고도 수정 지시로 옮긴다. 경고를 비평가가 보지 않으면
        # 병행 5·8도 같은 흠은 영원히 남는다.
        for w in self._warning_revisions(warnings or [], total):
            requests.append(w)

        # 성부 진행 점수는 병행 경고 수에 따라 깎는다 — 지표만으로는 안 보인다.
        parallel_count = sum(1 for w in (warnings or []) if "parallels" in w)
        if parallel_count:
            scores["voice_leading"] = max(
                0.0, scores["voice_leading"] - min(4.0, parallel_count * 0.6)
            )

        return CriticReport(
            scores=RubricScores(**scores),
            strengths=["모티브의 윤곽이 분명하다", "프레이즈 길이가 고르다"],
            revision_requests=requests[:5],
            overall_comment="규칙 기반 대역 비평 — 실제 심사 판단은 COMPOSER_MODEL 비평가가 한다.",
        )

    @staticmethod
    def _warning_revisions(warnings: list[str], total: int) -> list[RevisionRequest]:
        """검증기 경고 문자열에서 마디 번호를 뽑아 구체적 수정 지시로 만든다."""
        import re

        by_rule: dict[str, list[int]] = {}
        for w in warnings:
            rule_match = re.match(r"\[(\w+)\]", w)
            if not rule_match:
                continue
            rule = rule_match.group(1)
            nums = [int(n) for n in re.findall(r"(\d+)마디", w)]
            by_rule.setdefault(rule, []).extend(n for n in nums if 1 <= n <= total)

        table = {
            "parallels": (
                "병행 5·8도가 남아 있다",
                "해당 마디의 왼손 최저음과 오른손 최고음이 같은 방향으로 5도·8도를 이루지 않게 "
                "왼손 화음의 자리바꿈을 바꾸거나 반진행으로 처리한다",
            ),
            "first_eight": (
                "첫 8마디에 다이내믹 대비가 없다",
                "1~8마디 안에서 최소 한 번 다이내믹을 바꾸어 심사위원의 첫인상을 만든다",
            ),
            "cadence": (
                "마무리가 약하다",
                "마지막 마디의 오른손을 2박 이상 긴 음으로 정리하고 왼손에 으뜸화음을 채운다",
            ),
            "climax_position": (
                "클라이맥스 위치가 권장 대역 밖이다",
                "클라이맥스 마디에 곡 전체의 최고음과 가장 두꺼운 텍스처가 오도록 조정한다",
            ),
        }

        out: list[RevisionRequest] = []
        for rule, (issue, how) in table.items():
            nums = sorted(set(by_rule.get(rule, [])))
            if not nums:
                continue
            lo, hi = nums[0], min(total, max(nums))
            detail = f" (해당 마디 {nums[:8]})" if len(nums) > 1 else ""
            out.append(
                RevisionRequest(measures=[lo, max(lo, hi)], issue=issue + detail, instruction=how)
            )
        return out

    def _revision_for(
        self, key: str, plan: CompositionPlan, total: int
    ) -> tuple[list[int], str, str]:
        phrases = plan.phrases()
        mid = phrases[len(phrases) // 2].measures if phrases else [1, min(4, total)]
        table = {
            "motif_consistency": (
                mid, "모티브의 흔적이 사라진 프레이즈가 있다",
                "이 구간 오른손을 잠긴 모티브의 동형진행 또는 전위로 다시 쓴다",
            ),
            "phrase_balance": (
                mid, "프레이즈 끝에 숨 쉴 자리가 없다",
                "각 프레이즈 마지막 마디 오른손을 2박 이상 긴 음 또는 쉼표로 정리한다",
            ),
            "harmonic_consistency": (
                mid, "실제 음표가 Plan 화성에서 벗어난다",
                "각 마디 첫 음을 해당 로마숫자의 코드톤으로 바꾼다",
            ),
            "texture_contrast": (
                list(plan.form[1].measures) if len(plan.form) > 1 else mid,
                "섹션이 바뀌어도 왼손 텍스처가 그대로다",
                "B 섹션 왼손을 지속화음 또는 저음역 이동으로 바꾸고 음역을 한 옥타브 내린다",
            ),
            "dynamic_curve": (
                [1, min(8, total)], "다이내믹 표기가 Plan 곡선을 따르지 않는다",
                "Plan 의 dynamics_curve 지점마다 해당 다이내믹을 표기한다",
            ),
            "melodic_contour": (
                [max(1, plan.climax.measure - 2), min(total, plan.climax.measure + 2)],
                "최고음이 클라이맥스와 어긋난다",
                "클라이맥스 마디에 곡 전체의 최고음이 오도록 앞 구간의 음역을 낮춘다",
            ),
            "repetition_balance": (
                mid, "정확 반복 비율이 권장 대역을 벗어난다",
                "반복이 많으면 한 프레이즈를 리듬 변형으로, 적으면 A 섹션 첫 프레이즈를 한 번 재현한다",
            ),
            "playability": (
                mid, "손 이동·스팬이 학생 한계를 넘는다",
                "도약을 순차로 메우고 동시 타건 폭을 학생 스팬 이하로 줄인다",
            ),
        }
        rng, issue, how = table.get(key, (mid, f"{key} 지표 미달", "해당 구간을 다시 쓴다"))
        rng = [max(1, min(total, rng[0])), max(1, min(total, rng[1]))]
        if rng[1] < rng[0]:
            rng = [rng[0], rng[0]]
        return rng, issue, how
