"""이번 달에 얼마 썼는지 세고, 상한을 넘으면 막는다.

지금까지 방어선은 **실행 1회당 상한**(`cost.hard_cap_usd`)뿐이었다. 한 번에
$25 를 넘기지 못하게 막을 뿐, 하루 $2 씩 서른 번이면 $60 이 나가도 아무도
막지 않는다. 실제로 "비용이 너무 부담된다" 는 말이 나온 자리다.

그래서 **달 단위 상한**을 둔다. 이번 달 쓴 돈 + 이번에 쓸 돈이 상한을 넘으면
`--yes` 가 있어도 시작하지 않는다.

쓴 돈은 `runs/{run_id}/state.json` 의 `cost_usd` 를 더해서 센다. run_id 가
`YYYYMMDD_HHMMSS` 라서 폴더 이름만 봐도 어느 달인지 알 수 있다 — 파일을 열지
않고 먼저 걸러내므로 실행이 수백 개여도 빠르다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_RUN_ID = re.compile(r"^(\d{4})(\d{2})\d{2}_\d{6}")


@dataclass
class Budget:
    """이번 달 예산 현황."""

    month: str                  # "2026-08"
    cap: float                  # 0 이면 상한 없음
    spent: float
    videos: int

    @property
    def left(self) -> float | None:
        return round(self.cap - self.spent, 2) if self.cap > 0 else None

    @property
    def used_pct(self) -> int | None:
        if self.cap <= 0:
            return None
        return min(999, round(self.spent / self.cap * 100))

    def allows(self, amount: float) -> bool:
        """이만큼 더 써도 되는가."""
        return self.cap <= 0 or (self.spent + amount) <= self.cap + 1e-9

    def as_dict(self) -> dict:
        return {"month": self.month, "cap": self.cap, "spent": round(self.spent, 2),
                "videos": self.videos, "left": self.left, "used_pct": self.used_pct}


def month_key(when: date | None = None) -> str:
    d = when or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def spent_in(runs_dir: Path, month: str | None = None) -> tuple[float, int]:
    """(그 달에 쓴 돈, 편수). 폴더 이름으로 먼저 거르고 state.json 을 읽는다."""
    month = month or month_key()
    root = Path(runs_dir)
    if not root.is_dir():
        return 0.0, 0

    total, count = 0.0, 0
    for d in root.iterdir():
        if not d.is_dir():
            continue
        m = _RUN_ID.match(d.name)
        if not m or f"{m.group(1)}-{m.group(2)}" != month:
            continue
        sp = d / "state.json"
        if not sp.exists():
            continue
        try:
            cost = json.loads(sp.read_text(encoding="utf-8")).get("cost_usd")
        except (json.JSONDecodeError, OSError):
            continue
        try:
            value = float(cost or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            total += value
            count += 1
    return round(total, 4), count


def load(cfg, runs_dir: Path, *, when: date | None = None) -> Budget:
    """config 의 상한과 이번 달 실적을 묶어 돌려준다."""
    month = month_key(when)
    spent, videos = spent_in(runs_dir, month)
    try:
        cap = float(cfg.cost_cfg.get("monthly_cap_usd", 0) or 0)
    except (TypeError, ValueError):
        cap = 0.0
    return Budget(month=month, cap=max(0.0, cap), spent=spent, videos=videos)


def blocked_message(budget: Budget, amount: float) -> str | None:
    """이만큼 더 쓰면 상한을 넘는가. 넘으면 사람이 읽을 이유를, 아니면 None."""
    if budget.allows(amount):
        return None
    return (
        f"이번 달({budget.month}) 상한 ${budget.cap:.2f} 를 넘습니다.\n"
        f"  지금까지 {budget.videos}편에 ${budget.spent:.2f} 를 썼고, "
        f"이번에 ${amount:.2f} 가 더 듭니다 "
        f"(합계 ${budget.spent + amount:.2f}).\n"
        f"  다음 달까지 기다리거나, config.yaml 의 cost.monthly_cap_usd 를 "
        f"올리세요. 0 으로 두면 상한 없이 씁니다."
    )


def warn_message(budget: Budget, amount: float, *, at: float = 0.8) -> str | None:
    """상한에 가까워졌을 때의 알림. 막지는 않는다."""
    if budget.cap <= 0 or not budget.allows(amount):
        return None
    after = budget.spent + amount
    if after < budget.cap * at:
        return None
    return (f"이번 달 ${after:.2f} / ${budget.cap:.2f} "
            f"(남은 예산 ${budget.cap - after:.2f})")
