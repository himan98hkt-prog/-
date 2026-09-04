"""FastAPI 앱. 시작 시 모델 문자열 유효성을 확인한다(절대 규칙 12)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.api import (
    apikey,
    books,
    compositions,
    corpus,
    feedback,
    folder,
    handoff,
    health,
    judge,
    recitals,
    references,
    rights,
    students,
    studio,
    wallet,
)
from app.api.deps import get_store
from app.config import get_settings, validate_models
from app.generation.apierrors import ClaudeUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("concours")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    problems = validate_models(s)  # strict 모드면 여기서 기동이 멈춘다
    for p in problems:
        log.warning("모델 설정 확인: %s", p)
    log.info(
        "ConcoursComposer 시작 · COMPOSER_MODEL=%s · WRITER_MODEL=%s · API키=%s · 비용상한=$%.2f",
        s.composer_model,
        s.writer_model,
        "있음" if s.has_api_key else "없음(스텁 엔진)",
        s.max_cost_per_composition,
    )
    app.state.model_problems = problems

    # 원장이 폴더에 넣어 둔 참고 악보를 시작할 때 한 번 읽는다.
    # 업로드 화면을 거치지 않아도 참고가 걸리게 하는 것이 목적이다.
    try:
        import sys
        from pathlib import Path

        scripts = Path(__file__).resolve().parents[2] / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from import_scores import sync as sync_reference_scores

        from app.api.corpus import get_corpus

        r = sync_reference_scores(get_corpus(), quiet=True)
        app.state.reference_scores = r
        if r["added"] or r["failed"]:
            log.info("참고 악보 적재 %s", r)
    except Exception:  # 참고 악보가 없다고 기동을 막지 않는다
        log.warning("참고 악보 폴더를 읽지 못했다", exc_info=True)
        app.state.reference_scores = {"added": 0, "skipped": 0, "failed": 0}

    if s.store_persist:
        path = s.resolved_store_path()
        get_store().attach(path)
        log.info("저장소 파일 %s", path)

    # 저장해 둔 예명을 불러온다. 악보에 찍히는 이름은 이것 하나다(실명은 등록 서류에만).
    try:
        from app.api.rights import get_composer
        from app.identity import set_alias

        set_alias(get_composer(get_store()).alias)
    except Exception:  # 이름 때문에 기동을 막지 않는다
        log.warning("작곡가 예명을 불러오지 못했다", exc_info=True)
    yield
    get_store().flush()  # 예약된 저장까지 마치고 끝낸다


app = FastAPI(
    title="ConcoursComposer",
    version="0.3.0",
    description="학생 맞춤형 AI 콩쿨 독창곡 생성기 (SPEC.md v3 · A축)",
    lifespan=lifespan,
)
# ── 어떤 오류든 원장에게 말이 되게 ────────────────────────────────────────────
#

def _useful_lines(exc: BaseException) -> list[str]:
    """오류에서 **원인을 짚을 수 있는 줄**만 골라 낸다.

    지금까지는 traceback 의 마지막 줄을 보여 줬는데, 그것이 하필
    "For further information visit https://errors.pydantic.dev/..." 같은 주소일 때가 있다.
    원장님 화면에 실제로 그것만 떴고, 그래서 어디가 깨졌는지 알 수가 없었다.

    필요한 것은 둘이다 — **무엇이 잘못됐는가**(예외 종류와 첫 줄), 그리고
    **우리 코드 어디인가**(마지막 app/ 프레임). 남의 라이브러리 속 줄은 도움이 안 된다.
    """
    import traceback

    # 진짜 원인은 껍데기 예외 **안쪽**에 있다. Starlette 가 미들웨어를 거치며 다시
    # 던지고, 묶음 예외(ExceptionGroup)로 감싸기도 한다. 그대로 읽으면 "미들웨어에서
    # 났다" 는 쓸모없는 말만 나온다 — 뿌리까지 따라 내려간다.
    root: BaseException = exc
    for _ in range(8):
        inner = getattr(root, "exceptions", None)        # ExceptionGroup
        if inner:
            root = inner[0]
            continue
        nxt = root.__cause__ or root.__context__
        if nxt is None or nxt is root:
            break
        root = nxt
    exc = root

    out: list[str] = []
    first = str(exc).strip().splitlines()
    out.append(f"{type(exc).__name__}: {first[0][:200]}" if first else type(exc).__name__)
    # 값이 왜 거절됐는지는 보통 둘째 줄에 있다(예: "Invalid JSON: ... line 1 column 1").
    for line in first[1:4]:
        if line.strip():
            out.append(line.strip()[:200])

    sep = "app/"
    ours: list[str] = []
    for f in traceback.extract_tb(exc.__traceback__):
        path = f.filename.replace("\\", "/")
        if sep in path:
            where = path.split(sep)[-1]
            ours.append(f"{where}:{f.lineno} 에서 ({f.name})")
    if ours:
        out.append("우리 코드 마지막 자리 — " + ours[-1])
    else:
        # 남의 라이브러리 안에서만 터진 경우도 있다. 그래도 마지막 자리는 알려 준다 —
        # "어디인지 모른다" 보다는 언제나 낫다.
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            last = frames[-1]
            out.append(f"마지막 자리 — {last.filename.split('/')[-1]}:{last.lineno} ({last.name})")
    return [x for x in out if x]


# 스키마 검사에서 걸린 것은 **프로그램이 부서진 것이 아니다** — 값 하나가 안 맞는 것이다.
#
# 원장님 화면에 pydantic 의 `json_invalid` 가 떴다. 그때 화면이 한 말은 "처리하지 못한
# 오류" 였고, 원장은 프로그램이 통째로 망가진 줄 아셨다. 실제로는 어떤 값 하나가
# 모양에 안 맞았을 뿐이고, 그런 것은 **다음 곡을 만드는 데 아무 지장이 없다.**
#
# 그래서 따로 잡아 그 사실을 말한다. 곡은 이미 저장돼 있고, 다시 눌러도 된다.
@app.exception_handler(ValidationError)
async def _bad_shape(request: Request, exc: ValidationError) -> JSONResponse:
    import uuid

    mark = uuid.uuid4().hex[:8]
    log.warning("[%s] %s %s — 값이 모양에 맞지 않는다\n%s", mark, request.method, request.url.path, exc)
    _keep_what_was_made()
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "message": "값 하나가 모양에 맞지 않아 이 요청만 멈췄습니다",
                "what_to_do": (
                    "프로그램이 망가진 것이 아닙니다 — 방금까지 만든 곡은 그대로 있고, "
                    "다시 누르셔도 됩니다. 계속 같은 자리에서 막히면 아래 줄을 보내 주십시오."
                ),
                "issues": [f"오류 표시 {mark}", *_useful_lines(exc)],
            }
        },
    )


def _keep_what_was_made() -> None:
    """무슨 일이 나든 **이미 만든 곡부터 파일에 남긴다.**"""
    try:
        from app.api.deps import get_store

        get_store().save_soon()
    except Exception:  # 곡을 지키려다 오류 처리가 또 넘어지면 안 된다
        log.exception("저장 예약에 실패했다")


# Claude 를 부르지 못한 것은 **프로그램 결함이 아니다** — 키가 거절됐거나, 잔액이 없거나,
# 인터넷이 끊긴 것이다. 그런데 여태 그것이 처리되지 않은 예외로 올라가 `{}` 화면이 됐다.
# 원인마다 원장이 할 일이 다르므로(키 고치기 / 충전하기 / 인터넷 보기), 그 말을 그대로 보낸다.
@app.exception_handler(ClaudeUnavailable)
async def _claude_down(request: Request, exc: ClaudeUnavailable) -> JSONResponse:
    log.warning("%s %s — Claude 호출 실패: %s", request.method, request.url.path, exc.message)
    return JSONResponse(status_code=502, content={"detail": exc.as_detail()})


# 처리하지 못한 예외가 나면 Starlette 는 **평문** "Internal Server Error" 를 돌려준다.
# 화면은 JSON 을 기다리므로 그것을 읽지 못하고, 원장 눈에는 `{}` 만 남는다.
# 무엇이 잘못됐는지도, 다음에 무엇을 할지도 알 수 없는 화면이다 — 실제로 그렇게 막혔다.
#
# 그래서 여기서 붙잡아 **읽을 수 있는 말**로 돌려주고, 자국(traceback)은 파일에 남긴다.
# 원장은 그 파일만 보내면 되고, 화면은 무엇을 할지 알려 준다.
@app.exception_handler(Exception)
async def _any_error(request: Request, exc: Exception) -> JSONResponse:
    import traceback
    import uuid
    from datetime import UTC, datetime

    mark = uuid.uuid4().hex[:8]
    detail = "".join(traceback.format_exception(exc))
    log.error("[%s] %s %s 에서 처리하지 못한 오류\n%s", mark, request.method, request.url.path, detail)
    try:
        from app.config import resolve_data_dir

        book = resolve_data_dir() / "오류기록.txt"
        with book.open("a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.now(UTC).isoformat(timespec='seconds')}] {mark} "
                f"{request.method} {request.url.path}\n{detail}"
            )
        where = str(book)
    except OSError:
        where = ""

    # 곡이 이미 만들어졌다면 그 사실부터 말한다. "오류" 라는 말만 보면 원장은
    # 곡도 돈도 다 날아간 줄 안다 — 실제로는 보관함에 남아 있을 때가 있다.
    # **곡을 먼저 지킨다.**
    #
    # 원장님이 계속 겪으신 것이 이것이다 — "비용은 엄청 나왔는데 결과물은 없다".
    # 작곡은 곡을 다 만들어 저장소에 넣은 **뒤에도** 할 일이 남아 있다(제목·코퍼스 등록).
    # 거기서 넘어지면 응답은 500 이 되고, 저장 미들웨어는 그 요청을 실패로 보고
    # 디스크 쓰기를 건너뛴다. 검증까지 통과한 곡이 그렇게 사라졌다.
    #
    # 그 저장을 여기서 한다. 예외는 미들웨어를 뚫고 올라오므로 **이 자리는 반드시 실행된다.**
    saved = ""
    try:
        from app.api.deps import get_store

        store = get_store()
        store.save_soon()
        if store.compositions:
            last = list(store.compositions)[-1]
            saved = f"방금까지 만든 곡은 보관함에 남아 있습니다({last}). 먼저 보관함을 확인해 주십시오."
    except Exception:  # 곡을 지키려다 오류 처리가 또 넘어지면 안 된다
        saved = ""

    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "message": "프로그램 안에서 처리하지 못한 오류가 났습니다",
                "what_to_do": (
                    (saved + " ") if saved else ""
                ) + (
                    "여기까지 쓴 API 비용은 되돌아오지 않습니다. "
                    "다른 성격으로 다시 만들어 보시고, 계속 같은 자리에서 막히면 "
                    + (f"'{where}' 파일을 보내 주십시오." if where else "실행기록.txt 를 보내 주십시오.")
                ),
                "issues": [f"오류 표시 {mark}", *_useful_lines(exc)],
            }
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def persist_after_write(request, call_next):  # type: ignore[no-untyped-def]
    """쓰기가 일어난 요청 뒤에 저장소 스냅샷을 남긴다.

    라우터들이 버킷 안쪽을 직접 고치므로(예: `store.jobs["guides"][cid] = ...`)
    dict 쓰기를 가로채는 방식으로는 변경을 놓친다. 요청 단위로 통째 저장한다.
    """
    # 오류로 끝난 요청은 여기까지 오지 않는다. 처리되지 않은 예외는 미들웨어를
    # **뚫고 올라가** 바깥의 오류 처리기가 잡는다 — 그래서 '곡을 만든 뒤 터진'
    # 경우의 저장은 이 자리가 아니라 그 처리기에서 한다(아래 `_any_error`).
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400:
        # 저장을 예약만 한다. 곡이 200개면 통째 저장에 2초가 걸리는데,
        # 그것을 응답 앞에 두면 곡이 늘수록 버튼 하나가 느려진다.
        get_store().save_soon()
    return response


app.include_router(health.router)
app.include_router(apikey.router)
app.include_router(books.router)
app.include_router(students.router)
app.include_router(corpus.router)
app.include_router(references.router)
app.include_router(compositions.router)
app.include_router(studio.router)
app.include_router(rights.router)
app.include_router(judge.router)
app.include_router(recitals.router)
app.include_router(feedback.router)
app.include_router(wallet.router)
app.include_router(handoff.router)
app.include_router(folder.router)

# 원장 화면을 API 와 **같은 주소**로 내보낸다. 학원 PC 에서 서버 하나만 띄우면
# 브라우저에서 바로 열린다 — 정적 파일 서버를 따로 돌리지 않아도 된다.
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
if WEB_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")

    @app.get("/", include_in_schema=False)
    def _home() -> RedirectResponse:
        return RedirectResponse("/app/")
else:  # pragma: no cover - 배포 형태에 따라 web/ 이 없을 수 있다
    log.warning("web/ 디렉터리를 찾지 못했다 — 화면 없이 API 만 돈다: %s", WEB_DIR)
