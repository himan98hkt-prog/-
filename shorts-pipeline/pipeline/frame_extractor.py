"""클립의 마지막 프레임 추출. 체이닝의 연결 고리."""

from __future__ import annotations

from pathlib import Path

from .ffmpeg_util import FFmpegError, run

# 첫 시도가 빈 파일을 내면 조금 더 앞에서 다시 잡는다.
_OFFSETS = ("-0.1", "-0.3", "-0.6")


def extract_last_frame(clip: Path, dest: Path) -> Path:
    """clip 의 끝부분에서 1프레임을 뽑아 dest(PNG)로 저장한다."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for offset in _OFFSETS:
        dest.unlink(missing_ok=True)
        try:
            run(
                ["ffmpeg", "-v", "error", "-sseof", offset, "-i", str(clip),
                 "-frames:v", "1", "-q:v", "1", "-y", str(dest)],
                desc=f"라스트 프레임 추출 ({clip.name}, sseof {offset})",
            )
        except FFmpegError as exc:
            last_error = exc
            continue
        if dest.exists() and dest.stat().st_size > 0:
            return dest

    raise FFmpegError(
        f"{clip.name} 에서 마지막 프레임을 뽑지 못했습니다. "
        f"클립이 손상됐을 수 있습니다.\n{last_error or ''}"
    )


def extract_first_frame(clip: Path, dest: Path) -> Path:
    """loop_back 용. 첫 클립의 첫 프레임을 뽑는다."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-frames:v", "1",
         "-q:v", "1", "-y", str(dest)],
        desc=f"첫 프레임 추출 ({clip.name})",
    )
    if not dest.exists() or dest.stat().st_size == 0:
        raise FFmpegError(f"{clip.name} 의 첫 프레임 추출 실패")
    return dest
