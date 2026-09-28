"""매일 정해진 시각에 1편을 만들어 유튜브·인스타에 올린다.

  # 매일 저녁 9시 정각 게시 (20:30 에 시작해 만들고, 21:00 까지 기다렸다 올린다)
  30 20 * * *  cd /path/to/shorts-pipeline && python -m publish.scheduler \
                 --at 21:00 --youtube --instagram

생성에 5~10분이 걸리므로, 게시 시각보다 앞서 시작해 --at 으로 정각을 맞춘다.
시드는 seeds/ 에서 하나 고르고, 성공하면 seeds/_used/ 로 옮겨 재사용을 막는다.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.console import child_env, make_safe  # noqa: E402
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_WAIT = timedelta(hours=3)   # --at 대기 상한. 이보다 길면 그냥 올린다.


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# 예약 실행이 창 없이(pythonw) 돌 때 출력을 받을 파일. --log 로 연다.
_LOG_FH = None

# 윈도우에서 자식 프로세스가 검은 창을 띄우지 않게 한다. 아침에 뜬 빈 창을
# 누가 닫아버리면 그대로 작업이 죽는다.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

STATE_NAME = "schedule_state.json"

# 이 실행이 다루는 채널의 산출물 폴더. 설정을 읽는 순간 그 채널 것으로 바뀐다
# (main 참고). 채널마다 갈라 두지 않으면 latest_run 이 남의 채널 영상을 집고,
# 이력·상태 파일도 한 통에 섞인다.
RUNS_DIR = ROOT / "runs"


def _under_root(path) -> Path:
    """설정·인자의 상대 경로는 저장소 폴더 기준으로 푼다."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def child_python() -> str:
    """자식에게 쓸 파이썬. 예약은 창 없는 pythonw 로 도는데, 자식까지 pythonw 면
    출력 핸들을 못 잡는 경우가 있다. 같은 폴더의 python.exe 를 창 없이 띄운다."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return sys.executable


def write_state(**fields) -> None:
    """마지막 예약 실행이 어디까지 갔는지. 작업실의 '왜 안 됐나' 가 읽는다."""
    path = RUNS_DIR / STATE_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        old = {}
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                old = {}
        old.update(fields)
        path.write_text(json.dumps(old, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass


def open_log(path: str) -> None:
    """출력을 파일로 돌린다. pythonw 는 stdout 이 없어서 이게 없으면 다 사라진다."""
    global _LOG_FH
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    _LOG_FH = target.open("a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = _LOG_FH


def append_history(line: str) -> None:
    """cron 로그가 유실돼도 남도록 실행 이력을 따로 적는다."""
    path = RUNS_DIR / "schedule.log"
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


def latest_run(newer_than: float = 0.0) -> str | None:
    """방금 만든 영상의 run ID.

    `newer_than` 은 생성을 시작한 시각이다. 이걸 넘기지 않으면 **이전에
    만들어 둔 영상을 집어서 올린다** — 생성이 실패했는데 어제 영상이 다시
    올라가는 경로다. 중복 업로드는 되돌릴 수 없으니 하루 거르는 편이 낫다.
    """
    runs = RUNS_DIR
    if not runs.is_dir():
        return None
    dirs = [p for p in runs.iterdir()
            if p.is_dir() and (p / "final.mp4").exists()
            and (p / "final.mp4").stat().st_mtime >= newer_than]
    return max(dirs,
               key=lambda p: (p / "final.mp4").stat().st_mtime).name if dirs else None


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
    """자식 파이썬을 돌린다. UTF-8 을 넘기고, 창을 띄우지 않고, 같은 로그에 쓴다."""
    log(f"  $ {' '.join(args[1:])}")
    out = _LOG_FH
    return subprocess.call(args, cwd=ROOT, env=child_env(),
                           stdout=out, stderr=subprocess.STDOUT if out else None,
                           creationflags=_NO_WINDOW)


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
    ap.add_argument("--log", default=None, metavar="PATH",
                    help="출력을 이 파일에 덧붙인다 (창 없이 돌 때)")
    args = ap.parse_args(argv)

    if args.log:
        open_log(args.log)
    make_safe()

    # 어느 채널인지 먼저 정한다. 아래 write_state 가 벌써 산출물 폴더에 쓰므로
    # 설정을 읽기 전에 부르면 상태 파일이 기본 채널 폴더로 가 버린다.
    global RUNS_DIR
    sys.path.insert(0, str(ROOT))
    from pipeline.config import ConfigError, load_config

    try:
        cfg = load_config(_under_root(args.config))
    except ConfigError as exc:
        log(f"✗ 설정을 읽지 못했습니다: {exc}")
        return 1
    RUNS_DIR = _under_root(cfg.runs_dir)
    args.channel = cfg
    log(f"■ 채널 {cfg.channel_name or cfg.channel_slug} (설정 {args.config})")

    started = datetime.now().isoformat(timespec="seconds")
    write_state(started=started, finished="", result="running", message="",
                pid=os.getpid())
    try:
        code = _main(args)
    except Exception as exc:                           # noqa: BLE001
        # 무엇으로 죽었는지 남기지 않으면 사람은 "그냥 안 됐다" 밖에 모른다.
        traceback.print_exc()
        msg = f"{type(exc).__name__}: {exc}"[:300]
        append_history(f"FAIL\t예상 못 한 오류\t{msg}")
        write_state(finished=datetime.now().isoformat(timespec="seconds"),
                    result="crash", message=msg)
        return 1
    last = _last_history()
    write_state(finished=datetime.now().isoformat(timespec="seconds"),
                result="ok" if code == 0 else "fail", message=last)
    return code


def _last_history() -> str:
    path = RUNS_DIR / "schedule.log"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return lines[-1][:300] if lines else ""


def _main(args) -> int:
    seeds_dir = _under_root(args.seeds or args.channel.seeds_dir)
    if not seeds_dir.is_dir():
        log(f"✗ 시드 폴더가 없습니다: {seeds_dir}")
        append_history("FAIL\t시드 폴더 없음")
        return 1

    seed = pick_seed(seeds_dir)
    if seed is None:
        log(f"✗ {seeds_dir} 에 남은 시드가 없습니다. 이미지를 더 넣어주세요.")
        append_history("FAIL\t시드 소진")
        return 1

    from pipeline.content import load_content

    content = load_content(seed)
    log(f"▶ 시드 {seed.name} — 「{content.title}」")

    # ── 생성 ─────────────────────────────────────────────────────────
    gen = [child_python(), "main.py", "generate", "--image", str(seed),
           "--config", args.config, "--yes"]
    if args.clips:
        gen += ["--clips", str(args.clips)]
    if args.mode:
        gen += ["--mode", args.mode]
    # 파일 시각의 해상도가 1초인 파일 시스템이 있어 1초 빼고 잰다.
    started = time.time() - 1
    if run(gen) != 0:
        log("✗ 생성 실패 — 업로드를 건너뜁니다. 시드는 그대로 둡니다.")
        append_history(f"FAIL\t생성 실패\t{seed.name}")
        return 1

    run_id = latest_run(newer_than=started)
    if not run_id:
        # 이전 영상으로 대체하지 않는다. 어제 올린 것을 오늘 또 올리는 것보다
        # 오늘 안 올리는 편이 낫다 — 중복 업로드는 되돌릴 수 없다.
        log("✗ 이번 실행에서 만들어진 영상을 찾지 못했습니다.")
        append_history(f"FAIL\t결과물 없음\t{seed.name}")
        return 1
    log(f"  생성 완료 — run {run_id}")

    if args.generate_only:
        retire_seed(seed)
        append_history(f"OK\t생성만\t{run_id}\t{content.title}")
        return 0

    if not (args.youtube or args.instagram):
        args.youtube = True

    if args.at:
        wait_until(args.at)

    # ── 업로드 — 한쪽이 실패해도 다른 쪽은 시도한다 ───────────────────
    title = args.series and f"{args.series} part {_series_no(args.series)}" or content.title
    results = []
    for flag, label in (("--youtube", "유튜브"), ("--instagram", "인스타그램")):
        if not getattr(args, flag.lstrip("-")):
            continue
        cmd = [child_python(), "main.py", "publish", "--run", run_id,
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
        f"성공={','.join(ok) or '-'}\t실패={','.join(bad) or '-'}")
    return 0 if not bad else 1


def _series_no(series: str) -> int:
    """연재 회차. schedule.log 에서 같은 시리즈가 몇 번 올라갔는지 센다."""
    path = RUNS_DIR / "schedule.log"
    if not path.exists():
        return 1
    n = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
            if f"{series} part" in line)
    return n + 1


if __name__ == "__main__":
    sys.exit(main())
