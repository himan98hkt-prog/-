"""대시보드 라우트 테스트 — 화면이 뜨는지, 위험한 동작이 막히는지."""

from __future__ import annotations

from pathlib import Path

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from dashboard.app import create_app
from dashboard.env_file import write_env
from utils.db import connect, init_db, record_ai_usage, session, update_bot_state

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


@pytest.fixture(autouse=True)
def never_really_exit(monkeypatch):
    """업데이트 경로는 진짜로 os._exit 를 부른다 — 테스트 실행기까지 죽는다.

    개별 테스트가 패치를 깜빡해도 러너가 조용히 사라지지 않도록 여기서 막는다.
    """
    from dashboard import restart

    monkeypatch.setattr(restart, "request_restart", lambda *a, **kw: None)


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
    assert "아직 매수한 종목이 없습니다" in body
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
    # 요청을 수행하지 않는 것이 핵심이다. 오류 화면 대신 원래 화면으로 돌려보낸다.
    assert response.status_code == 302
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

    assert client.post("/control/stop", data={"csrf": "위조된-토큰"}).status_code == 302
    assert not (tmp_path / "STOP").exists(), "위조된 토큰으로 매매를 멈출 수 없어야 합니다"


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


# --------------------------------------------------------------------------- #
# 시작 · 재시작 · 종료 (원스텝 적용)
# --------------------------------------------------------------------------- #


def test_start_is_blocked_until_keys_are_filled(app, client):
    """설정이 안 끝났는데 매매를 시작하면 안 된다."""
    response = client.post("/control/start")
    assert response.status_code == 302
    assert "/setup" in response.headers["Location"]


def test_start_launches_the_bot(app, client, monkeypatch):
    from dashboard import process

    write_env(app.config["ENV_PATH"], FULL_ENV)
    launched = {}

    def fake_start(base_dir, data_dir, log_dir):
        launched["base"] = base_dir
        return process.ControlResult(True, "자동매매를 시작했습니다.")

    monkeypatch.setattr(process, "start", fake_start)
    client.post("/control/start", follow_redirects=False)
    assert launched, "main.py 를 띄우려고 시도해야 합니다"


def test_start_clears_stop_flag_first(app, client, monkeypatch):
    """정지 상태로 켜면 아무것도 안 하므로, 시작 시 플래그를 푼다."""
    from dashboard import process

    write_env(app.config["ENV_PATH"], FULL_ENV)
    (app.config["DATA_DIR"] / "STOP").write_text("이전 정지")
    monkeypatch.setattr(process, "start", lambda *a: process.ControlResult(True, "시작"))

    client.post("/control/start")
    assert not (app.config["DATA_DIR"] / "STOP").exists()


def test_restart_applies_new_keys(app, client, monkeypatch):
    from dashboard import process

    write_env(app.config["ENV_PATH"], FULL_ENV)
    calls = []
    monkeypatch.setattr(process, "restart",
                        lambda *a: (calls.append("restart"), process.ControlResult(True, "재시작"))[1])

    client.post("/control/restart")
    assert calls == ["restart"]


def test_shutdown_stops_the_process(app, client, monkeypatch):
    from dashboard import process

    write_env(app.config["ENV_PATH"], FULL_ENV)
    calls = []
    monkeypatch.setattr(process, "stop",
                        lambda *a: (calls.append("stop"), process.ControlResult(True, "종료"))[1])

    client.post("/control/shutdown")
    assert calls == ["stop"]


def test_saving_keys_while_running_warns_about_restart(app, client, monkeypatch):
    from dashboard import process

    write_env(app.config["ENV_PATH"], FULL_ENV)
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)

    response = client.post("/setup", data={**FULL_ENV, "KIS_ACCOUNT_NO": "50999999"},
                           follow_redirects=True)
    assert "재시작" in response.get_data(as_text=True), "실행 중이면 재적용 안내가 떠야 합니다"


def test_start_button_shown_when_not_running(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    body = client.get("/").get_data(as_text=True)
    assert "자동매매 시작" in body
    assert "재시작 (설정 반영)" not in body


def test_running_bot_shows_restart_and_shutdown(app, client, monkeypatch):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    (app.config["DATA_DIR"] / "trader.pid").write_text("1")  # PID 1 = 살아 있음

    body = client.get("/").get_data(as_text=True)
    assert "재시작 (설정 반영)" in body
    assert "봇 종료" in body
    assert "자동매매 시작" not in body


# --------------------------------------------------------------------------- #
# 업데이트 버튼 — 키를 다시 넣지 않아도 되는 것이 핵심이다
# --------------------------------------------------------------------------- #


def post_with_csrf(client, path: str) -> str:
    """CSRF 토큰을 받아 POST 하고, 리다이렉트를 따라가 flash 메시지를 읽는다."""
    import re

    body = client.get("/setup").get_data(as_text=True)
    token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
    response = client.post(path, data={"csrf": token}, follow_redirects=True)
    return response.get_data(as_text=True)


def test_update_button_applies_and_reports(client, monkeypatch, tmp_path):
    from dashboard import process
    from utils import updater

    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(updater, "apply_update", lambda base, **kw: updater.UpdateResult(
        updated=True, version=updater.Version(sha="c" * 40, message="새 기능"),
        changed=["main.py"], notes=[], deps_changed=False))

    page = post_with_csrf(client, "/control/update")
    assert "업데이트했습니다" in page
    assert "키와 매매 기록은 그대로" in page


def test_update_failure_leaves_a_plain_message(client, monkeypatch):
    from dashboard import process
    from utils import updater

    monkeypatch.setattr(process, "is_running", lambda data_dir: False)

    def boom(base, **kw):
        raise updater.UpdateError("인터넷 연결을 확인하세요")

    monkeypatch.setattr(updater, "apply_update", boom)

    page = post_with_csrf(client, "/control/update")
    assert "업데이트하지 못했습니다" in page and "인터넷 연결" in page


def test_running_bot_is_stopped_then_restarted(client, monkeypatch):
    from dashboard import process
    from utils import updater

    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda data_dir: (
        calls.append("stop"), process.ControlResult(True, "종료했습니다"))[1])
    monkeypatch.setattr(process, "start", lambda base, data, log: (
        calls.append("start"), process.ControlResult(True, "시작했습니다"))[1])
    monkeypatch.setattr(updater, "apply_update", lambda base, **kw: updater.UpdateResult(
        updated=True, version=updater.Version(sha="d" * 40, message="수정"),
        changed=[], notes=[], deps_changed=False))

    post_with_csrf(client, "/control/update")
    assert calls == ["stop", "start"], "멈췄다가 새 코드로 다시 띄워야 합니다"


def test_failed_update_restarts_the_bot_it_stopped(client, monkeypatch):
    """업데이트가 실패했다고 매매를 멈춰둔 채로 끝내면 안 된다."""
    from dashboard import process
    from utils import updater

    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda data_dir: (
        calls.append("stop"), process.ControlResult(True, "종료"))[1])
    monkeypatch.setattr(process, "start", lambda base, data, log: (
        calls.append("start"), process.ControlResult(True, "시작"))[1])

    def boom(base, **kw):
        raise updater.UpdateError("서버 오류")

    monkeypatch.setattr(updater, "apply_update", boom)

    page = post_with_csrf(client, "/control/update")
    assert calls == ["stop", "start"]
    assert "기존 버전으로 다시 시작" in page


def test_update_aborts_when_bot_cannot_be_stopped(client, monkeypatch):
    from dashboard import process
    from utils import updater

    applied: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda data_dir: process.ControlResult(False, "응답 없음"))
    monkeypatch.setattr(updater, "apply_update",
                        lambda base, **kw: applied.append("x"))

    page = post_with_csrf(client, "/control/update")
    assert applied == [], "멈추지 못했으면 코드를 갈아끼우면 안 됩니다"
    assert "멈추지 못했습니다" in page


def test_dependency_change_asks_for_a_manual_restart(client, monkeypatch):
    from dashboard import process
    from utils import updater

    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(updater, "apply_update", lambda base, **kw: updater.UpdateResult(
        updated=True, version=updater.Version(sha="e" * 40, message="패키지 추가"),
        changed=[], notes=[], deps_changed=True))

    page = post_with_csrf(client, "/control/update")
    assert "start.bat" in page


def test_update_restarts_the_dashboard_itself(client, monkeypatch):
    """코드만 갈아끼우면 화면은 그대로다 — 대시보드 프로세스도 갈아야 한다."""
    from dashboard import process, restart
    from utils import updater

    asked: list[bool] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(restart, "request_restart", lambda *a, **kw: asked.append(True))
    monkeypatch.setattr(updater, "apply_update", lambda base, **kw: updater.UpdateResult(
        updated=True, version=updater.Version(sha="f" * 40, message="새 입력칸"),
        changed=["dashboard/"], notes=[], deps_changed=False))

    page = post_with_csrf(client, "/control/update")
    assert asked == [True], "업데이트 후 대시보드가 스스로 다시 뜨지 않습니다"
    assert "새 창으로 대시보드가 다시 뜹니다" in page


def test_dependency_change_skips_self_restart(client, monkeypatch):
    """새 패키지는 설치가 먼저다 — 그냥 다시 띄우면 import 에러가 난다."""
    from dashboard import process, restart
    from utils import updater

    asked: list[bool] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(restart, "request_restart", lambda *a, **kw: asked.append(True))
    monkeypatch.setattr(updater, "apply_update", lambda base, **kw: updater.UpdateResult(
        updated=True, version=updater.Version(sha="a" * 40, message="패키지 추가"),
        changed=[], notes=[], deps_changed=True))

    page = post_with_csrf(client, "/control/update")
    assert asked == []
    assert "start.bat" in page


def test_failed_update_does_not_restart_the_dashboard(client, monkeypatch):
    from dashboard import process, restart
    from utils import updater

    asked: list[bool] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    monkeypatch.setattr(restart, "request_restart", lambda *a, **kw: asked.append(True))

    def boom(base, **kw):
        raise updater.UpdateError("연결 실패")

    monkeypatch.setattr(updater, "apply_update", boom)
    post_with_csrf(client, "/control/update")
    assert asked == []


# --------------------------------------------------------------------------- #
# 모의투자 ↔ 실전 전환
# --------------------------------------------------------------------------- #


def _write_env(app, **values):
    from dashboard.env_file import write_env

    write_env(app.config["ENV_PATH"], {**FULL_ENV, **values})


def test_switch_to_real_updates_env(client, app, monkeypatch):
    from dashboard import process
    from dashboard.env_file import read_env

    _write_env(app, KIS_ENV="VTS")
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)

    page = post_with_csrf(client, "/control/mode_real")
    assert read_env(app.config["ENV_PATH"])["KIS_ENV"] == "REAL"
    assert "실제 자금으로 주문이 나갑니다" in page


def test_switch_to_vts_updates_env(client, app, monkeypatch):
    from dashboard import process
    from dashboard.env_file import read_env

    _write_env(app, KIS_ENV="REAL")
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)

    page = post_with_csrf(client, "/control/mode_vts")
    assert read_env(app.config["ENV_PATH"])["KIS_ENV"] == "VTS"
    assert "가짜 돈" in page


def test_switching_warns_when_the_account_is_unknown(client, app, monkeypatch):
    """모의계좌와 실계좌는 번호가 다르다 — 안 바꾸면 인증부터 실패한다."""
    from dashboard import process

    _write_env(app, KIS_ENV="VTS")
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    assert "계좌번호를 아직 모릅니다" in post_with_csrf(client, "/control/mode_real")


def test_switching_swaps_a_remembered_account(client, app, monkeypatch):
    """한 번 넣어 둔 번호는 환경을 오갈 때 저절로 따라와야 한다."""
    from dashboard import process
    from dashboard.env_file import read_env

    _write_env(app, KIS_ENV="VTS", KIS_ACCOUNT_NO="50204881",
               KIS_ACCOUNT_NO_REAL="12345678")
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)

    assert "12345678" in post_with_csrf(client, "/control/mode_real")
    env = read_env(app.config["ENV_PATH"])
    assert env["KIS_ACCOUNT_NO"] == "12345678"
    assert env["KIS_ENV"] == "REAL"

    # 되돌아오면 모의계좌 번호도 그대로 살아 있어야 한다
    post_with_csrf(client, "/control/mode_vts")
    env = read_env(app.config["ENV_PATH"])
    assert env["KIS_ACCOUNT_NO"] == "50204881"
    assert env["KIS_ENV"] == "VTS"


def test_switching_restarts_a_running_bot(client, app, monkeypatch):
    """예전 도메인을 물고 있는 프로세스가 남으면 다른 계좌로 주문이 나간다."""
    from dashboard import process

    _write_env(app, KIS_ENV="VTS")
    calls: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda data_dir: (
        calls.append("stop"), process.ControlResult(True, "종료"))[1])
    monkeypatch.setattr(process, "start", lambda base, data, log: (
        calls.append("start"), process.ControlResult(True, "시작"))[1])

    post_with_csrf(client, "/control/mode_real")
    assert calls == ["stop", "start"]


def test_switching_aborts_when_bot_will_not_stop(client, app, monkeypatch):
    from dashboard import process

    _write_env(app, KIS_ENV="VTS")
    monkeypatch.setattr(process, "is_running", lambda data_dir: True)
    monkeypatch.setattr(process, "stop", lambda data_dir: process.ControlResult(False, "응답 없음"))
    started: list[str] = []
    monkeypatch.setattr(process, "start", lambda *a: started.append("x"))

    page = post_with_csrf(client, "/control/mode_real")
    assert started == []
    assert "예전 설정으로 계속 돌고 있습니다" in page


def test_switching_to_the_same_mode_is_a_no_op(client, app, monkeypatch):
    from dashboard import process

    _write_env(app, KIS_ENV="VTS")
    monkeypatch.setattr(process, "is_running", lambda data_dir: False)
    assert "이미 모의투자 입니다" in post_with_csrf(client, "/control/mode_vts")


def test_status_page_shows_the_current_mode(client, app):
    _write_env(app, KIS_ENV="REAL")
    seed(app)
    body = client.get("/").get_data(as_text=True)
    assert "실전 (REAL)" in body and "mode-real" in body


def test_status_page_shows_the_install_folder(client, app):
    """폴더가 여러 개일 때 어느 것을 보고 있는지 알 수 있어야 한다."""
    _write_env(app)
    seed(app)
    body = client.get("/").get_data(as_text=True)
    assert str(app.config["BASE_DIR"]) in body


# --------------------------------------------------------------------------- #
# 현황 화면은 막지 않는다 + 진단 화면
# --------------------------------------------------------------------------- #


def test_status_page_opens_even_with_missing_settings(client, app):
    """막아 세우면 무엇이 문제인지 볼 방법이 없어진다."""
    _write_env(app, KIS_ACCOUNT_NO="__CLEAR__")
    seed(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200, "설정이 덜 됐다고 현황 화면을 막으면 안 됩니다"


def test_status_page_names_the_missing_settings(client, app):
    _write_env(app, KIS_ACCOUNT_NO="__CLEAR__")
    seed(app)
    body = client.get("/").get_data(as_text=True)
    assert "계좌번호 앞 8자리" in body and "KIS_ACCOUNT_NO" in body


def test_start_button_is_disabled_when_settings_are_missing(client, app):
    _write_env(app, KIS_ACCOUNT_NO="__CLEAR__")
    seed(app)
    body = client.get("/").get_data(as_text=True)
    assert "disabled" in body.split("자동매매 시작")[0][-200:]


def test_start_button_is_enabled_when_complete(client, app):
    _write_env(app)
    seed(app)
    body = client.get("/").get_data(as_text=True)
    assert "설정이" not in body.split("자동매매 시작")[0][-200:]


def test_first_run_still_goes_to_setup(client, app):
    """.env 자체가 없으면 설정부터가 맞다."""
    from pathlib import Path as _Path

    _Path(app.config["ENV_PATH"]).unlink(missing_ok=True)
    assert client.get("/", follow_redirects=False).status_code == 302


def test_diagnose_lists_every_field(client, app):
    _write_env(app)
    body = client.get("/diagnose").get_data(as_text=True)
    for key in ("KIS_APP_KEY", "CLAUDE_MODEL", "GEMINI_MODEL", "OPENAI_API_KEY"):
        assert key in body


def test_diagnose_marks_the_empty_required_ones(client, app):
    _write_env(app, KIS_ACCOUNT_NO="__CLEAR__")
    body = client.get("/diagnose").get_data(as_text=True)
    assert "비었음" in body and "필수 항목 1개가 비어" in body


def test_diagnose_never_shows_secret_values(client, app):
    _write_env(app, KIS_APP_SECRET="비밀값이라노출금지1234")
    body = client.get("/diagnose").get_data(as_text=True)
    assert "비밀값이라노출금지1234" not in body
    assert "채워짐" in body


def test_diagnose_shows_where_files_are(client, app):
    _write_env(app)
    body = client.get("/diagnose").get_data(as_text=True)
    assert str(app.config["ENV_PATH"]) in body
    assert str(app.config["BASE_DIR"]) in body


def test_diagnose_says_all_clear_when_complete(client, app):
    _write_env(app)
    assert "필수 항목이 모두 채워져" in client.get("/diagnose").get_data(as_text=True)


# --------------------------------------------------------------------------- #
# 텔레그램 채팅 ID 자동 찾기
# --------------------------------------------------------------------------- #


def test_finds_and_fills_the_chat_id(client, app, monkeypatch):
    import dashboard.app as mod
    from dashboard.env_file import read_env

    _write_env(app, TELEGRAM_CHAT_ID="__CLEAR__")
    monkeypatch.setattr(mod, "find_telegram_chats", lambda token: [("8786453781", "홍길동")])

    page = post_with_csrf(client, "/setup/telegram-chat-id")
    assert read_env(app.config["ENV_PATH"])["TELEGRAM_CHAT_ID"] == "8786453781"
    assert "찾아 채웠습니다" in page and "홍길동" in page


def test_tells_the_user_to_message_the_bot_first(client, app, monkeypatch):
    import dashboard.app as mod

    _write_env(app)
    monkeypatch.setattr(mod, "find_telegram_chats", lambda token: [])

    page = post_with_csrf(client, "/setup/telegram-chat-id")
    assert "봇에게 온 메시지가 없습니다" in page
    assert "/start" in page


def test_mentions_other_chats_without_overwriting(client, app, monkeypatch):
    import dashboard.app as mod
    from dashboard.env_file import read_env

    _write_env(app)
    monkeypatch.setattr(mod, "find_telegram_chats",
                        lambda token: [("111", "나"), ("-222", "우리 그룹")])

    page = post_with_csrf(client, "/setup/telegram-chat-id")
    assert read_env(app.config["ENV_PATH"])["TELEGRAM_CHAT_ID"] == "111"
    assert "-222" in page and "우리 그룹" in page


def test_needs_the_bot_token_first(client, app, monkeypatch):
    _write_env(app, TELEGRAM_BOT_TOKEN="__CLEAR__")
    page = post_with_csrf(client, "/setup/telegram-chat-id")
    assert "봇 토큰을 저장하세요" in page


def test_diagnose_shows_the_bot_startup_log(client, app):
    """시작 버튼이 실패했을 때 원인을 한 화면에서 볼 수 있어야 한다."""
    log_dir = Path(app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "stdout.log").write_text(
        "2026-09-16 [ERROR] auto_trader.main: 기동 실패: 토큰 발급 요청 실패\n", encoding="utf-8")
    _write_env(app)

    body = client.get("/diagnose").get_data(as_text=True)
    assert "자동매매 기동 기록" in body
    assert "기동 실패: 토큰 발급 요청 실패" in body


def test_diagnose_says_when_the_bot_never_ran(client, app):
    _write_env(app)
    body = client.get("/diagnose").get_data(as_text=True)
    assert "한 번도 시작하지 않았습니다" in body


def test_session_key_survives_restart(tmp_path):
    """대시보드가 다시 떠도 열려 있던 탭이 살아 있어야 한다.

    업데이트 버튼이 스스로 재시작하므로, 키가 매번 바뀌면 그 직후 누르는
    버튼마다 CSRF 오류가 난다.
    """
    from dashboard.app import _session_key

    first = _session_key(tmp_path)
    assert len(first) >= 32
    assert _session_key(tmp_path) == first  # 재기동해도 같은 키
    assert (tmp_path / "session.key").exists()


def test_stale_csrf_redirects_instead_of_dead_ending(tmp_path, monkeypatch):
    """낡은 토큰이어도 막다른 오류 화면 대신 원래 화면으로 돌려보낸다."""
    import dashboard.app as module

    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    app = module.create_app(testing=False)
    app.config["TESTING"] = False
    app.config["DATA_DIR"] = tmp_path
    app.config["ENV_PATH"] = tmp_path / ".env"

    with app.test_client() as client:
        response = client.post("/control", data={"action": "start", "csrf": "틀린토큰"})

    assert response.status_code == 302, "400 오류 화면이면 사용자가 빠져나갈 길이 없다"


# --- 화면이 깨졌을 때 --------------------------------------------------------- #

def test_one_broken_card_does_not_blank_the_page(tmp_path, monkeypatch):
    """칸 하나가 터졌다고 화면 전체가 500 이면 사용자에게 아무 정보도 안 남는다."""
    import dashboard.app as module
    from dashboard import queries

    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(queries, "engine_accuracy",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("일부러 낸 오류")))
    init_db(tmp_path / "trader.db")
    env = tmp_path / ".env"
    env.write_text("KIS_ENV=VTS\nDRY_RUN=true\n", encoding="utf-8")

    app = module.create_app(testing=True)
    app.config.update(DB_PATH=tmp_path / "trader.db", DATA_DIR=tmp_path,
                      LOG_DIR=tmp_path / "logs", ENV_PATH=env)
    response = app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "일부러 낸 오류" in html, "무엇이 깨졌는지 알려주지 않았습니다"
    assert "단순 보유 대비" in html, "멀쩡한 칸까지 사라졌습니다"


def test_a_fatal_error_shows_the_cause(tmp_path, monkeypatch):
    """빈 '내부 서버 오류' 화면은 막다른 길이다."""
    import dashboard.app as module

    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    init_db(tmp_path / "trader.db")
    app = module.create_app(testing=False)
    app.config.update(DB_PATH=tmp_path / "trader.db", DATA_DIR=tmp_path,
                      LOG_DIR=tmp_path / "logs", ENV_PATH=module.ENV_PATH)

    @app.route("/boom")
    def boom():
        raise ValueError("치명적 오류 예시")

    response = app.test_client().get("/boom")
    html = response.get_data(as_text=True)

    assert response.status_code == 500
    assert "ValueError" in html and "치명적 오류 예시" in html
    assert "Traceback" in html, "원인을 복사해 전달할 수 없습니다"
    assert "update.bat" in html, "다음에 뭘 할지 알려주지 않았습니다"


def test_the_error_page_hides_secrets(tmp_path, monkeypatch):
    """오류 원문에 키가 섞여 들어갈 수 있다."""
    import dashboard.app as module
    from utils.logger import register_secret

    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    init_db(tmp_path / "trader.db")
    register_secret("sk-ant-super-secret-value")

    app = module.create_app(testing=False)
    app.config.update(DB_PATH=tmp_path / "trader.db", DATA_DIR=tmp_path,
                      LOG_DIR=tmp_path / "logs", ENV_PATH=module.ENV_PATH)

    @app.route("/leak")
    def leak():
        raise ValueError("키가 틀렸습니다: sk-ant-super-secret-value")

    html = app.test_client().get("/leak").get_data(as_text=True)
    assert "sk-ant-super-secret-value" not in html
    assert "REDACTED" in html


# --- 업데이트 버튼 (update.bat 과 같은 일을 하는가) ---------------------------- #

def _fake_release(files: dict[str, str]) -> bytes:
    """GitHub ZIP 대역 — repo/auto_trader/ 구조를 그대로 만든다."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, text in files.items():
            bundle.writestr(f"repo-main/auto_trader/{name}", text)
    return buffer.getvalue()


@pytest.fixture()
def installed(tmp_path, monkeypatch):
    """업데이트 버튼을 누를 수 있는 최소 설치본 + 네트워크 대역."""
    import json

    from utils import updater

    base = tmp_path / "install"
    for folder in ("config", "data", "logs", "utils"):
        (base / folder).mkdir(parents=True)
    (base / "main.py").write_text("print('old')\n", encoding="utf-8")
    (base / "requirements.txt").write_text("requests>=2.32.0\n", encoding="utf-8")
    (base / "config" / "loader.py").write_text("SCHEMA = 'old'\n", encoding="utf-8")
    (base / "config" / "settings.yaml").write_text("risk:\n  stop_loss_pct: -5\n",
                                                   encoding="utf-8")
    (base / ".env").write_text("KIS_ENV=VTS\nDRY_RUN=true\n", encoding="utf-8")

    incoming = {
        "main.py": "print('new')\n",
        "requirements.txt": "requests>=2.32.0\n",     # 의존성 변화 없음
        "config/loader.py": "SCHEMA = 'new'\n",
        "config/settings.yaml": "risk:\n  stop_loss_pct: -5\n",
    }
    state = {"zip": _fake_release(incoming), "sha": "abcdef1234567890",
             "message": "새 기능"}

    def fake_http(url, *, as_json=False):
        if as_json:
            return {"sha": state["sha"], "commit": {"message": state["message"]}}
        return state["zip"]

    monkeypatch.setattr(updater, "_http_get", fake_http)
    return {"base": base, "data": base / "data", "logs": base / "logs", "state": state}


def test_update_button_does_what_update_bat_does(installed, monkeypatch):
    """대시보드 하단 '업데이트' 버튼이 실제로 코드를 갈아 끼우는지.

    가장 자주 쓰는 버튼인데 그동안 테스트가 없었다.
    """
    import dashboard.app as module
    from dashboard import process, restart

    base, data, logs = installed["base"], installed["data"], installed["logs"]
    monkeypatch.setattr(module, "DATA_DIR", data)

    events: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda d: True)
    monkeypatch.setattr(process, "stop",
                        lambda d: events.append("봇 정지") or process.ControlResult(True, "종료"))
    monkeypatch.setattr(process, "start",
                        lambda b, d, l: events.append("봇 시작") or process.ControlResult(True, "시작"))
    monkeypatch.setattr(restart, "request_restart",
                        lambda b, p, **kw: events.append("대시보드 재시작"))

    app = module.create_app(testing=True)
    app.config.update(BASE_DIR=base, DATA_DIR=data, LOG_DIR=logs,
                      DB_PATH=data / "trader.db", ENV_PATH=base / ".env", PORT=8765)
    init_db(data / "trader.db")

    with app.test_request_context():
        module._apply_update(base, data, logs, 8765)

    assert (base / "main.py").read_text(encoding="utf-8") == "print('new')\n"
    # config/loader.py 가 갱신되지 않아 '없는 속성' 오류가 났던 적이 있다.
    assert (base / "config" / "loader.py").read_text(encoding="utf-8") == "SCHEMA = 'new'\n"
    # 순서가 중요하다 — 돌던 봇을 멈추고, 갈아 끼우고, 다시 띄운다.
    assert events == ["봇 정지", "봇 시작", "대시보드 재시작"]


def test_update_button_restarts_the_bot_even_when_it_fails(installed, monkeypatch):
    """멈춰만 놓고 끝내면 매매가 죽은 채로 남는다."""
    import dashboard.app as module
    from dashboard import process
    from utils import updater

    base, data, logs = installed["base"], installed["data"], installed["logs"]
    monkeypatch.setattr(module, "DATA_DIR", data)
    monkeypatch.setattr(updater, "_http_get",
                        lambda *a, **k: (_ for _ in ()).throw(
                            updater.UpdateError("인터넷 연결을 확인하세요")))

    events: list[str] = []
    monkeypatch.setattr(process, "is_running", lambda d: True)
    monkeypatch.setattr(process, "stop",
                        lambda d: events.append("정지") or process.ControlResult(True, "종료"))
    monkeypatch.setattr(process, "start",
                        lambda b, d, l: events.append("재시작") or process.ControlResult(True, "시작"))

    app = module.create_app(testing=True)
    app.config.update(BASE_DIR=base, DATA_DIR=data, LOG_DIR=logs,
                      DB_PATH=data / "trader.db", ENV_PATH=base / ".env", PORT=8765)
    init_db(data / "trader.db")

    with app.test_request_context():
        module._apply_update(base, data, logs, 8765)

    assert events == ["정지", "재시작"], "업데이트가 실패했는데 봇을 안 살렸습니다"
    assert (base / "main.py").read_text(encoding="utf-8") == "print('old')\n"


def test_update_button_keeps_user_settings(installed, monkeypatch):
    """직접 고친 매매 파라미터를 버튼이 덮어쓰면 안 된다."""
    import dashboard.app as module
    from dashboard import process, restart

    base, data, logs = installed["base"], installed["data"], installed["logs"]
    (base / "config" / "settings.yaml").write_text(
        "risk:\n  stop_loss_pct: -3   # 내가 고침\n", encoding="utf-8")
    monkeypatch.setattr(module, "DATA_DIR", data)
    monkeypatch.setattr(process, "is_running", lambda d: False)
    monkeypatch.setattr(restart, "request_restart", lambda b, p, **kw: None)

    app = module.create_app(testing=True)
    app.config.update(BASE_DIR=base, DATA_DIR=data, LOG_DIR=logs,
                      DB_PATH=data / "trader.db", ENV_PATH=base / ".env", PORT=8765)
    init_db(data / "trader.db")

    with app.test_request_context():
        module._apply_update(base, data, logs, 8765)

    assert "내가 고침" in (base / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert (base / ".env").read_text(encoding="utf-8") == "KIS_ENV=VTS\nDRY_RUN=true\n"


# --- 계속 쌓이는 표가 화면을 밀어내지 않는가 -------------------------------- #

def test_long_tables_scroll_inside_their_card():
    """판단 기록은 사이클마다 늘어난다. 카드 높이가 같이 늘면 아래 카드를
    보려고 한참 내려야 한다 — 표 안에서만 굴러야 한다."""
    root = Path(__file__).resolve().parent.parent
    page = (root / "dashboard" / "templates" / "index.html").read_text(encoding="utf-8")

    for heading in ("최근 AI 판단", "최근 주문</summary>", "리스크 규칙 차단"):
        start = page.index(heading)
        table = page.index("<table>", start)
        between = page[start:table]
        assert 'class="scroll-table"' in between, f"{heading} 표가 묶여 있지 않습니다"


def test_scroll_box_keeps_its_header_and_a_visible_bar():
    root = Path(__file__).resolve().parent.parent
    css = (root / "dashboard" / "static" / "style.css").read_text(encoding="utf-8")
    block = css[css.index(".scroll-table {"):]

    assert "max-height" in block and "overflow-y: auto" in block
    assert "position: sticky" in block, "굴리다 보면 어느 열인지 알 수 없게 됩니다"
    assert "::-webkit-scrollbar-thumb" in block, "잡아끌 막대가 보여야 합니다"
    # Chrome 121+ 는 이 둘이 있으면 위 규칙을 무시하고 오버레이 막대로 돌아간다.
    scroll_rule = block[:block.index("}")]
    assert "scrollbar-width" not in scroll_rule
    assert "scrollbar-color" not in scroll_rule


# --- 접히는 구조: 평소엔 짧게, 필요할 때만 펼친다 --------------------------- #

PINNED = ("tiles", "자산 추이", "일별 손익률", "매수 종목")
FOLDED = ("합의 근접도", "엔진별 적중률", "전자공시", "테마별 이슈", "매매 성적",
          "단순 보유 대비", "최근 AI 판단", "최근 주문", "리스크 규칙 차단",
          "AI 비용 추이", "최근 로그", "제어")


def _page() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "dashboard" / "templates" / "index.html").read_text(encoding="utf-8")


def test_only_the_top_stays_pinned():
    """요약·차트·매수 종목은 늘 보여야 한다 — 접으면 볼 이유가 없어진다."""
    page = _page()
    head = page[:page.index('<details class="card fold"')]
    for marker in PINNED:
        assert marker in head, f"{marker} 이 고정 영역 밖으로 밀려났습니다"


def test_everything_else_is_folded():
    import re

    summaries = re.findall(r"<summary>(.*?)</summary>", _page(), re.S)
    for heading in FOLDED:
        assert any(text.lstrip().startswith(heading) for text in summaries), \
            f"{heading} 카드가 접히지 않습니다"


def test_folds_start_closed_and_are_addressable():
    """열린 채로 시작하면 접은 의미가 없다. id 가 없으면 상태를 기억할 수 없다."""
    page = _page()
    assert '<details class="card fold" id="fold-' in page
    assert "<details open" not in page and 'fold" open' not in page


def test_fold_state_survives_the_auto_refresh():
    """이 화면은 30초마다 스스로 새로고침한다 — 기억하지 않으면 매번 다시 닫힌다."""
    page = _page()
    assert "localStorage" in page and "'fold:'" in page
    assert "addEventListener('toggle'" in page
    # 사생활 보호 모드에서는 localStorage 접근 자체가 예외를 던진다.
    assert page.count("try {") >= 2, "localStorage 접근을 감싸지 않으면 화면이 깨집니다"


def test_refresh_waits_after_the_user_opens_a_card():
    """펼치자마자 새로고침이 끼어들면 성가시다."""
    page = _page()
    assert "lastTouch" in page


def test_bought_stocks_card_answers_what_why_and_now(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    with session(app.config["DB_PATH"]) as conn:
        conn.execute(
            """INSERT INTO positions (code, name, qty, avg_price, current_price,
               eval_amount, pnl_amount, pnl_pct, first_bought_at, updated_at)
               VALUES ('005930','삼성전자',10,70000,73500,735000,35000,5.0,
                       '2026-09-16T09:35:00+09:00','x')""")
        conn.execute(
            """INSERT INTO orders (code, name, side, order_type, qty, price, filled_qty,
               filled_price, status, kis_env, created_at, updated_at)
               VALUES ('005930','삼성전자','BUY','limit',10,70000,10,70000,'FILLED','VTS',
                       '2026-09-16T09:35:00+09:00','x')""")
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, name, holding, claude_action,
               claude_confidence, claude_reason, claude_ok, final_action, final_weight_pct,
               final_reason, risk_passed, created_at)
               VALUES ('c1','005930','삼성전자',0,'BUY',0.8,'10개 중 거래량이 가장 뚜렷',1,
                       'STRONG_BUY',18,'전원 매수 합의',1,'2026-09-16T09:34:00+09:00')""")

    body = client.get("/").get_data(as_text=True)
    holdings = body[body.index('id="holdings"'):body.index('<details class="card fold"')]

    assert "삼성전자" in holdings and "005930" in holdings       # 무엇을
    assert "전원 매수 합의" in holdings                            # 왜
    assert "+5.00%" in holdings                                    # 지금
    assert "손절까지" in holdings and "트레일링" in holdings       # 언제 나갈지
    assert "시세" in holdings and "공시" in holdings               # 직접 확인할 길


def test_empty_bought_card_explains_why_nothing_was_bought(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    body = client.get("/").get_data(as_text=True)
    assert "아직 매수한 종목이 없습니다" in body
    assert "모두" in body and "합의 근접도" in body, "왜 비었는지 알려줘야 합니다"


def test_folded_cards_do_not_nest_another_card():
    """카드 안에 카드가 또 그려지면 테두리가 이중으로 보인다."""
    import re

    page = _page()
    for body in re.findall(r'<div class="fold-body">(.*?)\n  </div>\n</details>', page, re.S):
        assert '<div class="card">' not in body


def test_remarks_say_what_happened_to_a_buy(app, client):
    """'세 AI 가 모두 매수라는데 왜 안 샀지?' 에 화면이 답해야 한다."""
    write_env(app.config["ENV_PATH"], FULL_ENV)
    with session(app.config["DB_PATH"]) as conn:
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, name, holding, claude_action,
               claude_confidence, claude_ok, final_action, final_weight_pct, final_reason,
               risk_passed, outcome, created_at)
               VALUES ('c1','000660','SK하이닉스',0,'BUY',0.75,1,'STRONG_BUY',20,
                       '전원 매수 합의',1,
                       '매수 5주 @188,500원 — 기록만 (DRY_RUN, 실제 주문 아님)',
                       '2026-09-18T11:07:00+09:00')""")

    body = client.get("/").get_data(as_text=True)
    assert "DRY_RUN, 실제 주문 아님" in body


def test_risk_rejection_still_wins_the_remarks_cell(app, client):
    write_env(app.config["ENV_PATH"], FULL_ENV)
    with session(app.config["DB_PATH"]) as conn:
        conn.execute(
            """INSERT INTO decisions (cycle_id, code, name, holding, claude_action,
               claude_confidence, claude_ok, final_action, final_weight_pct, final_reason,
               risk_passed, risk_reason, outcome, created_at)
               VALUES ('c1','000660','SK하이닉스',0,'BUY',0.75,1,'STRONG_BUY',20,'합의',
                       0,'당일 손실 한도 도달','','2026-09-18T11:07:00+09:00')""")

    body = client.get("/").get_data(as_text=True)
    assert "리스크 거부: 당일 손실 한도 도달" in body


def test_dry_run_is_named_as_the_reason_nothing_was_bought(app, client):
    """가장 헷갈리는 상태다 — AI 도 리스크도 통과했는데 마지막에서 멈춘 것.

    설정 파일이 아니라 **돌고 있는 봇이 기록한 상태**를 본다. 설정만 바꾸고
    재시작하지 않으면 봇은 여전히 DRY_RUN 이므로, 그 사실을 그대로 보여야 한다.
    """
    write_env(app.config["ENV_PATH"], {**FULL_ENV, "DRY_RUN": "true"})
    update_bot_state(app.config["DB_PATH"], status="RUNNING", kis_env="VTS", dry_run=1)
    with session(app.config["DB_PATH"]) as conn:
        conn.execute(
            """INSERT INTO orders (code, name, side, order_type, qty, price, filled_qty,
               filled_price, status, kis_env, dry_run, created_at, updated_at)
               VALUES ('000660','SK하이닉스','BUY','limit',13,76228,0,0,'DRY_RUN','VTS',1,?,?)""",
            (datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),) * 2)

    body = client.get("/").get_data(as_text=True)
    assert "주문은 나가지 않았습니다" in body
    assert "DRY_RUN" in body
    assert "주문 전송" in body, "고치는 방법을 같이 알려줘야 합니다"


def test_without_dry_run_orders_the_card_stays_calm(app, client):
    write_env(app.config["ENV_PATH"], {**FULL_ENV, "DRY_RUN": "false"})
    update_bot_state(app.config["DB_PATH"], status="RUNNING", kis_env="VTS", dry_run=0)
    body = client.get("/").get_data(as_text=True)
    assert "아직 매수한 종목이 없습니다" in body
    assert "주문은 나가지 않았습니다" not in body
