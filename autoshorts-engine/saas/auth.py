"""인증.

bcrypt/argon2 의존성을 붙이지 않고 표준 라이브러리 ``hashlib.scrypt`` 를 쓴다.
scrypt 는 메모리 하드 KDF 이고 파이썬 3.6+ 표준이다. 파라미터(n, r, p)를 해시
문자열에 같이 저장해 두므로, 나중에 비용을 올려도 기존 해시가 그대로 검증된다.

토큰은 **원문을 저장하지 않는다.** DB 에는 SHA-256 만 남는다. DB 가 유출돼도
세션을 그대로 탈취할 수 없게 하기 위해서다.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

__all__ = [
    "AuthError",
    "InvalidCredentials",
    "Principal",
    "hash_password",
    "verify_password",
    "new_token",
    "token_fingerprint",
    "normalize_email",
    "validate_password",
    "session_expiry",
    "SESSION_TTL_HOURS",
    "MIN_PASSWORD_LENGTH",
]

# scrypt 파라미터. n 을 올리면 느려지고 안전해진다. 로그인 1회 ~100ms 목표.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32

SESSION_TTL_HOURS = 24 * 14
MIN_PASSWORD_LENGTH = 10

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(RuntimeError):
    """인증 관련 실패의 최상위."""


class InvalidCredentials(AuthError):
    """이메일 또는 비밀번호 불일치.

    어느 쪽이 틀렸는지 구분해 알려주지 않는다. 계정 존재 여부가 새어나간다.
    """


def normalize_email(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise AuthError("이메일 형식이 올바르지 않습니다.")
    if len(cleaned) > 254:
        raise AuthError("이메일이 너무 깁니다.")
    return cleaned


def validate_password(password: str) -> str:
    if not isinstance(password, str):
        raise AuthError("비밀번호는 문자열이어야 합니다.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
    if len(password) > 1024:
        # scrypt 에 임의 길이 입력을 넘기면 DoS 표면이 된다.
        raise AuthError("비밀번호가 너무 깁니다.")
    return password


def hash_password(password: str, *, n: int = _SCRYPT_N) -> str:
    """``scrypt$n$r$p$salt$key`` 형식 문자열을 돌려준다."""
    validate_password(password)
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_BYTES
    )
    return f"scrypt${n}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """상수 시간 비교. 형식이 깨졌으면 조용히 False."""
    try:
        scheme, n, r, p, salt_hex, key_hex = (encoded or "").split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            (password or "").encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(key_hex)),
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(candidate, bytes.fromhex(key_hex))


def new_token() -> str:
    """세션 토큰 원문. 사용자에게 딱 한 번만 보여준다."""
    return f"ast_{secrets.token_urlsafe(32)}"


def token_fingerprint(token: str) -> str:
    """DB 에 저장할 토큰 지문."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def session_expiry(hours: int = SESSION_TTL_HOURS) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def new_id(prefix: str) -> str:
    """읽을 수 있는 식별자. 로그에서 종류를 바로 알아볼 수 있다."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True)
class Principal:
    """요청을 보낸 주체. 라우트 핸들러가 받는 유일한 신원 정보."""

    user_id: str
    email: str
    display_name: str = ""
    memberships: dict[str, str] = field(default_factory=dict)  # workspace_id → role

    def role_in(self, workspace_id: str) -> str | None:
        return self.memberships.get(workspace_id)

    def is_member(self, workspace_id: str) -> bool:
        return workspace_id in self.memberships
