"""API 계약 — 워크플로 순서가 URL 로 강제되는지(절대 규칙 9 를 API 층에서도)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import STORE
from app.main import app


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals):
        bucket.clear()
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def req_id(client, student, competition):
    client.post("/api/students", json=student.model_dump(mode="json"))
    client.post("/api/competition-profiles", json=competition.model_dump(mode="json"))
    r = client.post("/api/requests", json={
        "id": "req-1", "student": student.model_dump(mode="json"),
        "competition": competition.model_dump(mode="json"),
        "target_difficulty": 4.0, "mood": "밝고 활기찬", "form": "ABA",
        "key_preference": ["A"], "meter": "4/4", "tempo": 104, "n_candidates": 1,
        "reference_style_ids": [], "texture_options": [], "must_include": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["request_id"]


def test_health_reports_models_and_engine(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["composer_model"] and body["writer_model"]
    assert body["engine"] in ("claude", "stub-rule-based")


def test_request_returns_constraints_and_feasibility(client, req_id):
    r = client.get("/health")
    assert r.status_code == 200
    # 요청 생성 응답에 하드 제약이 그대로 실려 나온다 — 화면이 같은 값을 보여야 한다.
    assert req_id


def test_infeasible_target_is_warned_at_request_time(client, student):
    payload = {
        "id": "req-bad", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 10.0, "mood": "느린 자장가", "form": "AB",
        "key_preference": ["C"], "meter": "4/4", "tempo": 60, "n_candidates": 1,
        "reference_style_ids": [], "texture_options": [], "must_include": "",
    }
    r = client.post("/api/requests", json=payload)
    assert r.status_code == 200
    assert r.json()["feasibility_warning"], "만들 수 없는 주문은 생성 전에 알려야 한다"


def test_competition_forbidding_original_is_rejected_at_request(client, student, competition):
    payload = {
        "id": "req-x", "student": student.model_dump(mode="json"),
        "competition": {**competition.model_dump(mode="json"), "original_allowed": False},
        "target_difficulty": 4.0, "mood": "밝은", "form": "ABA",
        "key_preference": ["C"], "meter": "4/4", "tempo": 100, "n_candidates": 1,
        "reference_style_ids": [], "texture_options": [], "must_include": "",
    }
    assert client.post("/api/requests", json=payload).status_code == 422


def test_plan_requires_a_selected_motif(client, req_id):
    r = client.post(f"/api/requests/{req_id}/realize")
    assert r.status_code == 409, "모티브·Plan 없이 실현할 수 없다"


def test_full_workflow_motif_plan_realize(client, req_id):
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 4})
    assert m.status_code == 200, m.text
    candidates = m.json()["candidates"]
    assert candidates

    p = client.post(f"/api/requests/{req_id}/motifs/{candidates[0]['id']}/select")
    assert p.status_code == 200, p.text
    assert p.json()["passed"], p.json()["issues"]
    assert p.json()["plan"]["key"] == candidates[0]["key"]

    r = client.post(f"/api/requests/{req_id}/realize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["measures"] == p.json()["plan"]["total_measures"]
    assert body["validation"]["passed"], body["validation"]["issues"]
    assert body["quality"]["musicality"]["metrics"]

    cid = body["composition_id"]
    xml = client.get(f"/api/compositions/{cid}/musicxml")
    assert xml.status_code == 200
    assert "<note" in xml.json()["musicxml"]

    q = client.get(f"/api/compositions/{cid}/quality")
    assert q.status_code == 200
    assert "combined_score" in q.json()["quality"]


def test_judge_panel_endpoint(client, req_id):
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 2})
    cid_motif = m.json()["candidates"][0]["id"]
    client.post(f"/api/requests/{req_id}/motifs/{cid_motif}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    j = client.post(f"/api/compositions/{cid}/judge")
    assert j.status_code == 200, j.text
    assert len(j.json()["panel"]["verdicts"]) == 3
    assert 0 <= j.json()["average"] <= 10


def test_recital_flags_consecutive_same_key(client, req_id):
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 2})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    r = client.post("/api/recitals", json={
        "name": "봄 연주회", "target_duration_sec": 3600, "order_rule": "difficulty",
        "items": [{"student_id": "s1", "composition_id": cid},
                  {"student_id": "s1", "composition_id": cid}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 2
    kinds = {w["kind"] for w in body["warnings"]}
    assert "key" in kinds and "tempo" in kinds, "같은 곡을 연달아 놓으면 대비 경고가 나와야 한다"
    assert body["total_sec"] > 0


def test_unvalidated_score_cannot_be_exported(client, req_id, monkeypatch):
    from app.api.deps import STORE as S

    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 2})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    res = S.compositions[cid]
    res.validation.add("range", "hard", "테스트용 강제 실패")
    assert client.get(f"/api/compositions/{cid}/musicxml").status_code == 409
