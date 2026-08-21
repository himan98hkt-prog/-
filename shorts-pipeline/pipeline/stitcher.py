"""클립들을 하나의 세로 영상으로 합성한다.

chain 모드   : 경계마다 xfade 크로스페이드. 이음매를 눈에 덜 띄게 한다.
montage 모드 : 하드 컷(concat) 또는 짧은 fade.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_util import FFmpegError, duration_of, has_audio, run


@dataclass
class StitchResult:
    path: Path
    duration: float
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


def stitch(
    clips: list[Path],
    dest: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    crf: int = 18,
    crossfade: float = 0.3,
    transition: str = "fade",
    audio: str = "silent",
    audio_file: str | None = None,
) -> StitchResult:
    """clips 를 순서대로 이어붙여 dest 에 쓴다.

    transition: "cut"(하드 컷) 또는 xfade 트랜지션 이름("fade", "fadeblack" 등).
    """
    if not clips:
        raise FFmpegError("합성할 클립이 없습니다.")
    missing = [c for c in clips if not c.exists() or c.stat().st_size == 0]
    if missing:
        raise FFmpegError(
            "다음 클립이 비었거나 없습니다: " + ", ".join(p.name for p in missing)
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    scale_chain = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p"
    )

    if len(clips) == 1 or transition == "cut" or crossfade <= 0:
        filter_complex, last_label = _concat_graph(clips, scale_chain)
    else:
        filter_complex, last_label = _xfade_graph(
            clips, scale_chain, crossfade, transition
        )

    args = ["ffmpeg", "-v", "error", "-stats"]
    for c in clips:
        args += ["-i", str(c)]

    audio_args, audio_map = _audio_args(audio, audio_file, len(clips))
    args += audio_args
    args += [
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        *audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest", "-y", str(dest),
    ]
    run(args, desc="최종 합성")

    if not dest.exists() or dest.stat().st_size == 0:
        raise FFmpegError("합성은 끝났는데 출력 파일이 비어 있습니다.")
    return StitchResult(dest, duration_of(dest), dest.stat().st_size)


def _concat_graph(clips: list[Path], scale_chain: str) -> tuple[str, str]:
    """하드 컷 이어붙이기."""
    parts = [f"[{i}:v]{scale_chain}[v{i}]" for i in range(len(clips))]
    inputs = "".join(f"[v{i}]" for i in range(len(clips)))
    parts.append(f"{inputs}concat=n={len(clips)}:v=1:a=0[outv]")
    return ";".join(parts), "outv"


def _xfade_graph(
    clips: list[Path], scale_chain: str, crossfade: float, transition: str
) -> tuple[str, str]:
    """xfade 를 누적 연결한다.

    offset 은 '지금까지 누적된 길이 - 크로스페이드' 다. 클립 길이를 가정하지 않고
    실제로 probe 한 값을 쓴다 — 모델이 요청한 길이를 정확히 지키지 않는 일이 잦다.
    """
    durations = [duration_of(c) for c in clips]
    shortest = min(durations)
    if crossfade >= shortest:
        raise FFmpegError(
            f"크로스페이드({crossfade}초)가 가장 짧은 클립({shortest:.2f}초)보다 "
            "짧아야 합니다. config 의 crossfade_seconds 를 줄이세요."
        )

    parts = [f"[{i}:v]{scale_chain}[v{i}]" for i in range(len(clips))]
    current = "v0"
    accumulated = durations[0]

    for i in range(1, len(clips)):
        offset = accumulated - crossfade
        label = "outv" if i == len(clips) - 1 else f"x{i}"
        parts.append(
            f"[{current}][v{i}]xfade=transition={transition}"
            f":duration={crossfade}:offset={offset:.4f}[{label}]"
        )
        current = label
        accumulated += durations[i] - crossfade

    return ";".join(parts), current


def _audio_args(
    audio: str, audio_file: str | None, n_clips: int
) -> tuple[list[str], list[str]]:
    """오디오 입력과 매핑을 만든다.

    Shorts / Reels 는 오디오 트랙이 없는 파일에서 종종 문제를 일으키므로
    기본값은 무음 트랙 삽입이다.
    """
    if audio == "file":
        if not audio_file:
            raise FFmpegError("output.audio 가 file 인데 output.audio_file 이 비었습니다.")
        path = Path(audio_file)
        if not path.exists():
            raise FFmpegError(f"음원 파일이 없습니다: {path}")
        return (["-stream_loop", "-1", "-i", str(path)], ["-map", f"{n_clips}:a"])

    # 무음 트랙
    return (
        ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"],
        ["-map", f"{n_clips}:a"],
    )
