"""내 PC 에서 하는 업스케일. Real-ESRGAN(ncnn-vulkan) 이 있을 때만 쓴다.

Real-ESRGAN ncnn-vulkan 은 파이썬 설치 없이 exe 하나로 돈다. NVIDIA 가
아니어도(AMD·인텔) Vulkan 만 되면 돈다. tools/realesrgan/ 에 풀어 두거나
PATH 에 두면 알아서 찾는다.

영상은 프레임으로 풀어 한 장씩 키운 뒤 같은 프레임률로 다시 묶는다.
소리가 있으면 그대로 붙인다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .ffmpeg_util import FFmpegError, fps_of, run

ROOT = Path(__file__).resolve().parent.parent
EXE_NAMES = ("realesrgan-ncnn-vulkan.exe", "realesrgan-ncnn-vulkan")

# 모델마다 되는 배율. animevideov3 는 영상용이라 빠르고 2·3·4 배를 다 한다.
# x4plus 는 실사에 더 낫지만 4배만 되고 훨씬 느리다.
SCALES = {
    "realesr-animevideov3": (2, 3, 4),
    "realesrgan-x4plus": (4,),
    "realesrgan-x4plus-anime": (4,),
}


def find_realesrgan() -> Path | None:
    """REALESRGAN_PATH -> tools/realesrgan/ -> PATH 순으로 찾는다."""
    env = (os.getenv("REALESRGAN_PATH") or "").strip()
    if env and Path(env).is_file():
        return Path(env)
    tools = ROOT / "tools" / "realesrgan"
    if tools.is_dir():
        for name in EXE_NAMES:
            hits = sorted(tools.rglob(name))
            if hits:
                return hits[0]
    for name in EXE_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def _scale_for(model: str, scale: int) -> int:
    allowed = SCALES.get(model)
    if not allowed:
        return scale
    return scale if scale in allowed else allowed[0]


def _esrgan(exe: Path, src: Path, dst: Path, model: str, scale: int) -> None:
    args = [str(exe), "-i", str(src), "-o", str(dst), "-n", model,
            "-s", str(_scale_for(model, scale)), "-f", "png"]
    try:
        p = subprocess.run(args, capture_output=True, text=True, errors="replace",
                           cwd=str(exe.parent), timeout=3 * 3600,
                           creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FFmpegError(f"Real-ESRGAN 실행 실패: {exc}") from exc
    if p.returncode != 0:
        raise FFmpegError("Real-ESRGAN 오류: " + (p.stderr or p.stdout).strip()[-300:])


def upscale_image(src: Path, dst: Path, *, exe: Path, model: str, scale: int = 2) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    _esrgan(exe, src, dst, model, scale)
    if not dst.exists():
        raise FFmpegError("Real-ESRGAN 결과 이미지가 없습니다.")
    return dst


def upscale_video(src: Path, dst: Path, *, exe: Path, model: str, scale: int = 2,
                  crf: int = 16) -> Path:
    """프레임으로 풀어 키우고 다시 묶는다. src 와 dst 가 같아도 된다."""
    fps = fps_of(src) or 24
    with tempfile.TemporaryDirectory(prefix="esr_", dir=str(dst.parent)) as tmp:
        frames, big = Path(tmp) / "in", Path(tmp) / "out"
        frames.mkdir()
        big.mkdir()
        run(["ffmpeg", "-v", "error", "-i", str(src), "-vsync", "0",
             str(frames / "%06d.png")], desc="프레임 풀기")
        _esrgan(exe, frames, big, model, scale)
        if not any(big.iterdir()):
            raise FFmpegError("Real-ESRGAN 이 프레임을 하나도 못 만들었습니다.")
        out = Path(tmp) / "up.mp4"
        run(["ffmpeg", "-v", "error", "-framerate", f"{fps:g}",
             "-i", str(big / "%06d.png"), "-i", str(src),
             "-map", "0:v", "-map", "1:a?", "-c:a", "copy",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
             "-pix_fmt", "yuv420p", "-r", f"{fps:g}", "-shortest",
             "-y", str(out)], desc="프레임 묶기")
        os.replace(out, dst)
    return dst
