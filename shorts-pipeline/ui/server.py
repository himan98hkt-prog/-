"""로컬 웹 UI 서버.

터미널 대신 브라우저에서 이미지를 골라 클릭으로 영상을 만들고 올린다.
추가 설치 없이 파이썬 표준 라이브러리만 쓴다.

  python main.py ui
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import jobs

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "seeds"
RUNS = ROOT / "runs"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_THUMBS: dict[str, bytes] = {}
_THUMB_LOCK = threading.Lock()

# 경로 파라미터로 상위 폴더를 타고 나가지 못하게 한다
_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _safe_name(name: str) -> str | None:
    return name if name and _SAFE.match(name) and ".." not in name else None


# ── 데이터 수집 ───────────────────────────────────────────────────────
def list_seeds() -> list[dict]:
    from pipeline.content import load_content

    if not SEEDS.is_dir():
        return []
    out = []
    for p in sorted(SEEDS.iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXT:
            continue
        c = load_content(p)
        out.append({
            "name": p.name,
            "theme": p.stem.rsplit("_", 1)[0],
            "title": c.title,
            "hook": c.hook,
            "prompt": c.prompt,
            "has_meta": c.source is not None,
        })
    return out


def list_runs(limit: int = 30) -> list[dict]:
    if not RUNS.is_dir():
        return []
    out = []
    for d in sorted(RUNS.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        final = d / "final.mp4"
        state = {}
        sp = d / "state.json"
        if sp.exists():
            try:
                state = json.loads(sp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        content = state.get("content", {})
        out.append({
            "id": d.name,
            "ready": final.exists(),
            "size_mb": round(final.stat().st_size / 1048576, 1) if final.exists() else 0,
            "duration": state.get("duration"),
            "cost": state.get("cost_usd"),
            "mode": state.get("mode"),
            "title": content.get("title", ""),
            "hook": content.get("hook", ""),
        })
        if len(out) >= limit:
            break
    return out


def doctor_state() -> dict:
    from pipeline.config import load_config
    from pipeline.doctor import run_all

    try:
        cfg = load_config(ROOT / "config.yaml")
        sections, can_generate = run_all(ROOT, cfg)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "sections": []}
    return {
        "ok": True,
        "can_generate": can_generate,
        "sections": [
            {"title": s.title, "required": s.required_for, "ready": s.ready,
             "checks": [{"name": c.name, "status": c.status,
                         "detail": c.detail, "fix": c.fix} for c in s.checks]}
            for s in sections
        ],
    }


def estimate(mode: str, clips: int, duration: int) -> dict:
    from pipeline.config import load_config
    from pipeline.costs import estimate as est

    try:
        cfg = load_config(ROOT / "config.yaml", mode=mode,
                          num_clips=clips, clip_duration=duration)
        e = est(cfg)
        return {"ok": True, "expected": round(e.expected, 2),
                "subtotal": round(e.subtotal, 2),
                "seconds": round(e.output_seconds, 1),
                "model": f"{e.provider}/{e.model}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def thumbnail(name: str, box: int = 320) -> bytes | None:
    with _THUMB_LOCK:
        if name in _THUMBS:
            return _THUMBS[name]
    path = SEEDS / name
    if not path.exists():
        return None
    from PIL import Image

    img = Image.open(path)
    img.draft("RGB", (box * 2, box * 2))
    img = img.convert("RGB")
    img.thumbnail((box, box), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=82)
    data = buf.getvalue()
    with _THUMB_LOCK:
        _THUMBS[name] = data
    return data


# ── HTTP ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "AIDeokhuUI/1.0"

    def log_message(self, fmt, *args):        # 콘솔을 요청 로그로 채우지 않는다
        pass

    # -- 응답 도우미 --------------------------------------------------
    def _json(self, payload, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data: bytes, ctype: str, cache: bool = True) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, ctype: str | None = None) -> None:
        """Range 지원. 브라우저 동영상 재생에 필요하다."""
        size = path.stat().st_size
        ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            part = rng[6:].split("-")
            try:
                if part[0]:
                    start = int(part[0])
                if len(part) > 1 and part[1]:
                    end = int(part[1])
            except ValueError:
                start, end = 0, size - 1
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(262144, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return          # 사용자가 재생을 멈춘 것뿐이다
                remaining -= len(chunk)

    # -- 라우팅 -------------------------------------------------------
    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path

        if p in ("/", "/index.html"):
            html = (Path(__file__).parent / "app.html").read_bytes()
            self._bytes(html, "text/html; charset=utf-8", cache=False)
            return

        if p == "/api/state":
            self._json({
                "seeds": list_seeds(),
                "runs": list_runs(),
                "jobs": jobs.recent(),
                "active": (jobs.active().snapshot() if jobs.active() else None),
            })
            return

        if p == "/api/doctor":
            self._json(doctor_state())
            return

        if p == "/api/estimate":
            self._json(estimate(
                q.get("mode", ["chain"])[0],
                int(q.get("clips", ["6"])[0]),
                int(q.get("duration", ["5"])[0])))
            return

        if p == "/api/job":
            job = jobs.get(q.get("id", [""])[0])
            self._json(job.snapshot() if job else {"error": "없는 작업"},
                       200 if job else 404)
            return

        if p == "/api/thumb":
            name = _safe_name(q.get("name", [""])[0])
            data = thumbnail(name) if name else None
            if data:
                self._bytes(data, "image/jpeg")
            else:
                self.send_error(404)
            return

        if p == "/api/video":
            run_id = _safe_name(q.get("run", [""])[0])
            if not run_id:
                self.send_error(400)
                return
            path = RUNS / run_id / "final.mp4"
            if not path.exists():
                self.send_error(404)
                return
            self._file(path, "video/mp4")
            return

        self.send_error(404)

    def do_HEAD(self) -> None:
        """일부 플레이어는 GET 전에 HEAD 로 길이를 먼저 물어본다."""
        u = urlparse(self.path)
        if u.path == "/api/video":
            run_id = _safe_name(parse_qs(u.query).get("run", [""])[0])
            path = (RUNS / run_id / "final.mp4") if run_id else None
            if path and path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                return
        self.send_error(404)

    def do_POST(self) -> None:
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "잘못된 요청입니다."}, 400)
            return

        if u.path == "/api/generate":
            self._generate(body)
            return
        if u.path == "/api/publish":
            self._publish(body)
            return
        if u.path == "/api/cancel":
            ok = jobs.cancel(body.get("id", ""))
            self._json({"ok": ok})
            return
        if u.path == "/api/save-meta":
            self._save_meta(body)
            return
        if u.path == "/api/upload":
            self._upload(body)
            return
        self.send_error(404)

    # -- 동작 ---------------------------------------------------------
    def _generate(self, body: dict) -> None:
        if jobs.active():
            self._json({"error": "이미 작업이 진행 중입니다. 끝난 뒤에 시작하세요."}, 409)
            return
        name = _safe_name(body.get("seed", ""))
        if not name or not (SEEDS / name).exists():
            self._json({"error": "이미지를 찾을 수 없습니다."}, 400)
            return

        mode = body.get("mode", "chain")
        if mode not in ("chain", "montage"):
            self._json({"error": "mode 가 잘못됐습니다."}, 400)
            return
        clips = max(1, min(int(body.get("clips", 6)), 20))
        duration = max(1, min(int(body.get("duration", 5)), 15))

        args = ["main.py", "generate", "--image", f"seeds/{name}",
                "--mode", mode, "--clips", str(clips),
                "--duration", str(duration), "--yes"]
        scenes = [s for s in (body.get("scenes") or []) if _safe_name(s)]
        for s in scenes:
            args += ["--scenes", f"seeds/{s}"]

        job = jobs.start("generate", body.get("title") or name, args, ROOT)
        self._json({"id": job.id})

    def _publish(self, body: dict) -> None:
        if jobs.active():
            self._json({"error": "이미 작업이 진행 중입니다."}, 409)
            return
        run_id = _safe_name(body.get("run", ""))
        if not run_id or not (RUNS / run_id / "final.mp4").exists():
            self._json({"error": "완성된 영상을 찾을 수 없습니다."}, 400)
            return
        targets = body.get("targets") or []
        if not targets:
            self._json({"error": "업로드할 곳을 선택하세요."}, 400)
            return

        args = ["main.py", "publish", "--run", run_id]
        if "youtube" in targets:
            args.append("--youtube")
        if "instagram" in targets:
            args.append("--instagram")
        if body.get("dry_run"):
            args.append("--dry-run")

        job = jobs.start("publish", f"{run_id} 업로드", args, ROOT)
        self._json({"id": job.id})

    def _upload(self, body: dict) -> None:
        """브라우저에서 올린 이미지를 seeds/ 에 넣고 제목까지 지어준다."""
        import base64
        import binascii

        from pipeline.copywriter import write as write_copy
        from pipeline.curate import analyze, classify, prompt_from_filename

        files = body.get("files") or []
        if not files:
            self._json({"error": "이미지가 없습니다."}, 400)
            return

        SEEDS.mkdir(parents=True, exist_ok=True)
        added, skipped = [], []
        for item in files[:60]:                      # 한 번에 60장까지
            raw_name = str(item.get("name", "image.png"))
            data_url = str(item.get("data", ""))
            if "," not in data_url:
                skipped.append((raw_name, "형식 오류"))
                continue
            try:
                blob = base64.b64decode(data_url.split(",", 1)[1], validate=True)
            except (binascii.Error, ValueError):
                skipped.append((raw_name, "읽을 수 없음"))
                continue
            if len(blob) > 25 * 1024 * 1024:
                skipped.append((raw_name, "25MB 초과"))
                continue

            ext = Path(raw_name).suffix.lower()
            if ext not in IMAGE_EXT:
                skipped.append((raw_name, "이미지가 아님"))
                continue

            # 파일명은 프롬프트 추출에 쓰이므로 임시로 원본을 살려 저장한다
            stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(raw_name).stem)[:70] or "seed"
            tmp = SEEDS / f"__tmp_{stem}{ext}"
            tmp.write_bytes(blob)

            shot = analyze(tmp)
            if shot is None:
                tmp.unlink(missing_ok=True)
                skipped.append((raw_name, "이미지를 열 수 없음"))
                continue
            if shot.disqualified:
                tmp.unlink(missing_ok=True)
                skipped.append((raw_name, shot.reasons[0] if shot.reasons else "규격 미달"))
                continue

            theme = classify(Path(raw_name))
            n = 1
            while (SEEDS / f"{theme}_{n:02d}{ext}").exists():
                n += 1
            dest = SEEDS / f"{theme}_{n:02d}{ext}"
            tmp.rename(dest)

            copy = write_copy(theme, prompt_from_filename(Path(raw_name)),
                              seed_key=dest.stem)
            dest.with_suffix(".yaml").write_text(
                "# 화면에서 올리며 자동 작성했습니다. 마음에 안 들면 고치세요.\n"
                f"title:  {copy.title}\n"
                f"hook:   {copy.hook}\n"
                f"\nprompt: {copy.prompt}\n"
                "\nscene_prompts: []\n", encoding="utf-8")
            added.append({"name": dest.name, "title": copy.title, "theme": theme})

        with _THUMB_LOCK:
            _THUMBS.clear()
        self._json({"added": added, "skipped": [
            {"name": n, "reason": r} for n, r in skipped]})

    def _save_meta(self, body: dict) -> None:
        name = _safe_name(body.get("seed", ""))
        if not name or not (SEEDS / name).exists():
            self._json({"error": "이미지를 찾을 수 없습니다."}, 400)
            return
        title = str(body.get("title", "")).strip()
        hook = str(body.get("hook", "")).strip()
        prompt = str(body.get("prompt", "")).strip()
        dest = (SEEDS / name).with_suffix(".yaml")
        dest.write_text(
            "# 웹 화면에서 저장했습니다.\n"
            f"title:  {title}\n"
            f"hook:   {hook}\n"
            f"prompt: {prompt}\n"
            "\nscene_prompts: []\n",
            encoding="utf-8")
        self._json({"ok": True})


def serve(port: int = 8765, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  AI DEOKHU 작업실이 열렸습니다\n  {url}\n")
    print("  창을 닫으려면 이 터미널에서 Ctrl+C 를 누르세요.\n")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  종료합니다.")
    finally:
        httpd.server_close()
