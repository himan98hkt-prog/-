"""테스트 공통 픽스처. 외부 API는 전부 mock한다."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import EnvConfig  # noqa: E402
from trading.kis_auth import TokenManager  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def make_env(**overrides) -> EnvConfig:
    defaults = dict(
        kis_env="VTS",
        dry_run=True,
        log_level="INFO",
        kis_app_key="APPKEY-TEST-0001",
        kis_app_secret="APPSECRET-TEST-0001",
        kis_account_no="50123456",
        kis_account_product_cd="01",
        anthropic_api_key="sk-ant-test",
        claude_model="claude-sonnet-5",
        claude_temperature=None,
        claude_effort=None,
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-pro",
        gemini_temperature=0.2,
        openai_api_key=None,
        openai_model="gpt-5.1",
        openai_temperature=None,
        notifier="telegram",
        telegram_bot_token="tg-token",
        telegram_chat_id="12345",
        discord_webhook_url=None,
    )
    defaults.update(overrides)
    return EnvConfig(**defaults)


@pytest.fixture
def env() -> EnvConfig:
    return make_env()


@pytest.fixture
def real_env() -> EnvConfig:
    return make_env(kis_env="REAL")


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    return tmp_path / "token.json"


@pytest.fixture
def auth(env, token_path, monkeypatch) -> TokenManager:
    """토큰 발급을 건너뛴 인증 매니저 (유효 토큰이 메모리에 있는 상태)."""
    manager = TokenManager(env, token_path)
    manager._token = "TEST-ACCESS-TOKEN"
    manager._expires_at = datetime.now(KST) + timedelta(hours=6)
    return manager


class FakeResponse:
    """requests.Response 대역."""

    def __init__(self, payload=None, status_code: int = 200, headers: dict | None = None, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text or (str(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def ok(output=None, **extra):
    """rt_cd=0 성공 응답 페이로드."""
    payload = {"rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다."}
    if output is not None:
        payload["output"] = output
    payload.update(extra)
    return payload


def fail(msg_cd: str = "40580000", msg1: str = "모의투자 장운영시간이 아닙니다"):
    return {"rt_cd": "1", "msg_cd": msg_cd, "msg1": msg1}


@pytest.fixture
def settings_obj(tmp_path, env):
    """실제 settings.yaml 값 + 임시 경로를 쓰는 Settings 객체."""
    from config.loader import CONFIG_DIR, AiConfig, RiskConfig, ScheduleConfig, Settings, UniverseConfig
    import yaml
    from datetime import time as dt_time

    raw = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    universe_raw, schedule_raw = raw["universe"], raw["schedule"]
    risk_raw, ai_raw = raw["risk"], raw["ai"]

    def as_time(text: str) -> dt_time:
        hour, minute = str(text).split(":")
        return dt_time(int(hour), int(minute))

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)

    return Settings(
        env=env,
        universe=UniverseConfig(
            mode=universe_raw["mode"],
            watchlist=list(universe_raw["watchlist"]),
            volume_rank_top_n=universe_raw["volume_rank_top_n"],
            exclude_keywords=list(universe_raw["exclude_keywords"]),
            min_price=universe_raw["min_price"],
            max_candidates_per_cycle=universe_raw["max_candidates_per_cycle"],
        ),
        schedule=ScheduleConfig(
            universe_refresh=as_time(schedule_raw["universe_refresh"]),
            first_cycle=as_time(schedule_raw["first_cycle"]),
            cycle_interval_min=schedule_raw["cycle_interval_min"],
            last_new_buy=as_time(schedule_raw["last_new_buy"]),
            eod_review=as_time(schedule_raw["eod_review"]),
            daily_report=as_time(schedule_raw["daily_report"]),
        ),
        risk=RiskConfig(**risk_raw),
        ai=AiConfig(**ai_raw),
        paths={"base": tmp_path, "config": CONFIG_DIR, "data": tmp_path,
               "snapshots": snapshots, "logs": tmp_path / "logs",
               "token": tmp_path / "token.json", "db": tmp_path / "trader.db",
               "holidays": tmp_path / "holidays.txt"},
    )
