"""실제 브라우저로 화면을 눌러 본다.

    python tests/test_ui_copy.py

두 가지를 확인한다.
  1) 클립 길이를 바꾸면 **클립 수 선택지가 따라 바뀌는지.** 예전에는 [4,6,8,10]
     고정이라 10초를 고르면 6개 = 60초짜리가 나왔다. 쇼츠로는 너무 길고
     값은 두 배였다.
  2) [AI로 제목 3개 뽑기] 가 실제로 눌리고, 고르면 제목 칸에 들어가고,
     키가 없거나 서버가 죽었을 때 **사람이 읽을 수 있는 말**이 뜨는지.

OpenRouter 는 부르지 않는다. 같은 모양으로 대답하는 가짜 서버를 띄우고
OPENROUTER_BASE_URL 로 그쪽을 보게 한다. 돈도 무료 한도도 쓰지 않는다.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image                          # noqa: E402

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_uicopy"

REPLY = json.dumps([
    {"title": "빛이 쏟아지는 계단", "hook": "이 끝에 뭐가 있을까"},
    {"title": "잠긴 신전을 지나", "hook": "물이 발목까지 찼다"},
    {"title": "끝나지 않는 회랑", "hook": "돌아갈 길이 없다"},
], ensure_ascii=False)


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  [{'OK  ' if cond else 'FAIL'}] {name}" +
          (f"  — {detail}" if detail else ""))


def chromium_path() -> str | None:
    """이 환경에 미리 깔린 크로미움을 찾는다.

    playwright 판올림과 브라우저 판이 어긋나면 기본 경로를 못 찾는다.
    깔려 있는 것을 직접 가리키면 다시 내려받지 않아도 된다.
    """
    for pat in ("chromium-*/chrome-linux/chrome",
                "chromium_headless_shell-*/chrome-linux/headless_shell"):
        for c in sorted(Path("/opt/pw-browsers").glob(pat), reverse=True):
            if c.is_file():
                return str(c)
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── 가짜 OpenRouter ──────────────────────────────────────────────────
class Stub(BaseHTTPRequestHandler):
    mode = "ok"                 # ok | boom | garbage
    seen: list[dict] = []

    def log_message(self, *a):
        pass

    def _send(self, code: int, payload) -> None:
        blob = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):
        if self.path.endswith("/models"):
            self._send(200, {"data": [{"id": "zz/paid"},
                                      {"id": "aa/qwen3:free"},
                                      {"id": "bb/gemini-flash:free"}]})
        else:
            self._send(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        Stub.seen.append({"model": body.get("model"),
                          "auth": self.headers.get("Authorization", "")})
        if Stub.mode == "boom":
            self._send(500, {"error": "터졌습니다"})
        elif Stub.mode == "garbage":
            self._send(200, {"choices": [{"message": {"content": "음 글쎄요"}}]})
        else:
            self._send(200, {"choices": [{"message": {"content": REPLY}}]})


def wait_up(port: int, timeout: float = 25.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.4):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def make_seed(seeds: Path) -> None:
    seeds.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (816, 1456), (30, 40, 80))
    img.save(seeds / "temple_01.png")
    (seeds / "temple_01.yaml").write_text(
        "title:  횃불이 밝힌 계단을 내려가는 길\n"
        "hook:   이 길 끝에 뭐가 있을까\n"
        "prompt: descending a vast temple staircase, forward motion\n"
        "theme:  temple\n"
        "source: descending_a_vast_temple_staircase_lit_by_braziers_abc123.png\n",
        encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    from playwright.sync_api import sync_playwright

    if TMP.exists():
        shutil.rmtree(TMP)
    work = TMP / "work"
    work.mkdir(parents=True)

    # 작업 폴더를 통째로 복사하면 무거우니, 서버가 보는 경로만 심는다.
    for name in ("main.py", "config.yaml"):
        shutil.copy2(ROOT / name, work / name)
    for d in ("pipeline", "publish", "ui", "brand"):
        shutil.copytree(ROOT / d, work / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    make_seed(work / "seeds")
    (work / "runs").mkdir()

    stub_port, ui_port = free_port(), free_port()
    stub = ThreadingHTTPServer(("127.0.0.1", stub_port), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    env = {**os.environ,
           "OPENROUTER_BASE_URL": f"http://127.0.0.1:{stub_port}",
           "OPENROUTER_API_KEY": "sk-or-fake",
           "PYTHONPATH": str(work), "PYTHONUNBUFFERED": "1"}
    env.pop("OPENROUTER_MODEL", None)

    proc = subprocess.Popen(
        [sys.executable, "main.py", "ui", "--port", str(ui_port), "--no-browser"],
        cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        if not wait_up(ui_port):
            out = ""
            if proc.poll() is not None and proc.stdout:
                out = proc.stdout.read()[-1500:]
            check("작업실이 뜬다", False, out or "시간 초과")
            return 1
        check("작업실이 뜬다", True)

        with sync_playwright() as pw:
            exe = chromium_path()
            browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{ui_port}/", wait_until="networkidle")

            # [1 · 이미지 고르기] 탭으로. 간편 모드는 버튼 하나만 보여준다.
            page.click("#t-make")
            page.wait_for_timeout(400)

            page.wait_for_selector("#grid .seed", timeout=15000)
            page.locator("#grid .seed").first.click()
            page.wait_for_timeout(300)

            # ── 1. 클립 수가 길이를 따라간다 ──────────────────────
            def opts() -> list[str]:
                return page.eval_on_selector_all(
                    "#clips option", "els => els.map(e => e.value)")

            page.select_option("#duration", "10")
            page.wait_for_timeout(200)
            o10, v10 = opts(), page.input_value("#clips")
            check("10초일 때 선택지가 [2,3,4,5]", o10 == ["2", "3", "4", "5"], str(o10))
            check("10초 기본이 3개 = 30초", v10 == "3", f"실제 {v10}")

            page.select_option("#duration", "5")
            page.wait_for_timeout(200)
            o5, v5 = opts(), page.input_value("#clips")
            check("5초일 때 선택지가 [4,6,8,10]", o5 == ["4", "6", "8", "10"], str(o5))
            check("길이를 바꿔도 30초를 지킨다", v5 == "6", f"실제 {v5}")

            page.select_option("#duration", "10")
            page.wait_for_timeout(200)
            check("되돌려도 30초 (3개)", page.input_value("#clips") == "3")
            check("select 가 비지 않는다 — 예전 5초 1클립 버그",
                  page.input_value("#clips") != "")

            # ── 2. AI 제목 뽑기 ───────────────────────────────────
            Stub.mode, Stub.seen = "ok", []
            page.click("#suggestBtn")
            page.wait_for_selector("#suggestList .sg", timeout=25000)
            cards = page.locator("#suggestList .sg")
            check("후보 3개가 뜬다", cards.count() == 3, f"실제 {cards.count()}")
            first = cards.first.inner_text()
            check("제목과 훅이 같이 보인다",
                  "빛이 쏟아지는 계단" in first and "이 끝에 뭐가" in first, first)
            check("살아 있는 무료 모델 중 선호 1순위를 골랐다",
                  Stub.seen and Stub.seen[0]["model"] == "bb/gemini-flash:free",
                  str(Stub.seen[:1]))
            check("키를 헤더로 보낸다",
                  bool(Stub.seen) and Stub.seen[0]["auth"] == "Bearer sk-or-fake")

            note = page.inner_text("#suggestNote")
            check("남은 무료 횟수를 알려준다", "/" in note and "회" in note, note)

            cards.nth(1).click()
            page.wait_for_timeout(200)
            check("고르면 제목 칸에 들어간다",
                  page.input_value("#title") == "잠긴 신전을 지나",
                  page.input_value("#title"))
            check("훅도 같이 들어간다",
                  page.input_value("#hook") == "물이 발목까지 찼다",
                  page.input_value("#hook"))
            check("고르고 나면 목록이 닫힌다",
                  page.locator("#suggestList .sg").count() == 0)

            # ── 3. 잘못될 때 ──────────────────────────────────────
            Stub.mode = "boom"
            page.click("#suggestBtn")
            page.wait_for_selector("#suggestNote.bad", timeout=25000)
            msg = page.inner_text("#suggestNote")
            check("서버가 500 이면 이유를 보여준다", bool(msg.strip()), msg)
            check("빈 오류창이 아니다", "undefined" not in msg and "null" not in msg, msg)
            check("버튼이 다시 눌린다", page.is_enabled("#suggestBtn"))
            check("제목은 그대로 남아 있다",
                  page.input_value("#title") == "잠긴 신전을 지나")

            Stub.mode = "garbage"
            page.click("#suggestBtn")
            page.wait_for_selector("#suggestNote.bad", timeout=25000)
            check("응답이 쓰레기여도 안내가 뜬다",
                  bool(page.inner_text("#suggestNote").strip()))
            check("제목은 여전히 그대로",
                  page.input_value("#title") == "잠긴 신전을 지나")

            check("콘솔 오류 0건", not errors, "; ".join(errors[:3]))
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        stub.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print(f"통과 {len(PASSED)} · 실패 {len(FAILED)}")
    for f in FAILED:
        print(f"  실패: {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
