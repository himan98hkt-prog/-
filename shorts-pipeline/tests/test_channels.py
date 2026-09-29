"""채널 분리와 LTX 지원을 붙잡아 두는 검사.

    python tests/test_channels.py

여기 있는 것은 전부 **그냥 두면 새벽에 조용히 깨지는** 자리다.

  1. LTX 는 6초부터 2초 단위로만 받는다 — 5 초로 두면 매일 아침 422 로 실패한다
  2. 길이를 num_frames 로 받는 모델이 있다  — 초를 그대로 보내면 0.2초짜리가 나온다
  3. 채널이 둘이면 예약이 서로를 덮어썼다   — 작업 이름과 daily.bat 이 하나였다
  4. 남의 채널 영상을 집어 올렸다            — latest_run 이 runs/ 전체를 봤다
  5. 생성이 실패하면 어제 영상이 다시 올라갔다 — 시각 제한이 없었다
  6. 모델이 만든 소리를 무음으로 덮었다      — LTX-2 는 소리를 함께 만든다

API 호출은 0회, 비용은 $0 이다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = ROOT / "tests" / "_tmp_channels"


# ── 도구 ────────────────────────────────────────────────────────────
def write_config(name: str, **over) -> Path:
    """최소한으로 도는 설정 한 벌. over 로 필요한 것만 덮어쓴다."""
    cfg = {
        "mode": "chain",
        "provider": "fal",
        "model": "ltx2_fast_1080",
        "clip_duration": 20,
        "num_clips": 1,
        "upscale_between_clips": False,
        "upscaler": "esrgan",
        "output": {"width": 1080, "height": 1920, "fps": "auto", "crf": 18,
                   "audio": "silent"},
        "cost": {"retry_multiplier": 1.8, "hard_cap_usd": 25.0},
        "providers": {
            "fal": {
                "endpoint_base": "https://queue.fal.run",
                "models": {
                    "ltx2_fast_1080": {
                        "endpoint": "fal-ai/ltx-2/image-to-video/fast",
                        "price_per_second": 0.04,
                        "min_duration": 6, "max_duration": 20, "duration_step": 2,
                        "supports_end_image": False, "supports_negative": True,
                        "has_native_audio": True,
                        "extra_params": {"resolution": "1080p"},
                    },
                    "ltxv_13b_distilled": {
                        "endpoint": "fal-ai/ltxv-13b-098-distilled/image-to-video",
                        "price_per_second": 0.02,
                        "min_duration": 2, "max_duration": 10, "duration_step": 1,
                        "duration_param": "num_frames", "frames_per_second": 24,
                        "supports_end_image": False, "supports_negative": True,
                    },
                    "plain": {
                        "endpoint": "fal-ai/whatever",
                        "price_per_second": 0.05, "max_duration": 10,
                        "supports_end_image": False, "supports_negative": True,
                    },
                },
                "upscalers": {"esrgan": {"endpoint": "fal-ai/esrgan",
                                         "price_per_image": 0.01}},
            }
        },
    }
    cfg.update(over)
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / name
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def make_clip(path: Path, *, seconds: float = 1.0, audio: bool) -> Path:
    """진짜 mp4. audio=False 면 오디오 트랙이 아예 없다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=320x568:rate=24:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                 "-c:a", "aac", "-shortest"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds), str(path)]
    subprocess.run(args, check=True, capture_output=True)
    return path


# ── 1. LTX 길이 격자 ─────────────────────────────────────────────────
def test_ltx_rejects_off_grid_duration():
    """6초부터 2초 단위. 5·7·21 은 설정을 읽는 시점에 막혀야 한다.

    fal 에 접수되기 전에 막는 것이 요점이다. 그냥 두면 예약이 새벽에
    돌다가 422 로 죽고, 그날 영상이 안 올라가는데 아무도 모른다.
    """
    from pipeline.config import ConfigError, load_config

    for bad in (5, 7, 21, 0):
        try:
            load_config(write_config(f"bad{bad}.yaml", clip_duration=bad))
        except ConfigError as exc:
            assert "받지 않습니다" in str(exc) or "1 이상" in str(exc), str(exc)
        else:
            raise AssertionError(f"clip_duration={bad} 가 통과했다")

    for good in (6, 8, 20):
        cfg = load_config(write_config(f"ok{good}.yaml", clip_duration=good))
        assert cfg.clip_duration == good

    # 안내 메시지에 실제로 받는 길이가 적혀 있어야 고칠 수 있다
    try:
        load_config(write_config("bad5b.yaml", clip_duration=5))
    except ConfigError as exc:
        assert "6" in str(exc) and "20" in str(exc), str(exc)


# ── 2. 길이 파라미터 ─────────────────────────────────────────────────
def test_duration_payload_shapes():
    """모델마다 길이를 받는 이름이 다르다. 초를 그대로 보내면 안 되는 모델이 있다."""
    from pipeline.config import ConfigError, load_config

    # 기본: duration (초)
    cfg = load_config(write_config("p1.yaml", model="plain", clip_duration=8))
    assert cfg.model.request_extras(8) == {"duration": 8}

    # LTX-2: duration + 고정 해상도
    cfg = load_config(write_config("p2.yaml"))
    assert cfg.model.request_extras(20) == {"duration": 20, "resolution": "1080p"}

    # 0.9.x: num_frames 로 환산. 10초 × 24fps = 240 프레임.
    cfg = load_config(write_config("p3.yaml", model="ltxv_13b_distilled",
                                   clip_duration=10))
    assert cfg.model.request_extras(10) == {"num_frames": 240}

    # 프레임률을 안 적어 두면 길이가 조용히 틀어지므로 차라리 죽는다
    from pipeline.config import ModelSpec
    spec = ModelSpec(key="x", endpoint="e", max_duration=10,
                     supports_end_image=False, supports_negative=False,
                     duration_param="num_frames")
    try:
        spec.duration_payload(5)
    except ConfigError:
        pass
    else:
        raise AssertionError("frames_per_second 없이 통과했다")


def test_model_params_reach_the_request():
    """config 의 extra_params 가 실제 fal 요청 본문까지 닿아야 한다."""
    from pipeline.config import load_config
    from pipeline.providers.base import GenerationRequest

    cfg = load_config(write_config("p4.yaml"))
    req = GenerationRequest(
        image=Path("x.png"), prompt="p", duration=cfg.clip_duration,
        duration_params=cfg.model.request_extras(cfg.clip_duration))

    # fal.py 가 만드는 payload 와 같은 순서로 재현한다
    payload = {"image_url": "...", "prompt": req.prompt}
    payload.update(req.duration_params or {"duration": req.duration})
    assert payload["duration"] == 20
    assert payload["resolution"] == "1080p"


# ── 3. 채널 분리 ─────────────────────────────────────────────────────
def test_channel_dirs_are_separate():
    """채널을 지정하면 산출물·시드가 갈리고, 지정 안 하면 예전 경로 그대로다."""
    from pipeline.config import ConfigError, load_config

    # 예전 설정(channel 없음)은 건드리지 않는다 — 경로를 바꾸면 지난 영상과
    # 이번 달 누적 비용을 잃는다.
    cfg = load_config(write_config("c1.yaml"))
    assert (cfg.channel_slug, cfg.runs_dir, cfg.seeds_dir) == ("default", "runs", "seeds")

    cfg = load_config(write_config("c2.yaml", channel={
        "slug": "wonri", "name": "원리한입", "publish_at": "09:00"}))
    assert cfg.channel_slug == "wonri"
    assert cfg.channel_name == "원리한입"
    assert cfg.publish_at == "09:00"
    # 기본값이 서로 겹치지 않아야 한다
    assert cfg.runs_dir == "runs-wonri" and cfg.seeds_dir == "seeds-wonri"

    for bad in ("../etc", "원리", "A B", "", "-x"):
        try:
            load_config(write_config("c3.yaml", channel={"slug": bad}))
        except ConfigError:
            pass
        else:
            raise AssertionError(f"slug={bad!r} 가 통과했다")


def test_publish_at_must_be_a_clock():
    from pipeline.config import ConfigError, load_config

    for bad in ("9:00", "25:00", "09:60", "아침"):
        try:
            load_config(write_config("t1.yaml",
                                     channel={"slug": "w", "publish_at": bad}))
        except ConfigError:
            pass
        else:
            raise AssertionError(f"publish_at={bad!r} 가 통과했다")

    cfg = load_config(write_config("t2.yaml",
                                   channel={"slug": "w", "publish_at": "09:00"}))
    assert cfg.publish_at == "09:00"


# ── 4. 예약이 채널마다 따로 ──────────────────────────────────────────
def test_schedule_does_not_collide():
    """두 번째 채널 예약이 첫 채널 예약을 덮어쓰면 안 된다."""
    from pipeline import win_schedule as ws

    # 기본 채널은 예전 이름·예전 파일을 그대로 쓴다 (이미 걸린 예약 보존)
    assert ws.task_name("default") == ws.TASK_NAME
    assert ws.runner_path("default").name == "daily.bat"

    assert ws.task_name("wonri", "원리한입") != ws.TASK_NAME
    assert ws.runner_path("wonri").name == "daily-wonri.bat"
    assert ws.runner_path("wonri") != ws.runner_path("default")


def test_runner_is_ascii_and_carries_channel():
    """daily.bat 은 ASCII 여야 하고 채널 설정을 넘겨야 한다.

    cmd 는 배치 파일을 코드페이지 949 로 읽는다. 한글이 섞이면 깨진 글자가
    명령으로 실행되려다 오류를 낸다 — 예약이 매일 밤 조용히 실패한다.
    """
    from pipeline import win_schedule as ws

    bat = ws.write_runner("09:00", ["youtube"], "chain",
                          config="config.wonri.yaml", seeds="seeds-wonri",
                          slug="wonri", runs_dir="runs-wonri")
    try:
        text = bat.read_bytes().decode("ascii")   # 깨지면 여기서 죽는다
        assert "--at 09:00" in text
        assert '--config "config.wonri.yaml"' in text
        assert '--seeds "seeds-wonri"' in text
        assert "--youtube" in text
        # 로그도 채널 폴더로 가야 서로 섞이지 않는다
        assert "--log runs-wonri/cron.log" in text
        # 첫 로그 줄에서 죽던 원인(cp949). 이게 빠지면 예약이 매일 조용히 실패한다.
        assert "set PYTHONUTF8=1" in text
        assert "\r\n" in text        # cmd 는 CRLF 를 기대한다
        # 기본 채널 파일을 덮어쓰면 기존 예약이 망가진다
        assert bat.name == "daily-wonri.bat"
    finally:
        bat.unlink(missing_ok=True)


def test_schedule_catches_up_missed_runs():
    """아침 예약의 핵심 — 절전으로 놓친 실행을 깨어난 뒤 따라잡아야 한다.

    08:30 에 PC 가 자고 있으면 그냥 건너뛰고 오류도 안 남는다. 그날 영상만
    안 올라간다.
    """
    from pipeline import win_schedule as ws

    script = ws.register_script(
        "08:30", "09:00", ["youtube"], "chain",
        pythonw=r"C:\py\pythonw.exe", workdir=r"C:\shorts",
        task="쇼츠 자동업로드 - 원리한입", config="config.wonri.yaml",
        seeds="seeds-wonri", runs_dir="runs-wonri")

    assert "-StartWhenAvailable" in script     # 깨어난 뒤 따라잡기
    assert "-WakeToRun" in script              # 절전에서 깨우기
    assert "-AllowStartIfOnBatteries" in script
    assert "-MultipleInstances IgnoreNew" in script   # 겹쳐 돌면 값이 두 번 나간다
    assert "08:30" in script
    # 채널 설정이 실제 명령줄까지 닿아야 한다
    assert '--config \\"config.wonri.yaml\\"' in script or "config.wonri.yaml" in script
    assert "원리한입" in script                 # 기본 채널 작업을 덮어쓰지 않는다


# ── 5. 방금 만든 것만 올린다 ─────────────────────────────────────────
def test_latest_run_only_sees_this_run():
    """생성이 실패했을 때 어제 영상이 다시 올라가면 안 된다.

    중복 업로드는 되돌릴 수 없다. 오늘 안 올리는 편이 낫다.
    """
    import os
    import time

    from publish import scheduler

    runs = TMP / "runs-x"
    old = runs / "20200101_000000"
    old.mkdir(parents=True, exist_ok=True)
    (old / "final.mp4").write_bytes(b"old")
    long_ago = time.time() - 86400
    os.utime(old / "final.mp4", (long_ago, long_ago))

    keep = scheduler.RUNS_DIR
    try:
        scheduler.RUNS_DIR = runs
        started = time.time() - 1
        # 이번 실행에서 아무것도 안 만들어졌다면 → 없다고 해야 한다
        assert scheduler.latest_run(newer_than=started) is None
        # 시각 제한이 없으면 예전 것을 집는다 (예전 동작 — 이게 문제였다)
        assert scheduler.latest_run() == "20200101_000000"

        fresh = runs / "20260101_090000"
        fresh.mkdir(parents=True, exist_ok=True)
        (fresh / "final.mp4").write_bytes(b"new")
        assert scheduler.latest_run(newer_than=started) == "20260101_090000"

        # 다른 채널 폴더는 아예 보이지 않는다
        other = TMP / "runs-y"
        other.mkdir(parents=True, exist_ok=True)
        scheduler.RUNS_DIR = other
        assert scheduler.latest_run(newer_than=started) is None
    finally:
        scheduler.RUNS_DIR = keep


# ── 6. 모델이 만든 소리를 지우지 않는다 ──────────────────────────────
def test_native_audio_is_kept():
    """LTX-2 는 소리를 함께 만든다. 무음 트랙으로 덮으면 통째로 버려진다."""
    from pipeline.stitcher import _audio_args

    clips = [make_clip(TMP / "a.mp4", audio=True),
             make_clip(TMP / "b.mp4", audio=True)]

    args, amap, graph = _audio_args("native", None, 2, 4.0, clips)
    # 입력을 더하지 않는다 — 소리는 이미 들어온 영상 입력에 있다
    assert args == []
    assert amap == ["-map", "[aout]"]
    assert graph == "[0:a][1:a]concat=n=2:v=0:a=1[aout]"
    # anullsrc 가 끼어들면 모델 소리가 사라진 것이다
    assert "anullsrc" not in graph

    # 소리 없는 클립이 섞이면 concat 이 실패하므로 무음으로 물러선다
    mixed = clips + [make_clip(TMP / "c.mp4", audio=False)]
    args, amap, graph = _audio_args("native", None, 3, 6.0, mixed)
    assert any("anullsrc" in a for a in args)


def test_native_audio_survives_stitching():
    """실제로 합성해서 최종 파일에 소리가 남아 있는지 본다."""
    from pipeline.ffmpeg_util import has_audio
    from pipeline.stitcher import stitch

    clips = [make_clip(TMP / "s1.mp4", seconds=1.0, audio=True),
             make_clip(TMP / "s2.mp4", seconds=1.0, audio=True)]
    dest = TMP / "final_native.mp4"
    stitch(clips, dest, width=180, height=320, fps=24, crf=30,
           crossfade=0, transition="cut", audio="native")
    assert dest.exists() and dest.stat().st_size > 0
    assert has_audio(dest), "모델이 만든 소리가 최종 파일에서 사라졌다"


# ── 7. 실제 원리한입 설정 ────────────────────────────────────────────
def test_wonri_config_is_usable():
    """저장소에 든 config.wonri.yaml 이 8GB 카드에서 그대로 돌 수 있어야 한다."""
    from pipeline.config import load_config
    from pipeline.providers import ltx09

    cfg = load_config(ROOT / "config.wonri.yaml")
    assert cfg.channel_slug == "wonri"
    assert cfg.publish_at == "09:00"              # 아침 9시
    assert cfg.provider == "ltx09"                # 집 PC 엔진
    assert cfg.model.cost_per_clip(cfg.clip_duration, 0.0) == 0   # 편당 $0

    s = cfg.provider_cfg
    w, h = int(s["width"]), int(s["height"])
    # 어기면 실행 시점에 깨지는 것들
    ltx09.check_size(w, h)                        # 32 의 배수
    assert w <= ltx09.SOFT_MAX_W and h <= ltx09.SOFT_MAX_H, \
        f"{w}x{h} 는 권장 범위(720x1280)를 넘는다 — 8GB 에서 위험하다"

    from pipeline.providers.ltx_local import num_frames
    frames = num_frames(cfg.clip_duration, float(s["fps"]))
    assert frames % 8 == 1, f"프레임 수는 8k+1 이어야 한다 ({frames})"
    assert frames < ltx09.SOFT_MAX_FRAMES, \
        f"{frames}프레임은 권장 상한(257)을 넘는다 — 8GB 에서 메모리가 모자란다"

    # 0.9.x 는 소리를 만들지 않는다. 음악을 깔아야 무음으로 나가지 않는다.
    assert not cfg.model.has_native_audio
    assert cfg.output.get("audio") != "silent"

    # 기본 채널과 폴더가 겹치면 서로의 영상을 집어 올린다
    base = load_config(ROOT / "config.yaml")
    assert cfg.runs_dir != base.runs_dir
    assert cfg.seeds_dir != base.seeds_dir


def test_wonri_end_to_end():
    """원리한입 설정 그대로 생성 → 합성까지 실제로 돌린다.

    그래픽카드가 없으므로 LTX 실행 파일만 가짜로 바꾼다. 명령을 만드는 코드와
    결과를 찾는 코드는 진짜가 돈다 — 그 둘이 이 엔진에서 틀리기 쉬운 자리다.
    """
    import os
    import shutil

    from pipeline.config import load_config
    from pipeline.ffmpeg_util import dimensions_of
    from pipeline.modes import orchestrate
    from pipeline.runlog import Run
    from pipeline.stitcher import stitch
    from pipeline.validator import prepare_input

    real = yaml.safe_load((ROOT / "config.wonri.yaml").read_text(encoding="utf-8"))

    # 가짜 LTX 설치본: inference.py · .venv 파이썬 · configs/
    home = TMP / "ltxhome"
    (home / "configs").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "tests" / "fake_ltx09.py", home / "inference.py")
    (home / "configs" / "ltxv-2b-0.9.8-distilled-fp8.yaml").write_text("{}\n",
                                                                      encoding="utf-8")
    venv = home / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv.mkdir(parents=True, exist_ok=True)
    py = venv / ("python.exe" if os.name == "nt" else "python")
    if not py.exists():
        py.symlink_to(sys.executable)

    real["providers"]["ltx09"]["ltx_dir"] = str(home)
    real["providers"]["ltx09"]["python"] = str(py)
    real["providers"]["ltx09"]["upscale_clips"] = "off"   # Real-ESRGAN 은 없다
    path = TMP / "wonri_fake.yaml"
    path.write_text(yaml.safe_dump(real, allow_unicode=True), encoding="utf-8")

    cfg = load_config(path)
    log = TMP / "ltx09_calls.log"
    log.unlink(missing_ok=True)
    os.environ["FAKE_LTX09_LOG"] = str(log)
    try:
        run = Run.create(TMP / "runs-wonri", "e2e09")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "testsrc=size=1080x1920:rate=1:duration=1",
             "-frames:v", "1", str(TMP / "seed09.png")],
            check=True, capture_output=True)
        prepare_input(TMP / "seed09.png", run.input_image)

        clips, stats = orchestrate(cfg, run, interactive=False, resume=False)
        assert len(clips) == cfg.num_clips == 2
        assert stats.clip_calls == 2

        # 가짜가 받은 명령 — 계약을 어기면 가짜가 먼저 거절한다
        sent = log.read_text(encoding="utf-8").splitlines()
        assert len(sent) == 2
        first = sent[0]
        assert "--num_frames 193" in first          # 8초 x 24fps = 8*24+1
        assert "--width 544" in first and "--height 960" in first
        assert "--output_path" in first
        assert "--num-frames" not in first          # 하이픈이면 진짜가 거절한다

        stitch(clips, run.final, width=cfg.output["width"],
               height=cfg.output["height"], fps=24, crf=30,
               crossfade=0.3, transition="fade", audio="silent")
        assert run.final.exists() and run.final.stat().st_size > 0
        assert dimensions_of(run.final) == (1080, 1920)
        assert (TMP / "runs-wonri" / "e2e09" / "final.mp4").exists()
    finally:
        os.environ.pop("FAKE_LTX09_LOG", None)


def test_ltx09_command_contract():
    """명령이 0.9.x 의 실제 계약과 어긋나면 안 된다."""
    from pipeline.providers import ltx09
    from pipeline.providers.base import GenerationRequest

    home = TMP / "ltxhome2"
    (home / "configs").mkdir(parents=True, exist_ok=True)
    (home / "inference.py").write_text("", encoding="utf-8")
    (home / "configs" / "c.yaml").write_text("{}\n", encoding="utf-8")
    venv = home / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv.mkdir(parents=True, exist_ok=True)
    py = venv / ("python.exe" if os.name == "nt" else "python")
    py.write_text("", encoding="utf-8")
    img = make_clip(TMP / "c.mp4", audio=False)   # 존재하기만 하면 된다

    p = ltx09.LTX09Provider("configs/c.yaml", settings={
        "ltx_dir": str(home), "python": str(py),
        "width": 544, "height": 960, "fps": 24, "offload_to_cpu": "true"})
    cmd = p.command(GenerationRequest(image=img, prompt="p", duration=8,
                                      negative_prompt="blurry"),
                    TMP / "outdir")

    assert "--num_frames" in cmd and cmd[cmd.index("--num_frames") + 1] == "193"
    assert "--conditioning_media_paths" in cmd
    assert cmd[cmd.index("--conditioning_start_frames") + 1] == "0"
    assert cmd[cmd.index("--negative_prompt") + 1] == "blurry"
    assert "--offload_to_cpu" in cmd
    # 2.5 판의 인자는 하나도 섞이면 안 된다
    for wrong in ("--num-frames", "--output-path", "--image", "--quantization"):
        assert wrong not in cmd, f"{wrong} 가 섞였다 (2.5 판 인자)"

    # 32 의 배수가 아니면 설정 단계에서 막는다
    bad = ltx09.LTX09Provider("configs/c.yaml", settings={
        "ltx_dir": str(home), "python": str(py), "width": 540, "height": 960})
    try:
        bad.command(GenerationRequest(image=img, prompt="p", duration=8),
                    TMP / "outdir2")
    except Exception as exc:
        assert "32" in str(exc)
    else:
        raise AssertionError("540 폭이 통과했다")


def test_ltx09_offload_defaults_on_for_small_cards():
    """8GB 에서 오프로드가 꺼진 채 돌면 첫 클립에서 OOM 이다."""
    from pipeline.providers import ltx09

    assert ltx09.offload_wanted({"offload_to_cpu": "true"}) is True
    assert ltx09.offload_wanted({"offload_to_cpu": "false"}) is False
    # auto 는 그래픽카드를 못 읽으면(이 환경이 그렇다) 켠다 — 켜서 느린 편이
    # 꺼서 죽는 것보다 낫다. 예약이 죽으면 그날 영상이 없다.
    assert ltx09.offload_wanted({"offload_to_cpu": "auto"}) is True

    # 8GB 는 되고, 그보다 작으면 클라우드를 권한다
    assert ltx09.vram_ok(8 * 1024)
    assert not ltx09.vram_ok(4 * 1024)
    assert "8GB" in ltx09.memory_note(8 * 1024)


def test_seamless_loop_does_not_desync_model_audio():
    """루프 잇기는 영상만 재배열한다 — 모델이 만든 소리와 어긋난다.

    make_seamless 는 마지막 L 초를 앞으로 옮겨 겹치면서 소리는 `-map 0:a` 로
    원본 순서 그대로 붙인다. 음악 반주에서는 티가 안 나지만, 그림에 맞춰
    만들어진 소리라면 그만큼 밀린다. 그래서 두 기능을 같이 켜지 않는다.

    (원리한입은 지금 소리를 만들지 않는 엔진을 쓰므로 루프를 켜 둔다. 그래도
    가드 자체는 남아 있어야 한다 — 엔진을 되돌리는 순간 다시 필요해진다.)
    """
    from pipeline.config import load_config

    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'loop_cfg.get("enabled") and cfg.model.has_native_audio' in src, \
        "native audio 일 때 루프를 건너뛰는 가드가 사라졌다"

    cfg = load_config(ROOT / "config.wonri.yaml")
    if cfg.model.has_native_audio:
        assert not (cfg.output.get("seamless_loop") or {}).get("enabled"), \
            "모델이 소리를 만드는데 seamless_loop 가 켜져 있다"


def test_base_config_still_loads():
    """기존 채널 설정이 새 키 때문에 깨지면 안 된다."""
    from pipeline.config import load_config

    cfg = load_config(ROOT / "config.yaml")
    assert cfg.channel_slug == "default"
    assert cfg.runs_dir == "runs" and cfg.seeds_dir == "seeds"


# ── 실행 ────────────────────────────────────────────────────────────
def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    try:
        for fn in tests:
            try:
                fn()
                print(f"  ✓ {fn.__name__}")
            except Exception as exc:  # noqa: BLE001
                failed.append(fn.__name__)
                print(f"  ✗ {fn.__name__} — {exc}")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "=" * 60)
    print(f"통과 {len(tests) - len(failed)} · 실패 {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
