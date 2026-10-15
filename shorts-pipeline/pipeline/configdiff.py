"""업데이트로 들어온 새 설정을 사용자 설정과 비교하고, 골라서 적용한다.

`update.ps1` 은 `config.yaml` 을 **덮어쓰지 않는다.** 사용자가 바꿔놓은
업스케일·클립 수·음악 설정이 조용히 되돌아가면 안 되기 때문이다. 새 버전은
`config.yaml.new` 로 남긴다.

그런데 그 결과 **개선된 기본값이 영영 사용자에게 닿지 않는다.** 실제로
모델을 hailuo 로 바꿔 편당 $2.15 -> $1.49 가 되게 해놓고도, 사용자 화면에는
여전히 $3.82(=kling) 가 떠 있었다. 본인은 싸진 줄 알고 계속 쓰고 있었다.

그래서 **다른 점을 화면에 보여주고 누르면 적용**되게 한다.

**깊이에 상관없이 본다.** 처음에는 맨 윗줄만 봤고, 그래서 `output.fps` 가
비교도 적용도 안 됐다. 그 다음엔 `output` 한 겹만 더 봤는데 이번에는
`output.seamless_loop.enabled` 가 빠졌다. 같은 실수를 세 번 하지 않으려고
점(.)으로 이어진 경로를 그대로 다루도록 바꿨다.

손대는 것은 `WATCHED` 에 적힌 항목뿐이고, 주석과 나머지 줄은 그대로 둔다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 화면에 보여줄 항목만. 여기 없는 경로는 비교도 적용도 하지 않는다.
# 점(.)으로 깊이를 나타낸다. (설명은 초보자가 읽을 수 있는 말로)
WATCHED: dict[str, str] = {
    "provider": "영상 만드는 곳",
    "model": "영상 모델",
    "clip_duration": "클립 길이(초)",
    "num_clips": "클립 수",
    "mode": "이어붙이는 방식",
    "upscale_between_clips": "클립 사이 화질 보정",
    "crossfade_seconds": "장면 이음새(초)",
    "poll_timeout_seconds": "클립 하나를 기다리는 한도(초)",
    "output.fps": "프레임률",
    "output.crf": "화질(낮을수록 좋음)",
    "output.audio": "음악",
    "output.hook_overlay.enabled": "첫 3초 훅 자막",
    "output.seamless_loop.enabled": "무한 루프",
    "output.look.grade": "색보정",
    "cost.monthly_cap_usd": "이번 달 상한(USD)",
    "cost.hard_cap_usd": "한 번에 쓸 수 있는 상한(USD)",
}

_LINE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")
_BLOCK_SCALARS = ("|", ">", ">-", "|-", "|+", ">+")


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


def _walk(text: str):
    """(줄 번호, 점으로 이은 경로, 값) 을 차례로 내놓는다.

    들여쓰기로 깊이를 따라간다. 값이 비어 있으면 그 줄은 하위 블록의
    머리이므로 경로에 쌓고 값은 내놓지 않는다.
    """
    stack: list[tuple[int, str]] = []          # (들여쓰기, 이름)
    for lineno, line in enumerate(text.splitlines()):
        if not line.strip() or line.lstrip().startswith(("#", "-")):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        indent, name, raw = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([n for _, n in stack] + [name])
        value = _strip_comment(raw)
        if not value or value in _BLOCK_SCALARS:
            stack.append((indent, name))       # 하위 블록의 머리
            continue
        yield lineno, path, value


def paths(text: str) -> dict[str, str]:
    """점으로 이은 경로 -> 값. 먼저 나온 것이 이긴다."""
    out: dict[str, str] = {}
    for _, path, value in _walk(text):
        out.setdefault(path, value)
    return out


def compare(current: Path, incoming: Path) -> list[Change]:
    """두 설정 파일에서 **볼 만한 차이**만 골라 돌려준다."""
    if not current.exists() or not incoming.exists():
        return []
    try:
        cur = paths(current.read_text(encoding="utf-8", errors="replace"))
        new = paths(incoming.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []

    out: list[Change] = []
    for key, label in WATCHED.items():
        a, b = cur.get(key, ""), new.get(key, "")
        if b and a != b:
            out.append(Change(key, label, a or "(없음)", b))
    return out


def apply(path: Path, updates: dict[str, str]) -> list[str]:
    """값만 제자리에서 고친다. 주석과 줄 순서는 그대로 둔다.

    실제로 바뀐 경로 목록을 돌려준다.
    """
    wanted = {k: v for k, v in updates.items() if k in WATCHED and v}
    if not wanted or not path.exists():
        return []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    changed: list[str] = []
    seen: set[str] = set()

    for lineno, key, value in _walk("\n".join(lines)):
        if key not in wanted or key in seen:
            continue
        seen.add(key)
        if value == wanted[key]:
            continue
        line = lines[lineno]
        indent = line[:len(line) - len(line.lstrip())]
        name = key.rsplit(".", 1)[-1]
        lines[lineno] = f"{indent}{name}: {wanted[key]}{_trailing(line)}"
        changed.append(key)

    # 파일에 아예 없던 항목은 위 루프가 못 고친다. 그대로 두면 "새 설정 있음"
    # 알림이 영영 안 사라지고, 정작 값은 반영되지 않는다. 끼워 넣는다.
    for key in [k for k in wanted if k not in seen]:
        if _insert(lines, key, wanted[key]):
            changed.append(key)

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def _insert(lines: list[str], key: str, value: str) -> bool:
    """없던 항목을 알맞은 자리에 끼워 넣는다. 넣었으면 True.

    맨 윗단이면 파일 끝에 붙인다 — 들여쓰기 없는 키는 앞의 블록을 닫으므로
    어디에 와도 유효하다.

    하위 항목(`cost.monthly_cap_usd`)이면 **부모 블록 안 마지막 줄 뒤**에
    넣는다. 부모가 없으면 포기한다. 잘못된 자리에 넣어 설정 파일을 망가뜨리는
    것보다, 안 넣고 알림을 남기는 편이 낫다.
    """
    parent, _, name = key.rpartition(".")
    if not parent:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# 새 기본값에서 추가된 항목")
        lines.append(f"{name}: {value}")
        return True

    head = _block_line(lines, parent)
    if head is None:
        return False
    indent, at = head
    child = " " * (indent + 2)
    # 이 블록에 속한 마지막 줄을 찾는다. 빈 줄과 주석은 블록의 끝이 아니다.
    last = at
    for i in range(at + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        current = len(line) - len(line.lstrip())
        if current <= indent:
            break
        last = i
    lines.insert(last + 1, f"{child}{name}: {value}")
    return True


def _block_line(lines: list[str], path: str) -> tuple[int, int] | None:
    """`path` 블록의 머리 줄. (들여쓰기, 줄 번호) 또는 None."""
    stack: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith(("#", "-")):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        indent, name, raw = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        here = ".".join([n for _, n in stack] + [name])
        if not _strip_comment(raw) and here == path:
            return indent, lineno
        if not _strip_comment(raw):
            stack.append((indent, name))
    return None


def _trailing(line: str) -> str:
    """줄 끝의 주석. 왜 그 값인지 적혀 있는 경우가 많아 살려 둔다."""
    hash_at = line.find("#")
    return "  " + line[hash_at:].strip() if hash_at >= 0 else ""
