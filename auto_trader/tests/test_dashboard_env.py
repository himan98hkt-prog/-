"""설정 화면의 .env 읽기·쓰기 테스트 — 비밀값 취급이 핵심."""

from __future__ import annotations

import pytest
from dotenv import dotenv_values

from dashboard.env_file import (
    ALL_FIELDS,
    GROUPS,
    missing_required,
    read_env,
    read_for_display,
    write_env,
)

SECRET = "sk-ant-super-secret-value-123"


@pytest.fixture
def env_path(tmp_path):
    return tmp_path / ".env"


def test_write_creates_readable_env(env_path):
    write_env(env_path, {"KIS_APP_KEY": "PSkey123456", "KIS_ACCOUNT_NO": "50123456"})
    values = dotenv_values(env_path)
    assert values["KIS_APP_KEY"] == "PSkey123456"
    assert values["KIS_ENV"] == "VTS", "기본값이 채워져야 합니다"
    assert values["DRY_RUN"] == "true"


def test_secrets_are_never_sent_to_the_browser(env_path):
    write_env(env_path, {"ANTHROPIC_API_KEY": SECRET})
    display = read_for_display(env_path)

    assert SECRET not in str(display), "원문이 화면 데이터에 들어가면 안 됩니다"
    assert display["ANTHROPIC_API_KEY"]["masked"].startswith("sk-a")
    assert display["ANTHROPIC_API_KEY"]["value"] == ""
    assert display["ANTHROPIC_API_KEY"]["filled"] is True


def test_non_secret_values_are_shown(env_path):
    write_env(env_path, {"KIS_ACCOUNT_NO": "50123456"})
    assert read_for_display(env_path)["KIS_ACCOUNT_NO"]["value"] == "50123456"


def test_blank_secret_keeps_existing_value(env_path):
    """화면에는 마스킹만 보이므로, 손대지 않은 칸이 값을 지우면 안 된다."""
    write_env(env_path, {"ANTHROPIC_API_KEY": SECRET})
    write_env(env_path, {"ANTHROPIC_API_KEY": "", "KIS_ACCOUNT_NO": "50123456"})
    assert read_env(env_path)["ANTHROPIC_API_KEY"] == SECRET


def test_explicit_clear_removes_secret(env_path):
    write_env(env_path, {"ANTHROPIC_API_KEY": SECRET})
    write_env(env_path, {"ANTHROPIC_API_KEY": "__CLEAR__"})
    assert read_env(env_path)["ANTHROPIC_API_KEY"] == ""


def test_blank_non_secret_is_cleared(env_path):
    write_env(env_path, {"NAVER_CLIENT_ID": "id"})
    write_env(env_path, {"NAVER_CLIENT_ID": ""})
    assert read_env(env_path)["NAVER_CLIENT_ID"] == ""


@pytest.mark.parametrize(
    "typed,stored",
    [
        ('"PSkey123"', "PSkey123"),
        ("'PSkey123'", "PSkey123"),
        ("PSkey123 # 내 키", "PSkey123"),
        ("  PSkey123  ", "PSkey123"),
    ],
)
def test_common_paste_mistakes_are_cleaned(env_path, typed, stored):
    write_env(env_path, {"KIS_APP_KEY": typed})
    assert read_env(env_path)["KIS_APP_KEY"] == stored


def test_written_file_has_no_inline_comments(env_path):
    """python-dotenv 가 주석을 값으로 읽는 함정을 저장 단계에서 만들지 않는다."""
    write_env(env_path, {"KIS_APP_KEY": "PSkey"})
    values = dotenv_values(env_path)
    assert {k: v for k, v in values.items() if v and v.strip().startswith("#")} == {}


def test_file_permissions_are_owner_only(env_path):
    write_env(env_path, {"KIS_APP_KEY": "PSkey"})
    assert oct(env_path.stat().st_mode)[-3:] == "600"


def test_write_is_atomic_and_leaves_no_temp_files(env_path):
    write_env(env_path, {"KIS_APP_KEY": "PSkey"})
    assert [p.name for p in env_path.parent.iterdir() if p.name.startswith(".env.")] == []


def test_changed_keys_are_reported(env_path):
    write_env(env_path, {"KIS_ACCOUNT_NO": "50123456"})
    changed = write_env(env_path, {"KIS_ACCOUNT_NO": "50123456", "KIS_ACCOUNT_PRODUCT_CD": "02"})
    assert changed == ["KIS_ACCOUNT_PRODUCT_CD"]


def test_missing_required_lists_empty_fields(env_path):
    write_env(env_path, {})
    missing = missing_required(env_path)
    assert "KIS_APP_KEY" in missing
    assert "NAVER_CLIENT_ID" not in missing, "선택 항목은 빠져야 합니다"


def test_all_fields_are_grouped():
    assert {f.key for group in GROUPS for f in group.fields} == set(ALL_FIELDS)


def test_env_example_keys_are_all_editable():
    """.env.example 에 있는 항목은 화면에서도 고칠 수 있어야 한다."""
    from config.loader import BASE_DIR

    example = dotenv_values(BASE_DIR / ".env.example")
    assert set(example) - set(ALL_FIELDS) == set()


# --------------------------------------------------------------------------- #
# 알림 채널별 필수 항목 (config/loader.py 와 같은 규칙이어야 한다)
# --------------------------------------------------------------------------- #


def test_telegram_requires_token_and_chat_id(env_path):
    write_env(env_path, {"NOTIFIER": "telegram"})
    missing = missing_required(env_path)
    assert "TELEGRAM_BOT_TOKEN" in missing
    assert "TELEGRAM_CHAT_ID" in missing, "loader 는 CHAT_ID 도 필수로 본다"
    assert "DISCORD_WEBHOOK_URL" not in missing


def test_discord_requires_webhook_not_telegram(env_path):
    write_env(env_path, {"NOTIFIER": "discord"})
    missing = missing_required(env_path)
    assert "DISCORD_WEBHOOK_URL" in missing
    assert "TELEGRAM_BOT_TOKEN" not in missing, "디스코드 사용자가 영원히 막히면 안 됩니다"


def test_discord_user_can_complete_setup(env_path):
    """디스코드만 쓰는 사용자도 설정을 끝낼 수 있어야 한다."""
    write_env(env_path, {
        "KIS_APP_KEY": "k", "KIS_APP_SECRET": "s", "KIS_ACCOUNT_NO": "50123456",
        "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g",
        "NOTIFIER": "discord", "DISCORD_WEBHOOK_URL": "https://discord.test/hook",
    })
    assert missing_required(env_path) == []


def test_dashboard_required_matches_loader(env_path, monkeypatch):
    """대시보드가 '완료'라고 한 설정은 loader 도 통과해야 한다."""
    from config.loader import ALL_ENV_KEYS, load

    # load_dotenv 는 값을 os.environ 에 남긴다 — 앞선 테스트의 잔재를 걷어낸다.
    for key in ALL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    write_env(env_path, {
        "KIS_APP_KEY": "key", "KIS_APP_SECRET": "secret", "KIS_ACCOUNT_NO": "50123456",
        "ANTHROPIC_API_KEY": "sk-ant-x", "GEMINI_API_KEY": "AIza-x",
        "NOTIFIER": "telegram", "TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "9",
    })
    assert missing_required(env_path) == []
    load(env_path=env_path, create_dirs=False)  # ConfigError 가 나면 실패
