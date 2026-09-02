"""막혔을 때 화면이 **말을 해야** 하고, 만든 곡은 **눈에 보여야** 한다.

원장이 곡을 만들다 26초쯤에 멈췄고, 화면에는 `{}` 두 글자만 남았다. 무엇이 잘못됐는지도
다음에 뭘 할지도 알 수 없는 화면이다. 게다가 그 뒤로는 아무것도 눌리지 않았다.

원인은 둘이었다.
1. 처리하지 못한 예외가 나면 Starlette 는 **평문** "Internal Server Error" 를 돌려준다.
   화면은 JSON 을 기다리므로 읽지 못하고 `{}` 만 남는다.
2. 만든 곡은 저장 파일 하나 안에 들어 있어 프로그램을 켜야만 보인다. 탐색기에서
   눈으로 확인할 길이 없었다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.api.deps import STORE
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    for bucket in (STORE.students, STORE.compositions, STORE.books, STORE.judgements,
                   STORE.rights, STORE.versions, STORE.requests, STORE.plans, STORE.motifs):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app, raise_server_exceptions=False,
                    client=("127.0.0.1", 51000)) as c:
        yield c
    get_settings.cache_clear()


def test_an_unhandled_error_speaks_korean_not_braces(client, monkeypatch) -> None:
    """`{}` 앞에서는 원장이 할 수 있는 일이 없다."""
    from app.api import studio

    def boom(*a, **k):
        raise RuntimeError("일부러 낸 오류")

    monkeypatch.setattr(studio, "run_auto", boom)

    r = client.post("/api/compositions/market", json={"tier_id": "middle"})
    assert r.status_code == 500
    body = r.json()
    d = body.get("detail")
    assert isinstance(d, dict), f"화면이 읽을 수 없는 응답이다: {r.text[:200]}"
    assert d["message"] and "오류" in d["message"]
    assert d["what_to_do"], "다음에 무엇을 할지 말해 주지 않는다"
    assert any("오류 표시" in str(i) for i in d["issues"]), "어느 오류인지 짚을 표가 없다"


def test_the_traceback_is_written_down_for_us(client, monkeypatch, tmp_path: Path) -> None:
    """원장은 화면을 사진으로 찍어 보낸다 — 우리가 볼 자국은 파일에 남아야 한다."""
    from app.api import studio

    monkeypatch.setattr(
        studio, "run_auto", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("자국 남기기"))
    )
    client.post("/api/compositions/market", json={"tier_id": "middle"})

    book = tmp_path / "오류기록.txt"
    assert book.exists(), "오류 자국이 아무 데도 안 남았다"
    text = book.read_text(encoding="utf-8")
    assert "자국 남기기" in text and "Traceback" in text


def test_made_pieces_can_be_pulled_out_as_files(client, tmp_path: Path) -> None:
    """만든 곡이 저장 파일 안에만 있으면 탐색기에서 눈으로 찾을 수 없다."""
    client.post("/api/compositions/market", json={"tier_id": "beginner"})

    r = client.post("/api/export-all")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["made"], "한 곡도 꺼내지 못했다"

    folder = Path(out["folder"])
    assert folder.exists()
    piece = next(folder.iterdir())
    names = {f.name for f in piece.iterdir()}
    assert any(n.endswith(".musicxml") and "지도용" not in n for n in names), names
    assert any("지도용" in n for n in names), "지도용 악보가 빠졌다"
    assert any(n.endswith((".mp3", ".wav")) for n in names), "음원이 빠졌다"
    assert any(n.endswith(".mid") for n in names), "MIDI 가 빠졌다"
    assert "읽어보세요.txt" in names


def test_exporting_twice_does_not_redo_the_work(client) -> None:
    """이미 꺼내 둔 곡을 다시 만들지 않는다 — 곡이 쌓이면 그것만으로 오래 걸린다."""
    client.post("/api/compositions/market", json={"tier_id": "beginner"})
    first = client.post("/api/export-all").json()
    again = client.post("/api/export-all").json()
    assert again["made"] == [] and again["skipped"] == first["made"]


def test_exporting_with_no_pieces_says_so(client) -> None:
    r = client.post("/api/export-all")
    assert r.status_code == 409
    assert "없습니다" in json.dumps(r.json(), ensure_ascii=False)


def test_folders_only_open_on_this_pc(tmp_path: Path, monkeypatch) -> None:
    """원격에서 남의 폴더를 열게 할 수는 없다."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app, client=("10.0.0.9", 5000)) as c:
        assert c.post("/api/open-folder").status_code == 403
    get_settings.cache_clear()


def test_an_unknown_folder_is_refused(client) -> None:
    assert client.post("/api/open-folder?which=없는곳").status_code == 404
