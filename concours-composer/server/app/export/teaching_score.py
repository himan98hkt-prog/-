"""지도용 악보 — 연주용 악보와 별개로, 가르칠 수 있게 표기를 얹은 판.

파는 곡은 두 벌이어야 한다.

- **연주용** — 음표만 있는 깨끗한 악보. 아이가 보고 치는 것.
- **지도용** — 손가락 번호와 지도 요점이 얹힌 악보. 원장이 보고 가르치는 것.

두 벌을 한 파일에 섞으면 아이 악보가 지저분해지고, 지도용만 주면 무대에 올릴 것이
없다. 그래서 같은 음표에서 **표기만 다른 두 파일**을 낸다.

표기는 music21 의 정식 객체로 얹는다(`articulations.Fingering`,
`expressions.TextExpression`). 그래야 MuseScore·Sibelius 에서 열었을 때 손가락 번호가
음표에 붙어 있고, 원장이 그 자리에서 고쳐 쓸 수 있다 — 그림으로 그려 넣으면 못 고친다.
"""

from __future__ import annotations

from music21 import articulations, expressions, stream

from app.analysis.teaching import TeachingMarks
from app.generation.assemble import AssembleOptions, assemble, to_musicxml
from app.schemas.music import Measure


def _attach_fingering(score: stream.Score, fingering: dict[str, int]) -> int:
    """음표 id 를 따라가 손가락 번호를 붙인다. 붙인 개수를 돌려준다."""
    attached = 0
    for n in score.recurse().notes:
        nid = getattr(n.editorial, "noteId", None) or n.id
        finger = fingering.get(str(nid))
        if finger is None:
            continue
        n.articulations.append(articulations.Fingering(str(finger)))
        attached += 1
    return attached


def _measure_map(score: stream.Score) -> dict[int, list[stream.Measure]]:
    out: dict[int, list[stream.Measure]] = {}
    for m in score.recurse().getElementsByClass(stream.Measure):
        out.setdefault(m.number, []).append(m)
    return out


def _attach_text(score: stream.Score, marks: TeachingMarks) -> int:
    """구간 안내와 걸리는 자리 설명을 마디 위에 적는다.

    같은 마디에 여러 줄이 붙으면 겹쳐 보이므로 한 줄로 합친다.
    """
    by_measure: dict[int, list[str]] = {}
    for number, text in marks.section_notes:
        by_measure.setdefault(number, []).append(f"[{text}]")
    for spot in marks.spots:
        by_measure.setdefault(spot.measure, []).append(spot.message)

    lookup = _measure_map(score)
    written = 0
    for number, lines in sorted(by_measure.items()):
        targets = lookup.get(number)
        if not targets:
            continue
        # 앞의 ▸ 는 이것이 음악 지시가 아니라 **지도 메모**임을 눈으로 가른다.
        # 글꼴 속성으로 구분하면 편집기마다 다르게 보인다 — 글자로 박아 두는 편이 낫다.
        te = expressions.TextExpression("▸ " + " · ".join(lines))
        te.placement = "above"
        targets[0].insert(0, te)          # 오른손 보표 위에만 — 두 번 적지 않는다
        written += 1
    return written


def build_teaching_score(
    measures: list[Measure], opts: AssembleOptions, marks: TeachingMarks
) -> str:
    """지도용 MusicXML.

    제목에 '지도용' 을 붙인다 — 두 파일이 한 폴더에 있을 때 어느 쪽이 아이 것인지
    파일을 열지 않고도 알아야 한다.
    """
    teaching_opts = AssembleOptions(
        title=f"{opts.title} (지도용)",
        composer=opts.composer,
        key_sig=opts.key_sig,
        meter=opts.meter,
        tempo=opts.tempo,
    )
    score = assemble(measures, teaching_opts)
    _attach_fingering(score, marks.fingering)
    _attach_text(score, marks)

    # 맨 앞에 이 악보가 무엇인지 한 줄. 원장이 아이에게 줄 판과 헷갈리지 않게.
    first = next(iter(score.recurse().getElementsByClass(stream.Measure)), None)
    if first is not None:
        head = expressions.TextExpression(
            "▸ 지도용 — 손가락 번호는 제안입니다. 아이 손에 맞게 고쳐 쓰십시오."
        )
        head.placement = "above"
        first.insert(0, head)
    return to_musicxml(score)


def teaching_markdown(marks: TeachingMarks, title: str) -> str:
    """악보를 열지 않고도 읽는 지도 메모. 꾸러미에 함께 넣는다."""
    lines = [f"# {title} — 지도 메모", "", marks.caution, ""]

    if marks.section_notes:
        lines += ["## 구간", ""]
        lines += [f"- **{n}마디부터** — {t}" for n, t in marks.section_notes]
        lines.append("")

    if marks.spots:
        lines += ["## 아이가 걸리는 자리", ""]
        for s in marks.spots:
            where = {"rh": "오른손", "lh": "왼손"}.get(s.hand or "", "")
            lines.append(f"- **{s.measure}마디**{' · ' + where if where else ''} — {s.message}")
        lines.append("")

    lines += [
        "## 손가락 번호",
        "",
        f"{len(marks.fingering)}개 음에 번호를 붙였습니다. 규칙으로 계산한 **제안**이므로,",
        "아이 손 크기와 버릇에 따라 더 나은 운지가 있습니다. 악보 파일에서 그대로",
        "고쳐 쓰실 수 있습니다(MuseScore 에서 번호를 눌러 수정).",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["build_teaching_score", "teaching_markdown"]
