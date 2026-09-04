"""**돈을 쓰고도 아무것도 못 얻는** 자리를 없앤다.

원장님이 몇 번이고 겪으신 것이 이것이다 — "소비 비용은 엄청 나왔는데 결과물은 없다".
앞선 판에서 그 원인 하나(글자 수 한도에 걸려 잘림)를 잡았다. 여기서 잡는 것은
**비용 원장(ledger)과 얽힌 세 자리**다.

  A. 값을 치르고 제대로 받아 온 답을, 바로 그 호출 때문에 상한이 넘었다는 이유로
     **버리고 있었다.** 이미 낸 돈으로 산 물건을 문 앞에서 버리는 셈이다.
  B. 단계별 작곡(모티브 고르기 → 설계 승인 → 작곡) 경로에는 상한 초과 안내가
     없어서, 화면에 '처리하지 못한 오류' 만 떴다.
  C. 잘려서 다시 부를 때 **남은 예산을 보지 않았다.** 낼 수 없는 값을 부르면
     그 호출이 상한을 넘겨 곡이 통째로 날아간다.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.config import Settings
from app.generation.client import CallRecord, ClaudeClient, CostLedger, CostLimitExceeded
from pydantic import BaseModel


class Tiny(BaseModel):
    ok: bool = True


def _rec(cost: float) -> CallRecord:
    return CallRecord(
        stage="realize[1-4]", model="claude-sonnet-5", input_tokens=100,
        output_tokens=1000, cache_read_tokens=0, cost_usd=cost,
    )


# ── A. 값을 치른 답을 버리지 않는다 ────────────────────────────────────────


def test_a_paid_answer_is_never_thrown_away() -> None:
    """상한을 넘긴 그 호출의 답도 **이미 산 물건**이다. 받아서 쓴다.

    예전에는 `add()` 가 그 자리에서 예외를 던져, 방금 돈 주고 받아 온 프레이즈가
    파이프라인에 닿지도 못하고 사라졌다.
    """
    ledger = CostLedger(limit_usd=1.00)
    ledger.add(_rec(0.60))
    ledger.add(_rec(0.70))  # 여기서 1.30 — 상한을 넘었다

    assert ledger.total_usd == pytest.approx(1.30)
    assert len(ledger.calls) == 2, "값을 치른 호출이 원장에 남지 않았다"


def test_but_the_next_call_is_refused() -> None:
    """넘긴 뒤에는 **다음 호출을 막는다** — 그것이 상한의 목적이다."""
    ledger = CostLedger(limit_usd=1.00)
    ledger.add(_rec(1.30))

    with pytest.raises(CostLimitExceeded):
        ledger.check_before_call()


def test_no_limit_means_no_limit() -> None:
    """'넘더라도 끝까지' 를 고르셨으면 아무 데서도 막지 않는다."""
    ledger = CostLedger(limit_usd=0)
    ledger.add(_rec(99.0))
    ledger.check_before_call()  # 던지지 않아야 한다


def test_the_whole_call_path_keeps_the_answer_that_broke_the_ceiling() -> None:
    """조각이 아니라 실제 호출 경로로 확인한다 — 배선이 빠지면 조각 검사는 못 잡는다."""
    asked: list[int] = []

    class Usage:
        input_tokens = 1000
        output_tokens = 60000          # 비싸게 나왔다 — 이 한 번으로 상한을 넘는다
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class Reply:
        parsed_output = Tiny()
        stop_reason = "end_turn"
        usage = Usage()

    class Ctx:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

        @staticmethod
        def get_final_message() -> Reply:
            return Reply()

    class Messages:
        @staticmethod
        def stream(**kw: Any) -> Any:
            asked.append(int(kw["max_tokens"]))
            return Ctx()

        @staticmethod
        def parse(**kw: Any) -> Reply:
            asked.append(int(kw["max_tokens"]))
            return Reply()

    class Fake:
        messages = Messages()

    c = ClaudeClient(settings=Settings(anthropic_api_key="sk-ant-" + "x" * 30))
    c._client = Fake()
    c.ledger.limit_usd = 0.10          # 아주 낮게 — 이 호출 하나로 반드시 넘는다

    got = c.parse(stage="realize[1-4]", system="s", user="u", output_model=Tiny)

    assert isinstance(got, Tiny), "돈을 내고 받아 온 프레이즈를 버렸다"
    assert c.ledger.total_usd > 0.10, "비용을 원장에 남기지 않았다"

    # 그리고 다음 호출은 막힌다.
    with pytest.raises(CostLimitExceeded):
        c.parse(stage="realize[5-8]", system="s", user="u", output_model=Tiny)


# ── C. 낼 수 없는 재시도는 부르지 않는다 ──────────────────────────────────


def test_a_retry_it_cannot_afford_is_not_attempted() -> None:
    """잘렸다고 무조건 다시 부르면, 그 호출이 상한을 넘겨 곡을 통째로 잃는다.

    남은 예산으로 감당이 안 되면 **부르지 않고** 원장에게 무엇을 하면 되는지 말한다.
    """
    from app.generation.apierrors import ClaudeUnavailable

    class Usage:
        input_tokens = 100
        output_tokens = 30000
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class Cut:
        parsed_output = None
        stop_reason = "max_tokens"
        usage = Usage()

    calls: list[int] = []

    class Ctx:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

        @staticmethod
        def get_final_message() -> Cut:
            return Cut()

    class Messages:
        @staticmethod
        def stream(**kw: Any) -> Any:
            calls.append(int(kw["max_tokens"]))
            return Ctx()

        @staticmethod
        def parse(**kw: Any) -> Cut:
            calls.append(int(kw["max_tokens"]))
            return Cut()

    class Fake:
        messages = Messages()

    c = ClaudeClient(settings=Settings(anthropic_api_key="sk-ant-" + "x" * 30))
    c._client = Fake()
    c.ledger.limit_usd = 0.35          # 첫 호출($0.30)은 되고, 더 큰 재시도는 안 된다

    with pytest.raises(ClaudeUnavailable) as caught:
        c.parse(stage="realize[25-28]", system="s", user="u", output_model=Tiny)

    assert len(calls) == 1, f"낼 수 없는 재시도를 불러 돈을 더 썼다: {calls}"
    assert caught.value.per_request, "이 프레이즈만의 문제인데 곡 전체를 버리게 표시했다"
    assert "비용" in caught.value.what_to_do or "예산" in caught.value.what_to_do, (
        f"돈 때문에 멈춘 것인데 그 말을 안 한다: {caught.value.what_to_do}"
    )


# ── D. 예산이 바닥나도 만든 마디는 남는다 ─────────────────────────────────


def test_when_the_budget_runs_out_the_bars_already_paid_for_survive(pipeline, ctx) -> None:
    """작곡 도중 예산이 바닥났다. **여기까지 만든 마디는 곡이 되어 나와야 한다.**

    예전에는 예외가 그대로 올라가 곡이 통째로 사라졌다. 앞 프레이즈들은 이미 값을
    치른 것이므로, 그것을 버리는 것은 원장님 돈을 버리는 것이다.
    """
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)
    real = pipeline.engine.realize_phrase

    def dies_after_two(ctx_: Any, req: Any) -> Any:
        if req.phrase_index >= 2:
            raise CostLimitExceeded("이미 상한 도달: $3.0100 / $3.00")
        return real(ctx_, req)

    pipeline.engine.realize_phrase = dies_after_two  # type: ignore[method-assign]
    try:
        measures, failures = pipeline.realize(ctx, plan, motif)
    finally:
        pipeline.engine.realize_phrase = real  # type: ignore[method-assign]

    assert measures, "예산이 바닥났다고 이미 만든 마디를 버렸다"
    assert any("비용 상한" in f for f in failures), f"왜 짧은지 말하지 않는다: {failures}"
    assert any("끝까지" in f for f in failures), "다음에 어떻게 하면 되는지 말하지 않는다"


def test_a_piece_still_comes_out_when_the_judge_cannot_be_paid_for(pipeline, ctx) -> None:
    """음표는 다 썼는데 채점할 돈이 없다 — 그래도 곡은 나온다."""
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)

    def broke(*a: object, **k: object) -> Any:
        raise CostLimitExceeded("이미 상한 도달: $3.0100 / $3.00")

    pipeline.engine.critique = broke  # type: ignore[method-assign]
    try:
        res = pipeline.compose(ctx, motif, plan)
    finally:
        del pipeline.engine.critique

    assert res.measures, "채점을 못 했다고 곡을 버렸다"
    assert any("비평" in n for n in res.quality.notes), (
        f"채점이 없다는 사실을 원장에게 말하지 않는다: {res.quality.notes}"
    )
    assert not res.quality.passed, "채점도 못 했는데 '통과' 로 표시했다"


def test_the_step_by_step_path_explains_the_cost_ceiling(monkeypatch) -> None:
    """단계별 작곡 경로에도 상한 안내가 있어야 한다 — 없어서 '처리하지 못한 오류' 만 떴다."""
    import app.api.compositions as mod

    src = (
        __import__("pathlib").Path(mod.__file__).read_text(encoding="utf-8")
    )
    body = src.split("def realize")[1].split("\ndef ")[0]
    assert "CostLimitExceeded" in body, "단계별 작곡 경로가 상한 초과를 잡지 않는다"
    assert "what_to_do" in body, "무엇을 하면 되는지 말하지 않는다"


def test_the_one_touch_path_keeps_the_piece_when_the_judge_round_dies(
    monkeypatch,
) -> None:
    """원터치 작곡: 심사 지적을 반영하다 멈춰도 **곡은 저장되어 나온다.**

    이 호출은 곡이 다 만들어진 **뒤**, 저장되기 **전**에 일어난다. 예전에는 여기서
    예외가 올라가 검증까지 통과한 곡이 디스크에 닿지도 못하고 사라졌다.
    """
    from app.api.deps import STORE
    from app.main import app
    from fastapi.testclient import TestClient

    for bucket in (STORE.requests, STORE.motifs, STORE.plans, STORE.compositions,
                   STORE.versions, STORE.judgements):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus

    get_corpus().scores.clear()
    get_corpus()._ngrams.clear()

    from app.api import studio

    def broke(*a: object, **k: object) -> Any:
        raise CostLimitExceeded("이미 상한 도달: $3.0100 / $3.00")

    # 심사 게이트가 반드시 한 번은 돌도록 문턱을 올린다.
    monkeypatch.setattr(
        studio.CompositionPipeline, "revise_with_notes", broke, raising=False
    )

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post(
            "/api/compositions/market",
            json={"tier_id": "beginner", "preset_id": "march"},
        )

    assert r.status_code == 200, f"심사 라운드가 멈췄다고 곡을 버렸다: {r.text[:300]}"
    assert r.json()["composition_id"]


# ── 안내가 가리키는 것이 화면에 실제로 있는가 ─────────────────────────────


def test_the_advice_points_at_a_button_that_exists() -> None:
    """'끝까지 만들기 를 고르십시오' 라고 해 놓고 그런 단추가 없으면 안내가 아니다.

    상한 없이 만드는 길이 예전에는 '직접 고르기' 를 누른 뒤 숫자를 0 으로 바꿔야만
    열렸다. 컴맹 원장님께 그것은 없는 길이나 같다.
    """
    from app.generation.budget import MODES

    unlimited = [m for m in MODES if m.cost_limit <= 0]
    assert unlimited, "상한 없이 만드는 등급이 등급 목록에 없다 — 한 번에 고를 수 없다"
    assert len(unlimited) == 1, f"상한 없는 등급이 둘 이상이다: {[m.id for m in unlimited]}"
    assert "끝까지" in unlimited[0].name, f"이름만 봐서는 뭘 하는 등급인지 모른다: {unlimited[0].name}"


def test_every_mode_says_what_it_costs_before_the_owner_spends() -> None:
    """등급마다 대략 얼마인지 미리 보여야 한다 — 겪고 나서 알면 늦다."""
    from app.generation.budget import MODES

    for m in MODES:
        assert m.detail.strip(), f"{m.id} 에 설명이 없다"
        assert m.typical_high > 0, f"{m.id} 가 얼마쯤인지 말하지 않는다"


def test_the_screen_no_longer_claims_the_notes_disappear() -> None:
    """상한에 닿아도 음표는 사라지지 않는다 — 화면이 그렇게 말하면 거짓이다.

    거짓이 무해하지도 않다. 겁이 난 원장님은 필요 없는 돈을 더 쓰시게 된다.
    """
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[2] / "web" / "index.html"
    ).read_text(encoding="utf-8")
    assert "만든 음표는 <b>사라집니다</b>" not in page, "화면이 아직 사라진다고 말하고 있다"
