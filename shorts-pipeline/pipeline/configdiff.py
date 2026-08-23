"""업데이트로 들어온 새 설정을 사용자 설정과 비교하고, 골라서 적용한다.

`update.ps1` 은 `config.yaml` 을 **덮어쓰지 않는다.** 사용자가 바꿔놓은
업스케일·클립 수·음악 설정이 조용히 되돌아가면 안 되기 때문이다. 새 버전은
`config.yaml.new` 로 남긴다.

그런데 그 결과 **개선된 기본값이 영영 사용자에게 닿지 않는다.** 실제로
모델을 hailuo 로 바꿔 편당 $2.15 -> $1.49 가 되게 해놓고도, 사용자 화면에는
여전히 $3.82(=kling) 가 떠 있었다. 본인은 싸진 줄 알고 계속 쓰고 있었다.

그래서 **다른 점을 화면에 보여주고 누르면 적용**되게 한다. 손대는 것은
맨 윗줄에 있는 단순한 값들뿐이고, 주석과 나머지 줄은 그대로 둔다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 화면에 보여줄 항목만. 여기 없는 키는 비교도 적용도 하지 않는다.
# (설명은 초보자가 읽을 수 있는 말로)
WATCHED: dict[str, str] = {
    "provider": "영상 만드는 곳",
    "model": "영상 모델",
    "clip_duration": "클립 길이(초)",
    "num_clips": "클립 수",
    "mode": "이어붙이는 방식",
    "upscale_between_clips": "클립 사이 화질 보정",
    "crossfade_seconds": "장면 이음새(초)",
}

# 맨 왼쪽 칸에서 시작하는 `key: value` 한 줄. 들여쓴 줄(하위 설정)은 건드리지 않는다.
_TOP = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")


@dataclass
class Change:
    key: str
    label: str
    current: str
    incoming: str


def _strip_comment(value: str) -> str:
    """`hailuo_23_pro       # providers 섹션의 키` -> `hailuo_23_pro`"""
    out, quote = [], ""
    for ch in value:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).strip()


def top_level(text: str) -> dict[str, str]:
    """맨 윗단의 `key: value` 만 뽑는다. 값이 비어 있으면(하위 블록) 제외."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        m = _TOP.match(line)
        if not m:
            continue
        value = _strip_comment(m.group(2))
        if value and value not in ("|", ">", ">-", "|-"):
            out.setdefault(m.group(1), value)
    return out


def compare(current: Path, incoming: Path) -> list[Change]:
    """두 설정 파일에서 **볼 만한 차이**만 골라 돌려준다."""
    if not current.exists() or not incoming.exists():
        return []
    try:
        cur = top_level(current.read_text(encoding="utf-8", errors="replace"))
        new = top_level(incoming.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []

    out: list[Change] = []
    for key, label in WATCHED.items():
        a, b = cur.get(key, ""), new.get(key, "")
        if b and a != b:
            out.append(Change(key, label, a or "(없음)", b))
    return out


def apply(path: Path, updates: dict[str, str]) -> list[str]:
    """맨 윗단 값만 제자리에서 고친다. 주석과 줄 순서는 그대로 둔다.

    실제로 바뀐 키 목록을 돌려준다.
    """
    wanted = {k: v for k, v in updates.items() if k in WATCHED and v}
    if not wanted or not path.exists():
        return []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    changed: list[str] = []
    seen: set[str] = set()

    for i, line in enumerate(lines):
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        m = _TOP.match(line)
        if not m:
            continue
        key = m.group(1)
        if key not in wanted or key in seen:
            continue
        seen.add(key)
        old = _strip_comment(m.group(2))
        if old == wanted[key]:
            continue
        # 값 뒤의 주석은 살려 둔다 — 왜 그 값인지 적혀 있는 경우가 많다.
        rest = line[len(m.group(1)):]
        comment = ""
        hash_at = rest.find("#")
        if hash_at >= 0:
            comment = "  " + rest[hash_at:].strip()
        lines[i] = f"{key}: {wanted[key]}{comment}"
        changed.append(key)

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed
