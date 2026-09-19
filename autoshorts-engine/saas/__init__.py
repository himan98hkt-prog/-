"""Phase 2 — SaaS Foundation.

``autoshorts`` 패키지(엔진)는 이 패키지를 **모른다.** 의존 방향은 한쪽이다::

    saas  ──▶  autoshorts

엔진은 Phase 1 에서 만든 :mod:`autoshorts.contracts` / :mod:`autoshorts.service`
경계로만 호출한다. 그래서 CLI·Gradio 는 SaaS 계층 없이도 그대로 돈다.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.2.0"
