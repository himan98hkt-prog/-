"""§6.1 코퍼스 · §7.1 StyleProfile · §7.8 RAG 검색 · 저작권 정책."""
from __future__ import annotations

import pytest
from app.analysis.style_profile import cosine, extract
from app.api.corpus import CORPUS
from app.api.deps import STORE
from app.generation.assemble import AssembleOptions, measures_to_musicxml
from app.ingest.corpus import Corpus
from app.ingest.parse import UnsupportedScore, parse_score
from app.main import app
from app.schemas.music import Measure, ScoreEvent, Voice
from fastapi.testclient import TestClient


def _piece(top: list[str], lh: str = "C3", n: int = 8) -> list[Measure]:
    return [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in top])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=[lh])])],
        )
        for i in range(1, n + 1)
    ]


# ── StyleProfile ─────────────────────────────────────────────────────────


def test_style_profile_captures_hand_ranges_and_density():
    sp = extract(_piece(["C5", "D5", "E5", "G5"]), key="C", meter="4/4", tempo=96)
    assert sp.measures == 8
    assert sp.rh.density == 4.0 and sp.lh.density == 1.0
    assert sp.rh.lowest == 72 and sp.rh.highest == 79
    assert sp.rhythm_vocab == [1.0, 4.0]
    assert 1.0 <= sp.difficulty_score <= 10.0
    assert len(sp.vector()) == len(sp.VECTOR_KEYS)


def test_similar_pieces_score_higher_than_different_ones():
    easy = extract(_piece(["C5", "D5", "E5", "F5"]), tempo=80)
    easy2 = extract(_piece(["C5", "D5", "E5", "G5"]), tempo=84)
    busy = extract(
        [
            Measure(
                number=i,
                rh=[Voice(events=[ScoreEvent(dur=0.25, pitches=["C6", "E6"]) for _ in range(16)])],
                lh=[Voice(events=[ScoreEvent(dur=0.5, pitches=["C2"]) for _ in range(8)])],
            )
            for i in range(1, 9)
        ],
        tempo=176,
    )
    same = cosine(easy.vector(), easy2.vector())
    other = cosine(easy.vector(), busy.vector())
    assert same > other, f"비슷한 곡 {same:.3f} vs 다른 곡 {other:.3f}"


# ── 파싱 ─────────────────────────────────────────────────────────────────


def test_musicxml_round_trip_preserves_measures(tmp_path):
    original = _piece(["C5", "D5", "E5", "G5"])
    path = tmp_path / "a.musicxml"
    path.write_text(measures_to_musicxml(original, AssembleOptions()), encoding="utf-8")
    back, meta = parse_score(path)
    assert len(back) == len(original)
    assert meta["meter"] == "4/4"
    for m in back:
        for v in (*m.rh, *m.lh):
            assert abs(sum(e.dur for e in v.events) - 4.0) < 1e-6, "마디 길이가 보존돼야 한다"


def test_unsupported_format_is_rejected(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(UnsupportedScore):
        parse_score(p)


# ── 저작권 정책 (절대 규칙 3) ────────────────────────────────────────────


def test_copyrighted_scores_never_store_their_notes():
    c = Corpus()
    c.add(_piece(["C5", "D5", "E5", "G5"]), score_id="pd", title="공유", copyright_status="public_domain")
    c.add(_piece(["C5", "D5", "E5", "G5"]), score_id="cr", title="저작권", copyright_status="copyrighted")
    assert c.scores["pd"].measures is not None
    assert c.scores["cr"].measures is None, "음표열을 애초에 보관하지 않는다"
    # 통계는 남는다 — 스타일 학습은 계속 가능해야 한다.
    assert c.scores["cr"].profile.difficulty_score > 0
    entry = c.scores["cr"].to_entry()
    assert entry.excerpt_measures is None


def test_copyrighted_scores_still_count_for_plagiarism():
    """음표열을 내보내지 않으면서도 '베끼지 않았는지' 는 검사해야 한다."""
    from app.analysis.ngram import find_plagiarism
    from app.analysis.pitch import midi_to_pitch

    line = [midi_to_pitch(60 + (i * 7) % 13) for i in range(80)]
    piece = [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p])
                              for p in line[(i - 1) * 4:(i - 1) * 4 + 4]])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])],
        )
        for i in range(1, 21)
    ]
    c = Corpus()
    c.add(piece, score_id="cr", title="저작권곡", copyright_status="copyrighted")
    assert c.scores["cr"].measures is None
    assert find_plagiarism(piece, c.ngram_index()), "표절 검사는 저작권곡에도 걸려야 한다"


# ── 검색 ─────────────────────────────────────────────────────────────────


def test_search_filters_by_difficulty_and_pins_requested_scores():
    from app.analysis.style_profile import StyleProfile

    c = Corpus()
    c.add(_piece(["C5", "D5", "E5", "F5"]), score_id="easy", title="쉬움", tempo=72)
    c.add(
        [
            Measure(
                number=i,
                rh=[Voice(events=[ScoreEvent(dur=0.25, pitches=["C6", "E6"]) for _ in range(16)])],
                lh=[Voice(events=[ScoreEvent(dur=0.5, pitches=["C2"]) for _ in range(8)])],
            )
            for i in range(1, 9)
        ],
        score_id="hard", title="어려움", tempo=168,
    )
    target = StyleProfile(key="C", meter="4/4", tempo=76, difficulty_score=2.5)
    results = c.search(target, difficulty=2.5)
    assert results
    assert results[0][0].id == "easy"

    pinned = c.search(target, difficulty=2.5, pinned_ids=["hard"])
    assert pinned[0][0].id == "hard", "원장이 지정한 곡은 항상 포함된다(§7.8)"


def test_search_falls_back_when_difficulty_filter_empties_the_pool():
    from app.analysis.style_profile import StyleProfile

    c = Corpus()
    c.add(_piece(["C5", "D5", "E5", "F5"]), score_id="only", title="유일", tempo=72)
    target = StyleProfile(key="C", meter="4/4", tempo=180, difficulty_score=9.5)
    assert c.search(target, difficulty=9.5), "빈 컨텍스트보다는 덜 맞는 참고곡이 낫다"


# ── API ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    CORPUS.scores.clear()
    CORPUS._ngrams.clear()
    for bucket in (STORE.requests, STORE.motifs, STORE.plans, STORE.compositions):
        bucket.clear()
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


def _upload(client, tmp_path, name: str, status: str, top: list[str]):
    path = tmp_path / f"{name}.musicxml"
    path.write_text(measures_to_musicxml(_piece(top), AssembleOptions()), encoding="utf-8")
    with path.open("rb") as f:
        return client.post(
            "/api/corpus",
            files={"file": (path.name, f.read())},
            data={"title": name, "copyright_status": status, "division_tags": "초등 저학년부"},
        )


def test_upload_extracts_a_profile_and_respects_copyright(client, tmp_path):
    pd = _upload(client, tmp_path, "공유곡", "public_domain", ["C5", "D5", "E5", "G5"])
    cr = _upload(client, tmp_path, "저작권곡", "copyrighted", ["C5", "E5", "G5", "C6"])
    assert pd.status_code == 200 and cr.status_code == 200
    assert pd.json()["has_notes"] is True
    assert cr.json()["has_notes"] is False
    assert pd.json()["difficulty"] > 0

    listed = client.get("/api/corpus").json()
    assert len(listed) == 2

    profile = client.get(f"/api/corpus/{pd.json()['id']}/profile")
    assert profile.status_code == 200
    assert profile.json()["vector"]


def test_corpus_reaches_the_composer_context(client, tmp_path, student):
    _upload(client, tmp_path, "참고곡", "public_domain", ["C5", "D5", "E5", "G5"])
    payload = {
        "id": "", "student": student.model_dump(mode="json"), "competition": None,
        "target_difficulty": 3.0, "mood": "밝은", "form": "ABA", "key_preference": ["C"],
        "meter": "4/4", "tempo": 96, "total_measures": 32,
        "reference_style_ids": [], "texture_options": [], "must_include": "", "n_candidates": 1,
    }
    rid = client.post("/api/requests", json=payload).json()["request_id"]

    found = client.post(f"/api/corpus/search?request_id={rid}")
    assert found.status_code == 200, found.text
    assert found.json(), "요청에 붙는 참고곡이 보여야 한다"

    from app.api.compositions import _ctx

    ctx = _ctx(STORE, rid)
    assert ctx.style_context, "Stage 0 컨텍스트에 코퍼스가 실려야 한다(차별점 #2)"
    assert "style_profile" in ctx.style_context[0]
    ctx.prompt_payload()   # 저작권 가드 통과


def test_delete_removes_from_index(client, tmp_path):
    r = _upload(client, tmp_path, "삭제할곡", "public_domain", ["C5", "D5", "E5", "G5"])
    sid = r.json()["id"]
    assert client.delete(f"/api/corpus/{sid}").status_code == 200
    assert client.get("/api/corpus").json() == []
    assert client.delete(f"/api/corpus/{sid}").status_code == 404
