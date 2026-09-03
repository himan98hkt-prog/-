"""곡 하나에 얼마를 쓸지 원장이 고른다.

원장님이 중급 토카타를 만들다 상한($4)에 걸려 멈췄다. 계산이 틀린 게 아니라 정말
그만큼 썼다 — 가장 비싼 모델(Opus, 출력 100만 토큰당 $25)이 작곡과 심사를 둘 다 맡고
있었고, 토카타는 음표가 가장 많은 곡이다.

여기서 지키는 것 셋:
  1. 등급을 고르면 **실제로 싼 모델·적은 라운드**로 바뀌는가
  2. 상한 0 = 넘더라도 끝까지 — 돈만 쓰고 곡은 못 얻는 일이 없는가
  3. 등급을 바꿔도 `.env` 와 다음 곡에 **번지지 않는가**
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.generation.budget import (
    BY_ID,
    DEFAULT_MODE,
    MODES,
    PICKABLE_IDS,
    custom_mode,
    resolve,
    settings_for,
)
from app.generation.client import PRICES, CostLedger, CostLimitExceeded


def test_the_cheap_grade_really_is_cheaper_on_the_thing_that_costs_money() -> None:
    """출력 단가가 곡값이다. 등급을 낮추면 그 단가가 실제로 내려가야 한다."""
    saver, best = BY_ID["saver"], BY_ID["best"]
    _, saver_out = PRICES[saver.composer_model]
    _, best_out = PRICES[best.composer_model]

    assert saver_out < best_out, "아껴 쓰기가 최고 품질보다 싸지 않다"
    assert saver.revision_rounds < best.revision_rounds
    assert saver.judges < best.judges
    assert saver.cost_limit < best.cost_limit


def test_every_grade_names_a_model_the_price_table_knows() -> None:
    """가격표에 없는 모델은 최상위가로 계산돼 상한이 실제보다 일찍 걸린다."""
    for m in MODES:
        assert m.composer_model in PRICES, f"{m.name}: 작곡 모델이 가격표에 없다"
        assert m.judge_model in PRICES, f"{m.name}: 심사 모델이 가격표에 없다"


def test_choosing_a_grade_does_not_touch_the_next_piece() -> None:
    """등급은 이번 한 곡에만 걸린다 — 바꿔 가며 눌러도 서로 번지지 않아야 한다."""
    base = Settings(anthropic_api_key="")
    before = base.composer_model

    cheap = settings_for(BY_ID["saver"], base)
    rich = settings_for(BY_ID["best"], base)

    assert cheap.composer_model != rich.composer_model
    assert base.composer_model == before, "원본 설정이 바뀌었다 — 다음 곡까지 번진다"


def test_an_unknown_grade_falls_back_instead_of_stopping() -> None:
    """오래된 화면이 모르는 값을 보내도 작곡이 멈추면 안 된다."""
    assert resolve("이런등급없음").id == DEFAULT_MODE
    assert resolve(None).id == DEFAULT_MODE
    assert resolve("").id == DEFAULT_MODE


def test_no_ceiling_means_the_piece_actually_finishes() -> None:
    """상한 0 = 넘더라도 끝까지.

    돈은 썼는데 곡은 못 얻는 것이 가장 나쁜 결과다 — 원장님이 그것을 겪었다.
    """
    from app.generation.client import CallRecord

    ledger = CostLedger(limit_usd=0.0)
    assert ledger.unlimited
    for _ in range(50):
        ledger.check_before_call()
        ledger.add(CallRecord("realize", "claude-opus-5", 1000, 4000, 0, 0.5))
    assert ledger.total_usd > 20, "상한 없음인데 멈췄다"


def test_a_ceiling_still_stops_when_the_owner_asked_for_one() -> None:
    """상한을 정했으면 지켜야 한다 — 안 그러면 '상한'이 아니다."""
    from app.generation.client import CallRecord

    ledger = CostLedger(limit_usd=1.0)
    with pytest.raises(CostLimitExceeded):
        for _ in range(10):
            ledger.check_before_call()
            ledger.add(CallRecord("realize", "claude-opus-5", 1000, 4000, 0, 0.4))


def test_a_typo_in_the_model_name_cannot_burn_money() -> None:
    """모르는 모델은 첫 호출에서 404 를 맞는다 — 목록 밖 이름은 받지 않는다."""
    m = custom_mode("claude-없는모델", 2.0, 1, 3)
    assert m.composer_model in PICKABLE_IDS


def test_picking_opus_does_not_also_make_the_judges_expensive() -> None:
    """심사위원 3인이 악보 전체를 읽는다. 거기까지 최고가 모델일 이유는 없다."""
    m = custom_mode("claude-opus-5", 0.0, 1, 3)
    assert m.composer_model == "claude-opus-5"
    _, judge_out = PRICES[m.judge_model]
    _, composer_out = PRICES[m.composer_model]
    assert judge_out < composer_out


def test_the_owner_s_own_numbers_are_kept_within_safe_bounds() -> None:
    """0 은 '상한 없음' 이고, 음수는 실수다 — 실수로 이상해지지 않게 한다."""
    assert custom_mode("claude-sonnet-5", -5.0, 9, 9).cost_limit == 0.0
    assert custom_mode("claude-sonnet-5", 2.0, 9, 9).judges == 3
    assert custom_mode("claude-sonnet-5", 2.0, 9, 9).revision_rounds == 2


def test_the_screen_can_ask_what_the_choices_are() -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        d = c.get("/api/quality-modes").json()

    ids = [m["id"] for m in d["modes"]]
    assert ids == ["saver", "standard", "best", "custom"]
    assert d["default"] == "standard"
    assert [m["id"] for m in d["models"]] == [
        "claude-haiku-4-5",
        "claude-sonnet-5",
        "claude-opus-5",
    ]
    for m in d["modes"]:
        assert m["detail"].strip(), f"{m['name']}: 설명이 비어 있으면 고를 수가 없다"
