"""설정. 모델 문자열은 여기서만 읽는다(CLAUDE.md 절대 규칙 12)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


def read_api_key_from_env_file(path: Path | None = None) -> str:
    """ANTHROPIC_API_KEY 는 **프로젝트 .env 파일에서만** 읽는다.

    시스템 환경변수는 쓰지 않는다(원장 지시). 셸에 키가 떠 있으면 다른 프로세스·로그·
    자식 프로세스로 새기 쉽고, 어느 키로 돌았는지도 추적이 안 된다. 파일 하나로 못박아
    두면 `.env` 가 gitignore 되는 한 유출 경로가 하나로 줄어든다.
    """
    f = path or ENV_FILE
    if not f.exists():
        return ""
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == "ANTHROPIC_API_KEY":
            return value.strip().strip("\"'")
    return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # 이 필드는 __init__ 에서 .env 파일 값으로 덮어쓴다. 환경변수를 신뢰하지 않는다.
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

    def __init__(self, **data: object) -> None:
        super().__init__(**data)  # type: ignore[arg-type]
        # 환경변수에서 온 값이 있어도 버리고 .env 파일 값만 쓴다(원장 지시).
        # 테스트가 명시적으로 넘긴 값은 존중한다.
        if "anthropic_api_key" not in data:
            object.__setattr__(self, "anthropic_api_key", read_api_key_from_env_file())

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
