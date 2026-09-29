"""LTX 클라우드(LTX API) 엔진 — 가짜 LTX 서버로 끝까지 시험한다.

    python tests/test_ltx_api.py

LTX Desktop 이 8GB 그래픽카드에서 영상을 만드는 경로와 같은 API 다.
진짜 서버 대신 같은 모양으로 답하는 가짜를 띄운다. 요청 모양(업로드 순서,
필드 이름, 해상도 문자열, 인증 헤더)은 LTX Desktop 의 ltx_api_client 와
맞춰 두었다. 돈은 한 푼도 안 나간다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_ltxapi"
KEY = "ltxv_test_key_1234"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


class FakeLTX(BaseHTTPRequestHandler):
    """POST /v1/upload · PUT /put/<n> · POST /v1/image-to-video 만 안다."""

    calls: list = []
    mode = "bytes"          # bytes | url | 401 | 402 | 422
    uploads: dict = {}

    def log_message(self, *a):
        pass

    def _auth_ok(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {KEY}"

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("x-request-id", "req-42")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        FakeLTX.calls.append(("POST", self.path, dict(self.headers), raw))
        if not self._auth_ok() or FakeLTX.mode == "401":
            return self._send(401, b'{"error":"unauthorized"}')
        host = f"http://127.0.0.1:{self.server.server_address[1]}"
        if self.path == "/v1/upload":
            i = len(FakeLTX.uploads)
            return self._send(200, json.dumps({
                "upload_url": f"{host}/put/{i}", "storage_uri": f"ltx://store/{i}",
                "required_headers": {"x-goog-meta-test": "1"}}).encode())
        if self.path == "/v1/image-to-video":
            if FakeLTX.mode == "402":
                return self._send(402, b'{"error":{"type":"insufficient_funds_error"}}')
            body = json.loads(raw)
            if body.get("image_uri") not in [f"ltx://store/{k}" for k in FakeLTX.uploads]:
                return self._send(422, b'{"error":"unknown image_uri"}')
            w, h = (int(x) for x in body["resolution"].split("x"))
            clip = TMP / f"out_{len(FakeLTX.calls)}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            f"testsrc2=size={w // 4}x{h // 4}:rate={int(body['fps'])}"
                            f":duration={body['duration']}",
                            "-vf", f"scale={w}:{h}", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", "-y", str(clip)], check=True)
            if FakeLTX.mode == "url":
                FakeLTX.uploads[f"video{len(FakeLTX.calls)}"] = clip.read_bytes()
                return self._send(200, json.dumps(
                    {"video_url": f"{host}/files/video{len(FakeLTX.calls)}"}).encode())
            return self._send(200, clip.read_bytes(), "video/mp4")
        self._send(404, b"{}")

    def do_PUT(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n)
        FakeLTX.calls.append(("PUT", self.path, dict(self.headers), b""))
        FakeLTX.uploads[self.path.rsplit("/", 1)[-1]] = data
        self._send(200, b"")

    def do_GET(self):
        FakeLTX.calls.append(("GET", self.path, dict(self.headers), b""))
        key = self.path.rsplit("/", 1)[-1]
        if key in FakeLTX.uploads:
            return self._send(200, FakeLTX.uploads[key], "video/mp4")
        self._send(404, b"")


def start_server() -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLTX)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def reset(mode: str = "bytes") -> None:
    FakeLTX.calls, FakeLTX.uploads, FakeLTX.mode = [], {}, mode


def seed(path: Path) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1080, 1920), (30, 40, 70)).save(path)
    return path


# ══════════════════════════════════════════════════════════════════════
def test_request_shape(base: str):
    section("요청 모양 — LTX Desktop 과 같게")
    from pipeline.providers.base import GenerationRequest
    from pipeline.providers.ltx_api import LtxApiProvider

    reset()
    os.environ["LTX_API_KEY"] = KEY
    img = seed(TMP / "a.png")
    prov = LtxApiProvider("ltx-2-5-fast/1080p", base_url=base)
    res = prov.generate(GenerationRequest(image=img, prompt="앞으로 계속", duration=10),
                        TMP / "clip_01.mp4")
    order = [(m, p.split("/")[1] if p.count("/") > 1 else p) for m, p, _, _ in FakeLTX.calls]
    check("업로드 준비 -> 업로드 -> 생성 순서",
          [c[0] for c in FakeLTX.calls] == ["POST", "PUT", "POST"], str(order))
    put_headers = FakeLTX.calls[1][2]
    check("업로드에 서버가 요구한 헤더를 붙인다",
          put_headers.get("x-goog-meta-test") == "1" and put_headers.get("Content-Type") == "image/png")
    body = json.loads(FakeLTX.calls[2][3])
    check("모델 ltx-2-5-fast", body["model"] == "ltx-2-5-fast")
    check("세로 1080x1920", body["resolution"] == "1080x1920")
    check("길이·프레임률은 숫자(float)", body["duration"] == 10.0 and body["fps"] == 24.0)
    check("올린 이미지를 image_uri 로", body["image_uri"] == "ltx://store/0")
    check("소리는 받지 않는다 (음악을 깐다)", body["generate_audio"] is False)
    check("Bearer 키로 인증", FakeLTX.calls[2][2].get("Authorization") == f"Bearer {KEY}")
    check("영상을 받아 저장", res.video_path.exists() and res.video_path.stat().st_size > 1000)
    check("요청 번호를 남긴다", res.job_id == "req-42")

    reset("url")
    prov.generate(GenerationRequest(image=img, prompt="p", duration=5), TMP / "clip_02.mp4")
    check("video_url 로 줘도 받아온다",
          (TMP / "clip_02.mp4").stat().st_size > 1000 and FakeLTX.calls[-1][0] == "GET")

    reset()
    end = seed(TMP / "end.png")
    prov.generate(GenerationRequest(image=img, prompt="p", duration=5, end_image=end),
                  TMP / "clip_03.mp4")
    body = json.loads([c for c in FakeLTX.calls if c[1] == "/v1/image-to-video"][0][3])
    check("끝 장면도 올려 last_frame_uri 로 (루프용)", body.get("last_frame_uri") == "ltx://store/1")


def test_limits_and_errors(base: str):
    section("길이 제한 · 오류 — 돈이 나갔는지 정직하게")
    from pipeline.providers.base import GenerationRequest, ProviderError
    from pipeline.providers.ltx_api import LtxApiProvider

    img = seed(TMP / "b.png")
    os.environ["LTX_API_KEY"] = KEY

    def err(endpoint: str, duration: int, mode: str = "bytes") -> ProviderError | None:
        reset(mode)
        try:
            LtxApiProvider(endpoint, base_url=base).generate(
                GenerationRequest(image=img, prompt="p", duration=duration), TMP / "x.mp4")
        except ProviderError as exc:
            return exc
        return None

    check("Fast 는 20초 한 번에 된다", err("ltx-2-5-fast/1080p", 20) is None)
    e = err("ltx-2-5-pro/1080p", 20)
    check("Pro 는 20초가 안 된다고 미리 말한다", e is not None and "10" in str(e) and e.billed is False)
    e = err("ltx-2-5-fast/1080p", 7)
    check("7초처럼 안 되는 길이는 보내기 전에 막는다", e is not None and e.billed is False
          and not any(c[1] == "/v1/image-to-video" for c in FakeLTX.calls))
    e = err("ltx-2-5-fast/1080p", 5, "402")
    check("크레딧 부족: 알아듣게 · 과금 없음 · 재시도 안 함",
          e is not None and "크레딧" in str(e) and e.billed is False and not e.retryable)
    e = err("ltx-2-5-fast/1080p", 5, "401")
    check("키가 틀리면 그렇게 말한다", e is not None and "틀렸" in str(e) and e.billed is False)

    os.environ.pop("LTX_API_KEY")
    try:
        LtxApiProvider("ltx-2-5-fast/1080p", base_url=base)
        ok = False
    except ProviderError as exc:
        ok = "LTX Desktop" in str(exc) and exc.billed is False
    check("키가 없으면 어디서 복사하는지 알려준다", ok)
    os.environ["LTX_API_KEY"] = KEY


def test_config_and_cost():
    section("설정 · 비용")
    from pipeline.config import load_config
    from pipeline.costs import estimate

    raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["providers"].pop("ltx", None)             # 업데이트 전 사용자 config
    raw.update(provider="ltx", model="ltx_25_fast_1080p", num_clips=1, clip_duration=20)
    p = TMP / "old.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    cfg = load_config(p)
    e = estimate(cfg)
    check("블록이 없어도 읽힌다", cfg.provider == "ltx")
    check("20초 1080p = $2.60", round(e.subtotal, 2) == 2.60, f"${e.subtotal:.2f}")
    raw["model"] = "ltx_25_fast_720p"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    check("20초 720p = $1.80", round(estimate(load_config(p)).subtotal, 2) == 1.80)
    check("업스케일러 esrgan -> 내 PC 것으로 대신", cfg.upscaler.key == "local")


def test_end_to_end(base: str):
    section("처음부터 끝까지 — 한 번에 20초, 합성까지")
    from pipeline.ffmpeg_util import dimensions_of, duration_of

    reset()
    img = seed(TMP / "seed.png")
    raw = yaml.safe_load((ROOT / "tests" / "config.test.yaml").read_text(encoding="utf-8"))
    raw.update(provider="ltx", model="ltx_25_fast_1080p", num_clips=1, clip_duration=20)
    raw["output"]["fps"] = "auto"
    raw["providers"]["ltx"] = {"endpoint_base": base}
    cfg = TMP / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    before = {x.name for x in runs.iterdir()}
    env = dict(os.environ, LTX_API_KEY=KEY, PYTHONIOENCODING="utf-8")
    env.pop("SHORTS_MOCK", None)
    try:
        p = subprocess.run([sys.executable, "main.py", "generate", "--image", str(img),
                            "--config", str(cfg), "--yes"], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        new = sorted(x for x in runs.iterdir() if x.is_dir() and x.name not in before)
        final = new[-1] / "final.mp4" if new else None
        ok = p.returncode == 0 and final is not None and final.exists()
        check("완성", ok, (p.stdout + p.stderr)[-500:] if not ok else "")
        if ok:
            check("1080x1920", dimensions_of(final) == (1080, 1920))
            check("20초 한 컷", 19.5 < duration_of(final) < 20.5, f"{duration_of(final):.2f}초")
            state = json.loads((new[-1] / "state.json").read_text("utf-8"))
            check("비용 $2.60 로 기록", abs(float(state.get("cost_usd", 0)) - 2.60) < 0.01,
                  str(state.get("cost_usd")))
        check("LTX 생성은 한 번", sum(1 for c in FakeLTX.calls
                                      if c[1] == "/v1/image-to-video") == 1)
    finally:
        for x in runs.iterdir():
            if x.is_dir() and x.name not in before:
                shutil.rmtree(x, ignore_errors=True)


def test_engine_switch():
    section("작업실에서 LTX 클라우드 고르기")
    import ui.server as srv

    cfg_copy = TMP / "switch.yaml"
    shutil.copyfile(ROOT / "config.yaml", cfg_copy)
    real_cfg, real_env = srv.CONFIG, os.environ.pop("LTX_API_KEY", None)
    from pipeline import envfile
    real_read = envfile.read_raw
    srv.CONFIG = cfg_copy
    try:
        envfile.read_raw = lambda path=None: {}
        ok, msg = srv.switch_engine("ltx")
        check("키가 없으면 안 바꾸고 어디에 넣는지 알려준다", not ok and "[설정]" in msg)
        envfile.read_raw = lambda path=None: {"LTX_API_KEY": KEY}
        ok, msg = srv.switch_engine("ltx")
        text = cfg_copy.read_text("utf-8")
        check("키가 있으면 바꾼다", ok, msg)
        check("provider/model", "\nprovider: ltx" in text and "\nmodel: ltx_25_fast_1080p" in text)
        check("한 번에 20초 (1개 x 20초)", "\nnum_clips: 1" in text and "\nclip_duration: 20" in text)
        from pipeline.config import load_config
        check("바꾼 설정이 그대로 읽힌다", load_config(cfg_copy).clip_duration == 20)
        envfile.read_raw = real_read
        ok, _ = srv.switch_engine("fal")
        text = cfg_copy.read_text("utf-8")
        check("fal 로 돌아가면 2개 x 10초 (hailuo 상한)",
              ok and "\nnum_clips: 2" in text and "\nclip_duration: 10" in text)
        check("돌아간 설정도 오류 없이 읽힌다", load_config(cfg_copy).model_key == "hailuo_23_pro")
    finally:
        srv.CONFIG = real_cfg
        envfile.read_raw = real_read
        if real_env is not None:
            os.environ["LTX_API_KEY"] = real_env
    html = (ROOT / "ui" / "app.html").read_text(encoding="utf-8")
    check("화면에 LTX 클라우드 선택지", 'name="eng" value="ltx"' in html)


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    srv, base = start_server()
    old = os.environ.get("LTX_API_KEY")
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                try:
                    fn(base) if fn.__code__.co_argcount else fn()
                except Exception as exc:              # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check(f"{name} 가 예외 없이 끝난다", False, repr(exc))
    finally:
        srv.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)
        if old is None:
            os.environ.pop("LTX_API_KEY", None)
        else:
            os.environ["LTX_API_KEY"] = old
    print(f"\n통과 {len(PASSED)} · 실패 {len(FAILED)}")
    for f in FAILED:
        print(f"  X {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
