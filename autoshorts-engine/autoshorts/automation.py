"""예약 실행용 자동화 흐름.

``급상승 탐색 → 쇼츠 제작 → 업로드`` 를 한 번에 수행한다. 예약으로 반복
실행되는 것을 전제로 하므로 다음을 지킨다.

- 이미 처리한 원본은 건너뛴다(이력 대조).
- 하루 업로드 할당량(무료 한도 6건)을 넘기지 않는다.
- 업로드 중 하나가 실패해도 나머지는 계속하고, 결과를 모아 보고한다.
- 무인 실행이므로 브라우저 인증 창을 띄우지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from . import downloader, pipeline, trend_finder, uploader
from .config import Settings
from .state import HistoryStore
from .uploader import DAILY_UPLOAD_LIMIT, UploadRequest, UploadResult
from .utils import get_logger

__all__ = ["AutoOptions", "AutoResult", "run_auto", "resolve_target", "build_upload_request"]

LOG = get_logger("automation")


@dataclass
class AutoOptions:
    """자동 실행 옵션."""

    upload: bool = False
    privacy: str = "private"
    publish_at: datetime | None = None
    upload_count: int | None = None          # None 이면 만들어진 전부(할당량 내에서)
    tags: list[str] = field(default_factory=list)
    category_id: str = "22"
    made_for_kids: bool = False
    skip_processed: bool = True
    trend_days: float = 14.0
    trend_min_vs: float = 1.0
    trend_min_subscribers: int = 1000
    trend_min_duration: float = 180.0
    as_channel: bool | None = None
    dry_run_upload: bool = False             # 업로드 직전까지만 수행


@dataclass
class AutoResult:
    """자동 실행 결과."""

    target: str = ""
    source_url: str = ""
    source_id: str = ""
    title: str = ""
    candidates: list[Any] = field(default_factory=list)
    renders: list[Any] = field(default_factory=list)
    uploads: list[UploadResult] = field(default_factory=list)
    upload_errors: list[str] = field(default_factory=list)
    skipped_reason: str = ""
    quota_used: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.renders) and not self.skipped_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "source_url": self.source_url,
            "source_id": self.source_id,
            "title": self.title,
            "rendered": [str(r.output_path) for r in self.renders],
            "uploads": [u.to_dict() for u in self.uploads],
            "upload_errors": self.upload_errors,
            "skipped_reason": self.skipped_reason,
            "quota_used": self.quota_used,
        }


def resolve_target(target: str) -> tuple[str, str]:
    """입력이 '바로 처리할 대상'인지 '탐색할 키워드'인지 가른다.

    반환값은 ``("direct"|"search", 값)``.
    영상 URL 이나 로컬 파일이면 탐색 없이 바로 처리한다.
    """
    value = str(target or "").strip()
    if not value:
        raise ValueError("대상을 입력하세요.")

    if trend_finder.extract_video_id(value):
        return ("direct", value)
    if not downloader.is_url(value) and Path(value).expanduser().exists():
        return ("direct", value)
    if downloader.is_url(value) and trend_finder.parse_channel_reference(value)[0] == "query":
        # 유튜브가 아닌 일반 영상 URL
        return ("direct", value)
    return ("search", value)


def build_upload_request(
    render: Any,
    *,
    options: AutoOptions,
    source_title: str = "",
    source_url: str = "",
) -> UploadRequest:
    """렌더 결과 하나를 업로드 요청으로 바꾼다.

    원본 출처를 설명란에 남긴다 — 재편집물임을 밝히는 편이 안전하다.
    """
    clip = render.clip
    lines = [clip.title]
    if clip.reason:
        lines.append("")
        lines.append(clip.reason)
    if source_title or source_url:
        lines.append("")
        lines.append("원본 영상")
        if source_title:
            lines.append(f"  {source_title}")
        if source_url:
            lines.append(f"  {source_url}")
    lines.append("")
    lines.append("#Shorts")

    return UploadRequest(
        video_path=render.output_path,
        title=clip.title,
        description="\n".join(lines),
        tags=list(options.tags),
        category_id=options.category_id,
        privacy=options.privacy,
        publish_at=options.publish_at,
        made_for_kids=options.made_for_kids,
    )


def _spread_publish_times(base: datetime | None, count: int, gap_hours: float = 24.0) -> list[datetime | None]:
    """여러 개를 한꺼번에 올릴 때 공개 시각을 일정 간격으로 벌린다."""
    if base is None:
        return [None] * count
    return [base + timedelta(hours=gap_hours * index) for index in range(count)]


def run_auto(
    settings: Settings,
    target: str,
    options: AutoOptions | None = None,
    *,
    history: HistoryStore | None = None,
    on_progress: Callable[[str, float, str], None] | None = None,
    upload_fn: Callable[..., UploadResult] | None = None,
) -> AutoResult:
    """탐색 → 제작 → 업로드를 한 번에 수행한다."""
    options = options or AutoOptions()
    history = history if history is not None else HistoryStore()
    upload_fn = upload_fn or uploader.upload_video
    result = AutoResult(target=target)

    kind, value = resolve_target(target)

    # ── 대상 선정 ──────────────────────────────────────────────
    if kind == "direct":
        result.source_url = value
        result.source_id = trend_finder.extract_video_id(value) or value
    else:
        if not settings.youtube_api_key:
            result.skipped_reason = (
                "키워드로 탐색하려면 YOUTUBE_API_KEY 가 필요합니다. "
                "영상 URL 이나 파일 경로를 직접 넘기면 키 없이도 동작합니다."
            )
            return result

        videos, quota = trend_finder.find_trending(
            value,
            api_key=settings.youtube_api_key,
            days=options.trend_days,
            limit=10,
            min_vs_ratio=options.trend_min_vs,
            min_subscribers=options.trend_min_subscribers,
            min_duration=options.trend_min_duration,
            as_channel=options.as_channel,
        )
        result.candidates = videos
        result.quota_used += quota

        if options.skip_processed:
            videos = [v for v in videos if not history.is_processed(v.video_id)]
        if not videos:
            result.skipped_reason = (
                "새로 처리할 급상승 영상이 없습니다. (이미 처리했거나 조건에 맞는 영상이 없음)"
            )
            return result

        chosen = videos[0]
        result.source_url = chosen.url
        result.source_id = chosen.video_id
        result.title = chosen.title
        LOG.info("대상 선정: %s (V/S %.2f)", chosen.title, chosen.vs_ratio)

    if options.skip_processed and kind == "direct" and history.is_processed(result.source_id):
        result.skipped_reason = f"이미 처리한 원본입니다: {result.source_id}"
        return result

    # ── 쇼츠 제작 ──────────────────────────────────────────────
    settings.source = result.source_url
    pipeline_result = pipeline.run_pipeline(settings, on_progress=on_progress)
    result.renders = list(pipeline_result.renders)
    result.title = result.title or pipeline_result.title
    if not result.renders:
        result.skipped_reason = "생성된 쇼츠가 없습니다."
        history.record(result.source_id, source_url=result.source_url, title=result.title)
        history.save()
        return result

    # ── 업로드 ────────────────────────────────────────────────
    if options.upload:
        remaining = history.remaining_uploads_today(DAILY_UPLOAD_LIMIT)
        wanted = options.upload_count if options.upload_count is not None else len(result.renders)
        allowed = min(wanted, remaining, len(result.renders))
        if allowed < wanted:
            LOG.warning(
                "오늘 남은 업로드 한도가 %d건이라 %d건만 올립니다. "
                "(업로드 1건 = %d 유닛, 무료 한도 하루 %d건)",
                remaining, allowed, uploader.UPLOAD_QUOTA_COST, DAILY_UPLOAD_LIMIT,
            )

        schedule_times = _spread_publish_times(options.publish_at, allowed)
        for index, render in enumerate(result.renders[:allowed]):
            request = build_upload_request(
                render, options=options, source_title=result.title, source_url=result.source_url
            )
            request.publish_at = schedule_times[index]
            if request.publish_at is not None:
                request.privacy = "private"

            if options.dry_run_upload:
                LOG.info("dry-run: 업로드하지 않고 요청만 확인합니다 — %s", request.title)
                continue
            try:
                uploaded = upload_fn(request)
                result.uploads.append(uploaded)
                result.quota_used += uploaded.quota_used
                LOG.info("업로드 완료: %s", uploaded.shorts_url)
            except Exception as exc:
                message = f"{render.output_path.name}: {exc}"
                result.upload_errors.append(message)
                LOG.error("업로드 실패 — %s", message)
                # 인증/할당량 문제면 나머지도 실패하므로 중단한다.
                if isinstance(exc, (uploader.AuthRequiredError, uploader.QuotaExceededError)):
                    break

    history.record(
        result.source_id,
        source_url=result.source_url,
        title=result.title,
        clip_count=len(result.renders),
        uploads=[u.to_dict() for u in result.uploads],
    )
    history.save()
    return result
