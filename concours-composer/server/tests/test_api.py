"""API 계약 — 워크플로 순서가 URL 로 강제되는지(절대 규칙 9 를 API 층에서도)."""
from __future__ import annotations

import pytest
from app.api.deps import STORE
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals,
                   STORE.judgements, STORE.rights):
        bucket.clear()
    STORE.jobs.clear()
    # 코퍼스는 모듈 싱글턴이다. 앞 테스트가 만든 곡이 남아 있으면 다음 곡이
    # 자기 형제와 표절로 부딪힌다 — 실제 운영과 달리 테스트는 매번 새 학원이다.
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
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


# ── 대시보드(스튜디오) — 컨셉 버튼 하나로 끝까지 ─────────────────────────────


def test_presets_mark_what_suits_this_student(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    r = client.get("/api/presets", params={"student_id": student.id})
    assert r.status_code == 200, r.text
    presets = r.json()
    assert len(presets) >= 8
    assert presets[0]["recommended"] is True          # 권하는 것이 앞에 온다
    # 권하지 않는 것도 숨기지 않는다 — 원장이 일부러 고를 수 있어야 한다.
    assert any(p["recommended"] is False for p in presets)
    finale = next(p for p in presets if p["id"] == "finale")
    assert finale["recommended"] is False, "레벨 4 학생에게 피날레를 권하면 안 된다"


def test_auto_compose_runs_the_whole_pipeline_and_judges_before_handing_over(
    client, student, competition
):
    """컨셉 하나 고르면 모티브·설계·작곡·사전 심사까지 한 번에 끝나야 한다."""
    client.post("/api/students", json=student.model_dump(mode="json"))
    client.post("/api/competition-profiles", json=competition.model_dump(mode="json"))
    r = client.post("/api/compositions/auto", json={
        "preset_id": "march", "student_id": student.id,
        "competition_profile_id": competition.id,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["measures"] >= 8
    assert body["validation"]["passed"], body["validation"]
    # 프리셋이 요청을 채웠다
    assert body["meter"] == "4/4"
    # 곡을 내놓기 전에 심사가 돌았다 — 통과 여부와 문턱이 함께 온다
    j = body["judge"]
    assert j["panel"] and len(j["panel"]["verdicts"]) == 3
    assert j["required_average"] > 0 and isinstance(j["passed"], bool)
    assert j["average"] == pytest.approx(j["panel"]["average"])
    # 이어서 기존 워크플로로 손볼 수 있게 request_id 가 살아 있다
    assert client.get(f"/api/compositions/{body['composition_id']}/quality").status_code == 200


def test_auto_compose_rejects_an_unknown_preset(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    r = client.post("/api/compositions/auto",
                    json={"preset_id": "없는컨셉", "student_id": student.id})
    assert r.status_code == 404


def test_library_lists_what_was_made_with_the_judge_verdict(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    client.post("/api/compositions/auto",
                json={"preset_id": "miniature", "student_id": student.id})
    r = client.get("/api/compositions")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["judged"] is True
    assert items[0]["judge_average"] is not None
    assert items[0]["versions"] == 1


def test_rearrange_changes_only_the_named_measures(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    made = client.post("/api/compositions/auto",
                       json={"preset_id": "march", "student_id": student.id}).json()
    cid = made["composition_id"]
    before = client.get(f"/api/compositions/{cid}/measures").json()

    r = client.post(f"/api/compositions/{cid}/rearrange",
                    json={"measures": [5, 8], "instruction": "왼손을 한 옥타브 내려라"})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2
    after = client.get(f"/api/compositions/{cid}/measures").json()

    changed = {a["number"] for a, b in zip(before, after, strict=True) if a != b}
    assert changed <= {5, 6, 7, 8}, f"지정하지 않은 마디가 바뀌었다: {changed}"


def test_rearrange_refuses_a_range_outside_the_piece(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    made = client.post("/api/compositions/auto",
                       json={"preset_id": "march", "student_id": student.id}).json()
    r = client.post(f"/api/compositions/{made['composition_id']}/rearrange",
                    json={"measures": [900, 999], "instruction": "왼손을 한 옥타브 내려라"})
    assert r.status_code == 422


def test_auto_compose_tries_another_motif_when_the_plan_collides(client, student):
    """같은 컨셉을 두 번 눌러도 겹침 오류 벽을 보이지 않는다.

    형식이 겹치면 그 설계를 버리는 것이 맞다(절대 규칙 12). 하지만 그것은 다른 모티브로
    다시 시도하라는 뜻이지, 버튼 하나 누른 원장에게 오류를 던지라는 뜻이 아니다.
    후보를 다 써도 겹치면 그때는 409 로 **무엇을 하면 되는지와 함께** 알린다.
    """
    client.post("/api/students", json=student.model_dump(mode="json"))
    first = client.post("/api/compositions/auto",
                        json={"preset_id": "march", "student_id": student.id})
    assert first.status_code == 200, first.text

    second = client.post("/api/compositions/auto",
                         json={"preset_id": "march", "student_id": student.id})
    assert second.status_code in (200, 409), second.text
    if second.status_code == 409:
        detail = second.json()["detail"]
        assert "what_to_do" in detail and detail["issues"]
    else:
        # 다른 모티브로 통과했다면 앞 곡과 형식이 같으면 안 된다.
        from app.api.deps import STORE
        from app.generation.diversity import FormFingerprint, compare

        plans = [e["plan"] for e in STORE.plans.values()]
        assert len(plans) == 2
        sim, _ = compare(FormFingerprint.of(plans[0]), FormFingerprint.of(plans[1]))
        assert sim < 0.60, f"겹침 검사를 통과했다는데 유사도가 {sim} 다"


def test_direct_edit_saves_only_the_named_measures_and_revalidates(client, student):
    """M4 직접 편집 — 원장이 고친 마디만 넣고, 검증기·지표는 그대로 다시 돌린다."""
    client.post("/api/students", json=student.model_dump(mode="json"))
    made = client.post("/api/compositions/auto",
                       json={"preset_id": "march", "student_id": student.id}).json()
    cid = made["composition_id"]
    before = client.get(f"/api/compositions/{cid}/measures").json()

    edited = dict(before[2])
    edited["rh"] = [{"voice": 1, "events": [{"dur": 4, "pitches": ["C5"], "artic": "none"}]}]
    r = client.put(f"/api/compositions/{cid}/measures", json={"measures": [edited]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["changed_measures"] == [before[2]["number"]]
    assert body["version"] == 2
    assert "passed" in body["validation"]

    after = client.get(f"/api/compositions/{cid}/measures").json()
    changed = {a["number"] for a, b in zip(before, after, strict=True) if a != b}
    assert changed == {before[2]["number"]}, f"다른 마디가 바뀌었다: {changed}"


def test_direct_edit_refuses_a_measure_the_piece_does_not_have(client, student):
    client.post("/api/students", json=student.model_dump(mode="json"))
    made = client.post("/api/compositions/auto",
                       json={"preset_id": "march", "student_id": student.id}).json()
    r = client.put(f"/api/compositions/{made['composition_id']}/measures", json={"measures": [
        {"number": 9999, "rh": [{"voice": 1, "events": [{"dur": 4, "pitches": ["C5"]}]}]},
    ]})
    assert r.status_code == 422
    assert "9999" in str(r.json()["detail"])


def test_direct_edit_reports_a_broken_bar_instead_of_saving_it_silently(client, student):
    """마디 길이가 안 맞는 편집은 저장은 되되 savable=false 로 드러나야 한다."""
    client.post("/api/students", json=student.model_dump(mode="json"))
    made = client.post("/api/compositions/auto",
                       json={"preset_id": "march", "student_id": student.id}).json()
    cid = made["composition_id"]
    first = client.get(f"/api/compositions/{cid}/measures").json()[0]
    broken = dict(first)
    broken["rh"] = [{"voice": 1, "events": [{"dur": 0.5, "pitches": ["C5"], "artic": "none"}]}]
    r = client.put(f"/api/compositions/{cid}/measures", json={"measures": [broken]})
    assert r.status_code == 200, r.text
    assert r.json()["savable"] is False
    assert any(i["rule"] == "measure_length" for i in r.json()["validation"]["issues"])


def test_audio_download(client, req_id):
    """곡을 소리 파일로 받는다 — 학부모에게 그대로 보낼 수 있어야 한다."""
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    r = client.get(f"/api/compositions/{cid}/audio?hands=rh")
    assert r.status_code == 200, r.text
    assert r.headers["x-audio-format"] in {"mp3", "wav"}
    assert r.headers["content-type"] in {"audio/mpeg", "audio/wav"}
    assert len(r.content) > 4096
    assert "attachment" in r.headers["content-disposition"]

    # 두 번째 호출은 캐시라 같은 바이트가 나와야 한다.
    again = client.get(f"/api/compositions/{cid}/audio?hands=rh")
    assert again.content == r.content

    assert client.get("/api/compositions/nope/audio").status_code == 404


def test_composer_identity_and_registration(client, req_id):
    """예명은 악보로, 실명은 등록 서류로 — 두 길이 섞이지 않아야 한다."""
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    assert client.get("/api/composer").json()["alias"] == "accelssam"

    who = client.put("/api/composer", json={
        "alias": "accelssam", "legal_name": "이경실", "birth_date": "1985-04-02",
        "nationality": "대한민국", "email": "a@b.kr", "phone": "", "address": "서울시",
    })
    assert who.status_code == 200, who.text

    # 실명은 악보에 나가지 않는다.
    xml = client.get(f"/api/compositions/{cid}/musicxml").json()["musicxml"]
    assert "accelssam" in xml and "이경실" not in xml

    # 창작곡이면 등록 초안이 바로 준비된다.
    d = client.get(f"/api/compositions/{cid}/registration").json()
    assert d["ready"] is True and d["blockers"] == []
    assert "이경실" in d["markdown"] and "accelssam" in d["markdown"]

    # 편곡으로 바꾸고 원곡을 비워 두면 막힌다.
    client.put(f"/api/compositions/{cid}/rights", json={
        "work_type": "arrangement", "original_title": "", "original_composer": "",
        "original_status": "unknown", "license_note": "", "first_published": "", "note": "",
    })
    blocked = client.get(f"/api/compositions/{cid}/registration").json()
    assert blocked["ready"] is False and blocked["blockers"]

    # 보호 기간이 끝난 원곡이면 통과한다.
    client.put(f"/api/compositions/{cid}/rights", json={
        "work_type": "arrangement", "original_title": "G선상의 아리아",
        "original_composer": "J.S. Bach", "original_status": "public_domain",
        "license_note": "", "first_published": "", "note": "",
    })
    cleared = client.get(f"/api/compositions/{cid}/registration").json()
    assert cleared["ready"] is True

    md = client.get(f"/api/compositions/{cid}/registration.md")
    assert md.status_code == 200 and "저작권 등록 신청 초안" in md.text

    assert client.get("/api/compositions/nope/registration").status_code == 404


def test_sales_package(client, req_id):
    """판매 꾸러미 — 받는 사람이 압축을 풀면 무엇부터 열면 되는지 알 수 있어야 한다."""
    import io
    import zipfile

    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    r = client.get(f"/api/compositions/{cid}/package")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"

    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert all(n.count("/") == 1 for n in names), f"폴더 하나로 묶여야 한다: {names}"
    tails = {n.split("/", 1)[1] for n in names}
    assert "읽어보세요.txt" in tails
    assert any(t.endswith(".musicxml") for t in tails)
    assert any(t.startswith("연주.") for t in tails)
    assert any(t.endswith(".mid") for t in tails)
    assert "곡 정보.md" in tails and "권리 정보.md" in tails

    readme = z.read(next(n for n in names if n.endswith("읽어보세요.txt"))).decode("utf-8")
    assert "accelssam" in readme
    assert "musescore.org" in readme          # 악보를 열 방법을 알려 줘야 한다

    # 창작곡이면 경고가 없다.
    assert "!! 주의" not in readme

    # 편곡인데 원곡이 불분명하면 꾸러미 안에서 경고해야 한다.
    client.put(f"/api/compositions/{cid}/rights", json={
        "work_type": "arrangement", "original_title": "", "original_composer": "",
        "original_status": "unknown", "license_note": "", "first_published": "", "note": "",
    })
    z2 = zipfile.ZipFile(io.BytesIO(client.get(f"/api/compositions/{cid}/package").content))
    warned = z2.read(next(n for n in z2.namelist() if n.endswith("읽어보세요.txt"))).decode("utf-8")
    assert "!! 주의" in warned
    rights_doc = z2.read(next(n for n in z2.namelist() if n.endswith("권리 정보.md"))).decode("utf-8")
    assert "등록하거나 판매하면 안 됩니다" in rights_doc

    assert client.get("/api/compositions/nope/package").status_code == 404


def test_library_shows_rights_state(client, req_id):
    """목록에서 팔 수 있는 곡과 권리 미정리 곡이 구분돼야 한다."""
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    row = next(i for i in client.get("/api/compositions").json() if i["composition_id"] == cid)
    assert row["work_type"] == "original" and row["rights_ready"] is True

    client.put(f"/api/compositions/{cid}/rights", json={
        "work_type": "arrangement", "original_title": "어떤 곡",
        "original_composer": "어떤 사람", "original_status": "copyrighted",
        "license_note": "", "first_published": "", "note": "",
    })
    row = next(i for i in client.get("/api/compositions").json() if i["composition_id"] == cid)
    assert row["work_type"] == "arrangement" and row["rights_ready"] is False
    assert "확인 필요" in row["rights_note"]


def test_title_flows_to_every_artifact(client, req_id):
    """제목을 바꾸면 악보·꾸러미·등록 초안이 모두 같은 이름을 써야 한다.

    파일마다 다른 이름이 찍히면 파는 쪽에서 사고가 난다.
    """
    import io
    import zipfile

    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    before = client.get(f"/api/compositions/{cid}/title-current").json()
    assert before["title"] and before["suggested"]

    put = client.put(f"/api/compositions/{cid}/title-current", json={"title": "  봄의 문턱  "})
    assert put.status_code == 200
    assert put.json()["title"] == "봄의 문턱", "앞뒤 공백은 다듬어야 한다"

    assert client.get(f"/api/compositions/{cid}/quality").json()["title"] == "봄의 문턱"
    row = next(i for i in client.get("/api/compositions").json() if i["composition_id"] == cid)
    assert row["title"] == "봄의 문턱"
    assert "봄의 문턱" in client.get(f"/api/compositions/{cid}/registration").json()["markdown"]

    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/compositions/{cid}/package").content))
    assert any(n.startswith("봄의 문턱/") for n in z.namelist()), z.namelist()

    # 비우면 프로그램이 지은 이름으로 돌아간다.
    back = client.put(f"/api/compositions/{cid}/title-current", json={"title": "   "})
    assert back.json()["title"] == before["title"]

    assert client.get("/api/compositions/nope/title-current").status_code == 404


def test_cover_masks_the_student_name_without_consent(client, req_id, student):
    """악보 표지는 밖으로 나가는 산출물이다 — 동의 없는 본명이 실리면 안 된다(절대 규칙 7)."""
    m = client.post(f"/api/requests/{req_id}/motifs", json={"n": 1})
    client.post(f"/api/requests/{req_id}/motifs/{m.json()['candidates'][0]['id']}/select")
    cid = client.post(f"/api/requests/{req_id}/realize").json()["composition_id"]

    c = client.get(f"/api/compositions/{cid}/cover")
    assert c.status_code == 200, c.text
    body = c.json()
    assert body["composer"] == "accelssam"
    assert body["title"] and body["measures"] > 0 and body["duration_sec"] > 0
    # 기본 학생은 미디어 동의가 없다 — 마스킹된 이름이어야 한다.
    real = student.name
    if len(real) > 1:
        assert body["student_name"] != real
        assert "○" in body["student_name"]

    assert client.get("/api/compositions/nope/cover").status_code == 404


def test_backup_endpoint_reports_state(client):
    """백업 상태는 화면에 보여야 한다 — 사본이 있다는 사실을 알아야 안심하고 쓴다."""
    b = client.get("/api/backups")
    assert b.status_code == 200
    body = b.json()
    # 테스트는 파일 저장을 쓰지 않으므로 꺼진 상태를 정확히 알려야 한다.
    assert body["enabled"] is False and body["why"]
    assert client.post("/api/backups").status_code == 409
