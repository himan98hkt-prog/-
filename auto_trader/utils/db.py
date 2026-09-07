"""SQLite 연결과 스키마 생성 (ORM 미사용).

테이블
  positions  : 보유 포지션 스냅샷 (매 사이클 KIS 잔고로 동기화)
  orders     : 주문·체결 내역 (DRY_RUN 주문 포함)
  decisions  : AI 원문 응답 + 파싱 결과 + 최종 결정 (사후 검증용, 전부 보관)
  daily_pnl  : 일자별 손익 요약
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS positions (
    code            TEXT PRIMARY KEY,
    name            TEXT,
    qty             INTEGER NOT NULL DEFAULT 0,
    avg_price       REAL    NOT NULL DEFAULT 0,
    current_price   REAL    NOT NULL DEFAULT 0,
    eval_amount     REAL    NOT NULL DEFAULT 0,
    pnl_amount      REAL    NOT NULL DEFAULT 0,
    pnl_pct         REAL    NOT NULL DEFAULT 0,
    first_bought_at TEXT,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id      TEXT,
    order_no      TEXT,
    code          TEXT    NOT NULL,
    name          TEXT,
    side          TEXT    NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type    TEXT    NOT NULL CHECK (order_type IN ('market', 'limit')),
    qty           INTEGER NOT NULL,
    price         REAL    NOT NULL DEFAULT 0,
    filled_qty    INTEGER NOT NULL DEFAULT 0,
    filled_price  REAL    NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL,
    dry_run       INTEGER NOT NULL DEFAULT 1,
    kis_env       TEXT    NOT NULL,
    reason        TEXT,
    error         TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_code_created ON orders (code, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_cycle        ON orders (cycle_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_no     ON orders (order_no);

CREATE TABLE IF NOT EXISTS decisions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id          TEXT    NOT NULL,
    code              TEXT    NOT NULL,
    name              TEXT,
    holding           INTEGER NOT NULL DEFAULT 0,
    claude_action     TEXT,
    claude_confidence REAL,
    claude_weight_pct INTEGER,
    claude_reason     TEXT,
    claude_ok         INTEGER,
    claude_raw        TEXT,
    gemini_action     TEXT,
    gemini_confidence REAL,
    gemini_weight_pct INTEGER,
    gemini_reason     TEXT,
    gemini_ok         INTEGER,
    gemini_raw        TEXT,
    final_action      TEXT    NOT NULL,
    final_weight_pct  INTEGER NOT NULL DEFAULT 0,
    final_reason      TEXT,
    forced_exit       TEXT,
    risk_passed       INTEGER NOT NULL DEFAULT 0,
    risk_reason       TEXT,
    snapshot_json     TEXT,
    created_at        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_cycle       ON decisions (cycle_id);
CREATE INDEX IF NOT EXISTS idx_decisions_code_created ON decisions (code, created_at);

CREATE TABLE IF NOT EXISTS daily_pnl (
    date            TEXT PRIMARY KEY,
    start_equity    REAL NOT NULL DEFAULT 0,
    end_equity      REAL NOT NULL DEFAULT 0,
    realized_pnl    REAL NOT NULL DEFAULT 0,
    unrealized_pnl  REAL NOT NULL DEFAULT 0,
    total_pnl_pct   REAL NOT NULL DEFAULT 0,
    buy_count       INTEGER NOT NULL DEFAULT 0,
    sell_count      INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);
"""


def now_kst_iso() -> str:
    """DB에 저장할 KST ISO8601 문자열 (naive datetime 사용 금지)."""
    return datetime.now(KST).isoformat(timespec="seconds")


def connect(db_path: Path | str) -> sqlite3.Connection:
    """행을 `sqlite3.Row`로 반환하는 연결을 만든다."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    """with 블록 종료 시 커밋(예외 시 롤백)하고 연결을 닫는다."""
    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str) -> Path:
    """스키마를 생성(이미 있으면 그대로 두기)하고 DB 경로를 반환한다."""
    path = Path(db_path)
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
    logger.info("SQLite 스키마 준비 완료: %s", path)
    return path


def table_names(db_path: Path | str) -> list[str]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [row["name"] for row in rows]
