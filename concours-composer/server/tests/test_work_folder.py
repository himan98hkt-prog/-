"""**곡을 어느 폴더에 쌓을지 원장님이 정하신다.**

원장님:

    "클로드에 만들고 다운받은 곡에 대한 전체 내용들을 저장할 수 있는
     폴더 설정도 할 수 있었으면 좋겠어."
    "실질적인 작곡 작업은 집pc로 진행할 계획이니 프로그램 자체를 다운 받아서
     같이 이용할 수 있게..."

집 PC 와 학원 PC 를 오가시려면 곡이 **파일로** 있어야 하고, 그 자리를 원장님이
고르실 수 있어야 한다(동기화 폴더·USB). 다만 아무 데나는 안 된다 — 프로그램 폴더
안은 새 판을 받을 때 덮어쓰이므로 거기 두면 갱신 한 번에 곡이 사라진다.
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
    # 폴더를 정하는 문은 **이 PC 에서만** 열린다. 테스트도 그 문으로 들어가야
    # 실제와 같은 길을 지난다 — TestClient 는 기본이 'testclient' 라는 가짜 호스트다.
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c


def test_the_default_is_a_real_place(client) -> None:
    f = client.get("/api/folder").json()
    assert f["is_default"] is True
    assert f["path"] and f["path"] == f["default_path"]


def test_the_owner_can_choose_a_folder(client, tmp_path) -> None:
    d = tmp_path / "원드라이브" / "콩쿨곡"
    f = client.put("/api/folder", json={"path": str(d)}).json()
    assert f["is_default"] is False
    assert f["path"] == str(d.resolve())
    assert d.exists(), "정한 자리를 만들어 두지 않으면 첫 곡에서 실패한다"


def test_the_program_folder_is_refused(client) -> None:
    """**여기에 두면 갱신 한 번에 곡이 사라진다.** 고치려던 바로 그 사고다."""
    from app.config import ROOT

    r = client.put("/api/folder", json={"path": str(ROOT / "내곡")})
    assert r.status_code == 422
    what = r.json()["detail"]["what_to_do"]
    assert "덮어쓰" in what and "사라" in what, "왜 안 되는지 말해 주지 않으면 원장님은 우기신다"


def test_a_folder_it_cannot_write_to_is_refused_at_the_time_of_choosing(client, tmp_path) -> None:
    """정해 놓고 나중에 못 쓰면, 그때는 곡을 꺼내려다 실패한다. 정하실 때 써 본다.

    권한이 아니라 **파일 밑을 폴더로 삼으려는** 경우로 시험한다 — 권한은 관리자
    계정에서 통과해 버려서 시험이 되지 않는다(테스트가 root 로 돈다).
    """
    afile = tmp_path / "이건파일.txt"
    afile.write_text("나는 폴더가 아니다", encoding="utf-8")
    r = client.put("/api/folder", json={"path": str(afile / "안쪽")})
    assert r.status_code == 422
    assert "쓸 수 없" in r.json()["detail"]["what_to_do"]


def test_going_back_to_the_default_works(client, tmp_path) -> None:
    client.put("/api/folder", json={"path": str(tmp_path / "어디")})
    f = client.put("/api/folder", json={"path": ""}).json()
    assert f["is_default"] is True


def test_a_folder_that_went_away_does_not_break_anything(client, tmp_path) -> None:
    """**USB 를 빼셨을 때 곡을 못 만들면 안 된다.**

    정하신 자리를 못 쓰게 되면 조용히 원래 자리로 물러나고, 그 사실을 화면에 알린다.
    """
    from app.api.folder import chosen_dir, default_dir

    gone = tmp_path / "USB" / "곡"
    client.put("/api/folder", json={"path": str(gone)})
    assert str(chosen_dir()) == str(gone), "정한 자리를 안 쓴다"

    # 드라이브가 사라진 셈 — 그 자리에 이제 폴더를 만들 수 없다.
    gone.rmdir()
    gone.write_text("이제 폴더가 아니다", encoding="utf-8")

    assert str(chosen_dir()) == str(default_dir()), "물러나지 않으면 곡을 못 꺼낸다"
    assert client.get("/api/folder").json()["fell_back"] is True, "물러난 사실을 안 알린다"


def test_the_setting_survives_a_restart(client, tmp_path) -> None:
    """껐다 켜면 원래대로 돌아가면 정할 이유가 없다."""
    from app.api.deps import PERSISTED
    from app.api.folder import KEY

    client.put("/api/folder", json={"path": str(tmp_path / "쭉")})
    assert "jobs" in PERSISTED and KEY in STORE.jobs


# ── 들인 곡이 그 폴더에 실제로 풀리는가 ────────────────────────────────────


@pytest.fixture
def piece():
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
        key_preference=list(p.keys), meter=p.meter, tempo=p.tempo[0])
    ctx = build_context(req)
    pipe = CompositionPipeline(StubComposerEngine(), progress=lambda *_: None)
    res = pipe.compose_candidates(ctx, pipe.motifs(ctx, 1)[0], None, n=1)[0]
    return {
        "tier_id": "middle", "preset_id": "toccata", "title": "달리는 손가락",
        "plan": json.loads(res.plan.model_dump_json()),
        "motif": json.loads(res.motif.model_dump_json()),
        "measures": [json.loads(m.model_dump_json()) for m in res.measures],
        "critic": {"scores": dict.fromkeys(
            ("motif_development", "form_clarity", "harmony", "voice_leading", "phrasing",
             "climax_ending", "student_fit", "competition_effect", "notation", "originality"), 8),
            "overall_comment": "형식이 뚜렷하다."},
    }


def test_a_piece_lands_in_the_chosen_folder_as_real_files(client, piece, tmp_path) -> None:
    """**저장 파일 안에만 있으면 프로그램을 켜야 보인다.** 탐색기에서 보여야 한다."""
    d = tmp_path / "내 콩쿨곡"
    client.put("/api/folder", json={"path": str(d)})
    got = client.post("/api/handoff/take-in", json=piece).json()
    assert got["folder"], "어느 폴더에 풀렸는지 알려 주지 않는다"

    from pathlib import Path

    made = Path(got["folder"])
    assert made.parent == d.resolve(), f"정하신 자리가 아니라 {made.parent} 에 떨어졌다"
    names = {p.name for p in made.iterdir()}
    got_kinds = {p.suffix for p in made.iterdir()}
    for suffix, what in [(".musicxml", "악보"), (".mid", "MIDI")]:
        assert suffix in got_kinds, f"{what} 가 폴더에 없다: {sorted(names)}"
    assert any(n.endswith((".wav", ".mp3")) for n in names), f"음원이 없다: {sorted(names)}"
    assert any(n.endswith(".md") or n.endswith(".txt") for n in names), "읽을 글이 없다"


def test_the_piece_is_kept_even_if_the_folder_fails(client, piece, tmp_path, monkeypatch) -> None:
    """**폴더에 못 풀었다고 곡을 잃으면 안 된다.** 곡은 이미 저장됐다."""
    def boom(*_a, **_k):
        raise OSError("디스크가 꽉 찼습니다")

    monkeypatch.setattr("app.handoff.spill.spill_to_folder", boom)
    r = client.post("/api/handoff/take-in", json=piece)
    assert r.status_code == 200, "폴더가 안 됐다고 곡까지 버렸다"
    assert r.json()["composition_id"] in STORE.compositions


def test_opening_and_exporting_use_the_chosen_folder(client, tmp_path) -> None:
    """화면이 말한 곳과 열리는 곳이 다르면 그것만으로 고장이다."""
    from pathlib import Path

    from app.api import health
    from app.api.folder import chosen_dir

    d = tmp_path / "여기다"
    client.put("/api/folder", json={"path": str(d)})
    assert Path(str(chosen_dir())) == d.resolve()

    src = (Path(health.__file__)).read_text(encoding="utf-8")
    i = src.index('"exports":')
    assert "chosen_dir()" in src[i:i + 120], "폴더 열기가 옛 자리를 연다"
    j = src.index("def export_all")
    assert "chosen_dir()" in src[j:j + 1600], "곡 꺼내기가 옛 자리에 쓴다"


def test_the_screen_lets_the_owner_set_it() -> None:
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_text(encoding="utf-8")
    assert "btnFldSave" in page and "곡을 쌓을 폴더" in page
    assert "프로그램 폴더 안은" in page, "왜 못 쓰는 자리가 있는지 미리 말하지 않는다"
    assert "주소창" in page, "경로를 어디서 얻는지 알려 주지 않으면 컴맹 원장은 막힌다"
