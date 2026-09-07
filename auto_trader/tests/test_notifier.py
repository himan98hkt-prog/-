"""알림 테스트 — 실패해도 매매를 막지 않는 것과 4096자 분할이 핵심."""

from __future__ import annotations

import pytest
import requests

from tests.conftest import FakeResponse, make_env
from utils.notifier import DISCORD_LIMIT, TELEGRAM_LIMIT, Notifier, split_message


class StubSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse({"ok": True})
        self.posts: list[dict] = []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


# --------------------------------------------------------------------------- #
# 분할
# --------------------------------------------------------------------------- #


def test_short_message_is_not_split():
    assert split_message("짧은 메시지", TELEGRAM_LIMIT) == ["짧은 메시지"]


def test_long_message_split_on_line_boundaries():
    text = "\n".join(f"{i}번째 줄" for i in range(2000))
    chunks = split_message(text, TELEGRAM_LIMIT)
    assert len(chunks) > 1
    assert all(len(chunk) <= TELEGRAM_LIMIT for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_single_line_longer_than_limit_is_hard_split():
    chunks = split_message("가" * 5000, TELEGRAM_LIMIT)
    assert len(chunks) == 2 and all(len(chunk) <= TELEGRAM_LIMIT for chunk in chunks)


def test_send_splits_into_multiple_requests():
    session = StubSession()
    notifier = Notifier(make_env(), session=session)
    assert notifier.send("\n".join(f"{i}번째 줄" for i in range(2000))) is True
    assert len(session.posts) > 1


def test_empty_message_sends_nothing():
    session = StubSession()
    assert Notifier(make_env(), session=session).send("   ") is True
    assert session.posts == []


# --------------------------------------------------------------------------- #
# 채널
# --------------------------------------------------------------------------- #


def test_telegram_payload():
    session = StubSession()
    Notifier(make_env(), session=session).send("테스트")
    post = session.posts[0]
    assert "api.telegram.org/bottg-token/sendMessage" in post["url"]
    assert post["json"]["chat_id"] == "12345" and post["json"]["text"] == "테스트"


def test_discord_payload_and_limit():
    env = make_env(notifier="discord", discord_webhook_url="https://discord.test/hook",
                   telegram_bot_token=None, telegram_chat_id=None)
    session = StubSession()
    Notifier(env, session=session).send("가" * 2500)
    assert session.posts[0]["url"] == "https://discord.test/hook"
    assert all(len(p["json"]["content"]) <= DISCORD_LIMIT for p in session.posts)


# --------------------------------------------------------------------------- #
# 실패는 매매를 막지 않는다
# --------------------------------------------------------------------------- #


def test_network_error_returns_false_without_raising():
    session = StubSession(requests.ConnectionError("network down"))
    assert Notifier(make_env(), session=session).send("테스트") is False


def test_http_error_returns_false():
    session = StubSession(FakeResponse({"ok": False}, status_code=403))
    assert Notifier(make_env(), session=session).send("테스트") is False


def test_missing_telegram_config_is_not_an_error():
    env = make_env(telegram_bot_token=None, telegram_chat_id=None)
    session = StubSession()
    assert Notifier(env, session=session).send("테스트") is False
    assert session.posts == []


# --------------------------------------------------------------------------- #
# 메시지 포맷
# --------------------------------------------------------------------------- #


def text_of(session) -> str:
    return "\n".join(post["json"]["text"] for post in session.posts)


def test_startup_warns_loudly_in_real_mode():
    session = StubSession()
    Notifier(make_env(kis_env="REAL", dry_run=False), session=session).send_startup(5)
    message = text_of(session)
    assert "실전 모드 시작" in message and "실제 자금" in message


def test_startup_in_paper_mode_has_no_warning():
    session = StubSession()
    Notifier(make_env(), session=session).send_startup(5)
    message = text_of(session)
    assert "실전 모드 시작" not in message
    assert "모의(VTS)" in message and "DRY_RUN: on" in message


def test_trade_message_marks_dry_run():
    session = StubSession()
    Notifier(make_env(), session=session).send_trade(
        {"code": "005930", "name": "삼성전자", "side": "BUY", "qty": 12,
         "price": 71_300, "status": "DRY_RUN", "dry_run": True, "reason": "합의 매수"}
    )
    message = text_of(session)
    assert "[DRY_RUN]" in message and "매수 삼성전자(005930)" in message
    assert "12주 @ 71,300원" in message


def test_cycle_summary_matches_spec_format():
    session = StubSession()
    Notifier(make_env(), session=session).send_cycle_summary("10:05", [
        {"code": "005930", "name": "삼성전자", "agents": "Claude BUY(0.8) / Gemini BUY(0.7)",
         "final_action": "STRONG_BUY", "weight_pct": 15, "ordered": True,
         "side": "BUY", "qty": 12, "price": 71_300},
        {"code": "000660", "name": "SK하이닉스", "agents": "Claude HOLD / Gemini BUY",
         "final_action": "HOLD"},
        {"code": "035720", "name": "카카오", "risk_blocked": True,
         "risk_reason": "당일 손실 한도 초과"},
    ])
    message = text_of(session)
    assert "📊 [10:05 사이클] 대상 3종목 / 주문 1건" in message
    assert "삼성전자: Claude BUY(0.8) / Gemini BUY(0.7) → STRONG_BUY 15% → 매수 12주 @71,300" in message
    assert "SK하이닉스: Claude HOLD / Gemini BUY → HOLD" in message
    assert "(리스크 거부) 카카오: 당일 손실 한도 초과" in message


def test_error_message_includes_context():
    session = StubSession()
    Notifier(make_env(), session=session).send_error(ValueError("계산 오류"), context="005930 수집")
    message = text_of(session)
    assert "005930 수집" in message and "계산 오류" in message


def test_daily_report_lists_positions():
    session = StubSession()
    Notifier(make_env(), session=session).send_daily_report({
        "total_pnl_pct": 1.23, "end_equity": 5_061_500, "buy_count": 2, "sell_count": 1,
        "position_count": 1,
        "positions": [{"code": "005930", "name": "삼성전자", "qty": 12, "pnl_pct": 2.4}],
    })
    message = text_of(session)
    assert "+1.23%" in message and "매수 2건 / 매도 1건" in message
    assert "삼성전자(005930) 12주 +2.40%" in message


def test_secrets_are_registered_for_log_masking():
    from utils.logger import _SECRETS

    Notifier(make_env(), session=StubSession())
    assert "tg-token" in _SECRETS
