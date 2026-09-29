"""무료 LLM 제목 작성 검사.

    python tests/test_llm.py

여기서 지키려는 것은 하나다 — **글자 때문에 영상이 막히지 않을 것.**
키가 없든, 인터넷이 끊겼든, 모델이 헛소리를 하든, 한도를 다 썼든,
파이프라인은 규칙 기반 제목으로 그대로 굴러가야 한다.

네트워크는 한 번도 타지 않는다. requests 를 가짜로 갈아끼운다.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import llm                      # noqa: E402
from pipeline.copywriter import Copy          # noqa: E402

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_llm"


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


class FakeResponse:
    def __init__(self, status: int, payload=None, text: str = ""):
        self.status_code = status
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("본문이 JSON 이 아닙니다")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequests(types.ModuleType):
    """requests 를 흉내낸다. 호출 기록을 남겨 실제로 몇 번 불렀는지 센다."""

    def __init__(self, *, get=None, post=None):
        super().__init__("requests")
        self._get, self._post = get, post
        self.calls: list[tuple[str, str]] = []

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if self._get is None:
            raise RuntimeError("네트워크 없음")
        return self._get(url, kw)

    def post(self, url, **kw):
        self.calls.append(("POST", url))
        if self._post is None:
            raise RuntimeError("네트워크 없음")
        return self._post(url, kw)


def install(fake) -> None:
    sys.modules["requests"] = fake
    llm.reset_model_cache()      # 캐시가 검사 사이로 새면 안 된다


def models_payload(ids: list[str]) -> FakeResponse:
    return FakeResponse(200, {"data": [{"id": i} for i in ids]})


def chat_payload(content: str) -> FakeResponse:
    return FakeResponse(200, {"choices": [{"message": {"content": content}}]})


THREE = json.dumps([
    {"title": "빛이 쏟아지는 계단", "hook": "이 끝에 뭐가 있을까"},
    {"title": "잠긴 신전을 지나", "hook": "물이 발목까지 찼다"},
    {"title": "끝나지 않는 회랑", "hook": "돌아갈 길이 없다"},
], ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════
def test_parse() -> None:
    print("\n[응답 파싱] 무료 모델은 지시를 자주 어긴다")

    got = llm.parse_suggestions(THREE)
    check("깔끔한 JSON 배열", len(got) == 3 and got[0].title == "빛이 쏟아지는 계단")

    fenced = f"물론이죠! 아래와 같습니다.\n```json\n{THREE}\n```\n도움이 되었길!"
    check("코드펜스 + 앞뒤 수다", len(llm.parse_suggestions(fenced)) == 3)

    wrapped = json.dumps({"suggestions": json.loads(THREE)}, ensure_ascii=False)
    check("{suggestions:[...]} 로 감싼 경우", len(llm.parse_suggestions(wrapped)) == 3)

    bare = f"제안드립니다:\n{THREE}\n"
    check("앞에 설명만 붙은 경우", len(llm.parse_suggestions(bare)) == 3)

    check("빈 응답은 빈 목록", llm.parse_suggestions("") == [])
    check("JSON 이 아니면 빈 목록", llm.parse_suggestions("제목: 그냥 산") == [])

    hashed = json.dumps([{"title": "네온 골목 #shorts #ai", "hook": "가보자"}],
                        ensure_ascii=False)
    got = llm.parse_suggestions(hashed)
    check("제목의 해시태그는 걷어낸다", got[0].title == "네온 골목",
          f"실제: {got[0].title!r}")

    longtitle = json.dumps([{"title": "가" * 200, "hook": "나" * 200}],
                           ensure_ascii=False)
    got = llm.parse_suggestions(longtitle)
    check("너무 긴 제목은 잘라낸다", len(got[0].title) <= 60 and len(got[0].hook) <= 60)

    check("제목이 없는 항목은 버린다",
          llm.parse_suggestions('[{"hook":"훅만 있음"}]') == [])
    check("배열이 아니면 빈 목록", llm.parse_suggestions('"그냥 문자열"') == [])
    check("limit 을 넘기지 않는다", len(llm.parse_suggestions(THREE, limit=2)) == 2)


def test_model_pick() -> None:
    print("\n[모델 고르기] 무료 모델 ID 는 수시로 사라진다")

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    os.environ.pop("OPENROUTER_MODEL", None)

    ids = ["zz/paid-model", "aa/mistral-small:free", "bb/gemini-2.5-flash:free",
           "cc/qwen3-30b:free", "dd/unknown-thing:free"]
    install(FakeRequests(get=lambda u, kw: models_payload(ids)))

    free = llm.free_models()
    check("유료 모델은 빼고 :free 만", all(m.endswith(":free") for m in free))
    check("개수가 맞다", len(free) == 4, f"실제 {len(free)}")
    check("선호 순서대로 (gemini 가 먼저)", free[0] == "bb/gemini-2.5-flash:free",
          f"실제 {free[0]}")
    check("모르는 계열은 뒤로", free[-1] == "dd/unknown-thing:free", f"실제 {free[-1]}")
    check("pick_model 이 1등을 고른다", llm.pick_model() == "bb/gemini-2.5-flash:free")

    os.environ["OPENROUTER_MODEL"] = "내가/지정한:free"
    fake = FakeRequests(get=lambda u, kw: models_payload(ids))
    install(fake)
    check("직접 지정하면 그것을 쓴다", llm.pick_model() == "내가/지정한:free")
    check("직접 지정하면 목록을 부르지 않는다", fake.calls == [])
    os.environ.pop("OPENROUTER_MODEL")

    cached = FakeRequests(get=lambda u, kw: models_payload(ids))
    install(cached)
    llm.free_models(); llm.free_models(); llm.free_models()
    gets = sum(1 for m, _ in cached.calls if m == "GET")
    check("목록은 한 번만 받아 재사용한다", gets == 1, f"실제 {gets}회")
    llm.reset_model_cache()
    llm.free_models()
    check("비우면 다시 받는다",
          sum(1 for m, _ in cached.calls if m == "GET") == 2)

    install(FakeRequests(get=lambda u, kw: models_payload(["zz/paid-only"])))
    try:
        llm.free_models()
        check("무료 모델이 하나도 없으면 알려준다", False)
    except llm.LLMUnavailable:
        check("무료 모델이 하나도 없으면 알려준다", True)

    install(FakeRequests(get=None))             # 네트워크 죽음
    try:
        llm.free_models()
        check("네트워크가 죽으면 LLMUnavailable", False)
    except llm.LLMUnavailable:
        check("네트워크가 죽으면 LLMUnavailable", True)


def test_suggest() -> None:
    print("\n[제목 받아오기]")

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    os.environ.pop("OPENROUTER_MODEL", None)
    os.environ.pop("OPENROUTER_DAILY_CAP", None)
    state = TMP / "s1"
    state.mkdir(parents=True, exist_ok=True)

    sent: dict = {}

    def post(url, kw):
        sent.update(kw.get("json") or {})
        sent["headers"] = kw.get("headers") or {}
        return chat_payload(THREE)

    install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]), post=post))

    got = llm.suggest("temple", "descending a vast temple staircase lit by braziers",
                      base_title="계단을 내려가는 길", state_dir=state)
    check("후보 3개", len(got) == 3)
    check("고른 모델로 보낸다", sent.get("model") == "a/gemini:free")
    check("장면 설명을 프롬프트에 넣는다", "braziers" in json.dumps(sent, ensure_ascii=False))
    check("지금 제목도 함께 보낸다", "계단을 내려가는 길" in json.dumps(sent, ensure_ascii=False))
    check("인증 헤더가 붙는다",
          sent["headers"].get("Authorization") == "Bearer sk-or-test")

    used, cap = llm.usage(state)
    check("호출 수를 센다", used == 1, f"실제 {used}")

    # 응답이 쓰레기면 조용히 실패해야 한다
    install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                         post=lambda u, kw: chat_payload("음... 잘 모르겠어요")))
    try:
        llm.suggest("temple", "a temple", state_dir=state)
        check("읽을 수 없는 응답은 LLMUnavailable", False)
    except llm.LLMUnavailable:
        check("읽을 수 없는 응답은 LLMUnavailable", True)

    # 429 / 401 은 사람이 읽을 수 있는 말로
    for code, word in ((429, "한도"), (401, "키")):
        install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                             post=lambda u, kw, c=code: FakeResponse(c, {}, "nope")))
        try:
            llm.suggest("temple", "a temple", state_dir=state)
            check(f"HTTP {code} 안내", False)
        except llm.LLMUnavailable as exc:
            check(f"HTTP {code} 안내", word in str(exc), str(exc))

    check("빈 장면이면 부르지도 않는다",
          _raises(lambda: llm.suggest("temple", "   ", state_dir=state)))

    # 404 = 모델이 목록에서 빠졌다. 캐시를 버리고 다음엔 다시 받아와야 한다.
    install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                         post=lambda u, kw: FakeResponse(404, {}, "no such model")))
    llm.free_models()                       # 캐시를 채워둔다
    try:
        llm.suggest("temple", "a temple", state_dir=state)
    except llm.LLMUnavailable as exc:
        check("404 는 '다시 눌러 보라'고 안내", "다시" in str(exc), str(exc))
    fresh = FakeRequests(get=lambda u, kw: models_payload(["b/qwen:free"]),
                         post=lambda u, kw: chat_payload(THREE))
    sys.modules["requests"] = fresh         # install() 은 캐시를 비우므로 직접
    llm.suggest("temple", "a temple", state_dir=state)
    check("404 뒤에는 목록을 다시 받는다",
          any(m == "GET" for m, _ in fresh.calls), str(fresh.calls))


def test_daily_cap() -> None:
    print("\n[하루 한도] 무료는 하루 50회다")

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    os.environ["OPENROUTER_DAILY_CAP"] = "2"
    state = TMP / "s2"
    state.mkdir(parents=True, exist_ok=True)

    fake = FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                        post=lambda u, kw: chat_payload(THREE))
    install(fake)

    llm.suggest("t", "a temple", state_dir=state)
    llm.suggest("t", "a temple", state_dir=state)
    posts = sum(1 for m, _ in fake.calls if m == "POST")
    check("두 번은 나간다", posts == 2, f"실제 {posts}")

    try:
        llm.suggest("t", "a temple", state_dir=state)
        check("한도를 넘으면 막는다", False)
    except llm.LLMUnavailable as exc:
        check("한도를 넘으면 막는다", "한도" in str(exc), str(exc))

    posts_after = sum(1 for m, _ in fake.calls if m == "POST")
    check("막힐 때는 네트워크를 아예 안 탄다", posts_after == 2, f"실제 {posts_after}")

    used, cap = llm.usage(state)
    check("상한을 환경변수로 바꿀 수 있다", cap == 2)

    # 날짜가 바뀌면 0 부터
    (state / llm.USAGE_FILE).write_text(
        json.dumps({"date": "2000-01-01", "count": 999}), encoding="utf-8")
    used, _ = llm.usage(state)
    check("날짜가 바뀌면 다시 0", used == 0, f"실제 {used}")

    os.environ.pop("OPENROUTER_DAILY_CAP")


def test_polish_never_breaks() -> None:
    print("\n[가장 중요] 제목 때문에 영상이 막히면 안 된다")

    base = Copy(title="원래 제목", hook="원래 훅", prompt="forward motion, no cut")
    state = TMP / "s3"
    state.mkdir(parents=True, exist_ok=True)

    os.environ.pop("OPENROUTER_API_KEY", None)
    install(FakeRequests())
    out = llm.polish(base, "temple", "a temple staircase", state_dir=state)
    check("키가 없으면 원본 그대로", out.title == "원래 제목" and out.hook == "원래 훅")
    check("키가 없으면 네트워크를 안 탄다", sys.modules["requests"].calls == [])
    check("enabled() 는 False", llm.enabled() is False)

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    for label, fake in (
        ("네트워크가 죽어도", FakeRequests()),
        ("모델 목록이 비어도", FakeRequests(get=lambda u, kw: models_payload([]))),
        ("응답이 쓰레기여도", FakeRequests(
            get=lambda u, kw: models_payload(["a/gemini:free"]),
            post=lambda u, kw: chat_payload("???"))),
        ("서버가 500 을 줘도", FakeRequests(
            get=lambda u, kw: models_payload(["a/gemini:free"]),
            post=lambda u, kw: FakeResponse(500, {}, "boom"))),
        ("본문이 JSON 이 아니어도", FakeRequests(
            get=lambda u, kw: models_payload(["a/gemini:free"]),
            post=lambda u, kw: FakeResponse(200, None, "<html>"))),
    ):
        install(fake)
        out = llm.polish(base, "temple", "a temple staircase", state_dir=state)
        check(f"{label} 원본 그대로", out.title == "원래 제목" and out.hook == "원래 훅")

    install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                         post=lambda u, kw: chat_payload(THREE)))
    out = llm.polish(base, "temple", "a temple staircase", state_dir=state)
    check("잘 되면 갈아끼운다", out.title == "빛이 쏟아지는 계단")
    check("움직임 프롬프트는 건드리지 않는다", out.prompt == base.prompt)
    check("돌려주는 것도 Copy", isinstance(out, Copy))


def test_status() -> None:
    print("\n[설정 탭 표시]")
    state = TMP / "s4"
    state.mkdir(parents=True, exist_ok=True)

    os.environ.pop("OPENROUTER_API_KEY", None)
    s = llm.status(state)
    check("키가 없으면 꺼짐", s["enabled"] is False and "규칙" in s["detail"])

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    os.environ.pop("OPENROUTER_MODEL", None)
    s = llm.status(state)
    check("키가 있으면 켜짐", s["enabled"] is True)
    check("모델은 자동 선택으로 표시", s["model"] == "자동 선택")
    check("사용량을 보여준다", "0/" in s["detail"], s["detail"])


def test_sidecar_keeps_source() -> None:
    print("\n[사이드카] 제목을 고쳐도 다시 분류할 수 있어야 한다")

    from ui import server

    seeds = TMP / "seeds"
    seeds.mkdir(parents=True, exist_ok=True)
    img = seeds / "temple_01.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")       # 내용은 안 본다
    img.with_suffix(".yaml").write_text(
        "title:  옛 제목\n"
        "hook:   옛 훅\n"
        "prompt: descending a temple staircase, forward motion\n"
        "theme:  temple\n"
        "source: descending_a_vast_temple_staircase_abc123.png\n",
        encoding="utf-8")

    server.save_meta(img, title="새 제목", hook="새 훅", prompt="new prompt")
    text = img.with_suffix(".yaml").read_text(encoding="utf-8")

    check("제목이 바뀐다", "새 제목" in text)
    check("훅이 바뀐다", "새 훅" in text)
    check("theme 이 남아 있다", "theme:" in text and "temple" in text)
    check("source 가 남아 있다",
          "descending_a_vast_temple_staircase_abc123.png" in text, text)

    from pipeline.intake import read_sidecar
    got = read_sidecar(img)
    check("다시 읽어도 source 가 살아 있다",
          got.get("source", "").endswith("abc123.png"), str(got))
    check("다시 읽으면 새 제목", got.get("title") == "새 제목", str(got))

    # source 가 원래 없던 파일은 없는 대로 저장돼야 한다 (줄을 지어내지 않는다)
    img2 = seeds / "misc_02.png"
    img2.write_bytes(b"\x89PNG\r\n\x1a\n")
    img2.with_suffix(".yaml").write_text("title:  그냥\nhook:   훅\nprompt: p\n",
                                         encoding="utf-8")
    server.save_meta(img2, title="바꿈", hook="훅2", prompt="p2")
    t2 = img2.with_suffix(".yaml").read_text(encoding="utf-8")
    check("없던 source 를 지어내지 않는다", "source:" not in t2, t2)

    # 사이드카가 아예 없어도 죽지 않는다
    img3 = seeds / "new_03.png"
    img3.write_bytes(b"\x89PNG\r\n\x1a\n")
    server.save_meta(img3, title="처음", hook="", prompt="")
    check("사이드카가 없어도 만든다", img3.with_suffix(".yaml").exists())


def test_easy_mode_never_blocks() -> None:
    print("\n[간편 모드] 제목 다듬기가 영상 생성을 막으면 안 된다")

    from ui import server

    seeds = TMP / "seeds"
    img = seeds / "temple_01.png"
    before = img.with_suffix(".yaml").read_text(encoding="utf-8")

    os.environ.pop("OPENROUTER_API_KEY", None)
    install(FakeRequests())
    server._polish_seed(img)
    check("키가 없으면 사이드카를 안 건드린다",
          img.with_suffix(".yaml").read_text(encoding="utf-8") == before)

    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    install(FakeRequests())                     # 네트워크 죽음
    server._polish_seed(img)
    check("네트워크가 죽어도 예외가 안 샌다",
          img.with_suffix(".yaml").read_text(encoding="utf-8") == before)

    install(FakeRequests(get=lambda u, kw: models_payload(["a/gemini:free"]),
                         post=lambda u, kw: chat_payload(THREE)))
    server._polish_seed(img)
    after = img.with_suffix(".yaml").read_text(encoding="utf-8")
    check("잘 되면 제목이 바뀐다", "빛이 쏟아지는 계단" in after, after)
    check("그래도 source 는 살아 있다", "abc123.png" in after, after)


def _raises(fn) -> bool:
    try:
        fn()
    except llm.LLMUnavailable:
        return True
    except Exception:
        return False
    return False


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    real_requests = sys.modules.get("requests")
    saved = {k: os.environ.get(k) for k in
             ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_DAILY_CAP")}
    try:
        test_parse()
        test_model_pick()
        test_suggest()
        test_daily_cap()
        test_polish_never_breaks()
        test_status()
        test_sidecar_keeps_source()
        test_easy_mode_never_blocks()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if real_requests is not None:
            sys.modules["requests"] = real_requests
        else:
            sys.modules.pop("requests", None)
        shutil.rmtree(TMP, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print(f"통과 {len(PASSED)} · 실패 {len(FAILED)}")
    for f in FAILED:
        print(f"  실패: {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
