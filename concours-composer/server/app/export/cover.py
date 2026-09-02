"""곡집 표지 — 여러 곡을 한 권으로 묶어 파는 데 필요한 얼굴.

낱장 악보 다섯 장과 표지가 붙은 한 권은 다른 물건이다. 학원 원장이 사는 것은 뒤쪽이다.
그래서 표지를 만든다.

**왜 SVG 인가.** 원장 PC 에 그림 도구를 깔게 할 수 없다. SVG 는 글자와 선만으로 그려지고,
브라우저가 그대로 그리며, 인쇄하면 벡터 그대로 나간다 — 확대해도 깨지지 않는다.
필요한 것은 파이썬 문자열 하나뿐이라 새 부품도 필요 없다.

**왜 여러 가지인가.** 곡집을 여러 권 내면 표지가 같아서는 서로 구분되지 않는다.
학원 책장에 나란히 꽂혔을 때 어느 것이 초급이고 어느 것이 상급인지 **표지만 보고**
알아야 한다. 그래서 다섯 가지를 서로 다른 뼈대로 만들었다 — 색만 바꾼 것이 아니다.

크기는 A4 비율(210×297)이다. 인쇄하면 그대로 한 장이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

W, H = 210.0, 297.0   # A4 (mm)


@dataclass(frozen=True)
class CoverStyle:
    id: str
    name: str
    blurb: str        # 원장에게 보이는 한 줄
    ink: str          # 글자
    paper: str        # 바탕
    accent: str       # 강조


STYLES: tuple[CoverStyle, ...] = (
    CoverStyle("classic", "고전", "금박 테두리와 명조 — 콩쿨 제출본에 어울립니다",
               ink="#1f1a14", paper="#faf6ec", accent="#a8853c"),
    CoverStyle("stage", "무대", "커튼의 진홍 — 대회용 묶음에 어울립니다",
               ink="#f6efe6", paper="#5d1a26", accent="#d9b25e"),
    CoverStyle("pastel", "파스텔", "어린 학생용 — 초급 곡집에 어울립니다",
               ink="#3b3630", paper="#f4f0f7", accent="#8f7fb5"),
    CoverStyle("modern", "모던", "굵은 획과 여백 — 학원 홍보물에 어울립니다",
               ink="#141414", paper="#f2f2ef", accent="#c2451f"),
    CoverStyle("score", "악보", "오선이 배경으로 흐르는 — 교재용에 어울립니다",
               ink="#22201c", paper="#ffffff", accent="#2c6a45"),
)

BY_STYLE = {s.id: s for s in STYLES}
DEFAULT_STYLE = STYLES[0].id


def _wrap(text: str, per_line: int) -> list[str]:
    """제목을 줄로 나눈다. 한글은 글자 수로 세는 편이 가로폭에 가깝다."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > per_line:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if not lines:
        lines = [text[:per_line]]
    # 너무 긴 한 낱말은 잘라 넘긴다 — 넘치는 것보다 낫다.
    out: list[str] = []
    for line in lines:
        rest = line
        while len(rest) > per_line:
            out.append(rest[:per_line])
            rest = rest[per_line:]
        out.append(rest)
    return out[:3]


def _contents(pieces: list[tuple[str, str]], style: CoverStyle, y0: float) -> str:
    """표지 아래쪽 차례. 몇 곡이 들었는지 표지에서 보여야 산다."""
    rows = []
    for i, (title, note) in enumerate(pieces[:8]):
        y = y0 + i * 8.2
        rows.append(
            f'<text x="30" y="{y:.1f}" font-size="6.4" fill="{style.ink}" opacity=".82">'
            f'{escape(title)}</text>'
            f'<text x="180" y="{y:.1f}" font-size="5.6" fill="{style.ink}" opacity=".5" '
            f'text-anchor="end">{escape(note)}</text>'
            f'<line x1="30" y1="{y + 2.4:.1f}" x2="180" y2="{y + 2.4:.1f}" '
            f'stroke="{style.ink}" stroke-opacity=".13" stroke-width=".3"/>'
        )
    if len(pieces) > 8:
        y = y0 + 8 * 8.2
        rows.append(
            f'<text x="30" y="{y:.1f}" font-size="5.6" fill="{style.ink}" opacity=".5">'
            f'그 밖에 {len(pieces) - 8}곡</text>'
        )
    return "".join(rows)


def _ornament(style: CoverStyle) -> str:
    """스타일마다 다른 뼈대. 색만 바꾼 것은 다른 표지가 아니다."""
    a, ink = style.accent, style.ink
    if style.id == "classic":
        return (
            f'<rect x="12" y="12" width="{W - 24}" height="{H - 24}" fill="none" '
            f'stroke="{a}" stroke-width="1.1"/>'
            f'<rect x="16" y="16" width="{W - 32}" height="{H - 32}" fill="none" '
            f'stroke="{a}" stroke-width=".35" stroke-opacity=".7"/>'
            f'<circle cx="{W / 2}" cy="46" r="9" fill="none" stroke="{a}" stroke-width=".7"/>'
            f'<text x="{W / 2}" y="49.6" text-anchor="middle" font-size="9" fill="{a}">♪</text>'
        )
    if style.id == "stage":
        # 커튼 — 위에서 드리운 주름
        folds = "".join(
            f'<path d="M{x} 0 Q{x + 9} 26 {x} 52" fill="none" stroke="{a}" '
            f'stroke-opacity=".28" stroke-width="1.4"/>'
            for x in range(6, int(W), 18)
        )
        return (
            f'<rect x="0" y="0" width="{W}" height="54" fill="{ink}" fill-opacity=".08"/>'
            f'{folds}'
            f'<line x1="0" y1="54" x2="{W}" y2="54" stroke="{a}" stroke-width="1.6"/>'
        )
    if style.id == "pastel":
        dots = "".join(
            f'<circle cx="{22 + (i * 37) % (W - 44):.0f}" cy="{34 + (i * 23) % 22:.0f}" '
            f'r="{2.4 + (i % 3) * 1.3:.1f}" fill="{a}" fill-opacity=".{18 + (i % 4) * 8}"/>'
            for i in range(9)
        )
        return (
            f'{dots}'
            f'<rect x="18" y="{H - 58}" width="{W - 36}" height="34" rx="6" fill="{a}" '
            f'fill-opacity=".10"/>'
        )
    if style.id == "modern":
        return (
            f'<rect x="0" y="0" width="16" height="{H}" fill="{a}"/>'
            f'<rect x="34" y="34" width="52" height="4.5" fill="{ink}"/>'
            f'<rect x="34" y="{H - 40}" width="{W - 68}" height="1" fill="{ink}" '
            f'fill-opacity=".25"/>'
        )
    # score — 오선이 배경으로 흐른다
    staves = "".join(
        f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{ink}" stroke-opacity=".10" '
        f'stroke-width=".45"/>'
        for base in (30, 250)
        for y in range(base, base + 20, 4)
    )
    return (
        f'{staves}'
        f'<line x1="24" y1="{H / 2 - 34}" x2="{W - 24}" y2="{H / 2 - 34}" stroke="{a}" '
        f'stroke-width="1.2"/>'
    )


def render_cover_svg(
    *,
    title: str,
    subtitle: str = "",
    composer: str = "",
    style_id: str = DEFAULT_STYLE,
    pieces: list[tuple[str, str]] | None = None,
) -> str:
    """곡집 표지 한 장. 글자와 선만 쓴다 — 바깥 그림 파일이 필요 없다."""
    style = BY_STYLE.get(style_id, BY_STYLE[DEFAULT_STYLE])
    pieces = pieces or []

    lines = _wrap(title.strip() or "콩쿨 곡집", 11)
    y0 = 118 - (len(lines) - 1) * 9
    title_svg = "".join(
        f'<text x="{W / 2}" y="{y0 + i * 18:.1f}" text-anchor="middle" font-size="17" '
        f'font-weight="600" fill="{style.ink}" '
        f'font-family="Nanum Myeongjo, Georgia, serif">{escape(ln)}</text>'
        for i, ln in enumerate(lines)
    )
    sub_svg = (
        f'<text x="{W / 2}" y="{y0 + len(lines) * 18 + 6:.1f}" text-anchor="middle" '
        f'font-size="7.4" fill="{style.ink}" opacity=".62">{escape(subtitle)}</text>'
        if subtitle else ""
    )
    comp_svg = (
        f'<text x="{W / 2}" y="{H - 26}" text-anchor="middle" font-size="7.6" '
        f'letter-spacing="1.6" fill="{style.accent}">{escape(composer)}</text>'
        if composer else ""
    )
    toc = _contents(pieces, style, y0 + len(lines) * 18 + 30) if pieces else ""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
        f'width="{W:.0f}mm" height="{H:.0f}mm" role="img" '
        f'aria-label="{escape(title)} 곡집 표지">'
        f'<rect width="{W}" height="{H}" fill="{style.paper}"/>'
        f'{_ornament(style)}'
        f'{title_svg}{sub_svg}{toc}{comp_svg}'
        f'</svg>'
    )
