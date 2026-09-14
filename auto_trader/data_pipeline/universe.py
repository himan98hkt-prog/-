"""매매 대상 종목(유니버스) 생성.

- `watchlist` 모드: yaml 리스트를 그대로 사용.
- `volume_rank` 모드: 거래량 상위 N개 → 종목명 키워드·최소가 필터.
  (모의투자 도메인은 거래량 순위 API를 제공하지 않으므로 watchlist로 폴백)
- **보유 종목은 모드와 무관하게 항상 포함**한다 — 매도 판단을 해야 하기 때문.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from config.loader import Settings
from trading.kis_api import Balance, KisApi, KisApiError
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("universe")


def is_excluded(name: str, keywords: Iterable[str]) -> bool:
    """종목명 기준 제외 판정.

    한 글자 키워드('우')는 우선주 접미사로만 취급한다 —
    '우리금융지주'처럼 이름에 포함만 된 종목을 걸러내지 않기 위함이다.
    """
    if not name:
        return False
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        if len(keyword) == 1:
            if name.endswith(keyword) or name.endswith(f"{keyword}B"):
                return True
        elif keyword.lower() in name.lower():
            return True
    return False


def _held_codes(balance: Balance | None) -> list[str]:
    if balance is None:
        return []
    return [holding.code for holding in balance.holdings if holding.qty > 0]


def _from_volume_rank(api: KisApi, settings: Settings) -> list[dict[str, Any]]:
    universe_cfg = settings.universe
    ranked = api.get_volume_rank(universe_cfg.volume_rank_top_n)
    picked: list[dict[str, Any]] = []
    for row in ranked:
        code, name, price = row["code"], row["name"], row["price"]
        if not code:
            continue
        if is_excluded(name, universe_cfg.exclude_keywords):
            logger.debug("제외(키워드): %s(%s)", name, code)
            continue
        if price < universe_cfg.min_price:
            logger.debug("제외(최소가 %d원 미만): %s(%s) %d원", universe_cfg.min_price, name, code, price)
            continue
        picked.append(row)
    return picked


def build_universe(
    api: KisApi,
    settings: Settings,
    *,
    balance: Balance | None = None,
    save: bool = True,
    now: datetime | None = None,
) -> list[str]:
    """이번 사이클에서 분석할 종목코드 리스트를 만든다(보유 종목 우선)."""
    universe_cfg = settings.universe
    timestamp = now or datetime.now(KST)
    holdings = _held_codes(balance)

    candidates: list[str] = []
    source = universe_cfg.mode
    details: list[dict[str, Any]] = []

    if universe_cfg.mode == "volume_rank":
        try:
            details = _from_volume_rank(api, settings)
            candidates = [row["code"] for row in details]
        except KisApiError as exc:
            logger.warning("거래량 순위 조회 실패(%s) — watchlist 로 폴백합니다", exc)
            source = "watchlist(fallback)"
            candidates = list(universe_cfg.watchlist)
    else:
        candidates = list(universe_cfg.watchlist)

    # 후보 수 제한은 AI 호출 비용 통제용 — 보유 종목에는 적용하지 않는다.
    limited = candidates[: universe_cfg.max_candidates_per_cycle]

    ordered: list[str] = []
    for code in [*holdings, *limited]:  # 보유 종목을 앞에 둔다
        if code and code not in ordered:
            ordered.append(code)

    logger.info(
        "유니버스 %d종목 (모드: %s / 보유 %d + 후보 %d, 후보 상한 %d)",
        len(ordered), source, len(holdings), len(limited), universe_cfg.max_candidates_per_cycle,
    )

    if save:
        _save_universe(settings.paths["data"], ordered, holdings, source, details, timestamp)
    return ordered


def _save_universe(
    data_dir: Path,
    codes: list[str],
    holdings: list[str],
    source: str,
    details: list[dict[str, Any]],
    timestamp: datetime,
) -> Path:
    path = Path(data_dir) / f"universe_{timestamp:%Y%m%d}.json"
    payload = {
        "generated_at": timestamp.isoformat(timespec="seconds"),
        "source": source,
        "codes": codes,
        "holdings": holdings,
        "details": details,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("유니버스 저장: %s", path)
    return path
