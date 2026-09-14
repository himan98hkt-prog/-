"""단일 실행 락과 긴급 정지 플래그 테스트."""

from __future__ import annotations

import os

import pytest

from utils.runtime import AlreadyRunningError, ProcessLock, StopFlag


@pytest.fixture
def lock_path(tmp_path):
    return tmp_path / "trader.pid"


def test_lock_writes_own_pid(lock_path):
    lock = ProcessLock(lock_path)
    assert lock.acquire() == os.getpid()
    assert lock.read_pid() == os.getpid()
    assert lock.is_running()


def test_second_process_is_blocked(lock_path):
    """살아 있는 다른 프로세스의 락은 뺏지 않는다 — 이중 주문 방지의 핵심."""
    lock_path.write_text("1")  # PID 1 은 항상 존재
    with pytest.raises(AlreadyRunningError, match="이미 실행 중"):
        ProcessLock(lock_path).acquire()


def test_stale_lock_is_reclaimed(lock_path):
    lock_path.write_text("999999")  # 존재하지 않는 PID
    assert ProcessLock(lock_path).acquire() == os.getpid()


def test_corrupt_lock_file_is_reclaimed(lock_path):
    lock_path.write_text("이건 숫자가 아님")
    assert ProcessLock(lock_path).acquire() == os.getpid()


def test_release_only_removes_own_lock(lock_path):
    lock = ProcessLock(lock_path)
    lock.acquire()
    lock_path.write_text("1")  # 그 사이 다른 프로세스가 잡은 상황
    lock.release()
    assert lock_path.exists(), "남의 락을 지우면 안 됩니다"


def test_context_manager_releases(lock_path):
    with ProcessLock(lock_path):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_reacquire_by_same_process_is_allowed(lock_path):
    lock = ProcessLock(lock_path)
    lock.acquire()
    assert lock.acquire() == os.getpid()


# --------------------------------------------------------------------------- #
# 긴급 정지
# --------------------------------------------------------------------------- #


def test_stop_flag_lifecycle(tmp_path):
    flag = StopFlag(tmp_path / "STOP")
    assert flag.is_set() is False

    flag.set("손실 급증")
    assert flag.is_set() is True
    assert "손실 급증" in flag.reason()

    flag.clear()
    assert flag.is_set() is False


def test_stop_flag_clear_is_idempotent(tmp_path):
    flag = StopFlag(tmp_path / "STOP")
    flag.clear()
    flag.clear()
    assert flag.is_set() is False


def test_stop_flag_can_be_created_by_hand(tmp_path):
    """`touch data/STOP` 만으로도 멈출 수 있어야 한다."""
    path = tmp_path / "STOP"
    path.touch()
    assert StopFlag(path).is_set() is True


# --------------------------------------------------------------------------- #
# 원자적 락 (동시 기동 방지)
# --------------------------------------------------------------------------- #


def test_concurrent_acquire_lets_only_one_through(lock_path, monkeypatch):
    """동시에 뜬 두 프로세스가 모두 락을 잡으면 이중 주문이 난다."""
    import threading

    from utils import runtime

    # 각 스레드를 서로 다른 '프로세스'처럼 보이게 하고, 모두 살아 있다고 본다.
    # getpid 는 acquire 안에서 여러 번 불리므로 스레드별로 같은 값을 돌려줘야 한다.
    assigned: dict[int, int] = {}
    lock_guard = threading.Lock()

    def fake_getpid() -> int:
        with lock_guard:
            return assigned.setdefault(threading.get_ident(), 4000 + len(assigned) + 1)

    monkeypatch.setattr(runtime.os, "getpid", fake_getpid)
    monkeypatch.setattr(runtime, "_process_alive", lambda pid: True)

    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        barrier.wait()
        try:
            ProcessLock(lock_path).acquire()
            results.append("acquired")
        except AlreadyRunningError:
            results.append("blocked")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(3)

    assert sorted(results) == ["acquired", "blocked"], f"정확히 하나만 통과해야 합니다 ({results})"


def test_lock_file_is_owner_only(lock_path):
    ProcessLock(lock_path).acquire()
    assert oct(lock_path.stat().st_mode)[-3:] == "600"
