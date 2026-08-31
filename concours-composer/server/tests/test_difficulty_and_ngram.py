"""§7.7 난이도 · 표절 n-gram."""
from __future__ import annotations

from helpers import simple_measure

from app.analysis.difficulty import difficulty_score
from app.analysis.ngram import DEFAULT_N, build_corpus_index, find_plagiarism, interval_ngrams
from app.schemas.music import Measure, ScoreEvent, Voice


def _easy() -> list[Measure]:
    tops = ["C5", "D5", "E5", "F5", "G5", "A5"]
    return [simple_measure(i, ["C5", "D5", "E5", tops[i % 6]], ["C3"]) for i in range(1, 17)]


def _hard() -> list[Measure]:
    return [
        Measure(
            number=i,
            rh=[Voice(events=[
                ScoreEvent(dur=0.25, pitches=["C6"]),
                ScoreEvent(dur=0.25, pitches=["E-6"]),
                ScoreEvent(dur=0.5, pitches=["G4", "C5", "E5"]),
                ScoreEvent(dur=1, pitches=["A#5"]),
                ScoreEvent(dur=2, pitches=["C4", "C5"]),
            ])],
            lh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["C2", "G3", "C2", "A3"]])],
        )
        for i in range(1, 17)
    ]


def test_difficulty_orders_easy_below_hard():
    e = difficulty_score(_easy(), tempo=80)
    h = difficulty_score(_hard(), tempo=160, key_sig="E")
    assert e.score < h.score
    assert 1.0 <= e.score <= 10.0 and 1.0 <= h.score <= 10.0


def test_difficulty_maps_to_a_competition_division():
    assert difficulty_score(_easy(), tempo=80).division_hint() in ("유치부", "초등 저학년부")
    assert difficulty_score(_hard(), tempo=160, key_sig="E").division_hint() in (
        "초등 고학년부", "중등부", "고등·일반부",
    )


def test_tempo_raises_difficulty():
    slow = difficulty_score(_easy(), tempo=60).score
    fast = difficulty_score(_easy(), tempo=160).score
    assert fast > slow


def test_features_are_exposed_for_later_recalibration():
    r = difficulty_score(_easy(), tempo=100)
    assert set(r.features) == set(r.raw)
    assert all(0.0 <= v <= 1.0 for v in r.features.values())


# ── 표절 ─────────────────────────────────────────────────────────────────


def _long_line(start: int = 60) -> list[Measure]:
    from app.analysis.pitch import midi_to_pitch

    pitches = [start + (i * 7) % 13 for i in range(80)]
    names = [midi_to_pitch(p) for p in pitches]
    return [
        simple_measure(i, names[(i - 1) * 4 : (i - 1) * 4 + 4], ["C3"])
        for i in range(1, 21)
    ]


def test_identical_melody_is_flagged():
    piece = _long_line()
    index = build_corpus_index([piece])
    assert find_plagiarism(piece, index)


def test_transposed_copy_is_also_flagged():
    """이조해서 베낀 것도 잡아야 한다 — 음정열로 비교하기 때문."""
    original = _long_line(60)
    transposed = _long_line(65)
    index = build_corpus_index([original])
    assert find_plagiarism(transposed, index)


def test_unrelated_melody_is_not_flagged():
    from app.analysis.pitch import midi_to_pitch

    index = build_corpus_index([_long_line()])
    other = [
        simple_measure(i, [midi_to_pitch(72 - (j + i) % 9) for j in range(4)], ["C3"])
        for i in range(1, 21)
    ]
    assert not find_plagiarism(other, index)


def test_short_pieces_produce_no_ngrams():
    short = [simple_measure(i, ["C5", "D5", "E5", "F5"], ["C3"]) for i in range(1, 3)]
    assert interval_ngrams(short, DEFAULT_N) == {}
