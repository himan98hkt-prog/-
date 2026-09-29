"""LTX-Video 0.9.x 의 inference.py 흉내. 그래픽카드 없이 8GB 경로를 시험한다.

    python fake_ltx09.py --pipeline_config configs/x.yaml --prompt "..." \\
        --conditioning_media_paths a.png --conditioning_start_frames 0 \\
        --width 544 --height 960 --num_frames 193 --frame_rate 24 \\
        --seed 0 --output_path <폴더>

진짜 계약을 그대로 흉내낸다. 특히 **어기면 실제로 깨지는 것들**을 여기서
막는다 — 이 셋이 이 엔진을 붙이며 틀리기 쉬운 자리다.

  · 인자 이름이 밑줄이다 (`--num_frames`, 하이픈이면 거절)
  · `--output_path` 는 폴더다. 파일 이름은 이쪽이 짓는다
  · 크기는 32 의 배수, 프레임 수는 8k+1

FAKE_LTX09_FAIL=oom   그래픽카드 메모리 부족 흉내
FAKE_LTX09_LOG=<경로> 받은 인자를 한 줄로 남긴다
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REQUIRED = ("--pipeline_config", "--prompt", "--conditioning_media_paths",
            "--conditioning_start_frames", "--width", "--height",
            "--num_frames", "--frame_rate", "--seed", "--output_path")

# 진짜 CLI 에 없는 이름. 2.5 판 습관으로 하이픈을 쓰면 여기서 걸린다.
FORBIDDEN = ("--num-frames", "--frame-rate", "--output-path", "--image",
             "--transformer-path", "--quantization", "--offload")


def value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("FAKE_LTX09_LOG")
    if log:
        Path(log).open("a", encoding="utf-8").write(" ".join(argv) + "\n")

    missing = [f for f in REQUIRED if f not in argv]
    if missing:
        print(f"error: the following arguments are required: {', '.join(missing)}",
              file=sys.stderr)
        return 2
    bad = [f for f in FORBIDDEN if f in argv]
    if bad:
        print(f"error: unrecognized arguments: {', '.join(bad)}", file=sys.stderr)
        return 2

    if os.environ.get("FAKE_LTX09_FAIL") == "oom":
        print("torch.cuda.OutOfMemoryError: CUDA out of memory.", file=sys.stderr)
        return 1

    width, height = int(value(argv, "--width")), int(value(argv, "--height"))
    if width % 32 or height % 32:
        print(f"error: resolution must be divisible by 32 ({width}x{height})",
              file=sys.stderr)
        return 2

    frames = int(value(argv, "--num_frames"))
    if frames % 8 != 1:
        print(f"error: num_frames must be divisible by 8 plus 1 ({frames})",
              file=sys.stderr)
        return 2

    image = Path(value(argv, "--conditioning_media_paths"))
    if not image.exists():
        print(f"error: conditioning media not found: {image}", file=sys.stderr)
        return 2

    cfg = Path(value(argv, "--pipeline_config"))
    if not cfg.exists():
        print(f"error: pipeline config not found: {cfg}", file=sys.stderr)
        return 2

    # 진짜와 같이 **폴더**를 받아, 이름은 이쪽이 짓는다.
    outdir = Path(value(argv, "--output_path"))
    outdir.mkdir(parents=True, exist_ok=True)
    seed = value(argv, "--seed")
    dest = outdir / f"video_output_0_fake_{seed}_{width}x{height}x{frames}_0.mp4"

    fps = int(value(argv, "--frame_rate"))
    seconds = max(0.1, (frames - 1) / fps)
    # 입력 이미지에서 시작하는 영상. 뒤 단계(업스케일·합성)가 진짜 파일을 받는다.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(image),
         "-t", f"{seconds:.3f}", "-r", str(fps),
         "-vf", f"scale={width}:{height},format=yuv420p",
         "-c:v", "libx264", str(dest)],
        check=True, capture_output=True)
    print(f"Saved video to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
