"""§6.6 해설 · 제목 · MIDI 내보내기."""
from __future__ import annotations

import pytest
from app.api.deps import STORE
from app.export.midi import measures_to_midi, note_events_to_midi
from app.generation.assemble import measures_to_note_events
from app.guide.writer import rule_based_guide
from app.main import app
from app.schemas.guide import Guide, GuideSection
from fastapi.testclient import TestClient
from music21 import converter

# ── MIDI ─────────────────────────────────────────────────────────────────


def test_midi_reparses_with_the_right_note_count(pipeline, ctx, tmp_path):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    data = measures_to_midi(res.measures, res.plan.tempo, res.plan.meter)

    path = tmp_path / "out.mid"
    path.write_bytes(data)
    score = converter.parse(str(path))
    reparsed = len(list(score.recurse().notes))
    expected = sum(
        1 for m in res.measures for v in (*m.rh, *m.lh) for e in v.events if e.pitches
    )
    assert reparsed == expected, f"MIDI {reparsed}개 vs 악보 {expected}개"


def test_midi_splits_hands_into_separate_tracks(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    data = measures_to_midi(res.measures, res.plan.tempo, res.plan.meter)
    assert data[:4] == b"MThd"
    assert b"Right Hand" in data and b"Left Hand" in data, "손 분리 연습에 트랙이 필요하다"


def test_midi_timing_matches_note_events(pipeline, ctx):
    """MIDI 총 길이가 NoteEvents 의 초 단위 길이와 맞아야 재생이 어긋나지 않는다."""
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    events = measures_to_note_events(res.measures, res.plan.tempo, res.plan.meter)
    data = note_events_to_midi(events)
    assert len(data) > 100
    assert data[:4] == b"MThd"


# ── 해설 ─────────────────────────────────────────────────────────────────


def test_rule_based_guide_anchors_are_all_valid(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    guide = rule_based_guide(ctx, res.measures, res.plan)
    assert guide.invalid_anchors(len(res.measures)) == [], "해설의 마디 참조가 곡 밖을 가리킨다"
    assert guide.sections
    assert len(guide.practice_plan) == 4, "4주 연습 계획(§6.6)"
    assert guide.competition_tips


def test_guide_detects_out_of_range_anchors():
    g = Guide(overview="x", sections=[GuideSection(measures=[1, 40], title="A", points=["p"])])
    assert g.invalid_anchors(32)
    assert g.invalid_anchors(40) == []


def test_memorization_required_competition_adds_a_tip(pipeline, ctx):
    motif = pipeline.motifs(ctx, 1)[0]
    res = pipeline.compose(ctx, motif)
    guide = rule_based_guide(ctx, res.measures, res.plan)
    if ctx.competition and ctx.competition.memorization_required:
        assert any("암보" in t for t in guide.competition_tips)


# ── API ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals):
        bucket.clear()
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


def test_motif_response_carries_playable_previews(client, student):
    payload = {
        "id": "", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 4.0, "mood": "밝은", "form": "ABA", "key_preference": ["A"],
        "meter": "4/4", "tempo": 104, "total_measures": 32,
        "reference_style_ids": [], "texture_options": [], "must_include": "", "n_candidates": 1,
    }
    rid = client.post("/api/requests", json=payload).json()["request_id"]
    body = client.post(f"/api/requests/{rid}/motifs", json={"n": 3}).json()

    assert len(body["previews"]) == len(body["candidates"])
    import base64

    for p in body["previews"]:
        raw = base64.b64decode(p["midi_base64"])
        assert raw[:4] == b"MThd", "원장이 들어보고 골라야 한다(§7.3 Stage 1)"


def test_guide_and_midi_endpoints(client, student):
    payload = {
        "id": "", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 4.0, "mood": "밝은", "form": "ABA", "key_preference": ["A"],
        "meter": "4/4", "tempo": 104, "total_measures": 32,
        "reference_style_ids": [], "texture_options": [], "must_include": "", "n_candidates": 1,
    }
    rid = client.post("/api/requests", json=payload).json()["request_id"]
    m = client.post(f"/api/requests/{rid}/motifs", json={"n": 2}).json()["candidates"]
    client.post(f"/api/requests/{rid}/motifs/{m[0]['id']}/select")
    cid = client.post(f"/api/requests/{rid}/realize").json()["composition_id"]

    assert client.get(f"/api/compositions/{cid}/guide").status_code == 404
    made = client.post(f"/api/compositions/{cid}/guide")
    assert made.status_code == 200, made.text
    assert made.json()["sections"]
    assert client.get(f"/api/compositions/{cid}/guide").status_code == 200

    title = client.post(f"/api/compositions/{cid}/title")
    assert title.status_code == 200
    assert title.json()["recommended"] in title.json()["candidates"]

    midi = client.get(f"/api/compositions/{cid}/midi")
    assert midi.status_code == 200
    assert midi.content[:4] == b"MThd"
    assert "attachment" in midi.headers["content-disposition"]
