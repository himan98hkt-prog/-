"""`.env`(비밀값) + `config/settings.yaml`(매매 파라미터)를 읽어 검증된 Settings 객체로 반환한다.

- 필수 키가 없거나 값이 잘못되면 `ConfigError`에 **모든** 문제를 모아 한 번에 알린다.
- 비밀값은 `mask()`를 거친 형태로만 노출된다(`print(load())` 안전).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time as dt_time
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

KST = ZoneInfo("Asia/Seoul")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LOG_DIR = BASE_DIR / "logs"
TOKEN_PATH = DATA_DIR / "token.json"
DB_PATH = DATA_DIR / "trader.db"
HOLIDAYS_PATH = CONFIG_DIR / "holidays.txt"

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# 이 프로그램이 읽는 환경변수 전체 — .env 와 프로세스 환경 양쪽에서 온다.
ALL_ENV_KEYS: tuple[str, ...] = (
    "KIS_ENV", "DRY_RUN", "LOG_LEVEL",
    "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO", "KIS_ACCOUNT_PRODUCT_CD",
    "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "CLAUDE_TEMPERATURE", "CLAUDE_EFFORT",
    "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_TEMPERATURE",
    "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_TEMPERATURE",
    "NOTIFIER", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL",
)
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

# ChatGPT 기본 모델 — Structured Outputs 를 지원하고 이 용도에 비용이 적당하다.
DEFAULT_OPENAI_MODEL = "gpt-5.1"

# KIS 도메인: 모의투자를 기본으로 삼는다(절대 규칙 1).
KIS_BASE_URLS: dict[str, str] = {
    "VTS": "https://openapivts.koreainvestment.com:29443",
    "REAL": "https://openapi.koreainvestment.com:9443",
}


class ConfigError(Exception):
    """설정 로딩·검증 실패."""


def mask(value: str | None, keep_head: int = 4, keep_tail: int = 2) -> str:
    """비밀값 마스킹. 로그·출력에는 반드시 이 형태만 사용한다."""
    if not value:
        return "(미설정)"
    keep_head = max(keep_head, 0)
    keep_tail = max(keep_tail, 0)
    if len(value) <= keep_head + keep_tail:
        return "*" * len(value)
    # keep_tail=0 에 value[-0:] 을 쓰면 문자열 전체가 남는다 — 슬라이스로 처리하지 않는다.
    tail = value[-keep_tail:] if keep_tail else ""
    return f"{value[:keep_head]}{'*' * 6}{tail}"


# --------------------------------------------------------------------------- #
# dataclass 정의
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EnvConfig:
    """`.env`에서 온 실행 환경·비밀값."""

    kis_env: Literal["VTS", "REAL"]
    dry_run: bool
    log_level: str

    kis_app_key: str
    kis_app_secret: str
    kis_account_no: str
    kis_account_product_cd: str

    anthropic_api_key: str
    claude_model: str
    claude_temperature: float | None
    claude_effort: str | None
    gemini_api_key: str
    gemini_model: str
    gemini_temperature: float
    # ChatGPT 는 선택 — 키가 없으면 Claude·Gemini 둘로만 판단한다.
    openai_api_key: str | None
    openai_model: str
    openai_temperature: float | None


    notifier: Literal["telegram", "discord"]
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    discord_webhook_url: str | None

    @property
    def base_url(self) -> str:
        return KIS_BASE_URLS[self.kis_env]

    @property
    def is_real(self) -> bool:
        return self.kis_env == "REAL"

    @property
    def chatgpt_enabled(self) -> bool:
        """키가 있을 때만 세 번째 판단 엔진으로 참여시킨다."""
        return bool(self.openai_api_key)

    def __repr__(self) -> str:  # 비밀값 노출 금지
        return (
            "EnvConfig("
            f"kis_env={self.kis_env!r}, dry_run={self.dry_run}, log_level={self.log_level!r}, "
            f"base_url={self.base_url!r}, "
            f"kis_app_key={mask(self.kis_app_key)!r}, kis_app_secret={mask(self.kis_app_secret)!r}, "
            f"kis_account_no={mask(self.kis_account_no, 2, 2)!r}, "
            f"kis_account_product_cd={self.kis_account_product_cd!r}, "
            f"anthropic_api_key={mask(self.anthropic_api_key)!r}, claude_model={self.claude_model!r}, "
            f"claude_temperature={self.claude_temperature!r}, claude_effort={self.claude_effort!r}, "
            f"gemini_api_key={mask(self.gemini_api_key)!r}, gemini_model={self.gemini_model!r}, "
            f"gemini_temperature={self.gemini_temperature!r}, "
            f"openai_api_key={mask(self.openai_api_key)!r}, openai_model={self.openai_model!r}, "
            f"openai_temperature={self.openai_temperature!r}, chatgpt_enabled={self.chatgpt_enabled}, "
            f"notifier={self.notifier!r}, "
            f"telegram_bot_token={mask(self.telegram_bot_token)!r}, "
            f"telegram_chat_id={mask(self.telegram_chat_id, 2, 2)!r}, "
            f"discord_webhook_url={mask(self.discord_webhook_url, 20, 0)!r})"
        )


@dataclass(frozen=True)
class UniverseConfig:
    mode: Literal["watchlist", "volume_rank"]
    watchlist: list[str]
    volume_rank_top_n: int
    exclude_keywords: list[str]
    min_price: int
    max_candidates_per_cycle: int


@dataclass(frozen=True)
class ScheduleConfig:
    universe_refresh: dt_time
    first_cycle: dt_time
    cycle_interval_min: int
    last_new_buy: dt_time
    eod_review: dt_time
    daily_report: dt_time


@dataclass(frozen=True)
class RiskConfig:
    total_investment_cap_krw: int
    max_position_pct: float
    max_positions: int
    daily_loss_limit_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    min_order_krw: int
    order_type: Literal["market", "limit"]
    limit_slippage_pct: float
    # 손절 감시 주기(분). 정규 사이클 사이에 급락해도 이 주기로 잡아낸다.
    guard_interval_min: int = 3


@dataclass(frozen=True)
class AiConfig:
    timeout_sec: int
    max_retries: int
    min_confidence: float
    news_max_items: int
    news_lookback_hours: int
    # 모델별 100만 토큰당 단가 (입력, 출력) USD. 비우면 내장 기본표를 쓴다.
    pricing: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    env: EnvConfig
    universe: UniverseConfig
    schedule: ScheduleConfig
    risk: RiskConfig
    ai: AiConfig
    paths: dict[str, Path] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# 파싱 헬퍼
# --------------------------------------------------------------------------- #


def _get_env(key: str, default: str | None = None) -> str | None:
    raw = os.getenv(key, default)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _parse_bool(raw: str | None, *, default: bool, key: str, errors: list[str]) -> bool:
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in ("true", "1", "yes", "y", "on"):
        return True
    if lowered in ("false", "0", "no", "n", "off"):
        return False
    errors.append(f"{key}: 'true' 또는 'false' 여야 합니다 (현재: {raw!r})")
    return default


def _parse_optional_float(key: str, minimum: float, maximum: float, errors: list[str]) -> float | None:
    """설정되지 않았으면 None(해당 파라미터를 아예 보내지 않음)."""
    raw = _get_env(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        errors.append(f"{key}: 숫자여야 합니다 (현재: {raw!r})")
        return None
    if not (minimum <= value <= maximum):
        errors.append(f"{key}: {minimum}~{maximum} 범위여야 합니다 (현재: {value})")
        return None
    return value


def _parse_time(raw: Any, key: str, errors: list[str]) -> dt_time:
    if isinstance(raw, dt_time):
        return raw
    text = str(raw).strip()
    try:
        hour_str, minute_str = text.split(":")
        return dt_time(int(hour_str), int(minute_str))
    except (ValueError, AttributeError):
        errors.append(f"{key}: 'HH:MM' 형식이어야 합니다 (현재: {raw!r})")
        return dt_time(0, 0)


def _num(
    section: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    cast: type = int,
    minimum: float | None = None,
    maximum: float | None = None,
    default: Any = None,
) -> Any:
    if key not in section:
        if default is not None:  # 나중에 추가된 항목은 기존 settings.yaml 도 그대로 쓰게 한다
            return cast(default)
        errors.append(f"{path}.{key}: 필수 항목이 없습니다")
        return cast(0)
    try:
        value = cast(section[key])
    except (TypeError, ValueError):
        errors.append(f"{path}.{key}: 숫자여야 합니다 (현재: {section[key]!r})")
        return cast(0)
    if minimum is not None and value < minimum:
        errors.append(f"{path}.{key}: {minimum} 이상이어야 합니다 (현재: {value})")
    if maximum is not None and value > maximum:
        errors.append(f"{path}.{key}: {maximum} 이하여야 합니다 (현재: {value})")
    return value


def _choice(
    section: dict[str, Any],
    key: str,
    path: str,
    allowed: tuple[str, ...],
    errors: list[str],
) -> str:
    value = str(section.get(key, "")).strip()
    if value not in allowed:
        errors.append(f"{path}.{key}: {list(allowed)} 중 하나여야 합니다 (현재: {value!r})")
        return allowed[0]
    return value


def _str_list(section: dict[str, Any], key: str, path: str, errors: list[str]) -> list[str]:
    value = section.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{path}.{key}: 문자열 리스트여야 합니다 (현재: {value!r})")
        return []
    return [item.strip() for item in value]


# --------------------------------------------------------------------------- #
# 섹션별 로더
# --------------------------------------------------------------------------- #


def _load_env(errors: list[str]) -> EnvConfig:
    kis_env = (_get_env("KIS_ENV", "VTS") or "VTS").upper()
    if kis_env not in KIS_BASE_URLS:
        errors.append(f"KIS_ENV: 'VTS' 또는 'REAL' 이어야 합니다 (현재: {kis_env!r})")
        kis_env = "VTS"

    dry_run = _parse_bool(_get_env("DRY_RUN", "true"), default=True, key="DRY_RUN", errors=errors)

    log_level = (_get_env("LOG_LEVEL", "INFO") or "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        errors.append(f"LOG_LEVEL: {list(VALID_LOG_LEVELS)} 중 하나여야 합니다 (현재: {log_level!r})")
        log_level = "INFO"

    required = {
        "KIS_APP_KEY": _get_env("KIS_APP_KEY"),
        "KIS_APP_SECRET": _get_env("KIS_APP_SECRET"),
        "KIS_ACCOUNT_NO": _get_env("KIS_ACCOUNT_NO"),
        "ANTHROPIC_API_KEY": _get_env("ANTHROPIC_API_KEY"),
        "CLAUDE_MODEL": _get_env("CLAUDE_MODEL"),
        "GEMINI_API_KEY": _get_env("GEMINI_API_KEY"),
        "GEMINI_MODEL": _get_env("GEMINI_MODEL"),
    }
    for key, value in required.items():
        if not value:
            errors.append(f"{key}: .env 에 반드시 설정해야 합니다")

    account_no = required["KIS_ACCOUNT_NO"] or ""
    if account_no and not (account_no.isdigit() and len(account_no) == 8):
        errors.append(f"KIS_ACCOUNT_NO: 계좌번호 앞 8자리 숫자여야 합니다 (현재 길이: {len(account_no)})")

    product_cd = _get_env("KIS_ACCOUNT_PRODUCT_CD", "01") or "01"
    if not (product_cd.isdigit() and len(product_cd) == 2):
        errors.append(f"KIS_ACCOUNT_PRODUCT_CD: 숫자 2자리여야 합니다 (현재: {product_cd!r})")

    # 샘플링 파라미터: Sonnet 5·Opus 5 등 최신 모델은 temperature 를 거부(400)하므로
    # 기본값은 '미전송'이다. 구형 모델을 쓸 때만 CLAUDE_TEMPERATURE 를 지정한다.
    claude_temperature = _parse_optional_float("CLAUDE_TEMPERATURE", 0.0, 1.0, errors)
    claude_effort = (_get_env("CLAUDE_EFFORT") or "").lower() or None
    if claude_effort and claude_effort not in VALID_EFFORTS:
        errors.append(f"CLAUDE_EFFORT: {list(VALID_EFFORTS)} 중 하나여야 합니다 (현재: {claude_effort!r})")
        claude_effort = None
    gemini_temperature = _parse_optional_float("GEMINI_TEMPERATURE", 0.0, 2.0, errors)
    if gemini_temperature is None:
        gemini_temperature = 0.2

    # ChatGPT — 선택. 키가 있으면 모델 이름도 있어야 한다.
    openai_api_key = _get_env("OPENAI_API_KEY")
    openai_model = _get_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL
    # 최신 추론 모델은 temperature 를 거부하므로 기본은 '미전송'이다.
    openai_temperature = _parse_optional_float("OPENAI_TEMPERATURE", 0.0, 2.0, errors)

    notifier = (_get_env("NOTIFIER", "telegram") or "telegram").lower()
    telegram_bot_token = _get_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = _get_env("TELEGRAM_CHAT_ID")
    discord_webhook_url = _get_env("DISCORD_WEBHOOK_URL")
    if notifier == "telegram":
        if not telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN: NOTIFIER=telegram 일 때 필수입니다")
        if not telegram_chat_id:
            errors.append("TELEGRAM_CHAT_ID: NOTIFIER=telegram 일 때 필수입니다")
    elif notifier == "discord":
        if not discord_webhook_url:
            errors.append("DISCORD_WEBHOOK_URL: NOTIFIER=discord 일 때 필수입니다")
    else:
        errors.append(f"NOTIFIER: 'telegram' 또는 'discord' 여야 합니다 (현재: {notifier!r})")
        notifier = "telegram"


    return EnvConfig(
        kis_env=kis_env,  # type: ignore[arg-type]
        dry_run=dry_run,
        log_level=log_level,
        kis_app_key=required["KIS_APP_KEY"] or "",
        kis_app_secret=required["KIS_APP_SECRET"] or "",
        kis_account_no=account_no,
        kis_account_product_cd=product_cd,
        anthropic_api_key=required["ANTHROPIC_API_KEY"] or "",
        claude_model=required["CLAUDE_MODEL"] or "",
        claude_temperature=claude_temperature,
        claude_effort=claude_effort,
        gemini_api_key=required["GEMINI_API_KEY"] or "",
        gemini_model=required["GEMINI_MODEL"] or "",
        gemini_temperature=gemini_temperature,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_temperature=openai_temperature,
        notifier=notifier,  # type: ignore[arg-type]
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        discord_webhook_url=discord_webhook_url,
    )


def _load_universe(raw: dict[str, Any], errors: list[str]) -> UniverseConfig:
    section = raw.get("universe") or {}
    mode = _choice(section, "mode", "universe", ("watchlist", "volume_rank"), errors)
    watchlist = _str_list(section, "watchlist", "universe", errors)
    for code in watchlist:
        if not (code.isdigit() and len(code) == 6):
            errors.append(f"universe.watchlist: 종목코드는 숫자 6자리여야 합니다 (현재: {code!r})")
    if mode == "watchlist" and not watchlist:
        errors.append("universe.watchlist: watchlist 모드에서는 최소 1종목이 필요합니다")

    return UniverseConfig(
        mode=mode,  # type: ignore[arg-type]
        watchlist=watchlist,
        volume_rank_top_n=_num(section, "volume_rank_top_n", "universe", errors, minimum=1, maximum=100),
        exclude_keywords=_str_list(section, "exclude_keywords", "universe", errors),
        min_price=_num(section, "min_price", "universe", errors, minimum=0),
        max_candidates_per_cycle=_num(
            section, "max_candidates_per_cycle", "universe", errors, minimum=1, maximum=100
        ),
    )


def _load_schedule(raw: dict[str, Any], errors: list[str]) -> ScheduleConfig:
    section = raw.get("schedule") or {}
    schedule = ScheduleConfig(
        universe_refresh=_parse_time(section.get("universe_refresh"), "schedule.universe_refresh", errors),
        first_cycle=_parse_time(section.get("first_cycle"), "schedule.first_cycle", errors),
        cycle_interval_min=_num(section, "cycle_interval_min", "schedule", errors, minimum=1, maximum=390),
        last_new_buy=_parse_time(section.get("last_new_buy"), "schedule.last_new_buy", errors),
        eod_review=_parse_time(section.get("eod_review"), "schedule.eod_review", errors),
        daily_report=_parse_time(section.get("daily_report"), "schedule.daily_report", errors),
    )
    if schedule.first_cycle >= schedule.last_new_buy:
        errors.append("schedule: first_cycle 은 last_new_buy 보다 빨라야 합니다")
    if schedule.eod_review >= schedule.daily_report:
        errors.append("schedule: eod_review 는 daily_report 보다 빨라야 합니다")
    return schedule


def _load_risk(raw: dict[str, Any], errors: list[str]) -> RiskConfig:
    section = raw.get("risk") or {}
    risk = RiskConfig(
        total_investment_cap_krw=_num(section, "total_investment_cap_krw", "risk", errors, minimum=1),
        max_position_pct=_num(section, "max_position_pct", "risk", errors, cast=float, minimum=0.1, maximum=100),
        max_positions=_num(section, "max_positions", "risk", errors, minimum=1, maximum=50),
        daily_loss_limit_pct=_num(section, "daily_loss_limit_pct", "risk", errors, cast=float, minimum=0.1, maximum=100),
        stop_loss_pct=_num(section, "stop_loss_pct", "risk", errors, cast=float, minimum=-100, maximum=-0.1),
        take_profit_pct=_num(section, "take_profit_pct", "risk", errors, cast=float, minimum=0.1),
        min_order_krw=_num(section, "min_order_krw", "risk", errors, minimum=0),
        order_type=_choice(section, "order_type", "risk", ("market", "limit"), errors),  # type: ignore[arg-type]
        limit_slippage_pct=_num(section, "limit_slippage_pct", "risk", errors, cast=float, minimum=0, maximum=30),
        guard_interval_min=_num(
            section, "guard_interval_min", "risk", errors,
            minimum=1, maximum=30, default=3,
        ),
    )
    if risk.min_order_krw > risk.total_investment_cap_krw:
        errors.append("risk: min_order_krw 가 total_investment_cap_krw 보다 큽니다")
    return risk


def _load_pricing(section: dict[str, Any], errors: list[str]) -> dict[str, tuple[float, float]]:
    """`ai.pricing` — {모델명: [입력단가, 출력단가]} (100만 토큰당 USD)."""
    raw = section.get("pricing") or {}
    if not isinstance(raw, dict):
        errors.append("ai.pricing: 매핑(모델명: [입력, 출력])이어야 합니다")
        return {}

    pricing: dict[str, tuple[float, float]] = {}
    for model, rates in raw.items():
        try:
            input_rate, output_rate = (float(rates[0]), float(rates[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            errors.append(f"ai.pricing.{model}: [입력단가, 출력단가] 두 숫자여야 합니다 (현재: {rates!r})")
            continue
        if input_rate < 0 or output_rate < 0:
            errors.append(f"ai.pricing.{model}: 단가는 0 이상이어야 합니다")
            continue
        pricing[str(model)] = (input_rate, output_rate)
    return pricing


def _load_ai(raw: dict[str, Any], errors: list[str]) -> AiConfig:
    section = raw.get("ai") or {}
    return AiConfig(
        timeout_sec=_num(section, "timeout_sec", "ai", errors, minimum=5, maximum=600),
        max_retries=_num(section, "max_retries", "ai", errors, minimum=0, maximum=10),
        min_confidence=_num(section, "min_confidence", "ai", errors, cast=float, minimum=0.0, maximum=1.0),
        news_max_items=_num(section, "news_max_items", "ai", errors, minimum=0, maximum=50),
        news_lookback_hours=_num(section, "news_lookback_hours", "ai", errors, minimum=1, maximum=720),
        pricing=_load_pricing(section, errors),
    )


# --------------------------------------------------------------------------- #
# 공개 API
# --------------------------------------------------------------------------- #


def load(
    env_path: Path | str | None = None,
    settings_path: Path | str | None = None,
    *,
    create_dirs: bool = True,
) -> Settings:
    """`.env` + `settings.yaml` 로드 → 검증 → Settings 반환.

    Raises:
        ConfigError: 파일이 없거나 검증에 실패한 경우(문제를 모두 모아 한 번에 보고).
    """
    env_file = Path(env_path) if env_path else BASE_DIR / ".env"
    yaml_file = Path(settings_path) if settings_path else CONFIG_DIR / "settings.yaml"

    if env_file.exists():
        load_dotenv(env_file, override=False)
    elif env_path is not None:
        raise ConfigError(f".env 파일을 찾을 수 없습니다: {env_file}")
    # 기본 경로의 .env 가 없으면 프로세스 환경변수만으로 진행하고, 부족분은 아래 검증에서 잡힌다.

    if not yaml_file.exists():
        raise ConfigError(f"설정 파일을 찾을 수 없습니다: {yaml_file}")
    try:
        raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"settings.yaml 파싱 실패: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("settings.yaml 최상위는 매핑(key: value)이어야 합니다")

    errors: list[str] = []
    env = _load_env(errors)
    universe = _load_universe(raw, errors)
    schedule = _load_schedule(raw, errors)
    risk = _load_risk(raw, errors)
    ai = _load_ai(raw, errors)

    if errors:
        bullet = "\n  - ".join(errors)
        raise ConfigError(
            f"설정 검증 실패 ({len(errors)}건):\n  - {bullet}\n"
            f"\n.env 는 {env_file} 에, 매매 파라미터는 {yaml_file} 에 있습니다."
        )

    if create_dirs:
        for directory in (DATA_DIR, SNAPSHOT_DIR, LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)

    return Settings(
        env=env,
        universe=universe,
        schedule=schedule,
        risk=risk,
        ai=ai,
        paths={
            "base": BASE_DIR,
            "config": CONFIG_DIR,
            "data": DATA_DIR,
            "snapshots": SNAPSHOT_DIR,
            "logs": LOG_DIR,
            "token": TOKEN_PATH,
            "db": DB_PATH,
            "holidays": HOLIDAYS_PATH,
        },
    )
