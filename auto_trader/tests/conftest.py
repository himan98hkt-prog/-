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
        gemini_api_key="gemini-test",
        gemini_model="gemini-2.5-pro",
        naver_client_id=None,
        naver_client_secret=None,
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
