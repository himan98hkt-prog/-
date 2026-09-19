"""presigned upload.

원본 영상은 수백 MB 다. API 프로세스가 그 바이트를 중계하면 워커 스레드가 업로드
시간만큼 묶이고, 수평 확장이 곧바로 막힌다. 그래서 **클라이언트가 저장소로 직접**
올리고 서버는 짧은 수명의 서명만 발급한다.

두 가지 백엔드를 둔다.

``LocalPresigner``
    개발·자체 호스팅용. 서명은 HMAC-SHA256, 수신은 API 의 ``PUT /v1/uploads/{id}``.
    서명 안에 키·크기 상한·만료가 묶여 있어서 티켓을 고쳐 다른 경로에 쓸 수 없다.

``S3Presigner``
    S3/R2/MinIO 용 SigV4 presigned PUT URL. boto3 없이 표준 라이브러리로만 만든다.
    의존성 하나를 아끼려는 게 아니라, 서명 규칙이 이 파일 안에서 **읽히고 테스트되게**
    하기 위해서다.

어느 쪽이든 서명은 자격증명이다. **로그에 남기지 않는다.**
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

from autoshorts.storage import Storage, StorageError
from autoshorts.utils import get_logger

__all__ = [
    "PresignedUpload",
    "Presigner",
    "LocalPresigner",
    "S3Presigner",
    "UploadError",
    "storage_key_for_asset",
    "sha256_stream",
    "MAX_UPLOAD_BYTES",
    "ALLOWED_CONTENT_TYPES",
]

LOG = get_logger("saas.uploads")

MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024        # 4 GiB
DEFAULT_TTL_SECONDS = 900

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class UploadError(RuntimeError):
    """업로드 티켓이 유효하지 않거나 본문이 규칙을 위반했다."""


def safe_filename(name: str, *, fallback: str = "source.mp4") -> str:
    """저장소 키에 넣을 안전한 파일 이름.

    한글 파일명은 키에서 떨어뜨리고 원본 이름은 DB 에만 남긴다. 키에 비ASCII 가
    들어가면 S3 서명과 로컬 파일시스템 인코딩이 서로 다르게 해석할 여지가 생긴다.
    """
    base = Path(str(name or "")).name
    suffix = Path(base).suffix
    stem = base[: len(base) - len(suffix)] if suffix else base
    # 확장자와 본체를 따로 씻는다. 한꺼번에 하면 비ASCII 이름에서 확장자가 통째로
    # 날아간다("영상.mp4" → "mp4"), 그러면 FFmpeg 가 컨테이너를 잘못 고른다.
    stem = _SAFE_NAME.sub("_", stem).strip("._")
    suffix = _SAFE_NAME.sub("", suffix).lower()
    if not stem:
        stem = "source" if suffix else ""
    if not stem:
        return fallback
    return (stem[:110] + suffix)[:120]


def storage_key_for_asset(
    workspace_id: str, project_id: str, asset_id: str, filename: str
) -> str:
    """자산 하나의 저장소 키.

    워크스페이스를 키의 **첫 요소**로 둔다. 버킷 정책이나 접두사 권한으로 테넌트를
    분리할 때 이 형태가 필요하다.
    """
    return f"workspaces/{workspace_id}/projects/{project_id}/assets/{asset_id}/{safe_filename(filename)}"


def sha256_stream(stream: BinaryIO, *, chunk: int = 1024 * 1024) -> tuple[str, int]:
    """스트림을 흘려보내며 체크섬과 크기를 구한다. 전체를 메모리에 올리지 않는다."""
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(chunk)
        if not block:
            break
        digest.update(block)
        total += len(block)
    return digest.hexdigest(), total


@dataclass(frozen=True)
class PresignedUpload:
    """클라이언트에게 그대로 넘기는 업로드 지시서."""

    url: str
    method: str
    headers: dict[str, str]
    storage_key: str
    expires_at: str
    max_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "headers": dict(self.headers),
            "storage_key": self.storage_key,
            "expires_at": self.expires_at,
            "max_bytes": self.max_bytes,
        }


class Presigner(ABC):
    @abstractmethod
    def presign_put(
        self, storage_key: str, *, content_type: str, max_bytes: int, ttl_seconds: int
    ) -> PresignedUpload: ...


# ── 로컬(자체 호스팅) ────────────────────────────────────────


class LocalPresigner(Presigner):
    """API 가 직접 수신하는 서명 업로드.

    ``secret`` 은 서명 키다. 프로세스마다 다르면 재시작 후 발급한 티켓이 모두 깨지므로
    운영에서는 반드시 환경변수로 고정해야 한다.
    """

    def __init__(self, secret: str, storage: Storage, *, base_url: str = "") -> None:
        if not secret:
            raise ValueError("서명 키가 비어 있습니다.")
        self._secret = secret.encode("utf-8")
        self.storage = storage
        self.base_url = base_url.rstrip("/")

    def _sign(self, ticket_id: str, storage_key: str, expires: int, max_bytes: int) -> str:
        payload = f"{ticket_id}\n{storage_key}\n{expires}\n{max_bytes}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def presign_put(
        self,
        storage_key: str,
        *,
        content_type: str = "",
        max_bytes: int = MAX_UPLOAD_BYTES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        ticket_id: str | None = None,
    ) -> PresignedUpload:
        ticket = ticket_id or secrets.token_urlsafe(18)
        expires_dt = datetime.now(timezone.utc) + timedelta(seconds=max(30, int(ttl_seconds)))
        expires = int(expires_dt.timestamp())
        max_bytes = max(1, min(int(max_bytes), MAX_UPLOAD_BYTES))
        signature = self._sign(ticket, storage_key, expires, max_bytes)
        url = f"{self.base_url}/v1/uploads/{ticket}?expires={expires}&signature={signature}"
        headers = {"Content-Type": content_type} if content_type else {}
        return PresignedUpload(
            url=url,
            method="PUT",
            headers=headers,
            storage_key=storage_key,
            expires_at=expires_dt.isoformat(),
            max_bytes=max_bytes,
        )

    def verify(
        self, ticket_id: str, storage_key: str, expires: int, max_bytes: int, signature: str
    ) -> None:
        """서명 검증. 실패하면 :class:`UploadError`."""
        try:
            expires = int(expires)
            max_bytes = int(max_bytes)
        except (TypeError, ValueError) as exc:
            raise UploadError("업로드 티켓이 올바르지 않습니다.") from exc
        expected = self._sign(ticket_id, storage_key, expires, max_bytes)
        if not hmac.compare_digest(expected, str(signature or "")):
            raise UploadError("업로드 서명이 올바르지 않습니다.")
        if datetime.now(timezone.utc).timestamp() > expires:
            raise UploadError("업로드 티켓이 만료됐습니다. 다시 요청하세요.")

    def receive(self, stream: BinaryIO, storage_key: str, *, max_bytes: int) -> tuple[str, int]:
        """본문을 저장소에 쓰고 (체크섬, 크기) 를 돌려준다.

        상한을 넘으면 **쓰다 말고 지운다.** 상한 검사를 Content-Length 헤더로만 하면
        거짓 헤더로 우회된다.
        """
        tmp = Path(tempfile.mkdtemp(prefix="autoshorts-upload-")) / "payload"
        digest = hashlib.sha256()
        total = 0
        try:
            with tmp.open("wb") as handle:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise UploadError(f"업로드 크기 상한({max_bytes} bytes)을 넘었습니다.")
                    digest.update(block)
                    handle.write(block)
            if total == 0:
                raise UploadError("빈 파일은 업로드할 수 없습니다.")
            self.storage.put(tmp, storage_key)
        except StorageError as exc:
            raise UploadError(f"저장에 실패했습니다: {exc}") from exc
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)
        return digest.hexdigest(), total


# ── S3 호환 ─────────────────────────────────────────────────


def _sigv4_key(secret: str, date: str, region: str, service: str) -> bytes:
    key = f"AWS4{secret}".encode("utf-8")
    for part in (date, region, service, "aws4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    return key


class S3Presigner(Presigner):
    """S3/R2/MinIO presigned PUT (SigV4, query 서명).

    ``UNSIGNED-PAYLOAD`` 로 서명한다. 본문 해시를 미리 알 수 없는 브라우저 직접
    업로드에서 표준적으로 쓰는 방식이다. 크기 상한은 서명이 아니라 **버킷 정책**으로
    걸어야 한다. 그 점을 :attr:`max_bytes` 주석으로 남겨 둔다.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint: str = "",
        service: str = "s3",
    ) -> None:
        if not (bucket and access_key and secret_key):
            raise ValueError("S3 자격증명이 비어 있습니다.")
        self.bucket = bucket
        self.region = region or "auto"
        self.service = service
        self._access_key = access_key
        self._secret_key = secret_key
        self.endpoint = (endpoint or f"https://{bucket}.s3.{self.region}.amazonaws.com").rstrip("/")

    @property
    def host(self) -> str:
        return self.endpoint.split("://", 1)[-1].split("/", 1)[0]

    def presign_put(
        self,
        storage_key: str,
        *,
        content_type: str = "",
        max_bytes: int = MAX_UPLOAD_BYTES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: datetime | None = None,
    ) -> PresignedUpload:
        moment = now or datetime.now(timezone.utc)
        amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = moment.strftime("%Y%m%d")
        ttl = max(30, min(int(ttl_seconds), 7 * 24 * 3600))

        canonical_uri = "/" + quote(storage_key.lstrip("/"), safe="/~")
        credential = f"{self._access_key}/{date_stamp}/{self.region}/{self.service}/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": credential,
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(ttl),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = "&".join(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items())
        )
        canonical_request = "\n".join(
            [
                "PUT",
                canonical_uri,
                canonical_query,
                f"host:{self.host}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                f"{date_stamp}/{self.region}/{self.service}/aws4_request",
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _sigv4_key(self._secret_key, date_stamp, self.region, self.service),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        url = f"{self.endpoint}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"
        headers = {"Content-Type": content_type} if content_type else {}
        return PresignedUpload(
            url=url,
            method="PUT",
            headers=headers,
            storage_key=storage_key,
            expires_at=(moment + timedelta(seconds=ttl)).isoformat(),
            # 서명으로는 강제되지 않는다. 버킷 정책에서 같은 값을 걸어야 실효가 있다.
            max_bytes=max(1, min(int(max_bytes), MAX_UPLOAD_BYTES)),
        )
