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


def test_startup_spells_out_what_dry_run_means():
    """'DRY_RUN: on' 만으로는 주문이 안 나간다는 뜻인 줄 모른다 — 하루를 날렸다."""
    session = StubSession()
    Notifier(make_env(), session=session).send_startup(5)
    message = text_of(session)
    assert "주문은 내지 않습니다" in message
    assert "DRY_RUN 을 false" in message


def test_startup_does_not_nag_when_orders_are_real():
    session = StubSession()
    Notifier(make_env(dry_run=False), session=session).send_startup(5)
    message = text_of(session)
    assert "주문은 내지 않습니다" not in message
    assert "실주문이 전송됩니다" in message


def test_startup_lists_upcoming_holidays_and_calendar_warning():
    session = StubSession()
    Notifier(make_env(), session=session).send_startup(
        5, holidays=["09/24(목)", "09/25(금)"], calendar_warning="달력이 곧 바닥납니다")
    message = text_of(session)
    assert "09/24(목), 09/25(금)" in message
    assert "달력이 곧 바닥납니다" in message


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


# --------------------------------------------------------------------------- #
# 알림 폭주 억제
# --------------------------------------------------------------------------- #


def test_repeated_error_is_suppressed():
    """같은 오류가 매 종목 반복돼도 텔레그램이 도배되지 않아야 한다."""
    session = StubSession()
    notifier = Notifier(make_env(), session=session, error_cooldown_sec=600)

    for _ in range(10):
        notifier.send_error(ValueError("시세 조회 실패"), context="005930")

    assert len(session.posts) == 1


def test_different_errors_are_not_suppressed():
    session = StubSession()
    notifier = Notifier(make_env(), session=session, error_cooldown_sec=600)

    notifier.send_error(ValueError("시세 조회 실패"))
    notifier.send_error(KeyError("스키마 누락"))
    assert len(session.posts) == 2


def test_dedupe_can_be_disabled():
    session = StubSession()
    notifier = Notifier(make_env(), session=session, error_cooldown_sec=600)

    notifier.send_error(ValueError("치명적"), dedupe=False)
    notifier.send_error(ValueError("치명적"), dedupe=False)
    assert len(session.posts) == 2


def test_cooldown_expiry_allows_resend():
    session = StubSession()
    notifier = Notifier(make_env(), session=session, error_cooldown_sec=0)

    notifier.send_error(ValueError("반복 오류"))
    notifier.send_error(ValueError("반복 오류"))
    assert len(session.posts) == 2


def test_alert_with_key_is_deduped():
    session = StubSession()
    notifier = Notifier(make_env(), session=session, error_cooldown_sec=600)

    for _ in range(5):
        notifier.send_alert("🚨 당일 손실 한도 도달", ["당일 손익 -3.20%"], key="daily_loss_limit")

    assert len(session.posts) == 1
    assert "당일 손실 한도" in session.posts[0]["json"]["text"]


def test_alert_without_key_always_sends():
    session = StubSession()
    notifier = Notifier(make_env(), session=session)
    notifier.send_alert("알림", ["내용"])
    notifier.send_alert("알림", ["내용"])
    assert len(session.posts) == 2


def test_cycle_summary_says_why_a_buy_did_not_go_out():
    """'STRONG_BUY 20%' 만 덩그러니 남으면 왜 안 샀는지 알 수 없다."""
    from utils.notifier import Notifier

    text = Notifier._format_row({
        "name": "SK하이닉스", "agents": "claude BUY(0.78)", "final_action": "STRONG_BUY",
        "weight_pct": 20, "ordered": False,
        "outcome": "매수 5주 @188,500원 — 기록만 (DRY_RUN, 실제 주문 아님)",
    })
    assert "DRY_RUN" in text and "STRONG_BUY 20%" in text


def test_a_placed_order_does_not_repeat_the_outcome():
    from utils.notifier import Notifier

    text = Notifier._format_row({
        "name": "KB금융", "agents": "claude BUY(0.40)", "final_action": "BUY_SMALL",
        "weight_pct": 5, "ordered": True, "side": "BUY", "qty": 1, "price": 176628,
        "outcome": "매수 1주 @176,628원 체결",
    })
    assert text.count("176,628") == 1, "같은 내용을 두 번 적지 않습니다"


def test_a_dry_run_order_never_reads_as_a_real_one():
    """요약만 보는 사람이 '매수 13주' 를 보면 진짜 산 줄 안다."""
    from utils.notifier import Notifier

    text = Notifier._format_row({
        "name": "SK하이닉스", "agents": "claude BUY(0.80)", "final_action": "STRONG_BUY",
        "weight_pct": 20, "ordered": True, "side": "BUY", "qty": 13, "price": 76228,
        "outcome": "매수 13주 @76,228원 — 기록만 (DRY_RUN, 실제 주문 아님)",
    })
    assert "DRY_RUN" in text
