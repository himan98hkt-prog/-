"""매일 정해진 시각에 1편을 만들어 유튜브·인스타에 올린다.

  # 매일 저녁 9시 정각 게시 (20:30 에 시작해 만들고, 21:00 까지 기다렸다 올린다)
  30 20 * * *  cd /path/to/shorts-pipeline && python -m publish.scheduler \
                 --at 21:00 --youtube --instagram

생성에 5~10분이 걸리므로, 게시 시각보다 앞서 시작해 --at 으로 정각을 맞춘다.
시드는 seeds/ 에서 하나 고르고, 성공하면 seeds/_used/ 로 옮겨 재사용을 막는다.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_WAIT = timedelta(hours=3)   # --at 대기 상한. 이보다 길면 그냥 올린다.


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def append_history(line: str, runs_dir: Path | None = None) -> None:
    """cron 로그가 유실돼도 남도록 실행 이력을 따로 적는다."""
    path = (runs_dir or ROOT / "runs") / "schedule.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{line}\n")


def pick_seed(seeds_dir: Path, *, shuffle: bool = True) -> Path | None:
    """아직 쓰지 않은 시드를 하나 고른다. 사이드카가 있는 것을 우선한다."""
    from pipeline.content import find_sidecar

    (seeds_dir / "_used").mkdir(exist_ok=True)
    candidates = [p for p in sorted(seeds_dir.iterdir())
                  if p.is_file() and p.suffix.lower() in _IMAGE_EXT]
    if not candidates:
        return None
    # 제목이 준비된 시드를 먼저 소진한다
    described = [p for p in candidates if find_sidecar(p)]
    pool = described or candidates
    return random.choice(pool) if shuffle else pool[0]


def retire_seed(seed: Path) -> None:
    """쓴 시드와 사이드카를 _used/ 로 옮긴다."""
    from pipeline.content import find_sidecar

    used = seed.parent / "_used"
    used.mkdir(exist_ok=True)
    for path in filter(None, (seed, find_sidecar(seed))):
        try:
            shutil.move(str(path), str(used / path.name))
        except OSError as exc:
            log(f"  ⚠ {path.name} 이동 실패 ({exc}) — 다음 실행에 중복될 수 있습니다.")


def latest_run(runs_dir: Path | None = None, *, newer_than: float = 0.0) -> str | None:
    """방금 만든 영상의 run ID.

    `newer_than` 은 생성을 시작한 시각이다. 이걸 넘기지 않으면 **이전에
    만들어 둔 영상을 집어서 올린다** — 생성이 실패했는데 어제 영상이
    다시 올라가는 경로다. 채널이 둘이면 남의 채널 영상까지 후보가 된다.
    """
    runs = runs_dir or ROOT / "runs"
    if not runs.is_dir():
        return None
    dirs = [p for p in runs.iterdir()
            if p.is_dir() and (p / "final.mp4").exists()
            and (p / "final.mp4").stat().st_mtime >= newer_than]
    return max(dirs, key=lambda p: (p / "final.mp4").stat().st_mtime).name if dirs else None


def wait_until(clock: str) -> None:
    """HH:MM 까지 기다린다. 이미 지났으면 바로 진행한다."""
    try:
        hh, mm = (int(x) for x in clock.split(":"))
        target = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    except ValueError:
        log(f"  ⚠ --at 형식이 잘못됐습니다 ({clock}). 기다리지 않고 진행합니다.")
        return

    delta = target - datetime.now()
    if delta.total_seconds() <= 0:
        log(f"  게시 예정 시각 {clock} 이 이미 지났습니다. 바로 올립니다.")
        return
    if delta > _MAX_WAIT:
        log(f"  ⚠ {clock} 까지 {delta} 남아 대기 상한을 넘습니다. 바로 올립니다.")
        return
    log(f"  {clock} 까지 {int(delta.total_seconds() // 60)}분 대기…")
    time.sleep(delta.total_seconds())


def run(args: list[str]) -> int:
    log(f"  $ {' '.join(args[1:])}")
    return subprocess.call(args, cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="정기 생성·업로드 배치")
    ap.add_argument("--seeds", default=None,
                    help="시드 폴더. 생략하면 설정의 channel.seeds_dir 을 쓴다")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--clips", type=int, default=None)
    ap.add_argument("--mode", default=None, choices=["chain", "montage"])
    ap.add_argument("--at", default=None, metavar="HH:MM",
                    help="이 시각까지 기다렸다 게시한다 (예: 21:00)")
    ap.add_argument("--series", default=None,
                    help="연재 제목. 사이드카 제목보다 우선한다")
    ap.add_argument("--youtube", action="store_true")
    ap.add_argument("--instagram", action="store_true")
    ap.add_argument("--generate-only", action="store_true", help="만들기만 하고 끝낸다")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT))

    # 어느 채널인지는 설정이 정한다 — 산출물 폴더·시드 폴더가 채널마다 다르다.
    from pipeline.config import ConfigError, load_config

    try:
        cfg = load_config(ROOT / args.config)
    except ConfigError as exc:
        log(f"✗ 설정을 읽지 못했습니다: {exc}")
        append_history(f"FAIL\t설정 오류\t{args.config}")
        return 1

    runs_dir = _under_root(cfg.runs_dir)
    label = cfg.channel_name or cfg.channel_slug
    log(f"■ 채널 {label} (설정 {args.config})")

    seeds_dir = _under_root(args.seeds or cfg.seeds_dir)
    if not seeds_dir.is_dir():
        log(f"✗ 시드 폴더가 없습니다: {seeds_dir}")
        append_history("FAIL\t시드 폴더 없음", runs_dir)
        return 1

    seed = pick_seed(seeds_dir)
    if seed is None:
        log(f"✗ {seeds_dir} 에 남은 시드가 없습니다. 이미지를 더 넣어주세요.")
        append_history("FAIL\t시드 소진", runs_dir)
        return 1

    from pipeline.content import load_content

    content = load_content(seed)
    log(f"▶ 시드 {seed.name} — 「{content.title}」")

    # ── 생성 ─────────────────────────────────────────────────────────
    gen = [sys.executable, "main.py", "generate", "--image", str(seed),
           "--config", args.config, "--yes"]
    if args.clips:
        gen += ["--clips", str(args.clips)]
    if args.mode:
        gen += ["--mode", args.mode]
    # 파일 시각의 해상도가 1초인 파일 시스템이 있어 1초 빼고 잰다.
    started = time.time() - 1
    if run(gen) != 0:
        log("✗ 생성 실패 — 업로드를 건너뜁니다. 시드는 그대로 둡니다.")
        append_history(f"FAIL\t생성 실패\t{seed.name}", runs_dir)
        return 1

    run_id = latest_run(runs_dir, newer_than=started)
    if not run_id:
        # 이전 영상으로 대체하지 않는다. 어제 올린 것을 오늘 또 올리는 것보다
        # 오늘 안 올리는 편이 낫다 — 중복 업로드는 되돌릴 수 없다.
        log("✗ 이번 실행에서 만들어진 영상을 찾지 못했습니다.")
        append_history(f"FAIL\t결과물 없음\t{seed.name}", runs_dir)
        return 1
    log(f"  생성 완료 — run {run_id}")

    if args.generate_only:
        retire_seed(seed)
        append_history(f"OK\t생성만\t{run_id}\t{content.title}", runs_dir)
        return 0

    if not (args.youtube or args.instagram):
        args.youtube = True

    if args.at:
        wait_until(args.at)

    # ── 업로드 — 한쪽이 실패해도 다른 쪽은 시도한다 ───────────────────
    title = args.series and f"{args.series} part {_series_no(args.series, runs_dir)}" or content.title
    results = []
    for flag, label in (("--youtube", "유튜브"), ("--instagram", "인스타그램")):
        if not getattr(args, flag.lstrip("-")):
            continue
        cmd = [sys.executable, "main.py", "publish", "--run", run_id,
               "--config", args.config, "--title", title, flag]
        if args.dry_run:
            cmd.append("--dry-run")
        code = run(cmd)
        results.append((label, code == 0))
        log(f"  {label}: {'성공' if code == 0 else '실패'}")

    ok = [n for n, good in results if good]
    bad = [n for n, good in results if not good]
    if ok:
        retire_seed(seed)   # 한 곳이라도 올라갔으면 시드를 소진 처리한다
    append_history(
        f"{'OK' if not bad else 'PARTIAL'}\t{run_id}\t{title}\t"
        f"성공={','.join(ok) or '-'}\t실패={','.join(bad) or '-'}", runs_dir)
    return 0 if not bad else 1


def _under_root(path: str | Path) -> Path:
    """설정·인자의 상대 경로는 저장소 폴더 기준으로 푼다."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _series_no(series: str, runs_dir: Path | None = None) -> int:
    """연재 회차. schedule.log 에서 같은 시리즈가 몇 번 올라갔는지 센다."""
    path = (runs_dir or ROOT / "runs") / "schedule.log"
    if not path.exists():
        return 1
    n = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
            if f"{series} part" in line)
    return n + 1


if __name__ == "__main__":
    sys.exit(main())
