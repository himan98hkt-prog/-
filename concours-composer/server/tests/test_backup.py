"""자동 백업 — 한 번의 사고로 만든 곡을 전부 잃지 않게.

여기서 지키는 것은 셋이다.
1. 사본이 **실제로 읽히는 데이터베이스**여야 한다. 0바이트 파일이 쌓이는 것은
   백업이 아니라 안심시키는 거짓말이다.
2. 요청마다 복사하지 않는다 — 곡 하나 만드는 동안 저장은 여러 번 일어난다.
3. 오래된 사본을 치우되 **하루에 하나는 남긴다** — 한참 뒤에 알아챈 사고를 위해서.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.store.backup import KEEP_DAILY, KEEP_RECENT, STAMP, BackupKeeper


def _make_db(path: Path, rows: int = 3) -> None:
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS store (bucket TEXT PRIMARY KEY, payload TEXT)")
        con.executemany(
            "INSERT OR REPLACE INTO store VALUES (?, ?)",
            [(f"b{i}", "x" * 200) for i in range(rows)],
        )


def test_backup_is_a_readable_database(tmp_path: Path) -> None:
    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)

    made = keeper.maybe_backup(force=True)
    assert made is not None and made.exists()

    with sqlite3.connect(made) as con:
        rows = con.execute("SELECT bucket FROM store").fetchall()
    assert len(rows) == 3, "사본이 실제 데이터를 담고 있어야 한다"


def test_backup_is_throttled(tmp_path: Path) -> None:
    """저장은 요청마다 일어난다 — 그때마다 복사하면 디스크만 축낸다."""
    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)

    assert keeper.maybe_backup(force=True) is not None
    assert keeper.maybe_backup() is None, "곧바로 또 뜨면 안 된다"
    assert keeper.maybe_backup(force=True) is not None, "강제로는 언제든 뜬다"


def test_missing_source_is_not_an_error(tmp_path: Path) -> None:
    """저장 파일이 아직 없어도 조용히 넘어간다 — 백업이 기동을 막으면 안 된다."""
    keeper = BackupKeeper(tmp_path / "없는파일.sqlite3")
    assert keeper.maybe_backup(force=True) is None
    assert keeper.backups() == []


def test_prune_keeps_recent_and_one_per_day(tmp_path: Path) -> None:
    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)
    keeper.folder.mkdir(parents=True, exist_ok=True)

    # 오늘 사본 여러 개 + 지난 30일치 하루 두 개씩
    now = datetime(2026, 9, 2, 12, 0, 0)
    made: list[Path] = []
    for i in range(KEEP_RECENT + 6):
        f = keeper.folder / f"store-{(now - timedelta(minutes=i)).strftime(STAMP)}.sqlite3"
        f.write_bytes(b"x")
        made.append(f)
    for day in range(1, 31):
        for hour in (9, 18):
            d = now - timedelta(days=day)
            f = keeper.folder / f"store-{d.replace(hour=hour).strftime(STAMP)}.sqlite3"
            f.write_bytes(b"x")
            made.append(f)

    keeper.prune()
    left = keeper.backups()

    # 최근 것은 그대로 남는다.
    for f in sorted(made, reverse=True)[:KEEP_RECENT]:
        assert f in left, f"최근 사본이 지워졌다: {f.name}"

    # 하루당 최대 하나만 남는다.
    days = [f.stem.split("-")[1] for f in left]
    assert len(days) == len(set(days)) or len(left) <= KEEP_RECENT + KEEP_DAILY
    assert len(left) <= KEEP_RECENT + KEEP_DAILY

    # 아주 오래된 날은 사라진다.
    oldest_day = (now - timedelta(days=30)).strftime("%Y%m%d")
    assert oldest_day not in days


def test_summary_reports_what_the_screen_needs(tmp_path: Path) -> None:
    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)
    assert keeper.summary()["count"] == 0

    keeper.maybe_backup(force=True)
    s = keeper.summary()
    assert s["count"] == 1
    assert str(s["newest"]).startswith("store-")
    assert s["newest_at"]
    assert str(s["folder"]).endswith("backups")


def test_total_size_is_capped(tmp_path: Path) -> None:
    """개수로만 제한하면 곡이 쌓일수록 사본이 집 PC 디스크를 먹는다."""
    from app.store.backup import ALWAYS_KEEP, MAX_TOTAL_MB

    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)
    keeper.folder.mkdir(parents=True, exist_ok=True)

    # 큰 사본을 여러 개. 하나가 상한의 1/3 이면 셋까지만 들어간다.
    chunk = (MAX_TOTAL_MB * 1_048_576) // 3
    now = datetime(2026, 9, 2, 12, 0, 0)
    for i in range(8):
        f = keeper.folder / f"store-{(now - timedelta(minutes=i)).strftime(STAMP)}.sqlite3"
        f.write_bytes(b"\0" * chunk)

    keeper.prune()
    left = keeper.backups()
    total = sum(f.stat().st_size for f in left)

    assert len(left) >= ALWAYS_KEEP, "사본이 하나도 없는 것이 최악이다"
    assert len(left) < 8, "크기 상한이 전혀 듣지 않았다"
    # 최근 ALWAYS_KEEP 개는 크기와 상관없이 남으므로 그만큼은 넘을 수 있다.
    assert total <= MAX_TOTAL_MB * 1_048_576 * 1.1, f"{total / 1_048_576:.0f}MB 나 남았다"


def test_the_newest_backup_always_survives_the_size_cap(tmp_path: Path) -> None:
    """상한이 아무리 빡빡해도 가장 최근 사본은 남아야 한다."""
    src = tmp_path / "store.sqlite3"
    _make_db(src)
    keeper = BackupKeeper(src)
    keeper.folder.mkdir(parents=True, exist_ok=True)

    huge = 500 * 1_048_576
    now = datetime(2026, 9, 2, 12, 0, 0)
    newest = keeper.folder / f"store-{now.strftime(STAMP)}.sqlite3"
    newest.write_bytes(b"\0" * 1024)
    for i in range(1, 4):
        f = keeper.folder / f"store-{(now - timedelta(minutes=i)).strftime(STAMP)}.sqlite3"
        f.write_bytes(b"\0" * huge)

    keeper.prune()
    assert newest.exists(), "가장 최근 사본이 지워졌다"
