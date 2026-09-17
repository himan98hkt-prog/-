"""SQLite 연결과 스키마 생성 (ORM 미사용).

테이블
  positions  : 보유 포지션 스냅샷 (매 사이클 KIS 잔고로 동기화)
  orders     : 주문·체결 내역 (DRY_RUN 주문 포함)
  decisions  : AI 원문 응답 + 파싱 결과 + 최종 결정 (사후 검증용, 전부 보관)
  daily_pnl  : 일자별 손익 요약
  ai_usage   : AI 호출 토큰·추정 비용 (비용 추적)
  bot_state  : 봇 실행 상태 한 줄 (대시보드용)
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
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
    chatgpt_action    TEXT,
    chatgpt_confidence REAL,
    chatgpt_weight_pct INTEGER,
    chatgpt_reason    TEXT,
    chatgpt_ok        INTEGER,
    chatgpt_raw       TEXT,
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

CREATE TABLE IF NOT EXISTS ai_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id      TEXT,
    code          TEXT,
    agent         TEXT    NOT NULL,
    model         TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    ok            INTEGER NOT NULL DEFAULT 1,
    elapsed_sec   REAL    NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage (created_at);
CREATE INDEX IF NOT EXISTS idx_ai_usage_cycle   ON ai_usage (cycle_id);

-- 대시보드가 읽는 봇 실행 상태 (단일 행, id=1)
CREATE TABLE IF NOT EXISTS bot_state (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    status                TEXT,
    pid                   INTEGER,
    kis_env               TEXT,
    dry_run               INTEGER,
    started_at            TEXT,
    last_cycle_at         TEXT,
    last_cycle_label      TEXT,
    last_cycle_codes      INTEGER NOT NULL DEFAULT 0,
    last_cycle_orders     INTEGER NOT NULL DEFAULT 0,
    next_cycle_at         TEXT,
    universe_size         INTEGER NOT NULL DEFAULT 0,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    last_error            TEXT,
    updated_at            TEXT
);

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

-- 벤치마크: 감시 종목을 그냥 사서 들고만 있었을 때의 성적.
-- 사이클마다 이미 받아 온 현재가를 그대로 적어 두므로 추가 API 호출이 없다.
CREATE TABLE IF NOT EXISTS benchmark_prices (
    date            TEXT NOT NULL,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    price           REAL NOT NULL,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (date, code)
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


# 나중에 추가된 컬럼 — 이미 쓰던 DB 에도 조용히 채워 넣는다(기록을 버리지 않는다).
LATER_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("decisions", "chatgpt_action", "TEXT"),
    ("decisions", "chatgpt_confidence", "REAL"),
    ("decisions", "chatgpt_weight_pct", "INTEGER"),
    ("decisions", "chatgpt_reason", "TEXT"),
    ("decisions", "chatgpt_ok", "INTEGER"),
    ("decisions", "chatgpt_raw", "TEXT"),
)


def _add_missing_columns(conn) -> None:
    for table, column, kind in LATER_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            logger.info("컬럼 추가: %s.%s", table, column)


def init_db(db_path: Path | str) -> Path:
    """스키마를 생성(이미 있으면 그대로 두기)하고 DB 경로를 반환한다."""
    path = Path(db_path)
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
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


# --------------------------------------------------------------------------- #
# 봇 상태 (대시보드가 읽는 단일 행)
# --------------------------------------------------------------------------- #


def update_bot_state(db_path: Path | str, **fields: Any) -> None:
    """`bot_state` 의 지정한 필드만 갱신한다 (없으면 행을 만든다)."""
    if not fields:
        return
    allowed = {
        "status", "pid", "kis_env", "dry_run", "started_at", "last_cycle_at",
        "last_cycle_label", "last_cycle_codes", "last_cycle_orders", "next_cycle_at",
        "universe_size", "consecutive_failures", "last_error",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"알 수 없는 bot_state 필드: {sorted(unknown)}")

    fields["updated_at"] = now_kst_iso()
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{name}=excluded.{name}" for name in fields)

    conn = connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO bot_state (id, {columns}) VALUES (1, {placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            tuple(fields.values()),
        )
    finally:
        conn.close()


def get_bot_state(db_path: Path | str) -> dict[str, Any]:
    """봇 상태 한 줄. 테이블이 아직 없어도 빈 dict 를 돌려준다(구버전 DB 호환)."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return dict(row) if row else {}


def record_ai_usage(
    db_path: Path | str,
    *,
    cycle_id: str,
    code: str,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    ok: bool,
    elapsed_sec: float,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO ai_usage (cycle_id, code, agent, model, input_tokens, output_tokens,
                                     cost_usd, ok, elapsed_sec, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cycle_id, code, agent, model, int(input_tokens), int(output_tokens),
             float(cost_usd), 1 if ok else 0, float(elapsed_sec), now_kst_iso()),
        )
    finally:
        conn.close()


# --- 벤치마크(단순 보유) ---------------------------------------------------- #

def record_benchmark_price(db_path: Path | str, *, date: str, code: str,
                           name: str, price: float) -> None:
    """그날 그 종목의 가장 최근 관측가를 남긴다(같은 날은 덮어쓴다).

    사이클이 이미 조회한 값을 재사용하므로 KIS 호출이 늘지 않는다.
    """
    if price <= 0:
        return  # 값을 못 읽은 경우 — 0 을 남기면 수익률이 망가진다
    with session(db_path) as conn:
        conn.execute(
            """INSERT INTO benchmark_prices (date, code, name, price, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date, code) DO UPDATE SET
                   price = excluded.price, name = excluded.name,
                   updated_at = excluded.updated_at""",
            (date, code, name, float(price), now_kst_iso()),
        )
