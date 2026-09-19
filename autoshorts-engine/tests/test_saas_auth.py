"""인증·권한 단위 테스트 (DB 불필요)."""

from __future__ import annotations

import pytest

from saas.auth import (
    MIN_PASSWORD_LENGTH,
    AuthError,
    Principal,
    hash_password,
    new_id,
    new_token,
    normalize_email,
    token_fingerprint,
    validate_password,
    verify_password,
)
from saas.tenancy import AccessDenied, NotFound, Role, require_member, require_role

# scrypt 기본 파라미터는 테스트 1회당 ~100ms 다. 검증 로직만 볼 때는 n 을 낮춘다.
FAST_N = 2 ** 8


def test_password_roundtrip():
    encoded = hash_password("correct horse battery", n=FAST_N)
    assert verify_password("correct horse battery", encoded) is True
    assert verify_password("correct horse batteryX", encoded) is False


def test_password_hash_is_salted():
    """같은 비밀번호라도 해시가 달라야 한다. 레인보우 테이블 대비."""
    first = hash_password("same-password-here", n=FAST_N)
    second = hash_password("same-password-here", n=FAST_N)
    assert first != second
    assert verify_password("same-password-here", first)
    assert verify_password("same-password-here", second)


def test_hash_records_its_own_parameters():
    """나중에 비용을 올려도 기존 해시가 검증돼야 한다."""
    encoded = hash_password("parameters-in-hash", n=FAST_N)
    scheme, n, r, p, _salt, _key = encoded.split("$")
    assert scheme == "scrypt"
    assert (int(n), int(r), int(p)) == (FAST_N, 8, 1)


@pytest.mark.parametrize("broken", ["", "not-a-hash", "scrypt$1$2$3", "bcrypt$1$8$1$aa$bb"])
def test_verify_rejects_malformed_hash(broken):
    assert verify_password("anything", broken) is False


def test_short_password_rejected():
    with pytest.raises(AuthError):
        validate_password("a" * (MIN_PASSWORD_LENGTH - 1))


def test_absurdly_long_password_rejected():
    """scrypt 에 임의 길이 입력을 흘리면 CPU DoS 표면이 된다."""
    with pytest.raises(AuthError):
        validate_password("a" * 2000)


@pytest.mark.parametrize("raw,expected", [
    ("  User@Example.COM ", "user@example.com"),
    ("a.b+tag@sub.example.co.kr", "a.b+tag@sub.example.co.kr"),
])
def test_email_normalized(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("bad", ["", "no-at-sign", "a@b", "a b@c.com", "@example.com"])
def test_bad_email_rejected(bad):
    with pytest.raises(AuthError):
        normalize_email(bad)


def test_token_is_not_stored_in_plaintext():
    token = new_token()
    assert token.startswith("ast_")
    fingerprint = token_fingerprint(token)
    assert token not in fingerprint
    assert len(fingerprint) == 64
    assert token_fingerprint(token) == fingerprint          # 결정적
    assert token_fingerprint(new_token()) != fingerprint    # 충돌하지 않음


def test_new_id_is_prefixed_and_unique():
    ids = {new_id("ws") for _ in range(200)}
    assert len(ids) == 200
    assert all(i.startswith("ws_") for i in ids)


# ── 권한 ───────────────────────────────────────────────────


def principal(**memberships) -> Principal:
    return Principal(user_id="usr_1", email="a@example.com", memberships=dict(memberships))


def test_member_of_other_workspace_gets_not_found_not_denied():
    """403 이면 '그 워크스페이스는 존재한다'가 새어나간다."""
    with pytest.raises(NotFound):
        require_member(principal(ws_mine="owner"), "ws_someone_else")


def test_role_hierarchy():
    user = principal(ws_1="editor")
    assert require_role(user, "ws_1", Role.VIEWER) == "editor"
    assert require_role(user, "ws_1", Role.EDITOR) == "editor"
    with pytest.raises(AccessDenied):
        require_role(user, "ws_1", Role.ADMIN)


def test_viewer_cannot_write():
    with pytest.raises(AccessDenied):
        require_role(principal(ws_1="viewer"), "ws_1", Role.EDITOR)


def test_owner_passes_every_gate():
    user = principal(ws_1="owner")
    for minimum in (Role.VIEWER, Role.EDITOR, Role.ADMIN, Role.OWNER):
        assert require_role(user, "ws_1", minimum) == "owner"
