"""§7.3 Stage 2 Plan 규칙 검사."""
from __future__ import annotations

import pytest
from app.generation.plan_rules import check_plan


@pytest.fixture
def plan(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    p, _ = pipeline.plan(ctx, motif)
    return p


def test_generated_plan_passes_all_rules(plan, student, ctx):
    r = check_plan(plan, student, time_limit_sec=ctx.hard.time_limit_sec)
    assert r.passed, [i.message for i in r.hard_failures]


def test_climax_outside_60_to_80_percent_fails(plan, student):
    broken = plan.model_copy(update={"climax": plan.climax.model_copy(update={"measure": 2})})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_climax" for i in r.hard_failures)


def test_time_limit_violation_is_caught_at_plan_stage(plan, student):
    r = check_plan(plan, student, time_limit_sec=30)
    assert any(i.rule == "plan_time_limit" for i in r.hard_failures)


def test_ending_must_reach_the_last_measure(plan, student):
    broken = plan.model_copy(update={"ending": plan.ending.model_copy(update={"measures": [1, 4]})})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_ending" for i in r.hard_failures)


def test_dominant_chord_at_the_end_is_rejected(plan, student):
    harmony = [h.model_copy() for h in plan.harmony]
    harmony[-1].roman = "V7"
    broken = plan.model_copy(update={"harmony": harmony})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_ending" for i in r.hard_failures)


def test_three_identical_motif_treatments_in_a_row_fail(plan, student):
    form = [s.model_copy(deep=True) for s in plan.form]
    for p in form[0].phrases[:3]:
        p.motif_treatment = "statement"
    broken = plan.model_copy(update={"form": form})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_treatment" for i in r.hard_failures)


def test_showcase_on_a_student_weakness_is_rejected(plan, student):
    from app.schemas.music import Showcase

    broken = plan.model_copy(update={"showcase_measures": [Showcase(range=[5, 8], strength_used="옥타브")]})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_showcase" for i in r.hard_failures)


def test_missing_showcase_for_a_student_with_strengths_is_rejected(plan, student):
    broken = plan.model_copy(update={"showcase_measures": []})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_showcase" for i in r.hard_failures)


def test_phrases_must_cover_every_measure(plan, student):
    form = [s.model_copy(deep=True) for s in plan.form]
    form[-1].phrases = form[-1].phrases[:-1]
    broken = plan.model_copy(update={"form": form})
    r = check_plan(broken, student)
    assert any(i.rule in ("plan_coverage", "plan_section") for i in r.hard_failures)


def test_tempo_above_student_comfort_is_rejected(plan, student):
    broken = plan.model_copy(update={"tempo": student.tempo_comfort_max_bpm + 20})
    r = check_plan(broken, student)
    assert any(i.rule == "plan_tempo" for i in r.hard_failures)


# ── 프레이즈 길이 (4마디 고정 해제) ──────────────────────────────────────────


def test_phrase_lengths_vary_across_the_piece() -> None:
    """모든 프레이즈가 4마디인 설계는 더 이상 나오지 않는다."""
    from app.generation.engines.stub import _phrase_lengths, _section_lengths

    for total in (16, 20, 24, 32, 40, 48, 52, 64, 96):
        a, b, c = _section_lengths(total)
        assert a + b + c == total, total
        lens = (
            _phrase_lengths(a, "A") + _phrase_lengths(b, "B") + _phrase_lengths(c, "A'")
        )
        assert sum(lens) == total, (total, lens)
        assert all(2 <= x <= 8 for x in lens), (total, lens)
        if total >= 32:
            assert len(set(lens)) >= 2, (total, lens)


def test_plan_rule_flags_uniform_phrase_lengths(student) -> None:
    from app.generation.plan_rules import check_plan
    from app.schemas.music import (
        Climax,
        CompositionPlan,
        Ending,
        PhrasePlan,
        SectionPlan,
        Showcase,
    )

    phrases = [
        PhrasePlan(measures=[i * 4 + 1, i * 4 + 4], motif_treatment="statement",
                   texture_rh="x", texture_lh="y")
        for i in range(4)
    ]
    plan = CompositionPlan(
        key="C", meter="4/4", tempo=100, total_measures=16, duration_est=38.4,
        form=[
            SectionPlan(label="A", measures=[1, 8], phrases=phrases[:2]),
            SectionPlan(label="B", measures=[9, 16], phrases=phrases[2:]),
        ],
        climax=Climax(measure=11, how="f"),
        showcase_measures=[Showcase(range=[9, 12], strength_used=student.strengths[0])],
        ending=Ending(type="완전종지", measures=[13, 16]),
        difficulty_target=4,
    )
    rep = check_plan(plan, student)
    assert any(i.rule == "plan_phrase_shape" for i in rep.warnings), rep.issues


def test_plan_rule_rejects_oversized_phrase(student) -> None:
    """한 프레이즈가 8마디를 넘으면 하드 실패 — 절대 규칙 9 의 설계 단계 방어선."""
    from app.generation.plan_rules import check_plan
    from app.schemas.music import (
        Climax,
        CompositionPlan,
        Ending,
        PhrasePlan,
        SectionPlan,
        Showcase,
    )

    plan = CompositionPlan(
        key="C", meter="4/4", tempo=100, total_measures=16, duration_est=38.4,
        form=[
            SectionPlan(label="A", measures=[1, 12],
                        phrases=[PhrasePlan(measures=[1, 12], motif_treatment="statement",
                                            texture_rh="x", texture_lh="y")]),
            SectionPlan(label="B", measures=[13, 16],
                        phrases=[PhrasePlan(measures=[13, 16], motif_treatment="repeat",
                                            texture_rh="x", texture_lh="y")]),
        ],
        climax=Climax(measure=11, how="f"),
        showcase_measures=[Showcase(range=[9, 12], strength_used=student.strengths[0])],
        ending=Ending(type="완전종지", measures=[13, 16]),
        difficulty_target=4,
    )
    rep = check_plan(plan, student)
    assert any(i.rule == "plan_phrase" and "12마디" in i.message for i in rep.hard_failures), rep.issues


def test_plan_rule_flags_piece_that_wastes_the_time_limit(student) -> None:
    from app.generation.plan_rules import check_plan
    from app.schemas.music import (
        Climax,
        CompositionPlan,
        Ending,
        PhrasePlan,
        SectionPlan,
        Showcase,
    )

    plan = CompositionPlan(
        key="C", meter="4/4", tempo=100, total_measures=16, duration_est=38.4,
        form=[
            SectionPlan(label="A", measures=[1, 8],
                        phrases=[PhrasePlan(measures=[1, 4], motif_treatment="statement",
                                            texture_rh="x", texture_lh="y"),
                                 PhrasePlan(measures=[5, 8], motif_treatment="repeat",
                                            texture_rh="x", texture_lh="y")]),
            SectionPlan(label="B", measures=[9, 16],
                        phrases=[PhrasePlan(measures=[9, 12], motif_treatment="inversion",
                                            texture_rh="x", texture_lh="y"),
                                 PhrasePlan(measures=[13, 16], motif_treatment="statement",
                                            texture_rh="x", texture_lh="y")]),
        ],
        climax=Climax(measure=11, how="f"),
        showcase_measures=[Showcase(range=[9, 12], strength_used=student.strengths[0])],
        ending=Ending(type="완전종지", measures=[13, 16]),
        difficulty_target=4,
    )
    rep = check_plan(plan, student, time_limit_sec=150)
    assert any(
        i.rule == "plan_time_limit" and "밖에 쓰지 않는다" in i.message for i in rep.warnings
    ), rep.issues
