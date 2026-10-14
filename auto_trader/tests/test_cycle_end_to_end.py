"""운영 코드 그대로 사이클을 한 번 돌린다.

기존 통합 테스트(test_cycle_integration)는 사이클의 **순서를 흉내내** 검증한다.
그래서 main.py 가 바뀌면 조용히 어긋난다(실제로 scripts/test_cycle.py 가 그렇게
낡아 있었다). 여기서는 TradingBot.run_cycle() 자체를 부른다 — KIS 와 모델만
대역이고, 수집·상대평가·합의·리스크·주문·기록·알림은 전부 진짜 코드다.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import main as main_module
from agents.base_agent import BaseAgent
from main import TradingBot
from tests.conftest import FakeResponse
from tests.test_market_data import StubApi
from trading.kis_api import Balance, OrderResult, OrderStatus
from utils.db import connect

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 18, 11, 35, tzinfo=KST)
NAMES = {"005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차",
         "005490": "POSCO홀딩스", "051910": "LG화학", "207940": "삼성바이오",
         "105560": "KB금융", "015760": "한국전력", "035420": "NAVER",
         "012330": "현대모비스"}
WATCHLIST = list(NAMES)
WINNER = "000660"        # 이 종목만 전원 매수


class FakeKis(StubApi):
    """시세는 StubApi, 잔고·주문은 여기서."""

    def __init__(self, cash=10_000_000):
        super().__init__()
        self.cash = cash
        self.orders: list[dict] = []

    def get_current_price(self, code):
        return {**self.quote, "code": code, "name": NAMES.get(code, code)}

    def get_balance(self):
        return Balance(holdings=[], deposit=self.cash, orderable_cash=self.cash)

    def place_order(self, code, qty, side, price=0, order_type="limit"):
        self.orders.append({"code": code, "side": side, "qty": qty,
                            "price": price, "order_type": order_type})
        return OrderResult(order_no="0001", org_no="00", order_time="113500",
                           code=code, side=side, qty=qty, price=price,
                           order_type=order_type)

    def get_order_status(self, order_no):
        last = self.orders[-1]
        return OrderStatus(order_no=order_no, code=last["code"], name=last["code"],
                           side=last["side"], order_qty=last["qty"],
                           filled_qty=last["qty"], remain_qty=0,
                           filled_price=float(last["price"] or 176_628),
                           filled_amount=float(last["qty"] * (last["price"] or 176_628)),
                           status="체결")


class BatchAgent(BaseAgent):
    """상대평가 응답을 만들어 주는 대역. 호출 횟수를 센다."""

    def __init__(self, name, ai, *, winner=WINNER, confidence=0.8):
        super().__init__(ai)
        self.name = name
        self.model = f"{name}-test"
        self.winner = winner
        self.confidence = confidence
        self.batch_calls = 0
        self.single_calls = 0

    def _call_model(self, system_prompt, user_prompt, schema=None):
        codes = [c for c in WATCHLIST if f'"code": "{c}"' in user_prompt]
        if len(codes) > 1:
            self.batch_calls += 1
            return json.dumps({"picks": [self._pick(c) for c in codes]}, ensure_ascii=False)
        self.single_calls += 1
        return json.dumps(self._pick(codes[0] if codes else WATCHLIST[0]))

    def _pick(self, code):
        buy = code == self.winner
        return {"code": code, "action": "BUY" if buy else "HOLD",
                "confidence": self.confidence if buy else 0.3,
                "weight_pct": 20 if buy else 0,
                "reason": f"{code}: 10개 중 거래량 증가가 가장 뚜렷" if buy else "상대적으로 밀린다",
                "target_price": 0, "stop_loss_price": 0}


class Sent:
    """텔레그램 대역 — 보낸 본문을 그대로 모은다."""

    def __init__(self):
        self.messages: list[str] = []

    def post(self, url, json=None, timeout=None):
        self.messages.append((json or {}).get("text", ""))
        return FakeResponse({"ok": True})


@pytest.fixture
def bot(settings_obj, tmp_path, monkeypatch, request):
    dry_run = getattr(request, "param", True)
    settings = replace(
        settings_obj,
        env=replace(settings_obj.env, dry_run=dry_run, notifier="telegram",
                    telegram_bot_token="T", telegram_chat_id="1",
                    openai_api_key="sk-test"),   # 세 번째 엔진도 참여시킨다
        universe=replace(settings_obj.universe, watchlist=list(WATCHLIST)),
    )

    api = FakeKis()
    sent = Sent()
    monkeypatch.setattr(main_module, "TokenManager",
                        lambda env, path: SimpleNamespace(get_access_token=lambda **kw: "T"))
    monkeypatch.setattr(main_module, "KisApi", lambda env, auth: api)
    monkeypatch.setattr(main_module, "is_trading_day", lambda *a, **kw: True)
    monkeypatch.setattr("logic.portfolio.time.sleep", lambda *_: None)

    agents = [BatchAgent(name, settings.ai) for name in ("claude", "gemini", "chatgpt")]
    monkeypatch.setattr(main_module, "ClaudeAgent", lambda env, ai: agents[0])
    monkeypatch.setattr(main_module, "GeminiAgent", lambda env, ai: agents[1])
    monkeypatch.setattr(main_module, "OpenAiAgent", lambda env, ai: agents[2])

    instance = TradingBot(settings)
    instance.notifier.session = sent
    instance.api = api
    return SimpleNamespace(bot=instance, api=api, sent=sent, agents=agents,
                           db=settings.paths["db"])


def _rows(db, sql):
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


# --- 한 사이클이 끝까지 돈다 -------------------------------------------------- #

def test_ten_candidates_take_one_call_per_engine(bot, monkeypatch):
    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    bot.bot.run_cycle(label="11:35")

    for agent in bot.agents:
        assert agent.batch_calls == 1, f"{agent.name}: 후보를 한 번에 보지 않았습니다"
        assert agent.single_calls == 0, f"{agent.name}: 종목별로도 불렀습니다(중복 비용)"


def test_every_candidate_gets_a_recorded_decision(bot, monkeypatch):
    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    results = bot.bot.run_cycle(label="11:35")

    assert len(results) == len(WATCHLIST)
    rows = _rows(bot.db, "SELECT code, final_action, outcome FROM decisions")
    assert {r["code"] for r in rows} == set(WATCHLIST)
    winner = next(r for r in rows if r["code"] == WINNER)
    assert winner["final_action"] == "STRONG_BUY"


def test_dry_run_records_but_sends_nothing(bot, monkeypatch):
    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    bot.bot.run_cycle(label="11:35")

    assert bot.api.orders == [], "DRY_RUN 인데 주문 API 가 불렸습니다"
    winner = next(r for r in _rows(bot.db, "SELECT code, outcome FROM decisions")
                  if r["code"] == WINNER)
    assert "DRY_RUN" in (winner["outcome"] or ""), "왜 안 샀는지 기록이 없습니다"

    orders = _rows(bot.db, "SELECT code, status, dry_run FROM orders")
    assert [o["code"] for o in orders] == [WINNER]
    assert orders[0]["dry_run"] == 1


@pytest.mark.parametrize("bot", [False], indirect=True)
def test_with_dry_run_off_the_order_actually_goes_out(bot, monkeypatch):
    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    bot.bot.run_cycle(label="11:35")

    assert [o["code"] for o in bot.api.orders] == [WINNER], "실주문이 나가지 않았습니다"
    assert bot.api.orders[0]["side"] == "BUY"
    winner = next(r for r in _rows(bot.db, "SELECT code, outcome FROM decisions")
                  if r["code"] == WINNER)
    assert "DRY_RUN" not in (winner["outcome"] or "")


def test_the_phone_gets_one_readable_summary(bot, monkeypatch):
    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    bot.bot.run_cycle(label="11:35")

    summaries = [m for m in bot.sent.messages if m.startswith("📊")]
    assert len(summaries) == 1, "사이클당 요약은 한 번이어야 합니다"
    text = summaries[0]
    assert f"대상 {len(WATCHLIST)}종목" in text
    assert "STRONG_BUY" in text and NAMES[WINNER] in text
    assert "DRY_RUN" in text, "모의 기록인데 진짜 산 것처럼 보이면 안 됩니다"
    assert not [m for m in bot.sent.messages if m.startswith("⚠️")], "정상인데 오류를 알렸습니다"


def test_a_slow_quote_costs_one_stock_not_the_cycle(bot, monkeypatch):
    from trading.kis_api import KisApiError

    monkeypatch.setattr(main_module, "datetime", _fixed_datetime())
    real = bot.api.get_daily_ohlcv

    def flaky(code, *a, **kw):
        if code == "012330":
            raise KisApiError("daily_ohlcv 요청 실패: Read timed out")
        return real(code, *a, **kw)

    monkeypatch.setattr(bot.api, "get_daily_ohlcv", flaky)
    results = bot.bot.run_cycle(label="11:35")

    assert len(results) == len(WATCHLIST), "실패한 종목도 결과에 남아야 합니다"
    assert any(r.get("error") for r in results)
    assert bot.bot.consecutive_failures == 0, "종목 하나 실패는 사이클 실패가 아닙니다"

    summaries = [m for m in bot.sent.messages if m.startswith("📊")]
    assert "(오류) 012330" in summaries[0]
    assert not [m for m in bot.sent.messages if m.startswith("⚠️")], \
        "요약에 이미 실렸는데 따로 또 울렸습니다"

    winner = next(r for r in _rows(bot.db, "SELECT code, final_action FROM decisions")
                  if r["code"] == WINNER)
    assert winner["final_action"] == "STRONG_BUY", "한 종목이 죽어도 나머지는 판단돼야 합니다"


def _fixed_datetime():
    """사이클 안에서 쓰는 datetime.now(KST) 를 장중으로 고정한다."""
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    return Fixed
