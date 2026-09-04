"""곡집 — 만든 곡을 한 권으로 묶고, 표지를 붙이고, 통째로 내려받는다.

낱장 다섯 장과 한 권은 다른 물건이다. 학원 원장이 사는 것은 뒤쪽이다.

여기서 하는 일은 넷이다. 묶고(만들기), 이름·표지를 고치고, 표지를 보여 주고,
한 권을 ZIP 하나로 내준다. 곡 자체는 보관함에 그대로 있고 곡집에는 번호만 든다 —
한 곡이 여러 곡집에 들어갈 수 있고, 곡을 고치면 그 곡이 든 모든 곡집에 반영된다.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import Store, get_store
from app.export.cover import BY_STYLE, DEFAULT_STYLE, STYLES, render_cover_svg
from app.schemas.book import Songbook

router = APIRouter(prefix="/api/books", tags=["books"])


class BookIn(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(default="", max_length=120)
    cover_style: str = DEFAULT_STYLE
    composition_ids: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=2000)


class BookPatch(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=80)
    subtitle: str | None = Field(default=None, max_length=120)
    cover_style: str | None = None
    composition_ids: list[str] | None = None
    note: str | None = Field(default=None, max_length=2000)


class BookPiece(BaseModel):
    composition_id: str
    title: str
    key: str
    meter: str
    tempo: int
    measures: int
    difficulty: float
    judge_passed: bool | None = None
    market_tier: str = ""


class BookOut(BaseModel):
    id: str
    title: str
    subtitle: str
    cover_style: str
    cover_style_name: str
    note: str
    created_at: str
    pieces: list[BookPiece]
    # 팔 준비가 된 곡 수. 사전 심사를 통과하지 못한 곡이 섞인 채로 팔면 안 된다.
    sellable: int


class CoverStyleOut(BaseModel):
    id: str
    name: str
    blurb: str


def _dedupe(ids: list[str]) -> list[str]:
    """같은 곡이 한 권에 두 번 들어가지 않게. 차례 순서는 그대로 지킨다.

    화면에서 여러 번 고르거나 이미 든 곡을 다시 넣으면 생긴다. 한 권에 같은 곡이
    두 번 실린 것은 원장이 학원에 보낸 뒤에야 드러난다.
    """
    seen: set[str] = set()
    out: list[str] = []
    for c in ids:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _books(store: Store) -> dict[str, Songbook]:
    raw = store.books
    for key, value in list(raw.items()):
        if isinstance(value, dict):   # 저장 파일에서 되살아난 것
            raw[key] = Songbook(**value)
    return raw  # type: ignore[return-value]


def _piece(store: Store, cid: str) -> BookPiece | None:
    """곡이 지워졌거나 아직 없으면 조용히 뺀다 — 곡집이 통째로 안 열리면 안 된다."""
    res = store.compositions.get(cid)
    if res is None:
        return None
    from app.api.studio import judge_summary
    from app.config import get_settings

    _, passed = judge_summary(store, cid, get_settings())
    tier = ""
    from app.generation.market import BY_TIER

    for j in store.jobs.get("auto_history", []):
        if isinstance(j, dict) and j.get("composition_id") == cid and j.get("market_tier"):
            got = BY_TIER.get(str(j["market_tier"]))
            if got:
                tier = got.name
    return BookPiece(
        composition_id=cid,
        title=store.title_of(cid),
        key=res.plan.key,
        meter=res.plan.meter,
        tempo=res.plan.tempo,
        measures=len(res.measures),
        difficulty=res.difficulty,
        judge_passed=passed,
        market_tier=tier,
    )


def _out(store: Store, book: Songbook) -> BookOut:
    pieces = [p for p in (_piece(store, cid) for cid in book.composition_ids) if p]
    style = BY_STYLE.get(book.cover_style, BY_STYLE[DEFAULT_STYLE])
    return BookOut(
        id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        cover_style=style.id,
        cover_style_name=style.name,
        note=book.note,
        created_at=book.created_at,
        pieces=pieces,
        sellable=sum(1 for p in pieces if p.judge_passed),
    )


@router.get("/cover-styles", response_model=list[CoverStyleOut])
def cover_styles() -> list[CoverStyleOut]:
    """표지 종류. 곡집을 여러 권 내면 표지가 같아서는 서로 구분되지 않는다."""
    return [CoverStyleOut(id=s.id, name=s.name, blurb=s.blurb) for s in STYLES]


@router.get("", response_model=list[BookOut])
def list_books(store: Store = Depends(get_store)) -> list[BookOut]:
    books = _books(store)
    return [_out(store, b) for b in sorted(books.values(), key=lambda b: b.id, reverse=True)]


@router.post("", response_model=BookOut)
def create_book(body: BookIn, store: Store = Depends(get_store)) -> BookOut:
    missing = [c for c in body.composition_ids if c not in store.compositions]
    if missing:
        raise HTTPException(404, f"곡을 찾을 수 없다: {', '.join(missing)}")
    if body.cover_style not in BY_STYLE:
        raise HTTPException(422, f"그런 표지는 없다: {body.cover_style}")

    books = _books(store)
    bid = store.next_id("book", books)
    book = Songbook(
        id=bid,
        title=body.title,
        subtitle=body.subtitle,
        cover_style=body.cover_style,
        composition_ids=_dedupe(body.composition_ids),
        note=body.note,
    )
    books[bid] = book
    store.save_soon()
    return _out(store, book)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: str, store: Store = Depends(get_store)) -> BookOut:
    book = _books(store).get(book_id)
    if book is None:
        raise HTTPException(404, f"곡집을 찾을 수 없다: {book_id}")
    return _out(store, book)


@router.put("/{book_id}", response_model=BookOut)
def update_book(book_id: str, body: BookPatch, store: Store = Depends(get_store)) -> BookOut:
    books = _books(store)
    book = books.get(book_id)
    if book is None:
        raise HTTPException(404, f"곡집을 찾을 수 없다: {book_id}")
    if body.cover_style is not None and body.cover_style not in BY_STYLE:
        raise HTTPException(422, f"그런 표지는 없다: {body.cover_style}")
    if body.composition_ids is not None:
        missing = [c for c in body.composition_ids if c not in store.compositions]
        if missing:
            raise HTTPException(404, f"곡을 찾을 수 없다: {', '.join(missing)}")

    fields = body.model_dump(exclude_none=True)
    if "composition_ids" in fields:
        fields["composition_ids"] = _dedupe(fields["composition_ids"])
    books[book_id] = book.model_copy(update=fields)
    store.save_soon()
    return _out(store, books[book_id])


@router.delete("/{book_id}")
def delete_book(book_id: str, store: Store = Depends(get_store)) -> dict:
    """곡집만 없앤다 — **곡은 그대로 남는다.**

    묶음을 지웠다고 곡까지 사라지면 원장이 돈 주고 만든 것을 잃는다.
    """
    books = _books(store)
    if book_id not in books:
        raise HTTPException(404, f"곡집을 찾을 수 없다: {book_id}")
    del books[book_id]
    store.save_soon()
    return {"deleted": book_id, "note": "곡집만 없앴습니다 — 곡은 보관함에 그대로 있습니다"}


def _cover_of(store: Store, book: Songbook) -> str:
    from app.api.rights import get_composer

    out = _out(store, book)
    pieces = [
        (p.title, f"{p.measures}마디 · 난이도 {p.difficulty}")
        for p in out.pieces
    ]
    return render_cover_svg(
        title=book.title,
        subtitle=book.subtitle or (f"{len(pieces)}곡" if pieces else ""),
        composer=get_composer(store).display(),
        style_id=book.cover_style,
        pieces=pieces,
    )


@router.get("/{book_id}/cover.svg")
def get_cover(book_id: str, store: Store = Depends(get_store)) -> Response:
    """표지 한 장. 브라우저가 그대로 그리고, 인쇄하면 벡터로 나간다."""
    book = _books(store).get(book_id)
    if book is None:
        raise HTTPException(404, f"곡집을 찾을 수 없다: {book_id}")
    return Response(content=_cover_of(store, book), media_type="image/svg+xml")


@router.get("/{book_id}/package")
def get_book_package(book_id: str, store: Store = Depends(get_store)) -> Response:
    """곡집 한 권을 ZIP 하나로 — 표지·차례·곡별 폴더.

    원장이 사서 여는 것은 파일 하나다. 풀면 책 한 권의 모양이 그대로 나와야 한다.
    """
    book = _books(store).get(book_id)
    if book is None:
        raise HTTPException(404, f"곡집을 찾을 수 없다: {book_id}")

    from app.api.compositions import package_input
    from app.api.rights import get_composer
    from app.export.songbook import build_book

    ids = [c for c in book.composition_ids if c in store.compositions]
    if not ids:
        raise HTTPException(409, "곡집에 든 곡이 하나도 없습니다")

    pieces = [package_input(store, cid) for cid in ids]
    data, filename = build_book(book, pieces, _cover_of(store, book), get_composer(store).display())
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{book_id}.zip\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )
