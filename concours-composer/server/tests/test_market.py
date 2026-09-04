"""학원에 팔 대중 콩쿨곡 — 얼굴을 모르는 아이들이 치는 곡.

맞춤곡과 목적이 다르고, 목적이 다르면 기준이 뒤집힌다.

    맞춤곡  — 이 아이가 **할 수 있는 최대**를 쓴다. 강점을 드러내는 것이 목표다.
    대중곡  — 그 급수 아이들이 **모두 할 수 있는 선**을 쓴다. 안 되는 아이가 없어야 한다.

손이 큰 아이는 작은 곡을 칠 수 있지만, 손이 작은 아이는 큰 곡을 못 친다. 실패가 한
방향으로만 나므로 **작은 쪽**에 맞춘다. 이 검사들이 지키는 것이 그 비대칭이다.
"""

from __future__ import annotations

import pytest
from app.api.deps import STORE
from app.generation.market import (
    BY_TIER,
    SAFE_FIRST,
    TIERS,
    recommended_presets,
    standard_competition,
    standard_student,
)
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


def test_the_standard_student_is_built_for_the_smallest_hand() -> None:
    """급수가 올라가도 손 기준이 나이대 평균을 앞지르면 안 된다.

    파는 곡의 실패는 한 방향이다 — 손이 모자라 못 치는 것. 그래서 기준을 낮게 잡는다.
    """
    for tier in TIERS:
        s = standard_student(tier)
        assert s.hand_span.max_interval <= 8, (
            f"{tier.name} 이 손 {s.hand_span.max_interval}도를 요구한다 — "
            "그 급수의 작은 손은 못 친다"
        )
        assert s.tempo_comfort_max_bpm <= 150, f"{tier.name} 의 빠르기가 무대에서 위험하다"


def test_the_standard_student_has_no_personal_traits() -> None:
    """특정 아이의 강점에 기댄 곡은 다른 아이에게 안 맞는다."""
    for tier in TIERS:
        s = standard_student(tier)
        assert s.strengths == [] and s.weaknesses == [], f"{tier.name} 에 개인 특성이 붙었다"


def test_tiers_go_up_in_one_direction() -> None:
    """급수가 올라가면 요구도 함께 올라가야 한다 — 뒤섞이면 원장이 고를 수 없다."""
    prev = None
    for tier in TIERS:
        if prev is not None:
            assert tier.level >= prev.level
            assert tier.span >= prev.span
            assert tier.tempo >= prev.tempo
            assert tier.reading >= prev.reading
        prev = tier


def test_the_safest_concept_comes_first() -> None:
    """심사표는 형식이 뚜렷한 곡에 후하다. 파는 곡은 도박을 하지 않는다."""
    for tier in TIERS:
        picks = recommended_presets(tier)
        assert picks, f"{tier.name} 에 권할 성격이 하나도 없다"
        assert picks[0].id in SAFE_FIRST, (
            f"{tier.name} 의 첫 권장이 {picks[0].id} 다 — 안전한 것부터 와야 한다"
        )


def test_every_tier_stays_inside_its_concepts_level_range() -> None:
    """권한 성격이 그 급수에서 살아나지 않으면 권하는 의미가 없다."""
    for tier in TIERS:
        for p in recommended_presets(tier):
            lo, hi = p.level_range
            assert lo <= tier.level <= hi, f"{tier.name}({tier.level}) 에 {p.id}({lo}~{hi}) 가 섞였다"


def test_the_competition_profile_gives_a_real_time_limit() -> None:
    """제한 시간이 없으면 곡 길이를 설계할 수 없다."""
    for tier in TIERS:
        c = standard_competition(tier)
        assert c.time_limit_sec and 60 <= c.time_limit_sec <= 300


# ── 화면이 실제로 부르는 길 ────────────────────────────────────────────────


def test_the_screen_can_list_the_tiers(client) -> None:
    rows = client.get("/api/market/tiers").json()
    assert len(rows) == len(TIERS)
    first = rows[0]
    assert first["who"], "원장은 '누가 치는 곡인가' 만 보고 고른다 — 그 줄이 비면 안 된다"
    assert first["presets"], "권할 성격이 없으면 버튼을 눌러도 만들 수 없다"


def test_one_button_makes_a_sellable_piece(client) -> None:
    """급수 하나만 고르면 곡이 나온다 — 학생을 적지 않아도 된다."""
    r = client.post("/api/compositions/market", json={"tier_id": "middle"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["measures"] > 0
    assert body["savable"] is True, "검증을 통과하지 못한 곡은 팔 수 없다"

    tier = BY_TIER["middle"]
    # 곡이 그 급수의 손·빠르기 안에 있어야 한다 — 이것이 파는 곡의 존재 이유다.
    assert body["tempo"] <= tier.tempo, f"♩={body['tempo']} 는 {tier.name} 에게 빠르다"


def test_a_market_piece_is_marked_in_the_library(client) -> None:
    """민준이 것과 파는 것이 목록에서 섞이면 사고가 난다."""
    client.post("/api/compositions/market", json={"tier_id": "beginner"})
    rows = client.get("/api/compositions").json()
    assert rows and rows[0]["market_tier"] == "초급"


def test_an_unknown_tier_says_so(client) -> None:
    r = client.post("/api/compositions/market", json={"tier_id": "없는급수"})
    assert r.status_code == 404


# ── 심사 통과할 때까지 다시 시도 ────────────────────────────────────────────


def test_a_chosen_concept_is_not_swapped_out(client) -> None:
    """원장이 성격을 직접 골랐으면 그 성격으로 만든다 — 마음대로 바꾸지 않는다."""
    r = client.post(
        "/api/compositions/market",
        json={"tier_id": "middle", "preset_id": "waltz", "max_attempts": 3},
    )
    assert r.status_code == 200, r.text
    # 왈츠는 3박이다. 다른 성격으로 갈아탔다면 박자가 달라진다.
    assert r.json()["meter"].startswith("3"), "고른 성격을 지키지 않았다"


def test_retrying_costs_money_so_it_is_bounded() -> None:
    """한 번 더 만들 때마다 돈이 또 든다 — 무한정 시도할 수 없다."""
    from app.api.studio import MarketComposeIn
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MarketComposeIn(tier_id="middle", max_attempts=9)
    assert MarketComposeIn(tier_id="middle").max_attempts == 1, "기본이 1이어야 돈이 안 샌다"


def test_retry_keeps_the_best_when_none_passes(client) -> None:
    """통과한 것이 없어도 버리지 않는다 — 원장이 돈을 낸 곡이다.

    규칙 기반 엔진에서는 심사 문턱을 넘기 어렵다. 그때도 곡은 나와야 하고,
    나온 것은 그중 **가장 나은 것**이어야 한다.
    """
    r = client.post("/api/compositions/market", json={"tier_id": "beginner", "max_attempts": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["savable"] is True

    # 시도한 곡은 모두 보관함에 남는다 — 미달본도 원장의 것이다.
    rows = client.get("/api/compositions").json()
    assert len(rows) >= 1
    assert all(x["market_tier"] == "초급" for x in rows)


# ── 급수별 한 벌 ────────────────────────────────────────────────────────────


def test_a_whole_set_is_made_in_one_go(client) -> None:
    """학원에 파는 단위는 한 곡이 아니라 묶음이다."""
    r = client.post(
        "/api/compositions/market/set",
        json={"tier_ids": ["beginner", "middle", "advanced"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["made"] == 3, f"{body['rows']}"
    names = [row["tier_name"] for row in body["rows"]]
    assert names == ["초급", "중급", "상급"], "고른 순서대로 나와야 한다"

    # 급수가 오르면 곡도 어려워져야 한다 — 그래야 한 벌로 쓸 수 있다.
    diffs = [row["difficulty"] for row in body["rows"] if row["ok"]]
    assert diffs == sorted(diffs), f"급수 순서와 난이도가 어긋난다: {diffs}"


def test_one_blocked_tier_does_not_lose_the_others(client) -> None:
    """다섯 곡을 기다렸는데 세 번째에서 통째로 엎어지면 앞의 둘까지 잃는다."""
    r = client.post(
        "/api/compositions/market/set",
        json={"tier_ids": ["beginner", "middle"]},
    )
    assert r.status_code == 200
    assert r.json()["made"] >= 1


def test_an_unknown_tier_in_a_set_is_refused_before_spending(client) -> None:
    """돈을 쓰기 전에 막는다 — 네 곡 만들고 다섯 번째에서 실패하면 늦다."""
    r = client.post(
        "/api/compositions/market/set",
        json={"tier_ids": ["beginner", "없는급수"]},
    )
    assert r.status_code == 404
    assert not client.get("/api/compositions").json(), "돈을 쓰고 나서 막혔다"


def test_the_set_reports_progress_piece_by_piece(client) -> None:
    """다섯 곡을 만드는 동안 막대가 곡마다 처음으로 돌아가면 안 된다."""
    client.post(
        "/api/compositions/market/set",
        json={"tier_ids": ["beginner", "middle"], "progress_id": "setwatch"},
    )
    p = client.get("/api/progress/setwatch").json()
    assert p["known"] is True and p["done"] is True
    assert p["total"] == 2, "몇 곡짜리인지 화면이 알아야 한다"
    assert p["pct"] == 1.0


def test_every_concept_stays_reachable_for_every_tier() -> None:
    """급수에 안 맞는 성격을 화면에서 아예 빼면 안 된다.

    원장이 "토카타가 왜 없지?" 에서 막혔다 — 없는 것인지, 숨은 것인지, 고장인지
    알 길이 없었다. 토카타는 레벨 5~10 이라 초급·초중급에서 목록에 뜨지 않았다.

    맞춤곡 화면은 이미 권하지 않는 컨셉도 흐리게 보여 주고 있었다. 두 화면이 다르게
    굴면 그 자체가 결함이다. 일부러 어려운 성격을 고를 수 있어야 하고, 대신 왜 권하지
    않는지를 적어 준다.

    화면 동작이라 여기서는 그 자리를 지키는지만 본다.
    """
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "web" / "index.html"
    text = web.read_text(encoding="utf-8")
    grid = text[text.index('$("btnMarketPick").onclick') : text.index('$("btnMarketGo").onclick')]
    assert "const rest = all.filter" in grid, "맞지 않는 성격을 목록에서 빼고 있다"
    assert "권하지 않습니다" in grid, "왜 흐린지 말해 주지 않으면 고장으로 보인다"
    assert "level_range" in grid, "어느 레벨에서 살아나는 성격인지 알려 줘야 한다"


def test_no_tier_can_reach_every_concept_by_itself() -> None:
    """이 검사가 전제를 못 박아 둔다 — 그래서 위의 '전부 보여 주기' 가 필요하다.

    어느 급수에서든 권장 목록만으로 열두 가지가 다 나온다면 화면이 굳이 나머지를
    보여 줄 이유가 없다. 실제로는 급수마다 두세 가지가 빠진다.
    """
    from app.generation.presets import PRESETS

    for tier in TIERS:
        got = {p.id for p in recommended_presets(tier)}
        assert len(got) < len(PRESETS), f"{tier.name} 이 모든 성격을 권한다 — 전제가 바뀌었다"


def test_the_preflight_survives_data_living_outside_the_program_folder() -> None:
    """실측 준비 점검이 참고 악보 경로에서 죽지 않아야 한다.

    자료를 프로그램 폴더 바깥으로 옮기자 `refs.relative_to(ROOT)` 가 ValueError 로
    터졌다 — 원장이 실측을 시작하는 바로 그 자리에서. 돈을 쓰기 전에 죽는 것이
    그나마 다행이지만, 죽는 것은 죽는 것이다.
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "auto_compose.py"), "--preflight"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=180,
        check=False,
    )
    # 키가 없으면 종료코드는 0이 아니다 — 그것은 옳다. 여기서 보는 것은 **죽지 않는가**다.
    assert "Traceback" not in r.stderr, f"준비 점검이 터졌다:\n{r.stderr}"
    assert "참고 악보" in r.stdout, f"점검이 끝까지 가지 못했다:\n{r.stdout}\n{r.stderr}"
    assert "컨셉" in r.stdout


def _fake_out(preset_id: str, *, passed: bool = True):
    """`run_auto` 가 돌려주는 모양만 흉내낸다 — 여기서 보는 것은 재시도 규칙뿐이다."""
    from app.api.studio import AutoComposeOut, JudgeGate

    return AutoComposeOut(
        request_id="req-x",
        composition_id=f"comp-{preset_id}",
        preset_id=preset_id,
        title="시험곡",
        engine="stub",
        measures=32,
        difficulty=3.0,
        key="C major",
        meter="4/4",
        tempo=100,
        savable=True,
        shown_as_draft=not passed,
        combined_score=8.0,
        musicality=8.0,
        validation={},
        judge=JudgeGate(
            passed=passed, average=8.2 if passed else 7.2, minimum=7.5 if passed else 6.5,
            required_average=8.0, required_minimum=7.0, rounds=0,
        ),
        cost={},
    )


def test_a_blocked_concept_does_not_cost_the_tier_its_place_in_the_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """형식이 겹쳐 막힌 급수는 **다른 성격으로** 넘어가야 한다.

    실측에서 잡힌 결함이다. 다섯 급수 한 벌을 만들었더니 초급이 통째로 비고
    "방금 만든 곡과 형식이 너무 닮아서 멈췄습니다" 한 줄만 남았다. 원인은 시도
    횟수(기본 1회)를 **곡이 안 나온 실패에도** 썼기 때문이다. 그 실패는 같은
    성격으로 다시 해도 같은 자리에서 막히므로, 시도 횟수를 쓰면 안 된다.
    """
    from app.api import studio
    from fastapi import HTTPException

    tried: list[str] = []

    def fake_run_auto(body, store, pipeline, settings):  # type: ignore[no-untyped-def]
        tried.append(body.preset_id)
        if len(tried) < 3:
            raise HTTPException(409, {"message": "방금 만든 곡과 형식이 너무 닮아서 멈췄습니다"})
        return _fake_out(body.preset_id)

    monkeypatch.setattr(studio, "run_auto", fake_run_auto)
    got = studio._compose_one_for_market(
        "beginner", None, 1, None, "", ("", -1.0), object(), object(), object()
    )
    assert len(tried) == 3, f"막힌 성격에서 멈췄다: {tried}"
    assert got.composition_id


def test_the_paid_retry_budget_still_counts_pieces_that_were_actually_made(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """곡이 나왔는데 심사만 미달인 경우는 다르다 — 다시 만들면 **또 돈이 든다**.

    그래서 그쪽은 원장이 정한 횟수를 정확히 지켜야 한다. 위 수정이 이것까지
    풀어 버리면 한 곡 값으로 다섯 곡 값이 나간다.
    """
    from app.api import studio

    made: list[str] = []

    def fake_run_auto(body, store, pipeline, settings):  # type: ignore[no-untyped-def]
        made.append(body.preset_id)
        return _fake_out(body.preset_id, passed=False)

    monkeypatch.setattr(studio, "run_auto", fake_run_auto)
    studio._compose_one_for_market(
        "beginner", None, 2, None, "", ("", -1.0), object(), object(), object()
    )
    assert len(made) == 2, f"돈이 드는 재시도가 {len(made)}번 일어났다 (정한 것은 2번)"
