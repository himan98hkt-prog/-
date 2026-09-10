"""Module F — YouTube Shorts Uploader.

렌더링한 세로 영상을 YouTube 에 업로드한다. 조회용 API 키와 달리
업로드는 **OAuth 2.0 사용자 인증**이 필요하므로, 최초 1회 브라우저 로그인 후
갱신 토큰을 로컬에 저장해 이후 무인 실행에 쓴다.

주의할 점 둘:

1. ``videos.insert`` 는 **1회 1,600 유닛**을 쓴다. 무료 한도가 하루 10,000
   유닛이므로 **하루 6개**가 사실상의 상한이다.
2. 남의 영상을 잘라 올리면 저작권 신고 대상이 될 수 있다. 그래서 기본
   공개범위를 ``private`` 으로 두고, 공개 전환은 명시적으로 선택하게 했다.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from .utils import get_logger

__all__ = [
    "UploadRequest",
    "UploadResult",
    "UploadError",
    "AuthRequiredError",
    "QuotaExceededError",
    "upload_video",
    "build_body",
    "sanitize_title",
    "sanitize_description",
    "normalise_tags",
    "load_credentials",
    "run_oauth_flow",
    "default_token_path",
    "PRIVACY_CHOICES",
    "UPLOAD_QUOTA_COST",
    "DAILY_UPLOAD_LIMIT",
    "SHORTS_MAX_SECONDS",
]

LOG = get_logger("uploader")

# 업로드 권한만 요청한다(읽기/삭제 권한은 받지 않는다).
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

UPLOAD_QUOTA_COST = 1600
DAILY_FREE_QUOTA = 10_000
DAILY_UPLOAD_LIMIT = DAILY_FREE_QUOTA // UPLOAD_QUOTA_COST   # = 6

PRIVACY_CHOICES = ("private", "unlisted", "public")

# YouTube 가 쇼츠로 인식하는 상한 (2024년 이후 3분)
SHORTS_MAX_SECONDS = 180.0

# API 가 거부하는 제목/설명 문자
_ANGLE_BRACKETS = re.compile(r"[<>]")
MAX_TITLE_CHARS = 100
MAX_DESCRIPTION_CHARS = 5000
MAX_TAGS_CHARS = 450          # 실제 상한 500. 여유를 둔다.


class UploadError(RuntimeError):
    """업로드 실패."""


class AuthRequiredError(UploadError):
    """OAuth 인증이 필요하거나 만료됨."""


class QuotaExceededError(UploadError):
    """업로드 할당량 초과."""


def default_token_path() -> Path:
    """갱신 토큰 저장 위치. 홈 디렉터리 아래에 둔다."""
    override = os.environ.get("AUTOSHORTS_TOKEN_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".autoshorts" / "youtube_token.json"


def default_client_secret_path() -> Path:
    override = os.environ.get("AUTOSHORTS_CLIENT_SECRET")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".autoshorts" / "client_secret.json"


@dataclass
class UploadRequest:
    """업로드 한 건의 요청 내용."""

    video_path: Path
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category_id: str = "22"                 # People & Blogs
    privacy: str = "private"                # 기본은 비공개 — 검토 후 공개
    publish_at: datetime | None = None      # 예약 공개 (privacy 는 private 이어야 함)
    made_for_kids: bool = False
    notify_subscribers: bool = False        # 자동 발행이므로 기본은 알림 없음
    add_shorts_tag: bool = True

    def __post_init__(self) -> None:
        self.video_path = Path(self.video_path)
        if self.privacy not in PRIVACY_CHOICES:
            raise ValueError(f"privacy 는 {PRIVACY_CHOICES} 중 하나여야 합니다: {self.privacy!r}")
        if self.publish_at is not None:
            # YouTube 는 예약 공개 시 업로드 시점 공개범위가 private 이어야 한다.
            if self.publish_at.tzinfo is None:
                self.publish_at = self.publish_at.replace(tzinfo=timezone.utc)
            self.privacy = "private"


@dataclass
class UploadResult:
    """업로드 결과."""

    video_id: str
    title: str = ""
    privacy: str = "private"
    publish_at: datetime | None = None
    quota_used: int = UPLOAD_QUOTA_COST

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def shorts_url(self) -> str:
        return f"https://www.youtube.com/shorts/{self.video_id}"

    @property
    def studio_url(self) -> str:
        return f"https://studio.youtube.com/video/{self.video_id}/edit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "shorts_url": self.shorts_url,
            "studio_url": self.studio_url,
            "privacy": self.privacy,
            "publish_at": self.publish_at.isoformat() if self.publish_at else None,
            "quota_used": self.quota_used,
        }


def sanitize_title(title: str, *, add_shorts_tag: bool = True) -> str:
    """제목을 API 가 받는 형태로 다듬는다.

    ``<``/``>`` 는 거부되므로 제거하고, ``#Shorts`` 를 붙인 뒤 100자로 맞춘다.
    태그를 붙이다 100자를 넘으면 본문 쪽을 줄여 태그를 살린다.
    """
    text = _ANGLE_BRACKETS.sub("", str(title or "")).strip()
    text = " ".join(text.split())
    if not text:
        # "Shorts" 로 두면 아래에서 태그가 붙어 "Shorts #Shorts" 가 된다.
        text = "무제 클립"

    suffix = " #Shorts"
    if add_shorts_tag and "#shorts" not in text.lower():
        room = MAX_TITLE_CHARS - len(suffix)
        if len(text) > room:
            text = text[:room].rstrip(" ,.·")
        text = f"{text}{suffix}"
    return text[:MAX_TITLE_CHARS]


def sanitize_description(description: str) -> str:
    text = _ANGLE_BRACKETS.sub("", str(description or ""))
    return text[:MAX_DESCRIPTION_CHARS]


def normalise_tags(tags: Sequence[str], *, add_shorts_tag: bool = True) -> list[str]:
    """태그 목록을 정리한다. 전체 길이 상한(500자)에 맞춰 잘라낸다."""
    seen: list[str] = []
    source = list(tags or [])
    if add_shorts_tag:
        source = ["Shorts", *source]
    total = 0
    for raw in source:
        tag = _ANGLE_BRACKETS.sub("", str(raw or "")).strip()
        if not tag or any(tag.lower() == kept.lower() for kept in seen):
            continue
        if total + len(tag) + 1 > MAX_TAGS_CHARS:
            break
        seen.append(tag)
        total += len(tag) + 1
    return seen


def build_body(request: UploadRequest) -> dict[str, Any]:
    """``videos.insert`` 에 넣을 요청 본문. 순수 함수라 테스트가 쉽다."""
    status: dict[str, Any] = {
        "privacyStatus": request.privacy,
        "selfDeclaredMadeForKids": bool(request.made_for_kids),
    }
    if request.publish_at is not None:
        status["publishAt"] = request.publish_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    return {
        "snippet": {
            "title": sanitize_title(request.title, add_shorts_tag=request.add_shorts_tag),
            "description": sanitize_description(request.description),
            "tags": normalise_tags(request.tags, add_shorts_tag=request.add_shorts_tag),
            "categoryId": str(request.category_id),
        },
        "status": status,
    }


def _secure_write(path: Path, content: str) -> None:
    """토큰처럼 민감한 파일은 본인만 읽도록 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)     # 0600
    except OSError:                                  # 윈도우 등에서는 무시
        LOG.debug("토큰 파일 권한 설정을 건너뜁니다: %s", path)


def run_oauth_flow(
    client_secret_path: str | Path | None = None,
    token_path: str | Path | None = None,
    *,
    port: int = 0,
) -> Any:
    """브라우저를 열어 최초 1회 인증하고 갱신 토큰을 저장한다."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise AuthRequiredError(
            "업로드에는 OAuth 라이브러리가 필요합니다.\n"
            "  pip install google-auth-oauthlib google-api-python-client"
        ) from exc

    client_secret_path = Path(client_secret_path or default_client_secret_path()).expanduser()
    token_path = Path(token_path or default_token_path()).expanduser()
    if not client_secret_path.exists():
        raise AuthRequiredError(
            f"OAuth 클라이언트 파일이 없습니다: {client_secret_path}\n"
            "Google Cloud Console → API 및 서비스 → 사용자 인증 정보에서 "
            "'데스크톱 앱' OAuth 클라이언트를 만들어 JSON 을 내려받아 위 경로에 두세요."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    credentials = flow.run_local_server(port=port, prompt="consent")
    _secure_write(token_path, credentials.to_json())
    LOG.info("인증 완료. 갱신 토큰 저장: %s", token_path)
    return credentials


def load_credentials(
    token_path: str | Path | None = None,
    client_secret_path: str | Path | None = None,
    *,
    allow_interactive: bool = False,
) -> Any:
    """저장된 토큰을 읽고, 만료됐으면 갱신한다.

    ``allow_interactive`` 가 False 인데 토큰이 없으면 예외를 낸다.
    예약 실행(무인)에서 브라우저가 뜨는 일을 막기 위해서다.
    """
    try:
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise AuthRequiredError(
            "업로드에는 Google 인증 라이브러리가 필요합니다.\n"
            "  pip install google-auth-oauthlib google-api-python-client"
        ) from exc

    token_path = Path(token_path or default_token_path()).expanduser()
    credentials = None
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as exc:
            LOG.warning("저장된 토큰을 읽지 못했습니다(%s). 다시 인증이 필요합니다.", exc)
            credentials = None

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _secure_write(token_path, credentials.to_json())
            LOG.info("액세스 토큰을 갱신했습니다.")
            return credentials
        except Exception as exc:
            LOG.warning("토큰 갱신 실패(%s). 다시 인증이 필요합니다.", exc)

    if not allow_interactive:
        raise AuthRequiredError(
            f"YouTube 업로드 인증이 없습니다({token_path}).\n"
            "집 PC 에서 한 번만 `autoshorts login` 을 실행해 브라우저로 로그인하세요."
        )
    return run_oauth_flow(client_secret_path, token_path)


def _classify_http_error(exc: Exception) -> UploadError:
    """googleapiclient 오류를 읽기 쉬운 예외로 바꾼다."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    text = str(exc)
    if "quotaExceeded" in text or "uploadLimitExceeded" in text:
        return QuotaExceededError(
            "YouTube 업로드 할당량을 초과했습니다. "
            f"업로드 1건이 {UPLOAD_QUOTA_COST} 유닛이라 무료 한도로는 하루 "
            f"{DAILY_UPLOAD_LIMIT}건이 상한입니다. 내일 다시 시도하세요."
        )
    if status in (401, 403) and ("authError" in text or "unauthorized" in text.lower()):
        return AuthRequiredError("인증이 만료됐습니다. `autoshorts login` 으로 다시 로그인하세요.")
    if status == 400:
        return UploadError(f"요청이 거부됐습니다(제목·설명·태그 형식 확인). {text}")
    return UploadError(f"업로드 실패: {text}")


def upload_video(
    request: UploadRequest,
    *,
    credentials: Any = None,
    token_path: str | Path | None = None,
    client_secret_path: str | Path | None = None,
    allow_interactive: bool = False,
    chunk_size: int = 4 * 1024 * 1024,
    on_progress: Callable[[float], None] | None = None,
    service: Any = None,
) -> UploadResult:
    """영상 한 개를 업로드한다.

    ``service`` 를 주입하면 실제 API 호출 없이 테스트할 수 있다.
    """
    path = Path(request.video_path)
    if not path.exists():
        raise UploadError(f"업로드할 파일이 없습니다: {path}")
    if path.stat().st_size == 0:
        raise UploadError(f"파일이 비어 있습니다: {path}")

    body = build_body(request)

    if service is None:
        try:
            from googleapiclient.discovery import build  # type: ignore
            from googleapiclient.http import MediaFileUpload  # type: ignore
        except ImportError as exc:  # pragma: no cover - 환경 의존
            raise UploadError(
                "업로드에는 google-api-python-client 가 필요합니다.\n"
                "  pip install google-api-python-client google-auth-oauthlib"
            ) from exc

        credentials = credentials or load_credentials(
            token_path, client_secret_path, allow_interactive=allow_interactive
        )
        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        media = MediaFileUpload(str(path), chunksize=chunk_size, resumable=True, mimetype="video/*")
    else:
        media = str(path)

    LOG.info(
        "업로드 시작: %s (%s, %.1fMB)",
        body["snippet"]["title"], request.privacy, path.stat().st_size / 1_048_576,
    )

    try:
        insert = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = insert.next_chunk()
            if status and on_progress:
                on_progress(float(getattr(status, "progress", lambda: 0.0)()))
    except Exception as exc:
        raise _classify_http_error(exc) from None

    video_id = (response or {}).get("id")
    if not video_id:
        raise UploadError(f"업로드 응답에 영상 id 가 없습니다: {response!r}")

    result = UploadResult(
        video_id=video_id,
        title=body["snippet"]["title"],
        privacy=request.privacy,
        publish_at=request.publish_at,
    )
    LOG.info("업로드 완료: %s", result.shorts_url)
    return result


def check_shorts_eligibility(duration_seconds: float, width: int, height: int) -> list[str]:
    """쇼츠로 인식되지 않을 만한 조건을 경고 목록으로 돌려준다."""
    warnings: list[str] = []
    if duration_seconds > SHORTS_MAX_SECONDS:
        warnings.append(
            f"길이가 {duration_seconds:.0f}초로 쇼츠 상한({SHORTS_MAX_SECONDS:.0f}초)을 넘습니다."
        )
    if height <= width:
        warnings.append(f"세로 영상이 아닙니다({width}x{height}). 쇼츠는 9:16 세로여야 합니다.")
    return warnings
