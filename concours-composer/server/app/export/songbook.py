"""곡집 한 권을 파일 하나로 — 표지·차례·곡별 폴더.

원장이 사서 여는 것은 ZIP 하나다. 풀면 책 한 권의 모양이 그대로 나와야 한다.

    콩쿨 곡집 중급/
      표지.svg              ← 브라우저로 열어 인쇄하면 A4 표지가 된다
      차례.md
      읽어보세요.txt
      01 작은 행진/  02 봄날의 왈츠/  …   ← 각 곡의 악보·음원·지도용·권리

번호를 폴더 이름 앞에 붙이는 이유는 하나다 — 그래야 탐색기에서 **차례 순서대로**
줄을 선다. 이름순 정렬은 사람이 정한 순서를 흐트러뜨린다.
"""

from __future__ import annotations

import io
import zipfile

from app.export.package import PackageInput, _safe, write_piece
from app.schemas.book import Songbook


def contents_markdown(book: Songbook, pieces: list[PackageInput], composer: str) -> str:
    rows = [f"# {book.title}", ""]
    if book.subtitle:
        rows.append(f"*{book.subtitle}*")
        rows.append("")
    rows += [f"작곡 {composer} · {len(pieces)}곡", "", "## 차례", ""]
    rows.append("| 번호 | 곡 | 조성·박자 | 마디 | 난이도 | 사전 심사 |")
    rows.append("|---:|---|---|---:|---:|---|")
    for i, p in enumerate(pieces, 1):
        judged = (
            "통과" if p.judge_passed
            else (f"미달 {p.judge_average}" if p.judge_average is not None else "—")
        )
        rows.append(
            f"| {i} | {p.title} | {p.key} {p.meter} ♩={p.tempo} | "
            f"{p.measures} | {p.difficulty} | {judged} |"
        )
    total = sum(p.duration_sec for p in pieces)
    rows += ["", f"전체 연주 시간 약 {total // 60}분 {total % 60}초", ""]
    if book.note:
        rows += ["## 메모", "", book.note, ""]
    return "\n".join(rows)


def _readme(book: Songbook, pieces: list[PackageInput], composer: str) -> str:
    lines = [
        f"{book.title}",
        "=" * 40,
        "",
        f"작곡 {composer} · {len(pieces)}곡",
        "",
        "무엇부터 열면 되는지",
        "  1. 표지.svg     — 두 번 누르면 브라우저에 뜹니다. 인쇄하면 A4 표지가 됩니다.",
        "  2. 차례.md      — 어떤 곡이 몇 마디이고 난이도가 얼마인지 한 장에 있습니다.",
        "  3. 번호 폴더    — 곡마다 악보(musicxml)·음원·MIDI·지도용 악보가 들어 있습니다.",
        "",
        "악보 파일(.musicxml)은 뮤즈스코어·시벨리우스·피날레에서 열립니다.",
        "무료로 보시려면 MuseScore 를 받으십시오 — musescore.org",
        "",
        "'지도용' 이 붙은 악보에는 손가락 번호와 가르칠 때 짚을 곳이 적혀 있습니다.",
        "학생에게는 그것 말고 원본을 주십시오.",
        "",
        "권리",
        "  곡마다 '권리 정보.md' 가 들어 있습니다. 편곡이라면 원곡의 권리 상태를",
        "  반드시 확인하고 쓰십시오.",
        "",
    ]
    return "\n".join(lines)


def build_book(
    book: Songbook, pieces: list[PackageInput], cover_svg: str, composer: str
) -> tuple[bytes, str]:
    """곡집 ZIP 과 파일 이름."""
    root = _safe(book.title) or "콩쿨 곡집"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{root}/표지.svg", cover_svg)
        z.writestr(f"{root}/차례.md", contents_markdown(book, pieces, composer))
        z.writestr(f"{root}/읽어보세요.txt", _readme(book, pieces, composer))
        for i, p in enumerate(pieces, 1):
            # 번호를 앞에 붙여야 탐색기에서 차례 순서대로 줄을 선다.
            write_piece(z, f"{root}/{i:02d} {_safe(p.title)}", p, readme=False)
    return buf.getvalue(), f"{root}.zip"
