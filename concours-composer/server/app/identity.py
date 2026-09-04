"""지금 이 설치본의 작곡가 이름 — 악보에 찍히는 쪽.

악보·음원에 나가는 이름은 **예명 하나**여야 한다. 곡을 만드는 파이프라인이
저장소를 알 필요는 없으므로, 이름만 여기에 하나 두고 양쪽이 이것을 본다.

실명은 여기에 **들어오지 않는다**. 실명은 저장소에만 있고 저작권 등록 서류를
만들 때만 꺼낸다 — 프롬프트로도 악보로도 새지 않게 하려는 것이다.
"""

from __future__ import annotations

DEFAULT_ALIAS = "accelssam"

# 한 칸짜리 상자. 전역 변수 재대입을 피하려고 dict 로 둔다.
_state: dict[str, str] = {"alias": DEFAULT_ALIAS}


def current_alias() -> str:
    """악보 표지·음원 태그에 찍을 이름."""
    return _state["alias"]


def set_alias(name: str) -> None:
    """저장된 예명을 반영한다. 빈 값이면 기본 예명으로 돌아간다."""
    _state["alias"] = name.strip() or DEFAULT_ALIAS
