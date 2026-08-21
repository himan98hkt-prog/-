"""실행 폴더 관리 · log.jsonl · resume 을 위한 상태 저장."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def new_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


@dataclass
class Run:
    """runs/{run_id}/ 하위 산출물의 단일 접근점."""

    root: Path
    run_id: str
    state: dict[str, Any] = field(default_factory=dict)

    # ── 경로 ──────────────────────────────────────────────────────────
    @property
    def clips_dir(self) -> Path:
        return self.root / "clips"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def input_image(self) -> Path:
        return self.root / "input.png"

    @property
    def final(self) -> Path:
        return self.root / "final.mp4"

    @property
    def log_path(self) -> Path:
        return self.root / "log.jsonl"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def clip(self, n: int) -> Path:
        return self.clips_dir / f"clip_{n:02d}.mp4"

    def frame(self, n: int, upscaled: bool = False) -> Path:
        suffix = "_upscaled" if upscaled else ""
        return self.frames_dir / f"last_{n:02d}{suffix}.png"

    def seed(self, n: int) -> Path:
        """montage 모드에서 장면 n 의 시작 이미지."""
        return self.frames_dir / f"seed_{n:02d}.png"

    # ── 생성 / 로드 ────────────────────────────────────────────────────
    @classmethod
    def create(cls, runs_dir: Path, run_id: str | None = None) -> "Run":
        run_id = run_id or new_run_id()
        root = Path(runs_dir) / run_id
        root.mkdir(parents=True, exist_ok=True)
        run = cls(root=root, run_id=run_id)
        run.clips_dir.mkdir(exist_ok=True)
        run.frames_dir.mkdir(exist_ok=True)
        return run

    @classmethod
    def load(cls, runs_dir: Path, run_id: str) -> "Run":
        root = Path(runs_dir) / run_id
        if not root.is_dir():
            available = sorted(p.name for p in Path(runs_dir).glob("*") if p.is_dir())
            raise FileNotFoundError(
                f"실행 폴더가 없습니다: {root}\n"
                + ("사용 가능한 run: " + ", ".join(available[-10:]) if available
                   else "runs/ 가 비어 있습니다.")
            )
        run = cls(root=root, run_id=run_id)
        run.clips_dir.mkdir(exist_ok=True)
        run.frames_dir.mkdir(exist_ok=True)
        if run.state_path.exists():
            run.state = json.loads(run.state_path.read_text(encoding="utf-8"))
        return run

    # ── 기록 ──────────────────────────────────────────────────────────
    def log(self, event: str, **payload: Any) -> None:
        """API 요청·응답 원본을 포함해 모든 사건을 append 한다."""
        record = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "event": event, **payload}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def save_state(self, **updates: Any) -> None:
        self.state.update(updates)
        self.state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def completed_clips(self) -> list[int]:
        """이미 만들어진 클립 번호. resume 의 근거."""
        found = []
        for p in sorted(self.clips_dir.glob("clip_*.mp4")):
            if p.stat().st_size > 0:
                try:
                    found.append(int(p.stem.split("_")[1]))
                except (IndexError, ValueError):
                    continue
        return found
