"""윈도우 작업 스케줄러 연동.

매일 정해진 시각에 자동 업로드가 돌도록 예약을 만들고 지운다.
관리자 권한 없이 현재 사용자 계정으로 등록된다.

리눅스·맥에서는 동작하지 않는다. supported() 로 먼저 확인할 것.
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

TASK_NAME = "AI DEOKHU 자동업로드"
ROOT = Path(__file__).resolve().parent.parent

# 생성에 5~10분이 걸리므로 게시 시각보다 앞서 시작한다.
LEAD_MINUTES = 30


@dataclass
class Schedule:
    enabled: bool
    start_time: str = ""        # 작업이 시작되는 시각 (HH:MM)
    publish_time: str = ""      # 실제 게시 시각 (HH:MM)
    next_run: str = ""
    targets: list[str] = None
    raw: str = ""

    def __post_init__(self):
        if self.targets is None:
            self.targets = []


def supported() -> bool:
    return platform.system() == "Windows"


def _run(args: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _minus(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    t = datetime(2000, 1, 1, h, m) - timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def write_runner(publish_time: str, targets: list[str], mode: str = "chain") -> Path:
    """예약이 실행할 배치 파일. 폴더를 옮겨도 따라가도록 %~dp0 을 쓴다."""
    flags = " ".join(f"--{t}" for t in targets) or "--youtube"
    bat = ROOT / "daily.bat"
    bat.write_text(
        "@echo off\r\n"
        "REM AI DEOKHU 매일 자동 업로드 — 작업 스케줄러가 실행합니다.\r\n"
        "REM 화면에서 예약을 켤 때 자동으로 만들어집니다. 직접 고치지 마세요.\r\n"
        'cd /d "%~dp0"\r\n'
        f"python -m publish.scheduler --at {publish_time} --mode {mode} {flags} "
        '>> "%~dp0runs\\cron.log" 2>&1\r\n',
        encoding="utf-8")
    return bat


def enable(publish_time: str = "21:00", targets: list[str] | None = None,
           mode: str = "chain") -> tuple[bool, str]:
    """매일 실행 예약을 만든다. 이미 있으면 덮어쓴다."""
    if not supported():
        return False, "윈도우에서만 예약을 만들 수 있습니다."
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", publish_time):
        return False, f"시각 형식이 잘못됐습니다: {publish_time} (예: 21:00)"

    targets = targets or ["youtube"]
    bad = [t for t in targets if t not in ("youtube", "instagram")]
    if bad:
        return False, f"알 수 없는 업로드 대상: {', '.join(bad)}"

    bat = write_runner(publish_time, targets, mode)
    start = _minus(publish_time, LEAD_MINUTES)

    code, out = _run(["schtasks", "/Create", "/TN", TASK_NAME,
                      "/TR", f'"{bat}"', "/SC", "DAILY", "/ST", start, "/F"])
    if code != 0:
        return False, f"예약 등록 실패:\n{out.strip()[:400]}"
    return True, (f"매일 {start} 에 시작해 {publish_time} 에 게시합니다. "
                  f"(생성 시간 {LEAD_MINUTES}분 확보)")


def disable() -> tuple[bool, str]:
    if not supported():
        return False, "윈도우에서만 예약을 지울 수 있습니다."
    code, out = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if code != 0 and "ERROR" in out.upper() and "cannot find" not in out.lower():
        return False, f"예약 해제 실패:\n{out.strip()[:300]}"
    return True, "예약을 껐습니다."


def status() -> Schedule:
    """현재 예약 상태. 없으면 enabled=False."""
    if not supported():
        return Schedule(enabled=False, raw="윈도우가 아닙니다.")

    code, out = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])
    if code != 0:
        return Schedule(enabled=False, raw=out.strip()[:200])

    def field(*names: str) -> str:
        for line in out.splitlines():
            for n in names:
                if line.strip().startswith(n):
                    return line.split(":", 1)[1].strip() if ":" in line else ""
        return ""

    next_run = field("Next Run Time", "다음 실행 시간")
    start = field("Start Time", "시작 시간")
    # 등록된 배치에서 실제 게시 시각과 대상을 되읽는다
    publish_time, targets = "", []
    bat = ROOT / "daily.bat"
    if bat.exists():
        text = bat.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"--at\s+(\d{2}:\d{2})", text)
        if m:
            publish_time = m.group(1)
        targets = [t for t in ("youtube", "instagram") if f"--{t}" in text]

    return Schedule(enabled=True, start_time=start, publish_time=publish_time,
                    next_run=next_run, targets=targets, raw="")
