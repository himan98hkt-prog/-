"""값 위생 검사 — 붙여넣기 사고를 API 호출 전에 잡아낸다."""

from __future__ import annotations

import sys

from utils.key_check import FAIL, OK, check_value_hygiene


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


def test_key_from_another_service_is_reported():
    detail = _problems(ANTHROPIC_API_KEY="AIzaSyWrongService")["ANTHROPIC_API_KEY"]
    assert "Gemini 키로 보입니다" in detail


def test_anthropic_key_in_the_gemini_box_is_reported():
    assert "Anthropic 키로 보입니다" in _problems(GEMINI_API_KEY="sk-ant-wrong")["GEMINI_API_KEY"]


def test_unfamiliar_key_format_is_not_rejected():
    """제공사가 키 형식을 바꿔도 멀쩡한 키를 막아서는 안 된다."""
    assert check_value_hygiene({"GEMINI_API_KEY": "x" * 53}) == []
    assert check_value_hygiene({"OPENAI_API_KEY": "abc123def456"}) == []


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



# --------------------------------------------------------------------------- #
# 선택 항목 실패는 진행을 막지 않는다
# --------------------------------------------------------------------------- #


def _result(name, status, detail=""):
    from utils.key_check import Result

    return Result(name, status, detail)


def test_optional_failure_does_not_block():
    from utils.key_check import OK, summarize

    counts = summarize([_result("KIS 인증", OK), _result("ChatGPT (선택)", FAIL, "잔액 0")])
    assert counts["blocking_fail"] == 0, "선택 항목 실패가 진행을 막으면 안 됩니다"
    assert counts["optional_fail"] == 1
    assert counts["fail"] == 1  # 화면에는 여전히 실패로 센다


def test_required_failure_blocks():
    from utils.key_check import OK, summarize

    counts = summarize([_result("KIS 인증", FAIL, "토큰 실패"), _result("Anthropic (Claude)", OK)])
    assert counts["blocking_fail"] == 1


def test_optional_and_required_failures_are_counted_apart():
    counts_all = __import__("utils.key_check", fromlist=["summarize"]).summarize([
        _result("KIS 인증", FAIL), _result("ChatGPT (선택)", FAIL),
    ])
    assert counts_all["blocking_fail"] == 1 and counts_all["optional_fail"] == 1


def test_no_credit_message_says_the_key_is_fine(monkeypatch):
    """잔액 0 은 키가 틀린 게 아니다 — 그렇게 읽히면 사용자가 키만 계속 다시 만든다."""
    import utils.key_check as module

    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise RuntimeError(
                        "Error code: 429 - {'error': {'message': 'You have no credits "
                        "remaining.', 'type': 'insufficient_quota'}}")

        def __init__(self, **kw):
            pass

    fake = type(sys)("openai")
    fake.OpenAI = Boom
    monkeypatch.setitem(sys.modules, "openai", fake)

    result = module.check_openai({"OPENAI_API_KEY": "sk-proj-real", "OPENAI_MODEL": "gpt-5.1"})
    assert result.status == FAIL
    assert "키는 정상입니다" in result.detail
    assert "충전" in result.detail
    assert result.optional, "ChatGPT 는 선택 항목이어야 합니다"


def test_missing_openai_key_is_skipped_not_failed():
    import utils.key_check as module

    result = module.check_openai({})
    assert result.status == "skip" and result.optional


# --------------------------------------------------------------------------- #
# 환경 문제를 '키가 틀렸다' 로 읽히게 하지 않는다
# --------------------------------------------------------------------------- #


def test_gemini_quota_message_blames_the_model_not_the_key(monkeypatch):
    import utils.key_check as module

    class Boom:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise RuntimeError(
                    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, "
                    "'message': 'You exceeded your current quota'}}")

        def __init__(self, **kw):
            pass

    fake = type(sys)("google")
    genai = type(sys)("google.genai")
    genai.Client = Boom
    monkeypatch.setitem(sys.modules, "google", fake)
    monkeypatch.setitem(sys.modules, "google.genai", genai)

    result = module.check_gemini({"GEMINI_API_KEY": "real", "GEMINI_MODEL": "gemini-3.1-pro-preview"})
    assert "키는 정상입니다" in result.detail
    assert "gemini-3.5-flash" in result.detail, "해결책(무료 모델)을 알려줘야 합니다"


def test_kis_timeout_is_retried(monkeypatch):
    import requests

    import utils.key_check as module

    attempts = []

    def flaky(url, **kw):
        attempts.append(kw.get("timeout"))
        raise requests.Timeout("Read timed out")

    monkeypatch.setattr(requests, "post", flaky)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)

    results = module.check_kis({"KIS_APP_KEY": "k", "KIS_APP_SECRET": "s",
                                "KIS_ACCOUNT_NO": "44123451", "KIS_ENV": "VTS"})
    auth = next(r for r in results if r.name == "KIS 인증")
    assert len(attempts) == module.KIS_TOKEN_ATTEMPTS, "한 번 실패로 포기하면 안 됩니다"
    assert attempts[0] >= 30, "타임아웃이 너무 짧으면 멀쩡한 키가 실패합니다"
    assert "키 문제가 아닙니다" in auth.detail
    assert "포트를 막고 있는지" in auth.detail, "타임아웃이면 방화벽을 의심하도록 안내해야 합니다"


def test_kis_succeeds_on_a_later_attempt(monkeypatch):
    import requests

    import utils.key_check as module

    calls = {"n": 0}

    class Ok:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"access_token": "T"}

    def flaky(url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.Timeout("Read timed out")
        return Ok()

    monkeypatch.setattr(requests, "post", flaky)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)

    results = module.check_kis({"KIS_APP_KEY": "k", "KIS_APP_SECRET": "s",
                                "KIS_ACCOUNT_NO": "44123451", "KIS_ENV": "VTS"})
    assert next(r for r in results if r.name == "KIS 인증").status == OK
