"""마이그레이션 실행기.

Alembic 을 쓰지 않는다. 필요한 건 "적용 안 된 .sql 을 순서대로 한 번씩" 뿐이고,
그 정도는 60 줄이면 된다. 대신 두 가지를 확실히 한다.

- **파일 잠금 없이 동시 실행해도 안전하다.** ``pg_advisory_lock`` 으로 한 프로세스만
  적용한다. worker 여러 개가 동시에 뜨는 게 정상 운영이기 때문이다.
- **이미 적용된 파일이 바뀌면 거부한다.** 체크섬을 저장한다. 운영 중인 스키마를
  소리 없이 갈아끼우는 사고를 막는다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from autoshorts.utils import get_logger

from .db import Database, DatabaseError

__all__ = ["Migration", "discover", "apply_all", "applied_versions", "MIGRATIONS_DIR"]

LOG = get_logger("saas.migrate")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# 임의의 고정 상수. 이 앱의 마이그레이션 전용 advisory lock 키.
_LOCK_KEY = 0x4155_5453

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    checksum    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover(directory: str | Path | None = None) -> list[Migration]:
    """``NNNN_name.sql`` 파일을 버전 순으로 읽는다."""
    root = Path(directory) if directory else MIGRATIONS_DIR
    if not root.is_dir():
        return []
    migrations: list[Migration] = []
    for path in sorted(root.glob("*.sql")):
        version = path.stem.split("_", 1)[0]
        if not version.isdigit():
            raise DatabaseError(f"마이그레이션 파일 이름이 잘못됐습니다: {path.name}")
        migrations.append(
            Migration(version=version, path=path, sql=path.read_text(encoding="utf-8"))
        )
    versions = [m.version for m in migrations]
    if len(set(versions)) != len(versions):
        raise DatabaseError(f"마이그레이션 버전이 중복됩니다: {versions}")
    return migrations


def applied_versions(db: Database) -> dict[str, str]:
    """적용된 버전 → 체크섬."""
    with db.transaction() as cur:
        cur.execute(_BOOTSTRAP)
        cur.execute("SELECT version, checksum FROM schema_migrations")
        return {row[0]: row[1] for row in cur.fetchall()}


def apply_all(db: Database, directory: str | Path | None = None) -> list[str]:
    """적용되지 않은 마이그레이션을 순서대로 실행하고, 적용한 버전 목록을 돌려준다."""
    migrations = discover(directory)
    applied: list[str] = []

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_BOOTSTRAP)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version, checksum FROM schema_migrations")
                known = {row[0]: row[1] for row in cur.fetchall()}

            for migration in migrations:
                existing = known.get(migration.version)
                if existing is not None:
                    if existing != migration.checksum:
                        raise DatabaseError(
                            f"이미 적용된 마이그레이션 {migration.version} 의 내용이 "
                            "바뀌었습니다. 기존 파일을 고치지 말고 새 파일을 추가하세요."
                        )
                    continue
                LOG.info("마이그레이션 적용: %s", migration.path.name)
                with conn.cursor() as cur:
                    cur.execute(migration.sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (migration.version, migration.checksum),
                    )
                conn.commit()
                applied.append(migration.version)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
            conn.commit()

    return applied


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI 진입점
    import argparse

    parser = argparse.ArgumentParser(description="AutoShorts SaaS 스키마 마이그레이션")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN (기본: 환경변수)")
    parser.add_argument("--status", action="store_true", help="적용 상태만 출력")
    args = parser.parse_args(argv)

    db = Database(args.dsn)
    try:
        if args.status:
            known = applied_versions(db)
            for migration in discover():
                mark = "적용됨" if migration.version in known else "미적용"
                print(f"  {migration.version}  {migration.path.name:<28} {mark}")
            return 0
        applied = apply_all(db)
        print("적용한 마이그레이션:", ", ".join(applied) if applied else "없음 (최신)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
