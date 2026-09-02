"""곡이 만들어지는 동안 어디까지 왔는지.

원장이 컨셉 카드를 누르면 수십 초에서 몇 분이 지나간다. 그동안 화면이 한 줄짜리
"만드는 중…" 으로 멈춰 있으면, 사람은 **고장 났는지 기다려야 하는지** 알 수 없다.
설치 화면에서 이미 겪은 일이다 — 멈춘 것처럼 보이면 창을 닫게 된다.

작곡 파이프라인은 이미 단계를 보고하고 있었다(`CompositionPipeline.progress`).
여기서는 그 보고를 받아 두었다가 화면이 물어볼 때 내어 준다. 지어내지 않는다 —
표시하는 숫자는 실제로 끝난 프레이즈 수와 실제로 끝난 단계에서 나온다.

여러 곡을 동시에 만들 수 있으므로 작업마다 따로 담고, 오래된 것은 버린다.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# 단계마다 전체에서 차지하는 구간. 겹치지 않고 순서대로 이어진다.
#
# 비율은 골든 20곡의 실제 소요 시간에서 잡았다. 작곡(realize)이 가장 길고,
# 심사가 그다음이다. 정확한 예측이 목적이 아니라 **막대가 뒤로 가지 않고 꾸준히
# 나아가는 것**이 목적이다 — 뒤로 가는 막대는 없느니만 못하다.
STAGE_SPAN: dict[str, tuple[float, float]] = {
    "motif": (0.02, 0.12),
    "plan": (0.12, 0.24),
    "realize": (0.24, 0.62),
    "candidates": (0.24, 0.62),
    "revise": (0.62, 0.70),
    "polish": (0.70, 0.76),
    "targeted": (0.76, 0.82),
    "judge": (0.82, 0.96),
    "save": (0.96, 1.0),
}

STAGE_KO: dict[str, str] = {
    "motif": "모티브 고르기",
    "plan": "설계도 그리기",
    "realize": "마디 쓰기",
    "candidates": "후보곡 만들기",
    "revise": "고쳐 쓰기",
    "polish": "다듬기",
    "targeted": "약한 항목 손보기",
    "judge": "심사받기",
    "save": "저장하기",
}

# 이보다 오래된 작업 기록은 버린다. 화면이 물어보지 않는 기록은 쓸모가 없다.
TTL_SEC = 1800.0
MAX_STEPS = 60


@dataclass
class Job:
    """작업 하나의 진행 상태."""

    stage: str = "motif"
    pct: float = 0.0
    message: str = "준비하는 중"
    started: float = field(default_factory=time.monotonic)
    touched: float = field(default_factory=time.monotonic)
    done: bool = False
    failed: str = ""
    steps: list[dict] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "stage": self.stage,
            "stage_ko": STAGE_KO.get(self.stage, self.stage),
            "pct": round(self.pct, 4),
            "message": self.message,
            "elapsed": round(time.monotonic() - self.started, 1),
            "done": self.done,
            "failed": self.failed,
            "steps": list(self.steps),
        }


class Tracker:
    """작업마다 진행 상태를 담아 둔다. 여러 곡을 동시에 만들 수 있다."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, job_id: str) -> None:
        with self._lock:
            self._prune()
            self._jobs[job_id] = Job()

    def report(self, job_id: str, stage: str, pct: float, message: str) -> None:
        """파이프라인이 부르는 자리. 여기서 막히면 작곡이 막힌다 — 절대 예외를 내지 않는다."""
        lo, hi = STAGE_SPAN.get(stage, (0.0, 1.0))
        overall = lo + (hi - lo) * max(0.0, min(1.0, pct))
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.done:
                return
            # 막대는 뒤로 가지 않는다. 단계가 겹쳐 보고돼도 사람 눈에는 한 방향이어야 한다.
            job.pct = max(job.pct, overall)
            job.stage = stage
            job.message = message
            job.touched = time.monotonic()
            label = STAGE_KO.get(stage, stage)
            if not job.steps or job.steps[-1]["stage"] != stage:
                job.steps.append({"stage": stage, "label": label, "message": message})
            else:
                job.steps[-1]["message"] = message
            del job.steps[:-MAX_STEPS]

    def finish(self, job_id: str, *, failed: str = "") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.done = True
            job.failed = failed
            job.touched = time.monotonic()
            if not failed:
                job.pct = 1.0
                job.stage = "save"
                job.message = "다 됐습니다"

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def _prune(self) -> None:
        now = time.monotonic()
        for key in [k for k, v in self._jobs.items() if now - v.touched > TTL_SEC]:
            del self._jobs[key]


_tracker = Tracker()


def tracker() -> Tracker:
    return _tracker
