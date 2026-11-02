"""엔진 명단(`ai.engines`)과 월 크레딧 표시.

명단의 존재 이유는 비용이다. 명단에 없는 엔진은 **객체조차 만들지 않으므로**
호출이 없고, 키도 필요 없고, 요금도 발생하지 않는다. 그래서 여기서 지킬 것은
두 가지다 — 출하 기본값이 실제로 Claude 단독인지, 그리고 쓰지 않는 엔진의
키를 요구해 기동을 막지 않는지.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from config.loader import (CONFIG_DIR, DEFAULT_ENGINES, VALID_ENGINES,
                           _load_engines, _load_env, _load_rules)
from dashboard.queries import credit_usage
from utils.db import connect, init_db

KST = ZoneInfo("Asia/Seoul")


# --- 출하 기본값 ----------------------------------------------------------- #

def test_the_shipped_default_is_claude_only():
    """실제로 내려주는 settings.yaml 이 Claude 단독인지.

    이 테스트가 이 변경의 핵심 주장을 지킨다 — ChatGPT·Gemini 를 호출하지 않으니
    별도 요금이 발생하지 않는다는 주장. 누군가 명단을 늘리면 여기서 걸린다.
    """
    raw = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    errors: list[str] = []
    engines = _load_engines(raw["ai"], errors)
    assert errors == []
    assert engines == ("claude",), f"출하 기본값이 Claude 단독이 아닙니다: {engines}"


def test_the_shipped_default_turns_the_rule_engine_on():
    """규칙 엔진이 꺼져 있으면 교차검증이 통째로 사라진다."""
    raw = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    errors: list[str] = []
    rules = _load_rules(raw, errors)
    assert errors == []
    assert rules.enabled is True


# --- 명단 파싱 ------------------------------------------------------------- #

def test_a_missing_roster_falls_back_to_the_default():
    errors: list[str] = []
    assert _load_engines({}, errors) == DEFAULT_ENGINES
    assert errors == []


@pytest.mark.parametrize("given, expected", [
    (["claude"], ("claude",)),
    (["claude", "gemini"], ("claude", "gemini")),
    ("claude, gemini", ("claude", "gemini")),
    ("CLAUDE", ("claude",)),
    (["claude", "claude"], ("claude",)),          # 중복 제거
])
def test_the_roster_accepts_the_shapes_people_actually_write(given, expected):
    errors: list[str] = []
    assert _load_engines({"engines": given}, errors) == expected
    assert errors == []


def test_an_unknown_engine_is_reported_not_ignored():
    """오타를 조용히 넘기면, 참여한다고 믿은 엔진 없이 돌게 된다."""
    errors: list[str] = []
    _load_engines({"engines": ["claude", "gpt4"]}, errors)
    assert any("gpt4" in e for e in errors), errors


def test_an_empty_roster_is_an_error():
    """판단 주체가 없으면 매수가 영구히 불가능해진다 — 조용히 넘길 수 없다."""
    errors: list[str] = []
    _load_engines({"engines": []}, errors)
    assert any("최소 한 개" in e for e in errors), errors


def test_every_valid_engine_name_parses():
    errors: list[str] = []
    assert _load_engines({"engines": list(VALID_ENGINES)}, errors) == VALID_ENGINES
    assert errors == []


# --- 명단에 없는 엔진의 키는 요구하지 않는다 -------------------------------- #

BASE_ENV = {
    "KIS_APP_KEY": "k", "KIS_APP_SECRET": "s", "KIS_ACCOUNT_NO": "12345678",
    "ANTHROPIC_API_KEY": "sk-ant", "CLAUDE_MODEL": "claude-opus-5-5",
    "NOTIFIER": "telegram", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1",
}


@pytest.fixture
def clean_env(monkeypatch):
    from config.loader import ALL_ENV_KEYS
    for key in ALL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_claude_only_starts_without_a_gemini_key(clean_env):
    """이게 막히면 Gemini 를 버릴 수 없다 — 전에는 GEMINI_API_KEY 가 필수였다."""
    errors: list[str] = []
    _load_env(errors, engines=("claude",))
    assert errors == [], f"Claude 단독인데 다른 키를 요구합니다: {errors}"


def test_adding_gemini_to_the_roster_asks_for_its_key(clean_env):
    errors: list[str] = []
    _load_env(errors, engines=("claude", "gemini"))
    assert any("GEMINI_API_KEY" in e for e in errors), errors


def test_the_error_says_which_engine_wants_the_key(clean_env):
    """'필수입니다' 만으로는 왜 필요한지 알 수 없다."""
    errors: list[str] = []
    _load_env(errors, engines=("claude", "chatgpt"))
    message = " ".join(errors)
    assert "OPENAI_API_KEY" in message
    assert "chatgpt" in message, message


def test_kis_keys_are_required_whatever_the_roster(clean_env):
    clean_env.delenv("KIS_APP_KEY", raising=False)
    errors: list[str] = []
    _load_env(errors, engines=("claude",))
    assert any("KIS_APP_KEY" in e for e in errors), errors


# --- 월 크레딧 표시 -------------------------------------------------------- #

@pytest.fixture
def db(tmp_path):
    path = tmp_path / "trader.db"
    init_db(path)
    return path


def _spend(db_path: Path, amount: float, day: int, month: str = "2026-11") -> None:
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO ai_usage (cycle_id, code, agent, model, input_tokens,
                                     output_tokens, cost_usd, ok, elapsed_sec, created_at)
               VALUES ('c', '005930', 'claude', 'claude-opus-5-5', 6316, 2500, ?, 1, 1.0, ?)""",
            (amount, f"{month}-{day:02d} 10:00:00"),
        )


def test_an_unused_credit_reads_as_spare(db):
    """크레딧은 매달 소멸한다 — 많이 남기는 것은 절약이 아니라 버리는 것이다.
    그래서 크게 남는 상태는 경고가 아니라 '더 쓸 수 있다' 는 안내여야 한다."""
    now = datetime.datetime(2026, 11, 15, 12, 0, tzinfo=KST)
    for day in range(1, 11):
        _spend(db, 0.5, day)
    usage = credit_usage(db, credit_usd=100.0, now=now)
    assert usage["state"] == "spare"
    assert usage["spent_usd"] == pytest.approx(5.0)
    assert usage["headroom_usd"] == pytest.approx(95.0)


def test_a_fast_burn_reads_as_watch(db):
    now = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=KST)
    for day in range(1, 11):
        _spend(db, 3.2, day)      # 열흘에 $32 → 월말 약 $96
    usage = credit_usage(db, credit_usd=100.0, now=now)
    assert usage["state"] == "watch"
    assert usage["projected_pct"] >= 90


def test_an_exhausted_credit_reads_as_over(db):
    now = datetime.datetime(2026, 11, 20, 12, 0, tzinfo=KST)
    _spend(db, 101.0, 5)
    usage = credit_usage(db, credit_usd=100.0, now=now)
    assert usage["state"] == "over"
    assert usage["headroom_usd"] == 0.0


def test_other_months_are_not_counted(db):
    now = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=KST)
    _spend(db, 50.0, 5, month="2026-10")
    _spend(db, 1.0, 5, month="2026-11")
    usage = credit_usage(db, credit_usd=100.0, now=now)
    assert usage["spent_usd"] == pytest.approx(1.0), "지난달 사용액이 섞였습니다"
    assert usage["month"] == "2026-11"


def test_an_empty_month_does_not_divide_by_zero(db):
    now = datetime.datetime(2026, 11, 1, 9, 0, tzinfo=KST)
    usage = credit_usage(db, credit_usd=100.0, now=now)
    assert usage["spent_usd"] == 0.0
    assert usage["projected_usd"] == 0.0
    assert usage["calls"] == 0


def test_a_zero_credit_is_reported_as_unknown(db):
    """크레딧 금액을 모르면 '한도 초과' 라고 단정하지 않는다."""
    now = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=KST)
    _spend(db, 5.0, 5)
    usage = credit_usage(db, credit_usd=0.0, now=now)
    assert usage["state"] == "unknown"


def test_the_calendar_approximation_is_declared(db):
    """실제 갱신일은 결제주기 기준이라 며칠 어긋난다 — 화면이 그 사실을 말해야 한다."""
    now = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=KST)
    assert credit_usage(db, credit_usd=100.0, now=now)["approximate"] is True
