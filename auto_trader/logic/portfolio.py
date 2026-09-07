"""보유 포지션·현금 상태 관리 (SQLite + KIS 잔고 동기화).

**DB를 진실로 삼지 않는다.** 사이클 시작마다 KIS 잔고로 덮어쓴다.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config.loader import Settings
from trading.kis_api import Balance, KisApi, KisApiError, OrderStatus
from utils.db import connect, init_db, now_kst_iso
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("portfolio")

FILL_POLL_SECONDS = 5
FILL_TIMEOUT_SECONDS = 30


@dataclass
class Position:
    code: str
    name: str
    qty: int
    orderable_qty: int
    avg_price: float
    current_price: float
    eval_amount: float
    pnl_amount: float
    pnl_pct: float

    @property
    def cost_basis(self) -> float:
        """취득원가 — 투자 한도 계산의 기준."""
        return self.avg_price * self.qty


@dataclass
class PortfolioState:
    """리스크 판단에 필요한 계좌 스냅샷."""

    positions: dict[str, Position] = field(default_factory=dict)
    cash: float = 0.0  # 주문가능현금
    deposit: float = 0.0
    daily_pnl_pct: float = 0.0
    bought_today: set[str] = field(default_factory=set)
    synced_at: datetime | None = None

    @property
    def total_invested(self) -> float:
        return sum(position.cost_basis for position in self.positions.values())

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def get(self, code: str) -> Position | None:
        return self.positions.get(code)

    def holds(self, code: str) -> bool:
        position = self.positions.get(code)
        return bool(position and position.qty > 0)


class Portfolio:
    """KIS 잔고 ↔ SQLite 동기화 + 주문·결정 기록."""

    def __init__(self, settings: Settings, api: KisApi, db_path: Path | str | None = None) -> None:
        self.settings = settings
        self.api = api
        self.db_path = Path(db_path or settings.paths["db"])
        init_db(self.db_path)
        self.state = PortfolioState()

    # -- 동기화 ------------------------------------------------------------ #

    def sync(self, *, now: datetime | None = None) -> PortfolioState:
        """KIS 잔고를 조회해 DB와 메모리 상태를 갱신한다."""
        moment = now or datetime.now(KST)
        balance: Balance = self.api.get_balance()

        positions = {
            holding.code: Position(
                code=holding.code,
                name=holding.name,
                qty=holding.qty,
                orderable_qty=holding.orderable_qty,
                avg_price=holding.avg_price,
                current_price=holding.current_price,
                eval_amount=holding.eval_amount,
                pnl_amount=holding.pnl_amount,
                pnl_pct=holding.pnl_pct,
            )
            for holding in balance.holdings
            if holding.qty > 0
        }
        self._write_positions(positions, moment)

        cash = balance.orderable_cash or balance.deposit
        equity = cash + sum(position.eval_amount for position in positions.values())
        daily_pnl_pct = self._update_daily_pnl(equity, positions, moment)

        self.state = PortfolioState(
            positions=positions,
            cash=cash,
            deposit=balance.deposit,
            daily_pnl_pct=daily_pnl_pct,
            bought_today=self._bought_today(moment),
            synced_at=moment,
        )
        logger.info(
            "잔고 동기화: %d종목 / 주문가능 %s원 / 당일손익 %+.2f%%",
            len(positions), f"{cash:,.0f}", daily_pnl_pct,
        )
        return self.state

    def _write_positions(self, positions: dict[str, Position], moment: datetime) -> None:
        conn = connect(self.db_path)
        try:
            stamp = moment.isoformat(timespec="seconds")
            existing = {row["code"] for row in conn.execute("SELECT code FROM positions")}
            for position in positions.values():
                conn.execute(
                    """INSERT INTO positions
                       (code, name, qty, avg_price, current_price, eval_amount,
                        pnl_amount, pnl_pct, first_bought_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(code) DO UPDATE SET
                         name=excluded.name, qty=excluded.qty, avg_price=excluded.avg_price,
                         current_price=excluded.current_price, eval_amount=excluded.eval_amount,
                         pnl_amount=excluded.pnl_amount, pnl_pct=excluded.pnl_pct,
                         updated_at=excluded.updated_at""",
                    (position.code, position.name, position.qty, position.avg_price,
                     position.current_price, position.eval_amount, position.pnl_amount,
                     position.pnl_pct, stamp, stamp),
                )
            # 청산된 종목은 DB에서 제거한다(잔고가 진실).
            for code in existing - set(positions):
                conn.execute("DELETE FROM positions WHERE code = ?", (code,))
        finally:
            conn.close()

    def _update_daily_pnl(
        self, equity: float, positions: dict[str, Position], moment: datetime
    ) -> float:
        """당일 시작 자산 대비 손익률. 첫 동기화 시 시작 자산을 기록한다."""
        today = moment.strftime("%Y-%m-%d")
        unrealized = sum(position.pnl_amount for position in positions.values())
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT start_equity FROM daily_pnl WHERE date = ?", (today,)).fetchone()
            if row is None:
                conn.execute(
                    """INSERT INTO daily_pnl (date, start_equity, end_equity, unrealized_pnl, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (today, equity, equity, unrealized, now_kst_iso()),
                )
                return 0.0

            start_equity = float(row["start_equity"])
            pnl_pct = ((equity - start_equity) / start_equity * 100) if start_equity > 0 else 0.0
            conn.execute(
                """UPDATE daily_pnl
                   SET end_equity = ?, unrealized_pnl = ?, total_pnl_pct = ?, updated_at = ?
                   WHERE date = ?""",
                (equity, unrealized, pnl_pct, now_kst_iso(), today),
            )
            return round(pnl_pct, 4)
        finally:
            conn.close()

    def _bought_today(self, moment: datetime) -> set[str]:
        """당일 매수 주문을 낸 종목 (DRY_RUN 주문 포함 — 1일 1회 제한 목적)."""
        conn = connect(self.db_path)
        try:
            rows = conn.execute(
                # substr 로 앞 10자를 비교한다. SQLite 의 date() 는 '+09:00' 오프셋을
                # UTC 로 환산해 09시 이전 기록의 날짜를 하루 앞당긴다.
                """SELECT DISTINCT code FROM orders
                   WHERE side = 'BUY' AND substr(created_at, 1, 10) = ?
                     AND status != 'REJECTED'""",
                (moment.strftime("%Y-%m-%d"),),
            ).fetchall()
        finally:
            conn.close()
        return {row["code"] for row in rows}

    # -- 기록 -------------------------------------------------------------- #

    def record_order(
        self,
        *,
        cycle_id: str,
        code: str,
        name: str,
        side: str,
        order_type: str,
        qty: int,
        price: float,
        status: str,
        order_no: str = "",
        dry_run: bool = True,
        reason: str = "",
        error: str = "",
    ) -> int:
        conn = connect(self.db_path)
        try:
            stamp = now_kst_iso()
            cursor = conn.execute(
                """INSERT INTO orders
                   (cycle_id, order_no, code, name, side, order_type, qty, price,
                    status, dry_run, kis_env, reason, error, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cycle_id, order_no, code, name, side, order_type, qty, price, status,
                 1 if dry_run else 0, self.settings.env.kis_env, reason, error, stamp, stamp),
            )
            return int(cursor.lastrowid or 0)
        finally:
            conn.close()

    def update_order_fill(self, order_id: int, status: OrderStatus | None, state: str) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute(
                """UPDATE orders SET filled_qty = ?, filled_price = ?, status = ?, updated_at = ?
                   WHERE id = ?""",
                (status.filled_qty if status else 0, status.filled_price if status else 0.0,
                 state, now_kst_iso(), order_id),
            )
        finally:
            conn.close()

    def record_decision(
        self,
        *,
        cycle_id: str,
        snapshot: dict[str, Any],
        decisions: dict[str, Any],
        final: Any,
        forced_exit: str | None = None,
        risk_passed: bool = False,
        risk_reason: str = "",
    ) -> int:
        """AI 원문·파싱 결과·최종 결정을 전부 남긴다(사후 검증용)."""
        claude = decisions.get("claude")
        gemini = decisions.get("gemini")
        conn = connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO decisions
                   (cycle_id, code, name, holding,
                    claude_action, claude_confidence, claude_weight_pct, claude_reason, claude_ok, claude_raw,
                    gemini_action, gemini_confidence, gemini_weight_pct, gemini_reason, gemini_ok, gemini_raw,
                    final_action, final_weight_pct, final_reason, forced_exit,
                    risk_passed, risk_reason, snapshot_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cycle_id, snapshot.get("code", ""), snapshot.get("name", ""),
                    1 if snapshot.get("position", {}).get("holding") else 0,
                    getattr(claude, "action", None), getattr(claude, "confidence", None),
                    getattr(claude, "weight_pct", None), getattr(claude, "reason", None),
                    1 if getattr(claude, "ok", False) else 0, getattr(claude, "raw", None),
                    getattr(gemini, "action", None), getattr(gemini, "confidence", None),
                    getattr(gemini, "weight_pct", None), getattr(gemini, "reason", None),
                    1 if getattr(gemini, "ok", False) else 0, getattr(gemini, "raw", None),
                    final.action, final.weight_pct, final.reason, forced_exit,
                    1 if risk_passed else 0, risk_reason,
                    json.dumps(snapshot, ensure_ascii=False), now_kst_iso(),
                ),
            )
            return int(cursor.lastrowid or 0)
        finally:
            conn.close()

    # -- 체결 확인 --------------------------------------------------------- #

    def wait_for_fill(self, order_no: str, order_type: str, code: str, qty: int) -> tuple[str, OrderStatus | None]:
        """최대 30초 동안 5초 간격으로 체결을 확인한다.

        Returns:
            (`FILLED` | `PARTIAL` | `PENDING` | `CANCELED` | `UNKNOWN`, 마지막 상태)
        """
        last: OrderStatus | None = None
        for _ in range(max(FILL_TIMEOUT_SECONDS // FILL_POLL_SECONDS, 1)):
            time.sleep(FILL_POLL_SECONDS)
            try:
                last = self.api.get_order_status(order_no)
            except KisApiError as exc:
                logger.warning("체결 조회 실패(%s) — 재시도합니다", exc)
                continue
            if last is None:
                continue
            if last.is_filled:
                return "FILLED", last

        if last is None:
            logger.warning("주문 %s 체결 상태를 확인하지 못했습니다", order_no)
            return "UNKNOWN", None

        if order_type == "limit":
            # 지정가 미체결은 취소하고 이번 사이클은 넘긴다.
            try:
                self.api.cancel_order(last.order_no, code, last.remain_qty or qty)
                logger.info("지정가 미체결 취소: %s (%d주)", order_no, last.remain_qty)
                return "CANCELED", last
            except KisApiError as exc:
                logger.error("주문 취소 실패(%s) — 미체결로 남깁니다", exc)
                return "PENDING", last

        # 시장가 미체결은 다음 사이클에서 다시 조회한다.
        return ("PARTIAL" if last.is_partially_filled else "PENDING"), last
