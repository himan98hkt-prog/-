"""호가가격단위 — 거래소가 받아주는 가격인가.

2026-09-21, 첫 실주문 두 건이 그대로 거부됐다. 삼성전자에 269,807원,
KB금융에 177,431원을 불렀는데 둘 다 호가단위 위반이다. DRY_RUN 은 주문 API 를
부르지 않으니, 같은 값이 며칠 동안 화면에 찍혀도 아무 일도 일어나지 않았다.
"""

from __future__ import annotations

import pytest

from trading.tick import (ceil_to_tick, floor_to_tick, is_valid_tick, snap, tick_size)


@pytest.mark.parametrize("price, expected", [
    (1_999, 1), (2_000, 5), (4_999, 5),
    (5_000, 10), (19_999, 10),
    (20_000, 50), (49_999, 50),
    (50_000, 100), (199_999, 100),
    (200_000, 500), (499_999, 500),
    (500_000, 1_000), (1_250_000, 1_000),
])
def test_tick_size_by_band(price, expected):
    assert tick_size(price) == expected


# --- 실제로 거부당한 값들 ------------------------------------------------------ #

@pytest.mark.parametrize("rejected", [177_431, 269_807, 261_281, 176_628])
def test_the_prices_that_got_rejected_are_invalid(rejected):
    assert not is_valid_tick(rejected)


@pytest.mark.parametrize("raw, expected", [
    (177_431, 177_400),   # KB금융 — 100원 단위
    (269_807, 269_500),   # 삼성전자 — 500원 단위
])
def test_snapping_makes_them_orderable(raw, expected):
    snapped = snap(raw, "BUY")
    assert snapped == expected
    assert is_valid_tick(snapped)


# --- 방향 ---------------------------------------------------------------------- #

def test_buy_rounds_down_and_sell_rounds_up():
    """어느 쪽도 우리에게 불리한 방향으로 넘어가지 않는다."""
    assert snap(269_807, "BUY") == 269_500    # 더 비싸게 사지 않는다
    assert snap(269_807, "SELL") == 270_000   # 더 싸게 팔지 않는다


def test_a_price_already_on_a_tick_is_left_alone():
    for price in (71_500, 269_500, 2_000, 500_000):
        assert snap(price, "BUY") == price
        assert snap(price, "SELL") == price
        assert is_valid_tick(price)


def test_rounding_never_drops_below_the_band_floor():
    """구간 하한은 아래 구간의 단위로도 나누어떨어져야 한다 — 아니면 내림이 깨진다."""
    for upper, _ in ((5_000, 5), (20_000, 10), (50_000, 50), (200_000, 100), (500_000, 500)):
        assert is_valid_tick(floor_to_tick(upper + 1))
        assert is_valid_tick(ceil_to_tick(upper - 1))


def test_fractional_and_zero_prices():
    assert not is_valid_tick(71_500.5)
    assert not is_valid_tick(0)
    assert snap(0, "BUY") == 0
