"""설정 로더 테스트 — .env.example 이 그대로 쓸 수 있는 형태인지 포함."""

from __future__ import annotations

import pytest
from dotenv import dotenv_values

from config.loader import BASE_DIR, CONFIG_DIR, ConfigError, load, mask

ENV_EXAMPLE = BASE_DIR / ".env.example"

REQUIRED_ENV = {
    "KIS_APP_KEY": "APPKEY-TEST",
    "KIS_APP_SECRET": "APPSECRET-TEST",
    "KIS_ACCOUNT_NO": "50123456",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "CLAUDE_MODEL": "claude-sonnet-5",
    "GEMINI_API_KEY": "gemini-test",
    "GEMINI_MODEL": "gemini-2.5-pro",
    "TELEGRAM_BOT_TOKEN": "tg-token",
    "TELEGRAM_CHAT_ID": "12345",
}


@pytest.fixture
def env_file(tmp_path):
    def write(**overrides):
        values = {**REQUIRED_ENV, **overrides}
        path = tmp_path / ".env"
        path.write_text("\n".join(f"{k}={v}" for k, v in values.items() if v is not None), encoding="utf-8")
        return path

    return write


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """프로세스 환경변수가 테스트에 새어들지 않게 한다."""
    for key in [*REQUIRED_ENV, "KIS_ENV", "DRY_RUN", "LOG_LEVEL", "NOTIFIER",
                "CLAUDE_TEMPERATURE", "CLAUDE_EFFORT", "GEMINI_TEMPERATURE",
                "KIS_ACCOUNT_PRODUCT_CD",
                "DISCORD_WEBHOOK_URL"]:
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- #
# .env.example 자체 검증
# --------------------------------------------------------------------------- #


def test_env_example_has_no_inline_comment_values():
    """`KEY=  # 설명` 형태면 python-dotenv 가 주석을 값으로 읽는다."""
    values = dotenv_values(ENV_EXAMPLE)
    polluted = {key: value for key, value in values.items() if value and value.strip().startswith("#")}
    assert polluted == {}, f"인라인 주석이 값으로 읽힙니다: {list(polluted)}"


def test_env_example_covers_every_required_key():
    values = dotenv_values(ENV_EXAMPLE)
    for key in [*REQUIRED_ENV, "KIS_ENV", "DRY_RUN", "NOTIFIER", "KIS_ACCOUNT_PRODUCT_CD"]:
        assert key in values, f".env.example 에 {key} 가 없습니다"


def test_env_example_defaults_to_paper_trading_and_dry_run():
    values = dotenv_values(ENV_EXAMPLE)
    assert values["KIS_ENV"] == "VTS", "기본값은 모의투자여야 합니다"
    assert values["DRY_RUN"] == "true", "기본값은 주문 미전송이어야 합니다"


# --------------------------------------------------------------------------- #
# load()
# --------------------------------------------------------------------------- #


def test_load_succeeds_and_masks_secrets(env_file):
    settings = load(env_path=env_file(), create_dirs=False)
    printed = repr(settings.env)

    assert settings.env.kis_env == "VTS" and settings.env.dry_run is True
    assert "APPSECRET-TEST" not in printed
    assert "sk-ant-test" not in printed
    assert settings.env.claude_temperature is None, "기본은 temperature 미전송"
    assert settings.env.gemini_temperature == 0.2


def test_missing_keys_are_reported_together(env_file, monkeypatch):
    path = env_file(KIS_APP_KEY="", ANTHROPIC_API_KEY="", TELEGRAM_CHAT_ID="")
    with pytest.raises(ConfigError) as exc_info:
        load(env_path=path, create_dirs=False)
    message = str(exc_info.value)
    assert "KIS_APP_KEY" in message and "ANTHROPIC_API_KEY" in message and "TELEGRAM_CHAT_ID" in message
    assert "3건" in message


def test_invalid_account_number_rejected(env_file):
    with pytest.raises(ConfigError, match="KIS_ACCOUNT_NO"):
        load(env_path=env_file(KIS_ACCOUNT_NO="123"), create_dirs=False)


def test_invalid_effort_rejected(env_file):
    with pytest.raises(ConfigError, match="CLAUDE_EFFORT"):
        load(env_path=env_file(CLAUDE_EFFORT="turbo"), create_dirs=False)


def test_temperature_out_of_range_rejected(env_file):
    with pytest.raises(ConfigError, match="CLAUDE_TEMPERATURE"):
        load(env_path=env_file(CLAUDE_TEMPERATURE="2.5"), create_dirs=False)


def test_discord_requires_webhook(env_file):
    with pytest.raises(ConfigError, match="DISCORD_WEBHOOK_URL"):
        load(env_path=env_file(NOTIFIER="discord", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID=""),
             create_dirs=False)


def test_real_environment_switches_base_url(env_file):
    settings = load(env_path=env_file(KIS_ENV="REAL"), create_dirs=False)
    assert settings.env.is_real
    assert "openapi.koreainvestment.com" in settings.env.base_url




def test_missing_env_file_raises(tmp_path):
    with pytest.raises(ConfigError, match=".env"):
        load(env_path=tmp_path / "nope.env", create_dirs=False)


def test_settings_yaml_values_are_loaded(env_file):
    settings = load(env_path=env_file(), create_dirs=False)
    assert settings.risk.stop_loss_pct < 0 < settings.risk.take_profit_pct
    assert settings.schedule.first_cycle < settings.schedule.last_new_buy
    assert settings.universe.watchlist


@pytest.mark.parametrize(
    "value,expected",
    [("", "(미설정)"), (None, "(미설정)"), ("abc", "***"), ("sk-ant-1234567890", "sk-a******90")],
)
def test_mask(value, expected):
    assert mask(value) == expected


def test_settings_yaml_exists_where_loader_expects_it():
    assert (CONFIG_DIR / "settings.yaml").exists()


def test_mask_with_zero_tail_does_not_leak(env_file):
    """keep_tail=0 에 value[-0:] 을 쓰면 문자열 전체가 남는다 — 웹훅 URL 누출."""
    secret = "https://discord.com/api/webhooks/123456/SECRET-TOKEN-HERE"
    masked = mask(secret, 20, 0)
    assert "SECRET-TOKEN-HERE" not in masked
    assert masked == "https://discord.com/******"


def test_discord_webhook_is_masked_in_repr(env_file):
    webhook = "https://discord.com/api/webhooks/123456/SECRET-TOKEN-HERE"
    settings = load(env_path=env_file(NOTIFIER="discord", DISCORD_WEBHOOK_URL=webhook,
                                      TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID=""),
                    create_dirs=False)
    printed = repr(settings.env)
    assert "SECRET-TOKEN-HERE" not in printed, "print(load()) 이 웹훅 시크릿을 노출하면 안 됩니다"


# --------------------------------------------------------------------------- #
# ai.pricing
# --------------------------------------------------------------------------- #


def test_settings_yaml_pricing_is_loaded(env_file):
    settings = load(env_path=env_file(), create_dirs=False)
    assert settings.ai.pricing, "settings.yaml 의 ai.pricing 이 읽혀야 합니다"
    for rates in settings.ai.pricing.values():
        assert len(rates) == 2 and all(value >= 0 for value in rates)


def test_malformed_pricing_is_reported(env_file, tmp_path):
    import yaml

    from config.loader import CONFIG_DIR

    raw = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    raw["ai"]["pricing"] = {"bad-model": "비싸요"}
    broken = tmp_path / "settings.yaml"
    broken.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError, match="ai.pricing"):
        load(env_path=env_file(), settings_path=broken, create_dirs=False)
