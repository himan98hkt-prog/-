"""사용량 · 비용 · 크레딧 원장.

Master Guard 11번: *실패한 렌더, 공급자 장애, 중복 작업이 사용자 크레딧을 소모하지
않게 설계한다.* 그걸 보장하는 구조가 이 파일이다.

    submit   → reserve   (잔액 → 예약, 총액 불변)
    성공     → commit    (예약 소멸, 실제 차감)
    실패/취소 → release   (예약 → 잔액, 총액 불변)
    중복     → reserve 자체를 하지 않는다

``credit_ledger`` 에 ``UNIQUE (job_id, entry_type)`` 이 걸려 있어서, 재시도나
경쟁 상태로 commit 이 두 번 들어와도 두 번 차감되지 않는다.

금액 단위
---------
- credit : 정수. 서비스 내부 단위.
- micro_usd : 정수. 1 USD = 1_000_000. 실제 공급자 원가 추적용이며 **청구와 무관**하다
  (결제는 Phase 7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from autoshorts.utils import get_logger

from .auth import new_id
from .db import Database

__all__ = [
    "Ledger",
    "InsufficientCredits",
    "CreditState",
    "MICRO_USD",
    "estimate_job_credits",
]

LOG = get_logger("saas.ledger")

MICRO_USD = 1_000_000

# 렌더 1초당 크레딧. Phase 7 에서 요금제와 함께 재조정한다.
CREDITS_PER_OUTPUT_SECOND = 1
MIN_JOB_CREDITS = 10


def estimate_job_credits(
    *, source_seconds: float | None, max_clips: int, max_clip_seconds: float
) -> int:
    """작업 전 예약할 크레딧.

    아직 결과 길이를 모르므로 **최대치**로 잡는다. 남는 만큼은 commit 때 돌려준다.
    부족하게 잡으면 실행 도중 잔액이 마이너스가 되는데, 그건 복구가 어렵다.
    """
    ceiling = max(1, int(max_clips)) * max(1.0, float(max_clip_seconds))
    if source_seconds and source_seconds > 0:
        ceiling = min(ceiling, float(source_seconds))
    return max(MIN_JOB_CREDITS, int(round(ceiling * CREDITS_PER_OUTPUT_SECOND)))


class InsufficientCredits(RuntimeError):
    """예약할 잔액이 모자란다."""


@dataclass(frozen=True)
class CreditState:
    balance: int
    reserved: int

    @property
    def available(self) -> int:
        return self.balance


def _jsonb(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


class Ledger:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ── 크레딧 ─────────────────────────────────────────────
    def state(self, workspace_id: str) -> CreditState:
        row = self.db.fetch_one(
            "SELECT credit_balance, credit_reserved FROM workspaces WHERE id = %s",
            (workspace_id,),
        )
        if not row:
            raise LookupError("워크스페이스를 찾을 수 없습니다.")
        return CreditState(balance=int(row["credit_balance"]), reserved=int(row["credit_reserved"]))

    def grant(self, workspace_id: str, amount: int, reason: str = "") -> CreditState:
        amount = int(amount)
        if amount <= 0:
            raise ValueError("지급액은 양수여야 합니다.")
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE workspaces SET credit_balance = credit_balance + %s WHERE id = %s "
                "RETURNING credit_balance, credit_reserved",
                (amount, workspace_id),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError("워크스페이스를 찾을 수 없습니다.")
            self._write(cur, workspace_id, None, "grant", amount, row[0], row[1], reason)
        return CreditState(int(row[0]), int(row[1]))

    def reserve(self, workspace_id: str, job_id: str, amount: int, reason: str = "") -> CreditState:
        """잔액에서 예약으로 옮긴다. 모자라면 :class:`InsufficientCredits`.

        ``credit_balance >= amount`` 를 UPDATE 의 WHERE 에 넣는다. 읽고-확인하고-쓰면
        동시 요청 두 개가 같은 잔액을 보고 둘 다 통과한다.
        """
        amount = int(amount)
        if amount <= 0:
            raise ValueError("예약액은 양수여야 합니다.")
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE workspaces SET credit_balance = credit_balance - %s, "
                "  credit_reserved = credit_reserved + %s "
                "WHERE id = %s AND credit_balance >= %s "
                "RETURNING credit_balance, credit_reserved",
                (amount, amount, workspace_id, amount),
            )
            row = cur.fetchone()
            if row is None:
                state = self.state(workspace_id)  # 워크스페이스가 없으면 여기서 LookupError
                raise InsufficientCredits(
                    f"크레딧이 부족합니다. 필요: {amount}, 잔액: {state.balance}"
                )
            self._write(cur, workspace_id, job_id, "reserve", -amount, row[0], row[1], reason)
        return CreditState(int(row[0]), int(row[1]))

    def commit(
        self, workspace_id: str, job_id: str, *, reserved: int, actual: int, reason: str = ""
    ) -> CreditState:
        """예약분을 실제 소모로 확정한다. 남는 예약은 잔액으로 돌려준다."""
        reserved, actual = int(reserved), max(0, int(actual))
        actual = min(actual, reserved)  # 예약보다 더 걷지 않는다
        refund = reserved - actual
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE workspaces SET credit_reserved = credit_reserved - %s, "
                "  credit_balance = credit_balance + %s WHERE id = %s "
                "RETURNING credit_balance, credit_reserved",
                (reserved, refund, workspace_id),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError("워크스페이스를 찾을 수 없습니다.")
            self._write(cur, workspace_id, job_id, "commit", -actual, row[0], row[1], reason)
        return CreditState(int(row[0]), int(row[1]))

    def release(self, workspace_id: str, job_id: str, amount: int, reason: str = "") -> CreditState:
        """실패·취소 시 예약을 전액 되돌린다."""
        amount = int(amount)
        if amount <= 0:
            return self.state(workspace_id)
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE workspaces SET credit_reserved = credit_reserved - %s, "
                "  credit_balance = credit_balance + %s WHERE id = %s "
                "RETURNING credit_balance, credit_reserved",
                (amount, amount, workspace_id),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError("워크스페이스를 찾을 수 없습니다.")
            self._write(cur, workspace_id, job_id, "release", amount, row[0], row[1], reason)
        return CreditState(int(row[0]), int(row[1]))

    def entries(self, workspace_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT id, job_id, entry_type, amount, balance_after, reserved_after, reason, created_at "
            "FROM credit_ledger WHERE workspace_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
            (workspace_id, max(1, min(int(limit), 500))),
        )

    @staticmethod
    def _write(cur, workspace_id, job_id, entry_type, amount, balance, reserved, reason) -> None:
        # 같은 (job_id, entry_type) 이 이미 있으면 조용히 무시한다. 재시도가
        # 원장을 두 번 쓰지 않게 하는 것이 목적이고, 잔액 UPDATE 는 위에서
        # 이미 조건부로 한 번만 일어난다.
        cur.execute(
            "INSERT INTO credit_ledger (id, workspace_id, job_id, entry_type, amount, "
            "  balance_after, reserved_after, reason) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (new_id("cl"), workspace_id, job_id, entry_type, int(amount),
             int(balance), int(reserved), (reason or "")[:500]),
        )

    # ── 사용량 · 원가 ───────────────────────────────────────
    def record_usage(
        self,
        workspace_id: str,
        *,
        event_type: str,
        quantity: float,
        unit: str = "",
        project_id: str | None = None,
        job_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_id("ue")
        self.db.execute(
            "INSERT INTO usage_events (id, workspace_id, project_id, job_id, user_id, "
            "  event_type, quantity, unit, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (event_id, workspace_id, project_id, job_id, user_id, event_type[:60],
             float(quantity), unit[:20], _jsonb(metadata)),
        )
        return event_id

    def record_cost(
        self,
        workspace_id: str,
        *,
        provider: str,
        resource: str,
        quantity: float,
        unit: str = "",
        micro_usd: int = 0,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_id("ce")
        self.db.execute(
            "INSERT INTO cost_events (id, workspace_id, job_id, provider, resource, "
            "  quantity, unit, micro_usd, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (event_id, workspace_id, job_id, provider[:60], resource[:60],
             float(quantity), unit[:20], int(micro_usd), _jsonb(metadata)),
        )
        return event_id

    def record_cost_events(
        self, workspace_id: str, job_id: str, events: Iterable[dict[str, Any]]
    ) -> int:
        """엔진이 돌려준 ``JobResult.cost_events`` 를 그대로 적재한다.

        엔진은 원가(달러)를 모른다. 수량만 남기고 단가는 Phase 7 에서 붙인다.
        """
        count = 0
        for event in events or []:
            # autoshorts.contracts.CostEvent 의 필드 이름(kind/units/unit_name)을
            # 원장 어휘(resource/quantity/unit)로 옮긴다.
            self.record_cost(
                workspace_id,
                provider=str(event.get("provider") or "engine"),
                resource=str(event.get("kind") or event.get("resource") or "unknown"),
                quantity=float(event.get("units", event.get("quantity", 0.0)) or 0.0),
                unit=str(event.get("unit_name") or event.get("unit") or ""),
                micro_usd=0,
                job_id=job_id,
                metadata={"detail": event.get("detail", ""), "at": event.get("at", "")},
            )
            count += 1
        return count

    def summary(self, workspace_id: str) -> dict[str, Any]:
        usage = self.db.fetch_all(
            "SELECT event_type, unit, SUM(quantity) AS total, COUNT(*) AS events "
            "FROM usage_events WHERE workspace_id = %s GROUP BY event_type, unit ORDER BY event_type",
            (workspace_id,),
        )
        cost = self.db.fetch_all(
            "SELECT provider, resource, unit, SUM(quantity) AS total, SUM(micro_usd) AS micro_usd "
            "FROM cost_events WHERE workspace_id = %s GROUP BY provider, resource, unit "
            "ORDER BY provider, resource",
            (workspace_id,),
        )
        state = self.state(workspace_id)
        return {
            "credits": {"balance": state.balance, "reserved": state.reserved},
            "usage": [{**row, "total": float(row["total"] or 0)} for row in usage],
            "cost": [
                {**row, "total": float(row["total"] or 0), "micro_usd": int(row["micro_usd"] or 0)}
                for row in cost
            ],
        }
