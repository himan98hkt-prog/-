"""**의뢰서를 뽑고, 받아온 곡을 들인다** — 관문은 하나도 낮추지 않고.

원장님이 내신 설계다:

    "프로그램에서는 내가 요청하려고 하는 내용의 프롬프트 생성을 만들어주고
     그걸 너에게 요청하는 형태는 어떠한지 제안할께. 왜냐하면 프로픔트를
     구체적으로 만드는 것이 문제인데... 만들어진 결과물을 해당 프로그램의
     폴더에 저장하면 ... 이내용은 비용이 발생되지 않으니깐."

이 파일이 지키는 것은 둘이다.

  1. **의뢰서에 규정이 빠지지 않는다.** 손 크기·음역·빠르기 상한·제한 시간·임시표
     비율이 하나라도 빠지면, 그 조건을 어긴 곡이 와서 검증에 떨어진다. 원장님은
     "왜 자꾸 떨어지지" 만 겪으신다.
  2. **밖에서 왔다고 문을 낮추지 않는다.** 검증기를 통과 못 한 곡은 저장하지 않는다
     (절대 규칙 2). 팔 곡이고, 학원 원장이 사서 아이에게 시킬 곡이다.
"""

from __future__ import annotations

import json

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
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def piece():
    """스텁 엔진으로 한 곡 만들어, 대화창이 돌려줄 법한 JSON 을 흉내낸다."""
    from app.generation.context import build_context
    from app.generation.engines.stub import StubComposerEngine
    from app.generation.market import BY_TIER, standard_competition, standard_student
    from app.generation.pipeline import CompositionPipeline
    from app.generation.presets import BY_ID
    from app.schemas.student import CompositionRequest

    t, p = BY_TIER["middle"], BY_ID["toccata"]
    req = CompositionRequest(
        id="r1", student=standard_student(t), competition=standard_competition(t),
        target_difficulty=float(t.level), mood=p.mood, form=p.form,
        key_preference=list(p.keys), meter=p.meter, tempo=p.tempo[0],
    )
    ctx = build_context(req)
    pipe = CompositionPipeline(StubComposerEngine(), progress=lambda *_: None)
    res = pipe.compose_candidates(ctx, pipe.motifs(ctx, 1)[0], None, n=1)[0]
    return {
        "tier_id": "middle", "preset_id": "toccata", "title": "달리는 손가락",
        "plan": json.loads(res.plan.model_dump_json()),
        "motif": json.loads(res.motif.model_dump_json()),
        "measures": [json.loads(m.model_dump_json()) for m in res.measures],
        "critic": {
            "scores": dict.fromkeys(
                ("motif_development", "form_clarity", "harmony", "voice_leading",
                 "phrasing", "climax_ending", "student_fit", "competition_effect",
                 "notation", "originality"), 8),
            "overall_comment": "형식이 뚜렷하고 마무리가 분명하다.",
        },
    }


# ── 1. 의뢰서에 규정이 빠지지 않는다 ───────────────────────────────────────


def test_the_brief_carries_every_rule_that_can_reject_the_piece(client) -> None:
    """빠진 규정 하나가 곧 떨어지는 곡 하나다."""
    r = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "toccata"})
    assert r.status_code == 200
    brief = r.json()["brief"]

    from app.generation.context import build_context
    from app.generation.market import BY_TIER, standard_competition, standard_student
    from app.schemas.student import CompositionRequest

    t = BY_TIER["middle"]
    ctx = build_context(CompositionRequest(
        id="x", student=standard_student(t), competition=standard_competition(t),
        target_difficulty=float(t.level), mood="", form="ABA",
        key_preference=["C"], meter="4/4", tempo=100))
    h = ctx.hard
    for must, why in [
        (str(h.max_span_semitones), "손 크기를 안 적으면 손이 안 닿는 화음이 온다"),
        (str(h.lowest_midi), "음역 아래를 안 적으면 건반 밖의 음이 온다"),
        (str(h.highest_midi), "음역 위를 안 적으면 건반 밖의 음이 온다"),
        (str(h.max_tempo_bpm), "빠르기 상한을 안 적으면 무대에서 못 치는 곡이 온다"),
        (str(h.time_limit_sec), "제한 시간을 안 적으면 실격되는 곡이 온다"),
        (str(h.target_difficulty), "목표 난이도를 안 적으면 급수가 안 맞는다"),
        ("병행 5도", "검증기가 잡는 것을 미리 안 알려 주면 헛일을 시킨다"),
        ("표절", "기억나는 곡을 옮겨 적으면 통째로 떨어진다"),
    ]:
        assert must in brief, f"의뢰서에 {must!r} 가 없다 — {why}"


def test_the_owners_own_words_go_in_untouched(client) -> None:
    """원장님이 쓰시는 칸은 원장님 말 그대로 들어가야 한다."""
    wish = "심사위원이 처음 듣는 리듬꼴로 시작하고, 마무리를 화려하게."
    r = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "toccata", "wish": wish})
    assert wish in r.json()["brief"]


def test_the_brief_says_exactly_what_shape_to_send_back(client) -> None:
    """형식을 못 박지 않으면 곡은 좋은데 프로그램이 못 읽는다."""
    brief = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    for key in ("\"measures\"", "\"plan\"", "\"motif\"", "\"critic\"", "\"pitches\"", "\"dur\""):
        assert key in brief, f"돌려줄 형식에 {key} 가 없다"
    assert "```json" in brief, "예시를 코드블록으로 주지 않으면 형식이 어긋난다"


def test_an_unknown_tier_is_a_plain_message(client) -> None:
    assert client.post("/api/handoff/brief", json={"tier_id": "없는급수"}).status_code == 404


# ── 2. 받아온 곡도 같은 관문을 지난다 ──────────────────────────────────────


def test_a_good_piece_comes_in_and_costs_nothing(client, piece) -> None:
    r = client.post("/api/handoff/take-in", json=piece)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["cost_usd"] == 0.0, "대화창에서 만든 곡에 비용이 붙으면 안 된다"
    assert got["savable"] is True
    assert got["title"] == "달리는 손가락", "붙여 주신 제목이 곡의 이름이 되어야 한다"
    assert got["composition_id"] in STORE.compositions


def test_it_lands_where_everything_else_can_reach_it(client, piece) -> None:
    """**여기가 이 기능의 전부다.** 들어와도 곡집·꾸러미가 안 되면 의미가 없다."""
    cid = client.post("/api/handoff/take-in", json=piece).json()["composition_id"]
    for name, path in [
        ("악보", f"/api/compositions/{cid}/musicxml"),
        ("MIDI", f"/api/compositions/{cid}/midi"),
        ("품질 리포트", f"/api/compositions/{cid}/quality"),
        ("마디(편집)", f"/api/compositions/{cid}/measures"),
        ("표지", f"/api/compositions/{cid}/cover"),
        ("레슨용 악보", f"/api/compositions/{cid}/teaching"),
    ]:
        assert client.get(path).status_code == 200, f"{name} 를 못 만든다"
    # 연주 해설은 "누가 치는 곡인가" 를 알아야 쓸 수 있다 — 요청을 등록해 두지 않으면
    # 곡은 들어왔는데 해설만 안 나온다. 실제로 한 번 빠뜨렸다.
    assert client.post(f"/api/compositions/{cid}/guide").status_code == 200, (
        "요청이 저장소에 없다 — 해설이 안 나온다"
    )
    assert client.get("/api/compositions").json(), "보관함에 안 보인다"


def test_a_piece_that_fails_validation_is_not_saved(client, piece) -> None:
    """**밖에서 왔다고 문을 낮추지 않는다** (절대 규칙 2).

    마디 하나의 길이를 망가뜨려 놓는다. 이런 악보는 인쇄하면 마디가 어긋난다.
    """
    piece["measures"][3]["rh"][0]["events"].append(
        {"dur": 1.0, "pitches": ["C5"]}      # 4/4 인데 5박이 된다
    )
    r = client.post("/api/handoff/take-in", json=piece)
    assert r.status_code == 422
    assert not STORE.compositions, "검증에 떨어진 곡이 저장됐다"
    body = r.json()["detail"]
    assert body["issues"], "무엇이 걸렸는지 알려 주지 않으면 고칠 수가 없다"


def test_the_rejection_tells_the_owner_what_to_do_next(client, piece) -> None:
    """떨어뜨리기만 하고 길을 안 알려 주면 원장님은 거기서 멈추신다."""
    piece["measures"][2]["rh"][0]["events"][0]["pitches"] = ["C9"]   # 건반 밖
    r = client.post("/api/handoff/take-in", json=piece)
    assert r.status_code == 422
    what = r.json()["detail"]["what_to_do"]
    assert "대화창" in what and "비용" in what, (
        "고치는 길과 '돈이 안 든다' 는 사실을 함께 말해야 한다 — 원장님은 돈이 무섭다"
    )


def test_broken_measure_numbers_are_named_plainly(client, piece) -> None:
    """마디 번호가 빠진 것을 음악 오류로 말하면 원장님은 무슨 소린지 모르신다."""
    piece["measures"] = piece["measures"][:10]
    piece["measures"][5]["number"] = 99
    r = client.post("/api/handoff/take-in", json=piece)
    assert r.status_code == 422
    issues = " ".join(r.json()["detail"]["issues"])
    assert "마디 번호" in issues


def test_the_import_never_composes_anything_itself(client, piece) -> None:
    """**들이는 문이 작곡을 시작하면 그것은 다른 곡이다.**"""
    from app.handoff.receive import HandoffEngine
    from app.schemas.quality import CriticReport, RubricScores

    eng = HandoffEngine(CriticReport(
        scores=RubricScores(**dict.fromkeys(
            ("motif_development", "form_clarity", "harmony", "voice_leading", "phrasing",
             "climax_ending", "student_fit", "competition_effect", "notation", "originality"), 8)),
        overall_comment="",
    ))
    for call in (lambda: eng.motifs(None, 1), lambda: eng.plan(None, None),
                 lambda: eng.realize_phrase(None, None)):
        with pytest.raises(RuntimeError):
            call()


def test_the_imported_piece_joins_the_plagiarism_index(client, piece) -> None:
    """다음 곡이 이 곡과 겹치지 않으려면 등록돼 있어야 한다(§7.8)."""
    from app.api.corpus import get_corpus

    cid = client.post("/api/handoff/take-in", json=piece).json()["composition_id"]
    assert f"gen-{cid}" in get_corpus().scores, "표절 인덱스에 안 들어갔다"


def test_spending_is_untouched_by_a_handoff_piece(client, piece) -> None:
    """비용 화면에 없던 돈이 생기면 원장님이 또 놀라신다."""
    before = client.get("/api/spending").json()["total_usd"]
    client.post("/api/handoff/take-in", json=piece)
    assert client.get("/api/spending").json()["total_usd"] == before


# ── 3. 화면이 실제로 그 길을 열어 준다 ─────────────────────────────────────


def test_the_screen_has_both_steps() -> None:
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_text(encoding="utf-8")
    assert "btnHoBrief" in page and "의뢰서 만들기" in page
    assert "btnHoTake" in page and "받아온 곡 넣기" in page
    # 대화창은 설명을 곁들여 답한다. "JSON 만 남기고 지우세요" 는 컴맹 원장께 할 말이 아니다.
    assert "function pickJson" in page, "코드블록만 골라 읽지 않는다"
    assert "비용 $0" in page, "돈이 안 든다는 사실이 화면에 없다"
