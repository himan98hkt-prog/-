"""파이프라인 설정값 정의와 ``.env`` 로딩."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

__all__ = ["Settings", "SubtitleStyle", "load_dotenv", "REFRAME_MODES"]

REFRAME_MODES = ("blur", "crop")
ReframeMode = Literal["blur", "crop"]


def load_dotenv(path: str | Path = ".env", *, override: bool = False) -> dict[str, str]:
    """의존성 없이 ``KEY=VALUE`` 형식의 .env 를 읽어 환경변수에 반영한다.

    ``python-dotenv`` 가 설치돼 있으면 그쪽을 우선 사용한다.
    """
    path = Path(path)
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded
    try:  # 선택적 의존성
        from dotenv import dotenv_values  # type: ignore

        parsed = {k: v for k, v in dotenv_values(path).items() if v is not None}
    except Exception:
        parsed = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key:
                parsed[key] = value
    for key, value in parsed.items():
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


@dataclass
class SubtitleStyle:
    """ASS 자막 스타일. 쇼츠에서 잘 읽히는 굵은 폰트 기본값."""

    font_name: str = "NanumGothic Bold"
    font_size: int = 78
    primary_color: str = "&H00FFFFFF"       # 기본 글자색 (흰색, AABBGGRR)
    highlight_color: str = "&H0000E5FF"     # 현재 발화 단어 (노란색)
    outline_color: str = "&H00000000"       # 테두리 (검정)
    back_color: str = "&HA0000000"          # 그림자/배경 (반투명 검정)
    outline: float = 5.0
    shadow: float = 2.0
    bold: bool = True
    margin_v: int = 320                     # 하단 여백 (1920 기준, UI 겹침 회피)
    margin_h: int = 90
    alignment: int = 2                      # ASS 기준 하단 중앙
    max_chars_per_line: int = 14
    max_words_per_cue: int = 6
    max_cue_duration: float = 2.4
    highlight_active_word: bool = True
    uppercase: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class Settings:
    """CLI/UI 양쪽이 공유하는 실행 설정."""

    # 입출력
    source: str = ""
    work_dir: Path = Path("work")
    output_dir: Path = Path("output")

    # 전사 (Module B)
    whisper_model: str = "base"
    whisper_device: str = "auto"            # auto | cpu | cuda
    whisper_compute_type: str = "auto"      # auto | int8 | float16 ...
    language: str | None = None             # None 이면 자동 감지
    beam_size: int = 5
    vad_filter: bool = True

    # 하이라이트 분석 (Module C)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    min_clip_seconds: float = 30.0
    max_clip_seconds: float = 60.0
    min_clips: int = 3
    max_clips: int = 5
    allow_offline_fallback: bool = True     # API 키가 없으면 휴리스틱으로 대체

    # 렌더링 (Module D)
    reframe_mode: str = "blur"
    width: int = 1080
    height: int = 1920
    fps: int | None = None                  # None 이면 원본 유지
    blur_sigma: float = 22.0
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 20
    preset: str = "veryfast"
    audio_bitrate: str = "192k"
    burn_subtitles: bool = True
    lossless_cut: bool = False              # True 면 무손실 컷 후 2단계 렌더
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)

    # 실행 제어
    keep_intermediate: bool = True
    overwrite: bool = False
    cookies_from_browser: str | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        self.work_dir = Path(self.work_dir)
        self.output_dir = Path(self.output_dir)
        if self.gemini_api_key is None:
            self.gemini_api_key = (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or None
            )
        if self.reframe_mode not in REFRAME_MODES:
            raise ValueError(
                f"reframe_mode 는 {REFRAME_MODES} 중 하나여야 합니다: {self.reframe_mode!r}"
            )
        if self.min_clip_seconds <= 0 or self.max_clip_seconds <= 0:
            raise ValueError("클립 길이는 0보다 커야 합니다.")
        if self.min_clip_seconds > self.max_clip_seconds:
            raise ValueError(
                f"min_clip_seconds({self.min_clip_seconds}) 가 "
                f"max_clip_seconds({self.max_clip_seconds}) 보다 큽니다."
            )
        if self.min_clips > self.max_clips:
            raise ValueError(
                f"min_clips({self.min_clips}) 가 max_clips({self.max_clips}) 보다 큽니다."
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width/height 는 양수여야 합니다.")

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    def clone(self, **overrides: Any) -> "Settings":
        """일부 값만 바꾼 사본. 호출자의 설정을 변형하지 않기 위해 쓴다."""
        values = {f.name: getattr(self, f.name) for f in fields(self)}
        values.update(overrides)
        return Settings(**values)

    def resolved(self, base: str | Path | None = None) -> "Settings":
        """작업/출력 디렉터리를 ``base`` 기준 절대 경로로 바꾼 사본."""
        base_path = Path(base or Path.cwd())
        clone = self.clone()
        clone.work_dir = (base_path / self.work_dir).resolve() if not self.work_dir.is_absolute() else self.work_dir
        clone.output_dir = (base_path / self.output_dir).resolve() if not self.output_dir.is_absolute() else self.output_dir
        return clone

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, Path):
                value = str(value)
            elif isinstance(value, SubtitleStyle):
                value = value.to_dict()
            data[f.name] = value
        # 키 값 자체는 기록하지 않는다.
        data["gemini_api_key"] = "***" if self.gemini_api_key else None
        return data
