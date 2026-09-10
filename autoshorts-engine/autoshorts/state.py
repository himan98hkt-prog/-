"""실행 이력 저장소.

예약 실행을 반복하면 같은 원본을 다시 처리하거나 같은 영상을 두 번 올리기
쉽다. 처리한 원본과 업로드 결과를 남겨 중복을 막고, 하루 업로드 할당량을
넘지 않도록 카운트를 관리한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .utils import get_logger

__all__ = ["HistoryStore", "default_history_path", "HistoryEntry"]

LOG = get_logger("state")

# 이력이 무한정 늘지 않도록 이 기간이 지난 항목은 정리한다.
RETENTION_DAYS = 180


def default_history_path() -> Path:
    override = os.environ.get("AUTOSHORTS_HISTORY_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".autoshorts" / "history.json"


@dataclass
class HistoryEntry:
    """원본 하나에 대한 처리 기록."""

    source_id: str
    source_url: str = ""
    title: str = ""
    processed_at: str = ""
    clip_count: int = 0
    uploads: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.uploads is None:
            self.uploads = []
        if not self.processed_at:
            self.processed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_url": self.source_url,
            "title": self.title,
            "processed_at": self.processed_at,
            "clip_count": self.clip_count,
            "uploads": self.uploads,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        return cls(
            source_id=data.get("source_id", ""),
            source_url=data.get("source_url", ""),
            title=data.get("title", ""),
            processed_at=data.get("processed_at", ""),
            clip_count=int(data.get("clip_count", 0) or 0),
            uploads=list(data.get("uploads") or []),
        )


class HistoryStore:
    """JSON 한 파일로 유지하는 가벼운 이력 저장소."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or default_history_path()).expanduser()
        self._data: dict[str, Any] = {"version": 1, "entries": []}
        self._load()

    # ── 입출력 ────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # 이력이 깨져도 실행 자체를 막지는 않는다.
            LOG.warning("이력 파일을 읽지 못해 새로 시작합니다(%s): %s", exc, self.path)
            return
        if isinstance(loaded, dict) and isinstance(loaded.get("entries"), list):
            self._data = loaded

    def save(self) -> Path:
        self.prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self.path

    # ── 조회 ──────────────────────────────────────────────────
    @property
    def entries(self) -> list[HistoryEntry]:
        return [HistoryEntry.from_dict(item) for item in self._data.get("entries", [])]

    def is_processed(self, source_id: str) -> bool:
        if not source_id:
            return False
        return any(item.get("source_id") == source_id for item in self._data.get("entries", []))

    def filter_unprocessed(self, source_ids: Iterable[str]) -> list[str]:
        done = {item.get("source_id") for item in self._data.get("entries", [])}
        return [sid for sid in source_ids if sid and sid not in done]

    def uploads_on(self, day: date | None = None) -> int:
        """해당 날짜(UTC)에 업로드한 건수."""
        target = (day or datetime.now(timezone.utc).date()).isoformat()
        count = 0
        for entry in self._data.get("entries", []):
            for upload in entry.get("uploads") or []:
                stamp = str(upload.get("uploaded_at", ""))
                if stamp.startswith(target):
                    count += 1
        return count

    def remaining_uploads_today(self, daily_limit: int) -> int:
        return max(0, daily_limit - self.uploads_on())

    # ── 기록 ──────────────────────────────────────────────────
    def record(
        self,
        source_id: str,
        *,
        source_url: str = "",
        title: str = "",
        clip_count: int = 0,
        uploads: Iterable[dict[str, Any]] = (),
    ) -> HistoryEntry:
        """처리 결과를 남긴다. 같은 원본이면 기존 항목에 합친다."""
        stamped = []
        now = datetime.now(timezone.utc).isoformat()
        for upload in uploads:
            item = dict(upload)
            item.setdefault("uploaded_at", now)
            stamped.append(item)

        for raw in self._data.setdefault("entries", []):
            if raw.get("source_id") == source_id:
                raw["clip_count"] = max(int(raw.get("clip_count", 0) or 0), clip_count)
                raw.setdefault("uploads", []).extend(stamped)
                raw["processed_at"] = now
                return HistoryEntry.from_dict(raw)

        entry = HistoryEntry(
            source_id=source_id, source_url=source_url, title=title,
            clip_count=clip_count, uploads=stamped,
        )
        self._data["entries"].append(entry.to_dict())
        return entry

    def prune(self, retention_days: int = RETENTION_DAYS) -> int:
        """오래된 항목을 정리하고 삭제 건수를 돌려준다."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        kept: list[dict[str, Any]] = []
        removed = 0
        for raw in self._data.get("entries", []):
            try:
                stamp = datetime.fromisoformat(str(raw.get("processed_at", "")))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
            except ValueError:
                kept.append(raw)          # 날짜를 못 읽으면 보존한다
                continue
            if stamp < cutoff:
                removed += 1
            else:
                kept.append(raw)
        self._data["entries"] = kept
        return removed
