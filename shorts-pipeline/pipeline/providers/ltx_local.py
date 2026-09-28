"""내 PC 그래픽카드로 LTX-2.5 를 돌려 클립을 만든다. 한 편에 $0.

Lightricks 가 공개한 LTX-2 저장소의 명령줄 도구를 그대로 부른다.

    python -m ltx_pipelines.distilled --image first.png 0 1.0 \\
        --width 576 --height 1024 --num-frames 241 --frame-rate 24 ...

**업스케일이 두 번 들어간다.**
  1) LTX 안에서. distilled 는 절반 크기(288x512)로 움직임을 잡은 뒤
     LTX 전용 공간 업스케일러로 2배(576x1024) 키워 다듬는다. `--width`
     `--height` 는 그 **최종** 크기다. (Lightricks 소스 distilled.py 에서
     `stage_1_w, stage_1_h = width // 2, height // 2` 로 확인)
  2) 클립이 나온 뒤 Real-ESRGAN 으로 한 번 더 (설치돼 있을 때만).
     그 다음 합성 단계에서 1080x1920 으로 맞춘다.

**정직하게 적어 둘 한계.** 모델 전체를 그래픽카드에 올리려면 VRAM 이
28GB 넘게 든다. 그보다 작은 카드는 모델을 시스템 메모리에 두고 조금씩
흘려보내며 돌린다(오프로드) — 돌기는 하지만 느리고, 시스템 메모리가
40GB 이상 있어야 한다. 그래서 두 메모리를 보고 설정을 자동으로 고른다(auto).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from .base import (
    HEARTBEAT_SECONDS,
    GenerationRequest,
    GenerationResult,
    ProviderError,
    VideoProvider,
)

# config.yaml 에 providers.local 이 없을 때 쓰는 기본값.
# 업데이트는 사용자의 config.yaml 을 덮어쓰지 않으므로, 이 블록이 없는 사람이
# 대부분이다. 그래도 [내 PC 로 만들기] 를 누르면 바로 돌아야 한다.
DEFAULTS: dict[str, Any] = {
    "ltx_dir": "",                     # 비우면 .env 의 LTX_DIR, 그것도 없으면 C:\LTX-2
    "python": "",                      # 비우면 ltx_dir\.venv 의 파이썬
    "models_dir": "models/ltx-2.5",    # ltx_dir 기준
    "width": 576,                      # 최종 크기. 64 의 배수
    "height": 1024,
    "fps": 24,
    "quantization": "auto",            # auto | none | fp8-cast
    "offload": "auto",                 # auto | none | cpu | disk
    "seed": 0,                         # 0 이면 매번 다르게
    "clip_timeout_minutes": 90,
    "upscale_clips": "auto",           # auto | realesrgan | off
    "realesrgan_model": "realesr-animevideov3",
    "realesrgan_scale": 2,
    "models": {
        "ltx_25_distilled": {
            "endpoint": "distilled",
            "price_per_clip": 0,
            "max_duration": 10,
            "supports_end_image": False,
            "supports_negative": False,
        },
        "ltx_25_dfr": {
            "endpoint": "dfr_pipeline",
            "price_per_clip": 0,
            "max_duration": 10,
            "supports_end_image": False,
            "supports_negative": False,
        },
    },
    "upscalers": {
        "local": {"endpoint": "realesrgan", "price_per_image": 0},
    },
}

DEFAULT_MODEL = "ltx_25_distilled"

# models_dir 안에서 찾는 파일. 영상 VAE 는 가벼운 conv 를 먼저 쓴다 —
# 기본 VAE(디퓨전 디코더)는 윈도우에서 빠른 경로(natten)를 못 써서 무겁다.
FILES = {
    "transformer": ["diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors"],
    "text_encoder": ["text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"],
    "video_vae": ["vae/ltx-2.5-video-vae-conv-bf16.safetensors",
                  "vae/ltx-2.5-video-vae-bf16.safetensors"],
    "audio_vae": ["vae/ltx-2.5-audio-vae-bf16.safetensors"],
    "spatial_upsampler": [
        "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"],
}
DFR_LORA = ["loras/ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors"]

FILE_LABEL = {
    "transformer": "LTX-2.5 본체 (distilled)",
    "text_encoder": "문장 이해 모델 (Gemma)",
    "video_vae": "영상 VAE",
    "audio_vae": "소리 VAE",
    "spatial_upsampler": "LTX 업스케일러 (2배)",
}

_OOM = re.compile(r"out of memory|OutOfMemoryError|CUBLAS_STATUS_ALLOC_FAILED", re.I)
_NO_MODULE = re.compile(r"No module named ['\"]?ltx_", re.I)


def settings_with_defaults(cfg: dict | None) -> dict:
    """사용자 설정 위에 기본값을 깐다. 모델·업스케일러 표는 합친다."""
    import copy

    out = copy.deepcopy(DEFAULTS)
    for key, value in (cfg or {}).items():
        if key in ("models", "upscalers") and isinstance(value, dict):
            out[key].update(value)
        elif value not in (None, ""):
            out[key] = value
    return out


def ltx_dir(settings: dict) -> Path:
    raw = (settings.get("ltx_dir") or os.getenv("LTX_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(r"C:\LTX-2") if os.name == "nt" else Path.home() / "LTX-2"


def python_path(settings: dict) -> Path:
    raw = (settings.get("python") or os.getenv("LTX_PYTHON") or "").strip()
    if raw:
        return Path(raw).expanduser()
    base = ltx_dir(settings) / ".venv"
    return base / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def models_dir(settings: dict) -> Path:
    p = Path(settings.get("models_dir") or DEFAULTS["models_dir"])
    return p if p.is_absolute() else ltx_dir(settings) / p


def find_files(settings: dict, *, dfr: bool = False) -> tuple[dict[str, Path], list[str]]:
    """필요한 모델 파일. (찾은 것, 없는 것의 이름)"""
    root = models_dir(settings)
    found, missing = {}, []
    wanted = dict(FILES)
    if dfr:
        wanted["detailing_lora"] = DFR_LORA
    for key, candidates in wanted.items():
        hit = next((root / c for c in candidates if (root / c).exists()), None)
        if hit:
            found[key] = hit
        else:
            missing.append(candidates[0])
    return found, missing


def gpu_memory_mb() -> int | None:
    """첫 번째 NVIDIA 그래픽카드의 메모리(MB). 못 읽으면 None."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=memory.total",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"\d+", out.stdout or "")
    return int(m.group(0)) if m else None


def system_ram_gb() -> float | None:
    """PC 의 전체 메모리(GB). 못 읽으면 None."""
    try:
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MemoryStatus()
            st.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullTotalPhys / 1024 ** 3
            return None
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 ** 2
    except (OSError, ValueError, AttributeError):
        return None
    return None


# Lightricks 문서(ltx_pipelines/utils/types.py OffloadMode) 의 수치:
#   none : 모델 전체를 그래픽카드에   (~28GB VRAM)
#   cpu  : 시스템 메모리에 두고 흘려보냄 (~36GB RAM + ~5GB VRAM)
#   disk : 디스크에서 그때그때 읽음    (~5GB RAM + ~5GB VRAM, 매우 느림)
RAM_FOR_CPU_OFFLOAD_GB = 40

# 이보다 작은 그래픽카드에서는 내 PC 생성을 막는다.
#
# Lightricks 가 직접 만든 LTX Desktop 이 쓰는 경계와 같다(runtime_policy.py:
# `if vram_gb < 15: return "unsupported"`, README: 16GB 미만은 API 전용).
# 그 앱은 조각조각 흘려보내는 최적화까지 들어 있는데도 이 아래에서는
# 클라우드로 돌린다. 여기서 억지로 돌리면 디스크까지 써서 한 클립에 몇 시간이
# 걸리거나 도중에 죽는다 — 매일 아침 예약이 매일 실패한다.
MIN_VRAM_GB = 15


def memory_plan(vram_mb: int | None, ram_gb: float | None = None) -> tuple[str, str, str]:
    """그래픽카드·시스템 메모리 -> (quantization, offload, 설명)."""
    if vram_mb is None:
        return "fp8-cast", "cpu", "그래픽카드 메모리를 못 읽어 안전하게 잡았습니다"
    gb = vram_mb / 1024
    if gb >= 44:
        return "none", "none", f"{gb:.0f}GB — 제한 없이 돕니다"
    if gb >= 30:
        return "fp8-cast", "none", f"{gb:.0f}GB — fp8 로 돕니다"
    ram_note = f", 시스템 메모리 {ram_gb:.0f}GB" if ram_gb else ""
    if gb < MIN_VRAM_GB:
        return "fp8-cast", "disk", (
            f"{gb:.0f}GB — 내 PC 생성에는 {MIN_VRAM_GB}GB 이상이 필요합니다. "
            "Lightricks 의 LTX Desktop 도 이 크기에서는 클라우드로 만듭니다")
    if ram_gb is None or ram_gb >= RAM_FOR_CPU_OFFLOAD_GB:
        return "fp8-cast", "cpu", (f"{gb:.0f}GB{ram_note} — 모델을 시스템 메모리에 두고 "
                                   "나눠 돕니다 (느림)")
    return "fp8-cast", "disk", (f"{gb:.0f}GB{ram_note} — 시스템 메모리가 모자라 디스크까지 "
                                "씁니다 (매우 느림). 메모리 64GB 를 권장합니다")


def vram_ok(vram_mb: int | None) -> bool:
    """내 PC 생성이 되는 그래픽카드인가. 못 읽으면 막지 않는다(점검에서 따로 알린다)."""
    return vram_mb is None or vram_mb / 1024 >= MIN_VRAM_GB


def num_frames(seconds: float, fps: float) -> int:
    """LTX 는 8k+1 프레임만 받는다. 10초 24fps -> 241."""
    k = max(1, round(seconds * fps / 8))
    return 8 * k + 1


def check_size(width: int, height: int) -> None:
    if width % 64 or height % 64:
        raise ProviderError(
            f"LTX 크기는 64 의 배수여야 합니다 (지금 {width}x{height}). "
            "세로 영상이면 576x1024, 704x1280, 1088x1920 중에서 고르세요.",
            retryable=False, billed=False)


class LocalLTXProvider(VideoProvider):
    """ltx_pipelines 명령줄을 자식 프로세스로 돌린다."""

    name = "local"

    def __init__(self, endpoint: str, *, settings: dict | None = None, **kwargs):
        kwargs.pop("base_url", None)
        super().__init__(endpoint or DEFAULTS["models"][DEFAULT_MODEL]["endpoint"], **kwargs)
        self.settings = settings_with_defaults(settings)
        minutes = float(self.settings.get("clip_timeout_minutes") or 90)
        self.timeout = max(self.timeout, minutes * 60)

    # ── 명령 만들기 ──────────────────────────────────────────────────
    def command(self, req: GenerationRequest, out: Path) -> list[str]:
        s = self.settings
        dfr = self.endpoint.startswith("dfr")
        files, missing = find_files(s, dfr=dfr)
        if missing:
            raise ProviderError(
                "LTX-2.5 모델 파일이 없습니다:\n  " + "\n  ".join(missing) +
                f"\n  찾은 곳: {models_dir(s)}\n  tools 폴더의 ltx_setup.bat 을 더블클릭하면 받습니다.",
                retryable=False, billed=False)
        py = python_path(s)
        if not py.exists():
            raise ProviderError(
                f"LTX 용 파이썬이 없습니다: {py}\n"
                "  tools 폴더의 ltx_setup.bat 을 먼저 더블클릭하세요.",
                retryable=False, billed=False)

        width, height = int(s["width"]), int(s["height"])
        check_size(width, height)
        fps = float(s["fps"])

        quant, offload = str(s["quantization"]), str(s["offload"])
        if "auto" in (quant, offload):
            q, o, _ = memory_plan(gpu_memory_mb(), system_ram_gb())
            quant = q if quant == "auto" else quant
            offload = o if offload == "auto" else offload

        seed = int(s.get("seed") or 0) or int(time.time()) % 2_000_000_000

        cmd = [str(py), "-m", f"ltx_pipelines.{self.endpoint}",
               "--transformer-path", str(files["transformer"]),
               "--text-encoder-path", str(files["text_encoder"]),
               "--video-vae-path", str(files["video_vae"]),
               "--audio-vae-path", str(files["audio_vae"]),
               "--spatial-upsampler-path", str(files["spatial_upsampler"])]
        if dfr:
            cmd += ["--detailing-lora", str(files["detailing_lora"])]
        # 이어지는 영상의 핵심: 앞 클립의 마지막 프레임을 0번 프레임에 고정한다
        cmd += ["--image", str(req.image), "0", "1.0",
                "--width", str(width), "--height", str(height),
                "--num-frames", str(num_frames(req.duration, fps))]
        if not dfr:                       # DFR 은 프레임률을 스스로 정한다(24)
            cmd += ["--frame-rate", f"{fps:g}"]
        cmd += ["--seed", str(seed), "--prompt", req.prompt, "--output-path", str(out)]
        if quant not in ("none", ""):
            cmd += ["--quantization", quant]
        if offload not in ("none", ""):
            cmd += ["--offload", offload]
        return cmd

    # ── 생성 ─────────────────────────────────────────────────────────
    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.stem + "_ltx.mp4")
        tmp.unlink(missing_ok=True)
        cmd = self.command(req, tmp)
        self.log("ltx.submit", endpoint=self.endpoint, image=str(req.image),
                 frames=cmd[cmd.index("--num-frames") + 1])

        started = time.time()
        tail = self._run(cmd, cwd=ltx_dir(self.settings), label=dest.stem)
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise ProviderError("LTX 가 끝났지만 영상 파일이 없습니다.\n  " +
                                "\n  ".join(tail[-8:]), retryable=False, billed=False)

        self._maybe_upscale(tmp)
        os.replace(tmp, dest)
        elapsed = time.time() - started
        self.log("ltx.done", path=str(dest), seconds=round(elapsed, 1))
        return GenerationResult(video_path=dest, job_id=f"local-{int(started)}",
                                raw_response={"command": cmd[:3]},
                                elapsed_seconds=elapsed)

    def _run(self, cmd: list[str], *, cwd: Path, label: str) -> list[str]:
        """자식 프로세스를 돌리며 30초마다 살아 있음을 찍는다. 끝의 40줄을 돌려준다."""
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd) if cwd.exists() else None, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=0x08000000 if os.name == "nt" else 0)
        except OSError as exc:
            raise ProviderError(f"LTX 를 실행하지 못했습니다: {exc}",
                                retryable=False, billed=False) from exc

        tail: deque[str] = deque(maxlen=40)

        def pump():
            for chunk in proc.stdout:              # tqdm 은 \r 로 줄을 덮어쓴다
                for piece in chunk.replace("\r", "\n").splitlines():
                    if piece.strip():
                        tail.append(piece.strip())

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()

        started = time.time()
        next_beat = HEARTBEAT_SECONDS
        while proc.poll() is None:
            elapsed = time.time() - started
            if elapsed > self.timeout:
                proc.kill()
                raise ProviderError(
                    f"{label} 이(가) {self.timeout / 60:.0f}분 안에 끝나지 않아 멈췄습니다.\n"
                    "  config.yaml 의 providers.local.clip_timeout_minutes 를 늘리거나 "
                    "width/height 를 줄이세요.", retryable=False, billed=False)
            if elapsed >= next_beat:
                last = tail[-1][:90] if tail else ""
                print(f"      내 PC 에서 만드는 중… {int(elapsed // 60)}분 {int(elapsed % 60)}초"
                      + (f"  ({last})" if last else ""), flush=True)
                next_beat += HEARTBEAT_SECONDS
            time.sleep(1.0)
        reader.join(timeout=5)
        lines = list(tail)

        if proc.returncode != 0:
            text = "\n".join(lines)
            if _OOM.search(text):
                raise ProviderError(
                    "그래픽카드 메모리가 모자랍니다.\n"
                    "  config.yaml 의 providers.local 에서 width/height 를 576x1024 로 "
                    "줄이거나 offload: cpu 로 두세요.", retryable=False, billed=False)
            if _NO_MODULE.search(text):
                raise ProviderError(
                    "LTX 가 설치돼 있지 않습니다. tools 폴더의 ltx_setup.bat 을 더블클릭하세요.",
                    retryable=False, billed=False)
            raise ProviderError(
                f"LTX 가 오류로 끝났습니다 (코드 {proc.returncode}).\n  " +
                "\n  ".join(lines[-10:]), retryable=False, billed=False)
        return lines

    def _maybe_upscale(self, clip: Path) -> None:
        """Real-ESRGAN 이 있으면 클립을 한 번 더 키운다. 실패해도 원본으로 계속."""
        from pipeline import upscale

        mode = str(self.settings.get("upscale_clips", "auto")).lower()
        if mode == "off":
            return
        exe = upscale.find_realesrgan()
        if exe is None:
            if mode == "realesrgan":
                print("    ⚠ Real-ESRGAN 을 못 찾아 LTX 업스케일까지만 합니다.")
            return
        try:
            upscale.upscale_video(
                clip, clip, exe=exe,
                model=str(self.settings.get("realesrgan_model")),
                scale=int(self.settings.get("realesrgan_scale") or 2))
            self.log("ltx.upscaled", path=str(clip))
        except Exception as exc:                    # noqa: BLE001 — 품질 보정일 뿐
            self.log("ltx.upscale_failed", error=str(exc))
            print(f"    ⚠ Real-ESRGAN 실패, LTX 결과로 계속합니다 ({exc})")

    # ── 클립 사이 프레임 ─────────────────────────────────────────────
    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        """다음 클립의 첫 프레임을 다듬는다. Real-ESRGAN 이 없으면 그대로 넘긴다."""
        from pipeline import upscale

        exe = upscale.find_realesrgan()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if exe is None:
            shutil.copyfile(image, dest)
            return dest
        try:
            upscale.upscale_image(image, dest, exe=exe,
                                  model=str(self.settings.get("realesrgan_model")),
                                  scale=int(self.settings.get("realesrgan_scale") or 2))
        except Exception as exc:                    # noqa: BLE001
            raise ProviderError(f"프레임 업스케일 실패: {exc}",
                                retryable=False, billed=False) from exc
        return dest


def status(settings: dict | None = None) -> dict:
    """작업실·점검 화면용. 무엇이 준비됐고 무엇이 남았나."""
    s = settings_with_defaults(settings)
    root = ltx_dir(s)
    py = python_path(s)
    _, missing = find_files(s)
    vram = gpu_memory_mb()
    ram = system_ram_gb()
    quant, offload, note = memory_plan(vram, ram)
    from pipeline import upscale

    esr = upscale.find_realesrgan()
    return {
        "ltx_dir": str(root), "ltx_dir_ok": root.is_dir(),
        "python": str(py), "python_ok": py.exists(),
        "models_dir": str(models_dir(s)), "missing": missing,
        "vram_mb": vram, "ram_gb": round(ram, 1) if ram else None,
        "plan": {"quantization": quant, "offload": offload, "note": note},
        "realesrgan": str(esr) if esr else "",
        "size": f"{s['width']}x{s['height']}",
        "ready": root.is_dir() and py.exists() and not missing,
        "vram_ok": vram_ok(vram),
        "min_vram_gb": MIN_VRAM_GB,
        "sys_python": sys.executable,
    }
