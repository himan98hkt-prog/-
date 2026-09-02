"""저장소 자동 백업 — 만든 곡을 한 번의 사고로 잃지 않게.

만든 곡·심사 결과·권리 정보·제목이 전부 `data/store.sqlite3` **파일 하나**에 들어
있다. 그 파일이 지워지거나 깨지면 그동안의 작업이 통째로 사라진다. 학원 PC 는
껐다 켜고, 옮기고, 정리하다 지우는 기계다.

그래서 저장이 일어날 때마다 사본을 남긴다. 다만 요청마다 복사하면 디스크만 축내므로
**시간 간격**과 **내용이 바뀌었는가**를 함께 본다.

보관 방식은 두 갈래다.
- 최근 것 몇 개 — 방금 한 실수를 되돌리기 위한 것.
- 하루에 하나씩 며칠치 — 한참 뒤에야 알아챈 사고를 위한 것.

되돌리는 것은 프로그램이 하지 않는다. 잘못 되돌리면 지금 것까지 잃기 때문이다.
어느 파일을 어떻게 되돌리는지는 화면에서 글로 알려 준다.
"""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# 이보다 자주는 복사하지 않는다. 곡 하나 만드는 동안 요청은 여러 번 오간다.
MIN_INTERVAL_SEC = 300.0
KEEP_RECENT = 12       # 최근 사본
KEEP_DAILY = 14        # 하루치 사본
STAMP = "%Y%m%d-%H%M%S"


class BackupKeeper:
    """저장 파일의 사본을 뜨고, 오래된 것을 치운다."""

    def __init__(self, source: Path, folder: Path | None = None) -> None:
        self.source = source
        self.folder = folder or source.parent / "backups"
        self._last_run = 0.0
        self._last_size = -1

    def maybe_backup(self, *, force: bool = False) -> Path | None:
        """조건이 맞으면 사본을 뜬다. 뜨지 않았으면 None.

        백업이 실패해도 예외를 올리지 않는다 — 사본을 못 떴다고 저장 자체를
        막으면 본말이 뒤집힌다.
        """
        if not self.source.exists():
            return None
        now = time.monotonic()
        try:
            size = self.source.stat().st_size
        except OSError:
            return None
        if not force:
            if now - self._last_run < MIN_INTERVAL_SEC:
                return None
            if size == self._last_size:
                return None      # 내용이 안 늘었으면 같은 것을 또 뜨지 않는다
        self._last_run = now
        self._last_size = size

        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            target = self.folder / f"store-{datetime.now().strftime(STAMP)}.sqlite3"
            # WAL 이 켜져 있어도 sqlite 의 백업 API 는 일관된 사본을 준다.
            self._copy(target)
        except (OSError, shutil.Error) as e:
            log.warning("백업을 뜨지 못했다: %s", e)
            return None
        self.prune()
        return target

    def _copy(self, target: Path) -> None:
        import sqlite3

        with sqlite3.connect(self.source) as src, sqlite3.connect(target) as dst:
            src.backup(dst)

    def backups(self) -> list[Path]:
        if not self.folder.exists():
            return []
        return sorted(self.folder.glob("store-*.sqlite3"), reverse=True)

    def prune(self) -> None:
        """최근 것 몇 개 + 하루에 하나씩만 남기고 지운다."""
        files = self.backups()
        keep: set[Path] = set(files[:KEEP_RECENT])

        seen_days: dict[str, Path] = {}
        for f in files:                       # 최신순 — 그날의 마지막 사본이 남는다
            day = f.stem.split("-")[1] if "-" in f.stem else ""
            if day and day not in seen_days:
                seen_days[day] = f
        for day in sorted(seen_days, reverse=True)[:KEEP_DAILY]:
            keep.add(seen_days[day])

        for f in files:
            if f not in keep:
                try:
                    f.unlink()
                except OSError:                # 지우지 못해도 그냥 둔다
                    log.debug("오래된 백업을 지우지 못했다: %s", f)

    def summary(self) -> dict[str, object]:
        """화면에 보여 줄 상태."""
        files = self.backups()
        newest = files[0] if files else None
        return {
            "folder": str(self.folder),
            "count": len(files),
            "newest": newest.name if newest else "",
            "newest_at": (
                datetime.fromtimestamp(newest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                if newest
                else ""
            ),
            "total_mb": round(sum(f.stat().st_size for f in files) / 1_048_576, 1),
        }
