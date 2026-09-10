"""Module D — Video Processor.

하이라이트 구간을 잘라 9:16(1080x1920)으로 리프레이밍하고, 해당 구간의
ASS 자막을 하드서브로 구워 최종 MP4 를 만든다.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from . import ffmpeg_tools
from .config import Settings
from .models import Clip, Transcript
from .subtitles import write_clip_subtitles
from .utils import CommandError, ensure_dir, get_logger, human_duration

__all__ = ["RenderResult", "render_clip", "render_clips", "RenderError"]

LOG = get_logger("renderer")


class RenderError(RuntimeError):
    """렌더링 실패."""


@dataclass
class RenderResult:
    """클립 하나의 렌더 결과."""

    clip: Clip
    output_path: Path
    subtitle_path: Path | None = None
    reframe_mode: str = "blur"
    duration: float = 0.0
    size_bytes: int = 0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.clip.to_dict(),
            "output_path": str(self.output_path),
            "subtitle_path": str(self.subtitle_path) if self.subtitle_path else None,
            "reframe_mode": self.reframe_mode,
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_bytes / 1_048_576, 2) if self.size_bytes else 0.0,
        }


def _unique_path(path: Path) -> Path:
    """같은 이름이 있으면 ``-2``, ``-3`` 을 붙여 덮어쓰기를 피한다."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    for counter in range(2, 1000):
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
    raise RenderError(f"출력 파일명을 확보하지 못했습니다: {path}")


def render_clip(
    video_path: str | Path,
    clip: Clip,
    transcript: Transcript | None,
    settings: Settings,
    *,
    output_dir: str | Path | None = None,
    subtitle_dir: str | Path | None = None,
    has_audio: bool = True,
) -> RenderResult:
    """클립 한 개를 9:16 세로 영상으로 렌더링한다."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise RenderError(f"원본 영상이 없습니다: {video_path}")
    if clip.duration <= 0:
        raise RenderError(f"클립 길이가 0입니다: {clip.title!r}")

    output_dir = ensure_dir(output_dir or settings.output_dir)
    subtitle_dir = ensure_dir(subtitle_dir or (settings.work_dir / "subtitles"))
    output_path = output_dir / clip.output_filename()
    if not settings.overwrite:
        output_path = _unique_path(output_path)

    subtitle_path: Path | None = None
    if settings.burn_subtitles and transcript is not None:
        subtitle_path = write_clip_subtitles(
            transcript,
            clip.start,
            clip.end,
            subtitle_dir / f"clip_{clip.index:02d}.ass",
            settings.subtitle_style,
            width=settings.width,
            height=settings.height,
        )
        if not _has_dialogue(subtitle_path):
            LOG.warning("클립 %d 구간에 자막으로 쓸 발화가 없습니다.", clip.index)
            subtitle_path = None

    filtergraph = ffmpeg_tools.build_reframe_filter(
        settings.reframe_mode,
        settings.width,
        settings.height,
        blur_sigma=settings.blur_sigma,
        subtitles_path=subtitle_path,
        fps=settings.fps,
    )

    source_for_render: Path = video_path
    start_for_render: float | None = clip.start
    temp_cut: Path | None = None

    if settings.lossless_cut:
        # 1) 스트림 복사로 구간만 무손실 추출 → 2) 그 조각만 재인코딩.
        # 긴 원본에서 반복 탐색 비용을 줄여준다.
        temp_cut = Path(tempfile.mkstemp(suffix=".mp4", dir=str(ensure_dir(settings.work_dir / "cuts")))[1])
        cut_command = ffmpeg_tools.build_lossless_cut_command(
            video_path, temp_cut, clip.start, clip.duration
        )
        LOG.info("클립 %d 무손실 컷: %.1fs~%.1fs", clip.index, clip.start, clip.end)
        _run(cut_command, f"클립 {clip.index} 무손실 컷")
        source_for_render = temp_cut
        start_for_render = None

    command = ffmpeg_tools.build_render_command(
        source_for_render,
        output_path,
        start=start_for_render,
        duration=clip.duration,
        filtergraph=filtergraph,
        video_codec=settings.video_codec,
        audio_codec=settings.audio_codec,
        crf=settings.crf,
        preset=settings.preset,
        audio_bitrate=settings.audio_bitrate,
        has_audio=has_audio,
        overwrite=True,
    )

    LOG.info(
        "클립 %d 렌더링: %s (%s, %s)",
        clip.index, clip.title, human_duration(clip.duration), settings.reframe_mode,
    )
    if settings.dry_run:
        LOG.info("dry-run: 실행하지 않고 명령만 확인합니다.")
        return RenderResult(
            clip=clip,
            output_path=output_path,
            subtitle_path=subtitle_path,
            reframe_mode=settings.reframe_mode,
            duration=clip.duration,
            extras={"command": command, "filtergraph": filtergraph, "dry_run": True},
        )

    try:
        _run(command, f"클립 {clip.index} 렌더링")
    finally:
        if temp_cut and not settings.keep_intermediate:
            temp_cut.unlink(missing_ok=True)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RenderError(f"렌더링 결과 파일이 비어 있습니다: {output_path}")

    return RenderResult(
        clip=clip,
        output_path=output_path,
        subtitle_path=subtitle_path,
        reframe_mode=settings.reframe_mode,
        duration=clip.duration,
        size_bytes=output_path.stat().st_size,
        extras={"filtergraph": filtergraph},
    )


def _run(command: Sequence[str], label: str) -> None:
    try:
        ffmpeg_tools.run_ffmpeg(command)
    except CommandError as exc:
        raise RenderError(f"{label} 실패\n{exc}") from None


def _has_dialogue(path: Path) -> bool:
    try:
        return "Dialogue:" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def render_clips(
    video_path: str | Path,
    clips: Sequence[Clip],
    transcript: Transcript | None,
    settings: Settings,
    *,
    on_progress: Callable[[int, int, Clip], None] | None = None,
    continue_on_error: bool = True,
) -> list[RenderResult]:
    """여러 클립을 순차 렌더링한다.

    한 클립이 실패해도 나머지는 계속 진행하고, 실패는 로그로 남긴다.
    """
    results: list[RenderResult] = []
    has_audio = True
    try:
        has_audio = ffmpeg_tools.probe_media(video_path).has_audio
    except Exception as exc:
        LOG.debug("오디오 스트림 확인 실패(오디오 있다고 가정): %s", exc)

    total = len(clips)
    for position, clip in enumerate(clips, start=1):
        if on_progress:
            on_progress(position, total, clip)
        try:
            results.append(
                render_clip(video_path, clip, transcript, settings, has_audio=has_audio)
            )
        except (RenderError, CommandError) as exc:
            LOG.error("클립 %d 렌더링 실패: %s", clip.index, exc)
            if not continue_on_error:
                raise
    return results
