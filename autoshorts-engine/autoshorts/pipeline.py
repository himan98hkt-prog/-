"""5단계 파이프라인 오케스트레이션.

다운로드 → 전사 → 하이라이트 분석 → 리프레이밍 → 자막 번인 렌더링을
순서대로 실행하고, 중간 산출물을 캐시해 재실행 비용을 줄인다.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from . import ai_analyzer, downloader, transcriber, video_renderer
from .config import Settings
from .models import Clip, Transcript
from .utils import ensure_dir, get_logger, human_duration, sanitize_filename

__all__ = ["PipelineResult", "run_pipeline", "STAGES"]

LOG = get_logger("pipeline")

STAGES = ("ingest", "transcribe", "analyze", "render")

ProgressCallback = Callable[[str, float, str], None]


@dataclass
class PipelineResult:
    """파이프라인 전체 산출물."""

    source: str
    title: str = ""
    video_path: Path | None = None
    audio_path: Path | None = None
    transcript_path: Path | None = None
    clips: list[Clip] = field(default_factory=list)
    renders: list[video_renderer.RenderResult] = field(default_factory=list)
    manifest_path: Path | None = None
    elapsed_seconds: float = 0.0
    used_offline_analysis: bool = False

    @property
    def output_paths(self) -> list[Path]:
        return [r.output_path for r in self.renders]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "video_path": str(self.video_path) if self.video_path else None,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "transcript_path": str(self.transcript_path) if self.transcript_path else None,
            "used_offline_analysis": self.used_offline_analysis,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "clips": [c.to_dict() for c in self.clips],
            "outputs": [r.to_dict() for r in self.renders],
        }


def _notify(callback: ProgressCallback | None, stage: str, fraction: float, message: str) -> None:
    LOG.info("[%s] %s", stage, message)
    if callback:
        try:
            callback(stage, fraction, message)
        except Exception as exc:  # UI 콜백 오류가 파이프라인을 멈추지 않게 한다.
            LOG.debug("진행률 콜백 오류(무시): %s", exc)


def _job_dir(settings: Settings, source: str) -> Path:
    """소스마다 분리된 작업 디렉터리. 캐시 재사용의 기준이 된다."""
    import hashlib

    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:10]
    label = sanitize_filename(Path(source).stem if not downloader.is_url(source) else "youtube", 24)
    return ensure_dir(settings.work_dir / f"{label or 'job'}-{digest}")


def run_pipeline(
    settings: Settings,
    *,
    on_progress: ProgressCallback | None = None,
    clips_override: Sequence[Clip] | None = None,
) -> PipelineResult:
    """전 단계를 실행하고 :class:`PipelineResult` 를 돌려준다."""
    started = time.monotonic()
    source = settings.source
    if not source:
        raise ValueError("settings.source 가 비어 있습니다.")

    work_dir = _job_dir(settings, source)
    ensure_dir(settings.output_dir)
    result = PipelineResult(source=source)

    # ── 1. 다운로드 / 오디오 추출 ────────────────────────────────
    _notify(on_progress, "ingest", 0.02, "입력 소스를 준비합니다.")
    ingested = downloader.ingest(
        source,
        work_dir,
        cookies_from_browser=settings.cookies_from_browser,
        overwrite=settings.overwrite,
    )
    result.video_path = ingested.video_path
    result.audio_path = ingested.audio_path
    result.title = ingested.title
    _notify(
        on_progress,
        "ingest",
        0.15,
        f"준비 완료: {ingested.title} ({human_duration(ingested.duration)})",
    )

    # ── 2. 전사 ────────────────────────────────────────────────
    transcript_path = work_dir / "transcription.json"
    if transcript_path.exists() and not settings.overwrite:
        _notify(on_progress, "transcribe", 0.2, "기존 전사 결과를 재사용합니다.")
        transcript = Transcript.load(transcript_path)
    else:
        _notify(on_progress, "transcribe", 0.2, "음성을 텍스트로 변환합니다. (시간이 걸립니다)")
        transcript = transcriber.transcribe(
            ingested.audio_path,
            model_size=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            language=settings.language,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            output_path=transcript_path,
            progress=lambda fraction, text: _notify(
                on_progress, "transcribe", 0.2 + fraction * 0.35, text[:60]
            ),
        )
    result.transcript_path = transcript_path
    _notify(
        on_progress,
        "transcribe",
        0.55,
        f"전사 완료: {len(transcript)}개 문장, 언어 {transcript.language}",
    )

    # ── 3. 하이라이트 분석 ──────────────────────────────────────
    if clips_override:
        clips = list(clips_override)
        for index, clip in enumerate(clips, start=1):
            clip.index = clip.index or index
        _notify(on_progress, "analyze", 0.6, f"지정된 클립 {len(clips)}개를 사용합니다.")
    else:
        _notify(on_progress, "analyze", 0.6, "하이라이트 구간을 분석합니다.")
        result.used_offline_analysis = not settings.has_gemini
        clips = ai_analyzer.analyze(
            transcript,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            min_seconds=settings.min_clip_seconds,
            max_seconds=settings.max_clip_seconds,
            min_clips=settings.min_clips,
            max_clips=settings.max_clips,
            video_title=ingested.title,
            allow_offline_fallback=settings.allow_offline_fallback,
        )
    result.clips = list(clips)
    if not clips:
        _notify(on_progress, "analyze", 1.0, "선정된 하이라이트가 없어 종료합니다.")
        result.elapsed_seconds = time.monotonic() - started
        return result

    (work_dir / "clips.json").write_text(
        json.dumps([c.to_dict() for c in clips], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _notify(on_progress, "analyze", 0.68, f"하이라이트 {len(clips)}개 선정 완료")

    # ── 4~5. 리프레이밍 + 자막 번인 렌더링 ──────────────────────
    def render_progress(position: int, total: int, clip: Clip) -> None:
        fraction = 0.7 + 0.3 * ((position - 1) / max(total, 1))
        _notify(on_progress, "render", fraction, f"[{position}/{total}] {clip.title}")

    # 호출자의 Settings 를 변형하면 다음 실행에서 작업 디렉터리가 중첩되고
    # 전사 캐시를 놓치므로, 사본에만 작업 디렉터리를 심는다.
    render_settings = settings.clone(work_dir=work_dir)
    result.renders = video_renderer.render_clips(
        ingested.video_path,
        clips,
        transcript if settings.burn_subtitles else None,
        render_settings,
        on_progress=render_progress,
    )

    result.elapsed_seconds = time.monotonic() - started
    manifest = ensure_dir(settings.output_dir) / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"settings": settings.to_dict(), **result.to_dict()}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    result.manifest_path = manifest

    _notify(
        on_progress,
        "render",
        1.0,
        f"완료: 쇼츠 {len(result.renders)}개, 총 {human_duration(result.elapsed_seconds)} 소요",
    )
    return result
