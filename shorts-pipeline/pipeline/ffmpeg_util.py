"""ffmpeg / ffprobe 호출 공통부."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(Exception):
    pass


def ensure_ffmpeg() -> None:
    """ffmpeg 가 없으면 설치 방법을 알려주고 죽는다."""
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise FFmpegError(
            f"{', '.join(missing)} 를 찾을 수 없습니다.\n"
            "  macOS : brew install ffmpeg\n"
            "  Ubuntu: sudo apt-get install -y ffmpeg\n"
            "  Windows: https://www.gyan.dev/ffmpeg/builds/ 에서 받아 PATH 에 추가"
        )


def run(args: list[str], *, desc: str = "") -> subprocess.CompletedProcess:
    """ffmpeg 실행. 실패하면 stderr 를 담아 예외를 던진다."""
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"{desc or args[0]} 실패 (exit {proc.returncode})\n{tail}")
    return proc


def probe(path: Path) -> dict:
    """스트림 + 포맷 정보를 dict 로."""
    proc = run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        desc=f"ffprobe {path.name}",
    )
    return json.loads(proc.stdout)


def duration_of(path: Path) -> float:
    info = probe(path)
    dur = info.get("format", {}).get("duration")
    if dur is not None:
        return float(dur)
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and s.get("duration"):
            return float(s["duration"])
    raise FFmpegError(f"{path.name} 의 길이를 읽지 못했습니다.")


def dimensions_of(path: Path) -> tuple[int, int]:
    for s in probe(path).get("streams", []):
        if s.get("codec_type") == "video":
            return int(s["width"]), int(s["height"])
    raise FFmpegError(f"{path.name} 에 비디오 스트림이 없습니다.")


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path).get("streams", []))
