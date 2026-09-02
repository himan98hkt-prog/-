"""설정. 모델 문자열은 여기서만 읽는다(CLAUDE.md 절대 규칙 12)."""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

APP_NAME = "ConcoursComposer"


def user_data_dir() -> Path:
    r"""만든 곡이 사는 곳 — **프로그램 폴더 바깥**이다.

    처음에는 프로그램 폴더 안(`ROOT/data`)에 두었다. 그것이 원장의 곡을 통째로
    날렸다. 새 판을 받는 방법이 "ZIP 을 다시 받아 폴더를 지우고 새로 푼다" 이기
    때문이다 — 폴더를 지우는 순간 만든 곡도 함께 지워진다. 실제로 그렇게 잃었다.

    그래서 사람 계정에 딸린 자리로 옮긴다. 프로그램을 몇 번을 다시 깔아도 그대로다.

        윈도우  %LOCALAPPDATA%\ConcoursComposer
        맥      ~/Library/Application Support/ConcoursComposer
        리눅스  ~/.local/share/ConcoursComposer

    DATA_DIR 로 덮어쓸 수 있다 — 두 대에서 같은 폴더를 쓰거나 시험할 때 필요하다.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return root / APP_NAME


def migrate_old_data(new_dir: Path) -> str:
    """프로그램 폴더 안에 있던 예전 자료를 새 자리로 옮겨 온다.

    **지우지 않는다.** 옛 폴더는 그대로 두고 복사만 한다 — 옮기다 잘못되면 원장의
    곡이 사라지고, 그것은 되돌릴 수 없다. 새 자리에 이미 저장 파일이 있으면 손대지
    않는다(그쪽이 최신이다).
    """
    old = ROOT / "data"
    if not old.exists() or old.resolve() == new_dir.resolve():
        return ""
    if (new_dir / "store.sqlite3").exists():
        return ""
    moved = []
    for item in old.iterdir():
        if item.name == "backups":
            continue          # 사본까지 옮길 필요는 없다. 원본이 옮겨 가면 새로 뜬다.
        target = new_dir / item.name
        if target.exists():
            continue
        try:
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
            moved.append(item.name)
        except OSError:
            continue
    return ", ".join(moved)


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
    # 골든 20곡 실측: 평균 $1.59, 최고 $3.15(96마디). 상한을 그 아래로 두면
    # 긴 곡이 파이프라인 도중에 끊긴다 — 돈은 이미 쓰고 곡은 못 얻는 최악이다.
    max_cost_per_composition: float = 4.00
    model_validation: Literal["strict", "warn", "off"] = "warn"

    # 저장소 — 기본은 data_dir/store.sqlite3. STORE_PERSIST=0 이면 메모리만 쓴다.
    store_persist: bool = True
    store_path: Path | None = None

    database_url: str = "postgresql+psycopg://concours:concours@localhost:5432/concours"
    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = Field(default_factory=user_data_dir)

    mscore_bin: str = "mscore"
    audiveris_bin: str = "audiveris"
    ffmpeg_bin: str = "ffmpeg"
    fluidsynth_bin: str = "fluidsynth"
    soundfont_path: str = ""

    # 비평 루프
    quality_threshold: float = Field(default=7.0, ge=0, le=10)
    max_revision_rounds: int = Field(default=2, ge=0, le=4)
    # 종합 점수가 문턱을 넘어도 **개별 루브릭**이 이보다 낮으면 그 항목을 겨냥해
    # 한 라운드 더 고친다. 종합 8.5 인 곡도 독창성 5.5 면 고칠 것이 있는 것이다.
    rubric_floor: float = Field(default=7.0, ge=0, le=10)
    # 목표 난이도에서 이만큼 벗어나면 텍스처를 조정하는 지시를 만든다.
    difficulty_tolerance: float = Field(default=0.5, ge=0.1, le=2.0)
    # 사전 전문심사 게이트(§6.13). 원클릭 작곡은 모의 심사 3인을 **곡을 내놓기 전에**
    # 돌리고, 평균과 최저가 둘 다 이 문턱을 넘어야 '심사 통과' 로 표시한다.
    # 미달이면 심사위원들이 공통으로 지적한 마디를 겨냥해 한 번 더 고쳐 본다.
    judge_gate_average: float = Field(default=8.0, ge=0, le=10)
    judge_gate_minimum: float = Field(default=7.0, ge=0, le=10)
    judge_gate_rounds: int = Field(default=1, ge=0, le=3)

    def __init__(self, **data: object) -> None:
        super().__init__(**data)  # type: ignore[arg-type]
        # 환경변수에서 온 값이 있어도 버리고 .env 파일 값만 쓴다(원장 지시).
        # 테스트가 명시적으로 넘긴 값은 존중한다.
        if "anthropic_api_key" not in data:
            object.__setattr__(self, "anthropic_api_key", read_api_key_from_env_file())

    def resolved_store_path(self) -> Path:
        return self.store_path or (self.data_dir / "store.sqlite3")

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
    """자료가 사는 폴더. 없으면 만들고, 프로그램 폴더 안의 옛 자료는 옮겨 온다."""
    d = Path(os.environ.get("DATA_DIR", get_settings().data_dir))
    d.mkdir(parents=True, exist_ok=True)
    migrate_old_data(d)
    return d
