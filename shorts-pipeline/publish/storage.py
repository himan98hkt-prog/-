"""S3 호환 스토리지 업로드.

인스타그램 Graph API 는 로컬 파일을 받지 않고 **공개적으로 접근 가능한 URL**
만 받는다. 이 모듈이 그 URL 을 만든다.

AWS S3 외에 endpoint_url 만 바꾸면 그대로 동작한다:
  * Cloudflare R2  https://<account_id>.r2.cloudflarestorage.com  (region: auto)
  * Backblaze B2   https://s3.<region>.backblazeb2.com
  * MinIO          http://localhost:9000

URL 전략은 두 가지다.
  presigned (기본) — 서명된 만료 URL. **버킷을 공개로 열 필요가 없다.**
                     인스타그램은 컨테이너 생성 시 한 번만 받아가므로 충분하다.
  public          — 영구 공개 URL. 버킷이 public-read 이거나 CloudFront/R2
                    커스텀 도메인이 붙어 있을 때 쓴다.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

# 인스타그램이 받아가는 동안 만료되면 안 된다. 인코딩 대기까지 감안한 여유값.
DEFAULT_EXPIRY_SECONDS = 3600
_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class StorageError(Exception):
    pass


@dataclass
class UploadedObject:
    bucket: str
    key: str
    url: str
    size_bytes: int
    expires_at: datetime | None = None

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def is_temporary(self) -> bool:
        return self.expires_at is not None


def _require_boto3():
    try:
        import boto3
        from boto3.exceptions import S3UploadFailedError
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError as exc:
        raise StorageError(
            "S3 업로드에 boto3 가 필요합니다.\n  pip install boto3"
        ) from exc
    return _Boto(boto3, Config, BotoCoreError, ClientError,
                 NoCredentialsError, S3UploadFailedError)


class _Boto(NamedTuple):
    boto3: object
    Config: type
    BotoCoreError: type
    ClientError: type
    NoCredentialsError: type
    S3UploadFailedError: type


class _Progress:
    """boto3 upload_file 의 콜백. 10% 단위로만 출력해 로그를 어지럽히지 않는다."""

    def __init__(self, total: int, label: str):
        self._total = max(total, 1)
        self._seen = 0
        self._last_decile = -1
        self._label = label
        self._lock = threading.Lock()

    def __call__(self, chunk: int) -> None:
        with self._lock:
            self._seen += chunk
            decile = int(self._seen * 10 / self._total)
            if decile > self._last_decile:
                self._last_decile = decile
                print(f"    {self._label} {min(decile * 10, 100)}%")


@dataclass
class S3Storage:
    bucket: str
    region: str = "auto"
    endpoint_url: str | None = None
    prefix: str = "reels"
    url_strategy: str = "presigned"        # presigned | public
    public_base_url: str | None = None     # CloudFront / R2 커스텀 도메인
    expiry_seconds: int = DEFAULT_EXPIRY_SECONDS
    acl: str | None = None                 # public 전략에서 "public-read" 로 줄 수 있다

    # ── 생성 ─────────────────────────────────────────────────────────
    @classmethod
    def from_env(cls, overrides: dict | None = None) -> "S3Storage":
        """환경변수에서 설정을 읽는다. overrides(config.yaml) 가 우선한다."""
        overrides = {k: v for k, v in (overrides or {}).items() if v not in (None, "")}
        bucket = overrides.get("bucket") or os.getenv("S3_BUCKET")
        if not bucket:
            raise StorageError(
                "S3 버킷이 설정되지 않았습니다.\n"
                "  .env 의 S3_BUCKET 또는 config.yaml 의 publish.storage.bucket 을 채우세요."
            )
        return cls(
            bucket=bucket,
            region=overrides.get("region") or os.getenv("S3_REGION") or "auto",
            endpoint_url=overrides.get("endpoint_url") or os.getenv("S3_ENDPOINT_URL"),
            prefix=str(overrides.get("prefix", "reels")).strip("/"),
            url_strategy=overrides.get("url_strategy", "presigned"),
            public_base_url=(
                overrides.get("public_base_url")
                or os.getenv("S3_PUBLIC_BASE_URL")
                or os.getenv("PUBLIC_MEDIA_BASE_URL")
            ),
            expiry_seconds=int(overrides.get("expiry_seconds", DEFAULT_EXPIRY_SECONDS)),
            acl=overrides.get("acl"),
        )

    def __post_init__(self) -> None:
        if self.url_strategy not in ("presigned", "public"):
            raise StorageError(
                f"url_strategy 는 presigned 또는 public 이어야 합니다 (현재: {self.url_strategy})"
            )
        if self.url_strategy == "public" and not self.public_base_url and self.endpoint_url:
            raise StorageError(
                "url_strategy: public 인데 public_base_url 이 없습니다.\n"
                "  R2/MinIO 같은 커스텀 엔드포인트는 공개 도메인을 따로 지정해야 합니다.\n"
                "  S3_PUBLIC_BASE_URL 을 설정하거나 url_strategy 를 presigned 로 두세요."
            )
        if self.expiry_seconds < 60:
            raise StorageError("expiry_seconds 는 최소 60 이상이어야 합니다.")
        # 최대 7일. 그 이상은 SigV4 가 거부한다.
        if self.expiry_seconds > 604800:
            raise StorageError("expiry_seconds 는 최대 604800(7일)까지 가능합니다.")

    # ── 클라이언트 ────────────────────────────────────────────────────
    def _client(self):
        b = _require_boto3()
        cfg = b.Config(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "standard"},
            s3={"addressing_style": "virtual" if not self.endpoint_url else "path"},
        )
        return b.boto3.client(
            "s3",
            region_name=None if self.region == "auto" else self.region,
            endpoint_url=self.endpoint_url,
            config=cfg,
        )

    # ── 업로드 ───────────────────────────────────────────────────────
    def key_for(self, path: Path, run_id: str | None = None) -> str:
        stamp = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        parts = [p for p in (self.prefix, stamp, path.name) if p]
        return "/".join(parts)

    def upload(
        self,
        path: Path,
        *,
        run_id: str | None = None,
        key: str | None = None,
        show_progress: bool = True,
    ) -> UploadedObject:
        """파일을 올리고 접근 가능한 URL 을 돌려준다."""
        path = Path(path)
        if not path.exists():
            raise StorageError(f"업로드할 파일이 없습니다: {path}")
        size = path.stat().st_size
        if size == 0:
            raise StorageError(f"업로드할 파일이 비어 있습니다: {path}")

        key = key or self.key_for(path, run_id)
        b = _require_boto3()
        client = self._client()

        extra: dict = {
            "ContentType": _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
        }
        if self.acl:
            extra["ACL"] = self.acl

        callback = _Progress(size, f"S3 업로드 {path.name}") if show_progress else None
        try:
            client.upload_file(
                str(path), self.bucket, key, ExtraArgs=extra, Callback=callback
            )
        except b.NoCredentialsError as exc:
            raise StorageError(_NO_CREDS) from exc
        except b.ClientError as exc:
            raise StorageError(_explain(exc, self.bucket, key)) from exc
        except b.S3UploadFailedError as exc:
            # boto3 의 upload_file 은 내부 ClientError 를 이 예외로 감싼다.
            # 원본을 꺼내 같은 안내를 쓰고, 못 꺼내면 메시지에서 코드를 긁는다.
            cause = exc.__cause__ or exc.__context__
            if isinstance(cause, b.NoCredentialsError):
                raise StorageError(_NO_CREDS) from exc
            if isinstance(cause, b.ClientError):
                raise StorageError(_explain(cause, self.bucket, key)) from exc
            raise StorageError(
                _explain_text(str(exc), self.bucket, key)
            ) from exc
        except b.BotoCoreError as exc:
            raise StorageError(f"S3 업로드 실패: {exc}") from exc

        url, expires_at = self._url_for(client, key)
        return UploadedObject(self.bucket, key, url, size, expires_at)

    def _url_for(self, client, key: str) -> tuple[str, datetime | None]:
        if self.url_strategy == "public":
            if self.public_base_url:
                return f"{self.public_base_url.rstrip('/')}/{key}", None
            host = (
                f"https://{self.bucket}.s3.amazonaws.com"
                if self.region in ("auto", "us-east-1")
                else f"https://{self.bucket}.s3.{self.region}.amazonaws.com"
            )
            return f"{host}/{key}", None

        b = _require_boto3()
        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=self.expiry_seconds,
            )
        except (b.ClientError, b.BotoCoreError) as exc:
            raise StorageError(f"presigned URL 생성 실패: {exc}") from exc
        expires = datetime.now(timezone.utc) + timedelta(seconds=self.expiry_seconds)
        return url, expires

    # ── 정리 ─────────────────────────────────────────────────────────
    def delete(self, key: str) -> None:
        """발행이 끝난 뒤 스토리지 비용을 아끼려면 호출한다."""
        b = _require_boto3()
        try:
            self._client().delete_object(Bucket=self.bucket, Key=key)
        except (b.ClientError, b.BotoCoreError) as exc:
            # 정리 실패로 파이프라인을 죽일 이유는 없다.
            print(f"    ⚠ S3 객체 삭제 실패 ({key}): {exc}")


_NO_CREDS = (
    "AWS 자격증명을 찾지 못했습니다.\n"
    "  .env 에 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 를 넣거나\n"
    "  ~/.aws/credentials 를 설정하세요."
)

# {bucket} 자리는 _explain 에서 채운다.
_HINTS = {
    "NoSuchBucket": "\n  버킷 '{bucket}' 이 존재하지 않습니다. 이름과 리전을 확인하세요.",
    "AccessDenied": "\n  키에 s3:PutObject 권한이 없습니다. IAM 정책을 확인하세요.",
    "InvalidAccessKeyId": "\n  AWS_ACCESS_KEY_ID 가 유효하지 않습니다.",
    "SignatureDoesNotMatch": (
        "\n  AWS_SECRET_ACCESS_KEY 가 틀렸거나, 엔드포인트/리전이 맞지 않습니다."
    ),
    "AccessControlListNotSupported": (
        "\n  이 버킷은 ACL 을 허용하지 않습니다 (S3 기본값).\n"
        "  config 의 publish.storage.acl 을 비우고 url_strategy: presigned 를 쓰세요."
    ),
    "PermanentRedirect": "\n  버킷 리전이 다릅니다. S3_REGION 을 버킷의 실제 리전으로 맞추세요.",
}


def _explain(exc, bucket: str, key: str) -> str:
    """ClientError 를 사람이 읽을 수 있는 안내로 바꾼다."""
    code = exc.response.get("Error", {}).get("Code", "")
    hint = _HINTS.get(code, f"\n  {exc}").format(bucket=bucket)
    return f"S3 업로드 실패 [{code}] {bucket}/{key}{hint}"


def _explain_text(message: str, bucket: str, key: str) -> str:
    """원본 예외를 못 꺼냈을 때, 메시지 문자열에서 오류 코드를 찾아 안내한다."""
    for code, hint in _HINTS.items():
        if code in message:
            return (
                f"S3 업로드 실패 [{code}] {bucket}/{key}" + hint.format(bucket=bucket)
            )
    return f"S3 업로드 실패 {bucket}/{key}\n  {message}"
