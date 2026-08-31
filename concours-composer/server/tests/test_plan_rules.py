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
