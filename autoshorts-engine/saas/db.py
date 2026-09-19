"""PostgreSQL 연결 계층.

ORM 을 쓰지 않는다. 스키마가 12개 남짓이고, 이 계층에서 가장 중요한 성질이
**workspace 격리**인데 그건 ORM 이 숨겨주면 오히려 위험하기 때문이다. 모든 조회는
``WHERE workspace_id = %s`` 를 눈으로 확인할 수 있게 SQL 로 남긴다.

연결은 작은 LIFO 풀로 관리한다. psycopg_pool 을 쓰지 않는 이유는 의존성 하나를
줄이기 위해서다. 필요한 기능이 "빌려주고 돌려받기"뿐이다.
"""

from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from autoshorts.utils import get_logger

__all__ = [
    "Database",
    "DatabaseError",
    "dsn_from_env",
    "connect",
]

LOG = get_logger("saas.db")

DEFAULT_DSN = "postgresql://postgres@127.0.0.1:5432/autoshorts"


class DatabaseError(RuntimeError):
    """연결·질의 실패."""


def dsn_from_env(env: dict[str, str] | None = None) -> str:
    """DSN 을 환경변수에서 읽는다.

    비밀번호가 포함될 수 있으므로 **로그에 찍지 않는다.** 호출부에서도 DSN 을
    그대로 출력하지 말 것.
    """
    source = os.environ if env is None else env
    return source.get("AUTOSHORTS_DATABASE_URL") or source.get("DATABASE_URL") or DEFAULT_DSN


def _import_psycopg():
    try:
        import psycopg  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 설치 안내 경로
        raise DatabaseError(
            "PostgreSQL 드라이버가 없습니다. `pip install 'autoshorts[saas]'` 또는 "
            "`pip install 'psycopg[binary]'` 로 설치하세요."
        ) from exc
    return psycopg


def connect(dsn: str | None = None):
    """단발 연결. 풀을 쓰지 않는 스크립트(마이그레이션 등)용."""
    psycopg = _import_psycopg()
    try:
        return psycopg.connect(dsn or dsn_from_env(), autocommit=False)
    except Exception as exc:
        raise DatabaseError(f"데이터베이스에 연결하지 못했습니다: {type(exc).__name__}") from exc


class Database:
    """연결 풀 + 트랜잭션 헬퍼."""

    def __init__(self, dsn: str | None = None, *, max_connections: int = 8) -> None:
        self.dsn = dsn or dsn_from_env()
        self._idle: queue.LifoQueue = queue.LifoQueue()
        self._max = max(1, int(max_connections))
        self._opened = 0
        self._lock = threading.Lock()
        self._closed = False

    # ── 풀 ─────────────────────────────────────────────────
    def _acquire(self):
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                with self._lock:
                    if self._opened < self._max:
                        self._opened += 1
                        break
                # 풀이 꽉 찼다 — 반납을 기다린다.
                conn = self._idle.get(timeout=30)
            if conn.closed:
                # 죽은 연결은 버리고 새로 연다.
                with self._lock:
                    self._opened -= 1
                continue
            return conn
        try:
            return connect(self.dsn)
        except Exception:
            with self._lock:
                self._opened -= 1
            raise

    def _release(self, conn) -> None:
        if self._closed or conn.closed:
            with self._lock:
                self._opened -= 1
            return
        self._idle.put(conn)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self._acquire()
        try:
            yield conn
        finally:
            self._release(conn)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """커서를 주고, 예외가 없으면 커밋한다.

        중첩 호출을 지원하지 않는다. 한 요청 = 한 트랜잭션이 이 계층의 규칙이다.
        """
        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:  # pragma: no cover - 이미 끊긴 연결
                pass
            raise
        finally:
            self._release(conn)

    # ── 편의 질의 ───────────────────────────────────────────
    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self.transaction() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self.transaction() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return _row_to_dict(cur, row)

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self.transaction() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [_row_to_dict(cur, r) or {} for r in rows]

    def ping(self) -> bool:
        try:
            with self.transaction() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception as exc:
            LOG.debug("ping 실패: %s", type(exc).__name__)
            return False

    def close(self) -> None:
        self._closed = True
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass
        with self._lock:
            self._opened = 0


def _row_to_dict(cur, row) -> dict[str, Any] | None:
    if row is None:
        return None
    columns = [d[0] for d in cur.description]
    return dict(zip(columns, row))


def row_to_dict(cur, row) -> dict[str, Any] | None:
    """커서 설명과 튜플을 dict 로. 저장소 구현에서 재사용한다."""
    return _row_to_dict(cur, row)
