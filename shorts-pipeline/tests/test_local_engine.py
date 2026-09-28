"""내 PC 엔진(LTX-2.5)을 그래픽카드 없이 끝까지 시험한다.

    python tests/test_local_engine.py

진짜 LTX 대신 tests/fake_ltx.py 가 같은 명령줄을 받아 ffmpeg 로 클립을
만든다. 그 명령이 Lightricks 의 진짜 인자 파서를 통과하는지는 개발 중에
따로 확인했다(FAKE_LTX_ARGS_CHECK). 여기서는 우리 쪽 흐름을 본다:

  명령 조립 · 메모리 자동 설정 · 이어 붙이기 · 합성 · 비용 0 · 업스케일 ·
  오류 안내 · 엔진 전환 · 점검 화면
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_local"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


def make_fake_ltx(root: Path) -> Path:
    """모델 파일(빈 파일)과 '파이썬'(fake_ltx.py 를 부르는 스크립트)을 깐다."""
    from pipeline.providers import ltx_local as L

    s = L.settings_with_defaults({"ltx_dir": str(root)})
    for cands in L.FILES.values():
        p = L.models_dir(s) / cands[0]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    py = L.python_path(s)
    py.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":                              # CI 는 리눅스지만 혹시 몰라
        shutil.copyfile(sys.executable, py)
    else:
        py.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{ROOT / "tests" / "fake_ltx.py"}" "$@"\n')
        py.chmod(py.stat().st_mode | stat.S_IEXEC)
    return root


def make_seed(path: Path) -> Path:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1080, 1920), (18, 26, 48))
    d = ImageDraw.Draw(img)
    for i in range(0, 1920, 120):
        d.rectangle([200, i, 880, i + 60], fill=(40 + i // 20, 80, 160))
    img.save(path)
    return path


def local_config(ltx_root: Path, **extra) -> Path:
    raw = yaml.safe_load((ROOT / "tests" / "config.test.yaml").read_text(encoding="utf-8"))
    raw.update(provider="local", model="ltx_25_distilled", clip_duration=5, num_clips=2)
    raw["output"]["fps"] = "auto"
    raw["providers"]["local"] = {"ltx_dir": str(ltx_root), "quantization": "fp8-cast",
                                 "offload": "cpu", "seed": 7, **extra}
    path = TMP / "config.local.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


class RunsGuard:
    def __enter__(self):
        self.runs = ROOT / "runs"
        self.runs.mkdir(exist_ok=True)
        self.before = {p.name for p in self.runs.iterdir()}
        return self

    def new_runs(self) -> list[Path]:
        return sorted(p for p in self.runs.iterdir()
                      if p.is_dir() and p.name not in self.before)

    def __exit__(self, *exc):
        for p in self.new_runs():
            shutil.rmtree(p, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════
def test_frames_and_sizes():
    section("프레임 수 · 크기 규칙")
    from pipeline.providers import ltx_local as L
    from pipeline.providers.base import ProviderError

    check("10초 24fps -> 241 (8k+1)", L.num_frames(10, 24) == 241)
    check("5초 24fps -> 121", L.num_frames(5, 24) == 121)
    check("모든 길이가 8k+1", all((L.num_frames(s, 24) - 1) % 8 == 0 for s in range(1, 11)))
    try:
        L.check_size(1080, 1920)
        ok = False
    except ProviderError as exc:
        ok = not exc.retryable and exc.billed is False and "576x1024" in str(exc)
    check("1080x1920 은 64 배수가 아니라서 알려준다", ok)
    L.check_size(576, 1024)
    L.check_size(1088, 1920)
    check("576x1024 · 1088x1920 은 통과", True)


def test_memory_plan():
    section("그래픽카드·메모리에 맞춘 자동 설정")
    from pipeline.providers.ltx_local import memory_plan

    gb = 1024
    check("48GB -> 제한 없음", memory_plan(48 * gb, 64)[:2] == ("none", "none"))
    check("32GB -> fp8 만", memory_plan(32 * gb, 64)[:2] == ("fp8-cast", "none"))
    check("24GB + RAM 64GB -> 시스템 메모리로 나눠서",
          memory_plan(24 * gb, 64)[:2] == ("fp8-cast", "cpu"))
    check("16GB + RAM 32GB -> 디스크까지", memory_plan(16 * gb, 32)[:2] == ("fp8-cast", "disk"))
    check("RAM 부족이면 64GB 권장이라고 말한다", "64GB" in memory_plan(16 * gb, 32)[2])
    check("6GB -> 너무 작다고 말한다", "너무 작" in memory_plan(6 * gb, 64)[2])
    check("못 읽으면 안전하게 cpu", memory_plan(None)[:2] == ("fp8-cast", "cpu"))


def test_config_defaults():
    section("설정 — 예전 config.yaml 에도 내 PC 엔진이 붙는다")
    from pipeline.config import load_config
    from pipeline.costs import estimate

    raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["providers"].pop("local", None)          # 업데이트 전 사용자 설정
    raw.update(provider="local", model="ltx_25_distilled")
    old = TMP / "old.yaml"
    old.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    cfg = load_config(old)
    check("블록이 없어도 읽힌다", cfg.provider_cfg["width"] == 576)
    check("업스케일러 esrgan -> 내 PC 것으로 대신", cfg.upscaler.key == "local",
          cfg.upscaler.key)
    e = estimate(cfg)
    check("한 편 비용 $0", e.expected == 0.0, f"${e.expected}")

    cloud = load_config(ROOT / "config.yaml")
    check("클라우드 설정은 그대로", cloud.provider == "fal" and estimate(cloud).expected > 0)


def test_command():
    section("LTX 명령 조립")
    from pipeline.providers import ltx_local as L
    from pipeline.providers.base import GenerationRequest, ProviderError

    fake = make_fake_ltx(TMP / "ltx_cmd")
    seed = make_seed(TMP / "seed_cmd.png")
    real = (L.gpu_memory_mb, L.system_ram_gb)
    L.gpu_memory_mb, L.system_ram_gb = (lambda: 24 * 1024), (lambda: 64.0)
    try:
        prov = L.LocalLTXProvider("distilled", settings={"ltx_dir": str(fake)})
        cmd = prov.command(GenerationRequest(image=seed, prompt="앞으로 'go'", duration=10),
                           TMP / "o.mp4")
    finally:
        L.gpu_memory_mb, L.system_ram_gb = real
    joined = " ".join(cmd)
    check("distilled 파이프라인", cmd[1:3] == ["-m", "ltx_pipelines.distilled"])
    i = cmd.index("--image")
    check("앞 클립 마지막 장면을 0번 프레임에 고정",
          cmd[i + 1:i + 4] == [str(seed), "0", "1.0"])
    check("241 프레임", cmd[cmd.index("--num-frames") + 1] == "241")
    check("24fps", cmd[cmd.index("--frame-rate") + 1] == "24")
    check("LTX 업스케일러를 넘긴다", "latent-spatial-upscaler-x2" in joined)
    check("가벼운 conv VAE 를 먼저 쓴다", "video-vae-conv" in joined)
    check("24GB+64GB 면 fp8 + cpu 로 자동",
          "--quantization fp8-cast" in joined and "--offload cpu" in joined)
    check("프롬프트는 통째로 한 인자", cmd[cmd.index("--prompt") + 1] == "앞으로 'go'")

    dfr = L.LocalLTXProvider("dfr_pipeline", settings={"ltx_dir": str(fake)})
    try:
        dfr.command(GenerationRequest(image=seed, prompt="p", duration=5), TMP / "d.mp4")
        ok = False
    except ProviderError as exc:
        ok = "ic-lora-pixel-spatial-upscaler" in str(exc)
    check("DFR 은 디테일 LoRA 가 없으면 무엇이 없는지 말한다", ok)

    empty = L.LocalLTXProvider("distilled", settings={"ltx_dir": str(TMP / "nowhere")})
    try:
        empty.command(GenerationRequest(image=seed, prompt="p", duration=5), TMP / "e.mp4")
        ok, msg = False, ""
    except ProviderError as exc:
        ok, msg = (not exc.retryable and exc.billed is False), str(exc)
    check("설치 전이면 설치 방법을 알려준다", ok and "ltx_setup" in msg)


def test_end_to_end():
    section("처음부터 끝까지 — 이어지는 영상 2클립, 비용 $0")
    from pipeline.ffmpeg_util import dimensions_of, duration_of, fps_of

    fake = make_fake_ltx(TMP / "ltx_e2e")
    seed = make_seed(TMP / "seed_e2e.png")
    cfg = local_config(fake)
    log = TMP / "fake_calls.log"
    env = dict(os.environ, FAKE_LTX_LOG=str(log), PYTHONIOENCODING="utf-8")
    env.pop("SHORTS_MOCK", None)
    env.pop("FAKE_LTX_FAIL", None)
    with RunsGuard() as guard:
        p = subprocess.run([sys.executable, "main.py", "generate", "--image", str(seed),
                            "--config", str(cfg), "--yes"],
                           cwd=ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        runs = guard.new_runs()
        final = runs[-1] / "final.mp4" if runs else None
        state = json.loads((runs[-1] / "state.json").read_text("utf-8")) if runs else {}
        calls = log.read_text().splitlines() if log.exists() else []
        ok = p.returncode == 0 and final is not None and final.exists()
        check("완성", ok, (p.stdout + p.stderr)[-400:] if not ok else "")
        if ok:
            w, h = dimensions_of(final)
            check("1080x1920 으로 맞춘다", (w, h) == (1080, 1920), f"{w}x{h}")
            check("LTX 프레임률(24)을 그대로", round(fps_of(final) or 0) == 24)
            dur = duration_of(final)
            check("길이가 맞다 (2 x 5초 - 이음새)", 8.5 < dur < 10.5, f"{dur:.2f}초")
        check("클립마다 LTX 를 한 번씩", len(calls) == 2, str(len(calls)))
        check("두 번째 클립은 첫 클립의 마지막 장면에서 시작",
              len(calls) == 2 and "last_01" in calls[1], calls[1][:120] if len(calls) > 1 else "")
        check("비용 $0 으로 기록", float(state.get("cost_usd", 1)) == 0.0,
              str(state.get("cost_usd")))
        check("살아 있음을 찍는다 (기다리는 화면용)",
              "만드는 중" in p.stdout or "클립 생성 완료" in p.stdout)


def test_preview_on_local():
    section("[싸게 먼저 시험하기] 도 내 PC 엔진으로")
    fake = make_fake_ltx(TMP / "ltx_pv")
    seed = make_seed(TMP / "seed_pv.png")
    cfg = local_config(fake)
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    # 시험용 모델은 클라우드 목록에만 있다. 예전에는 여기서 설정 오류로 죽었다.
    raw["preview"] = {"model": "wan_25_480p", "clip_duration": 5, "upscale": False}
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("FAKE_LTX_FAIL", None)
    with RunsGuard():
        p = subprocess.run([sys.executable, "main.py", "preview", "--image", str(seed),
                            "--config", str(cfg), "--yes"],
                           cwd=ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    check("시험판이 나온다", p.returncode == 0, (p.stdout + p.stderr)[-300:])
    check("내 PC 모델로, $0", "local/ltx_25_distilled" in p.stdout and "$0.00" in p.stdout)


def test_out_of_memory_message():
    section("그래픽카드 메모리 부족 — 알아듣게 말하고 헛되이 반복하지 않는다")
    fake = make_fake_ltx(TMP / "ltx_oom")
    seed = make_seed(TMP / "seed_oom.png")
    cfg = local_config(fake)
    log = TMP / "oom_calls.log"
    env = dict(os.environ, FAKE_LTX_FAIL="oom", FAKE_LTX_LOG=str(log),
               PYTHONIOENCODING="utf-8")
    env.pop("SHORTS_MOCK", None)
    with RunsGuard():
        p = subprocess.run([sys.executable, "main.py", "generate", "--image", str(seed),
                            "--config", str(cfg), "--yes"],
                           cwd=ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    out = p.stdout + p.stderr
    check("실패로 끝난다", p.returncode != 0)
    check("메모리가 모자라다고 말한다", "메모리가 모자랍니다" in out)
    check("무엇을 바꾸면 되는지 말한다", "576x1024" in out)
    calls = log.read_text().splitlines() if log.exists() else []
    check("같은 실패를 세 번 되풀이하지 않는다", len(calls) == 1, f"{len(calls)}회")


def test_realesrgan():
    section("Real-ESRGAN 업스케일 (설치돼 있을 때)")
    from pipeline import upscale
    from pipeline.ffmpeg_util import dimensions_of, duration_of

    # 진짜 realesrgan 처럼 -i 폴더 -o 폴더 -s 배율 을 받는 가짜
    fake = TMP / "esr" / "realesrgan-ncnn-vulkan"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text(f'''#!{sys.executable}
import sys
from pathlib import Path
from PIL import Image
a = sys.argv
src, dst, s = Path(a[a.index("-i")+1]), Path(a[a.index("-o")+1]), int(a[a.index("-s")+1])
files = sorted(src.glob("*.png")) if src.is_dir() else [src]
for f in files:
    out = dst / f.name if src.is_dir() else dst
    im = Image.open(f); im.resize((im.width*s, im.height*s)).save(out)
''')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    os.environ["REALESRGAN_PATH"] = str(fake)
    try:
        check("REALESRGAN_PATH 로 찾는다", upscale.find_realesrgan() == fake)
        clip = TMP / "esr" / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                        "-i", "testsrc2=size=192x320:rate=24:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(clip)], check=True)
        upscale.upscale_video(clip, clip, exe=fake, model="realesr-animevideov3", scale=2)
        check("2배로 커진다", dimensions_of(clip) == (384, 640), str(dimensions_of(clip)))
        check("길이는 그대로", abs(duration_of(clip) - 1.0) < 0.1)
        check("모델에 없는 배율은 되는 배율로",
              upscale._scale_for("realesrgan-x4plus", 2) == 4)
    finally:
        os.environ.pop("REALESRGAN_PATH", None)


def test_engine_switch_and_doctor():
    section("엔진 바꾸기 · 점검 화면")
    import ui.server as srv
    from pipeline.doctor import FAIL, check_local

    cfg_copy = TMP / "config.switch.yaml"
    shutil.copyfile(ROOT / "config.yaml", cfg_copy)
    real_cfg = srv.CONFIG
    srv.CONFIG = cfg_copy
    old_env = os.environ.get("LTX_DIR")
    try:
        os.environ["LTX_DIR"] = str(TMP / "not_installed")
        ok, msg = srv.switch_engine("local")
        check("설치 전에는 안 바꾼다", not ok and "ltx_setup" in msg, msg.splitlines()[0])
        check("config 는 그대로", "provider: fal" in cfg_copy.read_text("utf-8"))

        os.environ["LTX_DIR"] = str(make_fake_ltx(TMP / "ltx_switch"))
        ok, msg = srv.switch_engine("local")
        text = cfg_copy.read_text("utf-8")
        check("설치돼 있으면 바꾼다", ok, msg)
        check("provider/model 이 바뀐다",
              "\nprovider: local" in text and "\nmodel: ltx_25_distilled" in text)
        check("주석은 남는다", "# providers 섹션의 키" in text)
        st = srv.engine_state(quick=True)
        check("엔진 상태가 내 PC · 준비됨", st["provider"] == "local" and st["ready"])

        checks = check_local({"ltx_dir": os.environ["LTX_DIR"]})
        fails = [c.name for c in checks if c.status == FAIL]
        check("점검: 설치·모델 파일은 통과", not any("LTX" in n or "VAE" in n for n in fails),
              str(fails))

        ok, _ = srv.switch_engine("fal")
        check("클라우드로 되돌린다", ok and "\nprovider: fal" in cfg_copy.read_text("utf-8"))
        check("모르는 엔진은 거절", not srv.switch_engine("gpu9000")[0])
    finally:
        srv.CONFIG = real_cfg
        if old_env is None:
            os.environ.pop("LTX_DIR", None)
        else:
            os.environ["LTX_DIR"] = old_env

    html = (ROOT / "ui" / "app.html").read_text(encoding="utf-8")
    check("화면에 엔진 고르기", 'name="eng" value="local"' in html)
    check("실패 이유를 버리지 않는다 (message)", "data.error || data.message" in html)


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
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
