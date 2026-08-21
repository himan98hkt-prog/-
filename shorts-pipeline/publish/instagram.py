"""Instagram Graph API 로 Reels 업로드.

3단계다:
  1) 컨테이너 생성  POST /{ig-user-id}/media  (media_type=REELS, video_url=...)
  2) 상태 폴링      GET  /{container-id}?fields=status_code
  3) 발행           POST /{ig-user-id}/media_publish

제약 (2026-08 기준):
  * 로컬 파일을 직접 못 올린다. 반드시 '공개적으로 접근 가능한 URL' 이어야 한다.
  * API 발행은 24시간 롤링 윈도로 제한된다(문서상 50~100건).
    실사용량은 /{ig-user-id}/content_publishing_limit 로 조회한다.
  * 프로페셔널(비즈니스/크리에이터) 계정 + 연결된 페이스북 페이지가 필요하다.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v21.0"
_FINISHED = "FINISHED"
_ERROR_STATES = {"ERROR", "EXPIRED"}


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


def publishing_limit() -> dict:
    """남은 발행 가능 횟수를 조회한다."""
    user_id, token = _creds()
    resp = requests.get(
        f"{GRAPH}/{user_id}/content_publishing_limit",
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
        f"{GRAPH}/{user_id}/media",
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
            f"{GRAPH}/{container_id}",
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
        f"{GRAPH}/{user_id}/media_publish",
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
        f"{GRAPH}/{media_id}",
        params={"fields": "permalink", "access_token": token},
        timeout=60,
    )
    if link.status_code < 400:
        permalink = link.json().get("permalink", "")
    return UploadResult(media_id, permalink)
