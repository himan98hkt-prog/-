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


# ── 4. 의뢰서의 본보기는 **진짜 스키마**여야 한다 ──────────────────────────
#
# 여기가 어긋나면 가장 나쁜 실패가 난다. 곡은 좋은데 프로그램이 못 읽는다.
# 원장님은 시간을 다 쓰고 "또 안 되네" 를 겪으신다. 실제로 한 번 그랬다 —
# 의뢰서가 `plan.sections` 와 `motif.pitches` 라는, **존재하지 않는 모양**을
# 가르치고 있었다.


def test_the_example_in_the_brief_is_the_real_schema() -> None:
    """본보기를 그대로 따라 만들면 반드시 읽혀야 한다."""
    import json

    from app.handoff.example import example_json, example_measure_json
    from app.schemas.music import CompositionPlan, Measure, MotifCandidate
    from app.schemas.quality import CriticReport

    body = json.loads(example_json())
    CompositionPlan(**body["plan"])       # 여기서 터지면 의뢰서가 거짓을 가르치고 있다
    MotifCandidate(**body["motif"])
    CriticReport(**body["critic"])
    Measure(**json.loads(example_measure_json()))
    assert body["title"], "제목 자리를 안 보여 준다"


def test_every_code_block_in_the_brief_is_real_json(client) -> None:
    """코드블록이 하나라도 깨져 있으면 그대로 베껴 쓴 답이 거절된다."""
    import json
    import re

    brief = client.post("/api/handoff/brief",
                        json={"tier_id": "middle", "preset_id": "toccata"}).json()["brief"]
    blocks = re.findall(r"```json\n(.*?)\n```", brief, re.S)
    assert len(blocks) >= 2, "본보기 코드블록이 없다"
    for b in blocks:
        json.loads(b)


def test_the_brief_never_teaches_a_name_that_does_not_exist(client) -> None:
    """스키마에 없는 이름을 가르치면 그 곡은 통째로 거절된다."""
    brief = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    for ghost in ('"sections"', '"climax_measure"', '"rhythm"'):
        assert ghost not in brief, f"의뢰서가 없는 이름 {ghost} 를 가르친다"
    # 반대로 반드시 있어야 하는 것들
    for real in ('"duration_est"', '"climax"', '"ending"', '"difficulty_target"',
                 '"character_label"'):
        assert real in brief, f"의뢰서에 꼭 필요한 {real} 가 없다"


# ── 5. 프로그램의 중심이 옮겨졌다 ─────────────────────────────────────────
#
# 원장님: "이제는 비용이 들어가면서 제작하는 것은 최대한 자제할 것 같아.
#          이것은 숨켜져 있다가 버튼을 클릭하면 나타나지게하는 형태로 바꿔줘
#          ... 이 프로그램의 중심은 ... 프롬프트 만들어지고 ... 업로드 하는 형태"


def test_the_paid_path_is_folded_away_by_default() -> None:
    """돈이 드는 길이 먼저 눈에 띄면 원장님은 또 그것을 누르신다."""
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="apiFold"' in page and "<details" in page, "비용 드는 길이 접혀 있지 않다"
    assert "곡마다 돈이 듭니다" in page, "펼치기 전에 비용을 말하지 않는다"
    # 접었다고 기능을 없애면 안 된다 — 언젠가 쓰실 수 있고, 없애면 되돌리기 어렵다.
    assert "function layoutDashboard" in page
    for kept in ("secBudget", "paneMarket", "paneStudent", "secPresets"):
        assert kept in page, f"{kept} 가 사라졌다 — 접는 것과 없애는 것은 다르다"


def test_the_free_path_stands_first() -> None:
    """의뢰서와 곡 넣기가 화면 위에 있어야 한다."""
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_text(encoding="utf-8")
    order = page.index('"secHandoff"'), page.index('id="apiFold"')
    # layoutDashboard 의 차례표에서 secHandoff 가 apiFold 보다 앞이어야 한다.
    lay = page[page.index("function layoutDashboard"):]
    lay = lay[:lay.index("\n}")]
    assert lay.index("secHandoff") < lay.index("secLibrary") < lay.index("secBooks"), (
        "의뢰서 → 만든 곡 → 곡집 차례가 아니다"
    )
    assert "appendChild(foldBox)" in lay, "비용 드는 길이 맨 아래로 가지 않는다"
    assert order  # 두 구역 모두 존재


def test_the_owner_picks_differentiation_instead_of_writing_it(client) -> None:
    """**"차별화" 를 원장님이 글로 지어내시게 하면 안 된다.** 그건 작곡가의 언어다."""
    d = client.get("/api/handoff/wishes").json()
    assert len(d["wishes"]) >= 10, "고르실 것이 너무 적다"
    assert d["groups"], "묶음이 없으면 목록이 길어 못 고르신다"
    for w in d["wishes"]:
        assert w["name"] and w["blurb"], "왜 점수가 되는지 안 적혀 있다"


def test_a_picked_wish_becomes_a_concrete_instruction(client) -> None:
    """"인상적으로" 같은 말은 아무 지시도 아니다. 무엇을 하라가 적혀야 한다."""
    plain = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    rich = client.post("/api/handoff/brief", json={
        "tier_id": "middle", "wish_ids": ["hand_swap", "one_peak"],
    }).json()["brief"]
    assert len(rich) > len(plain), "고른 것이 의뢰서에 들어가지 않았다"
    assert "왼손과 오른손의 역할을 통째로 바꾸십시오" in rich
    assert "최고음이 클라이맥스 한 마디에만" in rich


def test_what_to_avoid_and_the_key_reach_the_brief(client) -> None:
    b = client.post("/api/handoff/brief", json={
        "tier_id": "middle", "avoid": "너무 어두운 화성", "key_pref": "A",
    }).json()["brief"]
    assert "너무 어두운 화성" in b and "피해" in b
    assert "조성은 A 로" in b


def test_reference_scores_never_leak_notes(client) -> None:
    """참고 악보는 **통계만** 나간다(절대 규칙 3). 음표열이 새면 저작권 사고다."""
    import inspect

    from app.api.corpus import get_corpus
    from app.api.handoff import _reference_flavour

    # 참고 악보에서 뽑는 값은 조성·박자·빠르기·마디 수뿐이다. 음표를 만지면 안 된다.
    src = inspect.getsource(_reference_flavour)
    for forbidden in ("measures_data", "all_pitches", "notes", "ngram", "events"):
        assert forbidden not in src, f"참고 악보에서 {forbidden} 를 꺼내고 있다"
    assert "profile" in src, "성향(StyleProfile) 이 아닌 것을 보고 있다"

    # 코퍼스가 비어 있어도 터지지 않아야 한다.
    assert isinstance(_reference_flavour(), list)
    assert get_corpus() is not None

    b = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "use_references": True}).json()["brief"]
    assert "옮겨 적지 마십시오" in b, "표절 경고가 의뢰서에서 사라졌다"


# ── 6. 밋밋한 곡을 미리 막는다 ────────────────────────────────────────────
#
# 원장님: "악보 및 곡이 토카타가 아닌데.. 다 엉망으로 나와"
#
# 실제로 그랬다. 내가 무늬 하나를 만들어 화성 따라 조옮김만 한 곡을 드렸다.
# 검증기와 음악성 지표는 통과했다(9.61). 지표는 "같은 마디가 열네 번" 을 듣지 못한다.
# 58마디에 리듬 생김새가 11가지뿐이었고, 가운데 열여섯 마디는 오른손이 4분음표였다 —
# 토카타에서 달리기가 멈추면 그것은 토카타가 아니다.
#
# 지표가 못 듣는 것은 **의뢰서가 미리 말해야** 한다.


def test_the_brief_forbids_stamping_one_figure_through_the_whole_piece(client) -> None:
    b = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    assert "무늬를 여덟 가지 이상" in b, "한 무늬로 곡 전체를 찍어 내는 것을 막지 않는다"
    assert "조옮김만 하면" in b, "왜 안 되는지 말해 주지 않으면 또 그렇게 만들어 온다"
    assert "마디를 하나씩 직접" in b, "기계적으로 찍어 내지 말라는 말이 없다"


def test_a_toccata_brief_says_the_running_must_not_stop(client) -> None:
    """성격마다 그 성격이 무너지는 자리가 다르다. 토카타는 달리기가 멈추는 것이다."""
    b = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "toccata"}).json()["brief"]
    assert "달리기가 멈추면" in b
    assert "왼손이 선율을 맡고 오른손이 계속 구르게" in b, (
        "역할을 바꾸는 올바른 방법을 알려 주지 않으면 가운데가 찬송가가 된다"
    )
    # 토카타가 아닌 성격에는 이 말이 붙지 않아야 한다 — 아무 데나 붙는 경고는 안 읽힌다.
    other = client.post("/api/handoff/brief",
                        json={"tier_id": "middle", "preset_id": "nocturne"}).json()["brief"]
    assert "달리기가 멈추면" not in other


# ── 7. 의뢰서가 성격을 **제대로** 설명한다 ────────────────────────────────
#
# 원장님: "프로그램에서 알려준 프롬프트로 만든것이 하나도 토카타 스럽지 않고 곡도 이상해..
#          프롬프트가 도데체 어떻게 되어 있는거야."
#
# 보니 토카타에 대해 하는 말이 이게 전부였다:
#     - 토카타 — 쉬지 않고 달리는 16분음표. 손가락이 강점일 때
#     - 이 성격이 드러내는 것: 손가락 속도, 화려한 스케일, 지구력
# 이것으로는 토카타를 쓸 수 없다. **무엇을 하라는 말이 없다.**


def test_the_brief_never_says_it_is_up_to_you_when_a_character_was_chosen(client) -> None:
    """**성격을 골라 놓고 "성격은 맡깁니다" 라고 하면 아무 곡이나 온다.**

    조성 지정과 성격 지정을 if/else 로 묶어 둔 탓에, 조성을 안 고르시면 토카타를
    골라 놓고도 이 줄이 붙었다. 원장님이 겪으신 일의 절반이 이것이다.
    """
    picked = client.post("/api/handoff/brief",
                         json={"tier_id": "middle", "preset_id": "toccata"}).json()["brief"]
    assert "성격은 맡깁니다" not in picked, "성격을 골랐는데 맡긴다고 한다"
    # 조성을 함께 골라도 마찬가지여야 한다.
    both = client.post("/api/handoff/brief",
                       json={"tier_id": "middle", "preset_id": "toccata", "key_pref": "A"}).json()["brief"]
    assert "성격은 맡깁니다" not in both
    assert "조성은 A 로" in both
    # 정말로 안 고르셨을 때만 나온다.
    free = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    assert "성격은 맡깁니다" in free


def test_every_character_tells_the_composer_what_the_hands_do(client) -> None:
    """프리셋 값만 옮겨 적는 것은 설명이 아니다. 손이 무엇을 하는지 적혀야 한다."""
    from app.generation.presets import PRESETS
    from app.handoff.character import CHARACTER

    for p in PRESETS:
        assert p.id in CHARACTER, f"{p.name} 에 '이런 곡입니다' 가 없다"
        what, how, breaks = CHARACTER[p.id]
        assert len(what) > 40, f"{p.name} 설명이 너무 짧다"
        assert len(how) >= 3, f"{p.name} 에 '이렇게 쓰십시오' 가 {len(how)}줄뿐이다"
        assert breaks, f"{p.name} 에 '이러면 무너집니다' 가 없다"

    b = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "toccata"}).json()["brief"]
    assert "토카타는 이런 곡입니다" in b
    assert "양손 교대를 반드시 한 번은" in b, "토카타의 얼굴을 안 알려 준다"
    assert "찬송가가 됩니다" in b, "가운데에서 무너지는 자리를 안 알려 준다"


def test_the_brief_says_exactly_what_to_hand_back(client) -> None:
    """원장님: "어떤 문서를 만들어 달라고 해야 정확하게 프로그램에서 인식이 될까?"

    따로 부탁하실 것이 없어야 맞다 — 의뢰서가 스스로 말해야 한다.
    """
    b = client.post("/api/handoff/brief", json={"tier_id": "middle"}).json()["brief"]
    assert "돌려주실 것" in b
    assert ".json" in b, "파일 형식을 말해 주지 않는다"
    assert "프로그램이 이 JSON 하나로 다 만듭니다" in b, (
        "악보·MP3·해설을 따로 부탁해야 하는 줄 아신다"
    )


# ── 8. 고르신 것이 **의뢰서에 보여야** 한다 ────────────────────────────────
#
# 원장님: "지금 원장 세부 요청사항도 전혀 반영되지 않았고, 그냥 최초 프롬프트가
#          그대로 반영되는 것 같아.. 버튼을 클릭함에 따른 내용들이 반영되어야 하는데"
#
# 반영은 되고 있었다. 다만 **의뢰서 어디에도 "당신이 이렇게 고르셨습니다" 가 없었다.**
# 눈으로 확인할 수 없으면 반영되지 않은 것과 같다.


def test_the_brief_shows_back_what_the_owner_chose(client) -> None:
    b = client.post("/api/handoff/brief", json={
        "tier_id": "middle", "preset_id": "toccata", "key_pref": "E",
        "wish_ids": ["odd_rhythm", "hand_swap"],
        "wish": "왼손은 단순하게", "avoid": "옥타브 도약",
    }).json()["brief"]
    head = b[:600]
    assert "원장님이 고르신 것" in head, "고르신 것을 되짚어 주지 않는다"
    for must in ("중급", "토카타", "E", "2개"):
        assert must in head, f"머리말에 {must} 가 없다"
    # 고른 항목 이름도 그대로 보여야 한다.
    assert "처음 듣는 리듬꼴로 시작한다" in head
    assert "중간에 손 역할을 뒤집는다" in head


def test_every_single_wish_reaches_the_brief(client) -> None:
    """**하나라도 새면 원장님은 '반영이 안 된다' 고 느끼신다.** 열네 개를 다 확인한다."""
    from app.handoff.wishes import WISHES

    for w in WISHES:
        b = client.post("/api/handoff/brief", json={
            "tier_id": "middle", "preset_id": "toccata", "wish_ids": [w.id],
        }).json()["brief"]
        assert w.tell in b, f"'{w.name}' 를 골랐는데 의뢰서에 지시가 없다"
        assert w.name in b[:600], f"'{w.name}' 가 머리말에 안 보인다"


def test_changing_the_character_changes_the_whole_description(client) -> None:
    """성격을 바꿨는데 설명이 그대로면 '최초 프롬프트가 그대로' 로 보인다."""
    t = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "toccata"}).json()["brief"]
    n = client.post("/api/handoff/brief",
                    json={"tier_id": "middle", "preset_id": "nocturne"}).json()["brief"]
    assert "손가락이 쉬지 않고 구르는" in t and "손가락이 쉬지 않고 구르는" not in n
    assert "밤의 노래입니다" in n and "밤의 노래입니다" not in t


def test_korean_particles_are_right() -> None:
    """"행진곡는" 처럼 적히면 원장님은 그것을 '대충 만든 것' 으로 읽으신다."""
    from app.handoff.brief import eun_neun

    assert eun_neun("토카타") == "는"      # 받침 없음
    assert eun_neun("행진곡") == "은"      # 받침 있음
    assert eun_neun("야상곡풍") == "은"
    assert eun_neun("") == "는"


def test_no_character_name_reads_wrong_in_any_brief(client) -> None:
    from app.generation.presets import PRESETS

    for p in PRESETS:
        b = client.post("/api/handoff/brief",
                        json={"tier_id": "middle", "preset_id": p.id}).json()["brief"]
        assert f"{p.name}는 이런 곡입니다" in b or f"{p.name}은 이런 곡입니다" in b, (
            f"{p.name} 의 '이런 곡입니다' 가 없다"
        )
