"""조성 이름 하나 때문에 **다 만든 곡을 잃지 않는다.**

원장님 화면에 뜬 것:

    AccidentalException: ajor is not a supported accidental type
    우리 코드 마지막 자리 — generation/assemble.py:126 에서 (assemble)

곡을 전부 만들고 **악보로 조립하는 마지막 자리**에서 죽었다. 돈은 이미 다 나갔고
곡은 한 마디도 못 건졌다. "만든곡도 0곡으로 아무것도 없어" 가 그 결과다.

원인은 한 줄이다 — music21 은 조성을 `"C"`(장조)·`"c"`(단조) 로 받는데, 모델은
사람이 쓰는 대로 `"C major"`·`"a minor"` 로 준다.
"""

from __future__ import annotations

import pytest
from app.analysis.keyname import normalize_key
from music21 import key as m21key

# ── 원장님이 실제로 만난 그 값 ────────────────────────────────────────────


def test_the_exact_value_that_killed_the_piece() -> None:
    """`"C major"` — 이것 하나가 26분짜리 곡을 통째로 날렸다."""
    with pytest.raises(Exception, match="ajor"):
        m21key.Key("C major")          # 고치기 전에는 이렇게 죽었다

    m21key.Key(normalize_key("C major"))   # 이제는 통과한다


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("C", "C"), ("C major", "C"), ("G Major", "G"),
        ("a minor", "a"), ("d moll", "d"), ("f# minor", "f#"),
        ("Bb major", "B-"), ("B- major", "B-"), ("Eb", "E-"),
        ("A-flat major", "A-"),
        # 한국어로 적혀도 받는다 — 콩쿨 서류가 이렇게 쓴다.
        ("C장조", "C"), ("내림마장조", "E-"), ("올림바단조", "f#"),
    ],
)
def test_every_way_a_key_gets_written(raw: str, want: str) -> None:
    assert normalize_key(raw) == want
    m21key.Key(normalize_key(raw))     # music21 이 실제로 받는지까지 본다


def test_nonsense_falls_back_instead_of_throwing() -> None:
    """읽을 수 없어도 **던지지 않는다.** 던지면 곡을 잃는다 — 그게 고치려던 문제다."""
    for junk in ("", "   ", "헛소리", "?!", "H major"):
        got = normalize_key(junk)
        m21key.Key(got)                 # 무엇이 나오든 music21 이 받아야 한다


def test_minor_stays_minor_and_major_stays_major() -> None:
    """대소문자가 곧 장·단조다 — 뒤바뀌면 곡의 성격이 달라진다."""
    assert normalize_key("a minor").islower()
    assert normalize_key("A major").isupper()
    assert normalize_key("f# minor") == "f#"
    assert normalize_key("F# major") == "F#"


# ── 들어오는 자리에서 고쳐 받는가 ─────────────────────────────────────────


def test_the_plan_cleans_the_key_as_it_arrives(pipeline, ctx) -> None:
    """모델이 "C major" 를 줘도 설계도에는 이미 고쳐져 담긴다.

    실제 설계도를 하나 만들어 그 위에 사람이 쓰는 조성을 얹어 본다 —
    손으로 지어낸 표본은 스키마가 바뀌면 같이 낡는다.
    """
    from app.schemas.music import CompositionPlan

    motif = pipeline.motifs(ctx, 1)[0]
    plan, _ = pipeline.plan(ctx, motif)

    raw = plan.model_dump()
    raw["key"] = "Bb major"
    again = CompositionPlan.model_validate(raw)

    assert again.key == "B-", "설계도가 사람이 쓴 조성을 그대로 들고 있다"
    m21key.Key(again.key)


def test_the_motif_cleans_it_too() -> None:
    from app.schemas.music import Measure, MotifCandidate, ScoreEvent, Voice

    m = MotifCandidate.model_validate({
        "id": "m1",
        "measures": [
            Measure(number=n, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])]).model_dump()
            for n in (1, 2)
        ],
        "key": "a minor", "meter": "4/4", "tempo": 100,
        "character_label": "노래하듯",
    })
    assert m.key == "a"


# ── 조립까지 끝까지 간다 ──────────────────────────────────────────────────


def test_a_piece_assembles_with_a_human_written_key() -> None:
    """조각이 아니라 **실제로 악보를 만들어 본다.**

    여기가 원장님 곡이 죽은 자리다. 스키마만 고치고 이 검사를 안 하면,
    저장소에 든 옛 곡이나 다른 경로로 들어온 값에서 또 같은 일이 난다.
    """
    from app.generation.assemble import AssembleOptions, measures_to_musicxml
    from app.schemas.music import Measure, ScoreEvent, Voice

    measures = [
        Measure(number=n, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])],
                lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])])
        for n in range(1, 5)
    ]
    for raw in ("C major", "a minor", "Bb major", "내림마장조"):
        xml = measures_to_musicxml(
            measures, AssembleOptions(title="시험곡", key_sig=raw, meter="4/4", tempo=100)
        )
        assert "<score-partwise" in str(xml), raw
