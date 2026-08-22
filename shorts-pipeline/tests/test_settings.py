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


def test_stale_server_detection():
    """업데이트 후 작업실을 안 껐다 켜면 새 버튼이 '알 수 없는 대상' 으로 죽는다.

    화면(HTML)은 파일에서 매번 새로 읽지만 서버 코드는 켤 때 한 번만 읽는다.
    실사용에서 정확히 이걸로 막혔다. 그 상태를 알아채는지 확인한다.
    """
    section("오래된 서버 감지")
    import time

    import ui.server as srv_mod

    check("켠 직후에는 재시작 불필요", srv_mod.needs_restart() is False)

    target = ROOT / "pipeline" / "costs.py"
    orig = target.stat().st_mtime
    os.utime(target, (time.time() + 5, time.time() + 5))
    try:
        check("코드가 바뀌면 알아챔", srv_mod.needs_restart() is True)

        server = ThreadingHTTPServer(("127.0.0.1", 0), srv_mod.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        c = Client(f"http://127.0.0.1:{server.server_address[1]}")
        try:
            _, st = c.get("/api/state")
            check("화면에 알릴 신호를 보냄", st.get("needs_restart") is True)
            code, r = c.post("/api/connect", {"target": "tiktok"})
            check("오류에 재시작하라고 붙여줌",
                  "다시 실행" in r.get("error", ""), r.get("error", "")[:60])
        finally:
            server.shutdown()
            server.server_close()
    finally:
        os.utime(target, (orig, orig))

    check("되돌리면 다시 정상", srv_mod.needs_restart() is False)


def test_app_icons():
    """바로가기·브라우저 탭이 쓰는 아이콘. 없으면 다시 기본 아이콘으로 돌아간다."""
    section("앱 아이콘")
    icons = ROOT / "brand" / "icons"

    for name in ("studio.ico", "update.ico", "folder.ico"):
        f = icons / name
        check(f"{name} 있음", f.exists())
        if not f.exists():
            continue
        raw = f.read_bytes()
        check(f"{name} 은 진짜 ICO", raw[:4] == b"\x00\x00\x01\x00", str(raw[:4]))
        # 16px 부터 256px 까지 여러 장이 들어 있어야 작업표시줄·바탕화면 양쪽에서 또렷하다
        count = int.from_bytes(raw[4:6], "little")
        check(f"{name} 에 여러 크기 담김 ({count}장)", count >= 6, str(count))
        from PIL import Image
        with Image.open(f) as im:
            got = {s2[0] for s2 in im.info.get("sizes", set())}
        check(f"{name} 에 16·32·256 포함", {16, 32, 256} <= got, str(sorted(got)))

    for name, side in (("app-32.png", 32), ("app-192.png", 192), ("app-512.png", 512)):
        f = icons / name
        check(f"{name} 있음", f.exists())
        if f.exists():
            from PIL import Image
            with Image.open(f) as im:
                check(f"{name} 크기 {side}", im.size == (side, side), str(im.size))

    # 아이콘이 없어도 바로가기 스크립트가 죽지 않아야 한다
    ps1 = (ROOT / "shortcuts.ps1").read_bytes().decode("utf-8-sig")
    check("아이콘 없을 때 기본값으로 물러남", "shell32.dll,220" in ps1)
    check("전용 아이콘을 먼저 씀", "studio.ico" in ps1)


def test_web_app_icons():
    section("브라우저 앱 아이콘")
    from ui.server import Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for path in ("/favicon.ico", "/icon-192.png", "/icon-512.png"):
            with urllib.request.urlopen(base + path, timeout=10) as r:
                body = r.read()
            check(f"{path} 내려감", r.status == 200)
            check(f"{path} 은 PNG", body[:4] == b"\x89PNG")

        with urllib.request.urlopen(base + "/manifest.webmanifest", timeout=10) as r:
            ctype = r.headers["Content-Type"]
            man = json.loads(r.read())
        # 크롬은 이 타입이 아니면 [앱으로 설치] 를 안 띄우는 경우가 있다
        check("manifest 타입이 맞음", ctype.startswith("application/manifest+json"), ctype)
        check("독립 창으로 뜸", man.get("display") == "standalone")
        check("아이콘 두 종류", len(man.get("icons", [])) == 2)
        check("이름 있음", man.get("name") == "AI DEOKHU 작업실")

        html = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        check("화면에 favicon 연결됨", 'rel="icon"' in html)
        check("화면에 manifest 연결됨", 'rel="manifest"' in html)
    finally:
        srv.shutdown()
        srv.server_close()


def test_job_output_encoding():
    """윈도우 파이썬은 파이프로 내보낼 때 코드페이지 949 를 쓴다. 한글이 깨지면 안 된다."""
    section("작업 로그 인코딩")
    import time

    from ui import jobs

    job = jobs.start("test", "인코딩",
                     ["-c", "print('브라우저가 열립니다 [허용]')"], ROOT)
    for _ in range(60):
        time.sleep(0.15)
        if job.status != "running":
            break
    check("자식 프로세스가 끝남", job.status == "done", job.status)
    got = "\n".join(job.lines)
    check("한글이 안 깨짐", "브라우저가 열립니다 [허용]" in got, got[:60])
    check("깨짐 문자 없음", "\ufffd" not in got)


def test_connect_youtube_survives_scope_error():
    """업로드 전용 권한이라 channels.list 는 403 이 난다. 그걸로 실패 처리하면 안 된다."""
    section("유튜브 연결 검증")
    import publish.youtube as yt_mod
    from typer.testing import CliRunner

    import main as main_mod

    secrets = ROOT / "secrets"
    secrets.mkdir(exist_ok=True)
    secret = secrets / "client_secret.json"
    had_secret = secret.exists()
    backup = secret.read_bytes() if had_secret else None
    secret.write_text('{"installed": {"client_id": "x"}}', encoding="utf-8")

    class FakeCreds:
        refresh_token = "1//fake-refresh"

    def boom(*a, **k):
        raise RuntimeError("insufficientPermissions (403)")

    real_creds, real_libs = yt_mod._credentials, yt_mod._require_libs
    yt_mod._credentials = lambda: FakeCreds()
    yt_mod._require_libs = lambda: (None, None, None, boom, None)
    try:
        res = CliRunner().invoke(main_mod.app, ["connect-youtube"])
        check("403 이 나도 성공으로 끝남", res.exit_code == 0, str(res.exit_code))
        check("연결 완료라고 알림", "연결 완료" in res.output, res.output[-120:])

        # 갱신용 토큰이 없으면 경고해야 한다 (내일부터 조용히 실패하는 경우)
        class NoRefresh:
            refresh_token = None

        yt_mod._credentials = lambda: NoRefresh()
        res = CliRunner().invoke(main_mod.app, ["connect-youtube"])
        check("갱신 토큰 없으면 경고", "갱신용 토큰" in res.output, res.output[-120:])
        check("그래도 실패로 끝내지는 않음", res.exit_code == 0, str(res.exit_code))
    finally:
        yt_mod._credentials, yt_mod._require_libs = real_creds, real_libs
        if backup is None:
            secret.unlink(missing_ok=True)
        else:
            secret.write_bytes(backup)


def test_ig_two_login_paths():
    """메타는 인스타 게시 API 를 두 갈래로 나눠놨고 서버 주소가 다르다.

    사용자가 어느 쪽으로 발급받았는지 알 필요 없어야 한다. 토큰을 보고 우리가 고른다.
    """
    section("인스타 토큰 두 종류")
    from publish.instagram import GRAPH_FB, GRAPH_IG, api_base

    for tok in ("IGAAabc123", "IGQVJxyz"):
        check(f"{tok[:4]}… 는 graph.instagram.com", api_base(tok) == GRAPH_IG)
    for tok in ("EAAG123", "EAAB456"):
        check(f"{tok[:3]}… 는 graph.facebook.com", api_base(tok) == GRAPH_FB)
    check("모르는 모양은 페이스북으로 (기존 동작 유지)", api_base("zzz") == GRAPH_FB)
    check("빈 토큰도 안 터짐", api_base("") == GRAPH_FB)

    # 계정 ID 찾는 방법도 갈래마다 다르다
    import contextlib
    import io
    import urllib.request

    import main as main_mod

    def fake(payload):
        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self):
                return json.dumps(payload).encode()
        return lambda *a, **k: R()

    def run(tok, payload):
        real = urllib.request.urlopen
        urllib.request.urlopen = fake(payload)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return main_mod._find_ig_user_id(tok)
        finally:
            urllib.request.urlopen = real

    got = run("IGAAxyz", {"user_id": "17841400000000009", "username": "ai.deokhu"})
    check("인스타 로그인: /me 로 찾음", got == ("17841400000000009", "@ai.deokhu"), str(got))

    got = run("EAAG123", {"data": [{"name": "Ai.deokhu",
                                    "instagram_business_account": {"id": "1784140000001"}}]})
    check("페이스북 로그인: 페이지에서 찾음", got == ("1784140000001", "Ai.deokhu"), str(got))

    got = run("IGAAxyz", {"username": "no-id-here"})
    check("인스타 로그인인데 ID 가 없으면 None", got is None)


def test_ig_user_id_autodiscovery():
    """계정 ID 를 사람이 그래프 API 탐색기에서 옮겨 적게 하지 않는다."""
    section("인스타 계정 ID 자동 찾기")
    import contextlib
    import io
    import urllib.request

    import main as main_mod

    def fake(payload):
        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self):
                return json.dumps(payload).encode()
        return lambda *a, **k: R()

    def run(payload):
        real = urllib.request.urlopen
        urllib.request.urlopen = fake(payload)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                got = main_mod._find_ig_user_id("tok")
        finally:
            urllib.request.urlopen = real
        return got, buf.getvalue()

    got, _ = run({"data": [{"name": "AI DEOKHU",
                            "instagram_business_account": {"id": "17841400000000001"}}]})
    check("연결된 계정을 찾음", got == ("17841400000000001", "AI DEOKHU"), str(got))

    got, out = run({"data": [
        {"name": "AI DEOKHU", "instagram_business_account": {"id": "1784140000000001"}},
        {"name": "다른페이지", "instagram_business_account": {"id": "1784140000000002"}}]})
    check("여러 개면 첫 번째를 쓰고 알림", got[0] == "1784140000000001" and "여러 개" in out)

    got, out = run({"data": [{"name": "빈페이지"}]})
    check("인스타 연결 안 됐으면 None", got is None)
    check("왜 안 되는지 알려줌", "연결돼 있지 않습니다" in out, out.strip()[:60])

    got, _ = run({"data": []})
    check("페이지가 없으면 None", got is None)

    # 조회가 터져도 예외를 밖으로 던지지 않는다
    def boom(*a, **k):
        raise OSError("down")

    real = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        check("조회 실패해도 None 으로 끝남", main_mod._find_ig_user_id("tok") is None)
    finally:
        urllib.request.urlopen = real


def test_ig_token_expiry_warning():
    """탐색기에서 그냥 복사한 임시 토큰(1~2시간)을 넣는 것이 가장 흔한 함정이다."""
    section("인스타 토큰 만료 안내")
    import contextlib
    import io
    import time
    import urllib.request

    import main as main_mod

    def fake(payload):
        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self):
                return json.dumps({"data": payload}).encode()
        return lambda *a, **k: R()

    def run(payload):
        real = urllib.request.urlopen
        urllib.request.urlopen = fake(payload)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                main_mod._report_ig_expiry("tok")
        finally:
            urllib.request.urlopen = real
        return buf.getvalue()

    now = time.time()
    out = run({"expires_at": 0})
    check("만료 0 은 '없음' 으로 읽음", "만료: 없음" in out, out.strip()[:50])

    # 인스타 로그인 토큰은 debug_token 을 못 쓴다. 조용히 넘어가면 사용자는
    # 만료가 없는 줄 오해한다. 통상값을 알려주는지 본다.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main_mod._report_ig_expiry("IGAAxyz")
    ig_out = buf.getvalue()
    check("인스타 로그인 토큰은 따로 안내", "보통 60일" in ig_out, ig_out.strip()[:60])
    check("재발급 위치도 알려줌", "다시 발급" in ig_out)

    out = run({"expires_at": int(now + 3600)})
    check("임시 토큰이면 경고", "임시 토큰" in out, out.strip()[:50])
    check("고치는 방법까지 알려줌", "확장 액세스 토큰" in out)

    out = run({"expires_at": int(now + 5 * 86400)})
    check("곧 만료면 미리 알림", "5일 뒤 만료" in out, out.strip()[:50])

    out = run({"expires_at": int(now + 59 * 86400)})
    check("넉넉하면 남은 날짜만", "59일 남았습니다" in out, out.strip()[:50])
    check("넉넉하면 경고 안 함", "임시 토큰" not in out)

    check("값이 없으면 조용히 넘어감", run({}).strip() == "")

    # 확인에 실패해도 연결 자체를 실패로 만들면 안 된다
    def boom(*a, **k):
        raise OSError("network down")

    real = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        main_mod._report_ig_expiry("tok")
        ok = True
    except Exception:
        ok = False
    finally:
        urllib.request.urlopen = real
    check("확인 실패해도 안 터짐", ok)


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
        test_stale_server_detection()
        test_app_icons()
        test_web_app_icons()
        test_job_output_encoding()
        test_connect_youtube_survives_scope_error()
        test_ig_two_login_paths()
        test_ig_user_id_autodiscovery()
        test_ig_token_expiry_warning()
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
