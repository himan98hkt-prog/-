"""YouTube Data API v3 로 Shorts 업로드.

쿼터 주의 (2026-08 기준):
  videos.insert 는 2026-06-01 부터 공용 10,000 유닛 풀이 아니라 전용 버킷을
  쓰며 하루 약 100회로 제한된다. config 의 daily_upload_cap 으로 방어한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_STATE_FILE = "youtube_uploads.json"


class UploadError(Exception):
    pass


@dataclass
class UploadResult:
    video_id: str
    url: str


def _require_libs():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise UploadError(
            "YouTube 업로드에 필요한 패키지가 없습니다.\n"
            "  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        ) from exc
    return Request, Credentials, InstalledAppFlow, build, MediaFileUpload


def _credentials():
    Request, Credentials, InstalledAppFlow, _, _ = _require_libs()
    secret_file = Path(os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "secrets/client_secret.json"))
    token_file = Path(os.getenv("YOUTUBE_TOKEN_FILE", "secrets/youtube_token.json"))

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not secret_file.exists():
            raise UploadError(
                f"OAuth 클라이언트 파일이 없습니다: {secret_file}\n"
                "  Google Cloud Console → API 및 서비스 → 사용자 인증 정보에서\n"
                "  'OAuth 클라이언트 ID (데스크톱 앱)' 를 만들어 JSON 을 내려받으세요.\n"
                "  YouTube Data API v3 도 함께 사용 설정해야 합니다."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
        creds = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _quota_state(state_dir: Path) -> tuple[Path, dict]:
    path = state_dir / _STATE_FILE
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    return path, data


def check_quota(state_dir: Path, cap: int) -> tuple[int, int]:
    """(오늘 사용량, 상한) 을 돌려준다."""
    _, data = _quota_state(Path(state_dir))
    return data["count"], cap


def _rfc3339(value: str) -> str:
    """'2026-08-25T21:00' 같은 로컬 시각을 UTC RFC3339 로 바꾼다.

    유튜브는 UTC 를 요구한다. 로컬 시각을 그대로 보내면 9시간 어긋난다.
    """
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(value.strip().replace(" ", "T"))
    except ValueError as exc:
        raise UploadError(
            f"공개 예약 시각을 읽지 못했습니다: {value!r} "
            "(예: 2026-08-25T21:00)") from exc
    if dt.tzinfo is None:
        dt = dt.astimezone()                    # 이 컴퓨터의 표준시로 해석
    if dt <= datetime.now(timezone.utc):
        raise UploadError(f"공개 예약 시각이 이미 지났습니다: {value}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload(
    video: Path,
    *,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str = "private",
    category_id: str = "24",
    state_dir: Path = Path("runs"),
    daily_cap: int = 90,
    publish_at: str | None = None,
    dry_run: bool = False,
) -> UploadResult:
    """유튜브에 올린다.

    publish_at 을 주면 **지금 올리고 그 시각에 공개**한다 (RFC3339).
    유튜브 서버가 공개를 처리하므로 그 시각에 이 컴퓨터가 꺼져 있어도 된다.
    예약 공개는 비공개 업로드에서만 동작하므로 privacy 를 private 로 강제한다.
    """
    if not video.exists():
        raise UploadError(f"업로드할 영상이 없습니다: {video}")

    state_path, state = _quota_state(Path(state_dir))
    if state["count"] >= daily_cap:
        raise UploadError(
            f"오늘 YouTube 업로드 한도({daily_cap}회)에 도달했습니다. "
            f"videos.insert 는 전용 일일 버킷을 씁니다 — 내일 다시 시도하세요."
        )

    # 제목은 100자, 설명은 5000자 제한.
    title = title[:100]
    description = description[:5000]

    when = _rfc3339(publish_at) if publish_at else None
    if when:
        privacy = "private"        # 예약 공개는 비공개 업로드에서만 된다

    if dry_run:
        extra = f", {when} 에 공개 예약" if when else ""
        print(f"  [dry-run] YouTube 업로드 생략: {title!r} ({privacy}{extra})")
        return UploadResult("dry-run", "https://youtube.com/shorts/dry-run")

    _, _, _, build, MediaFileUpload = _require_libs()
    youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": (tags or [])[:15],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    if when:
        body["status"]["publishAt"] = when
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True,
                            mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"    업로드 {int(status.progress() * 100)}%")

    state["count"] += 1
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")

    video_id = response["id"]
    return UploadResult(video_id, f"https://youtube.com/shorts/{video_id}")
