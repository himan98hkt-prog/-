"""8GB 그래픽카드에서도 도는 내 PC 엔진 — LTX-Video 0.9.8 (2B distilled).

**왜 따로 있나.** 같은 폴더의 `ltx_local.py` 는 LTX-2.5(22B)를 돌린다. 그건
그래픽카드 메모리가 15GB 이상이어야 하고(전체 적재는 28GB), Lightricks 의
LTX Desktop 도 그 아래는 '지원 안 함' 으로 보고 클라우드 API 로 보낸다.
8GB 카드에서는 어떤 설정을 해도 돌지 않는다.

그래서 **한 세대 앞 모델**을 쓴다. LTX-Video 0.9.8 의 2B distilled 는
Lightricks 가 README 에서 *"Smaller model … ideal for fast generation with
light VRAM usage"* 라고 적은 경량판이다. fp8 판을 쓰면 더 가볍다.

    python inference.py --pipeline_config configs/ltxv-2b-0.9.8-distilled-fp8.yaml \\
        --prompt "..." --conditioning_media_paths first.png \\
        --conditioning_start_frames 0 \\
        --width 544 --height 960 --num_frames 193 --frame_rate 24 \\
        --seed 0 --output_path <폴더>

**LTX-2.5 와 다른 점 셋.** 여기서 틀리면 실행 시점에 깨진다.

  1. 인자 이름이 밑줄이다 (`--num_frames`, `--frame_rate`, `--output_path`).
     HfArgumentParser 가 dataclass 필드 이름을 그대로 쓴다.
  2. `--output_path` 는 **파일이 아니라 폴더**다. 파일 이름은 프롬프트·시드·
     해상도를 조합해 저장 쪽에서 짓는다. 그래서 빈 폴더를 주고 거기 생긴
     mp4 를 찾아 옮긴다.
  3. 크기는 **32 의 배수**이고(2.5 는 64), 720x1280 아래가 권장이다.
     프레임 수는 8k+1 이며 257 미만이 권장이다 — 24fps 로 약 10.6초가 상한.

**8GB 에서 무엇을 조일 수 있나.** 메모리는 해상도와 프레임 수에 같이 붙는다.
기본값 544x960 · 193프레임(8초)이 8GB 를 겨냥한 값이다. 그래도 모자라면
`width`/`height` 를 480x864 로, `num_frames` 를 줄이도록 `clip_duration` 을
6초로 내린다. 둘 다 config 에서 바꾼다.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from .base import GenerationRequest, GenerationResult, ProviderError
from .ltx_local import (
    LocalLTXProvider,
    gpu_memory_mb,
    num_frames,
    system_ram_gb,
)

# 8GB 를 겨냥한 값. 근거는 모듈 설명 참고.
DEFAULTS: dict[str, Any] = {
    "ltx_dir": "",                    # 비우면 .env 의 LTX09_DIR, 그것도 없으면 C:\LTX-Video
    "python": "",                     # 비우면 ltx_dir\.venv 의 파이썬
    # 어느 설정으로 돌릴지. 저장소의 configs/ 안에 들어 있다.
    "pipeline_config": "configs/ltxv-2b-0.9.8-distilled-fp8.yaml",
    "width": 544,                     # 32 의 배수. 544/960 은 9:16 에 가장 가까운 조합
    "height": 960,
    "fps": 24,
    # 그래픽카드가 작으면 켠다. 0.9.x 는 30GB 미만이면 스스로도 켜지만,
    # 명시해 두는 편이 낫다 — 꺼진 채로 8GB 에서 돌면 첫 클립에서 OOM 이다.
    "offload_to_cpu": "auto",         # auto | true | false
    "seed": 0,                        # 0 이면 매번 다르게
    "clip_timeout_minutes": 90,
    "upscale_clips": "auto",          # auto | realesrgan | off
    "realesrgan_model": "realesr-animevideov3",
    "realesrgan_scale": 2,
    "models": {
        "ltx09_2b_distilled": {
            "endpoint": "configs/ltxv-2b-0.9.8-distilled-fp8.yaml",
            "price_per_clip": 0,
            "max_duration": 10,
            "supports_end_image": False,
            # 2.5 와 달리 네거티브 프롬프트를 받는다 (inference.py 의 필드)
            "supports_negative": True,
        },
        "ltx09_13b_distilled": {      # 12GB 이상에서. 8GB 에서는 쓰지 말 것
            "endpoint": "configs/ltxv-13b-0.9.8-distilled-fp8.yaml",
            "price_per_clip": 0,
            "max_duration": 10,
            "supports_end_image": False,
            "supports_negative": True,
        },
    },
    "upscalers": {"local": {"endpoint": "realesrgan", "price_per_image": 0}},
}

# 이 아래로는 2B fp8 도 버겁다. 6GB 는 되는 카드도 있어 경고만 한다.
MIN_VRAM_GB = 6
COMFORTABLE_VRAM_GB = 8

# 권장 상한 (README: "works best on resolutions under 720 x 1280 and
# number of frames below 257"). 넘으면 막지 않고 알린다 — 카드가 크면 된다.
SOFT_MAX_W, SOFT_MAX_H = 720, 1280
SOFT_MAX_FRAMES = 257

_VIDEO_EXT = {".mp4", ".webm", ".mov"}


def settings_with_defaults(cfg: dict | None) -> dict:
    import copy

    out = copy.deepcopy(DEFAULTS)
    for key, value in (cfg or {}).items():
        if key in ("models", "upscalers") and isinstance(value, dict):
            out[key].update(value)
        elif value not in (None, ""):
            out[key] = value
    return out


def ltx_dir(settings: dict) -> Path:
    raw = (settings.get("ltx_dir") or os.getenv("LTX09_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(r"C:\LTX-Video") if os.name == "nt" else Path.home() / "LTX-Video"


def python_path(settings: dict) -> Path:
    raw = (settings.get("python") or os.getenv("LTX09_PYTHON") or "").strip()
    if raw:
        return Path(raw).expanduser()
    base = ltx_dir(settings) / ".venv"
    return base / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_size(width: int, height: int) -> None:
    """0.9.x 는 32 의 배수. 2.5 의 64 와 다르다."""
    if width % 32 or height % 32:
        raise ProviderError(
            f"LTX-Video 0.9.x 크기는 32 의 배수여야 합니다 (지금 {width}x{height}).\n"
            "  세로 영상이면 480x864 · 544x960 · 608x1088 중에서 고르세요.",
            retryable=False, billed=False)


def size_note(width: int, height: int, frames: int) -> str:
    """권장 범위를 넘었을 때 사람에게 할 말. 넘어도 막지는 않는다."""
    bits = []
    if width > SOFT_MAX_W or height > SOFT_MAX_H:
        bits.append(f"{width}x{height} 는 권장 범위(720x1280 이하)를 넘습니다")
    if frames >= SOFT_MAX_FRAMES:
        bits.append(f"{frames}프레임은 권장 범위(257 미만)를 넘습니다")
    return " · ".join(bits)


def offload_wanted(settings: dict) -> bool:
    """CPU 오프로드를 켤 것인가. auto 면 그래픽카드 메모리를 보고 정한다."""
    raw = str(settings.get("offload_to_cpu", "auto")).strip().lower()
    if raw in ("true", "yes", "on", "1"):
        return True
    if raw in ("false", "no", "off", "0"):
        return False
    vram = gpu_memory_mb()
    # 못 읽으면 켠다. 켜서 느린 것이 꺼서 OOM 으로 죽는 것보다 낫다 —
    # 예약으로 도는 작업은 죽으면 그날 영상이 없다.
    return vram is None or vram / 1024 < 30


def memory_note(vram_mb: int | None, ram_gb: float | None = None) -> str:
    if vram_mb is None:
        return "NVIDIA 그래픽카드를 찾지 못했습니다"
    gb = vram_mb / 1024
    ram = f", 시스템 메모리 {ram_gb:.0f}GB" if ram_gb else ""
    if gb < MIN_VRAM_GB:
        return (f"{gb:.0f}GB{ram} — 2B 판도 버겁습니다. 클라우드(fal)를 쓰시는 편이 "
                "낫습니다")
    if gb < COMFORTABLE_VRAM_GB:
        return (f"{gb:.0f}GB{ram} — 됩니다. 480x864 · 6초로 줄여서 시작하세요")
    if gb < 12:
        return f"{gb:.0f}GB{ram} — 2B distilled 로 돕니다 (기본값 544x960 · 8초)"
    return f"{gb:.0f}GB{ram} — 여유가 있습니다. 13B distilled 도 써 볼 만합니다"


def vram_ok(vram_mb: int | None) -> bool:
    return vram_mb is None or vram_mb / 1024 >= MIN_VRAM_GB


class LTX09Provider(LocalLTXProvider):
    """LTX-Video 0.9.x 의 inference.py 를 자식 프로세스로 돌린다.

    하트비트·타임아웃·OOM 안내·Real-ESRGAN 업스케일은 LTX-2.5 판과 같아서
    그대로 물려받는다. 다른 것은 **명령을 만드는 법**과 **결과를 찾는 법**뿐이다.
    """

    name = "ltx09"

    def __init__(self, endpoint: str, *, settings: dict | None = None, **kwargs):
        kwargs.pop("base_url", None)
        # 부모의 __init__ 은 LTX-2.5 기본값을 깐다. 여기서 다시 덮는다.
        super().__init__(endpoint or DEFAULTS["models"]["ltx09_2b_distilled"]["endpoint"],
                         settings=None, **kwargs)
        self.settings = settings_with_defaults(settings)
        minutes = float(self.settings.get("clip_timeout_minutes") or 90)
        self.timeout = max(self.timeout, minutes * 60)

    # ── 명령 만들기 ──────────────────────────────────────────────────
    def command(self, req: GenerationRequest, out: Path) -> list[str]:
        """`out` 은 **결과를 받을 폴더**다. 0.9.x 는 파일 이름을 스스로 짓는다."""
        s = self.settings
        root = ltx_dir(s)
        script = root / "inference.py"
        if not script.exists():
            raise ProviderError(
                f"LTX-Video 가 없습니다: {script}\n"
                "  Lightricks/LTX-Video 를 받아 설치하세요 "
                "(docs/LOCAL_LTX_8GB.md 에 순서가 있습니다).",
                retryable=False, billed=False)
        py = python_path(s)
        if not py.exists():
            raise ProviderError(
                f"LTX 용 파이썬이 없습니다: {py}\n"
                "  docs/LOCAL_LTX_8GB.md 의 설치 순서를 먼저 밟으세요.",
                retryable=False, billed=False)

        cfg_rel = self.endpoint or str(s["pipeline_config"])
        if not (root / cfg_rel).exists():
            raise ProviderError(
                f"설정 파일이 없습니다: {root / cfg_rel}\n"
                "  받은 저장소의 configs/ 안에 있는 이름인지 확인하세요.",
                retryable=False, billed=False)

        width, height = int(s["width"]), int(s["height"])
        check_size(width, height)
        fps = float(s["fps"])
        frames = num_frames(req.duration, fps)      # 8k+1 — 2.5 와 같은 규칙
        note = size_note(width, height, frames)
        if note:
            print(f"    ⓘ {note}. 8GB 카드라면 줄이는 편이 안전합니다.", flush=True)

        seed = int(s.get("seed") or 0) or int(time.time()) % 2_000_000_000

        cmd = [str(py), str(script),
               "--pipeline_config", cfg_rel,
               "--prompt", req.prompt,
               "--conditioning_media_paths", str(req.image),
               "--conditioning_start_frames", "0",
               "--width", str(width), "--height", str(height),
               "--num_frames", str(frames),
               "--frame_rate", str(int(fps)),
               "--seed", str(seed),
               "--output_path", str(out)]
        if req.negative_prompt:
            cmd += ["--negative_prompt", req.negative_prompt]
        if offload_wanted(s):
            cmd += ["--offload_to_cpu", "true"]
        return cmd

    # ── 생성 ─────────────────────────────────────────────────────────
    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # 빈 폴더를 준다. 안에 뭐가 있으면 어느 것이 이번 결과인지 알 수 없다.
        outdir = dest.with_name(dest.stem + "_ltx09")
        if outdir.exists():
            shutil.rmtree(outdir, ignore_errors=True)
        outdir.mkdir(parents=True)

        cmd = self.command(req, outdir)
        self.log("ltx09.submit", config=self.endpoint, image=str(req.image),
                 frames=cmd[cmd.index("--num_frames") + 1])

        started = time.time()
        tail = self._run(cmd, cwd=ltx_dir(self.settings), label=dest.stem)

        made = sorted((p for p in outdir.rglob("*") if p.suffix.lower() in _VIDEO_EXT),
                      key=lambda p: p.stat().st_mtime)
        if not made:
            raise ProviderError(
                "LTX 가 끝났지만 영상 파일이 없습니다.\n  찾은 곳: "
                f"{outdir}\n  " + "\n  ".join(tail[-8:]),
                retryable=False, billed=False)
        clip = made[-1]

        self._maybe_upscale(clip)
        os.replace(clip, dest)
        shutil.rmtree(outdir, ignore_errors=True)

        elapsed = time.time() - started
        self.log("ltx09.done", path=str(dest), seconds=round(elapsed, 1))
        return GenerationResult(video_path=dest, job_id=f"ltx09-{int(started)}",
                                raw_response={"command": cmd[:3]},
                                elapsed_seconds=elapsed)


def status(settings: dict | None = None) -> dict:
    """작업실·점검 화면용. 무엇이 준비됐고 무엇이 남았나."""
    s = settings_with_defaults(settings)
    root = ltx_dir(s)
    py = python_path(s)
    script = root / "inference.py"
    cfg = root / (s.get("pipeline_config") or DEFAULTS["pipeline_config"])
    vram = gpu_memory_mb()
    ram = system_ram_gb()
    return {
        "ltx_dir": str(root),
        "ltx_dir_ok": script.exists(),
        "python": str(py),
        "python_ok": py.exists(),
        "config": str(cfg),
        "config_ok": cfg.exists(),
        "vram_mb": vram,
        "ram_gb": round(ram, 1) if ram else None,
        "vram_ok": vram_ok(vram),
        "min_vram_gb": MIN_VRAM_GB,
        "note": memory_note(vram, ram),
        "offload": offload_wanted(s),
        "width": int(s["width"]), "height": int(s["height"]), "fps": int(s["fps"]),
    }
