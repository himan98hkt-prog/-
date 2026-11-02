"""호가가격단위(tick size) — 거래소가 받아주는 가격으로 맞춘다.

한국 주식은 아무 가격이나 주문할 수 없다. 주가 구간마다 정해진 단위의 배수여야
하고, 아니면 거래소가 주문 자체를 거부한다. 2023년 개편 이후 유가증권·코스닥·
코넥스가 같은 7단계 표를 쓴다.

이게 없어서 첫 실주문 두 건이 그대로 튕겨 나갔다. 지정가를 `현재가 × 1.003` 으로
계산하고 1원 단위로 반올림했는데, 삼성전자 269,807원은 500원 단위가 아니고
KB금융 177,431원은 100원 단위가 아니다. DRY_RUN 은 주문 API 를 부르지 않으니
같은 값이 며칠 동안 화면에 찍혀도 아무도 몰랐다.
"""

from __future__ import annotations

import math

# (상한 미만, 호가단위). 구간은 '이상 ~ 미만' 이다.
TICK_TABLE: tuple[tuple[int, int], ...] = (
    (2_000, 1),
    (5_000, 5),
    (20_000, 10),
    (50_000, 50),
    (200_000, 100),
    (500_000, 500),
)
TICK_ABOVE = 1_000  # 50만원 이상


def tick_size(price: float) -> int:
    """이 가격대의 호가단위."""
    for upper, tick in TICK_TABLE:
        if price < upper:
            return tick
    return TICK_ABOVE


def floor_to_tick(price: float) -> int:
    """호가단위로 내림. 매수 지정가에 쓴다 — 의도한 상한을 넘지 않는다."""
    if price <= 0:
        return 0
    tick = tick_size(price)
    snapped = int(math.floor(price / tick) * tick)
    # 내림이 한 구간 아래로 떨어지는 경우는 없다(각 구간의 하한은 아래 구간의
    # 단위로도 나누어떨어진다). 그래도 0 으로 주저앉는 것만은 막는다.
    return max(snapped, tick)


def ceil_to_tick(price: float) -> int:
    """호가단위로 올림. 매도 지정가에 쓴다 — 의도한 하한보다 싸게 팔지 않는다."""
    if price <= 0:
        return 0
    tick = tick_size(price)
    return int(math.ceil(price / tick) * tick)


def is_valid_tick(price: float) -> bool:
    """거래소가 받아줄 가격인가. 정수가 아니면 그 자체로 무효다."""
    if price <= 0 or price != int(price):
        return False
    return int(price) % tick_size(price) == 0


def snap(price: float, side: str) -> int:
    """주문 가능한 가격으로 맞춘다.

    매수는 내리고 매도는 올린다 — 어느 쪽도 우리에게 불리해지지 않는 방향이다.
    다만 그 방향으로만 밀다가 현재가 반대편으로 넘어가면 체결될 수가 없으므로,
    최소한 '현재가 쪽 첫 호가' 까지는 돌아온다.
    """
    return floor_to_tick(price) if side == "BUY" else ceil_to_tick(price)
