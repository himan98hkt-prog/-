"""`.env` 파일을 화면에서 안전하게 읽고 고친다.

터미널을 못 여는 사람이 브라우저 [설정] 탭에서 키를 넣을 수 있도록 만든 것이다.
주석과 줄 순서를 그대로 남기고, 값만 제자리에서 바꾼다.
비밀값은 절대 원문 그대로 화면에 돌려주지 않는다 — 앞뒤 몇 글자만 보여준다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
SAMPLE_PATH = ROOT / ".env.example"

# 화면에서 손댈 수 있는 항목만 허용한다. 여기 없는 키는 저장 요청이 와도 무시한다.
SECRET = "secret"      # 값을 되돌려주지 않는다
PLAIN = "plain"        # 그대로 보여준다


@dataclass(frozen=True)
class Field:
    key: str
    kind: str
    label: str
    group: str
    hint: str = ""
    placeholder: str = ""


FIELDS: tuple[Field, ...] = (
    Field("FAL_API_KEY", SECRET, "fal.ai 키", "video",
          "fal.ai → Dashboard → API Keys 에서 만든 키를 붙여넣으세요.",
          "aaaaaaaa-bbbb-...:0123456789abcdef"),

    Field("YOUTUBE_CLIENT_SECRET_FILE", PLAIN, "client_secret.json 경로", "youtube",
          "아래 [파일 올리기] 를 쓰면 자동으로 채워집니다.",
          "secrets/client_secret.json"),
    Field("YOUTUBE_TOKEN_FILE", PLAIN, "토큰 저장 위치", "youtube",
          "그대로 두면 됩니다.", "secrets/youtube_token.json"),

    Field("IG_USER_ID", PLAIN, "인스타 비즈니스 계정 ID (비워도 됩니다)", "instagram",
          "비워두면 토큰으로 자동으로 찾아 채웁니다.",
          "비워두세요 — 자동으로 찾습니다"),
    Field("IG_ACCESS_TOKEN", SECRET, "인스타 액세스 토큰", "instagram",
          "장기 토큰(60일)을 넣으세요. 만료되면 다시 발급받아야 합니다.",
          "EAAG..."),

    Field("S3_ENDPOINT_URL", PLAIN, "R2 엔드포인트", "storage",
          "Cloudflare R2 → 계정 ID 가 들어간 주소입니다. AWS S3 면 비워두세요.",
          "https://<account_id>.r2.cloudflarestorage.com"),
    Field("S3_BUCKET", PLAIN, "버킷 이름", "storage", "", "ai-deokhu"),
    Field("AWS_ACCESS_KEY_ID", SECRET, "액세스 키 ID", "storage",
          "R2 → Manage API Tokens → Object Read & Write 로 만듭니다.", ""),
    Field("AWS_SECRET_ACCESS_KEY", SECRET, "시크릿 액세스 키", "storage",
          "토큰을 만들 때 한 번만 보입니다. 놓쳤으면 새로 만드세요.", ""),
    Field("S3_REGION", PLAIN, "리전", "storage",
          "R2 는 비워두세요. AWS S3 만 ap-northeast-2 처럼 넣습니다.", ""),
    Field("S3_PUBLIC_BASE_URL", PLAIN, "공개 도메인", "storage",
          "선택 사항. R2 커스텀 도메인을 붙였을 때만 넣습니다.", ""),
)

BY_KEY = {f.key: f for f in FIELDS}

GROUPS = {
    "video": "영상 만들기",
    "youtube": "유튜브 업로드",
    "instagram": "인스타그램 업로드",
    "storage": "영상 보관함 (인스타에 필요)",
}

# KEY=VALUE. 앞의 export 와 양옆 공백을 봐준다.
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _unquote(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def read_raw(path: Path | None = None) -> dict[str, str]:
    """.env 를 읽어 그대로 돌려준다. 파일이 없으면 빈 dict."""
    path = path or ENV_PATH
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _LINE.match(line)
        if m:
            out[m.group(1)] = _unquote(m.group(2))
    return out


def mask(value: str) -> str:
    """비밀값을 알아볼 만큼만 남긴다. 짧은 값은 길이만 알린다."""
    v = value.strip()
    if not v:
        return ""
    if len(v) <= 8:
        return "*" * len(v)
    return f"{v[:4]}{'*' * 6}{v[-4:]}"


def ensure_file() -> Path:
    """.env 가 없으면 예시 파일을 복사해 만든다."""
    if not ENV_PATH.exists():
        if SAMPLE_PATH.exists():
            ENV_PATH.write_text(SAMPLE_PATH.read_text(encoding="utf-8"),
                                encoding="utf-8")
        else:
            ENV_PATH.write_text("", encoding="utf-8")
    return ENV_PATH


def write(updates: dict[str, str], path: Path | None = None) -> list[str]:
    """허용된 키만 제자리에서 고친다. 실제로 바뀐 키 목록을 돌려준다.

    빈 문자열을 주면 값을 비운다(줄은 남긴다). 없는 키는 파일 끝에 붙인다.
    """
    path = path or ENV_PATH
    if path is ENV_PATH:
        ensure_file()
    elif not path.exists():
        path.write_text("", encoding="utf-8")

    wanted = {k: str(v) for k, v in updates.items() if k in BY_KEY}
    if not wanted:
        return []

    before = read_raw(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    seen: set[str] = set()

    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        m = _LINE.match(line)
        if not m or m.group(1) not in wanted:
            continue
        key = m.group(1)
        seen.add(key)
        lines[i] = f"{key}={wanted[key]}"

    tail = [k for k in wanted if k not in seen]
    if tail:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# 화면 [설정] 탭에서 추가했습니다.")
        lines += [f"{k}={wanted[k]}" for k in tail]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    changed = [k for k, v in wanted.items() if before.get(k, "") != v]
    if path == ENV_PATH:
        # 이번 프로세스에도 바로 먹히게 한다. 껐다 켜지 않아도 되도록.
        # 테스트가 임시 파일을 쓸 때는 진짜 환경을 건드리지 않는다.
        for k, v in wanted.items():
            if v:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
    return changed


def snapshot() -> dict:
    """화면에 뿌릴 설정 상태. 비밀값은 마스킹해서 나간다.

    화면에 보여주는 값은 어디까지나 .env 의 내용이다 — 사용자가 고치는 대상이니까.
    다만 윈도우에 같은 이름의 시스템 환경변수가 따로 잡혀 있으면 그쪽이 이긴다
    (python-dotenv 는 이미 있는 값을 덮지 않는다). 그럴 때만 따로 알려준다.
    """
    values = read_raw()
    fields = []
    for f in FIELDS:
        stored = values.get(f.key, "").strip()
        live = (os.getenv(f.key) or "").strip()
        # 방금 저장하면 os.environ 에도 같은 값을 넣으므로, 다를 때만 가로채기다.
        overridden = bool(live) and live != stored
        fields.append({
            "key": f.key,
            "label": f.label,
            "group": f.group,
            "hint": f.hint,
            "placeholder": f.placeholder,
            "secret": f.kind == SECRET,
            "filled": bool(stored),
            "value": mask(stored) if f.kind == SECRET else stored,
            "overridden": overridden,
            "override_note": (
                f"컴퓨터에 {f.key} 환경변수가 따로 잡혀 있어 그 값이 먼저 쓰입니다. "
                "여기서 고쳐도 안 바뀌면 시스템 환경변수를 지우세요."
                if overridden else ""),
        })
    return {
        "groups": [{"id": g, "label": GROUPS[g]} for g in GROUPS],
        "fields": fields,
        "env_path": str(ENV_PATH),
        "exists": ENV_PATH.exists(),
    }
