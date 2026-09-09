"""값 위생 검사 — 붙여넣기 사고를 API 호출 전에 잡아낸다."""

from __future__ import annotations

from utils.key_check import FAIL, check_value_hygiene


def _problems(**env) -> dict[str, str]:
    return {r.name.removeprefix("입력값 "): r.detail for r in check_value_hygiene(env)}


def test_clean_values_raise_nothing():
    assert check_value_hygiene({
        "ANTHROPIC_API_KEY": "sk-ant-api03-abcDEF123",
        "GEMINI_API_KEY": "AIzaSyABCdef123",
        "GEMINI_MODEL": "gemini-2.5-pro",
        "CLAUDE_MODEL": "claude-sonnet-5",
        "KIS_APP_KEY": "PSabcdef123456",
    }) == []


def test_ignores_missing_and_empty_values():
    assert check_value_hygiene({"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": None}) == []


def test_trailing_whitespace_is_reported():
    assert "앞뒤 공백" in _problems(ANTHROPIC_API_KEY="sk-ant-abc ")["ANTHROPIC_API_KEY"]


def test_newline_inside_value_is_reported():
    assert "줄바꿈" in _problems(GEMINI_MODEL="gemini-2.5-pro\n")["GEMINI_MODEL"]


def test_carriage_return_is_reported():
    """윈도우에서 메모장으로 .env 를 고치면 \\r 이 남는다."""
    assert "줄바꿈" in _problems(GEMINI_MODEL="gemini-2.5-pro\r")["GEMINI_MODEL"]


def test_quotes_are_reported():
    assert "따옴표" in _problems(KIS_APP_SECRET='"secret"')["KIS_APP_SECRET"]


def test_zero_width_space_is_reported():
    """웹페이지에서 복사하면 눈에 안 보이는 문자가 딸려온다."""
    assert "제로폭 공백" in _problems(KIS_APP_KEY="PS​abc")["KIS_APP_KEY"]


def test_hangul_suggests_the_ime_was_on():
    # 네이버 칸은 전용 안내가 따로 있으므로 다른 키로 확인한다.
    detail = _problems(TELEGRAM_CHAT_ID="abc한글")["TELEGRAM_CHAT_ID"]
    assert "한글 2자" in detail and "입력기" in detail


def test_wrong_prefix_is_reported():
    detail = _problems(ANTHROPIC_API_KEY="AIzaSyWrongService")["ANTHROPIC_API_KEY"]
    assert "'sk-ant-' 로 시작해야" in detail


def test_gemini_prefix_is_checked_too():
    assert "'AIza' 로 시작해야" in _problems(GEMINI_API_KEY="sk-ant-wrong")["GEMINI_API_KEY"]


def test_secret_value_is_never_echoed():
    """진단 메시지에 키 원문이 실리면 안 된다."""
    secret = "sk-ant-supersecret-do-not-leak "
    detail = _problems(ANTHROPIC_API_KEY=secret)["ANTHROPIC_API_KEY"]
    assert "supersecret" not in detail
    assert "길이 31자" in detail


def test_all_problems_are_listed_together():
    detail = _problems(GEMINI_API_KEY=' "AIzaSy" ')["GEMINI_API_KEY"]
    assert "앞뒤 공백" in detail and "따옴표" in detail


def test_hygiene_runs_before_network_checks(monkeypatch):
    """run_all 은 위생 검사 결과를 먼저 담는다."""
    import utils.key_check as module

    monkeypatch.setattr(module, "check_kis", lambda env: [])
    monkeypatch.setattr(module, "check_anthropic", lambda env: module.Result("A", FAIL, ""))
    monkeypatch.setattr(module, "check_gemini", lambda env: module.Result("G", FAIL, ""))
    monkeypatch.setattr(module, "check_telegram", lambda env, send_test: [])

    results = module.run_all({"ANTHROPIC_API_KEY": "sk-ant-abc "})
    assert results[0].name == "입력값 ANTHROPIC_API_KEY"


# --------------------------------------------------------------------------- #
# 실전 계좌 경고 — 초록불로 지나가면 안 된다
# --------------------------------------------------------------------------- #


def _kis_account_result(mode: str):
    import utils.key_check as module

    class _Resp:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"access_token": "T"}

    import requests

    original = requests.post
    requests.post = lambda *a, **kw: _Resp()
    try:
        results = module.check_kis({
            "KIS_APP_KEY": "k", "KIS_APP_SECRET": "s",
            "KIS_ACCOUNT_NO": "50123456", "KIS_ENV": mode,
        })
    finally:
        requests.post = original
    return next(r for r in results if r.name == "KIS 계좌번호")


def test_real_account_is_flagged_not_passed():
    result = _kis_account_result("REAL")
    assert result.status == FAIL, "실전 계좌가 ✅ 로 표시되면 안 됩니다"
    assert "REAL(실전) 계좌입니다" in result.detail


def test_vts_account_passes_quietly():
    result = _kis_account_result("VTS")
    assert result.status == "ok" and "모의투자" in result.detail


def test_account_number_is_masked_in_both_modes():
    for mode in ("REAL", "VTS"):
        assert "50123456" not in _kis_account_result(mode).detail

