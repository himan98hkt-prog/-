"""설정. 모델 문자열은 여기서만 읽는다(CLAUDE.md 절대 규칙 12)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env"), extra="ignore")

    anthropic_api_key: str = ""
    composer_model: str = "claude-opus-5"
    writer_model: str = "claude-sonnet-5"
    max_cost_per_composition: float = 2.50
    model_validation: Literal["strict", "warn", "off"] = "warn"

    database_url: str = "postgresql+psycopg://concours:concours@localhost:5432/concours"
    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = ROOT / "data"

    mscore_bin: str = "mscore"
    audiveris_bin: str = "audiveris"
    ffmpeg_bin: str = "ffmpeg"
    fluidsynth_bin: str = "fluidsynth"
    soundfont_path: str = ""

    # 비평 루프
    quality_threshold: float = Field(default=7.0, ge=0, le=10)
    max_revision_rounds: int = Field(default=2, ge=0, le=4)

    @property
    def has_api_key(self) -> bool:
        return self.anthropic_api_key.startswith("sk-ant-") and len(self.anthropic_api_key) > 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ── 시작 시 모델 문자열 유효성 검사 ──────────────────────────────────────────

# SDK 가 아는 모델 목록을 조회할 수 없는 환경(오프라인)에서도 동작해야 하므로,
# 형태 검사 → (가능하면) API 목록 대조 순으로 낮춰가며 확인한다.
_KNOWN_PREFIXES = ("claude-opus-", "claude-sonnet-", "claude-haiku-", "claude-fable-")


class ModelValidationError(RuntimeError):
    pass


def validate_models(settings: Settings | None = None) -> list[str]:
    """문제를 문자열 목록으로 돌려준다. strict 모드면 예외를 던진다."""
    s = settings or get_settings()
    problems: list[str] = []

    for label, name in (("COMPOSER_MODEL", s.composer_model), ("WRITER_MODEL", s.writer_model)):
        if not name:
            problems.append(f"{label} 이 비어 있다")
            continue
        if not name.startswith(_KNOWN_PREFIXES):
            problems.append(f"{label}={name!r} 이 알려진 모델 접두어가 아니다 ({', '.join(_KNOWN_PREFIXES)})")

    if s.has_api_key and not problems:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=s.anthropic_api_key)
            available = {m.id for m in client.models.list(limit=100).data}
            for label, name in (("COMPOSER_MODEL", s.composer_model), ("WRITER_MODEL", s.writer_model)):
                if name not in available and not any(a.startswith(name) for a in available):
                    problems.append(
                        f"{label}={name!r} 이 계정에서 사용 가능한 모델 목록에 없다. "
                        "docs.claude.com 모델 페이지에서 최신 문자열을 확인하라."
                    )
        except Exception as e:  # 네트워크·권한 문제로 목록 조회 실패는 치명적이지 않다
            problems.append(f"(참고) 모델 목록 조회를 건너뛴다: {type(e).__name__}")

    if s.model_validation == "strict":
        hard = [p for p in problems if not p.startswith("(참고)")]
        if hard:
            raise ModelValidationError("; ".join(hard))
    return problems


def resolve_data_dir() -> Path:
    d = Path(os.environ.get("DATA_DIR", get_settings().data_dir))
    d.mkdir(parents=True, exist_ok=True)
    return d
