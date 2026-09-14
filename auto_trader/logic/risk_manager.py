"""리스크 규칙 검사 — **AI 판단보다 상위**다(절대 규칙 3).

여기서 거부된 주문은 AI가 아무리 강하게 권해도 실행되지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from config.loader import RiskConfig, ScheduleConfig
from logic.portfolio import PortfolioState, Position
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("risk_manager")

ForcedExit = Literal["STOP_LOSS", "TAKE_PROFIT"]


@dataclass
class RiskVerdict:
    allowed: bool
    reason: str
    rule: str = ""  # 거부한 규칙 이름 (로그·알림용)

    def __bool__(self) -> bool:  # `if verdict:` 로 쓰기 위함
        return self.allowed

    def __iter__(self):  # `allowed, reason = check_buy(...)` 언패킹 지원
        yield self.allowed
        yield self.reason


class RiskManager:
    def __init__(self, risk: RiskConfig, schedule: ScheduleConfig) -> None:
        self.risk = risk
        self.schedule = schedule

    # -- 매수 가능 여부 ----------------------------------------------------- #

    def check_buy(
        self,
        code: str,
        amount_krw: float,
        portfolio: PortfolioState,
        *,
        now: datetime | None = None,
    ) -> RiskVerdict:
        """지시서 5-9의 7개 규칙을 순서대로 검사한다."""
        moment = (now or datetime.now(KST)).astimezone(KST)
        cap = self.risk.total_investment_cap_krw
        position = portfolio.get(code)
        held_cost = position.cost_basis if position else 0.0

        # 6. 최소 주문 금액 — 가장 먼저 걸러야 나머지 계산이 의미 있다.
        if amount_krw < self.risk.min_order_krw:
            return RiskVerdict(
                False,
                f"주문 금액 {amount_krw:,.0f}원이 최소 {self.risk.min_order_krw:,}원 미만",
                "min_order_krw",
            )

        # 1. 총 투자액 한도
        if portfolio.total_invested + amount_krw > cap:
            return RiskVerdict(
                False,
                f"총 투자액 한도 초과 (기보유 {portfolio.total_invested:,.0f} + 신규 "
                f"{amount_krw:,.0f} > 한도 {cap:,})",
                "total_investment_cap_krw",
            )

        # 2. 종목당 비중 한도 (기보유분 포함)
        position_cap = cap * self.risk.max_position_pct / 100
        if held_cost + amount_krw > position_cap:
            return RiskVerdict(
                False,
                f"종목당 비중 한도 초과 ({held_cost + amount_krw:,.0f} > "
                f"{position_cap:,.0f} = 총액의 {self.risk.max_position_pct:.0f}%)",
                "max_position_pct",
            )

        # 3. 동시 보유 종목 수 (추가매수는 허용)
        if position is None and portfolio.position_count >= self.risk.max_positions:
            return RiskVerdict(
                False,
                f"보유 종목 수 한도 도달 ({portfolio.position_count}/{self.risk.max_positions})",
                "max_positions",
            )

        # 4. 당일 손실 한도
        if portfolio.daily_pnl_pct <= -self.risk.daily_loss_limit_pct:
            return RiskVerdict(
                False,
                f"당일 손실 한도 초과 ({portfolio.daily_pnl_pct:+.2f}% ≤ "
                f"-{self.risk.daily_loss_limit_pct}%)",
                "daily_loss_limit_pct",
            )

        # 5. 신규 매수 마감 시각
        if moment.time() > self.schedule.last_new_buy:
            return RiskVerdict(
                False,
                f"신규 매수 마감 시각 경과 ({moment:%H:%M} > "
                f"{self.schedule.last_new_buy:%H:%M})",
                "last_new_buy",
            )

        # 7. 동일 종목 당일 매수 1회 제한
        if code in portfolio.bought_today:
            return RiskVerdict(False, "당일 이미 매수한 종목", "one_buy_per_day")

        return RiskVerdict(True, "리스크 규칙 통과")

    # -- 강제 청산 --------------------------------------------------------- #

    def check_forced_exit(self, position: Position | None) -> ForcedExit | None:
        """손절선 도달 → STOP_LOSS(AI 판단 없이 즉시 전량 매도),
        익절선 도달 → TAKE_PROFIT(플래그만; 합의 엔진에 전달)."""
        if position is None or position.qty <= 0:
            return None
        if position.pnl_pct <= self.risk.stop_loss_pct:
            logger.warning(
                "손절선 도달: %s %+.2f%% ≤ %.1f%% → 즉시 전량 매도",
                position.code, position.pnl_pct, self.risk.stop_loss_pct,
            )
            return "STOP_LOSS"
        if position.pnl_pct >= self.risk.take_profit_pct:
            logger.info(
                "익절선 도달: %s %+.2f%% ≥ %.1f%% → AI 재판단 요청",
                position.code, position.pnl_pct, self.risk.take_profit_pct,
            )
            return "TAKE_PROFIT"
        return None

    # -- 주문 수량 --------------------------------------------------------- #

    def buy_amount(self, weight_pct: int, portfolio: PortfolioState) -> float:
        """목표 비중과 가용 현금 중 작은 쪽."""
        target = self.risk.total_investment_cap_krw * min(weight_pct, self.risk.max_position_pct) / 100
        return max(min(target, portfolio.cash), 0.0)

    def buy_quantity(self, amount_krw: float, price: float) -> int:
        if price <= 0:
            return 0
        return int(math.floor(amount_krw / price))
