"""Module G — 예약 실행.

집 PC 에서 정기적으로 돌도록 OS 기본 스케줄러에 작업을 등록한다.
윈도우는 작업 스케줄러(schtasks), 리눅스는 cron, macOS 는 launchd 를 쓴다.
별도 상주 프로그램을 두지 않으므로 PC 를 껐다 켜도 그대로 살아 있다.

명령 문자열을 만드는 함수는 부수효과가 없어, 실제로 등록하지 않고도
무엇이 등록될지 확인(``--dry-run``)하고 테스트할 수 있다.
"""

from __future__ import annotations

import os
import platform
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .utils import get_logger

__all__ = [
    "Schedule",
    "TASK_NAME",
    "detect_platform",
    "parse_time",
    "build_auto_command",
    "cron_line",
    "schtasks_command",
    "launchd_plist",
    "install_schedule",
    "remove_schedule",
    "show_schedule",
    "ScheduleError",
]

LOG = get_logger("scheduler")

TASK_NAME = "AutoShortsEngine"
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2})[:시]?(?P<minute>\d{2})?$")

WEEKDAYS = {
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0,
    "월": 1, "화": 2, "수": 3, "목": 4, "금": 5, "토": 6, "일": 0,
}


class ScheduleError(RuntimeError):
    """예약 등록 실패."""


@dataclass
class Schedule:
    """실행 주기."""

    hour: int = 9
    minute: int = 0
    weekday: int | None = None      # None 이면 매일. 0=일 ~ 6=토
    every_hours: int | None = None  # 설정하면 N시간마다 (hour/minute 무시)

    def __post_init__(self) -> None:
        if self.every_hours is not None:
            if not 1 <= self.every_hours <= 23:
                raise ValueError("every_hours 는 1~23 사이여야 합니다.")
        if not 0 <= self.hour <= 23:
            raise ValueError(f"시(hour)는 0~23 이어야 합니다: {self.hour}")
        if not 0 <= self.minute <= 59:
            raise ValueError(f"분(minute)은 0~59 여야 합니다: {self.minute}")
        if self.weekday is not None and not 0 <= self.weekday <= 6:
            raise ValueError(f"요일은 0(일)~6(토) 이어야 합니다: {self.weekday}")

    @property
    def description(self) -> str:
        if self.every_hours:
            return f"{self.every_hours}시간마다"
        names = ["일", "월", "화", "수", "목", "금", "토"]
        when = f"{self.hour:02d}:{self.minute:02d}"
        if self.weekday is None:
            return f"매일 {when}"
        return f"매주 {names[self.weekday]}요일 {when}"


def parse_time(text: str) -> tuple[int, int]:
    """``09:00`` / ``9`` / ``21시30`` 을 (시, 분) 으로 바꾼다."""
    value = str(text or "").strip()
    if ":" in value:
        head, _, tail = value.partition(":")
        try:
            hour, minute = int(head), int(tail or 0)
        except ValueError:
            raise ValueError(f"시각을 해석할 수 없습니다: {text!r}") from None
    else:
        match = _TIME_RE.match(value)
        if not match:
            raise ValueError(f"시각을 해석할 수 없습니다: {text!r}")
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"시각 범위를 벗어났습니다: {text!r}")
    return hour, minute


def parse_weekday(text: str | None) -> int | None:
    if text is None or str(text).strip() == "":
        return None
    key = str(text).strip().lower()[:3]
    if key in WEEKDAYS:
        return WEEKDAYS[key]
    key1 = str(text).strip()[0]
    if key1 in WEEKDAYS:
        return WEEKDAYS[key1]
    raise ValueError(f"요일을 해석할 수 없습니다: {text!r}")


def detect_platform() -> str:
    """``windows`` / ``macos`` / ``linux``."""
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def _python_executable() -> str:
    return sys.executable or "python3"


def build_auto_command(
    target: str,
    *,
    extra_args: Sequence[str] = (),
    python: str | None = None,
    log_path: str | Path | None = None,
) -> list[str]:
    """예약에 등록할 실제 실행 명령(``autoshorts auto ...``)."""
    command = [python or _python_executable(), "-m", "autoshorts", "auto", target]
    command.extend(str(a) for a in extra_args)
    return command


def _quote(command: Sequence[str]) -> str:
    if detect_platform() == "windows":
        return " ".join(f'"{part}"' if " " in str(part) else str(part) for part in command)
    return " ".join(shlex.quote(str(part)) for part in command)


def cron_line(schedule: Schedule, command: Sequence[str], *, log_path: str | Path | None = None) -> str:
    """crontab 한 줄을 만든다."""
    if schedule.every_hours:
        timing = f"0 */{schedule.every_hours} * * *"
    else:
        weekday = "*" if schedule.weekday is None else str(schedule.weekday)
        timing = f"{schedule.minute} {schedule.hour} * * {weekday}"
    body = _quote(command)
    if log_path:
        body += f" >> {shlex.quote(str(log_path))} 2>&1"
    return f"{timing} {body} # {TASK_NAME}"


def schtasks_command(
    schedule: Schedule, command: Sequence[str], *, task_name: str = TASK_NAME
) -> list[str]:
    """윈도우 작업 스케줄러 등록 명령."""
    args = ["schtasks", "/Create", "/F", "/TN", task_name, "/TR", _quote(command)]
    if schedule.every_hours:
        args += ["/SC", "HOURLY", "/MO", str(schedule.every_hours)]
    elif schedule.weekday is None:
        args += ["/SC", "DAILY", "/ST", f"{schedule.hour:02d}:{schedule.minute:02d}"]
    else:
        names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        args += [
            "/SC", "WEEKLY", "/D", names[schedule.weekday],
            "/ST", f"{schedule.hour:02d}:{schedule.minute:02d}",
        ]
    return args


def launchd_plist(
    schedule: Schedule,
    command: Sequence[str],
    *,
    label: str = "com.autoshorts.engine",
    log_path: str | Path | None = None,
) -> str:
    """macOS launchd 용 plist 문서."""
    program_args = "".join(f"        <string>{part}</string>\n" for part in command)
    if schedule.every_hours:
        interval = f"    <key>StartInterval</key>\n    <integer>{schedule.every_hours * 3600}</integer>\n"
    else:
        rows = [f"        <key>Hour</key>\n        <integer>{schedule.hour}</integer>",
                f"        <key>Minute</key>\n        <integer>{schedule.minute}</integer>"]
        if schedule.weekday is not None:
            rows.append(f"        <key>Weekday</key>\n        <integer>{schedule.weekday}</integer>")
        interval = "    <key>StartCalendarInterval</key>\n    <dict>\n" + "\n".join(rows) + "\n    </dict>\n"

    logs = ""
    if log_path:
        logs = (
            f"    <key>StandardOutPath</key>\n    <string>{log_path}</string>\n"
            f"    <key>StandardErrorPath</key>\n    <string>{log_path}</string>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"    <key>Label</key>\n    <string>{label}</string>\n"
        "    <key>ProgramArguments</key>\n    <array>\n"
        f"{program_args}"
        "    </array>\n"
        f"{interval}{logs}"
        "    <key>RunAtLoad</key>\n    <false/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def _current_crontab() -> str:
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ScheduleError("crontab 명령을 찾을 수 없습니다.") from exc
    return proc.stdout if proc.returncode == 0 else ""


def _write_crontab(content: str) -> None:
    proc = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise ScheduleError(f"crontab 등록 실패: {proc.stderr.strip()}")


def install_schedule(
    schedule: Schedule,
    command: Sequence[str],
    *,
    log_path: str | Path | None = None,
    dry_run: bool = False,
    target_platform: str | None = None,
) -> str:
    """OS 스케줄러에 등록하고, 등록한 내용을 문자열로 돌려준다."""
    system = target_platform or detect_platform()

    if system == "windows":
        args = schtasks_command(schedule, command)
        preview = " ".join(args)
        if dry_run:
            return preview
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise ScheduleError(f"작업 스케줄러 등록 실패: {proc.stderr.strip() or proc.stdout.strip()}")
        return preview

    if system == "macos":
        plist = launchd_plist(schedule, command, log_path=log_path)
        destination = Path.home() / "Library" / "LaunchAgents" / "com.autoshorts.engine.plist"
        if dry_run:
            return f"# {destination}\n{plist}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(plist, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(destination)], capture_output=True, check=False)
        proc = subprocess.run(["launchctl", "load", str(destination)], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise ScheduleError(f"launchd 등록 실패: {proc.stderr.strip()}")
        return f"# {destination}\n{plist}"

    line = cron_line(schedule, command, log_path=log_path)
    if dry_run:
        return line
    existing = [l for l in _current_crontab().splitlines() if TASK_NAME not in l]
    existing.append(line)
    _write_crontab("\n".join(existing).strip() + "\n")
    return line


def remove_schedule(*, target_platform: str | None = None) -> bool:
    """등록된 예약을 지운다. 지운 게 있으면 True."""
    system = target_platform or detect_platform()

    if system == "windows":
        proc = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", TASK_NAME], capture_output=True, text=True, check=False
        )
        return proc.returncode == 0

    if system == "macos":
        destination = Path.home() / "Library" / "LaunchAgents" / "com.autoshorts.engine.plist"
        if not destination.exists():
            return False
        subprocess.run(["launchctl", "unload", str(destination)], capture_output=True, check=False)
        destination.unlink()
        return True

    lines = _current_crontab().splitlines()
    kept = [l for l in lines if TASK_NAME not in l]
    if len(kept) == len(lines):
        return False
    _write_crontab("\n".join(kept).strip() + "\n")
    return True


def show_schedule(*, target_platform: str | None = None) -> str:
    """현재 등록된 예약을 사람이 읽을 형태로 돌려준다."""
    system = target_platform or detect_platform()
    if system == "windows":
        proc = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
            capture_output=True, text=True, check=False,
        )
        return proc.stdout.strip() or "등록된 예약이 없습니다."
    if system == "macos":
        destination = Path.home() / "Library" / "LaunchAgents" / "com.autoshorts.engine.plist"
        return destination.read_text(encoding="utf-8") if destination.exists() else "등록된 예약이 없습니다."
    lines = [l for l in _current_crontab().splitlines() if TASK_NAME in l]
    return "\n".join(lines) if lines else "등록된 예약이 없습니다."
