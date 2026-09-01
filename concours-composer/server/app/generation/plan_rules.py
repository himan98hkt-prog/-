"""Stage 2 규칙 검사 (§7.3).

Plan 이 틀리면 뒤 단계가 전부 틀린다. 원장에게 보여주기 전에 코드가 먼저 본다.
제한 시간 · 종지 · 대비 존재 · showcase 가 학생 강점과 일치 · 클라이맥스 위치 60~80%.
"""
from __future__ import annotations

from collections.abc import Sequence

from music21 import meter as m21meter

from app.generation.diversity import collisions, suggest
from app.schemas.music import MAX_PHRASE_MEASURES, MIN_PHRASE_MEASURES, CompositionPlan
from app.schemas.student import Student
from app.validate.validator import ValidationReport


def check_plan(
    plan: CompositionPlan,
    student: Student,
    *,
    time_limit_sec: int | None = None,
    previous_plans: Sequence[tuple[str, CompositionPlan]] = (),
) -> ValidationReport:
    r = ValidationReport()

    # 1. 마디 수와 프레이즈 구획이 맞물리는가
    covered: set[int] = set()
    for s in plan.form:
        lo, hi = s.measures
        if hi < lo:
            r.add("plan_section", "hard", f"섹션 {s.label} 마디 범위가 뒤집혔다: {s.measures}")
        for p in s.phrases:
            plo, phi = p.measures
            if plo < lo or phi > hi:
                r.add("plan_phrase", "hard",
                      f"섹션 {s.label}({lo}-{hi}) 밖의 프레이즈 {p.measures}", list(p.measures))
            length = phi - plo + 1
            if not MIN_PHRASE_MEASURES <= length <= MAX_PHRASE_MEASURES:
                r.add("plan_phrase", "hard",
                      f"프레이즈 {p.measures} 가 {length}마디 — "
                      f"{MIN_PHRASE_MEASURES}~{MAX_PHRASE_MEASURES}마디여야 한다"
                      "(한 호출로 곡을 통째로 만드는 것을 막는 규칙이다)",
                      list(p.measures))
            covered.update(range(plo, phi + 1))
    missing = set(range(1, plan.total_measures + 1)) - covered
    if missing:
        lo = min(missing)
        r.add("plan_coverage", "hard",
              f"프레이즈가 덮지 않는 마디 {len(missing)}개 (예: {sorted(missing)[:6]})", [lo])
    extra = covered - set(range(1, plan.total_measures + 1))
    if extra:
        r.add(
            "plan_coverage", "hard",
            f"total_measures({plan.total_measures}) 를 넘는 마디 {sorted(extra)[:6]}",
        )

    # 2. 제한 시간 (§7.6 과 같은 95% 기준)
    bar_ql = float(m21meter.TimeSignature(plan.meter).barDuration.quarterLength)
    seconds = plan.total_measures * bar_ql * (60.0 / plan.tempo)
    if time_limit_sec:
        limit = time_limit_sec * 0.95
        if seconds > limit:
            r.add("plan_time_limit", "hard",
                  f"설계 연주시간 {seconds:.0f}초 > 제한 {time_limit_sec}초의 95%({limit:.0f}초). "
                  f"마디 수를 {int(limit / (bar_ql * 60.0 / plan.tempo))} 이하로 줄여라")
        # 짧은 곡은 심사에서 손해다. 제한 시간의 절반도 안 쓰면 곡이 덜 자란 것이다.
        elif seconds < time_limit_sec * 0.55:
            want = int(time_limit_sec * 0.75 / (bar_ql * 60.0 / plan.tempo))
            r.add("plan_time_limit", "soft",
                  f"설계 연주시간 {seconds:.0f}초 — 제한 {time_limit_sec}초의 "
                  f"{seconds / time_limit_sec:.0%}밖에 쓰지 않는다. "
                  f"{want}마디 정도로 늘리면 제한의 75% 를 쓴다")

    # 3. 종지
    ehi = plan.ending.measures[1]
    if ehi != plan.total_measures:
        r.add("plan_ending", "hard",
              f"ending 이 마지막 마디({plan.total_measures})에서 끝나지 않는다: {plan.ending.measures}")
    if plan.harmony:
        last = max(plan.harmony, key=lambda h: h.measure)
        if last.measure == plan.total_measures and last.roman.strip().upper().startswith("V"):
            r.add("plan_ending", "hard", f"마지막 마디 화성이 {last.roman} — 딸림화음으로 끝난다")

    # 4. 대비 존재
    labels = [s.label for s in plan.form]
    if len(set(labels)) < 2:
        r.add("plan_contrast", "hard", f"섹션 라벨이 하나뿐이다({labels}) — 대비가 없다")
    if plan.contrast_section is None:
        r.add("plan_contrast", "soft", "contrast_section 이 비었다 — 어떻게 대비할지 적어라")

    # 5. 모티브 처리 기법이 세 번 연속 같으면 전개가 아니라 반복이다
    treatments = [p.motif_treatment for p in plan.phrases()]
    run = 1
    for a, b in zip(treatments, treatments[1:], strict=False):
        run = run + 1 if a == b else 1
        if run >= 3:
            r.add("plan_treatment", "hard", f"모티브 처리 '{a}' 가 3회 연속 — 전개가 없다")
            run = 1
    if len(set(treatments)) < max(2, len(treatments) // 3):
        r.add("plan_treatment", "soft",
              f"모티브 처리 종류가 {len(set(treatments))}개뿐 — 단조로워진다")

    # 6. 쇼케이스가 학생 강점과 일치하는가
    if student.strengths and not plan.showcase_measures:
        r.add("plan_showcase", "hard",
              f"학생 강점({', '.join(student.strengths)})을 드러낼 showcase_measures 가 없다")
    for sc in plan.showcase_measures:
        if not (1 <= sc.range[0] <= sc.range[1] <= plan.total_measures):
            r.add("plan_showcase", "hard", f"showcase 범위가 곡 밖이다: {sc.range}", list(sc.range))
        if student.strengths and sc.strength_used not in " ".join(student.strengths):
            r.add("plan_showcase", "soft",
                  f"showcase 의 '{sc.strength_used}' 가 학생 강점 목록에 없다")
    for w in student.weaknesses:
        for sc in plan.showcase_measures:
            if w and w in sc.strength_used:
                r.add("plan_showcase", "hard",
                      f"학생 약점 '{w}' 을 showcase 로 잡았다 — 노출을 피해야 한다", list(sc.range))

    # 6b. 프레이즈 길이에 변화가 있는가
    lengths = [p.measures[1] - p.measures[0] + 1 for p in plan.phrases()]
    if len(lengths) >= 3 and len(set(lengths)) == 1:
        r.add("plan_phrase_shape", "soft",
              f"프레이즈가 전부 {lengths[0]}마디다 — 분절(2마디)이나 확장(6마디)이 없으면 "
              "형식이 격자처럼 들린다")

    # 7. 클라이맥스 위치
    pos = plan.climax.measure / plan.total_measures
    if not 0.60 <= pos <= 0.80:
        r.add("plan_climax", "hard",
              f"클라이맥스가 {pos:.0%} 지점({plan.climax.measure}/{plan.total_measures}) — 60~80% 밖",
              [plan.climax.measure])

    # 8. 템포가 학생 한계를 넘지 않는가
    if plan.tempo > student.tempo_comfort_max_bpm:
        r.add("plan_tempo", "hard",
              f"Plan 템포 {plan.tempo} > 학생 상한 {student.tempo_comfort_max_bpm}")

    # 9. 첫 8마디 다이내믹 대비(소프트) — 심사위원 첫인상
    head = [d.dyn for d in plan.dynamics_curve if d.measure <= 8]
    if len(set(head)) < 2:
        r.add("plan_first_eight", "soft", "첫 8마디 다이내믹 곡선에 대비가 없다")

    # 10. 이미 만든 곡과 같은 틀인가 (§7.9 — 곡 하나만 보는 지표가 못 잡는 것)
    for c in collisions(plan, previous_plans):
        r.add(
            "plan_diversity", "hard",
            f"{c.other_id} 과(와) 형식이 {c.similarity:.0%} 같다 — 겹치는 축: "
            f"{', '.join(c.shared)}. {suggest(c.shared)}",
        )

    return r
