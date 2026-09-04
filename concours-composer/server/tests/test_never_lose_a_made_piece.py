"""곡을 다 만든 **뒤에** 넘어져도 곡은 남아야 한다.

원장님이 계속 겪고 계신 것이 이것이다 — "소비 비용은 엄청 나왔는데 결과물은 없다".

원인은 한 줄이었다. 저장 미들웨어가 `status_code < 400` 일 때만 디스크에 썼다.
그런데 작곡은 곡을 다 만들어 저장소에 넣은 **뒤에도** 할 일이 남아 있고(제목 짓기·
코퍼스 등록), 거기서 넘어지면 응답은 500 이 된다. 그러면 검증까지 통과한 곡이
디스크에 닿지 못하고, 껐다 켜는 순간 사라진다. 돈은 이미 나간 뒤다.

여기서 지키는 것:
  1. 뒷정리가 실패해도 곡은 파일에 남는가
  2. 그 사실을 화면이 말해 주는가 ("보관함을 먼저 보라")
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_a_finished_piece_survives_a_crash_in_the_cleanup_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """곡을 저장한 다음 단계에서 터뜨려 놓고, 파일에 남았는지 본다."""
    from app.api.deps import STORE
    from app.main import app

    # 앞선 검사가 남긴 곡이 있으면 다양성 규칙에 걸려 다른 이유로 막힌다 —
    # 여기서 보려는 것은 그것이 아니다.
    for bucket in (STORE.requests, STORE.motifs, STORE.plans, STORE.compositions,
                   STORE.versions, STORE.judgements):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus as _corpus

    _corpus().scores.clear()
    _corpus()._ngrams.clear()

    saves: list[int] = []
    monkeypatch.setattr(STORE, "save_soon", lambda: saves.append(len(STORE.compositions)))

    # 곡을 다 만든 뒤에 실행되는 자리에서 터뜨린다.
    from app.api import corpus as corpus_mod

    class Exploding:
        def register_generated(self, *a: object, **k: object) -> None:
            raise RuntimeError("뒷정리에서 넘어졌다")

        def ngram_index(self) -> None:
            return None

    boom = Exploding()
    monkeypatch.setattr(corpus_mod, "get_corpus", lambda: boom)

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post(
            "/api/compositions/market",
            json={"tier_id": "beginner", "preset_id": "march"},
        )

    # 뒷정리 실패는 곡을 버릴 이유가 아니다 — 곡은 나와야 한다.
    assert r.status_code == 200, f"뒷정리가 넘어졌다고 곡을 버렸다: {r.text[:300]}"
    assert r.json()["composition_id"]
    assert saves, "곡을 만들고도 저장을 예약하지 않았다 — 껐다 켜면 사라진다"


def test_even_a_500_writes_the_piece_to_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """응답이 오류여도 **곡이 늘었으면** 저장한다.

    예전에는 200 일 때만 저장했다. 그 한 줄이 원장님의 곡을 잃게 했다.
    """
    from app.api.deps import STORE
    from app.main import app

    saved: list[str] = []
    monkeypatch.setattr(STORE, "save_soon", lambda: saved.append("저장"))

    @app.post("/__test_made_then_boom")
    def _boom() -> None:
        STORE.compositions[f"comp-test-{len(STORE.compositions)}"] = object()
        raise RuntimeError("곡을 만든 뒤에 터졌다")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/__test_made_then_boom")

    assert r.status_code == 500
    assert saved, "오류로 끝났다고 방금 만든 곡을 디스크에 안 썼다"


def test_the_error_screen_says_the_piece_is_not_lost() -> None:
    """'오류' 라는 말만 보면 원장은 곡도 돈도 다 날아간 줄 안다."""
    from app.api.deps import STORE
    from app.main import app

    STORE.compositions["comp-살아있음"] = object()

    @app.post("/__test_boom_with_pieces")
    def _boom() -> None:
        raise RuntimeError("무언가 터졌다")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/__test_boom_with_pieces")

    what = r.json()["detail"]["what_to_do"]
    assert "보관함" in what, f"곡이 남아 있다는 말을 안 한다: {what}"
