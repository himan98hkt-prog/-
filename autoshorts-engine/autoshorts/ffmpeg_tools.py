"""FFmpeg / FFprobe 호출 래퍼와 필터 그래프 생성기.

필터 그래프 문자열을 만드는 함수는 부수효과가 없어 단위 테스트에서
FFmpeg 설치 없이 그대로 검증할 수 있다.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .utils import CommandError, get_logger, run_command, which_or_raise

__all__ = [
    "MediaInfo",
    "ffmpeg_path",
    "ffprobe_path",
    "probe",
    "probe_media",
    "build_reframe_filter",
    "escape_filter_path",
    "build_render_command",
    "build_lossless_cut_command",
    "build_audio_extract_command",
    "run_ffmpeg",
]

LOG = get_logger("ffmpeg")

_INSTALL_HINT = (
    "FFmpeg 설치가 필요합니다. "
    "(macOS: brew install ffmpeg / Ubuntu: sudo apt install ffmpeg / Windows: winget install Gyan.FFmpeg)"
)


def ffmpeg_path() -> str:
    return which_or_raise("ffmpeg", _INSTALL_HINT)


def ffprobe_path() -> str:
    return which_or_raise("ffprobe", _INSTALL_HINT)


@dataclass
class MediaInfo:
    """ffprobe 로 얻은 최소한의 미디어 정보."""

    path: Path
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    video_codec: str = ""
    audio_codec: str = ""

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    @property
    def aspect_ratio(self) -> float:
        return (self.width / self.height) if self.height else 0.0


def probe(path: str | Path) -> dict[str, Any]:
    """ffprobe 원시 JSON."""
    command = [
        ffprobe_path(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = run_command(command, log=LOG)
    return json.loads(proc.stdout or "{}")


def _parse_fps(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def probe_media(path: str | Path) -> MediaInfo:
    """비디오/오디오 스트림 요약."""
    data = probe(path)
    info = MediaInfo(path=Path(path))
    fmt = data.get("format", {})
    try:
        info.duration = float(fmt.get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        info.duration = 0.0
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and not info.width:
            info.width = int(stream.get("width") or 0)
            info.height = int(stream.get("height") or 0)
            info.fps = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            info.video_codec = stream.get("codec_name", "")
            if not info.duration:
                try:
                    info.duration = float(stream.get("duration") or 0.0)
                except (TypeError, ValueError):
                    pass
        elif kind == "audio":
            info.has_audio = True
            info.audio_codec = info.audio_codec or stream.get("codec_name", "")
    return info


def escape_filter_path(path: str | Path) -> str:
    """필터 인자(subtitles=...) 안에 들어갈 경로 이스케이프.

    윈도우 드라이브 문자의 ``:`` 와 역슬래시, 작은따옴표를 필터 파서가
    삼키지 않도록 처리한다.
    """
    text = str(path).replace("\\", "/")
    text = text.replace("'", r"\'")
    text = text.replace(":", r"\:")
    return text


def build_reframe_filter(
    mode: str,
    width: int,
    height: int,
    *,
    blur_sigma: float = 22.0,
    subtitles_path: str | Path | None = None,
    fps: int | None = None,
) -> str:
    """16:9 -> 9:16 변환 필터 그래프를 만든다.

    - ``crop``: 중앙을 세로 비율로 잘라내고 목표 해상도로 스케일.
    - ``blur``: 배경은 화면을 채우도록 확대 후 가우시안 블러, 전경은
      원본 비율 그대로 가운데 배치.
    """
    if mode not in {"crop", "blur"}:
        raise ValueError(f"지원하지 않는 리프레이밍 방식입니다: {mode!r}")
    if width <= 0 or height <= 0:
        raise ValueError("width/height 는 양수여야 합니다.")

    ratio = f"{width}/{height}"
    if mode == "crop":
        chain = [
            # 원본 비율과 무관하게 목표 비율로 중앙 크롭 (세로가 짧으면 가로 기준)
            f"crop='min(iw,ih*{ratio})':'min(ih,iw*{height}/{width})'",
            f"scale={width}:{height}:flags=lanczos",
            "setsar=1",
        ]
        graph = f"[0:v]{','.join(chain)}[v0]"
    else:
        background = (
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma={blur_sigma:g},"
            f"eq=brightness=-0.06:saturation=1.1[bgout]"
        )
        foreground = (
            f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos[fgout]"
        )
        graph = (
            "[0:v]split=2[bg][fg];"
            + background
            + ";"
            + foreground
            + ";[bgout][fgout]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1[v0]"
        )

    tail: list[str] = []
    if fps:
        tail.append(f"fps={fps}")
    if subtitles_path:
        tail.append(f"subtitles='{escape_filter_path(subtitles_path)}'")
    tail.append("format=yuv420p")
    graph += f";[v0]{','.join(tail)}[vout]"
    return graph


def build_audio_extract_command(
    source: str | Path,
    destination: str | Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    overwrite: bool = True,
    executable: str | None = None,
) -> list[str]:
    """STT 입력용 16kHz 모노 WAV 추출 명령."""
    return [
        executable or ffmpeg_path(),
        "-hide_banner",
        "-loglevel", "error",
        "-y" if overwrite else "-n",
        "-i", str(source),
        "-vn",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "-acodec", "pcm_s16le",
        str(destination),
    ]


def build_lossless_cut_command(
    source: str | Path,
    destination: str | Path,
    start: float,
    duration: float,
    *,
    overwrite: bool = True,
    executable: str | None = None,
) -> list[str]:
    """스트림 복사(무손실) 컷 명령.

    재인코딩이 없어 매우 빠르지만 시작점이 키프레임으로 스냅된다.
    """
    return [
        executable or ffmpeg_path(),
        "-hide_banner",
        "-loglevel", "error",
        "-y" if overwrite else "-n",
        "-ss", f"{max(0.0, start):.3f}",
        "-i", str(source),
        "-t", f"{max(0.0, duration):.3f}",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(destination),
    ]


def build_render_command(
    source: str | Path,
    destination: str | Path,
    *,
    start: float | None = None,
    duration: float | None = None,
    filtergraph: str,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 20,
    preset: str = "veryfast",
    audio_bitrate: str = "192k",
    has_audio: bool = True,
    overwrite: bool = True,
    executable: str | None = None,
) -> list[str]:
    """리프레이밍 + 자막 번인 최종 렌더 명령.

    ``-ss`` 를 입력 앞에 두어 빠르게 탐색하되, 재인코딩 경로이므로
    프레임 단위 정확도는 유지된다.
    """
    command: list[str] = [
        executable or ffmpeg_path(),
        "-hide_banner",
        "-loglevel", "error",
        "-stats",
        "-y" if overwrite else "-n",
    ]
    if start is not None and start > 0:
        command += ["-ss", f"{start:.3f}"]
    command += ["-i", str(source)]
    if duration is not None and duration > 0:
        command += ["-t", f"{duration:.3f}"]
    command += [
        "-filter_complex", filtergraph,
        "-map", "[vout]",
    ]
    if has_audio:
        command += ["-map", "0:a:0?", "-c:a", audio_codec, "-b:a", audio_bitrate, "-ar", "48000"]
    else:
        command += ["-an"]
    command += [
        "-c:v", video_codec,
        "-crf", str(crf),
        "-preset", preset,
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        str(destination),
    ]
    return command


def run_ffmpeg(command: Sequence[str], *, timeout: float | None = None) -> None:
    """FFmpeg 실행. 실패하면 stderr 를 담아 예외를 올린다."""
    LOG.debug("ffmpeg: %s", " ".join(shlex.quote(str(c)) for c in command))
    try:
        run_command(command, capture=True, check=True, timeout=timeout, log=LOG)
    except CommandError as exc:
        raise CommandError(exc.command, exc.returncode, exc.stderr) from None
