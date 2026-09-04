"""§6.13 모의 심사 — 세 페르소나가 서로 다른 것을 보고, 지적 마디가 곡 안에 있어야 한다."""
from __future__ import annotations

from app.judge.panel import PERSONAS, run_panel_rules


def test_three_personas_with_distinct_views(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    panel = run_panel_rules(ctx, res.measures, res.plan, motif)

    assert [v.persona for v in panel.verdicts] == list(PERSONAS)
    # 세 사람이 같은 점수를 내면 세 명일 이유가 없다.
    assert len({v.total for v in panel.verdicts}) > 1
    assert 0 <= panel.average <= 10


def test_fix_lists_are_separated(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    panel = run_panel_rules(ctx, res.measures, res.plan, motif)
    for v in panel.verdicts:
        assert v.fix_in_practice, "연습 보완점은 항상 있어야 한다"
        # 곡 수정과 연습 보완이 같은 문장이면 원장이 구분할 수 없다.
        assert not (set(v.fix_in_score) & set(v.fix_in_practice))


def test_revision_measures_stay_inside_the_piece(pipeline, ctx):
    """심사 리포트의 마디 참조가 곡 밖을 가리키면 화면에서 점프할 수 없다."""
    import re

    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    panel = run_panel_rules(ctx, res.measures, res.plan, motif)
    total = len(res.measures)
    for v in panel.verdicts:
        for line in v.fix_in_score:
            for n in re.findall(r"(\d+)마디", line):
                assert 1 <= int(n) <= total, f"{line} — 곡은 {total}마디뿐이다"


def test_critic_revision_requests_reference_real_measures(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    total = len(res.measures)
    for rr in res.quality.critic["revision_requests"]:
        lo, hi = rr["measures"]
        assert 1 <= lo <= hi <= total, f"{rr} — 곡은 {total}마디뿐이다"


def test_consensus_fixes_surface_repeated_concerns(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    panel = run_panel_rules(ctx, res.measures, res.plan, motif)
    assert isinstance(panel.consensus_fixes(), list)
