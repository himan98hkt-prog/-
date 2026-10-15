"""Module A — Video Ingestion.

유튜브 URL 이면 ``yt-dlp`` 로 최고 화질 영상+오디오를 받아 병합하고,
로컬 파일이면 그대로 사용한다. 어느 쪽이든 STT 입력용 16kHz 모노 WAV 를
분리 추출한다.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import ffmpeg_tools
from .utils import ensure_dir, get_logger, sanitize_filename

__all__ = [
    "IngestResult",
    "is_url",
    "is_supported_media",
    "ingest",
    "download_video",
    "extract_audio",
    "build_ydl_options",
    "IngestError",
    "VIDEO_EXTENSIONS",
]

LOG = get_logger("downloader")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".flv", ".wmv", ".ts", ".mpg", ".mpeg"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class IngestError(RuntimeError):
    """입력 소스를 확보하지 못했을 때."""


@dataclass
class IngestResult:
    """1단계 산출물."""

    video_path: Path
    audio_path: Path
    title: str = ""
    source: str = ""
    duration: float = 0.0
    is_remote: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": str(self.video_path),
            "audio_path": str(self.audio_path),
            "title": self.title,
            "source": self.source,
            "duration": round(self.duration, 3),
            "is_remote": self.is_remote,
        }


def is_url(source: str) -> bool:
    """``http(s)://`` 등 스킴이 붙은 원격 주소인지."""
    return bool(_URL_RE.match(str(source).strip()))


def is_supported_media(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in VIDEO_EXTENSIONS or suffix in AUDIO_EXTENSIONS


def build_ydl_options(
    output_dir: str | Path,
    *,
    cookies_from_browser: str | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
    quiet: bool = True,
) -> dict[str, Any]:
    """yt-dlp 옵션. 최고 화질 비디오 + 최고 음질 오디오를 MP4 로 병합."""
    options: dict[str, Any] = {
        # bv*+ba: 분리 스트림 최고 조합, 실패 시 단일 파일(b) 로 폴백
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": str(Path(output_dir) / "source.%(ext)s"),
        "restrictfilenames": False,
        "noplaylist": True,
        "quiet": quiet,
        "no_warnings": quiet,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "overwrites": True,
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    }
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser,)
    if progress_hook:
        options["progress_hooks"] = [progress_hook]
    return options


def download_video(
    url: str,
    output_dir: str | Path,
    *,
    cookies_from_browser: str | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """yt-dlp 로 영상을 내려받고 (경로, 메타데이터) 를 반환."""
    try:
        import yt_dlp  # 지연 임포트: 로컬 파일만 쓸 때는 필요 없다.
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise IngestError(
            "yt-dlp 가 설치돼 있지 않습니다. `pip install yt-dlp` 로 설치하세요."
        ) from exc

    output_dir = ensure_dir(output_dir)
    options = build_ydl_options(
        output_dir,
        cookies_from_browser=cookies_from_browser,
        progress_hook=progress_hook,
    )
    LOG.info("영상 다운로드 시작: %s", url)
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if info.get("_type") == "playlist":  # noplaylist 로도 새는 경우 대비
            entries = [e for e in info.get("entries") or [] if e]
            if not entries:
                raise IngestError(f"다운로드할 항목이 없습니다: {url}")
            info = entries[0]
        path = Path(ydl.prepare_filename(info))

    if not path.exists():
        # 리먹싱으로 확장자가 바뀐 경우 같은 이름의 다른 확장자를 찾는다.
        candidates = sorted(
            (p for p in output_dir.glob(f"{path.stem}.*") if p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise IngestError(f"다운로드된 파일을 찾지 못했습니다: {path}")
        path = candidates[0]

    LOG.info("다운로드 완료: %s", path.name)
    return path, info


def extract_audio(
    video_path: str | Path,
    destination: str | Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    overwrite: bool = True,
) -> Path:
    """faster-whisper 입력 규격(16kHz 모노 WAV)으로 오디오 분리."""
    video_path = Path(video_path)
    destination = Path(destination)
    ensure_dir(destination.parent)
    if destination.exists() and not overwrite:
        LOG.info("오디오 재사용: %s", destination.name)
        return destination
    command = ffmpeg_tools.build_audio_extract_command(
        video_path,
        destination,
        sample_rate=sample_rate,
        channels=channels,
        overwrite=True,
    )
    LOG.info("오디오 추출: %s -> %s", video_path.name, destination.name)
    ffmpeg_tools.run_ffmpeg(command)
    if not destination.exists() or destination.stat().st_size == 0:
        raise IngestError(f"오디오 추출에 실패했습니다: {video_path}")
    return destination


def ingest(
    source: str,
    work_dir: str | Path,
    *,
    cookies_from_browser: str | None = None,
    overwrite: bool = False,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> IngestResult:
    """URL 또는 로컬 경로를 받아 영상/오디오 경로를 확정한다."""
    work_dir = ensure_dir(work_dir)
    source = str(source).strip()
    if not source:
        raise IngestError("입력 소스가 비어 있습니다.")

    metadata: dict[str, Any] = {}
    remote = is_url(source)

    if remote:
        video_path, metadata = download_video(
            source,
            work_dir,
            cookies_from_browser=cookies_from_browser,
            progress_hook=progress_hook,
        )
        title = metadata.get("title") or video_path.stem
    else:
        local = Path(source).expanduser()
        if not local.exists():
            raise IngestError(f"파일을 찾을 수 없습니다: {local}")
        if local.is_dir():
            raise IngestError(f"파일이 아니라 디렉터리입니다: {local}")
        if not is_supported_media(local):
            raise IngestError(
                f"지원하지 않는 형식입니다: {local.suffix or '(확장자 없음)'} "
                f"— 지원: {', '.join(sorted(VIDEO_EXTENSIONS))}"
            )
        video_path = local.resolve()
        title = local.stem

    audio_path = work_dir / "audio.wav"
    audio_path = extract_audio(video_path, audio_path, overwrite=overwrite or not audio_path.exists())

    duration = float(metadata.get("duration") or 0.0)
    if not duration:
        try:
            duration = ffmpeg_tools.probe_media(video_path).duration
        except Exception as exc:  # ffprobe 실패는 치명적이지 않다.
            LOG.debug("길이 측정 실패(무시): %s", exc)

    return IngestResult(
        video_path=Path(video_path),
        audio_path=Path(audio_path),
        title=sanitize_filename(title, max_length=80) or "video",
        source=source,
        duration=duration,
        is_remote=remote,
        metadata={k: metadata.get(k) for k in ("id", "uploader", "webpage_url", "duration") if metadata.get(k)},
    )


def copy_into(source: str | Path, destination_dir: str | Path) -> Path:
    """로컬 원본을 작업 디렉터리로 복사(원본 보호가 필요할 때)."""
    source = Path(source)
    destination = ensure_dir(destination_dir) / f"source{source.suffix.lower()}"
    if destination.resolve() == source.resolve():
        return destination
    shutil.copy2(source, destination)
    return destination
