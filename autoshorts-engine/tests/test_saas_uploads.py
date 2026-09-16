"""presigned upload 단위 테스트 (DB 불필요)."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

from autoshorts.storage import LocalStorage
from saas.uploads import (
    LocalPresigner,
    S3Presigner,
    UploadError,
    safe_filename,
    sha256_stream,
    storage_key_for_asset,
)


@pytest.fixture
def presigner(tmp_path) -> LocalPresigner:
    return LocalPresigner("test-secret", LocalStorage(tmp_path / "objects"))


@pytest.mark.parametrize("raw,expected", [
    ("영상.mp4", "source.mp4"),          # 비ASCII 는 떨어뜨리되 확장자는 지킨다
    ("../../etc/passwd", "passwd"),
    ("my video (1).mov", "my_video_1.mov"),
    ("", "source.mp4"),
    ("...", "source.mp4"),
    (".bashrc", "bashrc"),
])
def test_filename_is_sanitised(raw, expected):
    assert safe_filename(raw) == expected


def test_storage_key_starts_with_workspace():
    """버킷 접두사 권한으로 테넌트를 나눌 수 있어야 한다."""
    key = storage_key_for_asset("ws_1", "prj_2", "ast_3", "a.mp4")
    assert key == "workspaces/ws_1/projects/prj_2/assets/ast_3/a.mp4"
    assert key.startswith("workspaces/ws_1/")


def test_extension_survives_non_ascii_name():
    """확장자가 날아가면 FFmpeg 가 컨테이너를 잘못 고른다."""
    assert safe_filename("한국어 제목.mov").endswith(".mov")
    assert storage_key_for_asset("w", "p", "a", "긴 한글 제목.mp4").endswith(".mp4")


def test_long_name_is_bounded():
    assert len(safe_filename("a" * 400 + ".mp4")) <= 120


def test_key_cannot_escape_via_filename():
    key = storage_key_for_asset("ws_1", "prj_2", "ast_3", "../../../../secrets.env")
    assert ".." not in key


def test_presign_then_upload_roundtrip(presigner, tmp_path):
    key = "workspaces/ws_1/projects/prj_1/assets/ast_1/clip.mp4"
    ticket = presigner.presign_put(key, content_type="video/mp4", max_bytes=1024, ticket_id="t1")
    expires = int(ticket.url.split("expires=")[1].split("&")[0])
    signature = ticket.url.split("signature=")[1]

    presigner.verify("t1", key, expires, ticket.max_bytes, signature)   # 예외 없음
    checksum, size = presigner.receive(io.BytesIO(b"video-bytes"), key, max_bytes=1024)
    assert size == 11
    assert presigner.storage.exists(key)
    assert presigner.storage.open_local(key).read_bytes() == b"video-bytes"
    assert checksum == sha256_stream(io.BytesIO(b"video-bytes"))[0]


def test_tampered_key_fails_verification(presigner):
    """티켓의 키를 바꿔 다른 경로에 쓰려는 시도를 막는다."""
    ticket = presigner.presign_put("a/b/original.mp4", ticket_id="t1")
    expires = int(ticket.url.split("expires=")[1].split("&")[0])
    signature = ticket.url.split("signature=")[1]
    with pytest.raises(UploadError):
        presigner.verify("t1", "a/b/../../victim.mp4", expires, ticket.max_bytes, signature)


def test_tampered_max_bytes_fails_verification(presigner):
    ticket = presigner.presign_put("a/b/c.mp4", max_bytes=100, ticket_id="t1")
    expires = int(ticket.url.split("expires=")[1].split("&")[0])
    signature = ticket.url.split("signature=")[1]
    with pytest.raises(UploadError):
        presigner.verify("t1", "a/b/c.mp4", expires, 10 ** 12, signature)


def test_expired_ticket_rejected(presigner):
    key = "a/b/c.mp4"
    past = int((datetime.now(timezone.utc) - timedelta(seconds=10)).timestamp())
    signature = presigner._sign("t1", key, past, 1024)
    with pytest.raises(UploadError, match="만료"):
        presigner.verify("t1", key, past, 1024, signature)


def test_different_secret_cannot_forge(tmp_path):
    storage = LocalStorage(tmp_path / "o")
    good = LocalPresigner("real-secret", storage)
    evil = LocalPresigner("guessed-secret", storage)
    ticket = evil.presign_put("a/b/c.mp4", ticket_id="t1")
    expires = int(ticket.url.split("expires=")[1].split("&")[0])
    with pytest.raises(UploadError):
        good.verify("t1", "a/b/c.mp4", expires, ticket.max_bytes,
                    ticket.url.split("signature=")[1])


def test_oversize_body_rejected_and_nothing_written(presigner):
    """Content-Length 헤더를 믿지 않고 실제로 흘러온 바이트로 판단한다."""
    key = "a/b/big.mp4"
    with pytest.raises(UploadError, match="상한"):
        presigner.receive(io.BytesIO(b"x" * 5000), key, max_bytes=100)
    assert not presigner.storage.exists(key)


def test_empty_body_rejected(presigner):
    with pytest.raises(UploadError, match="빈 파일"):
        presigner.receive(io.BytesIO(b""), "a/b/empty.mp4", max_bytes=100)


def test_empty_secret_rejected(tmp_path):
    with pytest.raises(ValueError):
        LocalPresigner("", LocalStorage(tmp_path / "o"))


# ── S3 SigV4 ───────────────────────────────────────────────


@pytest.fixture
def s3() -> S3Presigner:
    return S3Presigner(
        bucket="my-bucket", region="ap-northeast-2",
        # 실제 자격증명이 아니다. 비밀 스캐너가 오탐하지 않도록 형식만 흉내 낸 값이다.
        access_key="test-access-key-id",
        secret_key="test-secret-access-key-not-real",
    )


FIXED_TIME = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)


def test_s3_url_has_required_query_parameters(s3):
    url = s3.presign_put("workspaces/ws_1/a.mp4", now=FIXED_TIME).url
    for parameter in (
        "X-Amz-Algorithm=AWS4-HMAC-SHA256", "X-Amz-Credential=", "X-Amz-Date=20260916T120000Z",
        "X-Amz-Expires=", "X-Amz-SignedHeaders=host", "X-Amz-Signature=",
    ):
        assert parameter in url


def test_s3_signature_is_deterministic_for_same_inputs(s3):
    first = s3.presign_put("a/b.mp4", now=FIXED_TIME).url
    second = s3.presign_put("a/b.mp4", now=FIXED_TIME).url
    assert first == second


@pytest.mark.parametrize("change", ["key", "time", "ttl"])
def test_s3_signature_changes_with_inputs(s3, change):
    base = s3.presign_put("a/b.mp4", now=FIXED_TIME).url
    if change == "key":
        other = s3.presign_put("a/c.mp4", now=FIXED_TIME).url
    elif change == "time":
        other = s3.presign_put("a/b.mp4", now=FIXED_TIME + timedelta(seconds=1)).url
    else:
        other = s3.presign_put("a/b.mp4", ttl_seconds=60, now=FIXED_TIME).url
    assert base.split("X-Amz-Signature=")[1] != other.split("X-Amz-Signature=")[1]


def test_s3_secret_never_appears_in_url(s3):
    url = s3.presign_put("a/b.mp4", now=FIXED_TIME).url
    assert "test-secret-access-key-not-real" not in url
    assert "test-access-key-id" in url        # access key 는 공개 값이다


def test_s3_ttl_is_capped_at_seven_days(s3):
    upload = s3.presign_put("a/b.mp4", ttl_seconds=999_999, now=FIXED_TIME)
    assert "X-Amz-Expires=604800" in upload.url


def test_s3_custom_endpoint_for_r2_or_minio():
    presigner = S3Presigner(
        bucket="b", region="auto", access_key="k", secret_key="s",
        endpoint="https://account.r2.cloudflarestorage.com/b",
    )
    assert presigner.host == "account.r2.cloudflarestorage.com"
    assert presigner.presign_put("x.mp4", now=FIXED_TIME).url.startswith(
        "https://account.r2.cloudflarestorage.com/b/x.mp4?"
    )


def test_s3_requires_credentials():
    with pytest.raises(ValueError):
        S3Presigner(bucket="b", region="r", access_key="", secret_key="s")
