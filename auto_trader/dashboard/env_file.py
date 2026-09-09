"""`.env` 읽기·쓰기.

- 비밀값은 **마스킹해서만** 화면에 보낸다. 브라우저로 원문을 내려보내지 않는다.
- 저장은 임시파일 → `os.replace` 로 원자적으로 하고 권한을 0600 으로 좁힌다.
- 값 뒤 인라인 주석은 python-dotenv 가 값으로 읽으므로, 쓸 때 절대 붙이지 않는다.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from config.loader import mask


@dataclass
class Field:
    key: str
    label: str
    help: str = ""
    secret: bool = False
    required: bool = True
    choices: tuple[str, ...] = ()
    placeholder: str = ""
    group: str = ""


@dataclass
class Group:
    title: str
    description: str = ""
    fields: list[Field] = field(default_factory=list)


# 화면에 뿌릴 항목 정의 — .env.example 과 같은 순서를 유지한다.
GROUPS: list[Group] = [
    Group("실행 환경", "검증이 끝나기 전에는 VTS(모의) + DRY_RUN 을 유지하세요.", [
        Field("KIS_ENV", "거래 환경", "VTS=모의투자, REAL=실전(실제 자금)", choices=("VTS", "REAL")),
        Field("DRY_RUN", "주문 전송", "true=주문을 보내지 않고 기록만", choices=("true", "false")),
        Field("LOG_LEVEL", "로그 레벨", choices=("INFO", "DEBUG", "WARNING", "ERROR"), required=False),
    ]),
    Group("한국투자증권", "apiportal.koreainvestment.com 에서 모의투자용으로 발급받은 값", [
        Field("KIS_APP_KEY", "APP KEY", secret=True),
        Field("KIS_APP_SECRET", "APP SECRET", "180자 내외의 긴 문자열. 줄바꿈 없이 한 줄로", secret=True),
        Field("KIS_ACCOUNT_NO", "계좌번호 앞 8자리",
              "50123456-01 이면 50123456 만", placeholder="50123456"),
        Field("KIS_ACCOUNT_PRODUCT_CD", "계좌 상품코드", "뒤 2자리", placeholder="01"),
    ]),
    Group("AI 판단 엔진", "두 모델의 합의로 매매를 결정합니다.", [
        Field("ANTHROPIC_API_KEY", "Anthropic API 키", "console.anthropic.com — 크레딧 충전 필요", secret=True),
        Field("CLAUDE_MODEL", "Claude 모델", placeholder="claude-sonnet-5"),
        Field("CLAUDE_TEMPERATURE", "Claude temperature",
              "비워두세요. 최신 모델은 이 값을 거부(400)합니다", required=False),
        Field("CLAUDE_EFFORT", "Claude effort",
              "비우면 기본(high). 비용을 줄이려면 low 또는 medium",
              choices=("", "low", "medium", "high", "xhigh", "max"), required=False),
        Field("GEMINI_API_KEY", "Gemini API 키", "aistudio.google.com/apikey", secret=True),
        Field("GEMINI_MODEL", "Gemini 모델", placeholder="gemini-2.5-pro"),
        Field("GEMINI_TEMPERATURE", "Gemini temperature", placeholder="0.2", required=False),
    ]),
    Group("알림", "매매·오류·일간 리포트를 받습니다.", [
        # 필수 여부는 NOTIFIER 값에 따라 달라진다 — missing_required() 참고
        Field("NOTIFIER", "알림 채널", choices=("telegram", "discord")),
        Field("TELEGRAM_BOT_TOKEN", "텔레그램 봇 토큰",
              "@BotFather 에서 /newbot (telegram 선택 시 필수)", secret=True, required=False),
        Field("TELEGRAM_CHAT_ID", "텔레그램 채팅 ID",
              "봇에게 먼저 /start 를 보내세요 (telegram 선택 시 필수)", required=False),
        Field("DISCORD_WEBHOOK_URL", "디스코드 웹훅",
              "discord 선택 시 필수", secret=True, required=False),
    ]),
    Group("뉴스 (선택)",
          "비워두셔도 됩니다 — 뉴스 없이 지표만으로 판단합니다. "
          "⚠️ 네이버 로그인 아이디·비밀번호가 아닙니다! "
          "developers.naver.com 에서 앱을 등록하면 나오는 인증키입니다.", [
        Field("NAVER_CLIENT_ID", "네이버 Client ID",
              "developers.naver.com/apps 에서 앱 등록 시 발급 (사용 API 에 '검색' 을 꼭 선택). "
              "네이버 아이디가 아닙니다", required=False, placeholder="Kx8dJ2mQ7bVn0pQr"),
        Field("NAVER_CLIENT_SECRET", "네이버 Client Secret",
              "위 앱의 Client Secret. 네이버 비밀번호가 아닙니다",
              secret=True, required=False, placeholder="aB3dEfGh1J"),
    ]),
]

ALL_FIELDS: dict[str, Field] = {f.key: f for group in GROUPS for f in group.fields}

# 값이 비어 있을 때 새로 만드는 .env 에 넣을 기본값
DEFAULTS = {
    "KIS_ENV": "VTS", "DRY_RUN": "true", "LOG_LEVEL": "INFO",
    "KIS_ACCOUNT_PRODUCT_CD": "01", "CLAUDE_MODEL": "claude-sonnet-5",
    "GEMINI_MODEL": "gemini-2.5-pro", "GEMINI_TEMPERATURE": "0.2", "NOTIFIER": "telegram",
}

HEADER = """# 자동매매 설정 — 대시보드 설정 화면에서 저장됨
# 주의: 값 뒤에 주석을 달지 마세요. `KEY=값  # 설명` 은 주석까지 값으로 읽힙니다.
"""


def read_env(path: Path | str) -> dict[str, str]:
    """`.env` 원문 값 (서버 내부용 — 화면으로 내보내지 않는다)."""
    values = dotenv_values(path) if Path(path).exists() else {}
    return {key: (value or "") for key, value in values.items()}


def read_for_display(path: Path | str) -> dict[str, dict[str, str]]:
    """화면에 뿌릴 형태. 비밀값은 마스킹되고 원문은 포함되지 않는다."""
    raw = read_env(path)
    display: dict[str, dict[str, str]] = {}
    for key, meta in ALL_FIELDS.items():
        value = raw.get(key, "")
        display[key] = {
            "value": "" if meta.secret else value,
            "masked": mask(value) if (meta.secret and value) else "",
            "filled": bool(value),
        }
    return display


def write_env(path: Path | str, updates: dict[str, str]) -> list[str]:
    """변경분을 반영해 `.env` 를 다시 쓴다.

    비밀값은 빈 문자열로 오면 **기존 값을 유지**한다(화면에는 마스킹만 보이므로,
    사용자가 건드리지 않은 칸을 지워버리면 안 된다). 지우려면 `__CLEAR__` 를 보낸다.

    Returns:
        실제로 값이 바뀐 키 목록.
    """
    target = Path(path)
    current = read_env(target)
    changed: list[str] = []

    for key, meta in ALL_FIELDS.items():
        if key not in updates:
            continue
        new_value = (updates[key] or "").strip()

        if new_value == "__CLEAR__":
            new_value = ""
        elif meta.secret and not new_value:
            continue  # 손대지 않은 비밀값은 유지

        # 인라인 주석과 따옴표는 흔한 붙여넣기 실수라 여기서 정리한다.
        new_value = new_value.strip().strip('"').strip("'").split(" #")[0].strip()
        if new_value != current.get(key, ""):
            changed.append(key)
        current[key] = new_value

    for key, value in DEFAULTS.items():
        current.setdefault(key, value)

    lines = [HEADER]
    for group in GROUPS:
        lines.append(f"\n# --- {group.title} ---")
        for meta in group.fields:
            lines.append(f"{meta.key}={current.get(meta.key, '')}")
    body = "\n".join(lines) + "\n"

    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, prefix=".env.", suffix=".tmp", delete=False
    )
    try:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, target)  # 원자적 교체 — 저장 중 크래시에도 반쪽 파일이 남지 않는다
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return changed


# 알림 채널별 추가 필수 항목 — config/loader.py 의 검증과 같은 규칙을 쓴다.
NOTIFIER_REQUIRED: dict[str, tuple[str, ...]] = {
    "telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"),
    "discord": ("DISCORD_WEBHOOK_URL",),
}


def required_keys(env: dict[str, str]) -> list[str]:
    """현재 값 기준으로 채워야 하는 항목 목록."""
    keys = [key for key, meta in ALL_FIELDS.items() if meta.required]
    notifier = (env.get("NOTIFIER") or "telegram").lower()
    keys.extend(NOTIFIER_REQUIRED.get(notifier, ()))
    return keys


def missing_required(path: Path | str) -> list[str]:
    raw = read_env(path)
    return [key for key in required_keys(raw) if not raw.get(key)]
