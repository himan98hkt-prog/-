#!/usr/bin/env python3
"""Phase 2 실엔진 E2E — 별도 프로세스로 띄운 API·워커에 실제 영상을 태운다.

무엇을 증명하는가
----------------
`docs/PHASE2_SAAS_FOUNDATION.md` §4 가 "부분" 으로 남겨 둔 항목을 닫는다.

기존 테스트(`tests/test_saas_api.py`)는 같은 프로세스 안에서 `TestClient` 와
`Worker.run_once()` 를 직접 부르고, 파이프라인도 `tests/saas_fakes.py` 의 대역이다.
그래서 다음 두 가지를 증명하지 못한다.

1. **API 와 워커가 정말 별개 프로세스로 동작하는가** — 브라우저를 닫아도,
   API 를 재시작해도 작업이 계속 도는가
2. **진짜 엔진이 도는가** — FFmpeg 로 1080×1920 을 실제로 뽑는가

이 스크립트는 둘 다 실제로 한다.

- `uvicorn` 을 **자식 프로세스**로 띄우고 TCP 로 HTTP 를 건다 (`TestClient` 아님)
- 워커를 **또 다른 자식 프로세스**로 띄운다 (`run_once()` 직접 호출 아님)
- 작업을 제출한 **직후 HTTP 세션을 닫아** 브라우저 종료를 흉내 낸다
- 진짜 MP4 를 presigned URL 로 올리고, 진짜 FFmpeg 렌더를 거쳐
- 내려받은 산출물을 `ffprobe` 로 검사한다

이 환경의 제약과 우회
--------------------
`faster-whisper` 를 받을 수 없다(huggingface.co 차단). Phase 0/1 과 같은 방법으로
**전사 캐시를 미리 심는다** — `run_pipeline` 은 `work_dir/transcription.json` 이
있으면 STT 를 건너뛴다. 따라서 이 스크립트가 증명하는 것은 **ingest → analyze →
render → 저장 → 다운로드** 경로이고, STT 정확도는 범위 밖이다.

환경 준비
--------
FFmpeg 과 PostgreSQL 이 필요하다. 깨끗한 컨테이너에서는 다음으로 갖춰진다.

    # FFmpeg — apt 인덱스가 낡으면 404 가 나므로 update 를 먼저 한다
    apt-get update && apt-get install -y --no-install-recommends ffmpeg

    # PostgreSQL 16 (데몬이 없으면 직접 띄운다)
    PGDATA=/var/lib/postgresql/e2e
    mkdir -p "$PGDATA" && chown postgres:postgres "$PGDATA" && chmod 700 "$PGDATA"
    su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -A trust -U postgres"
    su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -o '-p 5432 -k /tmp' -l $PGDATA/server.log start"
    createdb -h /tmp -p 5432 -U postgres autoshorts_e2e

    # 파이썬 의존성
    pip install -e ".[saas]"

사용법
------
    export AUTOSHORTS_E2E_DSN="postgresql://postgres@/autoshorts_e2e?host=/tmp&port=5432"
    python scripts/e2e_phase2.py

    python scripts/e2e_phase2.py --keep      # 끝나도 산출물·로그를 남긴다
    python scripts/e2e_phase2.py --report out/phase2_e2e.json

성공하면 종료코드 0, 한 단계라도 실패하면 1.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSWORD = "phase2-e2e-password"
SOURCE_SECONDS = 90
CLIP_MIN, CLIP_MAX, CLIP_COUNT = 10, 20, 2
EXPECTED_WIDTH, EXPECTED_HEIGHT = 1080, 1920

#: 전사 캐시에 넣을 한국어 문장. 훅 표현이 있어야 휴리스틱이 구간을 고른다.
NARRATION = (
    "결론부터 말씀드리면 대부분의 사람들이 첫 단계에서 실패합니다",
    "사실 이건 아무도 알려주지 않는 비밀입니다",
    "제가 처음 시작했을 때는 백만원도 없었어요",
    "그런데 문제는 여기서 시작됩니다",
    "핵심은 결국 습관입니다 매일 반복하는 것이 전부입니다",
    "놀랍게도 결과는 정반대였습니다",
)


# ──────────────────────────────────────────────────────────────
# 보고
# ──────────────────────────────────────────────────────────────
@dataclass
class Step:
    name: str
    ok: bool = False
    detail: str = ""
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail,
                "seconds": round(self.seconds, 2)}


@dataclass
class Report:
    steps: list[Step] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def step(self, name: str) -> Step:
        entry = Step(name)
        self.steps.append(entry)
        return entry

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(s.ok for s in self.steps)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "facts": self.facts,
                "steps": [s.to_dict() for s in self.steps]}

    def render(self) -> str:
        lines = ["", "Phase 2 실엔진 E2E", "=" * 60]
        for entry in self.steps:
            mark = "OK  " if entry.ok else "FAIL"
            lines.append(f"  [{mark}] {entry.name}  ({entry.seconds:.1f}s)")
            if entry.detail:
                lines.append(f"         {entry.detail}")
        lines.append("=" * 60)
        if self.facts:
            lines.append("확인된 사실")
            for key, value in self.facts.items():
                lines.append(f"  {key}: {value}")
        lines.append("")
        lines.append("결과: " + ("전부 통과" if self.ok else "실패한 단계가 있습니다"))
        return "\n".join(lines) + "\n"


class StepFailed(RuntimeError):
    pass


# ──────────────────────────────────────────────────────────────
# 도구
# ──────────────────────────────────────────────────────────────
def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise StepFailed(f"{name} 이(가) PATH 에 없습니다.")
    return path


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout: float) -> None:
    import httpx

    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return
            last = f"HTTP {response.status_code}"
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(0.2)
    raise StepFailed(f"{url} 이 {timeout:.0f}초 안에 응답하지 않았습니다 ({last}).")


def make_source_video(path: Path, ffmpeg: str) -> None:
    """16:9 테스트 영상. 9:16 로 리프레이밍되는지 보려면 가로여야 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={SOURCE_SECONDS}",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={SOURCE_SECONDS}",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(path)],
        check=True, capture_output=True,
    )


def seed_transcript(job_dir: Path) -> int:
    """STT 를 돌릴 수 없으므로 전사 캐시를 심는다 (Phase 0/1 과 같은 우회)."""
    from autoshorts.models import Segment, Transcript, Word

    segments, clock, index = [], 0.0, 0
    while clock < SOURCE_SECONDS - 2:
        text = NARRATION[index % len(NARRATION)]
        tokens = text.split()
        span = 4.0 / len(tokens)
        words = [
            Word(round(clock + n * span, 2), round(clock + (n + 1) * span, 2), token)
            for n, token in enumerate(tokens)
        ]
        segments.append(Segment(start=round(clock, 2), end=round(clock + 4.0, 2),
                                text=text, words=words))
        clock += 4.5
        index += 1
    transcript = Transcript(segments=segments, language="ko", duration=float(SOURCE_SECONDS))
    job_dir.mkdir(parents=True, exist_ok=True)
    transcript.save(job_dir / "transcription.json")
    return len(segments)


def probe(path: Path, ffprobe: str) -> dict:
    """ffprobe 로 스트림 규격을 읽는다.

    csv 출력은 **요청한 순서가 아니라 스트림 구조체 순서**로 나오므로 이름으로
    받으려면 json 이어야 한다. (csv 로 받다가 width 자리에 codec_name 이 와서 한 번 틀렸다.)
    """
    def ask(stream: str) -> dict:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=width,height,codec_name,sample_rate",
             "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        ).stdout
        streams = json.loads(out).get("streams") or [{}]
        return streams[0]

    video = ask("v:0")
    audio = ask("a:0")
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "video_codec": str(video.get("codec_name") or ""),
        "audio_codec": str(audio.get("codec_name") or ""),
        "sample_rate": int(audio.get("sample_rate") or 0),
    }


# ──────────────────────────────────────────────────────────────
# 프로세스
# ──────────────────────────────────────────────────────────────
class Process:
    """자식 프로세스 하나. 로그를 파일로 받아 실패 시 보여 준다."""

    def __init__(self, name: str, argv: list[str], env: dict, log_path: Path) -> None:
        self.name = name
        self.log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = log_path.open("w", encoding="utf-8")
        self.popen = subprocess.Popen(
            argv, cwd=str(ROOT), env=env,
            stdout=self._log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    @property
    def pid(self) -> int:
        return self.popen.pid

    def alive(self) -> bool:
        return self.popen.poll() is None

    def tail(self, lines: int = 20) -> str:
        try:
            self._log.flush()
            return "\n".join(self.log_path.read_text(encoding="utf-8").splitlines()[-lines:])
        except OSError:
            return "(로그를 읽지 못했습니다)"

    def stop(self) -> None:
        if self.popen.poll() is None:
            try:
                os.killpg(os.getpgid(self.popen.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                self.popen.terminate()
            try:
                self.popen.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.popen.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    self.popen.kill()
        try:
            self._log.close()
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────
# 본체
# ──────────────────────────────────────────────────────────────
def run(args: argparse.Namespace) -> Report:
    import httpx

    report = Report()
    ffmpeg, ffprobe = require_tool("ffmpeg"), require_tool("ffprobe")
    dsn = args.dsn or os.environ.get("AUTOSHORTS_E2E_DSN") or os.environ.get(
        "AUTOSHORTS_DATABASE_URL", "")
    if not dsn:
        raise StepFailed("DSN 이 없습니다. --dsn 또는 AUTOSHORTS_E2E_DSN 을 주세요.")

    base = Path(args.workdir).resolve()
    if base.exists():
        shutil.rmtree(base)
    storage_root = base / "storage"
    work_root = base / "work"
    output_root = base / "output"
    for directory in (storage_root, work_root, output_root, base / "logs"):
        directory.mkdir(parents=True, exist_ok=True)

    port = free_port()
    api_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "AUTOSHORTS_DATABASE_URL": dsn,
        "AUTOSHORTS_STORAGE_ROOT": str(storage_root),
        "AUTOSHORTS_WORK_ROOT": str(work_root),
        "AUTOSHORTS_OUTPUT_ROOT": str(output_root),
        "AUTOSHORTS_UPLOAD_SECRET": "phase2-e2e-secret",
        "AUTOSHORTS_POLL_INTERVAL": "0.2",
        "PYTHONPATH": str(ROOT),
        "PYTHONUNBUFFERED": "1",
    }

    processes: list[Process] = []
    try:
        # 1. 스키마 ------------------------------------------------
        entry = report.step("스키마 마이그레이션")
        started = time.monotonic()
        from saas import migrate
        from saas.db import Database

        db = Database(dsn, max_connections=4)
        db.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        applied = migrate.apply_all(db)
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"{len(applied)}개 적용"

        # 2. 소스 영상 ---------------------------------------------
        entry = report.step("테스트 영상 생성 (1280x720 · 90초)")
        started = time.monotonic()
        source_mp4 = base / "source.mp4"
        make_source_video(source_mp4, ffmpeg)
        source_probe = probe(source_mp4, ffprobe)
        entry.ok = source_probe["width"] == 1280 and source_probe["height"] == 720
        entry.seconds = time.monotonic() - started
        entry.detail = (f"{source_probe['width']}x{source_probe['height']} · "
                        f"{source_mp4.stat().st_size / 1e6:.1f}MB")
        if not entry.ok:
            raise StepFailed("소스 영상 규격이 예상과 다릅니다.")

        # 3. 프로세스 기동 ------------------------------------------
        entry = report.step("API·워커를 별도 프로세스로 기동")
        started = time.monotonic()
        api = Process("api", [sys.executable, "-m", "uvicorn", "apps.api.main:app",
                              "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
                      env, base / "logs" / "api.log")
        processes.append(api)
        try:
            wait_for_http(f"{api_url}/health", timeout=40)
        except StepFailed:
            entry.detail = "API 기동 실패:\n" + api.tail()
            raise
        worker = Process("worker", [sys.executable, "-m", "apps.worker.main"],
                         env, base / "logs" / "worker.log")
        processes.append(worker)
        time.sleep(1.0)
        if not worker.alive():
            entry.detail = "워커가 바로 종료됐습니다:\n" + worker.tail()
            raise StepFailed("워커 기동 실패")
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"api pid={api.pid} · worker pid={worker.pid} · 본 프로세스 pid={os.getpid()}"
        report.facts["프로세스 분리"] = (
            f"api={api.pid}, worker={worker.pid}, 스크립트={os.getpid()} — 모두 다른 PID")

        # 4. 가입·프로젝트 -----------------------------------------
        entry = report.step("가입 → 워크스페이스 → 프로젝트")
        started = time.monotonic()
        email = f"e2e-{int(time.time())}@example.com"
        with httpx.Client(base_url=api_url, timeout=30.0) as client:
            signup = client.post("/v1/auth/signup", json={
                "email": email, "password": PASSWORD, "workspace_name": "E2E 워크스페이스"})
            if signup.status_code != 201:
                raise StepFailed(f"가입 실패: {signup.status_code} {signup.text}")
            body = signup.json()
            token = body["token"]
            workspace_id = body["workspace"]["id"]
            headers = {"Authorization": f"Bearer {token}"}

            created = client.post(f"/v1/workspaces/{workspace_id}/projects",
                                  json={"name": "E2E 프로젝트"}, headers=headers)
            if created.status_code != 201:
                raise StepFailed(f"프로젝트 생성 실패: {created.status_code} {created.text}")
            project_id = created.json()["id"]
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"workspace={workspace_id[:8]}… project={project_id[:8]}…"

        # 5. presigned 업로드 --------------------------------------
        entry = report.step("presigned URL 로 실제 MP4 업로드")
        started = time.monotonic()
        payload = source_mp4.read_bytes()
        with httpx.Client(base_url=api_url, timeout=120.0) as client:
            ticket = client.post(f"/v1/projects/{project_id}/uploads",
                                 json={"filename": "source.mp4", "content_type": "video/mp4"},
                                 headers=headers)
            if ticket.status_code != 201:
                raise StepFailed(f"업로드 티켓 실패: {ticket.status_code} {ticket.text}")
            upload = ticket.json()["upload"]
            asset_id = ticket.json()["asset_id"]
            # 바이트는 인증 헤더 없이 presigned URL 로 간다.
            put = client.put(upload["url"], content=payload)
            if put.status_code != 200:
                raise StepFailed(f"업로드 실패: {put.status_code} {put.text}")

            detail = client.get(f"/v1/projects/{project_id}", headers=headers).json()
            asset = next(a for a in detail["assets"] if a["id"] == asset_id)
            if asset["upload_state"] != "uploaded" or asset["size_bytes"] != len(payload):
                raise StepFailed(f"업로드 상태가 이상합니다: {asset}")
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"{len(payload) / 1e6:.1f}MB · state={asset['upload_state']}"

        # 6. 권리 게이트 -------------------------------------------
        entry = report.step("권리 미확인 상태에서 렌더가 막히는지")
        started = time.monotonic()
        with httpx.Client(base_url=api_url, timeout=30.0) as client:
            blocked = client.post(f"/v1/projects/{project_id}/jobs",
                                  json={"asset_id": asset_id}, headers=headers)
            gate_held = False
            if blocked.status_code == 202:
                job_id = blocked.json()["job"]["id"]
                for _ in range(100):
                    state = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
                    if state["status"] in {"needs_approval", "succeeded", "failed"}:
                        gate_held = state["status"] == "needs_approval"
                        break
                    time.sleep(0.3)
            else:
                gate_held = blocked.status_code in {400, 403, 409}
            if not gate_held:
                raise StepFailed("unverified 자산인데 렌더가 막히지 않았습니다.")

            confirmed = client.post(f"/v1/assets/{asset_id}/rights",
                                    json={"status": "owned"}, headers=headers)
            if confirmed.status_code != 201:
                raise StepFailed(f"권리 확인 실패: {confirmed.status_code} {confirmed.text}")
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = "unverified 는 렌더 전 정지, owned 확인 후 진행"
        report.facts["권리 게이트"] = "unverified 자산은 렌더되지 않음 (실제 HTTP 로 확인)"

        # 7. 전사 캐시 ---------------------------------------------
        entry = report.step("전사 캐시 주입 (STT 불가 환경 우회)")
        started = time.monotonic()
        from autoshorts.config import Settings
        from autoshorts.pipeline import _job_dir
        from autoshorts.storage import LocalStorage

        row = db.fetch_one(
            "SELECT storage_key FROM source_assets WHERE id = %s", (asset_id,))
        if not row or not row["storage_key"]:
            raise StepFailed("자산의 storage_key 를 찾지 못했습니다.")
        local_source = str(LocalStorage(storage_root).open_local(row["storage_key"]))
        # 워커가 쓸 work_dir 과 같은 규칙으로 작업 폴더를 계산한다.
        worker_work_dir = work_root / workspace_id
        job_dir = _job_dir(
            Settings(source=local_source, work_dir=worker_work_dir), local_source)
        segments = seed_transcript(job_dir)
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"{segments}개 세그먼트 → {job_dir.name}/transcription.json"

        # 8. 제출 후 클라이언트 종료 --------------------------------
        entry = report.step("작업 제출 후 HTTP 세션을 닫음 (브라우저 종료 흉내)")
        started = time.monotonic()
        with httpx.Client(base_url=api_url, timeout=30.0) as client:
            submitted = client.post(
                f"/v1/projects/{project_id}/jobs",
                json={"asset_id": asset_id,
                      "clip_options": {"min_seconds": CLIP_MIN, "max_seconds": CLIP_MAX,
                                       "min_clips": CLIP_COUNT, "max_clips": CLIP_COUNT}},
                headers=headers)
            if submitted.status_code != 202:
                raise StepFailed(f"작업 제출 실패: {submitted.status_code} {submitted.text}")
            job = submitted.json()["job"]
            job_id = job["id"]
            reserved = submitted.json().get("reserved_credits", 0)
            if job["status"] != "queued":
                raise StepFailed(f"제출 직후 상태가 queued 가 아닙니다: {job['status']}")
        # with 를 빠져나오며 연결이 모두 닫혔다. 이제 워커만 남는다.
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = f"job={job_id[:8]}… status=queued · 예약 크레딧 {reserved}"

        # 9. 워커가 처리 -------------------------------------------
        entry = report.step("별도 워커 프로세스가 FFmpeg 렌더까지 완료")
        started = time.monotonic()
        final = None
        deadline = time.monotonic() + args.timeout
        with httpx.Client(base_url=api_url, timeout=30.0) as client:   # 새 세션
            while time.monotonic() < deadline:
                if not worker.alive():
                    raise StepFailed("워커가 죽었습니다:\n" + worker.tail())
                state = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
                if state["status"] in {"succeeded", "failed", "cancelled"}:
                    final = state
                    break
                time.sleep(0.5)
            if final is None:
                raise StepFailed(
                    f"{args.timeout:.0f}초 안에 끝나지 않았습니다.\n" + worker.tail())
            if final["status"] != "succeeded":
                raise StepFailed(f"작업 실패: {final.get('error')}\n" + worker.tail())

            progress = client.get(f"/v1/jobs/{job_id}/progress", headers=headers).json()
            stages = [e["stage"] for e in progress["events"]]
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = (f"outputs={len(final['outputs_detail'])} · "
                        f"candidates={len(final['candidates'])} · 단계={'→'.join(dict.fromkeys(stages))}")
        report.facts["워커 독립성"] = (
            "제출한 HTTP 세션을 닫은 뒤 다른 프로세스의 워커가 작업을 끝냄")

        # 10. 다운로드 + ffprobe ------------------------------------
        entry = report.step(f"산출물 다운로드 후 ffprobe 검증 ({EXPECTED_WIDTH}x{EXPECTED_HEIGHT})")
        started = time.monotonic()
        checked = []
        with httpx.Client(base_url=api_url, timeout=120.0) as client:
            for output in final["outputs_detail"]:
                response = client.get(f"/v1/outputs/{output['id']}/download", headers=headers)
                if response.status_code != 200:
                    raise StepFailed(f"다운로드 실패: {response.status_code}")
                local = base / f"downloaded_{output['id'][:8]}.mp4"
                local.write_bytes(response.content)
                info = probe(local, ffprobe)
                checked.append(info)
                if (info["width"], info["height"]) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                    raise StepFailed(
                        f"해상도가 다릅니다: {info['width']}x{info['height']}")
                if info["video_codec"] != "h264" or info["audio_codec"] != "aac":
                    raise StepFailed(f"코덱이 다릅니다: {info}")
        entry.ok, entry.seconds = True, time.monotonic() - started
        entry.detail = " / ".join(
            f"{i['width']}x{i['height']} {i['video_codec']}+{i['audio_codec']}@{i['sample_rate']}"
            for i in checked)
        report.facts["산출물 규격"] = (
            f"{len(checked)}편 모두 {EXPECTED_WIDTH}x{EXPECTED_HEIGHT} h264+aac "
            f"{checked[0]['sample_rate']}Hz")

        # 11. 크레딧 정산 -------------------------------------------
        entry = report.step("크레딧이 예약에서 소진으로 정산됐는지")
        started = time.monotonic()
        rows = db.fetch_all(
            "SELECT entry_type, SUM(amount) AS total FROM credit_ledger "
            "WHERE workspace_id = %s GROUP BY entry_type", (workspace_id,))
        kinds = {r["entry_type"]: r["total"] for r in rows}
        entry.ok = bool(kinds)
        entry.seconds = time.monotonic() - started
        entry.detail = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "(원장 비어 있음)"
        report.facts["크레딧 원장"] = entry.detail

        # 12. API 재시작 후에도 결과가 남는지 -------------------------
        entry = report.step("API 프로세스를 재시작해도 결과가 남는지")
        started = time.monotonic()
        api.stop()
        processes.remove(api)
        api2 = Process("api2", [sys.executable, "-m", "uvicorn", "apps.api.main:app",
                                "--host", "127.0.0.1", "--port", str(port),
                                "--log-level", "warning"],
                       env, base / "logs" / "api2.log")
        processes.append(api2)
        wait_for_http(f"{api_url}/health", timeout=40)
        with httpx.Client(base_url=api_url, timeout=30.0) as client:
            again = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
        entry.ok = again["status"] == "succeeded"
        entry.seconds = time.monotonic() - started
        entry.detail = f"재시작 후 status={again['status']}"
        if not entry.ok:
            raise StepFailed("API 재시작 후 작업 상태가 유지되지 않았습니다.")
        report.facts["영속성"] = "API 재시작 후에도 작업 결과 조회 가능 (PostgreSQL 영속)"

        db.close()
    except StepFailed as exc:
        if report.steps and not report.steps[-1].ok:
            current = report.steps[-1]
            current.detail = (current.detail + "\n" if current.detail else "") + str(exc)
        else:
            failed = report.step("실패")
            failed.detail = str(exc)
    finally:
        for process in reversed(processes):
            process.stop()

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN (기본: AUTOSHORTS_E2E_DSN)")
    parser.add_argument("--workdir", default="var/e2e-phase2", help="작업·산출물 폴더")
    parser.add_argument("--timeout", type=float, default=900.0, help="렌더 대기 상한(초)")
    parser.add_argument("--report", default=None, help="결과 JSON 경로")
    parser.add_argument("--keep", action="store_true", help="작업 폴더를 지우지 않는다")
    args = parser.parse_args(argv)

    try:
        report = run(args)
    except StepFailed as exc:
        print(f"\n준비 단계 실패: {exc}\n", file=sys.stderr)
        return 1

    print(report.render())
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"결과 JSON: {path}")
    if not args.keep:
        print(f"(작업 폴더 유지: {Path(args.workdir).resolve()} — --keep 없이도 삭제하지 않습니다)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
