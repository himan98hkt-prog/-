"""PDF 악보에서 **통계만** 읽는다. 음표는 읽지 않는다.

원장님이 가지고 계신 악보는 대부분 PDF 다. 그런데 PDF 는 그림이지 악보 데이터가
아니다 — 음표 하나하나를 알아내려면 악보 인식(OMR)이 필요하고, 그건 정확도가
들쭉날쭉해서 잘못 읽은 음이 참고 자료로 섞이면 **없느니만 못하다.**

그래서 여기서는 확실히 알 수 있는 것만 가져온다.

  · 몇 쪽인가 — 곡 길이의 대략을 말해 준다
  · 제목·작곡가 — 악보에 글자로 찍혀 있으면
  · 빠르기말(Allegro·♩=120) · 박자표 — 글자로 찍혀 있으면
  · 인쇄된 마디 번호 중 가장 큰 것 — 곡이 몇 마디인지

**모르는 것은 지어내지 않는다.** 못 찾은 값은 비워 둔다. 참고 자료에 거짓이 섞이는
것이 아무것도 없는 것보다 나쁘다.

MuseScore·피날레·시벨리우스로 짜서 낸 PDF 는 글자층이 있어 위의 것이 대부분 나온다.
종이를 스캔한 PDF 는 글자층이 없어 **쪽 수만** 나온다 — 그것도 아주 쓸모없지는 않다.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# 악보에 흔히 찍히는 빠르기말 → 대략의 BPM. 정확한 값이 아니라 '어느 대'인지다.
_TEMPO_WORDS: dict[str, int] = {
    "grave": 40, "largo": 50, "lento": 52, "adagio": 66, "larghetto": 60,
    "andantino": 80, "andante": 76, "moderato": 108, "allegretto": 112,
    "allegro": 132, "vivace": 160, "presto": 184, "prestissimo": 200,
}
# 사람이 붙인 제목에 잘 안 쓰이는, 악보에만 나오는 말들 — 제목으로 오인하면 안 된다.
_NOT_A_TITLE = re.compile(
    r"^(page|pag\.|\d+|copyright|©|all rights|www\.|http|edition|op\.?\s*\d+)",
    re.IGNORECASE,
)


@dataclass
class PdfStats:
    """PDF 에서 **실제로 확인한 것만** 담는다. 못 찾은 것은 None 이나 빈 값이다."""

    pages: int = 0
    has_text_layer: bool = False
    title: str = ""
    composer: str = ""
    meter: str = ""
    tempo: int = 0
    measures: int = 0
    # 원장님께 무엇을 알아냈고 무엇을 못 알아냈는지 그대로 말하기 위한 줄.
    notes: list[str] = field(default_factory=list)


def _first_lines(text: str, n: int = 12) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()][:n]


def _pick_title_and_composer(lines: list[str]) -> tuple[str, str]:
    """첫 쪽 위쪽 글자에서 제목과 작곡가를 고른다.

    관습이 뚜렷하다 — 제목은 위 가운데, 작곡가는 그 아래 오른쪽이다. 글자만 보고
    자리를 알 수는 없으므로 순서로 짐작한다. 틀릴 수 있으니 **파일 이름이 있으면
    그쪽을 우선**한다(부르는 쪽에서 그렇게 쓴다).
    """
    good = [ln for ln in lines if not _NOT_A_TITLE.match(ln) and len(ln) < 80]
    title = good[0] if good else ""
    composer = ""
    for ln in good[1:4]:
        # 작곡가 줄에는 생몰년이나 '작곡' 같은 말이 붙는 일이 많다.
        if re.search(r"\(\d{4}\s*[-–~]\s*\d{0,4}\)|작곡|composed|by\s+\w", ln, re.IGNORECASE):
            composer = ln
            break
    return title.strip(), composer.strip()


def _find_meter(text: str) -> str:
    """박자표가 글자로 찍혀 있으면 가져온다. 그림으로만 있으면 못 찾는다."""
    m = re.search(r"\b([2-9]|1[0-2])\s*/\s*(2|4|8|16)\b", text)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def _find_tempo(text: str) -> int:
    """♩=120 처럼 숫자로 찍혔으면 그것을, 아니면 빠르기말에서 대략을."""
    m = re.search(r"[♩♪𝅘𝅥]\s*=\s*(\d{2,3})", text)
    if m:
        n = int(m.group(1))
        if 30 <= n <= 250:
            return n
    m = re.search(r"\b(?:M\.?M\.?|Tempo)\s*[:=]?\s*(\d{2,3})\b", text, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 30 <= n <= 250:
            return n
    low = text.lower()
    for word, bpm in _TEMPO_WORDS.items():
        if re.search(rf"\b{word}\b", low):
            return bpm
    return 0


def _find_measures(pages_text: list[str]) -> int:
    """인쇄된 마디 번호 중 가장 큰 것.

    마디 번호는 보통 5·10 단위로 단 위에 작게 찍힌다. 쪽 번호와 헷갈리지 않게
    **뒤쪽 쪽에서 나온 큰 수**만 본다 — 쪽 번호는 쪽 수를 넘지 않는다.
    """
    best = 0
    for text in pages_text:
        for tok in re.findall(r"(?<![\d.])(\d{1,3})(?![\d.])", text):
            n = int(tok)
            # 마디 수가 400 을 넘는 콩쿨용 소품은 없다. 그 위는 잡음이다.
            if len(pages_text) < n <= 400:
                best = max(best, n)
    return best


def read_pdf_stats(path: str | Path) -> PdfStats:
    """PDF 를 열어 확인 가능한 것만 담아 돌려준다. 음표는 읽지 않는다."""
    p = Path(path)
    stats = PdfStats()
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - 설치 목록에 있다
        stats.notes.append("PDF 를 읽는 부품이 없습니다 — '설치.bat' 을 다시 한 번 돌려 주십시오.")
        return stats

    try:
        reader = PdfReader(str(p))
        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:  # 쪽 하나가 깨져도 나머지는 읽는다
                pages_text.append("")
    except Exception as e:
        stats.notes.append(f"PDF 를 열지 못했습니다: {type(e).__name__}")
        return stats

    stats.pages = len(pages_text)
    joined = "\n".join(pages_text)
    stats.has_text_layer = len(joined.strip()) >= 20

    if not stats.has_text_layer:
        # 종이를 스캔한 PDF 다. 쪽 수 말고는 알 수 있는 것이 없다 — 그대로 말한다.
        stats.notes.append(
            f"글자를 찾지 못했습니다(스캔한 악보로 보입니다). {stats.pages}쪽이라는 것만 "
            "알 수 있어 길이 짐작에만 씁니다."
        )
        return stats

    stats.title, stats.composer = _pick_title_and_composer(_first_lines(pages_text[0]))
    stats.meter = _find_meter(joined)
    stats.tempo = _find_tempo(joined)
    stats.measures = _find_measures(pages_text)

    got = [x for x in (
        f"{stats.pages}쪽",
        f"{stats.measures}마디" if stats.measures else "",
        stats.meter, f"♩={stats.tempo}" if stats.tempo else "",
    ) if x]
    stats.notes.append("PDF 에서 읽은 것: " + " · ".join(got))
    missing = [n for n, v in (("마디 수", stats.measures), ("박자", stats.meter),
                              ("빠르기", stats.tempo)) if not v]
    if missing:
        stats.notes.append(
            "찾지 못한 것: " + ", ".join(missing) + " — 악보에 글자로 찍혀 있지 않으면 알 수 없습니다."
        )
    return stats
