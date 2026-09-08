"""터미널 키 입력 마법사."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.env_file import read_env  # noqa: E402


@pytest.fixture()
def wizard(tmp_path, monkeypatch):
    module = importlib.import_module("scripts.setup_keys")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys, "argv", ["setup_keys.py"])
    return module


def _answers(module, monkeypatch, answers: list[str]) -> None:
    """평문·비밀 입력을 같은 큐에서 꺼내 쓴다."""
    queue = list(answers)

    def take(_prompt=""):
        assert queue, "예상보다 많은 입력을 요구했습니다"
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", take)
    monkeypatch.setattr(module.getpass, "getpass", take)
    return queue


def test_saves_entered_values(wizard, monkeypatch, capsys):
    # GROUPS 순서대로: 실행환경 3 → KIS 4 → AI 7 → 알림 4 → 뉴스 2
    left = _answers(wizard, monkeypatch, [
        "", "", "",                                   # 실행 환경 (기본값)
        "appkey", "appsecret", "50123456", "01",      # 한국투자증권
        "sk-ant-1", "", "", "",                       # Claude
        "gem-1", "", "",                              # Gemini
        "telegram", "bot-token", "12345", "",         # 알림
        "", "",                                       # 뉴스 (선택)
    ])
    assert wizard.main() == 0
    assert not left

    saved = read_env(wizard.ENV_PATH)
    assert saved["KIS_APP_KEY"] == "appkey"
    assert saved["KIS_ACCOUNT_NO"] == "50123456"
    assert saved["ANTHROPIC_API_KEY"] == "sk-ant-1"
    assert saved["TELEGRAM_CHAT_ID"] == "12345"
    # 빈 입력은 기본값으로 채워진다
    assert saved["KIS_ENV"] == "VTS"
    assert saved["DRY_RUN"] == "true"
    assert "sk-ant-1" not in capsys.readouterr().out  # 비밀값은 화면에 안 찍힌다


FILLED = """KIS_ENV=VTS
DRY_RUN=true
LOG_LEVEL=INFO
KIS_APP_KEY=a
KIS_APP_SECRET=keepme
KIS_ACCOUNT_NO=50123456
KIS_ACCOUNT_PRODUCT_CD=01
ANTHROPIC_API_KEY=d
CLAUDE_MODEL=claude-sonnet-5
GEMINI_API_KEY=e
GEMINI_MODEL=gemini-2.5-pro
NOTIFIER=telegram
TELEGRAM_BOT_TOKEN=f
TELEGRAM_CHAT_ID=1
NAVER_CLIENT_ID=old
"""


def test_enter_keeps_existing_secret(wizard, monkeypatch):
    wizard.ENV_PATH.write_text(FILLED, encoding="utf-8")
    left = _answers(wizard, monkeypatch, [""] * 20)
    assert wizard.main() == 0
    assert not left
    assert read_env(wizard.ENV_PATH)["KIS_APP_SECRET"] == "keepme"


def test_dash_clears_optional_value(wizard, monkeypatch):
    wizard.ENV_PATH.write_text(FILLED, encoding="utf-8")
    _answers(wizard, monkeypatch, [""] * 18 + ["-", ""])
    assert wizard.main() == 0
    assert read_env(wizard.ENV_PATH)["NAVER_CLIENT_ID"] == ""


def test_dash_refused_on_required_field(wizard, monkeypatch, capsys):
    wizard.ENV_PATH.write_text(FILLED, encoding="utf-8")
    # 4번째가 KIS_APP_KEY — 필수라 `-` 로 비울 수 없다.
    _answers(wizard, monkeypatch, [""] * 3 + ["-", "b"] + [""] * 16)
    assert wizard.main() == 0
    assert "비울 수 없습니다" in capsys.readouterr().out
    assert read_env(wizard.ENV_PATH)["KIS_APP_KEY"] == "b"


def test_rejects_invalid_choice_then_accepts(wizard, monkeypatch, capsys):
    wizard.ENV_PATH.write_text(FILLED, encoding="utf-8")
    _answers(wizard, monkeypatch, ["LIVE", "REAL"] + [""] * 19)
    assert wizard.main() == 0
    assert read_env(wizard.ENV_PATH)["KIS_ENV"] == "REAL"
    assert "골라 주세요" in capsys.readouterr().out


def test_missing_only_skips_filled(wizard, monkeypatch):
    wizard.ENV_PATH.write_text(
        "\n".join([
            "KIS_ENV=VTS", "DRY_RUN=true", "KIS_APP_KEY=a", "KIS_APP_SECRET=b",
            "KIS_ACCOUNT_NO=c", "KIS_ACCOUNT_PRODUCT_CD=01",
            "ANTHROPIC_API_KEY=d", "CLAUDE_MODEL=claude-sonnet-5",
            "GEMINI_API_KEY=e", "GEMINI_MODEL=gemini-2.5-pro",
            "NOTIFIER=telegram", "TELEGRAM_BOT_TOKEN=f",
        ]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["setup_keys.py", "--missing"])
    left = _answers(wizard, monkeypatch, ["999"])  # TELEGRAM_CHAT_ID 하나만 묻는다
    assert wizard.main() == 0
    assert not left
    assert read_env(wizard.ENV_PATH)["TELEGRAM_CHAT_ID"] == "999"


def test_non_tty_refuses(wizard, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    assert wizard.main() == 1
    assert "대화형 터미널이 아닙니다" in capsys.readouterr().out


def test_cancel_leaves_env_untouched(wizard, monkeypatch):
    wizard.ENV_PATH.write_text("KIS_APP_KEY=original\n", encoding="utf-8")

    def boom(_prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", boom)
    assert wizard.main() == 130
    assert wizard.ENV_PATH.read_text(encoding="utf-8") == "KIS_APP_KEY=original\n"
