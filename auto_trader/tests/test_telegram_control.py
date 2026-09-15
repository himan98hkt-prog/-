"""텔레그램 리모컨 — 등록된 채팅만, 보기와 멈추기만."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils.telegram_control import HELP, TelegramControl

CHAT = "8786453781"


class StubSession:
    def __init__(self, updates=None, fail=False):
        self.calls: list[tuple[str, dict]] = []
        self._updates = updates or []
        self._fail = fail

    def post(self, url, json=None, timeout=None):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, json or {}))
        if self._fail:
            raise ConnectionError("네트워크 끊김")
        if method == "getUpdates":
            return SimpleNamespace(json=lambda: {"ok": True, "result": self._updates})
        return SimpleNamespace(json=lambda: {"ok": True, "result": {}})

    @property
    def sent(self) -> list[str]:
        return [body.get("text", "") for method, body in self.calls if method == "sendMessage"]


def update(text, chat_id=CHAT, update_id=1):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


def make(handlers=None, session=None):
    session = session or StubSession()
    control = TelegramControl(
        "token", CHAT, handlers or {"/상태": lambda: "가동 중"}, session=session)
    return control, session


# --- 보안 ------------------------------------------------------------------- #


def test_ignores_messages_from_other_chats():
    control, session = make()
    assert control.handle(update("/상태", chat_id="999999")) is None
    assert session.sent == [], "등록되지 않은 사람에게는 답장조차 하면 안 됩니다"


def test_accepts_the_registered_chat_even_as_int():
    control, session = make()
    control.handle({"update_id": 1, "message": {"chat": {"id": int(CHAT)}, "text": "/상태"}})
    assert session.sent == ["가동 중"]


def test_no_handler_can_place_an_order():
    """폰으로 주문을 새로 내는 길은 열어두지 않는다."""
    import main as main_module

    bot_commands = {"/상태", "/status", "/보유", "/오늘",
                    "/정지", "/stop", "/재개", "/resume",
                    "/도움말", "/help", "/start"}
    source = (main_module.__file__)
    text = open(source, encoding="utf-8").read()
    section = text.split("_start_remote_control", 1)[1].split("def _cmd_help", 1)[0]
    for name in ("매수", "buy", "place_order"):
        assert name not in section, f"리모컨에 {name} 관련 명령이 들어가면 안 됩니다"
    assert "/정지" in section and "/재개" in section
    assert bot_commands  # 명령 목록이 비지 않았는지


# --- 명령 처리 --------------------------------------------------------------- #


def test_runs_the_matching_handler():
    control, session = make({"/보유": lambda: "삼성전자 10주"})
    control.handle(update("/보유"))
    assert session.sent == ["삼성전자 10주"]


def test_strips_the_bot_mention():
    """그룹에서는 /상태@내봇 형태로 온다."""
    control, session = make()
    control.handle(update("/상태@hupa98_trade_bot"))
    assert session.sent == ["가동 중"]


def test_ignores_plain_text():
    control, session = make()
    assert control.handle(update("안녕하세요")) is None
    assert session.sent == []


def test_unknown_command_shows_help():
    control, session = make()
    control.handle(update("/없는명령"))
    assert HELP in session.sent[0]


def test_handler_failure_does_not_crash():
    def boom():
        raise RuntimeError("DB 없음")

    control, session = make({"/상태": boom})
    control.handle(update("/상태"))
    assert "처리하지 못했습니다" in session.sent[0]


def test_help_mentions_that_orders_are_not_possible():
    assert "주문을 새로 낼 수 없습니다" in HELP


def test_help_explains_stop_blocks_exits_and_does_not_cancel_orders():
    assert "손절" in HELP and "새 주문을 차단" in HELP and "이미 접수된 주문" in HELP


# --- 폴링 ------------------------------------------------------------------- #


def test_poll_advances_the_offset():
    session = StubSession([update("/상태", update_id=10)])
    control, _ = make(session=session)
    assert control.poll_once() == 1
    assert control._offset == 11


def test_poll_survives_network_failure():
    control, session = make(session=StubSession(fail=True))
    assert control.poll_once() == 0, "네트워크가 끊겨도 예외를 던지면 안 됩니다"


def test_stop_ends_the_loop():
    control, _ = make()
    control.stop()
    assert control._stop.is_set()
