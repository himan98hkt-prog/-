"""Separate API/worker smoke with real FFmpeg and explicitly cached transcript.

Use a disposable PostgreSQL database. No paid AI calls or publication occur.
Run from autoshorts-engine: python -m scripts.smoke_saas_processes
"""

from __future__ import annotations

import json
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from autoshorts.config import Settings
from autoshorts.models import Segment, Transcript, Word
from autoshorts.pipeline import _job_dir
from saas.db import Database
from saas.migrate import apply_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-transcription", action="store_true")
    args = parser.parse_args()
    dsn = os.environ.get("AUTOSHORTS_TEST_DATABASE_URL")
    if not dsn:
        raise RuntimeError("A disposable AUTOSHORTS_TEST_DATABASE_URL is required")
    evidence = Path("speech-smoke-evidence" if args.real_transcription else "process-smoke-evidence").resolve()
    evidence.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="autoshorts-smoke-") as tmp:
        root = Path(tmp)
        env = dict(os.environ)
        env.update(AUTOSHORTS_DATABASE_URL=dsn,
                   AUTOSHORTS_UPLOAD_SECRET=secrets.token_hex(32),
                   AUTOSHORTS_STORAGE_ROOT=str(root / "storage"),
                   AUTOSHORTS_WORK_ROOT=str(root / "work"),
                   AUTOSHORTS_OUTPUT_ROOT=str(root / "output"),
                   GEMINI_API_KEY="", GOOGLE_API_KEY="")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        db = Database(dsn)
        apply_all(db)
        api_log = (evidence / "api.log").open("w")
        worker_log = (evidence / "worker.log").open("w")
        api = None
        worker = None

        def start_api():
            return subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1",
                 "--port", str(port)], env=env, stdout=api_log, stderr=subprocess.STDOUT)

        def call(method, path, data=None, token="", raw=False):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            if isinstance(data, dict):
                data = json.dumps(data).encode()
                headers["Content-Type"] = "application/json"
            req = Request(base + path, data=data, method=method, headers=headers)
            with urlopen(req, timeout=30) as response:
                content = response.read()
                return content if raw else json.loads(content)

        def ready():
            for _ in range(100):
                try:
                    call("GET", "/health")
                    return
                except (URLError, OSError):
                    if api.poll() is not None:
                        raise RuntimeError("API process exited; inspect api.log")
                    time.sleep(0.2)
            raise RuntimeError("API startup timed out")

        try:
            api = start_api()
            ready()
            suffix = secrets.token_hex(6)
            account = call("POST", "/v1/auth/signup", {
                "email": f"smoke-{suffix}@example.com", "password": secrets.token_urlsafe(24),
                "workspace_name": "Rendering smoke"})
            token, workspace = account["token"], account["workspace"]["id"]
            project = call("POST", f"/v1/workspaces/{workspace}/projects",
                           {"name": "Real FFmpeg / cached transcription"}, token)["id"]
            source = root / "source.mp4"
            audio_input = ["-f", "lavfi", "-i", "sine=frequency=440:duration=40"]
            if args.real_transcription:
                speech = root / "speech.wav"
                subprocess.run(["espeak-ng", "-v", "en-us", "-s", "145", "-w", str(speech),
                    "Today we will learn how to create a short video. First choose a clear topic. "
                    "Then record your voice in a quiet room. The most important step is to check "
                    "the sound before you start editing. Good sound helps people understand your story. "
                    "Next add captions so people can follow the story without sound. "
                    "Finally watch the complete video and check every caption before sharing it."],
                    check=True, timeout=30)
                audio_input = ["-stream_loop", "-1", "-i", str(speech)]
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "color=c=navy:s=640x360:r=24:d=40",
                            *audio_input,
                            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", str(source)], check=True, timeout=90)
            ticket = call("POST", f"/v1/projects/{project}/uploads",
                          {"filename": "source.mp4", "content_type": "video/mp4"}, token)
            call("PUT", ticket["upload"]["url"], source.read_bytes())
            asset = ticket["asset_id"]
            call("POST", f"/v1/assets/{asset}/rights", {"status": "owned"}, token)
            row = db.fetch_one("SELECT storage_key FROM source_assets WHERE id = %s", (asset,))
            local_source = str(root / "storage" / row["storage_key"])
            settings = Settings(source=local_source, work_dir=root / "work" / workspace)
            cache = _job_dir(settings, local_source) / "transcription.json"
            # Synthetic tone has no speech. This fixture verifies cached-STT plumbing,
            # offline selection and real rendering, NOT speech recognition accuracy.
            segments = []
            for i in range(8):
                text = "중요한 원칙은 결과를 직접 확인하는 것입니다"
                words = [Word(i * 5 + j * .6, i * 5 + (j + 1) * .6, w)
                         for j, w in enumerate(text.split())]
                segments.append(Segment(i * 5, i * 5 + 4.8, text, words))
            if not args.real_transcription:
                Transcript(segments=segments, language="ko", duration=40).save(cache)
            submitted = call("POST", f"/v1/projects/{project}/jobs", {
                "asset_id": asset, "language": "en" if args.real_transcription else "ko",
                "clip_options": {"min_seconds": 30, "max_seconds": 35,
                                 "min_clips": 1, "max_clips": 1},
                "render_options": {"width": 1080, "height": 1920, "fps": 24,
                                   "preset": "ultrafast", "burn_subtitles": True}}, token)
            job_id = submitted["job"]["id"]
            # The request has closed; stop the API entirely before starting worker.
            api.terminate()
            api.wait(timeout=15)
            worker = subprocess.Popen([sys.executable, "-m", "apps.worker.main", "--once"],
                                      env=env, stdout=worker_log, stderr=subprocess.STDOUT)
            assert worker.wait(timeout=600) == 0, "worker exited unsuccessfully"
            api = start_api()
            ready()
            job = call("GET", f"/v1/jobs/{job_id}", token=token)
            assert job["status"] == "succeeded", job
            if args.real_transcription:
                recognized = Transcript.load(cache)
                assert len(recognized.text.split()) >= 20, "Real STT did not recognize enough speech"
                assert "video" in recognized.text.lower(), "Speech did not match the input topic"
            outputs = job["outputs_detail"]
            assert outputs, "No persisted output"
            output = evidence / "sample-short.mp4"
            output.write_bytes(call("GET", f"/v1/outputs/{outputs[0]['id']}/download",
                                    token=token, raw=True))
            probe = json.loads(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)]))
            video = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert (video["width"], video["height"]) == (1080, 1920)
            assert any(s["codec_type"] == "audio" for s in probe["streams"])
            assert 29 <= float(probe["format"]["duration"]) <= 36
            other = call("POST", "/v1/auth/signup", {
                "email": f"other-{suffix}@example.com", "password": secrets.token_urlsafe(24)})
            try:
                call("GET", f"/v1/outputs/{outputs[0]['id']}/download", token=other["token"], raw=True)
            except HTTPError as exc:
                assert exc.code == 404
            else:
                raise AssertionError("Cross-workspace download was allowed")
            report = {"status": "passed", "api_stopped_during_worker": True,
                      "dimensions": [video["width"], video["height"]],
                      "duration": probe["format"]["duration"], "cross_workspace_download": "denied",
                      "transcription": "real Whisper on synthesized English speech" if args.real_transcription else "synthetic cached fixture", "analysis": "offline heuristic",
                      "render": "real FFmpeg", "paid_api": False, "youtube_upload": False}
            (evidence / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(report, ensure_ascii=False))
        finally:
            for process in (worker, api):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            db.close()
            api_log.close()
            worker_log.close()


if __name__ == "__main__":
    main()
