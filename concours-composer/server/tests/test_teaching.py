"""지도용 표기 — 원장이 이 악보로 가르칠 수 있는가.

손가락 번호는 제안이지만 **아무 번호나 붙이면 안 된다**. 올라가는 음계에서 손가락이
5를 넘어가면 사람 손으로는 못 친다. 걸리는 자리는 의견이 아니라 악보에서 센 것이므로,
심어 둔 도약과 벌림을 정확히 잡아내는지 본다.
"""

from __future__ import annotations

from app.analysis.teaching import (
    WIDE_CHORD,
    WIDE_LEAP,
    find_spots,
    note_id,
    suggest_fingering,
    teaching_marks,
)
from app.export.teaching_score import build_teaching_score, teaching_markdown
from app.generation.assemble import AssembleOptions
from app.generation.assemble import note_id as assemble_note_id
from app.schemas.music import Measure, ScoreEvent, Voice

SCALE = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]


def _rh(pitches: list[list[str]], number: int = 1) -> Measure:
    return Measure(
        number=number,
        rh=[Voice(events=[ScoreEvent(dur=0.5, pitches=p) for p in pitches])],
    )


def test_note_ids_match_the_score_exporter() -> None:
    """표기가 붙는 열쇠가 두 곳에서 어긋나면 엉뚱한 음에 번호가 찍힌다."""
    assert note_id(3, "rh", 1, 2) == assemble_note_id(3, "rh", 1, 2)


def test_fingers_stay_on_the_hand() -> None:
    """1~5 밖으로 나가면 사람 손이 아니다."""
    measures = [_rh([[p] for p in SCALE * 2])]
    fingering = suggest_fingering(measures)
    assert fingering, "손가락이 하나도 안 붙었다"
    assert all(1 <= f <= 5 for f in fingering.values()), fingering


def test_ascending_scale_tucks_the_thumb() -> None:
    """올라가는 음계는 1-2-3 다음에 엄지를 넣어야 계속 올라갈 수 있다."""
    measures = [_rh([[p] for p in SCALE])]
    seq = [suggest_fingering(measures)[note_id(1, "rh", 1, i)] for i in range(len(SCALE))]
    assert seq[0] == 1
    assert seq[:5] == [1, 2, 3, 4, 5], seq
    assert seq[5] == 1, f"5 다음에는 엄지를 넣어야 한다: {seq}"


def test_left_hand_mirrors_the_right() -> None:
    """왼손은 올라갈 때 손가락 번호가 줄어든다 — 5가 아래쪽이다."""
    measures = [
        Measure(
            number=1,
            lh=[Voice(events=[ScoreEvent(dur=0.5, pitches=[p]) for p in ["C3", "D3", "E3"]])],
        )
    ]
    f = suggest_fingering(measures)
    seq = [f[note_id(1, "lh", 1, i)] for i in range(3)]
    assert seq[0] == 5
    assert seq[1] < seq[0] and seq[2] < seq[1], seq


def test_wide_leap_is_reported() -> None:
    measures = [_rh([["C4"], ["C5"]])]      # 12반음
    spots = find_spots(measures)
    leaps = [s for s in spots if s.kind == "leap"]
    assert leaps and leaps[0].measure == 1
    assert "12반음" in leaps[0].message


def test_small_steps_are_not_reported() -> None:
    """한 음씩 걷는 곡에 '도약' 을 붙이면 경고가 소음이 된다."""
    measures = [_rh([[p] for p in SCALE])]
    assert not [s for s in find_spots(measures) if s.kind == "leap"]


def test_wide_chord_is_reported() -> None:
    measures = [_rh([["C4", "A5"]])]        # 21반음
    stretches = [s for s in find_spots(measures) if s.kind == "stretch"]
    assert stretches and "벌어집니다" in stretches[0].message


def test_thresholds_are_the_boundary_not_a_suggestion() -> None:
    """문턱 바로 아래는 잡지 않고 바로 위는 잡는다 — 애매하면 지표가 못 미덥다."""
    assert (WIDE_LEAP, WIDE_CHORD) == (8, 9), "문턱이 바뀌면 이 테스트의 음도 바꿔야 한다"

    # 도약: C4→G4 는 7반음(문턱 아래), C4→G#4 는 8반음(문턱).
    assert not [s for s in find_spots([_rh([["C4"], ["G4"]])]) if s.kind == "leap"]
    assert [s for s in find_spots([_rh([["C4"], ["G#4"]])]) if s.kind == "leap"]

    # 화음 벌림: C4+G#4 는 8반음(문턱 아래), C4+A4 는 9반음(문턱).
    assert not [s for s in find_spots([_rh([["C4", "G#4"]])]) if s.kind == "stretch"]
    assert [s for s in find_spots([_rh([["C4", "A4"]])]) if s.kind == "stretch"]


def test_teaching_score_carries_fingering_and_words() -> None:
    """MuseScore 에서 열었을 때 번호가 음표에 붙어 있어야 고쳐 쓸 수 있다."""
    measures = [_rh([[p] for p in SCALE], number=1), _rh([["C4"], ["C6"]], number=2)]
    marks = teaching_marks(measures)
    xml = build_teaching_score(measures, AssembleOptions(title="시범곡"), marks)

    assert "<fingering" in xml
    assert xml.count("<fingering") >= len(SCALE)
    assert "지도용" in xml            # 제목과 머리말로 두 판을 가른다
    assert "▸" in xml                 # 지도 메모임을 눈으로 가르는 표시


def test_teaching_notes_admit_the_fingering_is_a_suggestion() -> None:
    """제안을 사실처럼 적으면 원장이 그대로 가르친다."""
    marks = teaching_marks([_rh([[p] for p in SCALE])])
    md = teaching_markdown(marks, "시범곡")
    assert "제안" in md
    assert "고쳐 쓰" in md
