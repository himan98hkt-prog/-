"""설정 저장 · 간편 모드 · 실행 스크립트 인코딩 검사 (API 호출 0회)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from pipeline import envfile  # noqa: E402

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_settings"


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"  {'✓' if cond else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def section(title):
    print(f"\n── {title} " + "─" * max(0, 56 - len(title)))


# ── .env 읽고 쓰기 ───────────────────────────────────────────────────
def test_envfile():
    section(".env 읽고 쓰기")
    TMP.mkdir(parents=True, exist_ok=True)
    f = TMP / ".env"

    f.write_text("# 머리말\nFAL_API_KEY=\n\n# 다른 묶음\nIG_USER_ID=123\n"
                 "SOMETHING_ELSE=keepme\n", encoding="utf-8")
    changed = envfile.write({"FAL_API_KEY": "sk-live-1", "S3_BUCKET": "bkt"}, f)
    raw = envfile.read_raw(f)
    text = f.read_text(encoding="utf-8")

    check("기존 값 제자리 수정", raw["FAL_API_KEY"] == "sk-live-1")
    check("없던 키는 뒤에 추가", raw["S3_BUCKET"] == "bkt")
    check("주석 보존", "# 머리말" in text and "# 다른 묶음" in text)
    check("건드리지 않은 줄 유지", raw["IG_USER_ID"] == "123")
    check("바뀐 키만 보고", sorted(changed) == ["FAL_API_KEY", "S3_BUCKET"], str(changed))

    # 허용 목록 밖의 키는 저장 요청이 와도 무시한다
    envfile.write({"SOMETHING_ELSE": "hacked", "PATH": "/evil"}, f)
    raw = envfile.read_raw(f)
    check("허용 목록 밖 키 무시", raw["SOMETHING_ELSE"] == "keepme", raw["SOMETHING_ELSE"])
    check("PATH 같은 위험한 키 안 씀", "PATH=" not in f.read_text(encoding="utf-8"))

    # 빈 값은 줄을 남기고 값만 비운다
    envfile.write({"S3_BUCKET": ""}, f)
    check("값 비우기", envfile.read_raw(f)["S3_BUCKET"] == "")
    check("줄은 남음", "S3_BUCKET=" in f.read_text(encoding="utf-8"))

    # 따옴표와 export 접두사
    f.write_text('export FAL_API_KEY="따옴표 안"\n', encoding="utf-8")
    check("export/따옴표 해석", envfile.read_raw(f)["FAL_API_KEY"] == "따옴표 안")

    # 임시 파일에 쓸 때는 진짜 os.environ 을 안 건드린다
    before = os.environ.get("S3_BUCKET")
    envfile.write({"S3_BUCKET": "temp-only"}, f)
    check("테스트 경로는 환경변수 오염 없음", os.environ.get("S3_BUCKET") == before)

    # 시스템 환경변수가 .env 를 가로채는 경우를 알려준다
    real = ROOT / ".env"
    backup = real.read_bytes() if real.exists() else None
    try:
        real.write_text("S3_BUCKET=from-env-file\n", encoding="utf-8")
        os.environ["S3_BUCKET"] = "from-system"
        snap = {x["key"]: x for x in envfile.snapshot()["fields"]}
        check("가로채기 알림", snap["S3_BUCKET"]["overridden"] is True)
        check("화면에는 .env 값을 보여줌", snap["S3_BUCKET"]["value"] == "from-env-file",
              snap["S3_BUCKET"]["value"])
        os.environ["S3_BUCKET"] = "from-env-file"
        snap = {x["key"]: x for x in envfile.snapshot()["fields"]}
        check("같은 값이면 알림 없음", snap["S3_BUCKET"]["overridden"] is False)
    finally:
        os.environ.pop("S3_BUCKET", None)
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)

    # 마스킹
    check("긴 비밀값 마스킹", envfile.mask("0123456789abcdef") == "0123******cdef")
    check("짧은 값은 길이만", envfile.mask("abc") == "***")
    check("빈 값은 빈 문자열", envfile.mask("") == "")
    check("마스킹에 원문이 안 남음",
          "56789ab" not in envfile.mask("0123456789abcdef"))


# ── HTTP 엔드포인트 ──────────────────────────────────────────────────
class Client:
    def __init__(self, base):
        self.base = base

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.status, json.loads(r.read())

    def post(self, path, body, headers=None):
        head = {"Content-Type": "application/json"}
        head.update(headers or {})
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode(), headers=head)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())


def test_endpoints():
    section("작업실 화면 API")
    from ui.server import Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
    try:
        code, simple = c.get("/api/simple")
        check("간편 모드 응답", code == 200)
        check("연결 상태 네 칸", set(simple.get("connections", {})) ==
              {"video", "youtube", "instagram", "storage"})
        check("다음 할 일 하나", bool(simple.get("next_step", {}).get("action")))
        check("다음 할 일이 아는 화면을 가리킴",
              simple["next_step"]["go"] in ("settings", "images", "make"),
              simple["next_step"]["go"])
        check("오늘 계획에 비용 포함", simple.get("plan", {}).get("cost") is not None)

        code, st = c.get("/api/settings")
        check("설정 응답", code == 200)
        keys = {f["key"] for f in st["fields"]}
        check("fal 키 항목 있음", "FAL_API_KEY" in keys)
        check("비밀 항목은 secret 표시",
              all(f["secret"] for f in st["fields"]
                  if f["key"] in ("FAL_API_KEY", "IG_ACCESS_TOKEN",
                                  "AWS_SECRET_ACCESS_KEY")))
        check("비밀 항목 원문 노출 없음",
              all("*" in f["value"] or not f["value"]
                  for f in st["fields"] if f["secret"]))

        # 잘못된 client_secret.json 은 거절한다
        import base64

        def blob(obj):
            raw = base64.b64encode(json.dumps(obj).encode()).decode()
            return "data:application/json;base64," + raw

        code, r = c.post("/api/client-secret", {"data": blob({"web": {"client_id": "x"}})})
        check("웹 앱용 JSON 거절", code == 400 and "데스크톱" in r.get("error", ""))
        code, r = c.post("/api/client-secret", {"data": blob({"nope": 1})})
        check("엉뚱한 JSON 거절", code == 400)
        code, r = c.post("/api/client-secret",
                         {"data": "data:application/json;base64," +
                                  base64.b64encode(b"not json").decode()})
        check("JSON 아닌 파일 거절", code == 400)
        code, r = c.post("/api/client-secret", {"data": "쓰레기"})
        check("형식 깨진 요청 거절", code == 400)

        code, r = c.post("/api/connect", {"target": "tiktok"})
        check("모르는 연결 대상 거절", code == 400)

        code, r = c.post("/api/settings", {"values": "문자열"})
        check("dict 아닌 값 거절", code == 400)

        # 다른 웹사이트가 몰래 부르는 것을 막는다
        code, r = c.post("/api/settings", {"values": {"S3_BUCKET": "evil"}},
                         {"Content-Type": "text/plain"})
        check("JSON 아닌 content-type 거절", code == 403, str(code))
        code, r = c.post("/api/settings", {"values": {"S3_BUCKET": "evil"}},
                         {"Origin": "https://evil.example"})
        check("남의 사이트 Origin 거절", code == 403, str(code))
        code, r = c.post("/api/generate", {"seed": "x.png"},
                         {"Content-Type": "text/plain"})
        check("돈 드는 생성도 막힘", code == 403, str(code))
        code, r = c.post("/api/settings", {"values": {}},
                         {"Origin": f"http://127.0.0.1:{srv.server_address[1]}"})
        check("내 화면에서 온 요청은 통과", code == 200, str(code))
    finally:
        srv.shutdown()
        srv.server_close()


def test_masked_echo_is_ignored():
    """화면이 마스킹된 값을 그대로 돌려보내도 진짜 키를 별표로 덮으면 안 된다."""
    section("마스킹된 값 되돌려보내기")
    from ui.server import Handler

    real = ROOT / ".env"
    backup = real.read_bytes() if real.exists() else None
    real.write_text("FAL_API_KEY=sk-real-secret-value\n", encoding="utf-8")
    os.environ.pop("FAL_API_KEY", None)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
    try:
        _, st = c.get("/api/settings")
        shown = next(f["value"] for f in st["fields"] if f["key"] == "FAL_API_KEY")
        check("화면에 원문이 안 나감", "real-secret" not in shown, shown)

        # 화면이 본 그대로 저장 요청을 보낸다 (사용자가 아무것도 안 고친 경우)
        c.post("/api/settings", {"values": {"FAL_API_KEY": shown}})
        check("진짜 키가 살아 있음",
              envfile.read_raw(real).get("FAL_API_KEY") == "sk-real-secret-value",
              envfile.read_raw(real).get("FAL_API_KEY"))

        # 진짜로 고치면 반영된다
        c.post("/api/settings", {"values": {"FAL_API_KEY": "sk-brand-new"}})
        check("새 값은 반영됨",
              envfile.read_raw(real).get("FAL_API_KEY") == "sk-brand-new")
    finally:
        srv.shutdown()
        srv.server_close()
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)
        os.environ.pop("FAL_API_KEY", None)


# ── 윈도우에서 깨지지 않는 실행 파일 ─────────────────────────────────
def test_script_encoding():
    section("실행 스크립트 인코딩")
    BOM = b"\xef\xbb\xbf"
    for name in ("update.bat", "shortcuts.bat", "start.bat"):
        raw = (ROOT / name).read_bytes()
        # cmd 는 OEM 코드페이지로 읽는다. 한글을 넣으면 명령으로 실행되려다 깨진다.
        check(f"{name} 는 ASCII 만", all(b < 128 for b in raw))
        check(f"{name} 줄바꿈 CRLF", b"\n" in raw and raw.replace(b"\r\n", b"").count(b"\n") == 0)

    for name in ("update.ps1", "shortcuts.ps1", "start.ps1", "install.ps1"):
        raw = (ROOT / name).read_bytes()
        # 파워셸 5.1 은 BOM 없는 UTF-8 을 코드페이지 949 로 읽어 문자열을 깬다.
        check(f"{name} 에 UTF-8 BOM", raw.startswith(BOM))
        try:
            raw.decode("utf-8-sig")
            ok = True
        except UnicodeDecodeError:
            ok = False
        check(f"{name} 는 올바른 UTF-8", ok)


def test_daily_bat_is_ascii():
    section("예약 실행 배치")
    from pipeline import win_schedule as ws

    real = ROOT / "daily.bat"
    backup = real.read_bytes() if real.exists() else None
    try:
        bat = ws.write_runner("21:00", ["youtube", "instagram"], "chain")
        raw = bat.read_bytes()
        check("daily.bat 은 ASCII 만", all(b < 128 for b in raw))
        text = raw.decode("ascii")
        check("게시 시각이 들어감", "--at 21:00" in text)
        check("업로드 대상이 들어감", "--youtube" in text and "--instagram" in text)
        check("폴더를 따라감", "%~dp0" in text)
        st = ws.status()          # 윈도우가 아니면 enabled=False 로 조용히 돌아온다
        check("리눅스에서 status() 가 안 터짐", st.enabled is False)
    finally:
        if backup is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(backup)


def test_auto_needs_seed():
    section("간편 모드 안전장치")
    from ui.server import Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
    try:
        code, r = c.post("/api/auto", {"seed": "../../etc/passwd"})
        check("경로 탈출 시도 차단", code == 400, r.get("error", ""))
        code, r = c.post("/api/auto", {"seed": "없는파일.png"})
        check("없는 이름 차단", code == 400)
    finally:
        srv.shutdown()
        srv.server_close()


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    try:
        test_envfile()
        test_endpoints()
        test_masked_echo_is_ignored()
        test_script_encoding()
        test_daily_bat_is_ascii()
        test_auto_needs_seed()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    print("═" * 62)
    if FAILED:
        for f in FAILED:
            print(f"  ✗ {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
