"""**악보가 화면에 그려져야 한다.**

원장님 화면: "정식 악보를 그리지 못했습니다(OpenSheetMusicDisplay: The document which
was provided is invalid) — 간이 악보로 봅니다"

악보 자체는 멀쩡했다. 파트도 둘이고 마디도 다 있었다. 빠진 것은 **첫 줄**이다.

악보 그리개(OSMD)는 넘겨받은 글의 앞머리에서 `<?xml` 을 찾는다. 없으면 "이건 악보가
아니다" 하고 통째로 거절한다. 우리는 note 에 id 를 붙이려고 XML 을 한 번 뜯었다
붙이는데, 파이썬의 ElementTree 가 그 과정에서 선언과 DOCTYPE 을 버렸다.

한 줄 때문에 모든 곡의 정식 악보가 안 그려지고 있었다.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.generation.assemble import AssembleOptions, measures_to_musicxml
from app.schemas.music import Measure, ScoreEvent, Voice


def _piece() -> list[Measure]:
    return [
        Measure(
            number=n,
            rh=[Voice(events=[ScoreEvent(dur=1.0, pitches=[p]) for p in ("C5", "E5", "G5", "E5")])],
            lh=[Voice(events=[ScoreEvent(dur=2.0, pitches=["C3", "G3"])] * 2)],
        )
        for n in (1, 2)
    ]


def _xml() -> str:
    return measures_to_musicxml(
        _piece(), AssembleOptions(title="시험", key_sig="C", meter="4/4", tempo=100)
    )


def test_the_declaration_is_in_the_first_hundred_characters() -> None:
    """OSMD 는 앞 100자만 본다. 거기 없으면 악보 전체를 거절한다."""
    x = _xml()
    assert "<?xml" in x[:100], (
        "XML 선언이 앞머리에 없다 — 화면이 '정식 악보를 그리지 못했습니다' 로 떨어진다"
    )


def test_it_says_it_is_musicxml() -> None:
    """다른 악보 프로그램(뮤즈스코어·시벨리우스)이 열려면 DOCTYPE 이 있어야 한다."""
    x = _xml()
    assert "<!DOCTYPE score-partwise" in x
    assert "musicxml.org" in x


def test_it_is_still_valid_xml_and_music21_can_read_it_back() -> None:
    """머리를 붙이다 본문을 깨뜨리면 더 나쁘다."""
    import music21

    x = _xml()
    root = ET.fromstring(x)
    assert root.tag == "score-partwise"
    assert len(root.findall("part")) == 2, "오른손·왼손 두 파트가 그대로 있어야 한다"
    back = music21.converter.parse(x, format="musicxml")
    assert len(back.parts) == 2


def test_note_ids_survive() -> None:
    """편집·해설 앵커가 여기에 걸린다(절대 규칙 4)."""
    root = ET.fromstring(_xml())
    notes = list(root.iter("note"))
    assert notes, "음표가 없다"
    assert all(n.get("id") for n in notes), "id 없는 음표가 있다"
