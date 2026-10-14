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

ForcedExit = Literal["STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP"]
EPSILON = 1e-6  # 원 단위 가격 비교에서 부동소수점 오차를 흡수한다


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
        # 트레일링이 켜져 있으면 **승자의 청산은 트레일링이 전담한다.**
        # 예전 익절 경로를 함께 두면 +10% 마다 AI 재판단이 걸리고, 그때 AI 가
        # 응답하지 않으면 절반을 팔아버려 트레일링이 하려던 일을 무너뜨린다.
        if self.risk.trailing_stop_pct > 0:
            return self.trailing_exit(position)

        if position.pnl_pct >= self.risk.take_profit_pct:
            logger.info(
                "익절선 도달: %s %+.2f%% ≥ %.1f%% → AI 재판단 요청",
                position.code, position.pnl_pct, self.risk.take_profit_pct,
            )
            return "TAKE_PROFIT"
        return None

    def check_sell(self, position: Position | None, *,
                   now: datetime | None = None) -> RiskVerdict:
        """자발적 매도를 허용할지. **손절·트레일링은 여기를 거치지 않는다** —
        자산을 지키는 쪽은 언제나 통과해야 한다.

        하루짜리 회전은 왕복 거래비용만 내고 남는 게 없다. AI 가 산 날 바로
        마음을 바꿔도 한 번은 재워 둔다.
        """
        days = self.risk.min_holding_days
        if not position or days <= 0 or not position.first_bought_at:
            return RiskVerdict(True, "")
        try:
            bought = datetime.fromisoformat(position.first_bought_at)
        except ValueError:
            return RiskVerdict(True, "")  # 값이 깨졌으면 막지 않는다
        moment = (now or datetime.now(KST)).astimezone(KST)
        if bought.tzinfo is None:
            bought = bought.replace(tzinfo=KST)
        held = (moment.date() - bought.date()).days
        if held < days:
            return RiskVerdict(
                False,
                f"최소 보유기간 미달 ({held}일 < {days}일) — 손절·트레일링은 계속 동작합니다",
                "min_holding_days",
            )
        return RiskVerdict(True, "")

    def trailing_stop_price(self, position: Position) -> float:
        """고점 대비 트레일링 손절가. 기능이 꺼져 있거나 아직 발동 전이면 0.

        **활성화 가격 아래로는 내려가지 않는다.** 그래야 +10% 에 켜진 트레일링이
        나중에 +4% 에 팔아치우는 일이 없다 — 고정 익절선보다 나쁠 수가 없게 만든다.
        """
        risk = self.risk
        if risk.trailing_stop_pct <= 0 or position.avg_price <= 0:
            return 0.0
        peak = max(getattr(position, "peak_price", 0.0) or 0.0, position.current_price)
        armed_at = position.avg_price * (1 + risk.trailing_activate_pct / 100)
        # 부동소수점 때문에 '딱 +10%' 가 미달로 판정되지 않게 한 호가 미만을 눈감는다.
        if peak < armed_at - EPSILON:
            return 0.0  # 아직 활성화 가격을 밟은 적이 없다
        # 주가는 원 단위다. 소수점을 남기면 비교가 지저분해지고 로그도 읽기 어렵다.
        return float(round(max(peak * (1 - risk.trailing_stop_pct / 100), armed_at)))

    def trailing_exit(self, position: Position) -> ForcedExit | None:
        """트레일링 스톱에 걸렸으면 전량 청산."""
        stop = self.trailing_stop_price(position)
        # 기준선에 **닿은** 것만으로는 팔지 않는다. 활성화되는 순간에는 현재가와
        # 기준선이 같은데, 그때 팔아버리면 고정 익절선과 똑같아져 트레일링이
        # 하려던 일(승자를 더 태우기)을 전혀 못 하게 된다.
        if stop <= 0 or position.current_price >= stop - EPSILON:
            return None
        logger.info(
            "트레일링 스톱: %s 고점 %s → 현재 %s (기준 %s) %+.2f%% → 전량 매도",
            position.code, f"{max(getattr(position, 'peak_price', 0.0), position.current_price):,.0f}",
            f"{position.current_price:,.0f}", f"{stop:,.0f}", position.pnl_pct,
        )
        return "TRAILING_STOP"

    # -- 주문 수량 --------------------------------------------------------- #

    def buy_amount(self, weight_pct: int, portfolio: PortfolioState) -> float:
        """목표 비중과 가용 현금 중 작은 쪽."""
        target = self.risk.total_investment_cap_krw * min(weight_pct, self.risk.max_position_pct) / 100
        return max(min(target, portfolio.cash), 0.0)

    def buy_quantity(self, amount_krw: float, price: float) -> int:
        if price <= 0:
            return 0
        return int(math.floor(amount_krw / price))
