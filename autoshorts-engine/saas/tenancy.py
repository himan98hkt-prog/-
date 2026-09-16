"""워크스페이스 격리.

격리 규칙을 한 곳에 모은다. 라우트가 늘어날수록 "이 조회에 workspace 조건을
넣었던가?" 를 매번 기억하는 방식은 반드시 깨진다. 그래서 두 겹으로 막는다.

1. **질의 수준** — 저장소 메서드는 ``workspace_id`` 를 필수 인자로 받는다.
   조건을 빼먹으면 타입 오류가 나지 호출이 조용히 성공하지 않는다.
2. **권한 수준** — 여기 :func:`require_role` 이 역할을 확인한다.

없는 자원과 남의 자원을 **같은 오류(NotFound)** 로 답한다. 403 과 404 를 구분하면
"그 ID 는 존재한다"는 정보가 새어나간다.
"""

from __future__ import annotations

from .auth import Principal

__all__ = [
    "Role",
    "ROLES",
    "ROLE_RANK",
    "AccessDenied",
    "NotFound",
    "require_member",
    "require_role",
    "can_write",
]


class AccessDenied(PermissionError):
    """소속은 맞지만 역할이 부족하다."""


class NotFound(LookupError):
    """없거나, 남의 것이다. 둘을 구분해 알려주지 않는다."""


ROLES = ("owner", "admin", "editor", "viewer")

# 숫자가 클수록 권한이 넓다.
ROLE_RANK = {"viewer": 10, "editor": 20, "admin": 30, "owner": 40}


class Role:
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


def require_member(principal: Principal, workspace_id: str) -> str:
    """소속 확인. 아니면 :class:`NotFound`.

    ``AccessDenied`` 가 아니라 ``NotFound`` 인 것이 의도다. 남의 워크스페이스 ID 를
    찍어보며 존재 여부를 알아내지 못하게 한다.
    """
    role = principal.role_in(workspace_id)
    if role is None:
        raise NotFound("워크스페이스를 찾을 수 없습니다.")
    return role


def require_role(principal: Principal, workspace_id: str, minimum: str) -> str:
    """최소 역할 확인."""
    role = require_member(principal, workspace_id)
    if ROLE_RANK.get(role, 0) < ROLE_RANK.get(minimum, 99):
        raise AccessDenied(f"이 작업에는 {minimum} 이상의 권한이 필요합니다.")
    return role


def can_write(role: str | None) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[Role.EDITOR]
