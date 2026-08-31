"""§7.6 검증기.

하드 규칙 하나라도 깨지면 저장 불가(CLAUDE.md 절대 규칙 2).
소프트 규칙은 경고만 남기고 통과시킨다 — 원장이 판단할 몫이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from music21 import meter as m21meter

from app.analysis.pitch import pitch_to_midi
from app.schemas.music import CompositionPlan, Measure
from app.schemas.student import CompetitionProfile, Student

Severity = Literal["hard", "soft"]


@dataclass
class Issue:
    rule: str
    severity: Severity
    message: str
    measures: list[int] = field(default_factory=list)


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def hard_failures(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "hard"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "soft"]

    @property
    def passed(self) -> bool:
        """하드 규칙을 전부 통과했는가. 저장 가능 여부와 같다."""
        return not self.hard_failures

    def add(self, rule: str, severity: Severity, message: str, measures: list[int] | None = None) -> None:
        self.issues.append(Issue(rule, severity, message, measures or []))

    def summary(self) -> str:
        if self.passed:
            return f"통과 (경고 {len(self.warnings)}건)"
        return f"실패 {len(self.hard_failures)}건 · 경고 {len(self.warnings)}건"


# ── 개별 규칙 ────────────────────────────────────────────────────────────────


def _check_measure_lengths(measures: list[Measure], meter: str, r: ValidationReport) -> None:
    bar_ql = m21meter.TimeSignature(meter).barDuration.quarterLength
    for m in measures:
        for hand, voices in (("오른손", m.rh), ("왼손", m.lh)):
            for v in voices:
                total = round(v.total_dur, 6)
                if voices and abs(total - float(bar_ql)) > 1e-6:
                    r.add(
                        "measure_length", "hard",
                        f"{m.number}마디 {hand} 성부{v.voice} 길이 합계 {total} ≠ 박자표 {meter} ({bar_ql})",
                        [m.number],
                    )


# MusicXML 로 적을 수 있는 음길이(4분음표=1.0). 셋잇단은 tuplet 표기가 필요하므로
# 규칙 기반 생성에서는 만들지 않는다 — LLM 이 만들면 여기서 걸린다.
# 2배수·붙점·겹붙점. 셋잇단은 tuplet 표기가 필요하므로 규칙 기반 생성에서는 만들지 않는다.
NOTATABLE_QL = frozenset(
    {0.125, 0.1875, 0.25, 0.375, 0.4375, 0.5, 0.75, 0.875, 1.0, 1.5, 1.75, 2.0, 3.0, 3.5, 4.0, 6.0, 7.0, 8.0}
)


def _check_notatable_durations(measures: list[Measure], r: ValidationReport) -> None:
    """기보할 수 없는 길이는 MusicXML 내보내기에서 터진다 — 저장 전에 잡는다."""
    for m in measures:
        for hand, voices in (("오른손", m.rh), ("왼손", m.lh)):
            for v in voices:
                for e in v.events:
                    if round(e.dur, 6) not in NOTATABLE_QL:
                        r.add(
                            "notatable_duration", "hard",
                            f"{m.number}마디 {hand} 음길이 {e.dur} 는 기보할 수 없다 "
                            f"(허용: {sorted(NOTATABLE_QL)})",
                            [m.number],
                        )


def _check_range_and_span(measures: list[Measure], student: Student, r: ValidationReport) -> None:
    max_semi = student.hand_span.max_semitones
    for m in measures:
        for hand, voices in (("오른손", m.rh), ("왼손", m.lh)):
            for v in voices:
                for ev in v.events:
                    if not ev.pitches:
                        continue
                    midis = sorted(pitch_to_midi(p) for p in ev.pitches)
                    lo, hi = midis[0], midis[-1]
                    if lo < student.lowest_midi or hi > student.highest_midi:
                        r.add(
                            "range", "hard",
                            f"{m.number}마디 {hand} 음역 이탈 ({lo}~{hi}, 허용 "
                            f"{student.lowest_midi}~{student.highest_midi})",
                            [m.number],
                        )
                    if hi - lo > max_semi:
                        r.add(
                            "hand_span", "hard",
                            f"{m.number}마디 {hand} 동시 타건 폭 {hi - lo}반음 > 학생 스팬 "
                            f"{student.hand_span.max_interval}도({max_semi}반음)",
                            [m.number],
                        )


def _check_hand_crossing(measures: list[Measure], r: ValidationReport) -> None:
    """왼손이 오른손보다 높이 올라가는 교차는 초·중급 학생에게 사고가 잦다."""
    for m in measures:
        rh = [pitch_to_midi(p) for v in m.rh for e in v.events for p in e.pitches]
        lh = [pitch_to_midi(p) for v in m.lh for e in v.events for p in e.pitches]
        if rh and lh and max(lh) > min(rh):
            r.add(
                "hand_crossing", "hard",
                f"{m.number}마디 손 교차: 왼손 최고음({max(lh)}) > 오른손 최저음({min(rh)})",
                [m.number],
            )


def _check_repeat_limit(measures: list[Measure], r: ValidationReport) -> None:
    """같은 마디가 4회 연속이면 '이상한 곡' 신호(§7.9)."""
    def sig(m: Measure) -> str:
        return "|".join(
            f"{v.voice}:" + ",".join(f"{e.dur}:{'.'.join(e.pitches)}" for e in v.events)
            for v in (*m.rh, *m.lh)
        )

    run = 1
    for prev, cur in zip(measures, measures[1:], strict=False):
        run = run + 1 if sig(prev) == sig(cur) else 1
        if run >= 4:
            r.add("repeat_limit", "hard", f"{cur.number}마디까지 동일 마디 4회 연속", [cur.number])
            run = 1


def _check_duration(measures: list[Measure], tempo: int, meter: str,
                    competition: CompetitionProfile | None, r: ValidationReport) -> float:
    bar_ql = float(m21meter.TimeSignature(meter).barDuration.quarterLength)
    seconds = len(measures) * bar_ql * (60.0 / tempo)
    if competition and competition.time_limit_sec:
        limit = competition.time_limit_sec * 0.95
        if seconds > limit:
            r.add(
                "time_limit", "hard",
                f"예상 연주시간 {seconds:.0f}초 > 제한 {competition.time_limit_sec}초의 95% ({limit:.0f}초)",
            )
    return seconds


def _check_cadence(measures: list[Measure], r: ValidationReport) -> None:
    """마지막 마디가 긴 음/화음으로 끝나는가 — 종지의 확신."""
    if not measures:
        return
    last = max(measures, key=lambda m: m.number)
    tail = [e for v in last.rh for e in v.events if e.pitches]
    if not tail:
        r.add("cadence", "hard", f"마지막 {last.number}마디 오른손에 실음이 없다", [last.number])
        return
    if tail[-1].dur < 1.0:
        r.add(
            "cadence", "soft",
            f"마지막 {last.number}마디가 짧은 음({tail[-1].dur})으로 끝난다 — 마무리의 확신이 약하다",
            [last.number],
        )
    if not [e for v in last.lh for e in v.events if e.pitches]:
        r.add("cadence", "soft", f"마지막 {last.number}마디 왼손이 비었다", [last.number])


def _check_accidental_ratio(
    measures: list[Measure], max_ratio: float, key_sig: str, r: ValidationReport
) -> None:
    """조표 밖의 음만 임시표로 센다 — 샤프 조의 곡이 통째로 걸리지 않게."""
    from app.analysis.theory import count_accidentals

    total = 0
    acc = 0
    for m in measures:
        pitches = m.all_pitches()
        total += len(pitches)
        acc += count_accidentals(pitches, key_sig)
    if total and acc / total > max_ratio:
        r.add(
            "accidental_ratio", "hard",
            f"조표 밖 임시표 비율 {acc / total:.0%} > 상한 {max_ratio:.0%} — 학생 독보 수준을 넘는다",
        )


def _check_competition_rules(measures: list[Measure], competition: CompetitionProfile | None,
                             r: ValidationReport) -> None:
    if competition is None:
        return
    if not competition.original_allowed:
        r.add("competition_original", "hard",
              f"'{competition.name}' 은(는) 창작곡을 허용하지 않는다")
    if not competition.repeats_allowed:
        for m in measures:
            if m.text and "repeat" in m.text.lower():
                r.add("competition_repeat", "hard",
                      f"{m.number}마디 반복 지시 — 이 대회는 반복 연주를 허용하지 않는다", [m.number])


def _check_soft_first_eight(measures: list[Measure], r: ValidationReport) -> None:
    """§6.13 심사위원 첫인상 규칙 — 첫 8마디에 다이내믹 대비가 있는가."""
    head = [m for m in measures if m.number <= 8]
    dyns = {m.dynamics for m in head if m.dynamics}
    if head and len(dyns) < 2:
        r.add("first_eight", "soft",
              "첫 8마디에 다이내믹 대비가 없다 — 심사위원 첫인상이 밋밋해진다", [1, 8])


def _check_soft_climax(plan: CompositionPlan | None, total: int, r: ValidationReport) -> None:
    if plan is None or total == 0:
        return
    pos = plan.climax.measure / total
    if not 0.60 <= pos <= 0.80:
        r.add("climax_position", "soft",
              f"클라이맥스가 {pos:.0%} 지점 — 권장 60~80% 밖", [plan.climax.measure])


def _check_parallels(measures: list[Measure], r: ValidationReport) -> None:
    """병행 5도·8도(소프트). 오른손 최고음 · 왼손 최저음의 골격만 본다."""
    frame: list[tuple[int, int, int]] = []
    for m in measures:
        top = [max((pitch_to_midi(p) for p in e.pitches), default=None)
               for v in m.rh for e in v.events if e.pitches]
        bot = [min((pitch_to_midi(p) for p in e.pitches), default=None)
               for v in m.lh for e in v.events if e.pitches]
        if top and bot:
            frame.append((m.number, top[0], bot[0]))  # type: ignore[arg-type]
    for (m1, t1, b1), (m2, t2, b2) in zip(frame, frame[1:], strict=False):
        i1, i2 = (t1 - b1) % 12, (t2 - b2) % 12
        moved = (t1 != t2) and (b1 != b2)
        direction_same = (t2 - t1) * (b2 - b1) > 0
        if moved and direction_same and i1 == i2 and i1 in (0, 7):
            name = "8도" if i1 == 0 else "5도"
            r.add("parallels", "soft", f"{m1}→{m2}마디 병행 {name}", [m1, m2])


# ── 진입점 ───────────────────────────────────────────────────────────────────


def validate_score(
    measures: list[Measure],
    student: Student,
    *,
    meter: str = "4/4",
    tempo: int = 100,
    key_sig: str = "C",
    plan: CompositionPlan | None = None,
    competition: CompetitionProfile | None = None,
    target_difficulty: float | None = None,
    corpus_ngrams: set[tuple[int, ...]] | None = None,
    max_accidental_ratio: float = 0.25,
) -> ValidationReport:
    """§7.6 전체 검증. 저장 전에 반드시 통과해야 한다."""
    r = ValidationReport()
    if not measures:
        r.add("empty", "hard", "마디가 없다")
        return r

    measures = sorted(measures, key=lambda m: m.number)

    _check_measure_lengths(measures, meter, r)
    _check_notatable_durations(measures, r)
    _check_range_and_span(measures, student, r)
    _check_hand_crossing(measures, r)
    _check_repeat_limit(measures, r)
    _check_duration(measures, tempo, meter, competition, r)
    _check_cadence(measures, r)
    _check_accidental_ratio(measures, max_accidental_ratio, key_sig, r)
    _check_competition_rules(measures, competition, r)
    _check_soft_first_eight(measures, r)
    _check_soft_climax(plan, len(measures), r)
    _check_parallels(measures, r)

    if tempo > student.tempo_comfort_max_bpm:
        r.add("tempo", "hard",
              f"템포 {tempo}bpm > 학생 편안한 상한 {student.tempo_comfort_max_bpm}bpm")

    if target_difficulty is not None:
        from app.analysis.difficulty import difficulty_score

        got = difficulty_score(measures, meter=meter, tempo=tempo, key_sig=key_sig).score
        if abs(got - target_difficulty) > 1.0:
            r.add("difficulty", "hard",
                  f"난이도 {got:.1f} 이 목표 {target_difficulty:.1f} ±1.0 을 벗어난다")

    if corpus_ngrams:
        from app.analysis.ngram import find_plagiarism

        hits = find_plagiarism(measures, corpus_ngrams)
        for h in hits:
            r.add("plagiarism", "hard",
                  f"{h.start_measure}마디부터 코퍼스와 {h.length}마디 멜로디 일치", [h.start_measure])

    # music21 재파싱 — 조립 결과가 실제로 악보로 읽히는지(§7.6 마지막 항목)
    try:
        from music21 import converter

        from app.generation.assemble import AssembleOptions, measures_to_musicxml

        xml = measures_to_musicxml(
            measures, AssembleOptions(meter=meter, tempo=tempo, key_sig=key_sig)
        )
        converter.parse(xml, format="musicxml")
    except Exception as e:
        r.add("reparse", "hard", f"MusicXML 재파싱 실패: {e}")

    return r
