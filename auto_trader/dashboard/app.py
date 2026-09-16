"""로컬 대시보드 Flask 앱.

**반드시 127.0.0.1 에만 바인딩한다.** API 키를 입력·저장하고 매매를 멈출 수 있는
화면이므로 외부에 노출하면 안 된다.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

from config.loader import BASE_DIR, ConfigError, load
from dashboard import charts, process, queries, restart
from dashboard.env_file import (ALL_FIELDS, GROUPS, missing_required, read_env,
                                read_for_display, write_env)
from utils import autostart, updater
from utils.db import get_bot_state, init_db
from utils.key_check import SKIP, Result, find_telegram_chats, run_all, summarize
from utils.runtime import ProcessLock, StopFlag, pid_path, stop_flag_path

KST = ZoneInfo("Asia/Seoul")

# 비어 있는 항목을 사람이 읽는 이름으로 알려주기 위한 표
FIELD_LABELS = {key: field.label for key, field in ALL_FIELDS.items()}

ENV_PATH = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "trader.db"

# 설정값을 못 읽어도 화면은 떠야 하므로(키 입력 전이 그렇다) 기본값을 둔다.
FALLBACK_RISK = {"stop_loss_pct": -5.0, "take_profit_pct": 10.0}


def _load_settings() -> tuple[Any | None, str]:
    """설정을 읽되, 실패해도 화면은 뜨게 한다."""
    try:
        return load(create_dirs=False), ""
    except ConfigError as exc:
        return None, str(exc)


def create_app(*, testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)  # 프로세스마다 새로 — 세션은 CSRF 토큰 용도뿐
    app.config["TESTING"] = testing
    app.config["ENV_PATH"] = ENV_PATH
    app.config["DB_PATH"] = DB_PATH
    app.config["DATA_DIR"] = DATA_DIR
    app.config["LOG_DIR"] = LOG_DIR
    app.config["BASE_DIR"] = BASE_DIR
    app.config.setdefault("PORT", 8765)
    app.jinja_env.globals["now"] = lambda: datetime.now(KST)

    # ---------------------------------------------------------------- CSRF #
    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def _protect_post() -> None:
        """로컬 앱이라도 다른 사이트가 POST 를 날릴 수 있으므로 토큰을 확인한다."""
        if request.method != "POST" or app.config["TESTING"]:
            return
        expected = session.get("csrf")
        submitted = request.form.get("csrf")
        # 둘 다 없으면 `None == None` 으로 통과해 버린다 — 값이 있고 일치해야 한다.
        if not expected or not submitted or not secrets.compare_digest(
            submitted.encode("utf-8"), expected.encode("utf-8")
        ):
            abort(400, "CSRF 토큰이 올바르지 않습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")

    # ------------------------------------------------------------ 상태 조회 #
    def runtime_status() -> dict[str, Any]:
        lock = ProcessLock(pid_path(app.config["DATA_DIR"]))
        flag = StopFlag(stop_flag_path(app.config["DATA_DIR"]))
        db = app.config["DB_PATH"]
        state = get_bot_state(db) if Path(db).exists() else {}
        return {
            "running": lock.is_running(),
            "pid": lock.read_pid(),
            "stopped": flag.is_set(),
            "stop_reason": flag.reason(),
            "state": state,
            # 화면에 현재 버전을 띄운다. 파일이 없으면(첫 설치) 빈 문자열.
            "version": updater.read_version(app.config["BASE_DIR"]).short,
            "autostart": autostart.status(app.config["BASE_DIR"], app.config["DATA_DIR"]),
            "kis_env": (read_env(app.config["ENV_PATH"]).get("KIS_ENV") or "VTS").upper(),
            "dry_run": (read_env(app.config["ENV_PATH"]).get("DRY_RUN") or "true").lower() != "false",
            "base_dir": str(app.config["BASE_DIR"]),
        }

    # ------------------------------------------------------------- 라우트 #
    @app.route("/")
    def index() -> str:
        settings, config_error = _load_settings()
        # 설정이 덜 됐다고 현황 화면을 막지 않는다. 막아 세우면 무엇이 문제인지
        # 볼 방법이 없어져, 설정↔점검 사이를 오가며 헤매게 된다.
        # 화면은 항상 열고, 부족한 것은 화면 위에 적어 둔다.
        first_run = not Path(app.config["ENV_PATH"]).exists()
        if first_run:
            return redirect(url_for("setup", first="1"))

        missing = missing_required(app.config["ENV_PATH"])

        db = app.config["DB_PATH"]
        init_db(db)
        risk = settings.risk if settings else None
        stop_loss = risk.stop_loss_pct if risk else FALLBACK_RISK["stop_loss_pct"]
        take_profit = risk.take_profit_pct if risk else FALLBACK_RISK["take_profit_pct"]

        equity = queries.equity_series(db)
        return render_template(
            "index.html",
            status=runtime_status(),
            overview=queries.overview(db),
            positions=queries.positions(db, stop_loss, take_profit),
            decisions=queries.recent_decisions(db, 25),
            orders=queries.recent_orders(db, 15),
            risk_blocks=queries.recent_risk_blocks(db),
            decision_mix=queries.decision_mix(db),
            logs=queries.log_tail(app.config["LOG_DIR"]),
            equity_chart=charts.equity_line(equity),
            pnl_chart=charts.pnl_bars(equity),
            cost_chart=charts.cost_bars(queries.ai_cost_series(db)),
            settings=settings,
            config_error=config_error,
            missing=[(key, FIELD_LABELS.get(key, key)) for key in missing],
        )

    @app.route("/api/status")
    def api_status():
        db = app.config["DB_PATH"]
        if not Path(db).exists():
            return jsonify({"ready": False})
        return jsonify({
            "ready": True,
            "runtime": runtime_status(),
            "overview": queries.overview(db),
            "updated_at": datetime.now(KST).isoformat(timespec="seconds"),
        })

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        env_path = app.config["ENV_PATH"]
        if request.method == "POST":
            updates = {key: value for key, value in request.form.items() if key != "csrf"}
            changed = write_env(env_path, updates)
            flash(f"저장했습니다. 변경된 항목 {len(changed)}개" if changed else "변경된 항목이 없습니다", "ok")
            if changed and process.is_running(app.config["DATA_DIR"]):
                # 이미 떠 있는 프로세스는 옛 설정을 들고 있다.
                flash("실행 중인 자동매매에 반영하려면 현황 화면에서 '재시작'을 누르세요.", "warn")
            if not missing_required(env_path):
                flash("필수 항목이 모두 채워졌습니다. 아래 '키 점검'으로 실제 동작을 확인하세요.", "ok")
            return redirect(url_for("setup"))

        return render_template(
            "setup.html",
            groups=GROUPS,
            values=read_for_display(env_path),
            missing=missing_required(env_path),
            first_run=request.args.get("first") == "1",
            env_path=env_path,
            status=runtime_status(),
        )

    @app.route("/setup/verify", methods=["POST"])
    def verify():
        env = read_env(app.config["ENV_PATH"])
        results = run_all(env, telegram_test=request.form.get("telegram_test") == "1")
        # 현황 화면 진입 조건과 같은 기준을 여기서도 본다. 점검은 통과했는데
        # 현황 화면이 막히는 모순을 없앤다(모델 이름처럼 API 를 안 부르는 항목).
        blanks = missing_required(app.config["ENV_PATH"])
        for key in blanks:
            results.append(Result(f"미입력 {FIELD_LABELS.get(key, key)}", SKIP,
                                  "값이 비어 있습니다 — 설정 화면에서 채우세요"))
        return render_template(
            "verify.html",
            results=results,
            counts=summarize(results),
            status=runtime_status(),
        )

    @app.route("/control/<action>", methods=["POST"])
    def control(action: str):
        data_dir = app.config["DATA_DIR"]
        log_dir = app.config["LOG_DIR"]
        flag = StopFlag(stop_flag_path(data_dir))

        if action == "stop":
            flag.set("대시보드에서 정지")
            flash("긴급 정지했습니다. 진행 중인 사이클을 마친 뒤 새 사이클이 실행되지 않습니다.", "warn")

        elif action == "resume":
            flag.clear()
            flash("정지를 해제했습니다. 다음 사이클부터 재개됩니다.", "ok")

        elif action == "start":
            missing = missing_required(app.config["ENV_PATH"])
            if missing:
                flash(f"먼저 설정을 마치세요. 비어 있는 항목: {', '.join(missing)}", "warn")
                return redirect(url_for("setup"))
            flag.clear()  # 정지 상태로 켜면 아무것도 하지 않는다
            result = process.start(app.config["BASE_DIR"], data_dir, log_dir)
            flash(result.message, "ok" if result.ok else "warn")

        elif action == "restart":
            result = process.restart(app.config["BASE_DIR"], data_dir, log_dir)
            flash(result.message, "ok" if result.ok else "warn")

        elif action == "shutdown":
            result = process.stop(data_dir)
            flash(result.message, "ok" if result.ok else "warn")

        elif action == "update":
            _apply_update(app.config["BASE_DIR"], data_dir, log_dir,
                          app.config["PORT"])

        elif action in ("mode_vts", "mode_real"):
            _switch_mode(app, "VTS" if action == "mode_vts" else "REAL", data_dir, log_dir)

        elif action == "autostart_on":
            result = autostart.enable(app.config["BASE_DIR"], data_dir)
            if result.enabled:
                flash("PC 를 켜면 자동매매가 스스로 시작됩니다.\n"
                      "단, 윈도우에 로그인해야 실행됩니다 — 재부팅 후 잠금화면에 머물러 "
                      "있으면 그동안은 매매도 멈춰 있습니다.", "ok")
            else:
                flash(f"자동시작을 등록하지 못했습니다: {result.detail}", "warn")

        elif action == "autostart_off":
            autostart.disable(app.config["BASE_DIR"], data_dir)
            flash("자동시작을 해제했습니다. 이제 PC 를 켜도 자동으로 뜨지 않습니다.", "ok")

        else:
            abort(404)
        return redirect(url_for("index"))

    @app.route("/setup/telegram-chat-id", methods=["POST"])
    def find_chat_id():
        """봇 대화에서 채팅 ID 를 찾아 자동으로 채운다.

        숫자를 손으로 알아내게 하면 꼭 틀린다 — 'chat not found' 로
        헤매는 일을 없앤다.
        """
        env = read_env(app.config["ENV_PATH"])
        token = env.get("TELEGRAM_BOT_TOKEN")
        if not token:
            flash("먼저 텔레그램 봇 토큰을 저장하세요.", "warn")
            return redirect(url_for("setup"))

        found = find_telegram_chats(token)
        if not found:
            flash("봇에게 온 메시지가 없습니다.\n"
                  "텔레그램에서 봇 대화창을 열고 [시작] 또는 /start 를 보낸 뒤 "
                  "다시 눌러 주세요. (봇은 상대가 먼저 말을 걸어야 메시지를 보낼 수 있습니다)",
                  "warn")
            return redirect(url_for("setup"))

        chat_id, name = found[0]
        write_env(app.config["ENV_PATH"], {"TELEGRAM_CHAT_ID": chat_id})
        extra = ""
        if len(found) > 1:
            others = ", ".join(f"{cid} ({who})" for cid, who in found[1:])
            extra = f"\n다른 대화도 있습니다: {others} — 필요하면 직접 바꾸세요."
        flash(f"채팅 ID 를 찾아 채웠습니다: {chat_id} ({name}){extra}", "ok")
        return redirect(url_for("setup"))

    @app.route("/진단")
    @app.route("/diagnose")
    def diagnose() -> str:
        """무엇이 막고 있는지 한 화면에 모아 보여준다.

        설정↔점검을 오가며 원인을 짐작하는 대신, 프로그램이 실제로 보고 있는
        값을 그대로 늘어놓는다. 비밀값은 채워졌는지 여부와 길이만 보여준다.
        """
        env_path = Path(app.config["ENV_PATH"])
        raw = read_env(env_path) if env_path.exists() else {}
        missing = set(missing_required(env_path)) if env_path.exists() else set()

        rows = []
        for key, field in ALL_FIELDS.items():
            value = raw.get(key, "")
            if not value:
                shown = "(비어 있음)"
            elif field.secret:
                shown = f"채워짐 · {len(value)}자"
            else:
                shown = value
            rows.append({
                "key": key, "label": field.label, "value": shown,
                "required": field.required, "missing": key in missing,
            })

        settings, config_error = _load_settings()
        return render_template(
            "diagnose.html",
            rows=rows,
            missing_count=len(missing),
            env_path=str(env_path),
            env_exists=env_path.exists(),
            base_dir=str(app.config["BASE_DIR"]),
            db_path=str(app.config["DB_PATH"]),
            version=updater.read_version(app.config["BASE_DIR"]),
            status=runtime_status(),
            config_error=config_error,
            settings=settings,
        )

    @app.route("/health")
    def health():
        return jsonify({"ok": True})

    return app


def run(host: str = "127.0.0.1", port: int = 8765, *, debug: bool = False) -> None:
    create_app().run(host=host, port=port, debug=debug)


def _apply_update(base_dir, data_dir, log_dir, port: int = 8765) -> None:
    """업데이트 버튼 처리. 돌고 있는 봇은 멈췄다가 새 코드로 다시 띄운다."""
    was_running = process.is_running(data_dir)
    if was_running:
        stopped = process.stop(data_dir)
        if not stopped.ok:
            flash(f"업데이트 전에 자동매매를 멈추지 못했습니다 — {stopped.message}", "warn")
            return

    try:
        result = updater.apply_update(base_dir)
    except updater.UpdateError as exc:
        flash(f"업데이트하지 못했습니다: {exc}", "warn")
        if was_running:  # 멈춰만 놓고 끝내면 매매가 죽는다
            restarted = process.start(base_dir, data_dir, log_dir)
            flash(f"기존 버전으로 다시 시작했습니다 — {restarted.message}",
                  "ok" if restarted.ok else "warn")
        return

    lines = [f"최신 버전으로 업데이트했습니다 ({result.version.short} {result.version.message})",
             "키와 매매 기록은 그대로 유지됩니다."]
    lines.extend(result.notes)

    if result.deps_changed:
        # 사용자가 창을 닫고 start.bat 을 다시 실행하게 만들지 않는다 — 여기서 깐다.
        ok, message = updater.install_dependencies(base_dir)
        lines.append(("· " if ok else "⚠️ ") + message)
        if not ok:
            lines.append("이 창을 닫고 start.bat 을 다시 실행하면 설치가 다시 시도됩니다.")
            flash("\n".join(lines), "warn")
            return

    if was_running:
        restarted = process.start(base_dir, data_dir, log_dir)
        lines.append(f"자동매매를 다시 시작했습니다 — {restarted.message}")

    # 대시보드 자신은 옛 코드를 메모리에 물고 있다. 새 화면을 보려면 프로세스를
    # 갈아야 한다 — 새 대시보드를 직접 띄우고 이 프로세스는 빠진다.
    lines.append("잠시 뒤 새 창으로 대시보드가 다시 뜹니다.")
    flash("\n".join(lines), "ok")
    restart.request_restart(base_dir, port)


def _switch_mode(app, mode: str, data_dir, log_dir) -> None:
    """모의투자(VTS) ↔ 실전(REAL) 전환.

    돌고 있는 봇은 반드시 새 설정으로 다시 띄운다 — 예전 도메인·TR ID 를 물고
    있는 프로세스가 남으면 의도와 다른 계좌로 주문이 나간다.
    """
    changed = write_env(app.config["ENV_PATH"], {"KIS_ENV": mode})
    if not changed:
        flash(f"이미 {'모의투자' if mode == 'VTS' else '실전'} 입니다.", "ok")
        return

    label = "모의투자(VTS)" if mode == "VTS" else "실전(REAL)"
    lines = [f"{label} 로 전환했습니다."]
    if mode == "REAL":
        lines.append("⚠️ 지금부터 실제 자금으로 주문이 나갑니다.")
    else:
        lines.append("가짜 돈으로만 주문이 나갑니다.")
    lines.append("계좌번호도 해당 환경의 것으로 바꿔야 합니다 — 모의계좌와 실계좌는 번호가 다릅니다.")

    if process.is_running(data_dir):
        stopped = process.stop(data_dir)
        if not stopped.ok:
            lines.append(f"⚠️ 자동매매를 멈추지 못했습니다({stopped.message}) — "
                         "예전 설정으로 계속 돌고 있습니다. 직접 종료해 주세요.")
            flash("\n".join(lines), "warn")
            return
        restarted = process.start(app.config["BASE_DIR"], data_dir, log_dir)
        lines.append(f"자동매매를 새 설정으로 다시 시작했습니다 — {restarted.message}")

    flash("\n".join(lines), "warn" if mode == "REAL" else "ok")
