"""AI 토큰·비용 집계 테스트."""

from __future__ import annotations

import pytest

from agents.usage import DEFAULT_PRICING, Usage, estimate_cost


def test_usage_addition():
    total = Usage(100, 20) + Usage(50, 10)
    assert (total.input_tokens, total.output_tokens, total.total) == (150, 30, 180)


def test_cost_for_known_model():
    # sonnet 5: 입력 $2 / 출력 $10 per 1M
    cost = estimate_cost("claude-sonnet-5", Usage(1_000_000, 100_000))
    assert cost == pytest.approx(2.0 + 1.0)


def test_cost_for_unknown_model_is_zero():
    """단가를 모르면 추정하지 않는다 — 잘못된 숫자보다 0이 낫다."""
    assert estimate_cost("some-future-model", Usage(1_000_000, 1_000_000)) == 0.0


def test_prefix_match_uses_longest():
    pricing = {"gemini": (1.0, 1.0), "gemini-2.5-pro": (10.0, 10.0)}
    cost = estimate_cost("gemini-2.5-pro-latest", Usage(1_000_000, 0), pricing)
    assert cost == pytest.approx(10.0), "더 구체적인 항목을 써야 합니다"


def test_zero_usage_costs_nothing():
    assert estimate_cost("claude-sonnet-5", Usage()) == 0.0


def test_default_pricing_covers_configured_models():
    for model in ("claude-sonnet-5", "gemini-3.1-pro-preview", "gpt-5.1"):
        assert model in DEFAULT_PRICING


# --------------------------------------------------------------------------- #
# 설정으로 단가 덮어쓰기 (ai.pricing)
# --------------------------------------------------------------------------- #


def test_settings_pricing_overrides_defaults():
    from config.loader import AiConfig

    from agents.base_agent import BaseAgent

    class Stub(BaseAgent):
        name = "stub"

        def _call_model(self, system_prompt, user_prompt):
            raise NotImplementedError

    ai = AiConfig(timeout_sec=60, max_retries=1, min_confidence=0.6, news_max_items=5,
                  news_lookback_hours=24, pricing={"my-model": (100.0, 200.0)})
    agent = Stub(ai)
    agent.pricing = dict(ai.pricing) or None
    agent.model = "my-model"

    decision = type("D", (), {})()
    agent._attach_usage(decision, Usage(1_000_000, 1_000_000))
    assert decision.cost_usd == pytest.approx(300.0)


def test_usage_is_isolated_per_thread():
    """타임아웃된 고아 스레드가 다른 종목의 집계를 오염시키면 안 된다."""
    import threading

    from config.loader import AiConfig

    from agents.base_agent import BaseAgent

    class Stub(BaseAgent):
        name = "stub"

        def _call_model(self, system_prompt, user_prompt):
            raise NotImplementedError

    agent = Stub(AiConfig(timeout_sec=60, max_retries=0, min_confidence=0.6,
                          news_max_items=5, news_lookback_hours=24))
    seen: dict[str, int] = {}
    ready = threading.Event()

    def orphan() -> None:
        agent._last_usage = Usage(999_999, 999_999)  # 뒤늦게 쓰는 고아 스레드
        ready.set()

    thread = threading.Thread(target=orphan)
    thread.start()
    ready.wait(2)
    seen["main"] = agent._last_usage.total  # 메인 스레드는 영향받지 않아야 한다
    thread.join(2)

    assert seen["main"] == 0
