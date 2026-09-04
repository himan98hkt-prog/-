"""PDF 악보를 **통계만** 받는다.

원장님이 물으셨다: "악보가 pdf인데 이건 못 읽는거야?"

못 읽는 것이 맞았다 — 그리고 그건 원장님 악보의 **대부분**이 PDF 라는 뜻이므로,
참고 악보 기능이 원장님께는 사실상 없는 기능이었다는 뜻이기도 하다.

PDF 는 그림이라 음표를 알 수 없다. 악보 인식(OMR)을 붙이면 음표를 짐작할 수는
있지만 정확도가 들쭉날쭉해서 **잘못 읽은 음이 참고 자료로 섞인다** — 그건 없느니만
못하다. 그래서 확실한 것만 받기로 했다.

여기서 지키는 것 셋:
  1. PDF 를 거절하지 않는다
  2. 확실한 것은 가져온다 — 쪽 수, 제목, 글자로 찍힌 박자·빠르기·마디 번호
  3. **모르는 것은 지어내지 않는다.** 그리고 음표는 절대 만들어 넣지 않는다
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WEB = Path(__file__).resolve().parents[2] / "web" / "index.html"


def _pdf(objs: list[bytes]) -> bytes:
    out = b"%PDF-1.4\n"
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{x}\n%%EOF").encode()
    return out


def engraved_pdf(pages: list[list[str]]) -> bytes:
    """MuseScore 등으로 짜서 낸 PDF — 글자층이 있다."""
    n = len(pages)
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, lines in enumerate(pages):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {3 + n * 2} 0 R >> >> "
            f"/Contents {4 + i * 2} 0 R >>".encode()
        )
        body = "BT /F1 12 Tf 1 0 0 1 60 780 Tm 14 TL\n"
        for ln in lines:
            body += f"({ln}) Tj T*\n"
        body += "ET"
        st = body.encode("latin-1", "replace")
        objs.append(b"<< /Length " + str(len(st)).encode() + b" >>\nstream\n" + st + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return _pdf(objs)


def scanned_pdf(n: int) -> bytes:
    """종이를 스캔한 PDF — 글자층이 없다. 쪽 수 말고는 알 수 있는 것이 없다."""
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i in range(n):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {4 + i * 2} 0 R >>".encode()
        )
        st = b"0 0 1 rg 100 100 200 200 re f"
        objs.append(b"<< /Length " + str(len(st)).encode() + b" >>\nstream\n" + st + b"\nendstream")
    return _pdf(objs)


SONATINA = [
    ["Sonatina in C major", "Muzio Clementi (1752-1832)", "Allegro   4/4", "1", "5", "9"],
    ["17", "21", "25", "29", "33", "37", "41", "45"],
]


@pytest.fixture
def here(tmp_path, monkeypatch):
    import sys

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import import_scores

    monkeypatch.setattr(import_scores, "resolve_data_dir", lambda: tmp_path)

    # 코퍼스는 전역이라 앞선 검사가 넣어 둔 곡이 남아 있다. 같은 이름이 섞이면
    # 이 검사가 남의 항목을 보고 판정한다 — 비우고 시작한다.
    from app.api.corpus import get_corpus

    get_corpus().scores.clear()
    get_corpus()._ngrams.clear()
    return tmp_path / "reference_scores"


# ── 읽어 내는 것 ──────────────────────────────────────────────────────────


def test_an_engraved_pdf_gives_up_its_facts(tmp_path) -> None:
    """MuseScore 로 낸 PDF 는 글자층이 있어 꽤 많이 알아낼 수 있다."""
    from app.ingest.pdf_stats import read_pdf_stats

    f = tmp_path / "s.pdf"
    f.write_bytes(engraved_pdf(SONATINA))
    st = read_pdf_stats(f)

    assert st.pages == 2
    assert st.has_text_layer
    assert "Sonatina" in st.title
    assert "Clementi" in st.composer
    assert st.meter == "4/4"
    assert st.tempo > 0, "Allegro 라고 적혀 있는데 빠르기를 못 읽었다"
    assert st.measures == 45, f"인쇄된 마디 번호를 못 읽었다: {st.measures}"


def test_a_scanned_pdf_says_plainly_what_it_cannot_know(tmp_path) -> None:
    """스캔한 악보는 쪽 수뿐이다. **그 사실을 숨기지 않는다.**"""
    from app.ingest.pdf_stats import read_pdf_stats

    f = tmp_path / "scan.pdf"
    f.write_bytes(scanned_pdf(3))
    st = read_pdf_stats(f)

    assert st.pages == 3
    assert not st.has_text_layer
    assert st.measures == 0 and st.tempo == 0 and st.meter == ""
    assert any("스캔" in n for n in st.notes), f"왜 못 읽는지 말하지 않는다: {st.notes}"


def test_it_never_invents_what_it_did_not_find(tmp_path) -> None:
    """**지어내지 않는다.** 참고 자료에 거짓이 섞이면 없느니만 못하다."""
    from app.ingest.pdf_stats import read_pdf_stats

    f = tmp_path / "bare.pdf"
    f.write_bytes(engraved_pdf([["Something Untitled"]]))
    st = read_pdf_stats(f)

    assert st.measures == 0, "없는 마디 수를 만들어 냈다"
    assert st.tempo == 0, "없는 빠르기를 만들어 냈다"
    assert st.meter == "", "없는 박자를 만들어 냈다"


def test_a_broken_pdf_does_not_take_the_program_down(tmp_path) -> None:
    from app.ingest.pdf_stats import read_pdf_stats

    f = tmp_path / "깨진.pdf"
    f.write_bytes("%PDF-1.4\n이건 PDF 가 아니다".encode())
    st = read_pdf_stats(f)
    assert st.pages == 0
    assert st.notes, "열지 못했으면 그 사실을 말해야 한다"


# ── 음표는 절대 만들어 넣지 않는다 ────────────────────────────────────────


def test_a_pdf_entry_carries_no_notes_at_all(tmp_path) -> None:
    """PDF 에서 음표를 짐작해 넣으면 그 순간 참고 자료가 오염된다.

    표절 검사에도 들어가면 안 된다 — 있지도 않은 음으로 남의 곡을 잡게 된다.
    """
    from app.ingest.corpus import Corpus

    f = tmp_path / "s.pdf"
    f.write_bytes(engraved_pdf(SONATINA))
    c = Corpus()
    entry = c.add_pdf_stats(f, score_id="pdf-1", copyright_status="public_domain")

    assert entry.measures is None, "PDF 에서 음표를 만들어 냈다"
    assert not entry.summary()["has_notes"]
    assert "pdf-1" not in c._ngrams, "음표가 없는데 표절 인덱스에 넣었다"
    assert entry.needs_review, "글자에서 짐작한 값인데 검수 표시를 안 했다"


def test_the_facts_it_did_find_are_kept(tmp_path) -> None:
    from app.ingest.corpus import Corpus

    f = tmp_path / "s.pdf"
    f.write_bytes(engraved_pdf(SONATINA))
    entry = Corpus().add_pdf_stats(f, score_id="pdf-2")

    assert entry.profile.measures == 45
    assert entry.profile.meter == "4/4"
    assert "Sonatina" in entry.title


def test_defaults_never_masquerade_as_facts(tmp_path) -> None:
    """**표시 단계에서 거짓이 새어나오지 않는가.**

    StyleProfile 의 기본값은 C장조·4/4·♩=100·난이도 1.0 이다. 스캔한 악보처럼
    아무것도 못 읽은 PDF 에 그 기본값이 그대로 남으면, 화면은 그것을 **알아낸
    사실처럼** 보여 준다. 원장님은 "C장조 4/4 난이도 1.0" 이 이 악보의 성질인 줄
    아시게 된다. 지어내지 않겠다는 약속이 여기서 깨진다.
    """
    from app.ingest.corpus import Corpus

    f = tmp_path / "scan.pdf"
    f.write_bytes(scanned_pdf(3))
    entry = Corpus().add_pdf_stats(f, score_id="pdf-3")

    assert entry.profile.key == "", "못 읽은 조성을 C장조로 채웠다"
    assert entry.profile.meter == "", "못 읽은 박자를 4/4 로 채웠다"
    assert entry.profile.tempo == 0, "못 읽은 빠르기를 100 으로 채웠다"
    assert entry.difficulty == 0, "재지도 않은 난이도를 1.0 으로 채웠다"


def test_the_screen_does_not_promise_melody_for_a_pdf() -> None:
    """PDF 옆에 '선율까지 참고' 라고 적으면 그 자리에서 앞뒤가 안 맞는다.

    음표가 없다고 적어 두고 바로 옆에서 선율을 참고한다고 하면, 원장님은 둘 중
    무엇이 맞는지 알 수가 없다.
    """
    page = WEB.read_text(encoding="utf-8")
    row = page.split("refs.map(r =>")[1].split("</tr>")[0]
    assert "r.has_notes" in row, "음표 유무에 따라 다르게 보여 주지 않는다"
    assert "PDF · 통계만" in row


# ── 화면에서 올리는 길 ────────────────────────────────────────────────────


def test_the_owner_can_upload_a_pdf_from_the_screen(here) -> None:
    """원장님이 실제로 하실 일 그대로."""
    from app.main import app

    with TestClient(app) as c:
        r = c.post(
            "/api/references/upload",
            files={"files": ("소나티네.pdf", engraved_pdf(SONATINA), "application/pdf")},
            data={"copyright_status": "copyrighted"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] == ["소나티네.pdf"], f"PDF 를 거절했다: {body}"
    assert body["added"] == 1, f"저장은 했는데 읽지 않았다: {body}"
    assert (here / "소나티네.pdf").exists()


def test_a_pdf_shows_up_in_the_list_marked_as_stats_only(here) -> None:
    from app.main import app

    with TestClient(app) as c:
        c.post(
            "/api/references/upload",
            files={"files": ("소나티네.pdf", engraved_pdf(SONATINA), "application/pdf")},
            data={"copyright_status": "public_domain"},
        )
        rows = c.get("/api/corpus").json()

    row = next(x for x in rows if "소나티네" in x["title"] or "Sonatina" in x["title"])
    assert row["has_notes"] is False, "화면이 음표가 있는 것처럼 보여 준다"
    assert row["measures"] == 45


def test_the_screen_accepts_pdf_and_says_what_it_can_do() -> None:
    """받아 주면서 무엇까지 되는지 말하지 않으면 원장님이 기대를 잘못 갖는다."""
    page = WEB.read_text(encoding="utf-8")
    assert ".pdf" in page.split('id="refFiles"')[1][:200], "파일 고르는 칸이 PDF 를 안 받는다"
    assert "PDF 는 어디까지 되나요" in page, "PDF 가 어디까지 되는지 화면에 설명이 없다"
    assert "MuseScore" in page, "선율까지 쓰려면 어떻게 하는지 알려주지 않는다"
    assert "PDF · 통계만" in page, "표에서 통계뿐인 항목을 구분해 주지 않는다"


def test_a_pdf_is_not_filtered_out_of_the_search_for_being_unmeasured(tmp_path) -> None:
    """**모르는 것과 쉬운 것은 다르다.**

    PDF 는 음표가 없어 난이도를 잴 수 없고 값이 0 으로 남는다. 그것을 '난이도 0
    (아주 쉬움)' 으로 읽으면, 중급 곡을 만들 때 원장님이 올리신 PDF 가 난이도
    필터에 전부 걸려 **한 번도 쓰이지 않는다.** 올리는 자리를 만들어 놓고 정작
    쓰지 않으면 기능이 있는 척만 하는 것이다.
    """
    from app.analysis.style_profile import StyleProfile
    from app.ingest.corpus import Corpus

    c = Corpus()
    f = tmp_path / "중급.pdf"
    f.write_bytes(engraved_pdf(SONATINA))
    c.add_pdf_stats(f, score_id="pdf-mid", copyright_status="copyrighted")

    # 중급(난이도 5) 곡을 만드는 상황 — 예전에는 여기서 PDF 가 통째로 걸러졌다.
    found = c.search(StyleProfile(measures=0), difficulty=5.0)
    ids = [s.id for s, _ in found]
    assert "pdf-mid" in ids, f"난이도를 모른다고 PDF 를 빼 버렸다: {ids}"
