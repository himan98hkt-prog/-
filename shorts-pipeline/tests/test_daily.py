"""매일 아침 자동 업로드가 **실제로 도는지** 붙잡아 두는 검사.

    python tests/test_daily.py

"정기 업로드가 안 된다" 는 신고에서 왔다. 원인은 네 겹이었다.

  1. 한국어 윈도우에서 출력이 cp949 로 가면 첫 로그 줄(`—`)에서 죽었다
  2. 예약은 `python` 이라는 이름만 찾았다 (작업실은 `py` 로도 켜진다)
  3. 그 시각에 절전·꺼짐·배터리면 그날은 그냥 건너뛰었다
  4. 실패해도 아무 데도 이유가 안 남았다

API 호출 0회. 윈도우 작업 스케줄러는 가짜로 바꿔 끼워서 본다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_daily"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


def seed_dir(name: str) -> Path:
    from PIL import Image

    d = TMP / name / "seeds"
    shutil.rmtree(d.parent, ignore_errors=True)
    d.mkdir(parents=True)
    Image.new("RGB", (64, 112), (40, 60, 90)).save(d / "city_01.png")
    return d


class RunsGuard:
    """실제 runs/ 를 건드리는 검사 뒤에 원래대로 돌려놓는다."""

    KEEP = ("schedule.log", "schedule_state.json", "cron.log")

    def __enter__(self):
        self.runs = ROOT / "runs"
        self.runs.mkdir(exist_ok=True)
        self.before = {p.name for p in self.runs.iterdir()}
        self.saved = {n: (self.runs / n).read_bytes()
                      for n in self.KEEP if (self.runs / n).exists()}
        return self

    def __exit__(self, *exc):
        for p in self.runs.iterdir():
            if p.name not in self.before:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        for n in self.KEEP:
            if n in self.saved:
                (self.runs / n).write_bytes(self.saved[n])


# ══════════════════════════════════════════════════════════════════════
def test_cp949_does_not_kill_the_run():
    section("한국어 윈도우 출력(cp949)에서도 끝까지 돈다")
    seeds = seed_dir("cp949")
    env = dict(os.environ, PYTHONIOENCODING="cp949", SHORTS_MOCK="1")
    env.pop("PYTHONUTF8", None)
    log = TMP / "cp949" / "cron.log"
    with RunsGuard():
        with log.open("ab") as fh:
            code = subprocess.call(
                [sys.executable, "-m", "publish.scheduler", "--seeds", str(seeds),
                 "--generate-only", "--config", "tests/config.test.yaml"],
                cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=600)
        text = log.read_text(encoding="utf-8", errors="replace")
        history = (ROOT / "runs" / "schedule.log").read_text(encoding="utf-8")
    check("정상 종료", code == 0, f"exit={code}")
    check("UnicodeEncodeError 가 없다", "UnicodeEncodeError" not in text)
    check("생성까지 갔다", "생성 완료" in text)
    check("이력이 남았다", "OK" in history.splitlines()[-1], history.splitlines()[-1][:60])
    check("쓴 시드는 치웠다", not (seeds / "city_01.png").exists())


def test_log_option_and_crash_record():
    section("창 없이 돌 때 — 출력은 파일로, 죽으면 이유를 남긴다")
    import publish.scheduler as sch

    log = TMP / "log" / "cron.log"
    shutil.rmtree(log.parent, ignore_errors=True)
    with RunsGuard():
        real_out, real_err = sys.stdout, sys.stderr
        real_pick = sch.pick_seed
        seeds = seed_dir("crash")

        def boom(*a, **k):
            raise RuntimeError("시드 폴더를 읽다가 터짐")

        sch.pick_seed = boom
        try:
            code = sch.main(["--seeds", str(seeds), "--generate-only",
                             "--log", str(log)])
        finally:
            sch.pick_seed = real_pick
            if sch._LOG_FH:
                sch._LOG_FH.close()
                sch._LOG_FH = None
            sys.stdout, sys.stderr = real_out, real_err
        state = json.loads((ROOT / "runs" / "schedule_state.json").read_text("utf-8"))
        last = (ROOT / "runs" / "schedule.log").read_text("utf-8").splitlines()[-1]
    text = log.read_text(encoding="utf-8")
    check("실패 코드로 끝난다", code == 1)
    check("오류가 로그 파일에 들어간다", "시드 폴더를 읽다가 터짐" in text)
    check("이력에 이유가 남는다", "예상 못 한 오류" in last and "RuntimeError" in last, last[-60:])
    check("상태 파일이 crash", state.get("result") == "crash")
    check("끝난 시각이 찍힌다", bool(state.get("finished")))


def test_child_gets_utf8_env():
    section("자식 파이썬도 UTF-8 로 돈다")
    import publish.scheduler as sch

    seen = {}
    real = subprocess.call

    def fake_call(args, **kw):
        seen.update(kw)
        return 0

    sch.subprocess.call = fake_call
    try:
        sch.run([sys.executable, "main.py", "generate"])
    finally:
        sch.subprocess.call = real
    env = seen.get("env") or {}
    check("PYTHONIOENCODING=utf-8", env.get("PYTHONIOENCODING") == "utf-8")
    check("PYTHONUTF8=1", env.get("PYTHONUTF8") == "1")
    check("작업 폴더를 넘긴다", seen.get("cwd") == sch.ROOT)


# ══════════════════════════════════════════════════════════════════════
def test_runner_and_registration():
    section("예약 등록 내용")
    from pipeline import win_schedule as ws

    real = ROOT / "daily.bat"
    backup = real.read_bytes() if real.exists() else None
    try:
        text = ws.write_runner("09:00", ["youtube", "instagram"], "chain").read_text("ascii")
    finally:
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)
    check("배치에 UTF-8 강제", "PYTHONUTF8=1" in text and "PYTHONIOENCODING=utf-8" in text)
    check("배치가 파이썬 전체 경로를 쓴다", f'"{sys.executable}"' in text)
    check("배치도 로그를 남긴다", "--log runs/cron.log" in text)

    script = ws.register_script("07:00", "09:00", ["youtube", "instagram"], "chain",
                                pythonw=r"C:\Users\홍길동\py\pythonw.exe",
                                workdir=r"C:\AI DEOKHU's")
    for flag, why in (("-StartWhenAvailable", "꺼져 있었으면 켜지는 대로"),
                      ("-WakeToRun", "절전에서 깨운다"),
                      ("-AllowStartIfOnBatteries", "배터리여도 시작"),
                      ("-DontStopIfGoingOnBatteries", "배터리로 바뀌어도 계속"),
                      ("-MultipleInstances IgnoreNew", "겹쳐 돌지 않는다")):
        check(f"{flag} — {why}", flag in script)
    check("창 없는 pythonw 로 돈다", r"-Execute 'C:\Users\홍길동\py\pythonw.exe'" in script)
    check("출력은 로그 파일로", "--log runs/cron.log" in script)
    check("작은따옴표가 든 폴더 이름도 안 깨진다", r"'C:\AI DEOKHU''s'" in script)
    check("관리자 권한을 요구하지 않는다", "-RunLevel Limited" in script)
    check("넉넉한 실행 한도", f"-Hours {ws.TIME_LIMIT_HOURS}" in script)

    check("내 PC 엔진은 두 시간 먼저 시작", ws.lead_minutes_for("local") == 120)
    check("클라우드는 30분 먼저", ws.lead_minutes_for("fal") == 30)
    check("기본 게시 시각은 오전 9시", ws.DEFAULT_PUBLISH_TIME == "09:00")


class FakeWindows:
    """작업 스케줄러 대신 호출을 받아 적는다."""

    def __init__(self, ws, *, ps_ok=True, info=None):
        self.ws, self.calls, self.scripts = ws, [], []
        self.ps_ok, self.info = ps_ok, info

    def __enter__(self):
        ws = self.ws
        self.saved = (ws.supported, ws._run, ws._powershell)
        ws.supported = lambda: True
        ws._run = self._run
        ws._powershell = self._ps
        return self

    def __exit__(self, *exc):
        self.ws.supported, self.ws._run, self.ws._powershell = self.saved

    def _run(self, args, timeout=60):
        self.calls.append(args)
        return 0, "SUCCESS"

    def _ps(self, script, timeout=60):
        self.scripts.append(script)
        if "Get-ScheduledTask " in script:
            return (0, "잡음\n" + json.dumps(self.info)) if self.info else (1, "없음")
        return (0, "OK") if self.ps_ok else (1, "Access denied")


def test_enable_paths():
    section("예약 켜기 — 정상 · PowerShell 이 막힌 PC")
    from pipeline import win_schedule as ws

    real = ROOT / "daily.bat"
    backup = real.read_bytes() if real.exists() else None
    try:
        with FakeWindows(ws) as fw:
            ok, msg = ws.enable("09:00", ["youtube", "instagram"], "chain",
                                lead_minutes=120)
        check("등록 성공", ok, msg.splitlines()[0])
        check("두 시간 앞서 시작", "07:00" in msg)
        check("등록 스크립트를 썼다", any("Register-ScheduledTask" in s for s in fw.scripts))
        check("깨우기 타이머를 켰다",
              any(c[:2] == ["powercfg", "/SETACVALUEINDEX"] for c in fw.calls))
        check("schtasks 로 떨어지지 않았다", not any(c[0] == "schtasks" for c in fw.calls))

        with FakeWindows(ws, ps_ok=False) as fw:
            ok2, msg2 = ws.enable("09:00", ["youtube"], "chain")
        check("막혀도 예전 방식으로는 걸린다",
              ok2 and any(c[0] == "schtasks" for c in fw.calls))
        check("제한이 있다고 알려준다", "간단한 방식" in msg2)

        with FakeWindows(ws):
            bad, why = ws.enable("9시", ["youtube"])
        check("잘못된 시각은 거절", not bad and "형식" in why)
    finally:
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)


def test_status_and_repair():
    section("상태 읽기 · 예전 예약 고치기")
    from pipeline import win_schedule as ws

    check("잡음 섞인 JSON 도 읽는다", ws.parse_info('WARN\n{"a": 1}\n')["a"] == 1)
    check("못 읽으면 빈 dict", ws.parse_info("오류") == {})
    check("인자에서 되읽는다",
          ws.read_args("-m publish.scheduler --at 09:00 --mode montage --youtube")
          == ("09:00", ["youtube"], "montage"))

    legacy = {"last_run": "2026-09-27T20:30:01", "result": 1, "next_run": "",
              "missed": 0, "wake": False, "when_available": False, "no_battery": True,
              "execute": r"C:\x\daily.bat", "arguments": "",
              "start": "2026-08-30T20:30:00"}
    real = ROOT / "daily.bat"
    backup = real.read_bytes() if real.exists() else None
    try:
        real.write_text("python -m publish.scheduler --at 21:00 --mode chain "
                        "--youtube --instagram\r\n", encoding="ascii")
        with FakeWindows(ws, info=legacy) as fw:
            st = ws.status()
            check("예전 예약을 알아본다", ws.is_legacy(st.info))
            check("시각·대상을 배치에서 되읽는다",
                  st.publish_time == "21:00" and st.targets == ["youtube", "instagram"])
            ok, msg = ws.repair(None)
        regs = [s for s in fw.scripts if "Register-ScheduledTask" in s]
        check("새 방식으로 다시 건다", ok and len(regs) == 1)
        check("시각과 대상은 그대로", regs and "--at 21:00" in regs[0]
              and "--instagram" in regs[0])
        check("시작 시각 간격도 그대로 (30분)", regs and "-At '20:30'" in regs[0])

        fresh = dict(legacy, arguments=ws.scheduler_args("09:00", ["youtube"], "chain"),
                     when_available=True, wake=True, no_battery=False)
        with FakeWindows(ws, info=fresh) as fw:
            ok2, _ = ws.repair(None)
        check("이미 새 방식이면 건드리지 않는다",
              not ok2 and not any("Register" in s for s in fw.scripts))
    finally:
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)


def test_explain():
    section("왜 안 됐나 — 사람 말로")
    from pipeline import win_schedule as ws

    now = datetime(2026, 9, 28, 10, 0)
    good = {"last_run": "2026-09-28T07:00:02", "result": 0,
            "next_run": "2026-09-29T07:00:00", "wake": True, "when_available": True,
            "no_battery": False, "arguments": "--at 09:00 --youtube --log runs/cron.log",
            "start": "2026-09-01T07:00:00"}

    d = ws.explain({}, {}, "", "", now)
    check("예약 없음", d["level"] == "info" and "꺼져" in d["headline"])

    d = ws.explain(good, {"result": "ok"}, "2026-09-28 09:00:03\tOK\t...", "", now)
    check("정상", d["level"] == "ok", d["headline"])

    d = ws.explain(dict(good, last_run="1999-11-30T00:00:00", result=267011), {}, "", "", now)
    check("아직 안 돔", "한 번도" in d["headline"] and "09-29 07:00" in d["headline"])

    d = ws.explain(dict(good, last_run="2026-09-27T07:00:05"), {}, "", "", now)
    check("오늘 회차를 놓침 — PC 가 꺼져 있었다",
          d["level"] == "warn" and "돌지 않았습니다" in d["details"][0], d["details"][0])
    check("절전으로 두라고 안내", any("절전" in f for f in d["fixes"]))

    d = ws.explain(dict(good, result=1), {"result": "fail"},
                   "2026-09-28 07:00:04\tFAIL\t시드 소진", "", now)
    check("시드 소진을 알아본다", d["level"] == "bad" and "이미지를 다 썼" in d["details"][0])
    check("이미지를 넣으라고 안내", "이미지를 더 넣" in d["fixes"][0])

    d = ws.explain(dict(good, result=1), {"result": "crash"},
                   "2026-09-28 07:00:04\tFAIL\t예상 못 한 오류\tKeyError: 'x'",
                   "KeyError: 'x'", now)
    check("멈춘 오류를 그대로 보여준다", any("KeyError" in x for x in d["details"]))

    d = ws.explain(dict(good, result=2147942402), {}, "", "", now)
    check("결과 코드를 사람 말로", "찾지 못했습니다" in d["details"][0], d["details"][0])

    d = ws.explain(dict(good, result=267009), {}, "", "", now)
    check("지금 도는 중", "만드는 중" in d["headline"])

    stale = {"result": "running", "finished": "", "started": "2026-09-20T07:00:00"}
    d = ws.explain(good, stale, "", "", now)
    check("오래된 '실행 중' 기록은 믿지 않는다", "만드는 중" not in d["headline"])

    legacy = dict(good, arguments="", when_available=False, no_battery=True, wake=False)
    d = ws.explain(legacy, {"result": "ok"}, "", "", now)
    check("예전 방식이면 경고", d["level"] == "warn"
          and any("예전 방식" in x for x in d["details"]))
    check("배터리 설정도 짚는다", any("배터리" in x for x in d["details"]))


def test_server_endpoints():
    section("작업실")
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    import ui.server as srv

    st = srv.schedule_state()
    check("리눅스에서도 상태가 나온다", st["supported"] is False and st["diagnosis"] is None)
    check("시작 간격을 엔진에 맞춰 알려준다", st["lead_minutes"] in (30, 120))

    server = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/api/schedule-run",
            data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            code, body = 200, {}
        except urllib.error.HTTPError as e:
            code, body = e.code, json.loads(e.read().decode())
        check("지금 돌려보기 — 윈도우가 아니면 정중히 거절", code == 400
              and "윈도우" in body.get("message", ""), str(body))
    finally:
        server.shutdown()

    html = (ROOT / "ui" / "app.html").read_text(encoding="utf-8")
    check("오전 9시가 기본 선택", '<option value="09:00" selected>' in html)
    check("지금 돌려보기 버튼", 'id="autoRun"' in html)
    check("진단 칸", 'id="autoDiag"' in html)


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                try:
                    fn()
                except Exception as exc:              # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check(f"{name} 가 예외 없이 끝난다", False, repr(exc))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n통과 {len(PASSED)} · 실패 {len(FAILED)}")
    for f in FAILED:
        print(f"  X {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
