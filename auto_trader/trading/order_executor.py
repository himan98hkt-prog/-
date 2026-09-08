"""최종 결정 → 주문 수량 계산 → 주문 → 체결 확인 → 기록 → 알림.

`DRY_RUN=true` 면 주문 API를 호출하지 않고 로그·알림만 남긴다(절대 규칙 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.loader import Settings
from logic.decision_maker import FinalDecision
from logic.portfolio import Portfolio, PortfolioState
from logic.risk_manager import RiskManager
from trading.kis_api import KisApi, KisApiError
from utils.logger import get_logger
from utils.notifier import Notifier

logger = get_logger("order_executor")


@dataclass
class ExecutionResult:
    ordered: bool = False
    side: str = ""
    qty: int = 0
    price: float = 0.0
    status: str = ""
    order_no: str = ""
    reason: str = ""
    dry_run: bool = True
    error: str = ""

    @classmethod
    def skipped(cls, reason: str) -> "ExecutionResult":
        return cls(ordered=False, status="SKIPPED", reason=reason)


class OrderExecutor:
    def __init__(
        self,
        settings: Settings,
        api: KisApi,
        portfolio: Portfolio,
        risk: RiskManager,
        notifier: Notifier | None = None,
    ) -> None:
        self.settings = settings
        self.api = api
        self.portfolio = portfolio
        self.risk = risk
        self.notifier = notifier

    # -- 가격·수량 계산 ----------------------------------------------------- #

    def _limit_price(self, current_price: float, side: str) -> int:
        """지정가 = 현재가 ± 허용 슬리피지 (매수는 위로, 매도는 아래로)."""
        slippage = self.settings.risk.limit_slippage_pct / 100
        factor = (1 + slippage) if side == "BUY" else (1 - slippage)
        return int(round(current_price * factor))

    def _order_price(self, current_price: float, side: str) -> int:
        if self.settings.risk.order_type == "limit":
            return self._limit_price(current_price, side)
        return 0  # 시장가

    def buy_quantity(self, final: FinalDecision, price: float, state: PortfolioState) -> tuple[int, float]:
        """(수량, 주문금액). 수량 0이면 스킵 대상."""
        amount = self.risk.buy_amount(final.weight_pct, state)
        qty = self.risk.buy_quantity(amount, price)
        return qty, qty * price

    @staticmethod
    def sell_quantity(final: FinalDecision, state: PortfolioState, code: str) -> int:
        position = state.get(code)
        if position is None or position.qty <= 0:
            return 0
        # 주문가능수량 0 은 '락 걸린 물량' 이라는 뜻이다 — 보유수량으로 대체하지 않는다.
        available = position.orderable_qty
        if available <= 0:
            return 0
        if final.action == "SELL_ALL":
            return available
        return max(int(available * final.sell_ratio), 1)

    # -- 실행 -------------------------------------------------------------- #

    def execute(
        self,
        final: FinalDecision,
        snapshot: dict[str, Any],
        state: PortfolioState,
        *,
        cycle_id: str = "",
    ) -> ExecutionResult:
        code = snapshot["code"]
        name = snapshot.get("name", code)
        price = float(snapshot.get("price", {}).get("current", 0))

        if final.action == "HOLD":
            return ExecutionResult.skipped("관망")
        if price <= 0:
            return ExecutionResult.skipped("현재가를 알 수 없음")

        if final.is_buy:
            side = "BUY"
            qty, amount = self.buy_quantity(final, price, state)
            if qty <= 0:
                logger.info("%s 매수 수량 0주 — 스킵 (가용현금 %s원)", code, f"{state.cash:,.0f}")
                return ExecutionResult.skipped(f"매수 수량 0주 (가용현금 {state.cash:,.0f}원)")
        else:
            side = "SELL"
            qty = self.sell_quantity(final, state, code)
            amount = qty * price
            if qty <= 0:
                return ExecutionResult.skipped("매도 가능 수량 없음")

        order_type = self.settings.risk.order_type
        order_price = self._order_price(price, side)

        if self.settings.env.dry_run:
            return self._record_dry_run(cycle_id, code, name, side, order_type, qty,
                                        order_price or price, final.reason, amount)

        return self._place_real_order(cycle_id, code, name, side, order_type, qty,
                                      order_price, price, final.reason)

    def _record_dry_run(
        self, cycle_id: str, code: str, name: str, side: str, order_type: str,
        qty: int, price: float, reason: str, amount: float,
    ) -> ExecutionResult:
        label = "매수" if side == "BUY" else "매도"
        logger.info("[DRY_RUN] %s %s(%s) %d주 @%s원 (약 %s원) — %s",
                    label, name, code, qty, f"{price:,.0f}", f"{amount:,.0f}", reason)
        self.portfolio.record_order(
            cycle_id=cycle_id, code=code, name=name, side=side, order_type=order_type,
            qty=qty, price=price, status="DRY_RUN", dry_run=True, reason=reason,
        )
        result = ExecutionResult(ordered=True, side=side, qty=qty, price=price,
                                 status="DRY_RUN", reason=reason, dry_run=True)
        self._notify_trade(code, name, result)
        return result

    def _place_real_order(
        self, cycle_id: str, code: str, name: str, side: str, order_type: str,
        qty: int, order_price: int, current_price: float, reason: str,
    ) -> ExecutionResult:
        order_id = self.portfolio.record_order(
            cycle_id=cycle_id, code=code, name=name, side=side, order_type=order_type,
            qty=qty, price=order_price or current_price, status="SUBMITTING",
            dry_run=False, reason=reason,
        )
        try:
            order = self.api.place_order(code, qty, side, price=order_price, order_type=order_type)
        except KisApiError as exc:
            # 주문 API는 재시도하지 않는다(중복 체결 위험). 대신 반드시 알린다 —
            # 특히 손절 매도가 조용히 실패하면 손실이 그대로 커진다.
            logger.error("%s %s 주문 실패: %s", code, side, exc)
            self.portfolio.update_order_fill(order_id, None, "REJECTED")
            self._notify_rejected(code, name, side, qty, reason, str(exc))
            return ExecutionResult(ordered=False, side=side, qty=qty, price=current_price,
                                   status="REJECTED", reason=reason, dry_run=False, error=str(exc))

        state, status = self.portfolio.wait_for_fill(order.order_no, order_type, code, qty)
        self.portfolio.update_order_fill(order_id, status, state)

        filled_price = status.filled_price if status and status.filled_price else current_price
        filled_qty = status.filled_qty if status else 0
        logger.info("%s %s 주문 %s: %d/%d주 @%s원",
                    code, side, state, filled_qty, qty, f"{filled_price:,.0f}")

        result = ExecutionResult(
            ordered=True, side=side, qty=filled_qty or qty, price=filled_price,
            status=state, order_no=order.order_no, reason=reason, dry_run=False,
        )
        self._notify_trade(code, name, result)
        return result

    def _notify_rejected(
        self, code: str, name: str, side: str, qty: int, reason: str, error: str
    ) -> None:
        """주문 거부 알림. 손절 매도 실패는 최우선으로 알린다."""
        if self.notifier is None:
            return
        label = "매수" if side == "BUY" else "매도"
        stop_loss = "손절" in reason
        title = "🚨 손절 매도 실패 — 즉시 확인 필요" if stop_loss else f"⚠️ {label} 주문 거부"
        lines = [f"{name}({code}) {label} {qty:,}주", f"사유: {reason}", f"오류: {error}"]
        if stop_loss:
            lines.append("포지션이 그대로 남아 있습니다. 증권사 앱에서 직접 확인하세요.")
        # dedupe 되면 반복 실패가 묻히므로 key 를 종목·구분별로 나눈다.
        self.notifier.send_alert(title, lines, key=f"order_rejected:{code}:{side}")

    def _notify_trade(self, code: str, name: str, result: ExecutionResult) -> None:
        if self.notifier is None:
            return
        self.notifier.send_trade({
            "code": code, "name": name, "side": result.side, "qty": result.qty,
            "price": result.price, "filled_price": result.price, "status": result.status,
            "dry_run": result.dry_run, "reason": result.reason,
        })
