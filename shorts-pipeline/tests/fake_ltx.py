"""LTX-2 명령줄 흉내. 그래픽카드 없이 내 PC 엔진 경로 전체를 시험한다.

    python fake_ltx.py -m ltx_pipelines.distilled --image a.png 0 1.0 --width 576 ...

진짜처럼 받는 인자를 확인하고, 입력 이미지에서 시작하는 영상을 ffmpeg 로
만든다. 진행 막대는 tqdm 처럼 \\r 로 덮어쓴다.

FAKE_LTX_FAIL=oom      그래픽카드 메모리 부족 흉내
FAKE_LTX_ARGS_CHECK=<ltx_parse_check.py 경로> <ltx_pipelines 소스 경로>
                       Lightricks 의 진짜 args.py 로 인자를 한 번 더 파싱한다
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REQUIRED = ("--transformer-path", "--text-encoder-path", "--video-vae-path",
            "--audio-vae-path", "--spatial-upsampler-path", "--image", "--width",
            "--height", "--num-frames", "--prompt", "--output-path")


def value(argv: list[str], flag: str, n: int = 1) -> list[str]:
    i = argv.index(flag)
    return argv[i + 1:i + 1 + n]


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] != ["-m"] or not argv[1].startswith("ltx_pipelines."):
        print("usage: -m ltx_pipelines.<pipeline> ...", file=sys.stderr)
        return 2
    module, argv = argv[1].split(".", 1)[1], argv[2:]
    Path(os.environ.get("FAKE_LTX_LOG", os.devnull)).open("a").write(" ".join(argv) + "\n")

    missing = [f for f in REQUIRED if f not in argv]
    if missing:
        print(f"error: the following arguments are required: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    check = os.environ.get("FAKE_LTX_ARGS_CHECK")
    if check:
        harness, src = check.split(os.pathsep)
        sys.argv = ["x", src]
        scope: dict = {}
        exec(Path(harness).read_text(encoding="utf-8"), scope)
        scope["parse"](module, argv)          # 틀리면 여기서 SystemExit

    image, frame_idx, strength = value(argv, "--image", 3)
    width, height = int(value(argv, "--width")[0]), int(value(argv, "--height")[0])
    frames = int(value(argv, "--num-frames")[0])
    fps = float(value(argv, "--frame-rate")[0]) if "--frame-rate" in argv else 24.0
    out = value(argv, "--output-path")[0]
    for flag in ("--transformer-path", "--spatial-upsampler-path"):
        if not Path(value(argv, flag)[0]).exists():
            print(f"FileNotFoundError: {value(argv, flag)[0]}", file=sys.stderr)
            return 1
    if (frames - 1) % 8:
        print(f"AssertionError: num_frames={frames} is not 8k+1", file=sys.stderr)
        return 1
    if width % 64 or height % 64:
        print(f"AssertionError: {width}x{height} not divisible by 64", file=sys.stderr)
        return 1

    for step in range(1, 9):                   # tqdm 흉내
        sys.stdout.write(f"\rStage 1: {step}/8 [{'#' * step:<8}]")
        sys.stdout.flush()
        time.sleep(0.05)
    print()
    if os.environ.get("FAKE_LTX_FAIL") == "oom":
        print("torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB",
              file=sys.stderr)
        return 1

    seconds = frames / fps
    # 입력 이미지에서 시작해 천천히 확대 — 이어지는 영상처럼 보이게
    subprocess.run(
        ["ffmpeg", "-v", "error", "-loop", "1", "-i", image,
         "-vf", (f"scale={width * 2}:{height * 2},"
                 f"zoompan=z='1+0.002*on':d={frames}:s={width}x{height}:fps={fps:g},"
                 "format=yuv420p"),
         "-frames:v", str(frames), "-t", f"{seconds:.3f}",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-y", out],
        check=True)
    print(f"Saved video to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
