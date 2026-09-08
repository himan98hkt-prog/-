"""단일 실행 보장과 긴급 정지.

- **PID 락**: 같은 계좌에 두 프로세스가 붙으면 같은 종목을 두 번 매수한다.
  기동 시 락을 잡고, 죽은 프로세스의 락은 자동으로 회수한다.
- **긴급 정지**: `data/STOP` 파일이 있으면 새 사이클을 시작하지 않는다.
  대시보드 버튼이나 `touch data/STOP` 으로 즉시 멈출 수 있다.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("runtime")

STOP_FILENAME = "STOP"
PID_FILENAME = "trader.pid"
PID_WRITE_GRACE_SEC = 1.0  # 락 파일 생성 직후 PID 가 적히기를 기다리는 시간


class AlreadyRunningError(RuntimeError):
    """다른 프로세스가 이미 실행 중."""


def _process_alive(pid: int) -> bool:
    """해당 PID 의 프로세스가 살아 있는지."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)  # 신호 0 = 존재 확인만
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 다른 사용자 소유지만 살아 있다
    return True


class ProcessLock:
    """PID 파일 기반 단일 실행 락. with 문으로 쓴다."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def acquire(self) -> int:
        """락을 잡는다. 이미 살아 있는 프로세스가 잡고 있으면 `AlreadyRunningError`.

        생성은 `O_CREAT | O_EXCL` 로 원자적으로 한다 — 커널이 한쪽만 성공시키므로
        두 프로세스가 동시에 떠도 둘 다 통과하지 않는다.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):  # 죽은 락을 회수한 뒤 한 번만 다시 시도한다
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                existing = self._settled_pid()
                if existing == os.getpid():
                    return os.getpid()  # 내가 이미 잡고 있다
                if existing is not None and _process_alive(existing):
                    raise AlreadyRunningError(
                        f"이미 실행 중입니다 (PID {existing}). 중복 주문을 막기 위해 기동을 중단합니다. "
                        f"정말 죽은 프로세스라면 {self.path} 를 지우세요."
                    )
                logger.info("남아 있던 PID 파일을 회수합니다 (PID %s 는 실행 중이 아님)", existing)
                self.path.unlink(missing_ok=True)
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
                handle.flush()
                os.fsync(handle.fileno())
            logger.info("실행 락 획득: %s (%s)", self.path, os.getpid())
            return os.getpid()

        raise AlreadyRunningError(f"실행 락을 얻지 못했습니다: {self.path}")

    def _settled_pid(self) -> int | None:
        """PID 가 파일에 적힐 때까지 잠깐 기다렸다가 읽는다.

        O_EXCL 로 파일을 만든 쪽이 PID 를 쓰기 전 찰나에 다른 쪽이 읽으면 빈 파일이
        보인다. 그걸 '죽은 락' 으로 오인해 뺏으면 두 프로세스가 동시에 매매하게 된다.
        """
        deadline = time.monotonic() + PID_WRITE_GRACE_SEC
        while True:
            pid = self.read_pid()
            if pid is not None or time.monotonic() >= deadline:
                return pid
            time.sleep(0.02)

    def release(self) -> None:
        """내 PID 가 적힌 경우에만 지운다 (남의 락을 지우지 않는다)."""
        if self.read_pid() == os.getpid():
            self.path.unlink(missing_ok=True)
            logger.info("실행 락 해제")

    def read_pid(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def is_running(self) -> bool:
        pid = self.read_pid()
        return pid is not None and _process_alive(pid)

    def __enter__(self) -> "ProcessLock":
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class StopFlag:
    """긴급 정지 플래그 파일."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def is_set(self) -> bool:
        return self.path.exists()

    def reason(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def set(self, reason: str = "수동 정지") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(KST).isoformat(timespec="seconds")
        self.path.write_text(f"{reason} ({stamp})", encoding="utf-8")
        logger.warning("긴급 정지 플래그 설정: %s", reason)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink(missing_ok=True)
            logger.info("긴급 정지 플래그 해제")


def stop_flag_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / STOP_FILENAME


def pid_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / PID_FILENAME
