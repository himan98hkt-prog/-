"""예약 업로드 대기열.

"이 영상을 내일 저녁 9시에 유튜브+인스타에 올려줘" 를 파일에 적어 두고,
작업실이 켜져 있는 동안 때가 되면 실행한다.

파일에 적는 이유는 두 가지다.
  - 작업실을 껐다 켜도 예약이 남아야 한다 (메모리에 두면 사라진다)
  - 매일 밤 도는 자동 업로드 배치도 같은 대기열을 볼 수 있다

[한계] 컴퓨터가 꺼져 있으면 실행되지 않는다. 예약 시각이 지난 것은
버리지 않고 "밀린 것" 으로 남겨 두었다가 다음에 켜질 때 올린다.
너무 오래 지난 것(기본 24시간)은 그냥 두고 사람이 판단하게 한다.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

QUEUE_NAME = "upload_queue.json"

# 이 시간을 넘겨 밀린 예약은 자동으로 올리지 않는다. 하루 지난 영상을
# 갑자기 올리면 사용자가 의도한 타이밍이 아니다.
STALE_HOURS = 24

_LOCK = threading.Lock()

VALID_TARGETS = ("youtube", "instagram")


@dataclass
class Item:
    run: str
    targets: list[str]
    at: str                       # ISO. 로컬 시각.
    status: str = "waiting"       # waiting | running | done | failed | skipped
    dry_run: bool = False         # 연습. 진짜로 안 올리고 경로만 확인한다.
    # upload_at : 그 시각에 이 컴퓨터가 올린다 (켜져 있어야 함)
    # publish_at: 지금 올리고 유튜브가 그 시각에 공개한다 (꺼져 있어도 됨)
    kind: str = "upload_at"
    error: str = ""
    finished_at: str = ""
    tried: int = 0

    def when(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.at)
        except ValueError:
            return None


@dataclass
class Queue:
    path: Path
    items: list[Item] = field(default_factory=list)

    @classmethod
    def load(cls, runs_dir: Path) -> "Queue":
        path = Path(runs_dir) / QUEUE_NAME
        items: list[Item] = []
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = []
            for r in raw if isinstance(raw, list) else []:
                if not isinstance(r, dict) or not r.get("run"):
                    continue
                targets = [t for t in (r.get("targets") or []) if t in VALID_TARGETS]
                if not targets:
                    continue
                items.append(Item(
                    run=str(r["run"]), targets=targets, at=str(r.get("at", "")),
                    status=str(r.get("status", "waiting")),
                    error=str(r.get("error", "")),
                    finished_at=str(r.get("finished_at", "")),
                    tried=int(r.get("tried", 0) or 0),
                    dry_run=bool(r.get("dry_run", False)),
                    kind=str(r.get("kind", "upload_at")),
                ))
        return cls(path=path, items=items)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=1),
            encoding="utf-8")

    # ── 조작 ─────────────────────────────────────────────────────────
    def add(self, run: str, targets: list[str], at: str,
            dry_run: bool = False, kind: str = "upload_at") -> Item:
        """같은 영상의 기다리는 예약은 덮어쓴다. 두 번 올리지 않기 위해서."""
        clean = [t for t in targets if t in VALID_TARGETS]
        if not clean:
            raise ValueError("올릴 곳을 하나 이상 고르세요.")
        when = datetime.fromisoformat(at)          # 형식이 틀리면 여기서 걸린다
        self.items = [i for i in self.items
                      if not (i.run == run and i.status == "waiting")]
        item = Item(run=run, targets=clean, at=when.isoformat(timespec="minutes"),
                    dry_run=dry_run,
                    kind=kind if kind in ("upload_at", "publish_at") else "upload_at")
        self.items.append(item)
        self.save()
        return item

    def cancel(self, run: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items
                      if not (i.run == run and i.status == "waiting")]
        if len(self.items) == before:
            return False
        self.save()
        return True

    def mark(self, item: Item, status: str, error: str = "") -> None:
        item.status = status
        item.error = error
        if status in ("done", "failed", "skipped"):
            item.finished_at = datetime.now().astimezone().isoformat(
                timespec="minutes")
        self.save()

    # ── 조회 ─────────────────────────────────────────────────────────
    def due(self, now: datetime | None = None) -> Item | None:
        """지금 올려야 할 것 하나. 가장 오래 기다린 것부터."""
        now = now or datetime.now()
        best: Item | None = None
        for i in self.items:
            if i.status != "waiting":
                continue
            when = i.when()
            if when is None:
                continue
            # publish_at 은 지금 올려야 한다. 유튜브가 그 시각에 공개한다.
            if i.kind != "publish_at" and when > now:
                continue
            if i.kind != "publish_at" and now - when > timedelta(hours=STALE_HOURS):
                continue                     # 너무 밀린 것은 사람이 판단한다
            if best is None or (i.when() or now) < (best.when() or now):
                best = i
        return best

    def stale(self, now: datetime | None = None) -> list[Item]:
        """너무 오래 밀려서 자동으로 안 올리는 것들. 화면에 알려줘야 한다."""
        now = now or datetime.now()
        out = []
        for i in self.items:
            when = i.when()
            if i.status == "waiting" and when and now - when > timedelta(
                    hours=STALE_HOURS):
                out.append(i)
        return out

    def waiting(self) -> list[Item]:
        return sorted((i for i in self.items if i.status == "waiting"),
                      key=lambda i: i.at)

    def snapshot(self) -> list[dict]:
        return [asdict(i) for i in sorted(self.items, key=lambda i: i.at,
                                          reverse=True)][:40]


def with_lock(fn):
    """대기열 파일은 UI 스레드와 작업 스레드가 같이 만진다."""
    def wrapped(*a, **kw):
        with _LOCK:
            return fn(*a, **kw)
    return wrapped
