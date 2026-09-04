"""참고 악보를 **화면에서** 넣을 수 있는가.

원장님 말씀 그대로다:

    "참고할수 있는 악보들을 업로드 하려고 했는데
     업로드 하는곳이나 폴더를 확인하는곳이 없던데."

서버는 처음부터 업로드를 받을 수 있었다. 그런데 화면에 단추가 없었다.
**있는 기능도 누를 데가 없으면 없는 기능이다.** 그래서 여기서 지키는 것은 둘이다 —
길이 실제로 뚫려 있는가, 그리고 그 길이 화면에서 보이는가.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WEB = Path(__file__).resolve().parents[2] / "web" / "index.html"


@pytest.fixture
def here(tmp_path, monkeypatch):
    """참고 악보 폴더를 임시 자리로 돌린다 — 검사가 원장님 폴더를 건드리면 안 된다.

    **한 군데만 돌린다.** 저장하는 쪽과 훑는 쪽이 같은 함수를 보게 만들어 두었으므로,
    여기를 바꾸면 둘 다 따라온다. 예전처럼 두 군데를 따로 돌려야 했다면 그것 자체가
    설계가 어긋나 있다는 신호였다.
    """
    import sys

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import import_scores

    monkeypatch.setattr(import_scores, "resolve_data_dir", lambda: tmp_path)
    return tmp_path / "reference_scores"


def _xml() -> bytes:
    """music21 이 읽을 수 있는 가장 작은 악보."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
 "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1"><part-list>
<score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1">
<attributes><divisions>1</divisions><key><fifths>0</fifths></key>
<time><beats>4</beats><beat-type>4</beat-type></time>
<clef><sign>G</sign><line>2</line></clef></attributes>
<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
</measure></part></score-partwise>"""


def test_the_owner_can_upload_a_score_from_the_screen(here) -> None:
    """파일을 골라 올리면 폴더에 저장되고 **그 자리에서** 읽힌다."""
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("모차르트 소나타.musicxml", _xml(), "application/xml")},
            data={"copyright_status": "public_domain"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] == ["모차르트 소나타.musicxml"]
    assert (here / "모차르트 소나타.musicxml").exists(), "파일이 폴더에 저장되지 않았다"


def test_the_file_really_lands_on_disk_not_only_in_memory(here) -> None:
    """메모리에만 넣으면 껐다 켜는 순간 사라진다 — 원장님은 올렸다고 알고 계신데."""
    from app.main import app

    with TestClient(app) as c:
        c.post(
            "/api/references/upload",
            files={"files": ("곡.musicxml", _xml(), "application/xml")},
            data={"copyright_status": "own"},
        )

    saved = here / "곡.musicxml"
    assert saved.exists()
    # 저작권 표시가 옆에 남아야 다음에 읽을 때도 같은 대우를 받는다.
    side = saved.with_suffix(".json")
    assert side.exists(), "저작권 표시를 남기지 않았다 — 다시 읽으면 저작권곡이 되어 버린다"
    assert "own" in side.read_text(encoding="utf-8")


def test_an_unreadable_file_is_refused_with_a_reason(here) -> None:
    """읽을 수 없는 것을 조용히 삼키면 원장님은 올라간 줄 아신다."""
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("악보 사진.jpg", b"\xff\xd8\xff\xe0 ...", "image/jpeg")},
            data={"copyright_status": "copyrighted"},
        )

    body = r.json()
    assert body["saved"] == []
    assert body["rejected"], "거절했으면서 왜 안 됐는지 말하지 않는다"
    assert "MusicXML" in body["rejected"][0], f"무엇을 올려야 하는지 안 알려준다: {body['rejected']}"
    assert "PDF" in body["rejected"][0], "PDF 는 되는데 안 된다고 읽힌다"


def test_a_broken_pdf_is_reported_not_listed_as_an_empty_row(here) -> None:
    """쪽 수조차 못 읽은 PDF 를 목록에 넣으면 '—' 만 늘어선 칸이 생긴다.

    파일은 지우지 않는다 — 원장님 파일이다. 다만 읽지 못했다고 세어 알린다.
    """
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("깨진.pdf", b"%PDF-1.4 ...", "application/pdf")},
            data={"copyright_status": "copyrighted"},
        ).json()

    assert r["saved"] == ["깨진.pdf"], "파일은 남겨 두어야 한다"
    assert r["added"] == 0, "읽지도 못한 것을 읽었다고 한다"
    assert r["failed"] == 1, f"읽지 못했다는 사실을 세지 않는다: {r}"


def test_default_is_the_safe_side(here) -> None:
    """저작권 상태를 안 고르면 **저작권곡**으로 본다(절대 규칙 3).

    반대로 기울면 남의 곡 음표가 프롬프트에 들어간다. 안전한 쪽이 기본이어야 한다.
    """
    from app.main import app

    with TestClient(app) as c:
        c.post("/api/references/upload", files={"files": ("무표시.musicxml", _xml(), "application/xml")})

    side = (here / "무표시.json").read_text(encoding="utf-8")
    assert "copyrighted" in side


def test_a_bad_status_is_refused(here) -> None:
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("곡.musicxml", _xml(), "application/xml")},
            data={"copyright_status": "아무거나"},
        )
    assert r.status_code == 422


def test_uploading_the_same_name_twice_does_not_overwrite(here) -> None:
    """원장님이 먼저 넣어 두신 파일을 우리가 덮어쓰지 않는다."""
    from app.main import app

    with TestClient(app) as c:
        for _ in range(2):
            c.post(
                "/api/references/upload",
                files={"files": ("같은이름.musicxml", _xml(), "application/xml")},
                data={"copyright_status": "own"},
            )

    names = sorted(p.name for p in here.glob("*.musicxml"))
    assert names == ["같은이름 (2).musicxml", "같은이름.musicxml"], names


def test_the_screen_says_where_the_folder_is_and_what_it_read(here) -> None:
    """"넣긴 넣었는데 반영이 된 건가?" 에 답해야 한다."""
    from app.main import app

    with TestClient(app) as c:
        w = c.get("/api/references/where").json()

    assert "reference_scores" in w["folder"]
    assert "files" in w and "loaded" in w, "몇 개가 있고 몇 개를 읽었는지 말하지 않는다"


def test_rescan_exists_for_people_who_use_explorer(here) -> None:
    """탐색기로 직접 넣는 분도 껐다 켜지 않아도 되어야 한다."""
    from app.main import app

    with TestClient(app) as c:
        r = c.post("/api/references/rescan")
    assert r.status_code == 200
    assert set(r.json()) >= {"added", "skipped", "failed"}


# ── 화면에 단추가 실제로 있는가 ───────────────────────────────────────────


def test_the_screen_actually_has_the_buttons() -> None:
    """서버만 되고 화면에 단추가 없으면 원장님께는 없는 기능이다.

    이 검사가 지키는 것이 정확히 원장님이 겪으신 그 일이다.
    """
    page = WEB.read_text(encoding="utf-8")
    for what, mark in (
        ("파일 고르는 칸", 'id="refFiles"'),
        ("올리기 단추", 'id="btnRefUpload"'),
        ("폴더 여는 단추", 'id="btnRefOpen"'),
        ("다시 읽는 단추", 'id="btnRefRescan"'),
        ("저작권 고르는 칸", 'id="refRights"'),
    ):
        assert mark in page, f"화면에 {what} 이 없다"

    assert "/api/references/upload" in page, "올리기 단추가 서버로 가지 않는다"
    assert "which=references" in page, "폴더 열기가 참고 악보 폴더를 가리키지 않는다"


def test_the_screen_no_longer_tells_the_owner_to_restart() -> None:
    """이제 껐다 켤 필요가 없다 — 그렇게 적혀 있으면 거짓이다."""
    page = WEB.read_text(encoding="utf-8")
    assert "넣고 프로그램을 다시 켜면" not in page
    assert "넣고 프로그램을 다시 켜면 여기에 나옵니다" not in page


# ── 폴더가 통째로 고장나 있던 것 ──────────────────────────────────────────


def test_the_folder_actually_loads_scores_not_just_saves_them(here) -> None:
    """**저장만 되고 읽히지 않던 것을 잡는다.**

    참고 악보 폴더를 프로그램 폴더 바깥(AppData)으로 옮기면서 적재 코드에
    `path.relative_to(ROOT)` 한 줄이 남았다. ROOT 는 프로그램 폴더인데 악보는 그
    바깥에 있으니 **항상** ValueError 가 났고, 폴더에 넣은 악보가 하나도 읽히지
    않았다. 시작할 때는 조용히 도니 아무 말도 없었다 — 원장님은 "넣었는데 아무것도
    안 나온다" 만 보셨다.

    `saved` 만 보는 검사는 이것을 못 잡는다. **읽혔는지**를 봐야 한다.
    """
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("소나티네.musicxml", _xml(), "application/xml")},
            data={"copyright_status": "public_domain"},
        ).json()

    assert r["saved"], "저장조차 안 됐다"
    assert r["added"] == 1, f"저장은 됐는데 읽히지 않았다 — 폴더가 고장난 그 증상이다: {r}"

    with TestClient(app) as c:
        listed = c.get("/api/corpus").json()
    assert any("소나티네" in s["title"] for s in listed), "읽었다면서 목록에 없다"


def test_no_code_measures_the_score_folder_against_the_program_folder() -> None:
    """참고 악보 폴더는 프로그램 폴더 **바깥**이다 — ROOT 기준으로 재면 항상 터진다.

    같은 함정이 세 군데 있었다. 다시 기어들어오지 못하게 막아 둔다.
    """
    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "import_scores.py"
    ).read_text(encoding="utf-8")
    code = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    offenders = [ln.strip() for ln in code if "relative_to(ROOT)" in ln]
    assert not offenders, f"프로그램 폴더 기준으로 재는 줄이 남았다: {offenders}"


def test_the_owner_can_find_it_from_the_dashboard() -> None:
    """길잡이에 없으면 접힌 구역을 페이지 내려가며 찾아야 한다.

    원장님이 못 찾으신 이유가 이것이다 — 학생 정보 **아래**에 접힌 채 있었다.
    """
    page = WEB.read_text(encoding="utf-8")
    nav = page.split('class="gonav"')[1].split("</nav>")[0]
    assert 'data-go="refBox"' in nav, "대시보드 길잡이에 참고 악보로 가는 단추가 없다"
    assert "참고 악보" in nav
