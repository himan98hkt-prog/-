"""**한 곡이 정말 나오는가.** 원장님 물음 그대로다.

    "한곡이라도 만들어 낼 수 있는거야? 제발 제대로 한곡이 나올 수 있는지
     실측을 해보고 개선 및 오류 해결해줘."

진짜 API 키로 재 보는 것은 이 자리에서 할 수 없다(키는 원장님 PC .env 에만 있고
그래야 맞다). 대신 **모델이 실제로 주는 모양 그대로** 답하는 가짜 API 를 세워
파이프라인 끝까지 돌린다. 여태 곡을 잃은 자리는 전부 '모델이 준 값을 우리가 못
받아 낸' 자리였으므로, 그 모양만 정확하면 이 검사가 실제 실패를 잡는다.

특히 **조성을 "C major" 로 준다.** 원장님 곡을 죽인 바로 그 값이다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean():
    from app.api.corpus import get_corpus
    from app.api.deps import STORE

    for bucket in (STORE.requests, STORE.motifs, STORE.plans, STORE.compositions,
                   STORE.versions, STORE.judgements):
        bucket.clear()
    STORE.jobs.clear()
    get_corpus().scores.clear()
    get_corpus()._ngrams.clear()
    yield


def test_a_piece_comes_out_when_the_model_writes_keys_the_human_way(monkeypatch) -> None:
    """모델이 "C major" 라고 줘도 **곡이 끝까지 나온다.**

    고치기 전에는 여기서 이렇게 죽었다:
        AccidentalException: ajor is not a supported accidental type
    곡은 다 만들어졌고 돈도 다 나간 뒤였다.
    """
    from app.api.deps import STORE

    # 스텁 엔진이 만든 곡의 조성만 사람이 쓰는 표기로 바꿔치기한다 —
    # 실제 모델이 하는 일이 정확히 이것이다.
    from app.generation.engines import stub as stub_mod
    from app.main import app

    real_motifs = stub_mod.StubComposerEngine.motifs

    def human_keys(self: Any, *a: Any, **k: Any) -> Any:
        out = real_motifs(self, *a, **k)
        for m in out:
            # pydantic 이 들어오는 자리에서 고쳐 받는지 보려면 다시 검증시켜야 한다.
            m.key = type(m).model_validate({**m.model_dump(), "key": "C major"}).key
        return out

    monkeypatch.setattr(stub_mod.StubComposerEngine, "motifs", human_keys)

    with TestClient(app) as c:
        r = c.post("/api/compositions/market",
                   json={"tier_id": "beginner", "preset_id": "march"})

    assert r.status_code == 200, f"곡이 안 나왔다: {r.text[:400]}"
    body = r.json()
    assert body["composition_id"], "곡 번호가 없다"
    assert body["measures"] > 0, "마디가 하나도 없다"
    assert body["composition_id"] in STORE.compositions, "곡이 보관함에 없다"


def test_the_piece_is_still_there_after_a_restart() -> None:
    """"만든곡도 0곡으로 아무것도 없어" 가 다시는 없어야 한다."""
    from app.api.deps import STORE
    from app.main import app

    with TestClient(app) as c:
        made = c.post("/api/compositions/market",
                      json={"tier_id": "beginner", "preset_id": "march"}).json()
        listed = c.get("/api/compositions").json()

    assert made["composition_id"] in STORE.compositions
    assert any(x["composition_id"] == made["composition_id"] for x in listed), (
        "곡을 만들었는데 보관함 목록에 안 보인다"
    )


def test_the_score_file_is_real_musicxml() -> None:
    """번호만 있고 악보가 없으면 곡이 나온 것이 아니다."""
    from app.main import app

    with TestClient(app) as c:
        cid = c.post("/api/compositions/market",
                     json={"tier_id": "beginner", "preset_id": "march"}).json()["composition_id"]
        xml = c.get(f"/api/compositions/{cid}/musicxml").text

    assert "<score-partwise" in xml, "악보가 MusicXML 이 아니다"
    assert "<note" in xml, "악보에 음표가 없다"


# ── 실수에 얼마가 나갔는지 보이는가 ───────────────────────────────────────


def test_money_spent_on_a_failed_attempt_is_recorded() -> None:
    """**곡을 못 얻고 나간 돈이 장부에 남는가.**

    원장님: "실수시 얼마가 소비되는지 알고 있어야 할 것 같아."
    여태 비용 기록은 곡이 만들어진 뒤에만 남았다 — 정작 알고 싶은 돈만 빠져 있었다.
    """
    from app.api.deps import STORE
    from app.api.studio import _spend

    class Ledger:
        total_usd = 1.234

    class Engine:
        ledger = Ledger()

    class Pipe:
        engine = Engine()

    _spend(STORE, Pipe(), ok=False, what="토카타 · 중급")

    log = STORE.jobs.get("spend_log", [])
    assert log, "실패한 시도에 쓴 돈이 어디에도 안 남았다"
    assert log[-1]["usd"] == pytest.approx(1.234)
    assert log[-1]["ok"] is False


def test_the_screen_can_see_what_was_wasted() -> None:
    from app.api.deps import STORE
    from app.api.studio import _spend
    from app.main import app

    class L:
        total_usd = 2.0

    class E:
        ledger = L()

    class P:
        engine = E()

    _spend(STORE, P(), ok=False, what="토카타")
    L.total_usd = 3.0
    _spend(STORE, P(), ok=True, what="행진곡")

    with TestClient(app) as c:
        s = c.get("/api/spending").json()

    assert s["total_wasted_usd"] == pytest.approx(2.0), f"날린 돈을 안 센다: {s}"
    assert s["total_failed"] == 1
    assert s["this_month"]["wasted_usd"] == pytest.approx(2.0)
    assert len(s["recent"]) == 2, "최근 시도 낱낱이 안 보인다"


def test_free_runs_are_not_written_to_the_ledger() -> None:
    """규칙 기반(무료)으로 만든 것까지 적으면 장부가 지저분해진다."""
    from app.api.deps import STORE
    from app.api.studio import _spend

    class L:
        total_usd = 0.0

    class E:
        ledger = L()

    class P:
        engine = E()

    _spend(STORE, P(), ok=True, what="무료")
    assert not STORE.jobs.get("spend_log"), "0원짜리를 장부에 적었다"


def test_the_screen_shows_the_wasted_money() -> None:
    page = (
        Path(__file__).resolve().parents[2] / "web" / "index.html"
    ).read_text(encoding="utf-8")
    assert "곡을 못 얻고 나간 돈" in page, "날린 돈을 화면이 말하지 않는다"
    assert "최근 시도 낱낱" in page, "한 번에 얼마 나갔는지 볼 길이 없다"
