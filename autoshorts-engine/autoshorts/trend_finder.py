"""Module E — Trend Finder.

키워드나 채널을 받아 YouTube Data API v3 로 최근 업로드 중
**구독자 대비 조회수(V/S Ratio)** 가 높은 '떡상 영상'을 찾아 URL 목록으로 돌려준다.
1위 영상 URL 을 그대로 :mod:`autoshorts.pipeline` 에 넘기면 쇼츠까지 자동 완성된다.

무료 할당량(하루 10,000 유닛)을 아끼도록 호출을 배치하고, 소모한 유닛을
추적해 알려준다. 새 서드파티 의존성 없이 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Sequence

from .utils import get_logger

__all__ = [
    "TrendVideo",
    "YouTubeClient",
    "YouTubeApiError",
    "QuotaExceededError",
    "InvalidApiKeyError",
    "ChannelNotFoundError",
    "find_trending",
    "parse_iso8601_duration",
    "parse_channel_reference",
    "score_video",
    "watch_url",
    "extract_video_id",
    "API_COSTS",
]

LOG = get_logger("trend")

API_ROOT = "https://www.googleapis.com/youtube/v3"

# 엔드포인트별 할당량 소모(유닛). 무료 한도는 하루 10,000 유닛이다.
# search.list 만 유독 비싸서(100) 채널 모드를 쓰면 수백 배 저렴하다.
API_COSTS = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}

# 한 번에 조회할 수 있는 id 개수 상한 (videos.list / channels.list 공통)
MAX_IDS_PER_CALL = 50
MAX_RESULTS_PER_PAGE = 50

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)
_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")

# 쇼츠로 쓸 수 없는 원본을 걸러내는 기본값
DEFAULT_MIN_DURATION = 180.0     # 3분 미만은 하이라이트를 뽑을 여지가 적다
DEFAULT_MIN_SUBSCRIBERS = 1000   # 구독자 극소 채널은 V/S 가 무의미하게 폭증한다
DEFAULT_MIN_VIEWS = 1000


class YouTubeApiError(RuntimeError):
    """YouTube Data API 호출 실패."""


class QuotaExceededError(YouTubeApiError):
    """일일 할당량 초과."""


class InvalidApiKeyError(YouTubeApiError):
    """API 키가 없거나 잘못됐거나 YouTube Data API 가 비활성화됨."""


class ChannelNotFoundError(YouTubeApiError):
    """채널을 찾지 못함."""


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


_VIDEO_ID_RE = re.compile(r"^[\w-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """유튜브 URL 에서 영상 id 를 뽑는다. 못 찾으면 빈 문자열.

    ``watch?v=``, ``youtu.be/``, ``/shorts/``, ``/embed/`` 를 인식하고,
    11자리 id 를 그대로 준 경우도 받아들인다.
    """
    value = str(url_or_id or "").strip()
    if not value:
        return ""
    if _VIDEO_ID_RE.match(value) and "/" not in value:
        return value

    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return ""
    host = (parsed.netloc or "").lower()
    if "youtu.be" in host:
        candidate = (parsed.path or "").strip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    if "youtube.com" not in host:
        return ""

    query = urllib.parse.parse_qs(parsed.query or "")
    if query.get("v"):
        candidate = query["v"][0]
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    segments = [s for s in (parsed.path or "").split("/") if s]
    if len(segments) >= 2 and segments[0] in {"shorts", "embed", "v", "live"}:
        candidate = segments[1]
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    return ""


@dataclass
class TrendVideo:
    """급상승 후보 영상 하나."""

    video_id: str
    title: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: datetime | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    subscriber_count: int = 0
    duration_seconds: float = 0.0
    score: float = 0.0
    rank: int = 0

    @property
    def url(self) -> str:
        return watch_url(self.video_id)

    @property
    def vs_ratio(self) -> float:
        """구독자 대비 조회수. 1.0 이면 구독자 수만큼 조회된 것."""
        if self.subscriber_count <= 0:
            return 0.0
        return self.view_count / self.subscriber_count

    @property
    def age_hours(self) -> float:
        if not self.published_at:
            return 0.0
        delta = datetime.now(timezone.utc) - self.published_at
        return max(delta.total_seconds() / 3600.0, 0.0)

    @property
    def views_per_day(self) -> float:
        hours = self.age_hours
        if hours < 1.0:
            return float(self.view_count)
        return self.view_count / (hours / 24.0)

    @property
    def engagement_rate(self) -> float:
        """조회수 대비 좋아요 비율."""
        if self.view_count <= 0:
            return 0.0
        return self.like_count / self.view_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "channel_title": self.channel_title,
            "channel_id": self.channel_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "age_hours": round(self.age_hours, 1),
            "view_count": self.view_count,
            "subscriber_count": self.subscriber_count,
            "vs_ratio": round(self.vs_ratio, 2),
            "views_per_day": round(self.views_per_day, 1),
            "like_count": self.like_count,
            "engagement_rate": round(self.engagement_rate, 4),
            "duration_seconds": round(self.duration_seconds, 1),
            "score": round(self.score, 3),
        }


def parse_iso8601_duration(text: str | None) -> float:
    """``PT1H2M3S`` 형태의 ISO 8601 기간을 초로 바꾼다.

    파싱할 수 없으면 0.0 을 돌려준다(길이 필터에서 걸러진다).
    """
    if not text:
        return 0.0
    match = _DURATION_RE.match(str(text).strip())
    if not match:
        return 0.0
    parts = match.groupdict()
    return (
        float(parts["days"] or 0) * 86400
        + float(parts["hours"] or 0) * 3600
        + float(parts["minutes"] or 0) * 60
        + float(parts["seconds"] or 0)
    )


def _parse_published(text: str | None) -> datetime | None:
    if not text:
        return None
    value = str(text).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_channel_reference(text: str) -> tuple[str, str]:
    """입력이 채널을 가리키는지 판별한다.

    반환값은 ``("channel_id"|"handle"|"username"|"query", 값)``.
    URL, ``@핸들``, 원시 채널 ID(``UC...``) 를 인식하고, 그 밖은 검색어로 본다.
    """
    value = str(text or "").strip()
    if not value:
        return ("query", "")

    if _CHANNEL_ID_RE.match(value):
        return ("channel_id", value)
    if value.startswith("@") and len(value) > 1:
        return ("handle", value)

    if "://" in value or value.lower().startswith(("youtube.com", "www.youtube.com", "m.youtube.com")):
        candidate = value if "://" in value else f"https://{value}"
        parsed = urllib.parse.urlparse(candidate)
        host = (parsed.netloc or "").lower()
        if "youtube.com" not in host and "youtu.be" not in host:
            return ("query", value)
        segments = [s for s in (parsed.path or "").split("/") if s]
        if not segments:
            return ("query", value)
        head = segments[0]
        if head == "channel" and len(segments) > 1:
            return ("channel_id", segments[1])
        if head in {"c", "user"} and len(segments) > 1:
            return ("username", segments[1])
        if head.startswith("@"):
            return ("handle", head)
        return ("query", value)

    return ("query", value)


def score_video(
    vs_ratio: float,
    age_hours: float,
    window_hours: float,
    engagement_rate: float = 0.0,
) -> float:
    """급상승 점수.

    V/S 비율을 뼈대로, 같은 비율이면 최근 것을 위로 올린다.

    - ``freshness``: 탐색 창 안에서 오래될수록 최대 70% 까지 감점.
      영상은 시간이 지나면 조회수가 쌓이므로, 보정 없이 V/S 만 보면
      오래된 영상이 유리해진다.
    - ``engagement``: 좋아요 비율로 최대 +20% 가산. 조회수만 튄 영상과
      실제로 반응이 좋은 영상을 갈라 준다.
    """
    if vs_ratio <= 0:
        return 0.0
    window_hours = max(window_hours, 1.0)
    ratio_of_window = min(max(age_hours, 0.0) / window_hours, 1.0)
    freshness = max(0.3, 1.0 - ratio_of_window * 0.7)
    engagement_boost = 1.0 + min(max(engagement_rate, 0.0), 0.2)
    return vs_ratio * freshness * engagement_boost


def _default_transport(url: str, timeout: float) -> tuple[int, bytes]:
    """표준 라이브러리 HTTP GET. 테스트에서는 이 함수를 대체 주입한다."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise YouTubeApiError(f"YouTube API 에 연결하지 못했습니다: {exc.reason}") from exc


class YouTubeClient:
    """YouTube Data API v3 얇은 클라이언트.

    ``transport`` 는 ``(url, timeout) -> (status, body)`` 콜러블이며,
    테스트에서 네트워크 없이 대체할 수 있다.
    """

    def __init__(
        self,
        api_key: str,
        *,
        transport: Callable[[str, float], tuple[int, bytes]] | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not api_key:
            raise InvalidApiKeyError(
                "YOUTUBE_API_KEY 가 없습니다. "
                "https://console.cloud.google.com 에서 YouTube Data API v3 를 켜고 키를 발급해 "
                ".env 에 넣으세요."
            )
        self._api_key = api_key
        self._transport = transport or _default_transport
        self._timeout = timeout
        self.quota_used = 0

    # ── 저수준 ────────────────────────────────────────────────
    def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        query = {k: v for k, v in params.items() if v not in (None, "")}
        query["key"] = self._api_key
        url = f"{API_ROOT}/{endpoint}?{urllib.parse.urlencode(query)}"

        # 키가 새지 않도록 URL 대신 엔드포인트와 파라미터만 남긴다.
        LOG.debug("YouTube API %s %s", endpoint, {k: v for k, v in query.items() if k != "key"})
        status, body = self._transport(url, self._timeout)
        self.quota_used += API_COSTS.get(endpoint, 1)

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise YouTubeApiError(f"API 응답을 해석하지 못했습니다 (HTTP {status})") from exc

        if status >= 400:
            raise self._to_error(status, payload)
        return payload

    @staticmethod
    def _to_error(status: int, payload: dict[str, Any]) -> YouTubeApiError:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        reasons = {item.get("reason", "") for item in error.get("errors", []) or []}
        message = error.get("message") or f"HTTP {status}"

        if "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons or "rateLimitExceeded" in reasons:
            return QuotaExceededError(
                "YouTube Data API 일일 할당량(무료 10,000 유닛)을 초과했습니다. "
                "내일 초기화되며, 채널 모드(--channel)는 검색보다 100배 저렴합니다. "
                f"(원문: {message})"
            )
        if status in (400, 401) or "keyInvalid" in reasons or "badRequest" in reasons:
            return InvalidApiKeyError(
                f"API 키가 잘못됐거나 YouTube Data API v3 가 비활성 상태입니다. (원문: {message})"
            )
        if status == 403:
            return YouTubeApiError(f"API 접근이 거부됐습니다. (원문: {message})")
        if status == 404:
            return YouTubeApiError(f"대상을 찾을 수 없습니다. (원문: {message})")
        return YouTubeApiError(f"YouTube API 오류 (HTTP {status}): {message}")

    # ── 고수준 ────────────────────────────────────────────────
    def search_video_ids(
        self,
        query: str,
        *,
        published_after: datetime,
        max_results: int = 50,
        order: str = "viewCount",
        region_code: str | None = None,
        relevance_language: str | None = None,
    ) -> list[str]:
        """키워드로 영상 id 를 모은다. (호출당 100 유닛)"""
        collected: list[str] = []
        page_token: str | None = None
        while len(collected) < max_results:
            payload = self._get(
                "search",
                part="id",
                q=query,
                type="video",
                order=order,
                maxResults=min(MAX_RESULTS_PER_PAGE, max_results - len(collected)),
                publishedAfter=_rfc3339(published_after),
                regionCode=region_code,
                relevanceLanguage=relevance_language,
                pageToken=page_token,
            )
            for item in payload.get("items", []):
                video_id = (item.get("id") or {}).get("videoId")
                if video_id:
                    collected.append(video_id)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return collected[:max_results]

    def resolve_channel_id(self, reference: str) -> str:
        """``@핸들``/``UC...``/URL/채널명을 채널 id 로 바꾼다."""
        kind, value = parse_channel_reference(reference)
        if kind == "channel_id":
            return value

        if kind == "handle":
            payload = self._get("channels", part="id", forHandle=value)
            items = payload.get("items") or []
            if items:
                return items[0]["id"]
        elif kind == "username":
            payload = self._get("channels", part="id", forUsername=value)
            items = payload.get("items") or []
            if items:
                return items[0]["id"]

        # 마지막 수단: 채널 검색 (100 유닛)
        payload = self._get("search", part="snippet", q=value or reference, type="channel", maxResults=1)
        items = payload.get("items") or []
        if not items:
            raise ChannelNotFoundError(f"채널을 찾지 못했습니다: {reference!r}")
        channel_id = (items[0].get("id") or {}).get("channelId") or items[0].get("snippet", {}).get("channelId")
        if not channel_id:
            raise ChannelNotFoundError(f"채널 id 를 확인하지 못했습니다: {reference!r}")
        return channel_id

    def uploads_playlist_id(self, channel_id: str) -> str:
        payload = self._get("channels", part="contentDetails", id=channel_id)
        items = payload.get("items") or []
        if not items:
            raise ChannelNotFoundError(f"채널을 찾지 못했습니다: {channel_id!r}")
        playlist = (
            items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        if not playlist:
            raise ChannelNotFoundError(f"업로드 재생목록을 찾지 못했습니다: {channel_id!r}")
        return playlist

    def recent_upload_ids(
        self,
        playlist_id: str,
        *,
        published_after: datetime,
        max_results: int = 50,
    ) -> list[str]:
        """업로드 재생목록에서 기간 내 영상 id 를 모은다. (페이지당 1 유닛)

        업로드 재생목록은 최신순이라 기간을 벗어나면 즉시 멈춘다.
        """
        collected: list[str] = []
        page_token: str | None = None
        while len(collected) < max_results:
            payload = self._get(
                "playlistItems",
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=min(MAX_RESULTS_PER_PAGE, max_results - len(collected)),
                pageToken=page_token,
            )
            reached_old = False
            for item in payload.get("items", []):
                details = item.get("contentDetails") or {}
                published = _parse_published(details.get("videoPublishedAt"))
                if published and published < published_after:
                    reached_old = True
                    continue
                video_id = details.get("videoId")
                if video_id:
                    collected.append(video_id)
            page_token = payload.get("nextPageToken")
            if reached_old or not page_token:
                break
        return collected[:max_results]

    def fetch_videos(self, video_ids: Sequence[str]) -> list[dict[str, Any]]:
        """영상 상세를 50개씩 묶어 조회한다. (호출당 1 유닛)"""
        items: list[dict[str, Any]] = []
        for chunk in _chunks(list(dict.fromkeys(video_ids)), MAX_IDS_PER_CALL):
            payload = self._get(
                "videos", part="snippet,statistics,contentDetails,liveStreamingDetails", id=",".join(chunk)
            )
            items.extend(payload.get("items", []))
        return items

    def fetch_channels(self, channel_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
        """채널 통계를 50개씩 묶어 조회한다. (호출당 1 유닛)"""
        out: dict[str, dict[str, Any]] = {}
        for chunk in _chunks(list(dict.fromkeys(channel_ids)), MAX_IDS_PER_CALL):
            payload = self._get("channels", part="statistics,snippet", id=",".join(chunk))
            for item in payload.get("items", []):
                out[item.get("id", "")] = item
        return out


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _rfc3339(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_candidates(
    videos: Iterable[dict[str, Any]],
    channels: dict[str, dict[str, Any]],
) -> list[TrendVideo]:
    """API 응답을 :class:`TrendVideo` 목록으로 바꾼다(필터링 전)."""
    out: list[TrendVideo] = []
    for item in videos:
        video_id = item.get("id")
        if not video_id:
            continue
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        details = item.get("contentDetails") or {}
        channel_id = snippet.get("channelId", "")
        channel = channels.get(channel_id) or {}
        channel_stats = channel.get("statistics") or {}

        # 구독자 수 비공개 채널은 V/S 를 계산할 수 없다.
        subscribers = 0 if channel_stats.get("hiddenSubscriberCount") else _to_int(
            channel_stats.get("subscriberCount")
        )

        out.append(
            TrendVideo(
                video_id=video_id,
                title=snippet.get("title", ""),
                channel_id=channel_id,
                channel_title=snippet.get("channelTitle", "") or channel.get("snippet", {}).get("title", ""),
                published_at=_parse_published(snippet.get("publishedAt")),
                view_count=_to_int(stats.get("viewCount")),
                like_count=_to_int(stats.get("likeCount")),
                comment_count=_to_int(stats.get("commentCount")),
                subscriber_count=subscribers,
                duration_seconds=parse_iso8601_duration(details.get("duration")),
            )
        )
    return out


def filter_and_rank(
    candidates: Iterable[TrendVideo],
    *,
    window_hours: float,
    min_vs_ratio: float = 1.0,
    min_subscribers: int = DEFAULT_MIN_SUBSCRIBERS,
    min_views: int = DEFAULT_MIN_VIEWS,
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float | None = None,
    limit: int = 10,
) -> list[TrendVideo]:
    """조건에 맞는 영상만 남기고 급상승 점수순으로 정렬한다."""
    kept: list[TrendVideo] = []
    for video in candidates:
        if video.subscriber_count < max(min_subscribers, 1):
            continue                                    # 비공개이거나 극소 채널
        if video.view_count < min_views:
            continue
        if video.duration_seconds < min_duration:
            continue                                    # 이미 쇼츠이거나 너무 짧다
        if max_duration is not None and video.duration_seconds > max_duration:
            continue
        if video.vs_ratio < min_vs_ratio:
            continue
        video.score = score_video(
            video.vs_ratio, video.age_hours, window_hours, video.engagement_rate
        )
        kept.append(video)

    kept.sort(key=lambda v: (-v.score, -v.view_count))
    for index, video in enumerate(kept[:limit], start=1):
        video.rank = index
    return kept[:limit]


def find_trending(
    target: str,
    *,
    api_key: str,
    days: float = 14.0,
    limit: int = 10,
    max_candidates: int = 50,
    min_vs_ratio: float = 1.0,
    min_subscribers: int = DEFAULT_MIN_SUBSCRIBERS,
    min_views: int = DEFAULT_MIN_VIEWS,
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float | None = None,
    as_channel: bool | None = None,
    order: str = "viewCount",
    region_code: str | None = None,
    relevance_language: str | None = None,
    client: YouTubeClient | None = None,
) -> tuple[list[TrendVideo], int]:
    """키워드 또는 채널에서 급상승 영상을 찾는다.

    ``as_channel`` 이 None 이면 입력 형태로 자동 판별한다(``@핸들``,
    채널 URL, ``UC...`` 는 채널로 본다).

    반환값은 ``(영상 목록, 소모한 할당량 유닛)``.
    """
    if not str(target or "").strip():
        raise ValueError("검색어 또는 채널을 입력하세요.")

    client = client or YouTubeClient(api_key)
    window_hours = max(days, 0.1) * 24.0
    published_after = datetime.now(timezone.utc) - timedelta(days=max(days, 0.1))

    kind, _ = parse_channel_reference(target)
    treat_as_channel = as_channel if as_channel is not None else kind != "query"

    if treat_as_channel:
        channel_id = client.resolve_channel_id(target)
        playlist_id = client.uploads_playlist_id(channel_id)
        video_ids = client.recent_upload_ids(
            playlist_id, published_after=published_after, max_results=max_candidates
        )
        LOG.info("채널 %s 의 최근 %.0f일 업로드 %d개", channel_id, days, len(video_ids))
    else:
        video_ids = client.search_video_ids(
            target,
            published_after=published_after,
            max_results=max_candidates,
            order=order,
            region_code=region_code,
            relevance_language=relevance_language,
        )
        LOG.info("키워드 %r 검색 결과 %d개", target, len(video_ids))

    if not video_ids:
        return [], client.quota_used

    videos = client.fetch_videos(video_ids)
    # 라이브/예정 방송은 다운로드 대상이 아니다.
    videos = [
        item for item in videos
        if (item.get("snippet") or {}).get("liveBroadcastContent", "none") in ("none", "", None)
    ]
    channel_ids = [ (item.get("snippet") or {}).get("channelId", "") for item in videos ]
    channels = client.fetch_channels([cid for cid in channel_ids if cid])

    candidates = build_candidates(videos, channels)
    ranked = filter_and_rank(
        candidates,
        window_hours=window_hours,
        min_vs_ratio=min_vs_ratio,
        min_subscribers=min_subscribers,
        min_views=min_views,
        min_duration=min_duration,
        max_duration=max_duration,
        limit=limit,
    )
    LOG.info(
        "후보 %d개 중 조건 통과 %d개 · 할당량 %d 유닛 사용",
        len(candidates), len(ranked), client.quota_used,
    )
    return ranked, client.quota_used
