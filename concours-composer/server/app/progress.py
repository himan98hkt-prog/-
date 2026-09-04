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
    # "후보곡 만들기" 라고 적어 두었더니, 곡 하나를 만드는 중에도 여러 곡을
    # 만드는 것처럼 보였다. 몇 가지 안을 만드는지는 메시지 쪽에서 말한다.
    "candidates": "곡 쓰기",
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
    """작업 하나의 진행 상태.

    한 번에 여러 곡을 만들 수도 있다(급수별 한 벌). 그때 막대가 곡마다 처음으로
    돌아가면 사람은 얼마나 남았는지 알 수 없다 — 그래서 **몇 곡 중 몇 번째**를
    함께 담고, 전체 막대는 그것까지 셈해서 낸다.
    """

    stage: str = "motif"
    pct: float = 0.0
    message: str = "준비하는 중"
    started: float = field(default_factory=time.monotonic)
    touched: float = field(default_factory=time.monotonic)
    done: bool = False
    failed: str = ""
    steps: list[dict] = field(default_factory=list)
    # 여러 곡을 만들 때만 쓴다. 한 곡이면 total=1, index=0 이다.
    total: int = 1
    index: int = 0
    label: str = ""

    def remaining(self) -> float:
        """앞으로 몇 초 더 걸릴지. **재지 않은 것은 말하지 않는다.**

        성격마다 "토카타는 몇 분" 하는 표를 만들어 두는 방법도 있지만, 그 표는
        내가 재 본 적 없는 숫자다. 게다가 실제 시간은 성격만으로 정해지지 않는다 —
        등급(모델), 급수, 곡 길이, 그날 서버 혼잡도가 다 얽힌다. 지어낸 표는
        원장님을 또 한 번 속이는 일이다.

        그래서 **지금 이 곡이 실제로 간 속도**로 잰다. 5%를 가는 데 1분 걸렸으면
        남은 95%는 대략 19분이다. 곡이 진행될수록 저절로 정확해진다.

        진행이 너무 이르면(3% 미만) 아직 잴 것이 없다 — 0 을 돌려주고 화면은
        아무 말도 하지 않는다. 모르면 모른다고 하는 것이 틀린 숫자보다 낫다.
        """
        if self.done or self.pct < 0.03:
            return 0.0
        spent = time.monotonic() - self.started
        return max(0.0, spent * (1.0 - self.pct) / self.pct)

    def snapshot(self) -> dict:
        return {
            "stage": self.stage,
            "stage_ko": STAGE_KO.get(self.stage, self.stage),
            "pct": round(self.pct, 4),
            "message": self.message,
            "elapsed": round(time.monotonic() - self.started, 1),
            # 0 이면 "아직 모른다" 는 뜻이다. 화면은 그때 남은 시간을 감춘다.
            "remaining": round(self.remaining(), 1),
            "done": self.done,
            "failed": self.failed,
            "steps": list(self.steps),
            "total": self.total,
            "index": self.index,
            "label": self.label,
        }


class Tracker:
    """작업마다 진행 상태를 담아 둔다. 여러 곡을 동시에 만들 수 있다."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, job_id: str, *, total: int = 1) -> None:
        with self._lock:
            self._prune()
            self._jobs[job_id] = Job(total=max(1, total))

    def begin_piece(self, job_id: str, index: int, label: str) -> None:
        """여러 곡 중 다음 곡으로 넘어간다. 막대는 그만큼에서 다시 오른다."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.done:
                return
            job.index = index
            job.label = label
            job.steps.clear()   # 앞 곡의 발자국이 남아 있으면 헷갈린다
            job.touched = time.monotonic()

    def report(self, job_id: str, stage: str, pct: float, message: str) -> None:
        """파이프라인이 부르는 자리. 여기서 막히면 작곡이 막힌다 — 절대 예외를 내지 않는다."""
        lo, hi = STAGE_SPAN.get(stage, (0.0, 1.0))
        within = lo + (hi - lo) * max(0.0, min(1.0, pct))
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.done:
                return
            # 여러 곡이면 이 곡의 진행을 전체 안에서의 자리로 옮긴다.
            overall = (job.index + within) / job.total
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
                job.index = job.total
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
