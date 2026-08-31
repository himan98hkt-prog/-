"""세션 엔진(GOLDEN_ENGINE=session) · 원장 피드백 · 비용 로깅."""
from __future__ import annotations

import json

import pytest
from app.api.deps import STORE
from app.config import Settings, read_api_key_from_env_file
from app.generation.client import CostLedger
from app.generation.engines.session import AwaitingResponse, SessionComposerEngine
from app.generation.pipeline import CompositionPipeline
from app.main import app
from fastapi.testclient import TestClient

# ── API 키는 .env 파일에서만 (원장 지시 4) ───────────────────────────────


def test_api_key_ignores_system_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 40)
    s = Settings()
    assert "xxxx" not in s.anthropic_api_key, "시스템 환경변수를 키로 쓰면 안 된다"


def test_api_key_reads_only_the_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text('ANTHROPIC_API_KEY="sk-ant-from-file-0123456789"\nOTHER=1\n', encoding="utf-8")
    assert read_api_key_from_env_file(f) == "sk-ant-from-file-0123456789"
    assert read_api_key_from_env_file(tmp_path / "missing") == ""


# ── 세션 엔진 ────────────────────────────────────────────────────────────


def test_session_engine_writes_a_prompt_and_waits(ctx, tmp_path):
    engine = SessionComposerEngine(tmp_path, wait=False)
    pipe = CompositionPipeline(engine, progress=lambda *_: None)

    with pytest.raises(AwaitingResponse) as e:
        pipe.motifs(ctx, 3)

    assert e.value.stage == "motif"
    prompt = (tmp_path / "motif_prompt.md").read_text(encoding="utf-8")
    assert "## 시스템 지시" in prompt
    assert "## 출력 JSON 스키마" in prompt
    # 고정 컨텍스트에 학생 제약이 실려 있어야 프롬프트만 보고 작곡할 수 있다.
    assert "max_span_semitones" in prompt
    assert str(ctx.hard.max_span_semitones) in prompt


def test_session_engine_consumes_a_written_response(ctx, tmp_path, engine):
    """스텁 엔진의 출력을 응답 파일로 써 두면 세션 엔진이 그대로 이어받는다."""
    stub_motifs = engine.motifs(ctx, 3)
    payload = {"candidates": [m.model_dump(mode="json") for m in stub_motifs]}
    (tmp_path / "motif_response.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    session = SessionComposerEngine(tmp_path, wait=False)
    got = session.motifs(ctx, 3)
    assert [m.id for m in got] == [m.id for m in stub_motifs]
    assert session.stats.responses_read == 1


def test_session_engine_rejects_an_off_schema_response(ctx, tmp_path):
    (tmp_path / "motif_response.json").write_text('{"candidates": []}', encoding="utf-8")
    session = SessionComposerEngine(tmp_path, wait=False)
    with pytest.raises(ValueError, match="스키마"):
        session.motifs(ctx, 3)
    assert (tmp_path / "motif_error.txt").exists(), "무엇이 틀렸는지 파일로 남아야 한다"


def test_session_engine_counts_tokens_for_cost_projection(ctx, tmp_path, engine):
    """API 를 부르지 않아도 토큰은 센다 — 전환 시 곡당 비용을 바로 계산하려면 필요하다."""
    payload = {"candidates": [m.model_dump(mode="json") for m in engine.motifs(ctx, 2)]}
    (tmp_path / "motif_response.json").write_text(json.dumps(payload), encoding="utf-8")

    ledger = CostLedger(limit_usd=5.0, composition_id="t", engine="session")
    session = SessionComposerEngine(tmp_path, ledger=ledger, wait=False)
    session.motifs(ctx, 2)

    assert ledger.calls and ledger.total_input_tokens > 0
    assert ledger.total_usd == 0.0, "세션 모드의 실제 지출은 0 이다"

    projection = ledger.projected_cost("claude-opus-5")
    assert projection["cost_usd_no_cache"] > 0
    assert projection["cost_usd_with_cache"] < projection["cost_usd_no_cache"]

    out = tmp_path / "cost.json"
    ledger.write(out, model="claude-opus-5")
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["summary"]["calls"] == 1
    assert "projection" in saved


# ── 프롬프트 캐싱 ────────────────────────────────────────────────────────


def test_fixed_context_holds_what_does_not_change_within_a_piece(ctx):
    """캐시 접두사에는 곡 하나 동안 안 바뀌는 것만 들어가야 한다."""
    from app.generation.engines.claude_engine import fixed_context

    a = fixed_context(ctx)
    b = fixed_context(ctx)
    assert a == b, "같은 곡이면 고정 컨텍스트도 바이트까지 같아야 캐시가 산다"
    assert "student" in a and "constraints" in a
    # 프레이즈마다 바뀌는 것은 들어가면 안 된다.
    assert "previous_measures" not in a
    assert "phrase_plan" not in a


def test_system_blocks_mark_the_cache_boundary():
    from app.generation.client import ClaudeClient

    blocks = ClaudeClient._system_blocks("시스템", "고정")
    assert len(blocks) == 2
    assert "cache_control" not in blocks[0], "캐시 표시는 접두사 마지막 블록에만 붙는다"
    assert blocks[-1]["cache_control"] == {"type": "ephemeral"}


# ── 원장 피드백 ──────────────────────────────────────────────────────────


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals):
        bucket.clear()
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


def _compose(client, student) -> str:
    payload = {
        "id": "", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 4.0, "mood": "밝은", "form": "ABA", "key_preference": ["A"],
        "meter": "4/4", "tempo": 104, "total_measures": 32,
        "reference_style_ids": [], "texture_options": [], "must_include": "", "n_candidates": 1,
    }
    rid = client.post("/api/requests", json=payload).json()["request_id"]
    motifs = client.post(f"/api/requests/{rid}/motifs", json={"n": 2}).json()["candidates"]
    client.post(f"/api/requests/{rid}/motifs/{motifs[0]['id']}/select")
    return client.post(f"/api/requests/{rid}/realize").json()["composition_id"]


def test_feedback_snapshots_the_scores_at_the_time(client, student):
    cid = _compose(client, student)
    r = client.post("/api/feedback", json={
        "composition_id": cid, "thumbs": "up", "reason_tags": ["motif", "student_fit"],
        "comment": "모티브가 분명하다", "would_use_without_edit": True, "edited_measures": [],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # 나중에 회귀하려면 평가 시점의 지표가 함께 얼려져 있어야 한다.
    assert body["musicality_snapshot"]["metrics"]
    assert body["difficulty_snapshot"] is not None
    assert body["difficulty_target"] is not None


def test_feedback_rejects_unknown_tags_and_missing_compositions(client, student):
    cid = _compose(client, student)
    bad_tag = client.post("/api/feedback", json={
        "composition_id": cid, "thumbs": "down", "reason_tags": ["아무거나"],
    })
    assert bad_tag.status_code == 422

    missing = client.post("/api/feedback", json={"composition_id": "comp-9999", "thumbs": "up"})
    assert missing.status_code == 404


def test_feedback_stats_track_the_usable_rate(client, student):
    cid = _compose(client, student)
    for usable in (True, True, False):
        client.post("/api/feedback", json={
            "composition_id": cid, "thumbs": "up" if usable else "down",
            "reason_tags": ["boring"] if not usable else [],
            "would_use_without_edit": usable, "edited_measures": [] if usable else [13, 14],
        })
    st = client.get("/api/feedback/stats").json()
    assert st["total"] == 3 and st["up"] == 2 and st["down"] == 1
    assert st["usable_rate"] == round(2 / 3, 3)
    assert st["tag_counts"]["boring"] == 1
    # 표본이 적으면 가중치 보정을 시작하지 않는다(M8).
    assert st["ready_for_recalibration"] is False
    assert "M8" in st["note"]
