"""답이 글자 수 한도에 걸려 **잘렸을 때** 곡을 잃지 않는지.

원장님 화면에 뜬 것이 이것이다:

    RuntimeError: realize[25-28]: 구조화 출력 파싱 실패 (stop_reason=max_tokens)

모델이 음표 JSON 을 쓰다가 한도에 걸려 중간에 끊긴 것이다. 잘린 JSON 은 읽을 수
없으므로 그 프레이즈가 실패하고, 프레이즈 하나가 실패하면 곡 전체가 날아간다.
돈은 이미 쓴 뒤다 — 원장님이 "돈만 계속 날린다" 고 하신 것이 정확히 이 자리다.

내 설계 결함이 둘이었다.
  1. 음표를 쓰는 자리에 한도를 16000 으로 두었다. 토카타는 네 마디에도 음표가
     200개를 넘고, 요즘 모델은 답을 쓰기 전 **생각하는 데도 같은 한도를 나눠 쓴다.**
  2. 한도에 걸리면 그냥 죽었다. 같은 요청을 그대로 다시 해도 또 잘릴 텐데,
     **한도를 키워 다시 부르면** 대개 그 자리에서 풀린다.

한도는 천장이지 요금이 아니다 — 실제로 쓴 만큼만 청구된다. 아낄 이유가 없는 것을
아끼다 곡을 잃은 셈이다.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.config import Settings
from app.generation.apierrors import ClaudeUnavailable
from app.generation.client import ClaudeClient
from pydantic import BaseModel


class Tiny(BaseModel):
    ok: bool = True


class _Usage:
    input_tokens = 100
    output_tokens = 16000
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Reply:
    """SDK 응답 흉내. `parsed_output` 이 None 이면 잘린 것이다."""

    def __init__(self, parsed: object, stop_reason: str) -> None:
        self.parsed_output = parsed
        self.stop_reason = stop_reason
        self.usage = _Usage()


def _client(replies: list[_Reply]) -> tuple[ClaudeClient, list[int]]:
    """부를 때마다 정해진 답을 돌려주는 가짜 클라이언트. 요청한 한도를 기록한다."""
    asked: list[int] = []
    how: list[str] = []

    class Messages:
        @staticmethod
        def parse(**kw: Any) -> _Reply:
            asked.append(int(kw["max_tokens"]))
            how.append("parse")
            return replies.pop(0)

        @staticmethod
        def stream(**kw: Any) -> Any:
            asked.append(int(kw["max_tokens"]))
            how.append("stream")
            reply = replies.pop(0)

            class Ctx:
                def __enter__(self) -> Any:
                    return self

                def __exit__(self, *a: object) -> bool:
                    return False

                @staticmethod
                def get_final_message() -> _Reply:
                    return reply

            return Ctx()

    class Fake:
        messages = Messages()

    c = ClaudeClient(settings=Settings(anthropic_api_key="sk-ant-" + "x" * 30))
    c._client = Fake()
    c.how = how  # type: ignore[attr-defined]
    return c, asked


def test_a_cut_off_answer_is_retried_with_more_room() -> None:
    """한 번 잘렸다고 곡을 버리지 않는다 — 한도를 키워 다시 부른다."""
    c, asked = _client([_Reply(None, "max_tokens"), _Reply(Tiny(), "end_turn")])

    got = c.parse(stage="realize[25-28]", system="s", user="u", output_model=Tiny)

    assert isinstance(got, Tiny)
    assert len(asked) == 2, "다시 부르지 않았다"
    assert asked[1] > asked[0], f"같은 한도로 또 불렀다: {asked}"


def test_it_keeps_growing_until_it_fits() -> None:
    """한 번 키워서 모자라면 한 번 더. 무한정은 아니다."""
    c, asked = _client(
        [_Reply(None, "max_tokens"), _Reply(None, "max_tokens"), _Reply(Tiny(), "end_turn")]
    )

    c.parse(stage="realize[25-28]", system="s", user="u", output_model=Tiny, max_tokens=8000)

    assert len(asked) == 3
    assert asked[0] < asked[1] < asked[2], f"한도가 안 커졌다: {asked}"


def test_it_does_not_pay_twice_for_the_same_ceiling() -> None:
    """천장까지 올린 뒤에는 다시 부르지 않는다.

    모델이 받아 주는 최대치로 부탁했는데도 잘렸다면, 똑같이 다시 부탁해 봐야 똑같이
    잘린다. 그런데 그 한 번이 **또 돈이다.** 원장님이 "돈만 계속 날린다" 고 하신
    바로 그 낭비이므로, 안 될 것이 뻔한 재시도는 하지 않는다.
    """
    from app.generation.client import _MAX_BUDGET

    c, asked = _client([_Reply(None, "max_tokens")] * 3)

    with pytest.raises(ClaudeUnavailable):
        c.parse(
            stage="realize[25-28]", system="s", user="u",
            output_model=Tiny, max_tokens=_MAX_BUDGET,
        )

    assert asked == [_MAX_BUDGET], f"천장에서 헛돈을 더 썼다: {asked}"


def test_when_it_still_does_not_fit_the_owner_is_told_what_to_do() -> None:
    """끝내 안 되면 '무슨 오류' 가 아니라 **무엇을 하면 되는지** 를 말한다."""
    c, _ = _client([_Reply(None, "max_tokens")] * 3)

    with pytest.raises(ClaudeUnavailable) as caught:
        c.parse(stage="realize[25-28]", system="s", user="u", output_model=Tiny)

    assert "음표가 많아" in caught.value.message
    assert "짧은 성격" in caught.value.what_to_do
    assert "토카타" in caught.value.what_to_do, "어떤 곡이 잘 막히는지 알려주지 않는다"


def test_a_normal_answer_is_not_retried() -> None:
    """잘리지 않았으면 한 번만 부른다 — 재시도는 돈이 또 드는 일이다."""
    c, asked = _client([_Reply(Tiny(), "end_turn")])

    c.parse(stage="motif", system="s", user="u", output_model=Tiny)

    assert len(asked) == 1


def test_the_place_that_writes_the_notes_starts_with_real_room() -> None:
    """원장님 곡이 잘린 그 자리다 — 처음부터 넉넉해야 한다.

    한도는 천장이지 요금이 아니다. 실제로 쓴 만큼만 청구되므로 아낄 이유가 없다.
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "generation" / "engines" / "claude_engine.py"
    ).read_text(encoding="utf-8")

    realize = src.split("def realize_phrase")[1].split("def ")[0]
    assert "max_tokens=" in realize, "음표를 쓰는 자리에 한도를 정해 두지 않았다"
    asked = int(realize.split("max_tokens=")[1].split(",")[0])
    assert asked >= 32000, f"음표를 쓰는 자리 한도가 {asked} 로 너무 작다"


def test_one_bad_phrase_does_not_throw_away_the_whole_piece(pipeline, ctx) -> None:
    """프레이즈 하나가 안 됐다고 **이미 값을 치른** 나머지를 버리지 않는다.

    원장님 손해의 정체가 이것이다 — 25~28마디에서 잘렸는데 1~24마디까지도 함께
    사라졌다. 그 24마디는 이미 만들어졌고 이미 청구된 것이다.
    """
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)
    real = pipeline.engine.realize_phrase
    hit: list[int] = []

    def one_phrase_fails(ctx_: Any, req: Any) -> Any:
        if req.phrase_index == 1:
            hit.append(1)
            raise ClaudeUnavailable("잘렸습니다", "짧게 만들어 보십시오", [], per_request=True)
        return real(ctx_, req)

    pipeline.engine.realize_phrase = one_phrase_fails  # type: ignore[method-assign]
    try:
        measures, failures = pipeline.realize(ctx, plan, motif)
    finally:
        pipeline.engine.realize_phrase = real  # type: ignore[method-assign]

    assert hit, "그 프레이즈를 부르지도 않았다 — 검사가 헛돌았다"
    assert measures, "프레이즈 하나가 실패했다고 곡을 통째로 버렸다"
    assert failures, "빠진 자리를 원장에게 알리지 않는다"


def test_a_rejected_key_stops_everything_at_once(pipeline, ctx) -> None:
    """반대로 키·잔액 문제는 즉시 멈춘다 — 계속 불러 봐야 똑같이 막힌다."""
    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)
    real = pipeline.engine.realize_phrase
    calls: list[int] = []

    def always_rejected(ctx_: Any, req: Any) -> Any:
        calls.append(req.phrase_index)
        raise ClaudeUnavailable("API 키가 거절되었습니다", ".env 를 확인하십시오", [])

    pipeline.engine.realize_phrase = always_rejected  # type: ignore[method-assign]
    try:
        with pytest.raises(ClaudeUnavailable):
            pipeline.realize(ctx, plan, motif)
    finally:
        pipeline.engine.realize_phrase = real  # type: ignore[method-assign]

    assert calls == [0], f"키가 거절됐는데 계속 불렀다: {calls}"


def test_a_big_answer_is_streamed_not_waited_for() -> None:
    """한도가 크면 **흘려 받아야** 한다.

    한 번에 다 받으려고 기다리면 답이 다 나오기 전에 연결이 먼저 끊긴다. 그러면
    곡은 만들어졌는데 우리 손에는 아무것도 안 남는다 — 돈만 나가는 그 실패다.
    작곡이 실제로 지나는 길(기본 한도)이 이쪽인지 못 박아 둔다.
    """
    c, _ = _client([_Reply(Tiny(), "end_turn")])

    c.parse(stage="realize[1-4]", system="s", user="u", output_model=Tiny)

    assert c.how == ["stream"], f"큰 한도를 한 번에 받으려 한다: {c.how}"


def test_the_ceiling_is_one_the_models_actually_accept() -> None:
    """천장을 모델이 안 받는 값으로 올려 두면 첫 호출부터 400 으로 튕긴다."""
    from app.generation.client import _MAX_BUDGET, _STREAM_ABOVE

    assert _MAX_BUDGET <= 64000, "Claude 모델들이 받아 주는 출력 한도를 넘었다"
    assert _STREAM_ABOVE < _MAX_BUDGET, "천장까지 올린 요청이 흘려 받지 못한다"
