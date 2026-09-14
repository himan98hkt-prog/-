"""PC 재부팅 후 자동 실행 — 등록·해제와 부팅 스크립트."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from utils import autostart

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def win(tmp_path, monkeypatch):
    """윈도우인 척하고, 시작 프로그램 폴더를 임시 경로로 돌린다."""
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "is_supported", lambda: True)
    monkeypatch.setattr(autostart, "startup_dir", lambda: startup)

    base = tmp_path / "app"
    (base / "data").mkdir(parents=True)
    (base / "boot.bat").write_text("@echo off\n", encoding="utf-8")

    # PowerShell 대신 바로가기 파일을 직접 만든다.
    def fake_run(cmd, **kw):
        (startup / autostart.SHORTCUT_NAME).write_text("shortcut", encoding="utf-8")
        return None

    monkeypatch.setattr(autostart.subprocess, "run", fake_run)
    return base, base / "data", startup


def test_disabled_by_default(win):
    base, data, _ = win
    assert not autostart.status(base, data).enabled


def test_enable_creates_the_shortcut(win):
    base, data, startup = win
    result = autostart.enable(base, data)
    assert result.enabled
    assert (startup / autostart.SHORTCUT_NAME).exists()


def test_enable_sets_the_trading_flag(win):
    base, data, _ = win
    autostart.enable(base, data)
    assert autostart.should_trade_on_boot(data), "부팅 때 매매까지 시작해야 합니다"


def test_enable_without_trading_leaves_flag_off(win):
    base, data, _ = win
    result = autostart.enable(base, data, trade_on_boot=False)
    assert result.enabled and not autostart.should_trade_on_boot(data)


def test_disable_removes_shortcut_and_flag(win):
    base, data, startup = win
    autostart.enable(base, data)
    result = autostart.disable(base, data)
    assert not result.enabled
    assert not (startup / autostart.SHORTCUT_NAME).exists()
    assert not autostart.should_trade_on_boot(data)


def test_disable_is_safe_when_not_enabled(win):
    base, data, _ = win
    assert not autostart.disable(base, data).enabled


def test_enable_fails_cleanly_without_boot_bat(win):
    base, data, _ = win
    (base / "boot.bat").unlink()
    result = autostart.enable(base, data)
    assert not result.enabled and "boot.bat" in result.detail


def test_powershell_failure_is_reported(win, monkeypatch):
    base, data, _ = win

    def boom(cmd, **kw):
        raise OSError("powershell 없음")

    monkeypatch.setattr(autostart.subprocess, "run", boom)
    result = autostart.enable(base, data)
    assert not result.enabled and "powershell" in result.detail


def test_unsupported_platform_reports_plainly(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "is_supported", lambda: False)
    result = autostart.status(tmp_path, tmp_path)
    assert not result.supported and "Windows" in result.detail


def test_disable_never_touches_user_data(win):
    base, data, _ = win
    (data / "trader.db").write_text("소중한 기록", encoding="utf-8")
    (base / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-mine", encoding="utf-8")
    autostart.enable(base, data)
    autostart.disable(base, data)
    assert (data / "trader.db").read_text(encoding="utf-8") == "소중한 기록"
    assert (base / ".env").exists()


# --- 부팅 스크립트 ---------------------------------------------------------- #


def test_boot_bat_is_ascii_with_crlf():
    raw = (BASE_DIR / "boot.bat").read_bytes()
    assert all(b < 128 for b in raw), "boot.bat 에 비ASCII 문자가 있습니다"
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_boot_bat_waits_for_the_network():
    """재부팅 직후 바로 증권사 API 를 부르면 실패한다."""
    text = (BASE_DIR / "boot.bat").read_text(encoding="ascii")
    assert "timeout /t 30" in text


def test_boot_bat_checks_the_trading_flag():
    text = (BASE_DIR / "boot.bat").read_text(encoding="ascii")
    assert f"data\\{autostart.TRADING_FLAG}" in text
    assert "boot_trading.py" in text


def test_boot_trading_skips_without_env(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("scripts.boot_trading")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(sys, "argv", ["boot_trading.py"])
    assert module.main() == 0


def test_boot_trading_skips_when_already_running(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("scripts.boot_trading")
    module = importlib.reload(module)
    env = tmp_path / ".env"
    env.write_text("x", encoding="utf-8")
    monkeypatch.setattr(module, "ENV_PATH", env)
    monkeypatch.setattr(module, "missing_required", lambda path: [])
    monkeypatch.setattr(module.process, "is_running", lambda data_dir: True)
    started: list[str] = []
    monkeypatch.setattr(module.process, "start", lambda *a: started.append("x"))
    assert module.main() == 0
    assert started == [], "이미 돌고 있으면 다시 띄우면 안 됩니다"


def test_boot_trading_skips_when_config_incomplete(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("scripts.boot_trading")
    module = importlib.reload(module)
    env = tmp_path / ".env"
    env.write_text("x", encoding="utf-8")
    monkeypatch.setattr(module, "ENV_PATH", env)
    monkeypatch.setattr(module, "missing_required", lambda path: ["KIS_APP_KEY"])
    started: list[str] = []
    monkeypatch.setattr(module.process, "start", lambda *a: started.append("x"))
    assert module.main() == 0 and started == []
