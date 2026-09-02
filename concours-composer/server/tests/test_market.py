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
