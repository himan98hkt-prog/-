"""정기 업로드용 배치 러너.

cron / 작업 스케줄러에서 이 스크립트를 부르면 된다.

  # 매일 09시, 시드 폴더에서 1장 골라 생성 후 업로드
  0 9 * * *  cd /path/to/shorts-pipeline && python -m publish.scheduler --seeds ./seeds --publish

시드 이미지는 사용한 뒤 seeds/_used/ 로 옮겨 중복 사용을 막는다.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def pick_seed(seeds_dir: Path, *, shuffle: bool = True) -> Path | None:
    """아직 쓰지 않은 시드 이미지를 하나 고른다."""
    used = seeds_dir / "_used"
    used.mkdir(exist_ok=True)
    candidates = [
        p for p in sorted(seeds_dir.iterdir())
        if p.is_file() and p.suffix.lower() in _IMAGE_EXT
    ]
    if not candidates:
        return None
    return random.choice(candidates) if shuffle else candidates[0]


def retire_seed(seed: Path) -> None:
    used = seed.parent / "_used"
    used.mkdir(exist_ok=True)
    try:
        shutil.move(str(seed), str(used / seed.name))
    except OSError as exc:
        print(f"  ⚠ 시드 이동 실패 ({exc}) — 중복 사용될 수 있습니다.")


def latest_run() -> str | None:
    runs = ROOT / "runs"
    dirs = [p for p in runs.iterdir() if p.is_dir() and (p / "final.mp4").exists()] \
        if runs.exists() else []
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime).name


def _run(args: list[str]) -> int:
    print(f"  $ {' '.join(args)}")
    return subprocess.call(args, cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="정기 생성·업로드 배치")
    ap.add_argument("--seeds", default="seeds", help="시드 이미지 폴더")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--clips", type=int, default=None)
    ap.add_argument("--mode", default=None, choices=["chain", "montage"])
    ap.add_argument("--title", default=None)
    ap.add_argument("--series", default=None,
                    help="연재 제목. 'Infinite peace' → 'Infinite peace part 17'")
    ap.add_argument("--publish", action="store_true", help="생성 후 업로드까지")
    ap.add_argument("--youtube", action="store_true")
    ap.add_argument("--instagram", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    seeds_dir = Path(args.seeds)
    if not seeds_dir.is_dir():
        print(f"✗ 시드 폴더가 없습니다: {seeds_dir}")
        return 1
    seed = pick_seed(seeds_dir)
    if seed is None:
        print(f"✗ {seeds_dir} 에 사용 가능한 이미지가 없습니다.")
        return 1

    print(f"▶ {datetime.now():%Y-%m-%d %H:%M}  시드: {seed.name}")

    gen = [sys.executable, "main.py", "generate", "--image", str(seed),
           "--config", args.config, "--yes"]
    if args.clips:
        gen += ["--clips", str(args.clips)]
    if args.mode:
        gen += ["--mode", args.mode]
    if _run(gen) != 0:
        print("✗ 생성 실패 — 업로드를 건너뜁니다.")
        return 1
    retire_seed(seed)

    if not args.publish:
        return 0

    run_id = latest_run()
    if not run_id:
        print("✗ 업로드할 run 을 찾지 못했습니다.")
        return 1

    title = args.title or seed.stem.replace("_", " ").title()
    if args.series:
        # runs 개수로 회차를 매긴다. 연재 형태(@cyborg.digitalart 'part N')를 흉내낸다.
        n = len([p for p in (ROOT / "runs").iterdir() if p.is_dir()])
        title = f"{args.series} part {n}"

    pub = [sys.executable, "main.py", "publish", "--run", run_id, "--title", title]
    if args.youtube:
        pub.append("--youtube")
    if args.instagram:
        pub.append("--instagram")
    if args.dry_run:
        pub.append("--dry-run")
    if not (args.youtube or args.instagram):
        pub.append("--youtube")
    return _run(pub)


if __name__ == "__main__":
    sys.exit(main())
