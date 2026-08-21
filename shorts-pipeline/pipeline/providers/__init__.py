"""provider 레지스트리."""

from __future__ import annotations

from typing import Callable

from .base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
    VideoProvider,
)

_REGISTRY: dict[str, Callable[..., VideoProvider]] = {}


def register(name: str, factory: Callable[..., VideoProvider]) -> None:
    _REGISTRY[name] = factory


def build_provider(name: str, **kwargs) -> VideoProvider:
    if name not in _REGISTRY:
        raise ProviderError(
            f"알 수 없는 provider: {name}. 사용 가능: {', '.join(sorted(_REGISTRY))}",
            retryable=False,
        )
    return _REGISTRY[name](**kwargs)


def available() -> list[str]:
    return sorted(_REGISTRY)


# 등록은 import 시점에 이뤄진다.
from .fal import FalProvider          # noqa: E402
from .higgsfield import HiggsfieldProvider  # noqa: E402

register("fal", FalProvider)
register("higgsfield", HiggsfieldProvider)

__all__ = [
    "GenerationRequest",
    "GenerationResult",
    "ProviderError",
    "VideoProvider",
    "build_provider",
    "available",
    "register",
]
