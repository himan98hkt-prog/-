"""곡집 — 낱장 다섯 장과 표지가 붙은 한 권은 다른 물건이다.

학원 원장이 사는 것은 한 권이고, 책장에 꽂는 것도 한 권이다. 그래서 곡집은
한 번 만들고 마는 목록이 아니라 **저장되는 물건**이다 — 이름을 고치고 표지를
바꾸고 곡을 더 넣을 수 있어야 한다.

여기서 지키는 것은 넷이다.
1. 표지는 서로 **알아볼 만큼** 달라야 한다. 색만 바꾼 것은 다른 표지가 아니다.
2. 곡집을 지워도 **곡은 남는다** — 원장이 돈 주고 만든 것이다.
3. 한 권 ZIP 은 풀면 **책의 모양**이 나온다 — 표지·차례·번호 붙은 곡 폴더.
4. 한 벌로 만든 다섯 곡은 **서로 다른 곡**이어야 한다. 같은 성격 다섯 벌은 곡집이 아니다.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from app.api.deps import STORE
from app.export.cover import STYLES, render_cover_svg
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals,
                   STORE.judgements, STORE.rights, STORE.books):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
    with TestClient(app) as c:
        yield c


# ── 표지 ───────────────────────────────────────────────────────────────────


def test_covers_are_really_different_not_just_recolored() -> None:
    """곡집을 여러 권 내면 표지가 같아서는 책장에서 구분되지 않는다."""
    shapes = {}
    for s in STYLES:
        svg = render_cover_svg(title="콩쿨 곡집", style_id=s.id)
        # 색을 뺀 뼈대만 남긴다 — 그것이 서로 달라야 다른 표지다.
        bones = "".join(sorted(tag.split()[0] for tag in svg.split("<")[1:]))
        shapes[s.id] = bones
    assert len(set(shapes.values())) == len(STYLES), (
        f"뼈대가 겹치는 표지가 있다: {shapes.keys()}"
    )


def test_a_cover_is_valid_svg_at_a4() -> None:
    import xml.etree.ElementTree as ET

    svg = render_cover_svg(title="아첼쌤 콩쿨 곡집 1권", subtitle="중급 · 5곡", composer="accelssam")
    root = ET.fromstring(svg)   # 깨진 SVG 면 여기서 죽는다
    assert root.get("viewBox") == "0 0 210 297", "A4 비율이 아니면 인쇄가 어긋난다"
    assert "accelssam" in svg


def test_a_long_title_does_not_run_off_the_cover() -> None:
    svg = render_cover_svg(title="아주아주아주아주아주아주 긴 이름의 콩쿨 곡집 특별판 하나 둘 셋")
    lines = svg.count('font-size="17"')
    assert 1 <= lines <= 3, f"제목이 {lines}줄이다 — 표지를 넘친다"


def test_an_unknown_style_falls_back_instead_of_crashing() -> None:
    svg = render_cover_svg(title="곡집", style_id="그런것없음")
    assert svg.startswith("<svg")


def test_the_title_is_escaped() -> None:
    """제목은 원장이 적는다 — 꺾쇠가 들어가면 표지가 깨진다."""
    svg = render_cover_svg(title='<script>x</script>')
    assert "<script>" not in svg and "&lt;script&gt;" in svg


# ── 곡집 ───────────────────────────────────────────────────────────────────


def _two_pieces(client) -> list[str]:
    client.post("/api/compositions/market", json={"tier_id": "beginner"})
    client.post("/api/compositions/market", json={"tier_id": "middle"})
    return [r["composition_id"] for r in client.get("/api/compositions").json()]


def test_a_book_can_be_made_renamed_and_restyled(client) -> None:
    ids = _two_pieces(client)
    r = client.post("/api/books", json={"title": "1권", "composition_ids": ids})
    assert r.status_code == 200, r.text
    book = r.json()
    assert len(book["pieces"]) == 2
    assert book["cover_style_name"], "표지 이름이 없으면 화면에 뭘 보여 줄 수 없다"

    r = client.put(f"/api/books/{book['id']}", json={"title": "아첼쌤 1권", "cover_style": "stage"})
    assert r.status_code == 200
    assert r.json()["title"] == "아첼쌤 1권"
    assert r.json()["cover_style"] == "stage"


def test_the_order_of_pieces_is_the_table_of_contents(client) -> None:
    """목록이 아니라 차례다 — 순서를 지켜야 한다."""
    ids = _two_pieces(client)
    book = client.post("/api/books", json={"title": "1권", "composition_ids": ids}).json()
    assert [p["composition_id"] for p in book["pieces"]] == ids

    flipped = list(reversed(ids))
    got = client.put(f"/api/books/{book['id']}", json={"composition_ids": flipped}).json()
    assert [p["composition_id"] for p in got["pieces"]] == flipped


def test_deleting_a_book_keeps_the_pieces(client) -> None:
    """묶음을 지웠다고 곡까지 사라지면 원장이 돈 주고 만든 것을 잃는다."""
    ids = _two_pieces(client)
    book = client.post("/api/books", json={"title": "1권", "composition_ids": ids}).json()
    assert client.delete(f"/api/books/{book['id']}").status_code == 200
    assert client.get("/api/books").json() == []
    assert len(client.get("/api/compositions").json()) == len(ids), "곡이 함께 지워졌다"


def test_a_missing_piece_does_not_break_the_book(client) -> None:
    ids = _two_pieces(client)
    book = client.post("/api/books", json={"title": "1권", "composition_ids": ids}).json()
    STORE.compositions.pop(ids[0])
    got = client.get(f"/api/books/{book['id']}").json()
    assert len(got["pieces"]) == 1, "곡 하나가 없다고 곡집이 통째로 안 열리면 안 된다"


def test_a_book_refuses_unknown_pieces_and_styles(client) -> None:
    assert client.post("/api/books", json={"title": "1권", "composition_ids": ["없음"]}).status_code == 404
    ids = _two_pieces(client)
    r = client.post("/api/books", json={"title": "1권", "composition_ids": ids, "cover_style": "없음"})
    assert r.status_code == 422


def test_the_cover_endpoint_serves_svg(client) -> None:
    ids = _two_pieces(client)
    book = client.post("/api/books", json={"title": "1권", "composition_ids": ids}).json()
    r = client.get(f"/api/books/{book['id']}/cover.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "1권" in r.text


# ── 한 권 내려받기 ──────────────────────────────────────────────────────────


def test_one_zip_unpacks_into_the_shape_of_a_book(client) -> None:
    ids = _two_pieces(client)
    book = client.post("/api/books", json={"title": "아첼쌤 1권", "composition_ids": ids}).json()

    r = client.get(f"/api/books/{book['id']}/package")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    root = "아첼쌤 1권"

    assert f"{root}/표지.svg" in names
    assert f"{root}/차례.md" in names
    assert f"{root}/읽어보세요.txt" in names

    # 번호를 앞에 붙여야 탐색기에서 차례 순서대로 줄을 선다.
    folders = sorted({n.split("/")[1] for n in names if n.count("/") > 1})
    assert folders[0].startswith("01 ") and folders[1].startswith("02 ")

    # 곡마다 악보·음원·지도용이 다 들어야 한다 — 하나라도 빠지면 학원에서 드러난다.
    first = [n for n in names if n.startswith(f"{root}/01 ")]
    assert any(n.endswith(".musicxml") and "지도용" not in n for n in first)
    assert any("지도용" in n for n in first)
    assert any(n.endswith((".mp3", ".wav")) for n in first)
    assert any(n.endswith(".mid") for n in first)
    assert any(n.endswith("권리 정보.md") for n in first)

    toc = z.read(f"{root}/차례.md").decode("utf-8")
    assert "차례" in toc and "난이도" in toc


def test_an_empty_book_says_so_instead_of_giving_an_empty_zip(client) -> None:
    book = client.post("/api/books", json={"title": "빈 권"}).json()
    assert client.get(f"/api/books/{book['id']}/package").status_code == 409


# ── 한 벌이 곡집이 된다 ─────────────────────────────────────────────────────


def test_a_set_becomes_a_book_with_different_pieces(client) -> None:
    """같은 성격 다섯 벌은 곡집이 아니다 — 성격이 돌아가며 골라져야 한다."""
    r = client.post(
        "/api/compositions/market/set",
        json={
            "tier_ids": ["beginner", "lower", "middle"],
            "book_title": "아첼쌤 콩쿨 곡집 1권",
            "cover_style": "stage",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["book_id"] and body["book_title"] == "아첼쌤 콩쿨 곡집 1권"

    titles = [row["title"] for row in body["rows"] if row["ok"]]
    assert len(set(titles)) == len(titles), f"곡집에 같은 이름이 둘 있다: {titles}"

    book = client.get(f"/api/books/{body['book_id']}").json()
    assert len(book["pieces"]) == body["made"]
    assert book["cover_style"] == "stage"

    # 박자가 전부 같으면 성격이 안 돌아간 것이다.
    meters = {p["meter"] for p in book["pieces"]}
    assert len(meters) > 1 or len(book["pieces"]) < 3, f"성격이 겹쳤다: {meters}"


def test_books_survive_a_restart(client) -> None:
    """곡집은 저장되는 물건이다 — 프로그램을 껐다 켜면 사라지면 안 된다."""
    from app.api.deps import PERSISTED

    assert "books" in PERSISTED, "곡집이 저장 목록에 없다 — 껐다 켜면 사라진다"


def test_the_same_piece_never_lands_in_one_book_twice(client) -> None:
    """한 권에 같은 곡이 두 번 실린 것은 학원에 보낸 뒤에야 드러난다."""
    ids = _two_pieces(client)
    book = client.post(
        "/api/books", json={"title": "1권", "composition_ids": [ids[0], ids[1], ids[0]]}
    ).json()
    assert [p["composition_id"] for p in book["pieces"]] == [ids[0], ids[1]]

    got = client.put(
        f"/api/books/{book['id']}", json={"composition_ids": [ids[1], ids[1], ids[0]]}
    ).json()
    assert [p["composition_id"] for p in got["pieces"]] == [ids[1], ids[0]]


def test_the_library_is_shown_the_moment_the_program_opens() -> None:
    """저장은 되어 있는데 화면에만 안 나오면 원장은 곡이 사라진 줄 안다.

    실제로 프로그램을 다시 켜면 보관함이 비어 있었다 — 곡을 하나 더 만들기 전까지는.
    """
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "web" / "index.html"
    text = web.read_text(encoding="utf-8")
    boot = text[text.index("// ── 처음 켤 때"):]
    assert "refreshLibrary();" in boot, "켤 때 보관함을 읽지 않는다 — 곡이 사라진 것처럼 보인다"
    assert "refreshBooks();" in boot, "켤 때 곡집을 읽지 않는다"


def test_the_printed_score_can_stretch_to_the_paper() -> None:
    """viewBox 가 없으면 종이 폭에 늘려도 그림은 그대로라 오른쪽이 빈다."""
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "web" / "index.html"
    text = web.read_text(encoding="utf-8")
    assert 'viewBox="0 0 ${width} ${height}"' in text, "악보 SVG 에 viewBox 가 없다"
