"""YouTube Data API 할당량 정책 계층.

이 모듈이 존재하는 이유
----------------------
예전 코드는 ``videos.insert = 1,600 유닛``, ``하루 10,000 / 1,600 = 6건`` 을
**상수로 박아** 두고 그 숫자를 사용자에게 안내했다. 그 가정은 2026년 정책에서
깨졌다. Google 은 granular quota 로 옮겨 가면서 ``videos.insert`` 와
``search.list`` 를 **각각 전용 버킷**으로 분리했고, 두 버킷 모두 호출당 1 유닛에
기본 일일 100 호출이다. 나머지 메서드만 기존 10,000 유닛 공용 버킷을 쓴다.

숫자가 또 바뀔 수 있으므로 여기서는 두 가지를 지킨다.

1. **하드코딩하지 않는다.** 정책은 :class:`QuotaPolicy` 값이고 환경변수로
   덮어쓸 수 있다. 코드 상수가 아니라 설정 계층이다.
2. **API 응답이 최종 진실이다.** 이 정책값은 사전 예산 계산과 안내 문구에만
   쓴다. 실제 한도 판정은 언제나 API 가 돌려주는 ``quotaExceeded`` /
   ``uploadLimitExceeded`` 오류로 한다. 정책값이 낙관적이든 비관적이든
   업로드 성공/실패의 근거가 되지 않는다.

정책 출처
--------
- Google 공식 Revision History / Determine Quota Cost / videos.insert 문서
  (https://developers.google.com/youtube/v3/revision_history,
   https://developers.google.com/youtube/v3/determine_quota_cost,
   https://developers.google.com/youtube/v3/docs/videos/insert)
- 확인일: :data:`POLICY_VERIFIED_ON`
- 주의: 아래 기본값은 2026-06-01 시행된 granular quota 기준이다. 이 저장소의
  CI/개발 환경에서는 ``developers.google.com`` 이 egress proxy 에 막혀 1차
  출처를 직접 열어 확인하지 못했다. 정책을 신뢰해야 하는 상황이라면
  :func:`describe_policy` 가 출력하는 출처를 사람이 직접 확인하고
  :data:`POLICY_VERIFIED_ON` 을 갱신하라.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from .utils import get_logger

__all__ = [
    "QuotaBucket",
    "QuotaPolicy",
    "DEFAULT_POLICY",
    "POLICY_VERIFIED_ON",
    "POLICY_SOURCES",
    "ENDPOINT_BUCKETS",
    "load_policy",
    "policy_from_env",
    "describe_policy",
]

LOG = get_logger("quota")

#: 아래 기본값을 사람이 마지막으로 공식 문서와 맞춰 본 날짜 (YYYY-MM-DD).
POLICY_VERIFIED_ON = "2026-09-19"

#: 정책 근거. 숫자를 의심할 때 사람이 직접 열어 볼 주소.
POLICY_SOURCES = (
    "https://developers.google.com/youtube/v3/revision_history",
    "https://developers.google.com/youtube/v3/determine_quota_cost",
    "https://developers.google.com/youtube/v3/docs/videos/insert",
)

#: 엔드포인트 → 버킷 이름. granular quota 로 분리된 둘만 전용 버킷이다.
ENDPOINT_BUCKETS = {
    "videos.insert": "uploads",
    "search": "search",
    "search.list": "search",
}

#: 전용 버킷이 없는 엔드포인트는 모두 공용 버킷을 쓴다.
DEFAULT_BUCKET = "queries"


@dataclass(frozen=True)
class QuotaBucket:
    """할당량 버킷 하나.

    ``daily_units`` 와 ``daily_calls`` 중 채워진 쪽이 그 버킷의 상한을 말한다.
    공용 버킷은 유닛으로, granular 버킷은 호출 수로 세는 편이 실제 정책에
    가깝기 때문에 둘을 함께 둔다.
    """

    name: str
    unit_cost: int = 1
    daily_units: int | None = None
    daily_calls: int | None = None
    note: str = ""

    def calls_allowed(self) -> int | None:
        """이 버킷으로 하루에 가능한 호출 수. 알 수 없으면 ``None``."""
        if self.daily_calls is not None:
            return self.daily_calls
        if self.daily_units is not None and self.unit_cost > 0:
            return self.daily_units // self.unit_cost
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit_cost": self.unit_cost,
            "daily_units": self.daily_units,
            "daily_calls": self.daily_calls,
            "calls_allowed": self.calls_allowed(),
            "note": self.note,
        }


def _default_buckets() -> dict[str, QuotaBucket]:
    """2026-06-01 granular quota 기준 기본값."""
    return {
        "uploads": QuotaBucket(
            name="uploads",
            unit_cost=1,
            daily_calls=100,
            note="videos.insert 전용 버킷 (2026-06-01 분리). 호출당 1 유닛, 기본 하루 100건.",
        ),
        "search": QuotaBucket(
            name="search",
            unit_cost=1,
            daily_calls=100,
            note="search.list 전용 버킷 (2026-06-01 분리). 호출당 1 유닛, 기본 하루 100건.",
        ),
        "queries": QuotaBucket(
            name="queries",
            unit_cost=1,
            daily_units=10_000,
            note="videos.list/channels.list/playlistItems.list 등 나머지 공용 버킷.",
        ),
    }


@dataclass(frozen=True)
class QuotaPolicy:
    """할당량 정책 한 벌.

    이 값은 **안내와 사전 예산용 추정치**다. 한도 초과 판정의 근거가 아니다.
    """

    buckets: Mapping[str, QuotaBucket] = field(default_factory=_default_buckets)
    verified_on: str = POLICY_VERIFIED_ON
    sources: tuple[str, ...] = POLICY_SOURCES
    #: 환경변수로 덮어쓴 항목 이름. 보고서/로그에서 출처를 구분하는 데 쓴다.
    overrides: tuple[str, ...] = ()

    # ── 조회 ──────────────────────────────────────────────────
    def bucket_for(self, endpoint: str) -> QuotaBucket:
        """엔드포인트가 속한 버킷.

        ``"videos.insert"`` 처럼 메서드까지 준 이름과 ``"search"`` 처럼
        엔드포인트만 준 이름을 모두 받는다.
        """
        key = ENDPOINT_BUCKETS.get(endpoint, DEFAULT_BUCKET)
        return self.buckets.get(key) or self.buckets[DEFAULT_BUCKET]

    def cost_for(self, endpoint: str) -> int:
        """호출 1회가 자기 버킷에서 소모하는 유닛."""
        return self.bucket_for(endpoint).unit_cost

    def daily_calls_for(self, endpoint: str) -> int | None:
        """해당 엔드포인트를 하루에 부를 수 있는 횟수. 모르면 ``None``."""
        return self.bucket_for(endpoint).calls_allowed()

    @property
    def upload_unit_cost(self) -> int:
        return self.cost_for("videos.insert")

    @property
    def daily_upload_limit(self) -> int:
        """하루 업로드 상한. 정책에 없으면 보수적으로 1 을 준다."""
        allowed = self.daily_calls_for("videos.insert")
        return allowed if allowed and allowed > 0 else 1

    @property
    def search_unit_cost(self) -> int:
        return self.cost_for("search")

    @property
    def daily_search_limit(self) -> int | None:
        return self.daily_calls_for("search")

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified_on": self.verified_on,
            "sources": list(self.sources),
            "overrides": list(self.overrides),
            "buckets": {name: bucket.to_dict() for name, bucket in self.buckets.items()},
        }


#: 설정을 주지 않았을 때 쓰는 정책.
DEFAULT_POLICY = QuotaPolicy()


def _env_int(env: Mapping[str, str], key: str) -> int | None:
    """환경변수를 양의 정수로 읽는다. 비었거나 이상하면 ``None``."""
    raw = (env.get(key) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        LOG.warning("%s 값을 정수로 읽을 수 없어 무시합니다: %r", key, raw)
        return None
    if value <= 0:
        LOG.warning("%s 는 1 이상이어야 해서 무시합니다: %d", key, value)
        return None
    return value


#: 환경변수 → (버킷, 필드)
_ENV_MAP = {
    "AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": ("uploads", "daily_calls"),
    "AUTOSHORTS_YT_UPLOAD_UNIT_COST": ("uploads", "unit_cost"),
    "AUTOSHORTS_YT_SEARCH_DAILY_CALLS": ("search", "daily_calls"),
    "AUTOSHORTS_YT_SEARCH_UNIT_COST": ("search", "unit_cost"),
    "AUTOSHORTS_YT_QUERIES_DAILY_UNITS": ("queries", "daily_units"),
}


def policy_from_env(env: Mapping[str, str] | None = None) -> QuotaPolicy:
    """환경변수로 기본 정책을 덮어쓴다.

    Google 이 한도를 또 바꾸거나, 프로젝트가 quota 증액을 받았을 때 코드를
    고치지 않고 운영에서 맞출 수 있게 하는 통로다.
    """
    env = os.environ if env is None else env
    buckets = dict(_default_buckets())
    overrides: list[str] = []

    for key, (bucket_name, attr) in _ENV_MAP.items():
        value = _env_int(env, key)
        if value is None:
            continue
        bucket = buckets[bucket_name]
        # 호출 수를 직접 지정하면 유닛 상한은 의미가 없어지므로 비운다.
        if attr == "daily_calls":
            buckets[bucket_name] = replace(bucket, daily_calls=value, daily_units=None)
        else:
            buckets[bucket_name] = replace(bucket, **{attr: value})
        overrides.append(key)

    if overrides:
        LOG.info("할당량 정책을 환경변수로 덮어썼습니다: %s", ", ".join(sorted(overrides)))
    return QuotaPolicy(buckets=buckets, overrides=tuple(sorted(overrides)))


def load_policy(policy: QuotaPolicy | None = None) -> QuotaPolicy:
    """인자로 받은 정책을 그대로 쓰거나, 없으면 환경변수에서 만든다."""
    return policy if policy is not None else policy_from_env()


def describe_policy(policy: QuotaPolicy | None = None) -> str:
    """사람이 읽을 정책 요약. CLI ``autoshorts quota`` 와 보고서에서 쓴다."""
    policy = load_policy(policy)
    lines = [
        "YouTube Data API 할당량 정책 (추정치 — 실제 판정은 API 오류가 최종 진실)",
        f"  확인일: {policy.verified_on}",
    ]
    for name in ("uploads", "search", "queries"):
        bucket = policy.buckets.get(name)
        if bucket is None:
            continue
        allowed = bucket.calls_allowed()
        limit = "알 수 없음" if allowed is None else f"하루 {allowed:,}회"
        units = "" if bucket.daily_units is None else f", 일일 {bucket.daily_units:,} 유닛"
        lines.append(f"  [{name}] 호출당 {bucket.unit_cost} 유닛, {limit}{units}")
        if bucket.note:
            lines.append(f"      {bucket.note}")
    if policy.overrides:
        lines.append(f"  환경변수 덮어쓰기: {', '.join(policy.overrides)}")
    lines.append("  근거:")
    lines.extend(f"    - {url}" for url in policy.sources)
    return "\n".join(lines)
