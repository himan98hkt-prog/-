"""YouTube API 할당량 정책 계층.

이 모듈이 존재하는 이유
-----------------------
초기 구현은 ``videos.insert = 1,600 유닛`` / ``10,000 ÷ 1,600 = 하루 6건`` 을
코드 상수로 박아 두고, 그 값으로 업로드를 **사전 차단**했다. 두 가지가 잘못됐다.

1. 숫자 자체가 구식이다. ``docs/COMMERCIALIZATION_ROADMAP.md`` 는 2026-09-14
   기준 공식 Quota Calculator 를 인용해 ``videos.insert`` 가 **별도의 Video
   Uploads 버킷**에서 ``1 call = 1 unit``, 기본 **하루 100건**으로 집계된다고
   기록한다.
2. 더 중요한 건 구조다. Google 은 할당량 정책을 예고 없이 바꾸고 프로젝트마다
   한도가 다르다. 클라이언트가 계산한 추정치를 **진실로 취급하면** 정책이 바뀌는
   순간 조용히 틀린다.

그래서 이 모듈은 할당량을 **설정 가능한 정책**으로 다루고, 최종 판정은 항상
**API 응답**에 맡긴다. 여기 있는 숫자는 "차단 기준"이 아니라 "사용자에게 보여줄
안내와 느슨한 사전 가드"일 뿐이다.

재검증 필요
-----------
아래 기본값은 위 로드맵 문서의 조사 결과를 옮긴 것이며, **개발 환경의 egress
정책상 공식 문서를 직접 확인하지 못했다**. 실제 값은 배포 전에
``docs/PHASE0_PRODUCTIZATION_REPORT.md`` 의 수동 확인 절차로 검증해야 한다.

  https://developers.google.com/youtube/v3/determine_quota_cost
  https://developers.google.com/youtube/v3/docs/videos/insert
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Any

from .utils import get_logger

__all__ = [
    "QuotaPolicy",
    "UploadQuotaPolicy",
    "SearchQuotaPolicy",
    "load_quota_policy",
    "DEFAULT_POLICY",
    "QUOTA_SOURCE_NOTE",
    "QUOTA_DOC_URLS",
]

LOG = get_logger("quota")

QUOTA_DOC_URLS = (
    "https://developers.google.com/youtube/v3/determine_quota_cost",
    "https://developers.google.com/youtube/v3/docs/videos/insert",
)

QUOTA_SOURCE_NOTE = (
    "할당량 값은 프로젝트마다 다르고 Google 정책 변경에 따라 바뀝니다. "
    "여기 표시되는 수치는 안내용 기본값이며, 실제 한도는 API 응답이 최종 기준입니다."
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        LOG.warning("환경변수 %s 값을 정수로 읽지 못해 기본값 %s 를 씁니다: %r", name, default, raw)
        return default
    if value <= 0:
        LOG.warning("환경변수 %s 는 양수여야 합니다. 기본값 %s 를 씁니다: %r", name, default, raw)
        return default
    return value


@dataclass(frozen=True)
class UploadQuotaPolicy:
    """업로드(``videos.insert``) 할당량 정책.

    ``videos.insert`` 는 일반 쿼리 할당량과 **다른 버킷**에서 집계되므로
    "10,000 유닛을 1,600으로 나눈다" 는 식의 계산을 하지 않는다.
    """

    # 호출 1건이 소모하는 유닛 (Video Uploads 버킷 기준)
    cost_per_call: int = 1
    # 하루 업로드 건수 기본 상한 (프로젝트별로 다를 수 있음)
    daily_uploads: int = 100
    # 사전 가드를 켤지 여부. False 면 API 응답만으로 판단한다.
    enforce_local_guard: bool = True

    @property
    def daily_limit(self) -> int:
        return self.daily_uploads


@dataclass(frozen=True)
class SearchQuotaPolicy:
    """조회(``search.list`` 등) 할당량 정책."""

    daily_units: int = 10_000
    search_cost: int = 100
    videos_cost: int = 1
    channels_cost: int = 1
    playlist_items_cost: int = 1


@dataclass(frozen=True)
class QuotaPolicy:
    """업로드/조회 정책 묶음."""

    upload: UploadQuotaPolicy = UploadQuotaPolicy()
    search: SearchQuotaPolicy = SearchQuotaPolicy()
    verified: bool = False           # 공식 문서 대조를 마쳤는지
    source: str = "docs/COMMERCIALIZATION_ROADMAP.md (2026-09-14 조사, 미재검증)"

    def describe_upload_limit(self) -> str:
        """사용자에게 보여줄 업로드 한도 설명."""
        text = f"기본 정책상 하루 {self.upload.daily_uploads}건"
        if not self.verified:
            text += " (미검증 기본값)"
        return text

    def to_dict(self) -> dict[str, Any]:
        return {
            "upload": {f.name: getattr(self.upload, f.name) for f in fields(self.upload)},
            "search": {f.name: getattr(self.search, f.name) for f in fields(self.search)},
            "verified": self.verified,
            "source": self.source,
        }


def load_quota_policy() -> QuotaPolicy:
    """환경변수로 덮어쓸 수 있는 정책을 만든다.

    운영에서 실제 한도가 다르면 코드 수정 없이 아래 값만 바꾸면 된다.

      AUTOSHORTS_UPLOAD_COST_PER_CALL
      AUTOSHORTS_UPLOAD_DAILY_LIMIT
      AUTOSHORTS_UPLOAD_LOCAL_GUARD   (0/false 면 사전 가드 해제)
      AUTOSHORTS_SEARCH_DAILY_UNITS
      AUTOSHORTS_QUOTA_VERIFIED       (1/true 면 공식 확인 완료로 표시)
    """
    guard_raw = os.environ.get("AUTOSHORTS_UPLOAD_LOCAL_GUARD", "")
    enforce = str(guard_raw).strip().lower() not in {"0", "false", "no", "off"}

    verified_raw = os.environ.get("AUTOSHORTS_QUOTA_VERIFIED", "")
    verified = str(verified_raw).strip().lower() in {"1", "true", "yes", "on"}

    upload = UploadQuotaPolicy(
        cost_per_call=_env_int("AUTOSHORTS_UPLOAD_COST_PER_CALL", 1),
        daily_uploads=_env_int("AUTOSHORTS_UPLOAD_DAILY_LIMIT", 100),
        enforce_local_guard=enforce,
    )
    search = SearchQuotaPolicy(
        daily_units=_env_int("AUTOSHORTS_SEARCH_DAILY_UNITS", 10_000),
    )
    source = (
        "환경변수 재정의"
        if os.environ.get("AUTOSHORTS_UPLOAD_DAILY_LIMIT")
        else "docs/COMMERCIALIZATION_ROADMAP.md (2026-09-14 조사, 미재검증)"
    )
    return QuotaPolicy(upload=upload, search=search, verified=verified, source=source)


DEFAULT_POLICY = QuotaPolicy()
