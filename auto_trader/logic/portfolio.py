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
from utils.db import connect, init_db, now_kst_iso, sync_peaks
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
    # 보유 중 고점 — 트레일링 스톱의 기준. DB 에서 채워 넣는다.
    peak_price: float = 0.0
    # 이 종목을 처음 보유한 시각(ISO). 최소 보유기간 판단에 쓴다.
    first_bought_at: str = ""

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

    def apply_execution(self, code: str, name: str, side: str, qty: int, price: float) -> None:
        """주문 실행분을 메모리 상태에 즉시 반영한다.

        잔고 동기화는 사이클 시작에 한 번뿐이라, 이 갱신이 없으면 같은 사이클 안에서
        뒤에 오는 종목이 **이미 쓴 현금과 늘어난 보유 종목 수를 못 본 채** 리스크 검사를
        통과한다(한도 초과 매수). DRY_RUN 에서도 동일하게 반영해 시뮬레이션을 실제와 맞춘다.
        다음 사이클 시작 시 KIS 잔고로 다시 덮어써지므로 오차는 누적되지 않는다.
        """
        if qty <= 0 or price <= 0:
            return
        amount = qty * price
        position = self.positions.get(code)

        if side == "BUY":
            self.cash = max(self.cash - amount, 0.0)
            self.bought_today.add(code)
            if position is None:
                self.positions[code] = Position(
                    code=code, name=name, qty=qty, orderable_qty=qty,
                    avg_price=price, current_price=price, eval_amount=amount,
                    pnl_amount=0.0, pnl_pct=0.0,
                )
            else:
                total_qty = position.qty + qty
                position.avg_price = (position.cost_basis + amount) / total_qty
                position.qty = total_qty
                position.orderable_qty += qty
                position.eval_amount = total_qty * position.current_price
            return

        # SELL
        self.cash += amount
        if position is None:
            return
        position.qty = max(position.qty - qty, 0)
        position.orderable_qty = max(position.orderable_qty - qty, 0)
        if position.qty <= 0:
            del self.positions[code]
        else:
            position.eval_amount = position.qty * position.current_price


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

        # 보유 중 고점을 현재가로 갱신하고 각 포지션에 붙인다. 프로세스가 죽어도
        # 남아야 해서 DB 에 둔다 — 재기동 때 고점이 현재가로 리셋되면 트레일링
        # 스톱이 이미 번 이익을 그냥 놓친다.
        peaks = sync_peaks(
            self.db_path,
            {code: position.current_price for code, position in positions.items()},
        )
        entries = self._first_bought_at()
        for code, position in positions.items():
            position.peak_price = peaks.get(code, position.current_price)
            position.first_bought_at = entries.get(code, "")

        cash = balance.orderable_cash  # 0 이면 실제로 주문 가능 금액이 없는 것이다
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

    def _first_bought_at(self) -> dict[str, str]:
        """종목별 최초 보유 시각. _write_positions 가 남긴 값을 그대로 읽는다."""
        conn = connect(self.db_path)
        try:
            return {row["code"]: (row["first_bought_at"] or "")
                    for row in conn.execute("SELECT code, first_bought_at FROM positions")}
        finally:
            conn.close()

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
        """당일 매수 주문을 낸 종목 (1일 1회 제한용).

        **지금 내고 있는 주문과 같은 종류만 센다.** DRY_RUN 주문은 현금을 쓰지도,
        보유를 만들지도 않았다. 장중에 DRY_RUN 을 끄면 아침에 남긴 모의 기록이
        그날 남은 진짜 매수를 통째로 막아 버린다(실제로 그런 일이 있었다).
        DRY_RUN 중에는 모의 기록끼리 세어야 시뮬레이션이 실제와 같아진다.
        """
        query = ["""SELECT DISTINCT code FROM orders
                    WHERE side = 'BUY' AND substr(created_at, 1, 10) = ?
                      AND status != 'REJECTED'"""]
        # substr 로 앞 10자를 비교한다. SQLite 의 date() 는 '+09:00' 오프셋을
        # UTC 로 환산해 09시 이전 기록의 날짜를 하루 앞당긴다.
        params: list[object] = [moment.strftime("%Y-%m-%d")]
        if not self.settings.env.dry_run:
            query.append("AND dry_run = 0")

        conn = connect(self.db_path)
        try:
            rows = conn.execute(" ".join(query), params).fetchall()
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
        outcome: str = "",
    ) -> int:
        """AI 원문·파싱 결과·최종 결정을 전부 남긴다(사후 검증용)."""
        claude = decisions.get("claude")
        gemini = decisions.get("gemini")
        chatgpt = decisions.get("chatgpt")
        conn = connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO decisions
                   (cycle_id, code, name, holding,
                    claude_action, claude_confidence, claude_weight_pct, claude_reason, claude_ok, claude_raw,
                    gemini_action, gemini_confidence, gemini_weight_pct, gemini_reason, gemini_ok, gemini_raw,
                    chatgpt_action, chatgpt_confidence, chatgpt_weight_pct, chatgpt_reason, chatgpt_ok, chatgpt_raw,
                    final_action, final_weight_pct, final_reason, forced_exit,
                    risk_passed, risk_reason, outcome, snapshot_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cycle_id, snapshot.get("code", ""), snapshot.get("name", ""),
                    1 if snapshot.get("position", {}).get("holding") else 0,
                    getattr(claude, "action", None), getattr(claude, "confidence", None),
                    getattr(claude, "weight_pct", None), getattr(claude, "reason", None),
                    1 if getattr(claude, "ok", False) else 0, getattr(claude, "raw", None),
                    getattr(gemini, "action", None), getattr(gemini, "confidence", None),
                    getattr(gemini, "weight_pct", None), getattr(gemini, "reason", None),
                    1 if getattr(gemini, "ok", False) else 0, getattr(gemini, "raw", None),
                    getattr(chatgpt, "action", None), getattr(chatgpt, "confidence", None),
                    getattr(chatgpt, "weight_pct", None), getattr(chatgpt, "reason", None),
                    1 if getattr(chatgpt, "ok", False) else 0, getattr(chatgpt, "raw", None),
                    final.action, final.weight_pct, final.reason, forced_exit,
                    1 if risk_passed else 0, risk_reason, outcome,
                    json.dumps(snapshot, ensure_ascii=False), now_kst_iso(),
                ),
            )
            return int(cursor.lastrowid or 0)
        finally:
            conn.close()

    # -- 미체결 정리 ------------------------------------------------------- #

    OPEN_STATUSES = ("SUBMITTING", "PENDING", "PARTIAL", "UNKNOWN")

    def reconcile_open_orders(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """미체결로 남은 실주문을 체결조회로 다시 확인해 DB를 맞춘다.

        시장가 미체결은 `wait_for_fill` 이 30초만 보고 넘어가므로, 다음 사이클
        시작 때 여기서 최종 상태를 확정한다. 이걸 하지 않으면 이미 체결된 주문이
        영원히 PENDING 으로 남아 리포트와 손익이 어긋난다.
        """
        moment = now or datetime.now(KST)
        today = moment.strftime("%Y-%m-%d")
        placeholders = ", ".join("?" for _ in self.OPEN_STATUSES)

        conn = connect(self.db_path)
        try:
            rows = conn.execute(
                f"""SELECT id, order_no, code, name, side, qty, status FROM orders
                    WHERE dry_run = 0 AND order_no != ''
                      AND status IN ({placeholders})
                      AND substr(created_at, 1, 10) = ?""",
                (*self.OPEN_STATUSES, today),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        logger.info("미체결 주문 %d건 재확인", len(rows))
        updated: list[dict[str, Any]] = []
        for row in rows:
            try:
                status = self.api.get_order_status(row["order_no"])
            except KisApiError as exc:
                logger.warning("주문 %s 재확인 실패: %s", row["order_no"], exc)
                continue
            if status is None:
                continue

            if status.is_filled:
                state = "FILLED"
            elif status.is_partially_filled:
                state = "PARTIAL"
            elif status.filled_qty == 0 and status.remain_qty == 0:
                state = "CANCELED"  # 장 마감 등으로 소멸
            else:
                state = "PENDING"

            if state != row["status"]:
                self.update_order_fill(row["id"], status, state)
                logger.info("주문 %s: %s → %s (%d/%d주)",
                            row["order_no"], row["status"], state,
                            status.filled_qty, status.order_qty)
                updated.append({"order_no": row["order_no"], "code": row["code"],
                                "name": row["name"], "side": row["side"],
                                "before": row["status"], "after": state,
                                "filled_qty": status.filled_qty})
        return updated

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
