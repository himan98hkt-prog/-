"""설정. 모델 문자열은 여기서만 읽는다(CLAUDE.md 절대 규칙 12)."""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("concours")

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
        """저장 파일의 자리. **자리를 정하는 곳은 여기 하나뿐이어야 한다.**

        예전에는 이 함수와 `resolve_data_dir()` 이 각자 계산했다. 둘이 어긋나면
        화면은 A 를 가리키는데 곡은 B 에 쌓인다 — 곡을 잃어버린 것과 다르지 않다.
        그래서 판단을 `resolve_data_dir()` 한 곳에 모으고 여기서는 그것을 따른다.
        """
        if self.store_path:
            return self.store_path
        return resolve_data_dir() / "store.sqlite3"

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



def _out_of_the_program_folder(d: Path) -> Path:
    """프로그램 폴더 안을 가리키는 **상대 경로** 설정은 옛 함정이다 — 비켜 세운다.

    예전 `.env.example` 에 `DATA_DIR=./data` 가 박혀 있었다. 그 시절에 설치한 PC 는
    `.env` 를 그대로 들고 있고, 설치 스크립트는 이미 있는 `.env` 를 건드리지 않는다.
    그러면 새 판을 받으려고 폴더를 지울 때 만든 곡이 함께 사라진다 — 실제로 그렇게
    사라졌고, 그건 내가 만든 함정이었다. 그래서 옛 설정이 남아 있어도 곡은 바깥에
    저장하고, 안에 있던 것은 `migrate_old_data` 가 **복사해서** 가져온다(지우지 않는다).

    절대 경로는 손대지 않는다. 그건 원장이 일부러 정한 자리다.
    """
    if d.is_absolute():
        return d
    try:
        inside = (Path.cwd() / d).resolve().is_relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return d
    if not inside:
        return d
    log.info("옛 설정(DATA_DIR=%s)이 프로그램 폴더 안을 가리켜 안전한 자리로 옮긴다", d)
    return user_data_dir()

def resolve_data_dir() -> Path:
    """자료가 사는 폴더. 없으면 만들고, 프로그램 폴더 안의 옛 자료는 옮겨 온다.

    빈 값(`DATA_DIR=`)은 **없는 것으로 본다**. 파이썬은 빈 경로를 현재 폴더(`.`)로
    읽는데, 그러면 자료가 프로그램 폴더 안에 떨어져 새 판을 받을 때 곡이 사라진다 —
    고치려던 바로 그 사고다. 설정 파일에 줄만 남기고 값을 지우는 일은 흔하다.
    """
    raw = (os.environ.get("DATA_DIR") or "").strip()
    d = Path(raw) if raw else Path(get_settings().data_dir)
    if not str(d).strip() or str(d) == ".":
        d = user_data_dir()
    d = _out_of_the_program_folder(d)
    d = _writable_or_fallback(d)
    migrate_old_data(d)
    return d


# 자리를 못 잡았을 때 남기는 한 줄. 화면의 저장 위치 안내가 이것을 읽어 보여 준다.
_DATA_DIR_WARNING: list[str] = [""]


def data_dir_warning() -> str:
    """저장 폴더를 원래 자리에 못 잡았다면 그 사정. 정상이면 빈 문자열."""
    return _DATA_DIR_WARNING[0]


def _writable_or_fallback(preferred: Path) -> Path:
    """쓸 수 있는 폴더를 반드시 하나 돌려준다 — 여기서 죽으면 아이콘이 먹통이 된다.

    백신이 폴더를 잠그거나, 회사 PC 정책이 AppData 쓰기를 막거나, 디스크가 꽉 차면
    `mkdir` 이 실패한다. 그 예외가 그대로 올라가면 창 없는 실행(`pythonw`)에서는
    **아무 일도 일어나지 않는다** — 원장이 겪은 "아이콘 눌렀는데 아무 변화가 없어" 다.
    그래서 자리를 옮겨서라도 켜지게 하고, 옮겼다는 사실을 화면에 알린다.
    """
    candidates = [preferred, Path.home() / f".{APP_NAME}", Path(tempfile.gettempdir()) / APP_NAME]
    problems: list[str] = []
    for i, cand in enumerate(candidates):
        try:
            cand.mkdir(parents=True, exist_ok=True)
            probe = cand / ".쓰기시험"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            problems.append(f"{cand}: {e.strerror or e}")
            continue
        if i:
            _DATA_DIR_WARNING[0] = (
                f"원래 저장하려던 폴더에 쓸 수 없어 '{cand}' 에 저장합니다. "
                "백신이나 회사 PC 정책이 폴더를 막고 있을 수 있습니다. "
                "곡은 정상으로 만들어지지만, 저장 위치를 확인해 두십시오."
            )
            log.warning("%s (막힌 곳: %s)", _DATA_DIR_WARNING[0], "; ".join(problems))
        else:
            _DATA_DIR_WARNING[0] = ""
        return cand

    # 세 자리가 다 막히는 일은 사실상 없다. 그래도 조용히 죽지는 않는다.
    _DATA_DIR_WARNING[0] = "저장할 수 있는 폴더를 찾지 못했습니다: " + "; ".join(problems)
    raise OSError(_DATA_DIR_WARNING[0])
