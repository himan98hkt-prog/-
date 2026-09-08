"""대시보드 라우트 테스트 — 화면이 뜨는지, 위험한 동작이 막히는지."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from dashboard.app import create_app
from dashboard.env_file import write_env
from utils.db import connect, init_db, record_ai_usage, update_bot_state

KST = ZoneInfo("Asia/Seoul")
NOW = datetime.now(KST)

FULL_ENV = {
    "KIS_APP_KEY": "PSkey1234567", "KIS_APP_SECRET": "secret1234567",
    "KIS_ACCOUNT_NO": "50123456", "KIS_ACCOUNT_PRODUCT_CD": "01",
    "ANTHROPIC_API_KEY": "sk-ant-test1234", "CLAUDE_MODEL": "claude-sonnet-5",
    "GEMINI_API_KEY": "AIzatest1234", "GEMINI_MODEL": "gemini-2.5-pro",
    "NOTIFIER": "telegram", "TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "999",
}


@pytest.fixture
def app(tmp_path):
    """설정·DB 를 임시 경로로 돌린 앱."""
    instance = create_app(testing=True)
    instance.config.update(
        ENV_PATH=tmp_path / ".env",
        DB_PATH=tmp_path / "trader.db",
        DATA_DIR=tmp_path,
        LOG_DIR=tmp_path / "logs",
    )
    init_db(instance.config["DB_PATH"])
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def seed(app, *, with_positions: bool = True) -> None:
    db = app.config["DB_PATH"]
    conn = connect(db)
    if with_positions:
        conn.execute(
            """INSERT INTO positions (code,name,qty,avg_price,current_price,eval_amount,
                                      pnl_amount,pnl_pct,first_bought_at,updated_at)
               VALUES ('005930','삼성전자',12,70000,76300,915600,75600,9.0,?,?)""",
            (NOW.isoformat(timespec="seconds"), NOW.isoformat(timespec="seconds")),
        )
    conn.execute(
        """INSERT INTO daily_pnl (date,start_equity,end_equity,realized_pnl,unrealized_pnl,
                                  total_pnl_pct,buy_count,sell_count,updated_at)
           VALUES (?,5000000,5060000,0,60000,1.2,1,0,?)""",
        (NOW.strftime("%Y-%m-%d"), NOW.isoformat(timespec="seconds")),
    )
    conn.execute(
        """INSERT INTO decisions (cycle_id,code,name,holding,claude_action,claude_confidence,
                                  claude_ok,gemini_action,gemini_confidence,gemini_ok,
                                  final_action,final_weight_pct,risk_passed,risk_reason,created_at)
           VALUES ('c1','005930','삼성전자',1,'BUY',0.8,1,'BUY',0.7,1,'STRONG_BUY',15,0,
                   '당일 이미 매수한 종목',?)""",
        (NOW.isoformat(timespec="seconds"),),
    )
    conn.close()
    record_ai_usage(db, cycle_id="c1", code="005930", agent="claude", model="claude-sonnet-5",
                    input_tokens=2800, output_tokens=400, cost_usd=0.0096, ok=True, elapsed_sec=3.0)
    update_bot_state(db, status="RUNNING", pid=1, kis_env="VTS", dry_run=1,
                     last_cycle_label="10:05", last_cycle_codes=5,
                     next_cycle_at=(NOW + timedelta(minutes=25)).isoformat(timespec="seconds"))


# --------------------------------------------------------------------------- #
# 첫 실행 흐름
# --------------------------------------------------------------------------- #


def test_root_redirects_to_setup_when_keys_missing(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/setup" in response.headers["Location"]


def test_setup_renders_without_env_file(client):
    response = client.get("/setup?first=1")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "APP KEY" in body and "Anthropic API 키" in body


def test_health_always_ok(client):
    assert client.get("/health").get_json() == {"ok": True}


# --------------------------------------------------------------------------- #
# 설정 저장
# --------------------------------------------------------------------------- #


def test_saving_keys_makes_dashboard_reachable(app, client):
    client.post("/setup", data=FULL_ENV)
    assert client.get("/").status_code == 200


def test_saved_secret_is_masked_on_the_page(app, client):
    client.post("/setup", data={**FULL_ENV, "ANTHROPIC_API_KEY": "sk-ant-VERYSECRET99"})
    body = client.get("/setup").get_data(as_text=True)
    assert "sk-ant-VERYSECRET99" not in body, "원문이 HTML 에 실리면 안 됩니다"
    assert "sk-a******99" in body


def test_blank_secret_does_not_wipe_saved_value(app, client):
    client.post("/setup", data={**FULL_ENV, "ANTHROPIC_API_KEY": "sk-ant-keepme123"})
    client.post("/setup", data={**FULL_ENV, "ANTHROPIC_API_KEY": ""})

    from dashboard.env_file import read_env

    assert read_env(app.config["ENV_PATH"])["ANTHROPIC_API_KEY"] == "sk-ant-keepme123"


# --------------------------------------------------------------------------- #
# 대시보드 화면
# --------------------------------------------------------------------------- #


def test_dashboard_shows_positions_and_decisions(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    seed(app)

    body = client.get("/").get_data(as_text=True)
    assert "삼성전자" in body
    assert "STRONG_BUY" in body
    assert "당일 이미 매수한 종목" in body, "리스크 거부 사유가 보여야 합니다"
    assert "+1.20%" in body or "+1.2" in body
    assert "<svg" in body, "차트가 렌더링돼야 합니다"


def test_dashboard_works_with_empty_database(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    body = client.get("/").get_data(as_text=True)
    assert "보유 중인 종목이 없습니다" in body
    assert "아직 판단 기록이 없습니다" in body


def test_api_status_returns_summary(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    seed(app)

    payload = client.get("/api/status").get_json()
    assert payload["ready"] is True
    assert payload["overview"]["position_count"] == 1
    assert payload["overview"]["ai_calls"] == 1
    assert payload["runtime"]["stopped"] is False


def test_api_status_does_not_leak_secrets(app, client):
    write_env(app.config["ENV_PATH"], {**FULL_ENV, "ANTHROPIC_API_KEY": "sk-ant-LEAKTEST"})
    seed(app)
    assert "sk-ant-LEAKTEST" not in client.get("/api/status").get_data(as_text=True)


# --------------------------------------------------------------------------- #
# 긴급 정지
# --------------------------------------------------------------------------- #


def test_stop_and_resume_toggle_the_flag(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    stop_file = app.config["DATA_DIR"] / "STOP"

    client.post("/control/stop")
    assert stop_file.exists()
    assert "긴급 정지 상태입니다" in client.get("/").get_data(as_text=True)

    client.post("/control/resume")
    assert not stop_file.exists()


def test_unknown_control_action_is_404(client):
    assert client.post("/control/selfdestruct").status_code == 404


# --------------------------------------------------------------------------- #
# CSRF
# --------------------------------------------------------------------------- #


def test_post_without_csrf_token_is_rejected(tmp_path):
    """로컬 앱이라도 다른 사이트가 POST 를 날릴 수 있다."""
    app = create_app(testing=False)
    app.config.update(ENV_PATH=tmp_path / ".env", DB_PATH=tmp_path / "trader.db",
                      DATA_DIR=tmp_path, LOG_DIR=tmp_path / "logs")
    init_db(app.config["DB_PATH"])

    response = app.test_client().post("/control/stop")
    assert response.status_code == 400
    assert not (tmp_path / "STOP").exists(), "토큰 없이 매매를 멈출 수 없어야 합니다"


def test_form_includes_csrf_token(tmp_path):
    app = create_app(testing=False)
    app.config.update(ENV_PATH=tmp_path / ".env", DB_PATH=tmp_path / "trader.db",
                      DATA_DIR=tmp_path, LOG_DIR=tmp_path / "logs")
    init_db(app.config["DB_PATH"])
    body = app.test_client().get("/setup").get_data(as_text=True)
    assert 'name="csrf"' in body


def test_post_with_wrong_csrf_token_is_rejected(tmp_path):
    app = create_app(testing=False)
    app.config.update(ENV_PATH=tmp_path / ".env", DB_PATH=tmp_path / "trader.db",
                      DATA_DIR=tmp_path, LOG_DIR=tmp_path / "logs")
    init_db(app.config["DB_PATH"])
    client = app.test_client()
    client.get("/setup")  # 세션에 토큰 생성

    assert client.post("/control/stop", data={"csrf": "위조된-토큰"}).status_code == 400
    assert not (tmp_path / "STOP").exists()


def test_post_with_valid_csrf_token_succeeds(tmp_path):
    import re

    app = create_app(testing=False)
    app.config.update(ENV_PATH=tmp_path / ".env", DB_PATH=tmp_path / "trader.db",
                      DATA_DIR=tmp_path, LOG_DIR=tmp_path / "logs")
    init_db(app.config["DB_PATH"])
    client = app.test_client()

    body = client.get("/setup").get_data(as_text=True)
    token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)

    assert client.post("/control/stop", data={"csrf": token}).status_code == 302
    assert (tmp_path / "STOP").exists()


# --------------------------------------------------------------------------- #
# 리뷰 지적 사항 회귀
# --------------------------------------------------------------------------- #


def test_rejected_orders_do_not_inflate_order_count(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    conn = connect(app.config["DB_PATH"])
    for status in ("FILLED", "REJECTED", "REJECTED"):
        conn.execute(
            """INSERT INTO orders (cycle_id,order_no,code,name,side,order_type,qty,price,
                                   filled_qty,filled_price,status,dry_run,kis_env,created_at,updated_at)
               VALUES ('c1','O1','005930','삼성전자','BUY','market',1,100,1,100,?,0,'VTS',?,?)""",
            (status, NOW.isoformat(timespec="seconds"), NOW.isoformat(timespec="seconds")),
        )
    conn.close()

    overview = client.get("/api/status").get_json()["overview"]
    assert overview["buy_count"] == 1, "거부된 주문은 세지 않습니다"
    assert overview["rejected_orders"] == 2


def test_setup_works_on_database_without_bot_state(app, client, tmp_path):
    """구버전 DB(bot_state 없음)에서도 설정 화면이 떠야 한다 — 유일한 복구 경로."""
    conn = connect(app.config["DB_PATH"])
    conn.execute("DROP TABLE bot_state")
    conn.close()
    assert client.get("/setup").status_code == 200


def test_config_error_is_shown_on_dashboard(app, client, monkeypatch):
    from config.loader import ConfigError

    write_env(app.config["ENV_PATH"], FULL_ENV)
    monkeypatch.setattr(
        "dashboard.app.load",
        lambda **kw: (_ for _ in ()).throw(ConfigError("risk.max_positions: 1 이상이어야 합니다")),
    )
    body = client.get("/").get_data(as_text=True)
    assert "설정을 읽지 못했습니다" in body
    assert "max_positions" in body


def test_discord_only_setup_reaches_dashboard(app, client):
    """디스코드 사용자가 /setup 으로 무한 리다이렉트되면 안 된다."""
    client.post("/setup", data={
        "KIS_APP_KEY": "k", "KIS_APP_SECRET": "s", "KIS_ACCOUNT_NO": "50123456",
        "KIS_ACCOUNT_PRODUCT_CD": "01", "ANTHROPIC_API_KEY": "sk-ant-x",
        "CLAUDE_MODEL": "claude-sonnet-5", "GEMINI_API_KEY": "AIza-x",
        "GEMINI_MODEL": "gemini-2.5-pro", "NOTIFIER": "discord",
        "DISCORD_WEBHOOK_URL": "https://discord.test/hook",
    })
    assert client.get("/").status_code == 200
