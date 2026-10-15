"""OpenRouter 무료 모델로 제목·훅을 다시 지어 본다.

**이 파일이 없어도, 키가 없어도, 인터넷이 끊겨도 파이프라인은 그대로 돌아간다.**
여기서 하는 일은 규칙으로 이미 지어놓은 제목을 더 나은 것으로 바꿔보는 것뿐이고,
무엇 하나라도 어긋나면 조용히 원래 제목을 그대로 쓴다. 돈 드는 영상 생성이
글자 몇 개 때문에 막히는 일은 없어야 한다.

── 왜 모델 이름을 코드에 박지 않았나 ────────────────────────────────
OpenRouter 의 `:free` 모델은 **수시로 사라진다.** 2026-08 조사 시점에도
`deepseek/deepseek-r1:free` 와 `meta-llama/llama-3.3-70b-instruct:free` 가
이미 목록에서 빠져 있었다. 특정 ID 를 박아두면 몇 주 뒤 조용히 죽는다.
그래서 **실행할 때마다 `/models` 로 살아 있는 무료 모델을 받아와** 그중에서
고른다. 사용자가 `OPENROUTER_MODEL` 로 직접 지정하면 그것을 우선한다.

── 무료 한도 ────────────────────────────────────────────────────────
`:free` 모델은 분당 20회 · 하루 50회다 (한 번이라도 $10 를 충전한 이력이
있으면 하루 1000회). 하루 상한을 넘기지 않도록 호출 수를 파일에 세어 둔다.
영상 한 편에 1회면 충분하므로 기본 상한 40회는 넉넉하다.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
USAGE_FILE = "openrouter_usage.json"
DEFAULT_DAILY_CAP = 40          # 무료 한도 50 보다 낮게 잡아 여유를 둔다
TIMEOUT = 45                    # 초. 넘으면 그냥 포기하고 규칙 제목을 쓴다

# 살아 있는 무료 모델 중에서 고를 때의 선호 순서. **부분 문자열**로 맞춘다 —
# 정확한 ID 는 자주 바뀌지만 계열 이름은 오래 간다. 한국어 문장을 뽑아야
# 하므로 한국어가 되는 계열을 앞에 뒀다.
PREFERRED = (
    "gemini",       # 한국어 자연스러움 · 빠름
    "qwen",         # 한국어 무난 · 무료 티어에 오래 남아 있는 편
    "llama",
    "mistral",
    "gemma",
    "phi",
)


class LLMUnavailable(Exception):
    """키가 없거나 한도를 다 썼거나 응답이 이상할 때. 바깥에서는 무시해도 된다."""


@dataclass
class Suggestion:
    title: str
    hook: str


# ── 키 · 한도 ────────────────────────────────────────────────────────
def base_url() -> str:
    """기본은 OpenRouter. 사내 프록시나 호환 서버를 쓸 수 있게 열어 둔다.

    (검사할 때 가짜 서버를 물리는 데도 쓴다 — 진짜 돈이나 한도를 쓰지 않으려고.)
    """
    return (os.getenv("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def api_key() -> str:
    return (os.getenv("OPENROUTER_API_KEY") or "").strip()


def enabled() -> bool:
    return bool(api_key())


def daily_cap() -> int:
    raw = (os.getenv("OPENROUTER_DAILY_CAP") or "").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_DAILY_CAP


def _usage_path(state_dir: Path) -> Path:
    return Path(state_dir) / USAGE_FILE


def usage(state_dir: Path) -> tuple[int, int]:
    """(오늘 쓴 횟수, 상한). 날짜가 바뀌면 0 부터 다시 센다."""
    path = _usage_path(state_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    count = int(data.get("count", 0)) if data.get("date") == today else 0
    return count, daily_cap()


def _spend(state_dir: Path) -> None:
    path = _usage_path(state_dir)
    count, _ = usage(state_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": today, "count": count + 1}),
                        encoding="utf-8")
    except OSError:
        pass                    # 세는 데 실패해도 본 작업은 계속한다


# ── HTTP ─────────────────────────────────────────────────────────────
def _headers() -> dict:
    key = api_key()
    if not key:
        raise LLMUnavailable("OPENROUTER_API_KEY 가 없습니다.")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # OpenRouter 가 권장하는 식별 헤더. 무료 티어에서도 붙여두는 편이 좋다.
        "HTTP-Referer": "https://github.com/ai-deokhu/shorts-pipeline",
        "X-Title": "AI DEOKHU",
    }


# 목록은 자주 안 바뀐다. 한 번 받아두고 잠깐 재사용해 왕복을 줄인다.
_MODEL_CACHE: dict[str, object] = {"at": 0.0, "ids": []}
MODEL_CACHE_SECONDS = 900


def reset_model_cache() -> None:
    """다음에 부를 때 목록을 다시 받게 한다.

    모델이 목록에서 빠지면 404 가 오는데, 그때 캐시를 비워야 다음 시도에서
    살아 있는 다른 모델로 넘어간다. 안 비우면 15분 동안 죽은 모델만 부른다.
    """
    _MODEL_CACHE.update(at=0.0, ids=[])


def free_models(*, timeout: int = 15, refresh: bool = False) -> list[str]:
    """지금 살아 있는 `:free` 모델 ID 를 선호 순서로 돌려준다."""
    import time

    import requests

    if not refresh:
        cached = _MODEL_CACHE.get("ids") or []
        if cached and time.monotonic() - float(_MODEL_CACHE["at"]) < MODEL_CACHE_SECONDS:
            return list(cached)

    try:
        r = requests.get(f"{base_url()}/models", headers=_headers(), timeout=timeout)
        r.raise_for_status()
        data = r.json().get("data") or []
    except LLMUnavailable:
        raise
    except Exception as exc:                        # 네트워크·JSON 무엇이든
        raise LLMUnavailable(f"모델 목록을 받지 못했습니다: {exc}") from exc

    ids = [str(m.get("id", "")) for m in data if str(m.get("id", "")).endswith(":free")]
    if not ids:
        raise LLMUnavailable("지금 쓸 수 있는 무료 모델이 없습니다.")

    def rank(mid: str) -> tuple[int, str]:
        low = mid.lower()
        for i, hint in enumerate(PREFERRED):
            if hint in low:
                return (i, low)
        return (len(PREFERRED), low)

    ranked = sorted(ids, key=rank)
    _MODEL_CACHE.update(at=time.monotonic(), ids=list(ranked))
    return ranked


def pick_model(*, timeout: int = 15) -> str:
    """쓸 모델을 정한다. 사용자가 지정했으면 그것, 아니면 살아 있는 것 중 최선."""
    fixed = (os.getenv("OPENROUTER_MODEL") or "").strip()
    if fixed:
        return fixed
    return free_models(timeout=timeout)[0]


def _chat(messages: list[dict], *, model: str, state_dir: Path,
          max_tokens: int = 700, timeout: int = TIMEOUT) -> str:
    import requests

    count, cap = usage(state_dir)
    if count >= cap:
        raise LLMUnavailable(
            f"오늘 무료 호출 한도({cap}회)를 다 썼습니다. 내일 다시 됩니다.")

    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 0.9}
    try:
        r = requests.post(f"{base_url()}/chat/completions", headers=_headers(),
                          json=payload, timeout=timeout)
    except Exception as exc:
        raise LLMUnavailable(f"연결하지 못했습니다: {exc}") from exc

    _spend(state_dir)           # 응답이 오류여도 호출은 한 것이므로 먼저 센다

    if r.status_code == 429:
        raise LLMUnavailable("무료 한도에 걸렸습니다 (분당 20회 · 하루 50회). "
                             "잠시 뒤 다시 눌러 주세요.")
    if r.status_code == 401:
        raise LLMUnavailable("OpenRouter 키가 거부됐습니다. [설정] 탭에서 다시 넣어 주세요.")
    if r.status_code in (404, 400):
        # 모델이 목록에서 빠졌을 수 있다. 캐시를 버려 다음엔 다른 것을 고르게.
        reset_model_cache()
        raise LLMUnavailable(
            f"'{model}' 을(를) 쓸 수 없습니다. 무료 모델이 바뀐 듯하니 "
            "다시 한 번 눌러 주세요.")
    if r.status_code >= 400:
        raise LLMUnavailable(f"OpenRouter 오류 {r.status_code}: {r.text[:200]}")

    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable("응답을 읽지 못했습니다.") from exc


# ── 응답 파싱 ────────────────────────────────────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_suggestions(text: str, *, limit: int = 3) -> list[Suggestion]:
    """모델 응답에서 제목·훅 쌍을 뽑는다.

    무료 모델은 지시를 자주 어긴다 — 코드펜스로 감싸거나, 앞에 설명을 붙이거나,
    JSON 대신 목록으로 준다. 그래서 세 단계로 물러서며 읽는다.
    """
    if not text:
        return []

    def clean(v: object) -> str:
        s = re.sub(r"\s+", " ", str(v or "")).strip().strip('"“”')
        # 제목에 해시태그가 섞여 오면 걷어낸다 — 태그는 따로 붙인다
        s = re.sub(r"#\S+", "", s).strip(" -·—,")
        return s[:60]

    def collect(items: object) -> list[Suggestion]:
        out: list[Suggestion] = []
        if not isinstance(items, list):
            return out
        for it in items:
            if not isinstance(it, dict):
                continue
            title, hook = clean(it.get("title")), clean(it.get("hook"))
            if title:
                out.append(Suggestion(title, hook))
        return out

    # 1) 통째로 JSON
    candidates: list[str] = [text]
    # 2) 코드펜스 안쪽
    candidates += _FENCE.findall(text)
    # 3) 본문에서 가장 바깥 대괄호 / 중괄호 덩어리
    for opener, closer in (("[", "]"), ("{", "}")):
        i, j = text.find(opener), text.rfind(closer)
        if 0 <= i < j:
            candidates.append(text[i:j + 1])

    for blob in candidates:
        try:
            data = json.loads(blob.strip())
        except ValueError:
            continue
        if isinstance(data, list):
            found = collect(data)
        elif isinstance(data, dict):
            # {"suggestions": [...]} 로 감싸 오는 모델이 흔하다. 키 이름도 제각각.
            found = collect(data.get("suggestions") or data.get("titles")
                            or data.get("results"))
            if not found:
                found = collect([data])         # 통째로 한 개만 준 경우
        else:
            continue                            # 문자열·숫자 — 여기서는 건질 게 없다
        if found:
            return found[:limit]

    return []


# ── 실제로 부르는 곳 ─────────────────────────────────────────────────
_SYSTEM = (
    "너는 한국어 유튜브 Shorts·인스타 릴스 채널의 카피라이터다. "
    "채널은 AI 로 만든 판타지 풍경을 끊김 없이 전진하며 보여주는 영상만 올린다. "
    "사람이 실제로 누르고 싶어지는 짧은 한국어 제목을 쓴다."
)

_RULES = """규칙:
- title: 한국어 18자 이내. 해시태그·이모지·따옴표 금지. 장면이 눈에 그려질 것.
- hook: 한국어 22자 이내. 인스타 피드에서 잘리지 않는 첫 줄. 궁금하게 만들 것.
- 과장된 낚시("충격", "소름", "역대급")는 쓰지 말 것.
- 서로 다른 각도로 3개를 낼 것.

반드시 아래 형식의 JSON 배열만 출력한다. 설명을 붙이지 마라.
[{"title":"...","hook":"..."},{"title":"...","hook":"..."},{"title":"...","hook":"..."}]"""


def suggest(theme: str, raw_prompt: str, *, base_title: str = "",
            base_hook: str = "", state_dir: Path = Path("runs"),
            limit: int = 3, model: str | None = None) -> list[Suggestion]:
    """제목·훅 후보를 받아온다. 실패하면 LLMUnavailable 을 올린다.

    부르는 쪽에서 잡아서 무시하면 규칙 기반 제목이 그대로 쓰인다.
    """
    scene = re.sub(r"\s+", " ", raw_prompt or "").strip()[:600]
    if not scene:
        raise LLMUnavailable("장면 설명이 비어 있습니다.")

    user = (
        f"영상의 장면(미드저니 프롬프트): {scene}\n"
        f"분류: {theme}\n"
        + (f"지금 제목: {base_title}\n" if base_title else "")
        + (f"지금 훅: {base_hook}\n" if base_hook else "")
        + "\n" + _RULES
    )
    chosen = model or pick_model()
    text = _chat(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": user}],
        model=chosen, state_dir=state_dir)

    found = parse_suggestions(text, limit=limit)
    if not found:
        raise LLMUnavailable("제목을 읽어내지 못했습니다. 잠시 뒤 다시 눌러 주세요.")
    return found


def polish(copy, theme: str, raw_prompt: str, *,
           state_dir: Path = Path("runs")):
    """제목·훅을 LLM 으로 갈아끼운다. **어떤 이유로든 실패하면 원본 그대로.**

    copy 는 copywriter.Copy. 여기서 예외를 내보내지 않는 것이 핵심이다.
    """
    if not enabled():
        return copy
    try:
        best = suggest(theme, raw_prompt, base_title=copy.title,
                       base_hook=copy.hook, state_dir=state_dir, limit=1)[0]
    except Exception:
        return copy
    return type(copy)(title=best.title or copy.title,
                      hook=best.hook or copy.hook,
                      prompt=copy.prompt)


def status(state_dir: Path = Path("runs")) -> dict:
    """[설정] 탭에 보여줄 상태."""
    if not enabled():
        return {"enabled": False, "detail": "키가 없어 규칙으로 제목을 짓습니다."}
    count, cap = usage(state_dir)
    fixed = (os.getenv("OPENROUTER_MODEL") or "").strip()
    return {"enabled": True, "used": count, "cap": cap,
            "model": fixed or "자동 선택",
            "detail": f"오늘 {count}/{cap}회 사용"}
