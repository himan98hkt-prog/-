"""config.yaml 로드 · 검증 · CLI 오버라이드 병합."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """설정이 잘못됐을 때. 메시지는 사용자에게 그대로 보여준다."""


@dataclass
class ModelSpec:
    """provider 안의 모델 하나. 단가와 능력치를 함께 들고 다닌다."""

    key: str
    endpoint: str
    max_duration: int
    supports_end_image: bool
    supports_negative: bool
    price_per_second: float | None = None
    price_per_clip: float | None = None
    credits_per_clip: float | None = None

    # ── 길이 제약 ────────────────────────────────────────────────────
    # 예전에는 상한만 봤다. 그런데 LTX 계열은 **6초부터 2초 단위**로만
    # 받는다. 상한만 검사하면 clip_duration: 5 가 그대로 통과해서, 돈이
    # 나가기 직전에 fal 이 422 로 거절한다. 접수 전 거절이라 과금은 없지만
    # 예약으로 새벽에 돌던 작업이 조용히 실패하고 그날 영상이 안 올라간다.
    # 그래서 설정을 읽는 시점에 막는다.
    min_duration: int = 1
    duration_step: int = 1

    # 길이를 어떤 파라미터로 표현하는가. 대부분 초 단위 `duration` 이지만
    # LTX 0.9.x 계열은 `num_frames` 로 받는다.
    duration_param: str = "duration"
    frames_per_second: int | None = None

    # 모델마다 고정으로 얹어야 하는 값 (해상도 등).
    extra_params: dict[str, Any] = field(default_factory=dict)

    # 모델이 소리를 함께 만들어 주는가. True 면 음악을 덧씌우지 않는다.
    has_native_audio: bool = False

    def cost_per_clip(self, duration: int, usd_per_credit: float) -> float:
        if self.price_per_second is not None:
            return self.price_per_second * duration
        if self.price_per_clip is not None:
            return self.price_per_clip
        if self.credits_per_clip is not None:
            return self.credits_per_clip * usd_per_credit
        raise ConfigError(
            f"모델 '{self.key}' 에 단가가 없습니다. "
            "price_per_second / price_per_clip / credits_per_clip 중 하나를 채우세요."
        )

    # ── 길이 ─────────────────────────────────────────────────────────
    def allowed_durations(self) -> list[int]:
        """이 모델이 받는 클립 길이 목록. 안내 메시지에 그대로 쓴다."""
        return list(range(self.min_duration, self.max_duration + 1,
                          max(1, self.duration_step)))

    def accepts_duration(self, duration: int) -> bool:
        if not self.min_duration <= duration <= self.max_duration:
            return False
        return (duration - self.min_duration) % max(1, self.duration_step) == 0

    def duration_payload(self, duration: int) -> dict[str, Any]:
        """길이를 이 모델이 받는 파라미터 형태로 만든다.

        `num_frames` 로 받는 모델은 프레임률을 곱해서 넘긴다. 프레임률이
        선언돼 있지 않으면 초 단위로 보낼 수밖에 없으므로 그렇게 둔다 —
        여기서 임의의 기본 프레임률을 지어내면 길이가 조용히 틀어진다.
        """
        if self.duration_param == "num_frames":
            if not self.frames_per_second:
                raise ConfigError(
                    f"모델 '{self.key}' 는 num_frames 로 길이를 받는데 "
                    "frames_per_second 가 없습니다. config 에 추가하세요."
                )
            return {"num_frames": int(duration * self.frames_per_second)}
        return {self.duration_param: duration}

    def request_extras(self, duration: int) -> dict[str, Any]:
        """provider 요청에 얹을 값 전부 (길이 + 모델 고정 파라미터)."""
        params = self.duration_payload(duration)
        params.update(self.extra_params)
        return params


@dataclass
class UpscalerSpec:
    key: str
    endpoint: str
    price_per_image: float | None = None
    credits_per_image: float | None = None

    def cost_per_image(self, usd_per_credit: float) -> float:
        if self.price_per_image is not None:
            return self.price_per_image
        if self.credits_per_image is not None:
            return self.credits_per_image * usd_per_credit
        return 0.0


@dataclass
class Config:
    raw: dict[str, Any]
    path: Path

    # 자주 쓰는 값은 속성으로 승격시켜 둔다.
    mode: str = "chain"
    provider: str = "fal"
    model_key: str = ""
    clip_duration: int = 5
    num_clips: int = 6
    motion_prompt: str = ""
    negative_prompt: str = ""
    scene_prompts: list[str] = field(default_factory=list)
    upscale_between_clips: bool = True
    upscaler_key: str = ""
    crossfade_seconds: float = 0.3
    montage_transition: str = "cut"
    montage_transition_seconds: float = 0.25
    loop_back: bool = False
    # 클립 하나를 최대 몇 초까지 기다릴지. 넘으면 **재제출하지 않고** 멈춘다.
    # 재제출하면 먼저 낸 작업 값까지 두 번 내게 된다.
    poll_timeout_seconds: float = 1800.0

    # ── 채널 ─────────────────────────────────────────────────────────
    # 한 설치에서 채널을 둘 이상 돌리기 위한 축이다. 예전에는 runs/ 와
    # 예약 이름이 하나뿐이라, 두 번째 채널의 예약을 켜는 순간 첫 채널의
    # 예약을 덮어썼고 산출물도 같은 폴더에 섞였다. 채널마다 slug 를 주고
    # 산출물·시드·예약을 그 아래로 가른다.
    channel_slug: str = "default"
    channel_name: str = ""
    runs_dir: str = "runs"
    seeds_dir: str = "seeds"
    # 예약이 이 시각에 게시한다 (HH:MM). 작업실 화면과 예약 등록의 기본값.
    publish_at: str = "21:00"

    # ── 파생값 ────────────────────────────────────────────────────────
    @property
    def output(self) -> dict[str, Any]:
        return self.raw["output"]

    @property
    def cost_cfg(self) -> dict[str, Any]:
        return self.raw["cost"]

    @property
    def preview_cfg(self) -> dict[str, Any]:
        """싸게 먼저 시험할 때 쓸 설정. 없으면 빈 dict — 그러면 본편 설정을 쓴다."""
        return self.raw.get("preview") or {}

    @property
    def publish_cfg(self) -> dict[str, Any]:
        return self.raw.get("publish", {})

    @property
    def provider_cfg(self) -> dict[str, Any]:
        try:
            return self.raw["providers"][self.provider]
        except KeyError as exc:
            known = ", ".join(self.raw.get("providers", {}))
            raise ConfigError(
                f"provider '{self.provider}' 를 config.yaml 에서 찾을 수 없습니다. "
                f"사용 가능: {known}"
            ) from exc

    @property
    def usd_per_credit(self) -> float:
        """크레딧 기반 provider 의 실효 단가. 초당 과금이면 0."""
        plan_key = self.provider_cfg.get("plan")
        if not plan_key:
            return 0.0
        plans = self.provider_cfg.get("plans", {})
        if plan_key not in plans:
            raise ConfigError(
                f"plan '{plan_key}' 이 providers.{self.provider}.plans 에 없습니다."
            )
        plan = plans[plan_key]
        credits = plan["credits_per_month"]
        if not credits:
            raise ConfigError(f"plan '{plan_key}' 의 credits_per_month 가 0 입니다.")
        return plan["usd_per_month"] / credits

    @property
    def model(self) -> ModelSpec:
        models = self.provider_cfg.get("models", {})
        if self.model_key not in models:
            known = ", ".join(models)
            raise ConfigError(
                f"모델 '{self.model_key}' 가 provider '{self.provider}' 에 없습니다. "
                f"사용 가능: {known}"
            )
        m = models[self.model_key]
        return ModelSpec(
            key=self.model_key,
            endpoint=m["endpoint"],
            max_duration=int(m.get("max_duration", 10)),
            supports_end_image=bool(m.get("supports_end_image", False)),
            supports_negative=bool(m.get("supports_negative", False)),
            price_per_second=m.get("price_per_second"),
            price_per_clip=m.get("price_per_clip"),
            credits_per_clip=m.get("credits_per_clip"),
            min_duration=int(m.get("min_duration", 1)),
            duration_step=int(m.get("duration_step", 1)),
            duration_param=m.get("duration_param", "duration"),
            frames_per_second=m.get("frames_per_second"),
            extra_params=dict(m.get("extra_params") or {}),
            has_native_audio=bool(m.get("has_native_audio", False)),
        )

    @property
    def upscaler(self) -> UpscalerSpec | None:
        if not self.upscale_between_clips:
            return None
        ups = self.provider_cfg.get("upscalers", {})
        # 엔진을 내 PC 로 바꿔도 upscaler: esrgan 은 그대로 남아 있다.
        # 그걸로 막히면 안 된다 — 내 PC 쪽 업스케일러로 대신한다.
        if self.provider == "local" and self.upscaler_key not in ups and ups:
            self.upscaler_key = next(iter(ups))
        if self.upscaler_key not in ups:
            known = ", ".join(ups) or "(없음)"
            raise ConfigError(
                f"업스케일러 '{self.upscaler_key}' 가 provider '{self.provider}' 에 "
                f"없습니다. 사용 가능: {known}. --no-upscale 로 끌 수 있습니다."
            )
        u = ups[self.upscaler_key]
        return UpscalerSpec(
            key=self.upscaler_key,
            endpoint=u["endpoint"],
            price_per_image=u.get("price_per_image"),
            credits_per_image=u.get("credits_per_image"),
        )


_REQUIRED_TOP_LEVEL = ("mode", "provider", "model", "clip_duration", "num_clips", "output")


def load_config(path: str | Path = "config.yaml", **overrides: Any) -> Config:
    """config.yaml 을 읽고 CLI 오버라이드를 얹어 Config 를 만든다.

    overrides 의 값이 None 이면 무시한다 (typer 의 미지정 옵션).
    """
    load_dotenv()
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"설정 파일이 없습니다: {path}\n"
            "저장소의 config.yaml 을 복사해 사용하세요."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing = [k for k in _REQUIRED_TOP_LEVEL if k not in raw]
    if missing:
        raise ConfigError(f"config.yaml 에 필수 항목이 없습니다: {', '.join(missing)}")

    raw = copy.deepcopy(raw)
    for key, value in overrides.items():
        if value is None:
            continue
        raw[key] = value

    # 내 PC 엔진(LTX) 설정은 없어도 된다. 업데이트가 config.yaml 을 덮어쓰지
    # 않으니 이 블록이 없는 사람이 대부분이다. 있으면 그 위에 얹는다.
    from .providers.ltx_local import settings_with_defaults

    providers = raw.setdefault("providers", {})
    providers["local"] = settings_with_defaults(providers.get("local"))

    cfg = Config(
        raw=raw,
        path=path,
        mode=raw["mode"],
        provider=raw["provider"],
        model_key=raw["model"],
        clip_duration=int(raw["clip_duration"]),
        num_clips=int(raw["num_clips"]),
        motion_prompt=(raw.get("motion_prompt") or "").strip(),
        negative_prompt=(raw.get("negative_prompt") or "").strip(),
        scene_prompts=list(raw.get("scene_prompts") or []),
        upscale_between_clips=bool(raw.get("upscale_between_clips", False)),
        upscaler_key=raw.get("upscaler", ""),
        crossfade_seconds=float(raw.get("crossfade_seconds", 0.3)),
        montage_transition=raw.get("montage_transition", "cut"),
        montage_transition_seconds=float(raw.get("montage_transition_seconds", 0.25)),
        loop_back=bool(raw.get("loop_back", False)),
        poll_timeout_seconds=float(raw.get("poll_timeout_seconds", 1800)),
        **_channel_fields(raw),
    )
    _validate(cfg)
    return cfg


# slug 는 폴더 이름과 윈도우 작업 이름에 그대로 들어간다. 경로를 벗어나거나
# 예약 이름을 깨뜨리는 문자가 섞이면 곤란하므로 좁게 받는다.
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}$")


def _channel_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """channel 블록을 읽는다. 없으면 예전 그대로 runs/ · seeds/ 를 쓴다.

    기본값을 'default' 로 두는 것이 중요하다. 이미 돌고 있는 채널의
    산출물 경로를 바꾸면 지난 영상과 이번 달 누적 비용을 잃는다.
    """
    ch = raw.get("channel") or {}
    if not isinstance(ch, dict):
        raise ConfigError("channel 은 이름·slug 를 담은 블록이어야 합니다.")

    # 키가 아예 없으면 예전 그대로 기본 채널이다. 하지만 **비워 둔 것**은
    # 다르다 — 그대로 'default' 로 떨어지면 두 번째 채널이 기본 채널의
    # runs/ 와 예약을 말없이 가로챈다. 적었는데 비었으면 틀린 것이다.
    slug = "default" if "slug" not in ch else str(ch.get("slug") or "").strip()
    if not _SLUG_RE.fullmatch(slug):
        raise ConfigError(
            f"channel.slug 가 잘못됐습니다: {slug!r}\n"
            "  영문 소문자·숫자로 시작하고 -, _ 만 쓸 수 있습니다 (최대 32자). 예: wonri"
        )

    return {
        "channel_slug": slug,
        "channel_name": str(ch.get("name") or "").strip(),
        # 채널을 지정하지 않으면 예전 경로 그대로다.
        "runs_dir": str(ch.get("runs_dir") or
                        ("runs" if slug == "default" else f"runs-{slug}")),
        "seeds_dir": str(ch.get("seeds_dir") or
                         ("seeds" if slug == "default" else f"seeds-{slug}")),
        "publish_at": str(ch.get("publish_at") or "21:00"),
    }


def _validate(cfg: Config) -> None:
    if cfg.mode not in ("chain", "montage"):
        raise ConfigError(f"mode 는 chain 또는 montage 여야 합니다 (현재: {cfg.mode})")
    if cfg.num_clips < 1:
        raise ConfigError("num_clips 는 1 이상이어야 합니다.")
    if cfg.clip_duration < 1:
        raise ConfigError("clip_duration 은 1 이상이어야 합니다.")

    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", cfg.publish_at):
        raise ConfigError(
            f"channel.publish_at 은 HH:MM 이어야 합니다 (현재: {cfg.publish_at!r}). 예: 09:00"
        )

    model = cfg.model  # 여기서 모델 존재 여부까지 검증된다
    if not model.accepts_duration(cfg.clip_duration):
        allowed = model.allowed_durations()
        # 목록이 길면 앞뒤만 보여준다. 1초 단위 모델은 20개가 넘는다.
        shown = (", ".join(str(d) for d in allowed) if len(allowed) <= 8
                 else f"{allowed[0]}, {allowed[1]}, … , {allowed[-1]}")
        raise ConfigError(
            f"clip_duration={cfg.clip_duration}초는 모델 '{model.key}' 가 받지 않습니다.\n"
            f"  이 모델이 받는 길이: {shown} (초)\n"
            f"  config.yaml 의 clip_duration 을 고치세요."
        )
    if cfg.loop_back and not model.supports_end_image:
        raise ConfigError(
            f"loop_back 은 end_image 를 지원하는 모델에서만 됩니다. "
            f"'{model.key}' 는 지원하지 않습니다. "
            "kling_30_pro / hailuo_23_pro / veo_31_fast / minimax_h3 등을 쓰세요."
        )
    cfg.upscaler  # 업스케일러 존재 여부 검증
    if cfg.crossfade_seconds >= cfg.clip_duration:
        raise ConfigError(
            f"crossfade_seconds({cfg.crossfade_seconds})가 "
            f"clip_duration({cfg.clip_duration})보다 짧아야 합니다."
        )
    if cfg.poll_timeout_seconds < 60:
        raise ConfigError(
            "poll_timeout_seconds 는 60 이상이어야 합니다. 짧게 잡으면 "
            "아직 만들어지는 중인(그리고 이미 과금된) 작업을 포기하게 됩니다."
        )
    _validate_fps(cfg)


def _validate_fps(cfg: Config) -> None:
    """fps 는 숫자이거나 'auto' 다.

    'auto' 는 모델이 준 클립의 프레임률을 그대로 쓴다는 뜻이다. 왜 이게
    기본인지는 stitcher 쪽에 적어 뒀다 — 25fps 소스를 30 으로 올리면
    5프레임마다 한 장이 복제돼 눈에 보이는 떨림이 생긴다.
    """
    fps = cfg.output.get("fps", "auto")
    if isinstance(fps, str) and fps.strip().lower() == "auto":
        return
    try:
        value = int(fps)
    except (TypeError, ValueError):
        raise ConfigError(
            f"output.fps 는 숫자이거나 auto 여야 합니다 (현재: {fps!r})"
        ) from None
    if not 1 <= value <= 120:
        raise ConfigError(f"output.fps 는 1~120 사이여야 합니다 (현재: {value})")


def require_env(*names: str) -> dict[str, str]:
    """필요한 환경변수를 한 번에 확인하고, 없으면 안내 메시지와 함께 죽는다."""
    load_dotenv()
    found, missing = {}, []
    for n in names:
        v = os.getenv(n)
        if v:
            found[n] = v
        else:
            missing.append(n)
    if missing:
        raise ConfigError(
            "환경변수가 설정되지 않았습니다: " + ", ".join(missing) + "\n"
            ".env.example 을 .env 로 복사한 뒤 값을 채우세요."
        )
    return found
