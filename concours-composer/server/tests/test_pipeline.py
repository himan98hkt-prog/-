"""§7.9 '이상한 곡' 방지 6원칙과 파이프라인 계약 — 절대 규칙 9·10 포함."""
from __future__ import annotations

import pytest
from app.generation.engines.base import PhraseRequest
from app.generation.pipeline import MAX_PHRASE_MEASURES, PhraseTooLongError, PlanRejected
from app.schemas.music import Measure, PhraseRealization, ScoreEvent, Voice

# ── 원칙 1·2: 모티브를 먼저 잠그고 프레이즈 단위로만 생성 ──────────────────


def test_motifs_are_validated_against_student_constraints(pipeline, ctx):
    motifs = pipeline.motifs(ctx, 4)
    assert motifs, "모든 후보가 탈락하면 원장에게 보여줄 것이 없다"
    for m in motifs:
        for measure in m.measures:
            for v in (*measure.rh, *measure.lh):
                for e in v.events:
                    if len(e.pitches) > 1:
                        from app.analysis.pitch import pitch_to_midi

                        midis = [pitch_to_midi(p) for p in e.pitches]
                        assert max(midis) - min(midis) <= ctx.hard.max_span_semitones


def test_selecting_a_motif_locks_it(pipeline, ctx):
    motif = pipeline.motifs(ctx, 3)[0]
    plan, _ = pipeline.plan(ctx, motif)
    # Plan 은 잠긴 모티브의 조성·박자·템포를 그대로 물려받는다.
    assert plan.key == motif.key
    assert plan.meter == motif.meter
    assert plan.tempo == motif.tempo


def test_phrase_units_never_exceed_the_limit(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)
    for p in plan.phrases():
        assert p.measures[1] - p.measures[0] + 1 <= MAX_PHRASE_MEASURES


def test_engine_returning_whole_piece_at_once_is_rejected(pipeline, ctx, engine):
    """절대 규칙 9 — 32마디를 한 호출로 만드는 엔진은 거부된다."""
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)

    class GreedyEngine:
        name = "greedy"

        def motifs(self, *a, **k):
            return []

        def plan(self, *a, **k):
            return plan

        def realize_phrase(self, ctx_, req: PhraseRequest) -> PhraseRealization:
            return PhraseRealization(
                measures=[
                    Measure(number=n, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])])
                    for n in range(1, plan.total_measures + 1)
                ]
            )

        def critique(self, *a, **k):
            raise AssertionError("여기까지 오면 안 된다")

    from app.generation.pipeline import CompositionPipeline

    greedy = CompositionPipeline(GreedyEngine(), progress=lambda *_: None)
    with pytest.raises(PhraseTooLongError):
        greedy.realize(ctx, plan, motif)


# ── 원칙 3: 작곡가와 비평가는 별도 호출 ──────────────────────────────────


def test_critic_is_a_separate_call_from_realize(pipeline, ctx, monkeypatch):
    calls: list[str] = []
    orig_realize = pipeline.engine.realize_phrase
    orig_critique = pipeline.engine.critique

    def spy_realize(*a, **k):
        calls.append("realize")
        return orig_realize(*a, **k)

    def spy_critique(*a, **k):
        calls.append("critique")
        return orig_critique(*a, **k)

    monkeypatch.setattr(pipeline.engine, "realize_phrase", spy_realize)
    monkeypatch.setattr(pipeline.engine, "critique", spy_critique)

    motif = pipeline.motifs(ctx, 1)[0]
    pipeline.compose(ctx, motif)
    assert "realize" in calls and "critique" in calls
    # 비평은 실현이 모두 끝난 뒤에 별도로 일어난다.
    assert calls.index("critique") > calls.index("realize")


# ── 원칙 4: 하드 규칙은 코드가, 음악성은 지표가 ─────────────────────────


def test_compose_produces_savable_score(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    assert res.savable, [i.message for i in res.validation.hard_failures]
    assert res.measures
    assert res.plan.total_measures == len(res.measures), "Plan 이 설계한 마디가 전부 실현돼야 한다"
    assert "<note" in res.musicxml
    assert res.quality.musicality["metrics"]
    assert 0 <= res.quality.combined_score <= 10


def test_plan_rejected_when_rules_fail(pipeline, ctx, engine, monkeypatch):
    motif = pipeline.motifs(ctx, 1)[0]
    good, _ = pipeline.plan(ctx, motif)
    # 클라이맥스를 첫 마디로 옮기면 규칙 검사에 걸린다.
    broken = good.model_copy(update={"climax": good.climax.model_copy(update={"measure": 1})})
    monkeypatch.setattr(engine, "plan", lambda *a, **k: broken)
    with pytest.raises(PlanRejected):
        pipeline.compose(ctx, motif)


def test_below_threshold_score_is_marked_as_draft(pipeline, ctx, monkeypatch):
    """절대 규칙 10 — 문턱 미달 곡은 '초안(미통과)' 으로만 보인다."""
    monkeypatch.setattr(pipeline.settings, "quality_threshold", 9.9)
    monkeypatch.setattr(pipeline.settings, "max_revision_rounds", 0)
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    assert not res.quality.passed
    assert res.shown_as_draft is res.savable


def test_deterministic_offline_engine_is_reproducible(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    a = pipeline.compose(ctx, motif)
    b = pipeline.compose(ctx, motif)
    assert a.musicxml == b.musicxml, "골든 회귀가 성립하려면 스텁이 결정적이어야 한다"


# ── 겨냥 수정 라운드 (문턱을 넘어도 약한 항목은 고친다) ─────────────────────


def _critic(scores: dict[str, float], requests: list[tuple[list[int], str]]):
    from app.schemas.quality import CriticReport, RevisionRequest, RubricScores

    base = dict.fromkeys(RubricScores.model_fields, 9.0)
    base.update(scores)
    return CriticReport(
        scores=RubricScores(**base),
        revision_requests=[
            RevisionRequest(measures=m, issue="약함", instruction=i) for m, i in requests
        ],
    )


def test_targeted_round_runs_even_when_the_total_passes(ctx) -> None:
    """종합 8점대라도 개별 루브릭이 문턱 아래면 겨냥 수정이 돈다."""
    from app.generation.engines.stub import StubComposerEngine
    from app.generation.pipeline import CompositionPipeline

    pipe = CompositionPipeline(StubComposerEngine())
    motifs = pipe.motifs(ctx, 2)
    plan, _ = pipe.plan(ctx, motifs[0])
    measures, _ = pipe.realize(ctx, plan, motifs[0])
    critic = _critic({"originality": 5.5}, [([1, 4], "1~4마디를 다시 써라")])

    _, tuned, notes = pipe._targeted(ctx, measures, plan, motifs[0], critic, combined=8.5)
    assert any("originality" in n for n in notes), notes
    # 채택 여부는 결과에 달렸지만, 시도는 반드시 있어야 한다
    assert tuned is not None or any("유지" in n or "없다" in n for n in notes), notes


def test_targeted_round_leaves_whole_piece_remarks_to_the_director(ctx) -> None:
    """곡 전체를 가리키는 지적은 프레이즈 재생성으로 옮기지 않고 글로 남긴다."""
    from app.generation.engines.stub import StubComposerEngine
    from app.generation.pipeline import CompositionPipeline

    pipe = CompositionPipeline(StubComposerEngine())
    motifs = pipe.motifs(ctx, 2)
    plan, _ = pipe.plan(ctx, motifs[0])
    measures, _ = pipe.realize(ctx, plan, motifs[0])
    critic = _critic(
        {"originality": 5.0},
        [([1, plan.total_measures], "재료가 평범하다")],
    )
    out, tuned, notes = pipe._targeted(ctx, measures, plan, motifs[0], critic, combined=8.5)
    assert out is measures and tuned is None
    assert any("재료가 평범하다" in n for n in notes), notes


def test_targeted_round_is_quiet_when_nothing_is_weak(ctx) -> None:
    from app.generation.engines.stub import StubComposerEngine
    from app.generation.pipeline import CompositionPipeline

    pipe = CompositionPipeline(StubComposerEngine())
    motifs = pipe.motifs(ctx, 2)
    plan, _ = pipe.plan(ctx, motifs[0])
    measures, _ = pipe.realize(ctx, plan, motifs[0])
    # 난이도까지 맞다고 가정할 수 없으므로 허용 오차를 넓혀 둔다
    pipe.settings = pipe.settings.model_copy(update={"difficulty_tolerance": 2.0})
    critic = _critic({}, [([1, 4], "사소한 것")])
    out, tuned, notes = pipe._targeted(ctx, measures, plan, motifs[0], critic, combined=9.0)
    assert out is measures and tuned is None and notes == []


def test_difficulty_advice_names_a_lever() -> None:
    from app.analysis.difficulty import DifficultyReport, difficulty_advice

    rep = DifficultyReport(score=3.0, features={"note_density": 0.1, "simultaneity": 0.9})
    up = difficulty_advice(rep, 6.0)
    assert "올려야" in up[0]
    assert any("note_density" in line for line in up)      # 가장 낮은 축부터 만진다
    down = difficulty_advice(rep, 1.5)
    assert "내려야" in down[0]
    assert any("simultaneity" in line for line in down)    # 가장 높은 축부터 만진다
