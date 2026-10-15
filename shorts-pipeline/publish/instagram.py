"""Instagram Graph API 로 Reels 업로드.

3단계다:
  1) 컨테이너 생성  POST /{ig-user-id}/media  (media_type=REELS, video_url=...)
  2) 상태 폴링      GET  /{container-id}?fields=status_code
  3) 발행           POST /{ig-user-id}/media_publish

제약 (2026-08 기준):
  * 로컬 파일을 직접 못 올린다. 반드시 '공개적으로 접근 가능한 URL' 이어야 한다.
  * API 발행은 24시간 롤링 윈도로 제한된다(문서상 50~100건).
    실사용량은 /{ig-user-id}/content_publishing_limit 로 조회한다.
  * 프로페셔널(비즈니스/크리에이터) 계정이어야 한다.
  * 페이스북 페이지는 'Facebook 로그인' 경로에서만 필요하다.
    'Instagram 로그인' 으로 받은 토큰(IGAA...)은 페이지 없이 인스타만으로 된다.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import time
from dataclasses import dataclass
from pathlib import Path

import requests

# 인스타 게시 API 는 두 갈래이고 서버 주소가 다르다. 엔드포인트 모양은 같다.
#   'Facebook 로그인이 있는 Instagram API'  -> 토큰 EAA...   graph.facebook.com
#   'Instagram 로그인이 있는 Instagram API' -> 토큰 IGAA...  graph.instagram.com
# 앞은 페이스북 페이지가 있어야 하고, 뒤는 페이지 없이 인스타만으로 된다.
# 어느 쪽으로 발급받았는지 사용자가 알 필요 없게 토큰을 보고 우리가 고른다.
GRAPH_FB = "https://graph.facebook.com/v21.0"
GRAPH_IG = "https://graph.instagram.com/v21.0"
_IG_LOGIN_PREFIXES = ("IGAA", "IGQ")

_FINISHED = "FINISHED"
_ERROR_STATES = {"ERROR", "EXPIRED"}


def api_base(token: str) -> str:
    """토큰 종류에 맞는 서버 주소."""
    return GRAPH_IG if token.startswith(_IG_LOGIN_PREFIXES) else GRAPH_FB


class UploadError(Exception):
    pass


@dataclass
class UploadResult:
    media_id: str
    permalink: str


def _creds() -> tuple[str, str]:
    user_id = os.getenv("IG_USER_ID")
    token = os.getenv("IG_ACCESS_TOKEN")
    if not user_id or not token:
        raise UploadError(
            "IG_USER_ID / IG_ACCESS_TOKEN 이 설정되지 않았습니다.\n"
            "  1) 인스타그램 계정을 프로페셔널로 전환하고 페이스북 페이지에 연결\n"
            "  2) Meta 앱에 instagram_content_publish 권한 추가\n"
            "  3) 장기 액세스 토큰 발급 후 .env 에 기록"
        )
    return user_id, token


def token_status(token: str = "") -> dict:
    """토큰이 언제 만료되는지. **이게 없으면 60일 뒤 조용히 죽는다.**

    장기 토큰은 60일이면 만료된다. 만료되면 인스타 업로드만 실패하고
    유튜브는 계속 되므로, 며칠에서 몇 주가 지나서야 알아채게 된다.
    남은 날짜를 미리 보여주고, 얼마 안 남았으면 갱신하라고 말한다.

    갱신은 만료 **전에** 해야 한다. 만료된 토큰은 갱신할 수 없고 처음부터
    다시 발급해야 한다. Meta 는 발급 후 24시간이 지나야 갱신을 받아준다.
    """
    token = token or os.getenv("IG_ACCESS_TOKEN", "")
    if not token:
        return {"ok": False, "reason": "토큰이 없습니다."}

    base = api_base(token)
    try:
        resp = requests.get(f"{base}/debug_token",
                            params={"input_token": token, "access_token": token},
                            timeout=20)
    except requests.RequestException as exc:
        return {"ok": False, "reason": f"확인하지 못했습니다 ({exc})"}
    if resp.status_code >= 400:
        return {"ok": False,
                "reason": f"토큰이 거절됐습니다 (HTTP {resp.status_code}). "
                          "만료됐거나 권한이 바뀌었을 수 있습니다."}

    data = (resp.json().get("data") or {})
    expires = data.get("expires_at")
    out: dict = {"ok": bool(data.get("is_valid", True)),
                 "scopes": data.get("scopes") or []}
    if not expires:                      # 0 이면 만료 없음
        out.update({"expires_at": None, "days_left": None,
                    "note": "만료 없음"})
        return out

    when = datetime.fromtimestamp(int(expires), tz=timezone.utc)
    days = (when - datetime.now(timezone.utc)).days
    out.update({
        "expires_at": when.isoformat(timespec="seconds"),
        "days_left": days,
        "note": (f"{days}일 남음" if days > 0 else "만료됨"),
    })
    return out


def refresh_token(token: str = "") -> dict:
    """장기 토큰을 60일 더 연장한다.

    만료된 뒤에는 안 된다. 그래서 남은 날짜를 보고 미리 눌러야 한다.
    """
    token = token or os.getenv("IG_ACCESS_TOKEN", "")
    if not token:
        raise UploadError("IG_ACCESS_TOKEN 이 없습니다.")

    if token.startswith(_IG_LOGIN_PREFIXES):
        url = f"{GRAPH_IG}/refresh_access_token"
        params = {"grant_type": "ig_refresh_token", "access_token": token}
    else:
        # 페이스북 로그인 경로의 장기 토큰은 app_id/secret 이 있어야 연장된다.
        app_id = os.getenv("IG_APP_ID", "")
        secret = os.getenv("IG_APP_SECRET", "")
        if not (app_id and secret):
            raise UploadError(
                "이 토큰을 연장하려면 IG_APP_ID 와 IG_APP_SECRET 이 필요합니다.\n"
                "  Meta 개발자 앱 → 설정 → 기본 설정에서 확인해 [설정] 탭에 넣으세요.\n"
                "  (인스타그램 로그인으로 받은 IGAA... 토큰은 이게 필요 없습니다)")
        url = f"{GRAPH_FB}/oauth/access_token"
        params = {"grant_type": "fb_exchange_token", "client_id": app_id,
                  "client_secret": secret, "fb_exchange_token": token}

    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        raise UploadError(f"연장 요청이 실패했습니다: {exc}") from exc
    if resp.status_code >= 400:
        raise UploadError(
            f"연장이 거절됐습니다 (HTTP {resp.status_code}): {resp.text[:300]}\n"
            "  이미 만료됐다면 연장이 안 됩니다. 새로 발급해야 합니다.")

    body = resp.json()
    fresh = body.get("access_token")
    if not fresh:
        raise UploadError(f"응답에 새 토큰이 없습니다: {body}")
    seconds = int(body.get("expires_in") or 0)
    return {"token": fresh, "days": round(seconds / 86400) if seconds else None}


def publishing_limit() -> dict:
    """남은 발행 가능 횟수를 조회한다."""
    user_id, token = _creds()
    resp = requests.get(
        f"{api_base(token)}/{user_id}/content_publishing_limit",
        params={"fields": "config,quota_usage", "access_token": token},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise UploadError(f"발행 한도 조회 실패: {resp.text[:300]}")
    return resp.json()


def upload(
    video_url: str,
    *,
    caption: str,
    share_to_feed: bool = True,
    poll_interval: float = 5.0,
    timeout: float = 600.0,
    dry_run: bool = False,
) -> UploadResult:
    """공개 URL 의 mp4 를 릴스로 발행한다."""
    if not video_url.startswith("http"):
        raise UploadError(
            f"인스타그램은 공개 URL 만 받습니다 (받은 값: {video_url}).\n"
            "  최종 mp4 를 S3/R2/정적 호스팅에 올린 뒤 그 URL 을 넘기세요."
        )
    caption = caption[:2200]  # 캡션 상한

    if dry_run:
        print(f"  [dry-run] Instagram 발행 생략: {video_url}")
        return UploadResult("dry-run", "https://instagram.com/reel/dry-run")

    user_id, token = _creds()

    # 1) 컨테이너 생성
    resp = requests.post(
        f"{api_base(token)}/{user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
            "access_token": token,
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        raise UploadError(f"컨테이너 생성 실패: {resp.text[:400]}")
    container_id = resp.json().get("id")
    if not container_id:
        raise UploadError(f"컨테이너 ID 를 받지 못했습니다: {resp.text[:300]}")

    # 2) 인코딩 완료까지 폴링
    started = time.time()
    while True:
        st = requests.get(
            f"{api_base(token)}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        )
        body = st.json()
        code = body.get("status_code")
        if code == _FINISHED:
            break
        if code in _ERROR_STATES:
            raise UploadError(f"인스타그램 인코딩 실패 ({code}): {body.get('status')}")
        if time.time() - started > timeout:
            raise UploadError(
                f"컨테이너 {container_id} 가 {timeout:.0f}초 안에 준비되지 않았습니다."
            )
        time.sleep(poll_interval)

    # 3) 발행
    pub = requests.post(
        f"{api_base(token)}/{user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=120,
    )
    if pub.status_code >= 400:
        text = pub.text[:400]
        hint = ""
        if '"code":9' in text or "limit" in text.lower():
            hint = "\n  24시간 발행 한도에 걸렸습니다. content_publishing_limit 을 확인하세요."
        raise UploadError(f"발행 실패: {text}{hint}")
    media_id = pub.json().get("id", "")

    permalink = ""
    link = requests.get(
        f"{api_base(token)}/{media_id}",
        params={"fields": "permalink", "access_token": token},
        timeout=60,
    )
    if link.status_code < 400:
        permalink = link.json().get("permalink", "")
    return UploadResult(media_id, permalink)
