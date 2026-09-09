"""지수 백오프 재시도 데코레이터.

모든 외부 API 조회 호출에 붙인다. **주문 API에는 절대 붙이지 않는다**
(중복 주문 방지 — 실패 시 체결 조회로 상태를 확인한다).
"""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from utils.logger import get_logger

logger = get_logger("retry")

T = TypeVar("T")


class RetryExhausted(Exception):
    """모든 재시도가 실패했을 때 마지막 예외를 감싸 올린다."""

    def __init__(self, attempts: int, last_error: BaseException) -> None:
        super().__init__(f"{attempts}회 시도 모두 실패: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    *,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    give_up_on: tuple[type[BaseException], ...] = (),
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.2,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """`max_attempts`회까지 재시도하며 대기 시간을 `backoff` 배로 늘린다.

    Args:
        max_attempts: 총 시도 횟수(첫 호출 포함).
        backoff: 대기 시간 배수. 대기 = base_delay * backoff**(n-1) (+ 지터).
        exceptions: 재시도 대상 예외.
        give_up_on: 이 예외들은 재시도하지 않고 즉시 올린다(`exceptions`보다 우선).
        jitter: 대기 시간에 곱해지는 무작위 편차 비율(동시 재시도 몰림 방지).
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except give_up_on:
                    raise
                except exceptions as exc:
                    last_error = exc
                    if attempt >= max_attempts:
                        break
                    delay = min(base_delay * (backoff ** (attempt - 1)), max_delay)
                    delay *= 1 + random.uniform(-jitter, jitter)
                    logger.warning(
                        "%s 실패 (%d/%d): %s — %.1f초 후 재시도",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            assert last_error is not None
            logger.error("%s 재시도 소진 (%d회): %s", func.__name__, max_attempts, last_error)
            raise RetryExhausted(max_attempts, last_error) from last_error

        return wrapper

    return decorator
