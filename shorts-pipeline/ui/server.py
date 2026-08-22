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


def _code_stamp() -> float:
    """프로그램 코드 파일 중 가장 최근에 바뀐 시각.

    업데이트를 받으면 파일은 새것이 되지만 이미 켜져 있는 서버는 계속
    예전 코드로 돈다 (파이썬은 모듈을 다시 읽지 않는다). 화면만 새 파일에서
    읽어오니, 새 버튼이 보이는데 누르면 '알 수 없는 대상' 이 뜬다.
    부팅 때 찍어둔 값과 지금 값을 비교해 그 상태를 알아챈다.
    """
    newest = 0.0
    for folder in (ROOT / "ui", ROOT / "pipeline", ROOT / "publish"):
        if folder.is_dir():
            for f in folder.glob("*.py"):
                newest = max(newest, f.stat().st_mtime)
    main = ROOT / "main.py"
    if main.exists():
        newest = max(newest, main.stat().st_mtime)
    return newest


# 서버가 켜진 시점의 코드 상태. 이후 파일이 바뀌면 재시작이 필요하다.
_BOOT_STAMP = _code_stamp()


def needs_restart() -> bool:
    try:
        return _code_stamp() > _BOOT_STAMP + 1     # 1초는 저장 오차 여유
    except OSError:
        return False
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


def overview() -> dict:
    """대시보드 상단 요약. 한눈에 상태를 본다."""
    from pipeline.content import find_sidecar

    seeds = list_seeds()
    with_meta = sum(1 for s in seeds if s["has_meta"])
    runs = list_runs(limit=400)
    ready = [r for r in runs if r["ready"]]
    spent = sum(r["cost"] or 0 for r in runs)

    published = 0
    log = RUNS / "schedule.log"
    if log.exists():
        try:
            published = sum(1 for ln in log.read_text(encoding="utf-8").splitlines()
                            if "\tOK\t" in ln or ln.count("OK") and "성공=" in ln)
        except OSError:
            pass

    from pipeline import music as music_mod

    music_dir = ROOT / "music"
    return {
        "seeds": len(seeds),
        "seeds_with_meta": with_meta,
        "days_left": len(seeds),          # 하루 1편 기준
        "videos": len(ready),
        "published": published,
        "spent": round(spent, 2),
        "music": music_mod.total_tracks(music_dir),
        "music_note": music_mod.describe(music_dir),
    }


def schedule_state() -> dict:
    from pipeline import win_schedule as ws

    st = ws.status()
    return {
        "supported": ws.supported(),
        "enabled": st.enabled,
        "start_time": st.start_time,
        "publish_time": st.publish_time,
        "next_run": st.next_run,
        "targets": st.targets,
        "lead_minutes": ws.LEAD_MINUTES,
        "note": st.raw,
    }


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


SECRETS = ROOT / "secrets"


def _seed_pool() -> list[Path]:
    """아직 안 쓴 시드. 다 쓴 것은 스케줄러가 seeds/_used/ 로 옮기므로 여기 안 잡힌다."""
    if not SEEDS.is_dir():
        return []
    return [p for p in sorted(SEEDS.iterdir())
            if p.is_file() and p.suffix.lower() in IMAGE_EXT]


def music_state() -> dict:
    """music/ 안을 분위기별로 보여준다. 넣은 곡이 실제로 잡히는지 확인용."""
    from pipeline import music as m

    md = ROOT / "music"
    shelf = m.catalog(md)
    moods = []
    for key in (*m.MOODS, "any"):
        found = shelf.get(key, [])
        moods.append({
            "key": key,
            "label": m.MOOD_LABEL.get(key, key),
            "count": len(found),
            "tracks": [f.name for f in found[:8]],
            "more": max(0, len(found) - 8),
            "themes": sorted(t for t, mood in m.MOOD_OF.items() if mood == key),
        })
    return {"dir": str(md), "total": sum(x["count"] for x in moods),
            "moods": moods, "note": m.describe(md)}


def clip_count(raw, mode: str, scene_count: int) -> int:
    """만들 클립 수를 정한다.

    화면의 select 가 비어 있으면 Number("") 가 0 으로 넘어온다. 예전에는
    그걸 max(1, ...) 로 1 까지 깎아서, **장면 5장을 골랐는데 5초짜리 한
    클립만** 나왔다. 조용히 1 로 만드는 대신 기본값으로 되돌린다.

    장면 전환은 고른 장 수가 곧 클립 수다. 화면 값을 믿으면 장면이 버려지거나
    같은 그림이 반복된다.
    """
    if mode == "montage" and scene_count > 0:
        return max(1, min(scene_count, 20))
    return max(1, min(_positive(raw, 6), 20))


def _positive(value, fallback: int) -> int:
    """숫자로 못 읽히면 fallback. 빈 문자열·None·문자를 전부 받아낸다."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return n if n > 0 else fallback


def _group_reasons(items) -> list[dict]:
    """건너뛴 이유를 묶어 센다. 300장을 건너뛰면 목록이 아니라 숫자가 필요하다."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return [{"reason": r, "count": n}
            for r, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def connection_state() -> dict:
    """[설정] 탭 위쪽 요약. 지금 무엇이 연결됐는지 한 줄로 본다."""
    from pipeline import envfile

    env = envfile.read_raw()

    def val(key: str) -> str:
        return (os.getenv(key) or env.get(key, "")).strip()

    secret_file = ROOT / (val("YOUTUBE_CLIENT_SECRET_FILE")
                          or "secrets/client_secret.json")
    token_file = ROOT / (val("YOUTUBE_TOKEN_FILE")
                         or "secrets/youtube_token.json")

    channel = ""
    if token_file.exists():
        try:
            tok = json.loads(token_file.read_text(encoding="utf-8"))
            channel = tok.get("_channel_title", "")
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "video": {
            "ready": bool(val("FAL_API_KEY") or val("HIGGSFIELD_API_KEY")),
            "label": "영상 만들기",
        },
        "youtube": {
            "ready": token_file.exists(),
            "has_secret": secret_file.exists(),
            "secret_path": str(secret_file.relative_to(ROOT))
                            if secret_file.is_relative_to(ROOT) else str(secret_file),
            "channel": channel,
            "label": "유튜브",
        },
        "instagram": {
            "ready": bool(val("IG_USER_ID") and val("IG_ACCESS_TOKEN")),
            "label": "인스타그램",
        },
        "storage": {
            "ready": bool(val("S3_BUCKET") and val("AWS_ACCESS_KEY_ID")
                          and val("AWS_SECRET_ACCESS_KEY")),
            "label": "영상 보관함",
        },
    }


def simple_state() -> dict:
    """간편 모드 화면에 필요한 것만 추린다."""
    from pipeline.config import load_config

    conn = connection_state()
    pool = _seed_pool()
    runs = list_runs(limit=400)
    ready = [r for r in runs if r["ready"]]

    try:
        cfg = load_config(ROOT / "config.yaml")
        clips, duration = cfg.num_clips, cfg.clip_duration
        mode = cfg.mode
    except Exception:                                # noqa: BLE001 - 화면은 계속 떠야 한다
        clips, duration, mode = 6, 5, "chain"

    est = estimate(mode, clips, duration)

    # 다음에 뭘 하면 되는지 딱 하나만 알려준다
    if not conn["video"]["ready"]:
        step = {"id": "key", "text": "fal.ai 키를 먼저 넣어야 영상을 만들 수 있어요.",
                "action": "설정 열기", "go": "settings"}
    elif not pool:
        step = {"id": "seed", "text": "쓸 이미지가 없어요. 미드저니 이미지를 올려주세요.",
                "action": "이미지 올리기", "go": "images"}
    elif not ready:
        step = {"id": "make", "text": "준비 끝. 오늘 영상을 만들어 보세요.",
                "action": "오늘 영상 만들기", "go": "make"}
    elif not (conn["youtube"]["ready"] or conn["instagram"]["ready"]):
        step = {"id": "connect", "text": "영상은 있어요. 이제 유튜브·인스타를 연결하면 자동 업로드까지 됩니다.",
                "action": "계정 연결하기", "go": "settings"}
    else:
        step = {"id": "go", "text": "전부 준비됐어요. 매일 자동 업로드를 켜두면 끝입니다.",
                "action": "오늘 영상 만들기", "go": "make"}

    return {
        "connections": conn,
        "seeds_left": len(pool),
        "videos_ready": len(ready),
        "latest": ready[0] if ready else None,
        "plan": {"mode": mode, "clips": clips, "duration": duration,
                 "seconds": est.get("seconds"), "cost": est.get("expected")},
        "next_step": step,
        "schedule": schedule_state(),
    }


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

        # 브라우저 탭 아이콘과 [앱으로 설치]. 없으면 조용히 404.
        if p in ("/favicon.ico", "/icon-192.png", "/icon-512.png"):
            name = {"/favicon.ico": "app-32.png",
                    "/icon-192.png": "app-192.png",
                    "/icon-512.png": "app-512.png"}[p]
            f = ROOT / "brand" / "icons" / name
            if f.exists():
                self._bytes(f.read_bytes(), "image/png")
            else:
                self.send_error(404)
            return

        if p == "/manifest.webmanifest":
            # 엣지·크롬이 이걸 보고 [앱으로 설치] 를 띄운다.
            # 설치하면 주소창 없는 창으로 뜨고 작업 표시줄에 아이콘이 박힌다.
            manifest = {
                "name": "AI DEOKHU 작업실",
                "short_name": "AI DEOKHU",
                "start_url": "/",
                "scope": "/",
                "display": "standalone",
                "background_color": "#070B1A",
                "theme_color": "#070B1A",
                "lang": "ko",
                "icons": [
                    {"src": "/icon-192.png", "sizes": "192x192",
                     "type": "image/png", "purpose": "any"},
                    {"src": "/icon-512.png", "sizes": "512x512",
                     "type": "image/png", "purpose": "any"},
                ],
            }
            # 크롬은 manifest 의 Content-Type 을 본다. application/json 이면
            # 설치 제안이 안 뜨는 경우가 있다.
            self._bytes(json.dumps(manifest, ensure_ascii=False).encode(),
                        "application/manifest+json; charset=utf-8", cache=False)
            return

        if p == "/api/state":
            self._json({
                "seeds": list_seeds(),
                "runs": list_runs(),
                "jobs": jobs.recent(),
                "active": (jobs.active().snapshot() if jobs.active() else None),
                "needs_restart": needs_restart(),
            })
            return

        if p == "/api/doctor":
            self._json(doctor_state())
            return

        if p == "/api/overview":
            self._json(overview())
            return

        if p == "/api/schedule":
            self._json(schedule_state())
            return

        if p == "/api/music":
            self._json(music_state())
            return
        if p == "/api/simple":
            self._json(simple_state())
            return

        if p == "/api/settings":
            from pipeline import envfile

            data = envfile.snapshot()
            data["connections"] = connection_state()
            self._json(data)
            return

        if p == "/api/history":
            log = RUNS / "schedule.log"
            lines = []
            if log.exists():
                try:
                    lines = log.read_text(encoding="utf-8").splitlines()[-40:]
                except OSError:
                    pass
            self._json({"lines": list(reversed(lines))})
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

    def _same_origin(self) -> bool:
        """다른 웹사이트가 몰래 이 서버를 부르지 못하게 막는다.

        이 화면은 내 컴퓨터에서만 열리지만, 브라우저는 아무 사이트에서나
        127.0.0.1 로 POST 를 보낼 수 있다. 그대로 두면 방문한 광고 페이지가
        내 fal 키를 바꾸거나 돈 드는 생성을 시작시킬 수 있다.

        - JSON content-type 을 요구하면 브라우저가 사전 요청(preflight)을 보내는데,
          여기서는 그걸 받아주지 않으므로 크로스 오리진 요청 자체가 막힌다.
        - Origin 헤더가 붙어 오면 내 주소인지 한 번 더 본다.
        """
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return False
        origin = self.headers.get("Origin")
        if origin:
            host = self.headers.get("Host", "")
            allowed = {f"http://{host}", f"https://{host}"}
            if origin not in allowed:
                return False
        return True

    def do_POST(self) -> None:
        if not self._same_origin():
            self._json({"error": "허용되지 않은 요청입니다."}, 403)
            return
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
        if u.path == "/api/intake":
            self._intake(body)
            return
        if u.path == "/api/reclassify":
            self._reclassify(body)
            return
        if u.path == "/api/schedule":
            self._schedule(body)
            return
        if u.path == "/api/settings":
            self._save_settings(body)
            return
        if u.path == "/api/client-secret":
            self._client_secret(body)
            return
        if u.path == "/api/connect":
            self._connect(body)
            return
        if u.path == "/api/auto":
            self._auto(body)
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
        scenes = [s for s in (body.get("scenes") or []) if _safe_name(s)]

        clips = clip_count(body.get("clips"), mode, len(scenes))
        duration = max(1, min(_positive(body.get("duration"), 5), 15))

        args = ["main.py", "generate", "--image", f"seeds/{name}",
                "--mode", mode, "--clips", str(clips),
                "--duration", str(duration), "--yes"]
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

    def _schedule(self, body: dict) -> None:
        """매일 자동 업로드 예약을 켜고 끈다."""
        from pipeline import win_schedule as ws

        if not ws.supported():
            self._json({"error": "윈도우에서만 예약을 설정할 수 있습니다."}, 400)
            return
        if body.get("enabled"):
            targets = [t for t in (body.get("targets") or [])
                       if t in ("youtube", "instagram")]
            if not targets:
                self._json({"error": "업로드할 곳을 하나 이상 고르세요."}, 400)
                return
            mode = body.get("mode", "chain")
            ok, msg = ws.enable(str(body.get("time", "21:00")), targets,
                                mode if mode in ("chain", "montage") else "chain")
        else:
            ok, msg = ws.disable()
        self._json({"ok": ok, "message": msg}, 200 if ok else 400)

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

    def _intake(self, body: dict) -> None:
        """폴더 하나를 통째로 훑어 새 이미지만 seeds/ 에 들여온다.

        브라우저는 폴더를 통째로 넘길 수 없다. 그래서 경로를 문자열로 받아
        서버가 직접 읽는다. 서버는 이 컴퓨터에서만 돌고, 요청은 같은 출처만
        받으므로 임의 경로 읽기 위험은 파일 선택창과 같은 수준이다.
        """
        from pipeline.intake import import_folder

        raw = str(body.get("folder", "")).strip().strip('"')
        if not raw:
            self._json({"error": "폴더 경로를 넣어 주세요."}, 400)
            return
        try:
            report = import_folder(Path(raw), SEEDS,
                                   min_score=float(body.get("min_score") or 0))
        except NotADirectoryError as exc:
            self._json({"error": str(exc)}, 400)
            return
        except OSError as exc:
            self._json({"error": f"폴더를 읽지 못했습니다: {exc}"}, 400)
            return

        with _THUMB_LOCK:
            _THUMBS.clear()
        self._json({
            "scanned": report.scanned,
            "added": [{"name": i.name, "title": i.title, "theme": i.theme,
                       "score": i.score} for i in report.added],
            "skipped": _group_reasons(report.skipped),
        })

    def _reclassify(self, body: dict) -> None:
        """seeds/ 전체를 지금 기준으로 다시 분류한다."""
        from pipeline.intake import reclassify

        try:
            report = reclassify(SEEDS, rewrite_copy=bool(body.get("rewrite_copy")))
        except NotADirectoryError as exc:
            self._json({"error": str(exc)}, 400)
            return

        with _THUMB_LOCK:
            _THUMBS.clear()
        self._json({
            "scanned": report.scanned,
            "renamed": [{"was": a, "now": b} for a, b in report.renamed],
            "fixed": report.fixed,
            "skipped": _group_reasons(report.skipped),
        })

    def _save_settings(self, body: dict) -> None:
        """[설정] 탭에서 넣은 값을 .env 에 쓴다."""
        from pipeline import envfile

        values = body.get("values")
        if not isinstance(values, dict):
            self._json({"error": "보낼 값이 없습니다."}, 400)
            return

        # 마스킹된 값이 그대로 돌아오면 '안 고침' 이다. 진짜 키를 별표로 덮어쓰면 안 된다.
        clean = {}
        for key, raw in values.items():
            field = envfile.BY_KEY.get(key)
            if field is None:
                continue
            v = str(raw).strip()
            if field.kind == envfile.SECRET and set(v) <= {"*"} and v:
                continue
            if field.kind == envfile.SECRET and "*" * 6 in v:
                continue
            clean[key] = v

        try:
            changed = envfile.write(clean)
        except OSError as exc:
            self._json({"error": f".env 를 저장하지 못했습니다: {exc}"}, 500)
            return
        self._json({"ok": True, "changed": changed,
                    "connections": connection_state()})

    def _client_secret(self, body: dict) -> None:
        """client_secret.json 을 브라우저에서 받아 secrets/ 에 둔다."""
        import base64
        import binascii

        from pipeline import envfile

        data_url = str(body.get("data", ""))
        if "," not in data_url:
            self._json({"error": "파일을 읽지 못했습니다."}, 400)
            return
        try:
            blob = base64.b64decode(data_url.split(",", 1)[1], validate=True)
        except (binascii.Error, ValueError):
            self._json({"error": "파일을 읽지 못했습니다."}, 400)
            return
        if len(blob) > 128 * 1024:
            self._json({"error": "JSON 파일이 아닌 것 같습니다 (너무 큽니다)."}, 400)
            return

        try:
            parsed = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "JSON 파일이 아닙니다. 구글에서 받은 "
                                 "client_secret_....json 을 그대로 올려주세요."}, 400)
            return
        block = parsed.get("installed") or parsed.get("web")
        if not isinstance(block, dict) or "client_id" not in block:
            self._json({"error": "OAuth 클라이언트 파일이 아닙니다. 구글 클라우드 콘솔의 "
                                 "[사용자 인증 정보]에서 받은 JSON 인지 확인하세요."}, 400)
            return
        if parsed.get("web"):
            self._json({"error": "'웹 애플리케이션' 용으로 만드셨습니다. "
                                 "'데스크톱 앱' 으로 다시 만들어 주세요."}, 400)
            return

        SECRETS.mkdir(parents=True, exist_ok=True)
        dest = SECRETS / "client_secret.json"
        dest.write_bytes(blob)
        envfile.write({"YOUTUBE_CLIENT_SECRET_FILE": "secrets/client_secret.json"})
        self._json({"ok": True, "path": "secrets/client_secret.json",
                    "connections": connection_state()})

    def _connect(self, body: dict) -> None:
        """유튜브/인스타 연결을 확인한다. 유튜브는 브라우저 로그인 창이 뜬다."""
        target = body.get("target")
        if target not in ("youtube", "instagram", "storage"):
            hint = ("  최신 코드를 받은 뒤 작업실을 다시 켜지 않으면 이렇게 됩니다.\n"
                    "  검은 창을 닫고 [AI DEOKHU 작업실] 을 다시 실행하세요."
                    if needs_restart() else "")
            self._json({"error": f"알 수 없는 대상입니다.\n{hint}".rstrip()}, 400)
            return
        if jobs.active():
            self._json({"error": "이미 작업이 진행 중입니다. 끝난 뒤에 시도하세요."}, 409)
            return
        label = {"youtube": "유튜브 연결", "instagram": "인스타 연결",
                 "storage": "보관함 확인"}[target]
        job = jobs.start("connect", label,
                         ["main.py", f"connect-{target}"], ROOT)
        self._json({"id": job.id})

    def _auto(self, body: dict) -> None:
        """간편 모드. 이미지를 알아서 고르고 오늘 영상을 만든다."""
        from publish.scheduler import pick_seed

        if jobs.active():
            self._json({"error": "이미 작업이 진행 중입니다."}, 409)
            return

        name = _safe_name(body.get("seed", "")) if body.get("seed") else None
        # pick_seed 는 seeds/_used 를 만들려 하므로 폴더가 없으면 먼저 막는다
        seed = (SEEDS / name) if name else (
            pick_seed(SEEDS, shuffle=False) if SEEDS.is_dir() else None)
        if seed is None or not seed.exists():
            self._json({"error": "쓸 수 있는 이미지가 없습니다. "
                                 "[이미지] 탭에서 먼저 올려주세요."}, 400)
            return

        from pipeline.config import load_config
        try:
            cfg = load_config(ROOT / "config.yaml")
            mode, clips, duration = cfg.mode, cfg.num_clips, cfg.clip_duration
        except Exception:                            # noqa: BLE001
            mode, clips, duration = "chain", 6, 5
        # 간편 모드는 항상 끊김 없는 chain 이다. montage 는 같은 그림으로 되돌아간다.
        mode = "chain"

        from pipeline.content import load_content
        title = load_content(seed).title or seed.stem

        args = ["main.py", "generate", "--image", f"seeds/{seed.name}",
                "--mode", mode, "--clips", str(clips),
                "--duration", str(duration), "--yes"]
        job = jobs.start("generate", title, args, ROOT)
        self._json({"id": job.id, "seed": seed.name, "title": title})

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
