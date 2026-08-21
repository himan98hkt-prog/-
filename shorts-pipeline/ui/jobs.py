"""백그라운드 작업 관리.

영상 생성은 5~10분이 걸린다. 브라우저를 붙잡아 둘 수 없으므로 별도 스레드에서
돌리고, 진행 상황을 메모리에 쌓아 화면이 주기적으로 읽어가게 한다.
"""

from __future__ import annotations

import itertools
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_counter = itertools.count(1)
_lock = threading.Lock()
_jobs: dict[str, "Job"] = {}

# "[3/6] 클립 생성 완료" 같은 줄에서 진행률을 뽑는다
_PROGRESS = re.compile(r"\[(\d+)/(\d+)\]")


@dataclass
class Job:
    id: str
    kind: str                      # generate | publish
    label: str
    status: str = "running"        # running | done | failed | cancelled
    lines: list[str] = field(default_factory=list)
    step: int = 0
    total: int = 0
    started: float = field(default_factory=time.time)
    finished: float | None = None
    result: dict = field(default_factory=dict)
    _proc: subprocess.Popen | None = None

    @property
    def elapsed(self) -> int:
        return int((self.finished or time.time()) - self.started)

    def snapshot(self, tail: int = 40) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "step": self.step,
            "total": self.total,
            "elapsed": self.elapsed,
            "lines": self.lines[-tail:],
            "result": self.result,
        }


def get(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def recent(limit: int = 8) -> list[dict]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j.started)[:limit]
    return [j.snapshot(tail=3) for j in jobs]


def active() -> Job | None:
    with _lock:
        for j in sorted(_jobs.values(), key=lambda j: -j.started):
            if j.status == "running":
                return j
    return None


def cancel(job_id: str) -> bool:
    job = get(job_id)
    if job is None or job.status != "running" or job._proc is None:
        return False
    job._proc.terminate()
    job.status = "cancelled"
    job.finished = time.time()
    job.lines.append("사용자가 중단했습니다.")
    return True


def start(kind: str, label: str, args: list[str], cwd: Path,
          on_done=None) -> Job:
    """main.py 를 자식 프로세스로 돌리고 출력을 실시간으로 모은다."""
    job = Job(id=f"{kind}-{next(_counter)}", kind=kind, label=label)
    with _lock:
        _jobs[job.id] = job

    def run() -> None:
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", *args],
                cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            job._proc = proc
            for raw in proc.stdout:
                line = raw.rstrip()
                if not line:
                    continue
                job.lines.append(line)
                m = _PROGRESS.search(line)
                if m:
                    job.step, job.total = int(m.group(1)), int(m.group(2))
            code = proc.wait()
            if job.status == "cancelled":
                return
            job.status = "done" if code == 0 else "failed"
        except Exception as exc:                      # 스레드가 조용히 죽지 않게
            job.status = "failed"
            job.lines.append(f"실행 오류: {exc}")
        finally:
            if job.finished is None:
                job.finished = time.time()
            if on_done:
                try:
                    on_done(job)
                except Exception as exc:
                    job.lines.append(f"후처리 오류: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return job
