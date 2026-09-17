"""대시보드가 읽는 조회 함수 모음 (전부 읽기 전용)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from types import SimpleNamespace

from utils.db import connect, get_bot_state, read_peaks

KST = ZoneInfo("Asia/Seoul")


def _rows(db_path: Path | str, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def overview(db_path: Path | str, *, now: datetime | None = None) -> dict[str, Any]:
    """상단 요약 타일 값."""
    moment = now or datetime.now(KST)
    today = moment.strftime("%Y-%m-%d")

    positions = _rows(db_path, "SELECT * FROM positions ORDER BY pnl_pct DESC")
    pnl = _rows(db_path, "SELECT * FROM daily_pnl WHERE date = ?", (today,))
    state = get_bot_state(db_path)

    # 거부된 주문은 '오늘 주문' 에 세지 않는다 — 체결되지도, 접수되지도 않았다.
    orders_today = _rows(
        db_path,
        """SELECT side, status, dry_run FROM orders
           WHERE substr(created_at, 1, 10) = ? AND status != 'REJECTED'""",
        (today,),
    )
    rejected_today = _rows(
        db_path,
        """SELECT COUNT(*) n FROM orders
           WHERE substr(created_at, 1, 10) = ? AND status = 'REJECTED'""",
        (today,),
    )[0]["n"]
    cost = _rows(
        db_path,
        """SELECT COALESCE(SUM(cost_usd), 0) total, COALESCE(SUM(input_tokens), 0) input,
                  COALESCE(SUM(output_tokens), 0) output, COUNT(*) calls,
                  COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) failures
           FROM ai_usage WHERE substr(created_at, 1, 10) = ?""",
        (today,),
    )[0]

    eval_amount = sum(float(p["eval_amount"] or 0) for p in positions)
    pnl_amount = sum(float(p["pnl_amount"] or 0) for p in positions)

    return {
        "date": today,
        "state": state,
        "position_count": len(positions),
        "eval_amount": eval_amount,
        "unrealized_pnl": pnl_amount,
        "end_equity": float(pnl[0]["end_equity"]) if pnl else 0.0,
        "start_equity": float(pnl[0]["start_equity"]) if pnl else 0.0,
        "daily_pnl_pct": float(pnl[0]["total_pnl_pct"]) if pnl else 0.0,
        "buy_count": sum(1 for o in orders_today if o["side"] == "BUY"),
        "sell_count": sum(1 for o in orders_today if o["side"] == "SELL"),
        "dry_run_orders": sum(1 for o in orders_today if o["dry_run"] == 1),
        "rejected_orders": int(rejected_today),
        "ai_cost_usd": float(cost["total"]),
        "ai_calls": int(cost["calls"]),
        "ai_failures": int(cost["failures"]),
        "ai_tokens": int(cost["input"]) + int(cost["output"]),
    }


def positions(db_path: Path | str, stop_loss_pct: float, take_profit_pct: float,
              risk: Any | None = None) -> list[dict[str, Any]]:
    """보유 종목 + 손절·익절선까지 남은 거리. 트레일링이 켜져 있으면 기준선도."""
    from logic.risk_manager import RiskManager

    peaks = read_peaks(db_path)
    trailing_on = bool(risk and getattr(risk, "trailing_stop_pct", 0) > 0)
    result = []
    for row in _rows(db_path, "SELECT * FROM positions ORDER BY pnl_pct DESC"):
        pnl_pct = float(row["pnl_pct"] or 0)
        row["to_stop_loss"] = round(pnl_pct - stop_loss_pct, 2)
        row["to_take_profit"] = round(take_profit_pct - pnl_pct, 2)
        row["danger"] = pnl_pct <= stop_loss_pct + 1.0  # 손절선 1%p 이내
        row["peak_price"] = peaks.get(row["code"], 0.0)
        row["trailing_stop"] = 0.0
        if trailing_on:
            # 화면에 보이는 기준선이 실제 청산 기준과 같아야 한다 — 같은 함수를 쓴다.
            row["trailing_stop"] = RiskManager.trailing_stop_price(
                SimpleNamespace(risk=risk),
                SimpleNamespace(avg_price=float(row["avg_price"] or 0),
                                current_price=float(row["current_price"] or 0),
                                peak_price=row["peak_price"]),
            )
        result.append(row)
    return result


def recent_decisions(db_path: Path | str, limit: int = 30) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT cycle_id, code, name, holding, claude_action, claude_confidence, claude_ok,
                  gemini_action, gemini_confidence, gemini_ok,
                  chatgpt_action, chatgpt_confidence, chatgpt_ok,
                  final_action, final_weight_pct,
                  final_reason, forced_exit, risk_passed, risk_reason, created_at
           FROM decisions ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def recent_orders(db_path: Path | str, limit: int = 20) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT code, name, side, order_type, qty, price, filled_qty, filled_price,
                  status, dry_run, reason, error, created_at
           FROM orders ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def equity_series(db_path: Path | str, days: int = 30) -> list[dict[str, Any]]:
    """일자별 자산·손익률 (차트용, 오래된 순)."""
    rows = _rows(
        db_path,
        """SELECT date, start_equity, end_equity, total_pnl_pct
           FROM daily_pnl ORDER BY date DESC LIMIT ?""",
        (days,),
    )
    return list(reversed(rows))


def ai_cost_series(db_path: Path | str, days: int = 14) -> list[dict[str, Any]]:
    return list(reversed(_rows(
        db_path,
        """SELECT substr(created_at, 1, 10) date, SUM(cost_usd) cost, COUNT(*) calls
           FROM ai_usage GROUP BY 1 ORDER BY 1 DESC LIMIT ?""",
        (days,),
    )))


def decision_mix(db_path: Path | str, *, now: datetime | None = None) -> dict[str, int]:
    """당일 최종 결정 분포."""
    today = (now or datetime.now(KST)).strftime("%Y-%m-%d")
    rows = _rows(
        db_path,
        """SELECT final_action, COUNT(*) n FROM decisions
           WHERE substr(created_at, 1, 10) = ? GROUP BY 1 ORDER BY n DESC""",
        (today,),
    )
    return {row["final_action"]: row["n"] for row in rows}


def recent_risk_blocks(db_path: Path | str, limit: int = 8) -> list[dict[str, Any]]:
    return _rows(
        db_path,
        """SELECT code, name, risk_reason, created_at FROM decisions
           WHERE risk_passed = 0 AND risk_reason != '' ORDER BY id DESC LIMIT ?""",
        (limit,),
    )


def log_tail(log_dir: Path | str, lines: int = 40, prefix: str = "trader") -> list[str]:
    """오늘 로그의 마지막 N줄. prefix 로 매매(trader)·대시보드(dashboard)를 고른다."""
    path = Path(log_dir) / f"{prefix}_{datetime.now(KST):%Y%m%d}.log"
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-lines:]


def benchmark_comparison(db_path: Path | str) -> dict[str, Any]:
    """자동매매 성적 vs 감시 종목을 그냥 사서 들고만 있었을 때.

    벤치마크는 **첫날 관측된 종목들에 똑같이 나눠 담고 그대로 둔** 포트폴리오다.
    동일 비중이므로 수익률은 종목별 수익률의 평균과 같아, 주식 수를 따로
    들고 있을 필요가 없다. 나중에 감시 목록에 추가된 종목은 시작 가격이 없어
    제외한다 — 넣으면 '오른 뒤에 담은' 셈이 되어 벤치마크가 유리해진다.
    """
    empty = {"ready": False, "reason": "", "start_date": "", "days": 0,
             "codes": 0, "benchmark_pct": 0.0, "actual_pct": 0.0, "edge_pct": 0.0,
             "legs": []}
    conn = connect(db_path)
    try:
        dates = [row["date"] for row in conn.execute(
            "SELECT DISTINCT date FROM benchmark_prices ORDER BY date")]
        if not dates:
            empty["reason"] = "아직 기록이 없습니다 — 첫 사이클이 돌면 쌓입니다"
            return empty
        first, last = dates[0], dates[-1]
        if first == last:
            empty["reason"] = "거래일 2일치가 쌓이면 비교가 표시됩니다"
            empty["start_date"] = first
            return empty

        start = {row["code"]: row for row in conn.execute(
            "SELECT code, name, price FROM benchmark_prices WHERE date = ?", (first,))}
        end = {row["code"]: row["price"] for row in conn.execute(
            "SELECT code, price FROM benchmark_prices WHERE date = ?", (last,))}

        legs = []
        for code, row in start.items():
            if code not in end or not row["price"]:
                continue  # 마지막 날 값이 없으면 비교가 성립하지 않는다
            change = (end[code] / row["price"] - 1) * 100
            legs.append({"code": code, "name": row["name"] or code,
                         "pct": round(change, 2)})
        if not legs:
            empty["reason"] = "비교할 종목이 없습니다"
            empty["start_date"] = first
            return empty
        legs.sort(key=lambda leg: leg["pct"], reverse=True)
        benchmark_pct = sum(leg["pct"] for leg in legs) / len(legs)

        # 실제 성적: 첫날 시작 자산 대비 마지막으로 기록된 평가 자산.
        rows = list(conn.execute(
            """SELECT date, start_equity, end_equity FROM daily_pnl
               WHERE date >= ? ORDER BY date""", (first,)))
    finally:
        conn.close()

    opening = next((float(r["start_equity"]) for r in rows if r["start_equity"]), 0.0)
    closing = next((float(r["end_equity"]) for r in reversed(rows) if r["end_equity"]), 0.0)
    actual_pct = ((closing / opening - 1) * 100) if opening > 0 else 0.0

    return {
        "ready": True, "reason": "", "start_date": first, "end_date": last,
        "days": len(dates), "codes": len(legs),
        "benchmark_pct": round(benchmark_pct, 2),
        "actual_pct": round(actual_pct, 2),
        "edge_pct": round(actual_pct - benchmark_pct, 2),
        "legs": legs,
    }


# --- 매매 성적 --------------------------------------------------------------- #

# 왕복 거래비용 추정. 실제 체결가에 이미 반영된 슬리피지는 빼고, 명시적으로
# 빠져나가는 돈만 센다 — 증권사 수수료(양방향)와 매도 시 증권거래세.
BROKER_FEE_PCT = 0.015     # 편도, %
SELL_TAX_PCT = 0.15        # 매도 시, %


def _net_pnl_pct(entry: float, exit_price: float) -> float:
    """수수료·세금을 뺀 실질 수익률(%)."""
    if entry <= 0:
        return 0.0
    gross = (exit_price / entry - 1) * 100
    return gross - (BROKER_FEE_PCT * 2 + SELL_TAX_PCT)


def closed_trades(db_path: Path | str) -> list[dict[str, Any]]:
    """체결된 주문을 종목별 선입선출로 짝지어 '닫힌 거래' 목록을 만든다.

    주문 기록만으로 계산하므로 별도 테이블이 없다 — 주문과 어긋날 일이 없다.
    부분 매도는 산 물량을 앞에서부터 덜어내는 방식으로 처리한다.
    """
    rows = _rows(
        db_path,
        """SELECT code, name, side, filled_qty, filled_price, created_at
           FROM orders
           WHERE status = 'FILLED' AND filled_qty > 0 AND filled_price > 0
           ORDER BY id""",
    )
    open_lots: dict[str, list[dict[str, Any]]] = {}
    trades: list[dict[str, Any]] = []

    for row in rows:
        code = row["code"]
        if row["side"] == "BUY":
            open_lots.setdefault(code, []).append(
                {"qty": int(row["filled_qty"]), "price": float(row["filled_price"]),
                 "at": row["created_at"], "name": row["name"] or code}
            )
            continue

        remaining = int(row["filled_qty"])
        lots = open_lots.get(code, [])
        while remaining > 0 and lots:
            lot = lots[0]
            matched = min(remaining, lot["qty"])
            entry, exit_price = lot["price"], float(row["filled_price"])
            trades.append({
                "code": code, "name": lot["name"], "qty": matched,
                "entry_price": entry, "exit_price": exit_price,
                "entry_at": lot["at"], "exit_at": row["created_at"],
                "pnl_pct": round(_net_pnl_pct(entry, exit_price), 2),
                "pnl_amount": round((exit_price - entry) * matched
                                    - (entry + exit_price) * matched
                                    * (BROKER_FEE_PCT + SELL_TAX_PCT / 2) / 100),
                "held_days": _days_between(lot["at"], row["created_at"]),
            })
            lot["qty"] -= matched
            remaining -= matched
            if lot["qty"] <= 0:
                lots.pop(0)
    trades.reverse()  # 최근 것부터
    return trades


def _days_between(start: str, end: str) -> int:
    try:
        opened = datetime.fromisoformat(start)
        closed = datetime.fromisoformat(end)
    except (TypeError, ValueError):
        return 0
    return max((closed.date() - opened.date()).days, 0)


def trade_stats(db_path: Path | str) -> dict[str, Any]:
    """승률·손익비·평균 보유일. 개선할 지점을 여기서 찾는다."""
    trades = closed_trades(db_path)
    blank = {"ready": False, "count": 0, "win_rate": 0.0, "avg_win": 0.0,
             "avg_loss": 0.0, "payoff": 0.0, "avg_days": 0.0,
             "realized_krw": 0, "fee_krw": 0, "breakeven_win_rate": 0.0,
             "trades": []}
    if not trades:
        return blank

    wins = [t["pnl_pct"] for t in trades if t["pnl_pct"] > 0]
    losses = [t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    # 손익비: 평균 이익 / 평균 손실 크기. 이 값이 클수록 낮은 승률로도 버틴다.
    payoff = (avg_win / abs(avg_loss)) if avg_loss else 0.0
    # 본전 승률 = 1 / (1 + 손익비). 실제 승률이 이보다 낮으면 잃고 있는 것이다.
    breakeven = (1 / (1 + payoff) * 100) if payoff else 0.0

    fee = sum(
        (t["entry_price"] + t["exit_price"]) * t["qty"]
        * (BROKER_FEE_PCT + SELL_TAX_PCT / 2) / 100
        for t in trades
    )
    return {
        "ready": True,
        "count": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff": round(payoff, 2),
        "breakeven_win_rate": round(breakeven, 1),
        "avg_days": round(sum(t["held_days"] for t in trades) / len(trades), 1),
        "realized_krw": round(sum(t["pnl_amount"] for t in trades)),
        "fee_krw": round(fee),
        "trades": trades[:15],
    }


# --- 매수 사유 --------------------------------------------------------------- #

def buy_rationale(db_path: Path | str, codes: list[str]) -> dict[str, dict[str, Any]]:
    """보유 종목별 '왜 샀는지'. 매수 주문 직전의 판단을 찾아 온다.

    사유는 이미 decisions 에 쌓여 있었는데 화면에 내보내지 않고 있었다.
    무엇을 근거로 내 돈이 들어갔는지 볼 수 없으면 신뢰할 수가 없다.
    """
    if not codes:
        return {}
    result: dict[str, dict[str, Any]] = {}
    conn = connect(db_path)
    try:
        for code in codes:
            # 가장 최근 매수 체결 시각을 찾고, 그 시각 이전의 마지막 매수 판단을 붙인다.
            bought = conn.execute(
                """SELECT created_at, filled_price, filled_qty FROM orders
                   WHERE code = ? AND side = 'BUY' AND filled_qty > 0
                   ORDER BY id DESC LIMIT 1""", (code,)).fetchone()
            if bought is None:
                continue
            row = conn.execute(
                """SELECT created_at, final_action, final_reason,
                          claude_action, claude_confidence, claude_reason,
                          gemini_action, gemini_confidence, gemini_reason,
                          chatgpt_action, chatgpt_confidence, chatgpt_reason
                   FROM decisions
                   WHERE code = ? AND created_at <= ?
                   ORDER BY id DESC LIMIT 1""", (code, bought["created_at"])).fetchone()
            if row is None:
                continue
            engines = [
                {"name": label, "action": row[f"{key}_action"],
                 "confidence": row[f"{key}_confidence"], "reason": row[f"{key}_reason"]}
                for key, label in (("claude", "Claude"), ("gemini", "Gemini"),
                                   ("chatgpt", "ChatGPT"))
                if row[f"{key}_action"]
            ]
            result[code] = {
                "bought_at": bought["created_at"],
                "bought_price": float(bought["filled_price"]),
                "bought_qty": int(bought["filled_qty"]),
                "final_action": row["final_action"],
                "final_reason": row["final_reason"] or "",
                "engines": engines,
            }
    finally:
        conn.close()
    return result


# --- 테마별 성과 ------------------------------------------------------------- #

def theme_performance(db_path: Path | str, themes: dict[str, str]) -> list[dict[str, Any]]:
    """테마별 등락. 한 테마가 통째로 밀리면 종목 문제가 아니라 업황 문제다.

    사이클이 적어 둔 관측가를 그대로 쓰므로 추가 조회가 없다.
    """
    if not themes:
        return []
    conn = connect(db_path)
    try:
        dates = [r["date"] for r in conn.execute(
            "SELECT DISTINCT date FROM benchmark_prices ORDER BY date")]
        if len(dates) < 2:
            return []
        first, last = dates[0], dates[-1]
        prev = dates[-2]
        rows = {}
        for label, day in (("start", first), ("prev", prev), ("now", last)):
            rows[label] = {r["code"]: (r["price"], r["name"])
                           for r in conn.execute(
                               "SELECT code, name, price FROM benchmark_prices WHERE date = ?",
                               (day,))}
    finally:
        conn.close()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for code, theme in themes.items():
        start, now = rows["start"].get(code), rows["now"].get(code)
        if not start or not now or start[0] <= 0:
            continue
        previous = rows["prev"].get(code)
        grouped.setdefault(theme or "기타", []).append({
            "code": code, "name": now[1] or code,
            "since_start": (now[0] / start[0] - 1) * 100,
            "since_prev": ((now[0] / previous[0] - 1) * 100
                           if previous and previous[0] > 0 else 0.0),
        })

    result = [
        {"theme": theme,
         "codes": len(legs),
         "since_start": round(sum(l["since_start"] for l in legs) / len(legs), 2),
         "since_prev": round(sum(l["since_prev"] for l in legs) / len(legs), 2),
         "legs": sorted(legs, key=lambda l: l["since_start"], reverse=True)}
        for theme, legs in grouped.items()
    ]
    result.sort(key=lambda row: row["since_start"], reverse=True)
    return result


# --- 엔진별 적중률 ----------------------------------------------------------- #

ENGINES = (("claude", "Claude"), ("gemini", "Gemini"), ("chatgpt", "ChatGPT"))
ACCURACY_HORIZON_DAYS = 5   # 판단 이후 며칠 뒤 가격으로 채점할지 (단기 스윙 기준)


def engine_accuracy(db_path: Path | str,
                    horizon_days: int = ACCURACY_HORIZON_DAYS) -> dict[str, Any]:
    """엔진별 방향 적중률. 세 곳에 매달 돈을 쓰는데 어디가 값을 하는지 보려는 칸.

    판단한 날의 가격과 `horizon_days` 거래일 뒤 가격을 비교해, BUY 는 올랐으면
    적중, SELL 은 내렸으면 적중으로 센다. HOLD 는 방향을 주장하지 않으므로
    **적중률에서 제외**하고 횟수만 센다 — 넣으면 관망만 하는 엔진이 좋아 보인다.

    아직 채점할 미래가 없는 최근 판단은 세지 않는다.
    """
    conn = connect(db_path)
    try:
        dates = [row["date"] for row in conn.execute(
            "SELECT DISTINCT date FROM benchmark_prices ORDER BY date")]
        prices: dict[tuple[str, str], float] = {
            (row["date"], row["code"]): float(row["price"])
            for row in conn.execute("SELECT date, code, price FROM benchmark_prices")
        }
        rows = _rows(
            db_path,
            """SELECT code, created_at, claude_action, gemini_action, chatgpt_action
               FROM decisions WHERE forced_exit IS NULL OR forced_exit = ''""",
        )
    finally:
        conn.close()

    index = {date: position for position, date in enumerate(dates)}
    tally = {key: {"name": label, "calls": 0, "hits": 0, "holds": 0, "graded": 0}
             for key, label in ENGINES}

    for row in rows:
        day = (row["created_at"] or "")[:10]
        later = index.get(day, -1) + horizon_days
        if day not in index or later >= len(dates):
            continue  # 아직 채점할 미래가 없다
        start = prices.get((day, row["code"]))
        end = prices.get((dates[later], row["code"]))
        if not start or not end:
            continue
        rose = end > start

        for key, _label in ENGINES:
            action = (row[f"{key}_action"] or "").upper()
            if not action:
                continue
            tally[key]["calls"] += 1
            if action == "HOLD":
                tally[key]["holds"] += 1
                continue
            tally[key]["graded"] += 1
            if (action == "BUY" and rose) or (action == "SELL" and not rose):
                tally[key]["hits"] += 1

    engines = []
    for key, _label in ENGINES:
        row = tally[key]
        if not row["calls"]:
            continue
        engines.append({
            "engine": row["name"],
            "calls": row["calls"],
            "graded": row["graded"],
            "holds": row["holds"],
            "hit_rate": round(row["hits"] / row["graded"] * 100, 1) if row["graded"] else 0.0,
            "hold_rate": round(row["holds"] / row["calls"] * 100, 1),
        })
    engines.sort(key=lambda row: row["hit_rate"], reverse=True)
    return {
        "ready": any(row["graded"] for row in engines),
        "horizon_days": horizon_days,
        "engines": engines,
    }
