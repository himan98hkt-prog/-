"""정밀 분석에서 발견한 결함들의 회귀 테스트.

각 테스트는 한 번 실제로 깨졌던 동작을 고정한다.
"""
from __future__ import annotations

import pytest
from app.api.deps import STORE
from app.generation.context import build_context
from app.generation.engines.stub import StubComposerEngine, _climax_measure
from app.generation.plan_rules import check_plan
from app.main import app
from app.schemas.student import CompositionRequest
from fastapi.testclient import TestClient

# ── 1. 짧은 곡의 클라이맥스가 60~80% 밖으로 나가 Plan 검사가 실패했다 ──────


@pytest.mark.parametrize("total", [16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60, 72, 96])
def test_climax_always_lands_in_the_60_to_80_percent_band(total: int):
    m = _climax_measure(total)
    assert 0.60 <= m / total <= 0.80, f"{total}마디 → 클라이맥스 {m} ({m / total:.0%})"


@pytest.mark.parametrize("total", [16, 20, 32, 52])
def test_short_pieces_produce_a_valid_plan(total: int, student):
    """16마디는 허용 최소값이다. 여기서 Plan 규칙이 깨지면 요청 자체가 막힌다."""
    req = CompositionRequest(
        id="r", student=student, target_difficulty=4.0,
        key_preference=["C"], meter="4/4", tempo=100, total_measures=total,
    )
    ctx = build_context(req)
    engine = StubComposerEngine()
    motif = engine.motifs(ctx, 1)[0]
    plan = engine.plan(ctx, motif)
    report = check_plan(plan, student)
    assert report.passed, [i.message for i in report.hard_failures]


# ── 2. Plan 을 수정하면 모의 심사가 409 로 막혔다(객체 동일성 비교) ───────


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals):
        bucket.clear()
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


def _make_composition(client, student) -> tuple[str, str, dict]:
    payload = {
        "id": "", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 4.0, "mood": "밝은", "form": "ABA",
        "key_preference": ["A"], "meter": "4/4", "tempo": 104, "total_measures": 32,
        "reference_style_ids": [], "texture_options": [], "must_include": "", "n_candidates": 1,
    }
    rid = client.post("/api/requests", json=payload).json()["request_id"]
    motifs = client.post(f"/api/requests/{rid}/motifs", json={"n": 2}).json()["candidates"]
    plan = client.post(f"/api/requests/{rid}/motifs/{motifs[0]['id']}/select").json()["plan"]
    cid = client.post(f"/api/requests/{rid}/realize").json()["composition_id"]
    return rid, cid, plan


def test_judge_still_works_after_the_plan_is_edited(client, student):
    rid, cid, plan = _make_composition(client, student)
    assert client.post(f"/api/compositions/{cid}/judge").status_code == 200

    # 원장이 Plan 을 손보면 저장된 Plan 객체가 교체된다.
    assert client.patch(f"/api/requests/{rid}/plan", json=plan).status_code == 200
    assert client.post(f"/api/compositions/{cid}/judge").status_code == 200, (
        "곡은 자기 요청 id 를 들고 있어야 한다 — Plan 객체 동일성으로 찾으면 안 된다"
    )


def test_composition_remembers_its_request(client, student):
    rid, cid, _ = _make_composition(client, student)
    assert STORE.compositions[cid].request_id == rid


# ── 3. 검증기 경고가 비평가에게 전달되지 않아 아무도 고치지 않았다 ────────


def test_validator_warnings_reach_the_critic(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)
    measures, _ = pipeline.realize(ctx, plan, motif)

    warnings = pipeline.soft_warnings(ctx, measures, plan)
    _musicality, critic = pipeline.evaluate(ctx, measures, plan, motif)

    if warnings:
        # 경고가 있으면 비평가의 수정 지시에 그 취지가 반영돼야 한다.
        issues = " ".join(rr.issue for rr in critic.revision_requests)
        tokens = ("병행", "다이내믹 대비", "마무리", "클라이맥스")
        assert any(t in issues for t in tokens), (
            f"경고 {warnings[:3]} 가 수정 지시로 이어지지 않았다: {issues}"
        )


def test_parallel_fifths_and_octaves_stay_rare(pipeline, ctx):
    """왼손 베이스를 고를 때 병행 5·8도를 피한다.

    고치기 전에는 32마디 곡에 5~10건씩 남았다. 여기서는 마디 수 대비 5% 이하를 요구한다.
    """
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    parallels = [i for i in res.validation.warnings if i.rule == "parallels"]
    ratio = len(parallels) / max(1, len(res.measures))
    assert ratio <= 0.05, (
        f"{len(res.measures)}마디에 병행 {len(parallels)}건 ({ratio:.0%}) — "
        f"{[i.message for i in parallels[:5]]}"
    )


def test_left_hand_stays_inside_the_student_range(pipeline, ctx):
    """자리바꿈을 고르다 저음이 학생 음역 아래로 새던 회귀."""
    from app.analysis.pitch import pitch_to_midi

    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    for m in res.measures:
        for v in m.lh:
            for e in v.events:
                for p in e.pitches:
                    assert ctx.hard.lowest_midi <= pitch_to_midi(p) <= ctx.hard.highest_midi, (
                        f"{m.number}마디 왼손 {p} 가 음역 밖"
                    )
