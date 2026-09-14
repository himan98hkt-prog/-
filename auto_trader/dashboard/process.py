"""대시보드에서 매매 프로세스를 켜고 끄고 재시작한다.

키를 바꿔도 이미 떠 있는 프로세스는 옛 설정을 들고 있다 —
**재시작해야 반영된다.** 그 재시작을 버튼 하나로 할 수 있게 한다.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.runtime import ProcessLock, pid_path

logger = get_logger("dashboard.process")

START_TIMEOUT_SEC = 20  # 기동 후 PID 파일이 생길 때까지 기다리는 시간
SETTLE_SEC = 8  # PID 가 생긴 뒤 '진짜로 살아 있는지' 지켜보는 시간
STOP_TIMEOUT_SEC = 90  # 진행 중 사이클을 마칠 시간 (체결 대기 30초 + 여유)
POLL_SEC = 0.5


@dataclass
class ControlResult:
    ok: bool
    message: str


def _stdout_log(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "stdout.log"


def is_running(data_dir: Path) -> bool:
    return ProcessLock(pid_path(data_dir)).is_running()


def start(base_dir: Path, data_dir: Path, log_dir: Path) -> ControlResult:
    """`main.py` 를 백그라운드로 띄운다. 이미 돌고 있으면 아무것도 하지 않는다."""
    if is_running(data_dir):
        return ControlResult(False, "이미 실행 중입니다.")

    log_file = _stdout_log(log_dir)
    creation: dict = {}
    if os.name == "nt":  # Windows
        creation["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        creation["start_new_session"] = True  # 대시보드를 껐다 켜도 봇은 살아 있게

    try:
        with log_file.open("a", encoding="utf-8") as handle:
            subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=str(base_dir),
                stdout=handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                **creation,
            )
    except OSError as exc:
        logger.exception("매매 프로세스 기동 실패")
        return ControlResult(False, f"기동에 실패했습니다: {exc}")

    # 1) PID 파일이 생길 때까지 기다린다.
    deadline = time.monotonic() + START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if is_running(data_dir):
            break
        time.sleep(POLL_SEC)
    else:
        return _failure(log_file, "기동했지만 응답이 없습니다")

    # 2) 잠깐 지켜본다. 키가 틀렸거나 잔고 조회에 실패하면 몇 초 만에 죽는다 —
    #    그걸 '시작 성공' 이라고 알리면 사용자가 원인을 영영 못 본다.
    settle = time.monotonic() + SETTLE_SEC
    while time.monotonic() < settle:
        if not is_running(data_dir):
            return _failure(log_file, "기동 직후 종료됐습니다")
        time.sleep(POLL_SEC)

    logger.info("매매 프로세스 기동 완료")
    return ControlResult(True, "자동매매를 시작했습니다.")


def _failure(log_file: Path, headline: str) -> ControlResult:
    """실패 사유를 로그 꼬리와 함께 돌려준다 — 사용자가 원인을 바로 보게."""
    tail = _tail(log_file, 15)
    reason = _first_error(tail)
    logger.error("%s\n%s", headline, tail)
    detail = f" — {reason}" if reason else ""
    return ControlResult(False, f"{headline}{detail}\n\n최근 출력:\n{tail or '(출력 없음)'}")


def _first_error(tail: str) -> str:
    """로그 꼬리에서 가장 도움이 되는 한 줄을 뽑는다."""
    for line in reversed(tail.splitlines()):
        if "[ERROR" in line or "[CRITICAL" in line or "설정 오류" in line:
            # 타임스탬프·레벨 표시를 걷어내고 본문만
            return line.split("]", 1)[-1].strip().lstrip(":").strip()[:200]
    return ""


def stop(data_dir: Path) -> ControlResult:
    """SIGTERM 을 보내 진행 중 사이클을 마치고 안전하게 종료시킨다."""
    lock = ProcessLock(pid_path(data_dir))
    pid = lock.read_pid()
    if not lock.is_running() or pid is None:
        return ControlResult(False, "실행 중이 아닙니다.")

    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError) as exc:
        return ControlResult(False, f"종료 신호를 보내지 못했습니다: {exc}")

    logger.info("종료 신호 전송 (PID %d) — 진행 중 사이클 완료 대기", pid)
    deadline = time.monotonic() + STOP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if not lock.is_running():
            return ControlResult(True, "자동매매를 종료했습니다.")
        time.sleep(POLL_SEC)

    return ControlResult(
        False,
        f"{STOP_TIMEOUT_SEC}초 안에 종료되지 않았습니다. 진행 중인 사이클이 길어지는 중일 수 있습니다.",
    )


def restart(base_dir: Path, data_dir: Path, log_dir: Path) -> ControlResult:
    """설정을 다시 읽도록 껐다 켠다 — 키를 바꾼 뒤 반영하는 방법."""
    if is_running(data_dir):
        stopped = stop(data_dir)
        if not stopped.ok:
            return ControlResult(False, f"재시작 실패 — {stopped.message}")
    started = start(base_dir, data_dir, log_dir)
    if started.ok:
        return ControlResult(True, "새 설정으로 재시작했습니다.")
    return started


def _tail(path: Path, lines: int) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""
