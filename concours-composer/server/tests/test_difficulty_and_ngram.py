"""§7.7 난이도 · 표절 n-gram."""
from __future__ import annotations

from app.analysis.difficulty import difficulty_score
from app.analysis.ngram import DEFAULT_N, build_corpus_index, find_plagiarism, interval_ngrams
from app.schemas.music import Measure, ScoreEvent, Voice
from helpers import simple_measure


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


def test_saturated_features_are_named() -> None:
    """상한에 걸려 1.0 으로 잘린 특징은 원값과 함께 드러나야 한다.

    난이도 9 를 겨냥한 곡에서 밀도가 상한의 2.2배인데도 점수가 오르지 않아
    한참을 헤맸다. 화면에 이것이 보였다면 바로 조표를 봤을 것이다.
    """
    from app.analysis.difficulty import CAPS

    ms = _hard()
    d = difficulty_score(ms, meter="4/4", tempo=170, key_sig="F#")
    for k, v in d.features.items():
        cap, _ = CAPS[k]
        if v >= 1.0 and d.raw[k] > cap:
            assert k in d.saturated()
            assert "상한" in d.saturated()[k]
    # 상한을 넘지 않은 특징은 나오지 않는다
    assert all(d.raw[k] > CAPS[k][0] for k in d.saturated())


def test_advice_does_not_offer_a_lever_that_is_already_maxed() -> None:
    from app.analysis.difficulty import difficulty_advice

    d = difficulty_score(_hard(), meter="4/4", tempo=170, key_sig="F#")
    lines = difficulty_advice(d, 10.0)
    for k, v in d.features.items():
        if v >= 1.0:
            assert not any(line.startswith(f"{k} ") for line in lines), lines


def test_key_signature_advice_fires_only_when_the_key_is_the_blocker() -> None:
    from app.analysis.difficulty import key_signature_advice

    # 다장조(조표 0개)·느린 템포로 난이도 9 는 나오지 않는다.
    hard = key_signature_advice(target=9.0, tempo=100, key_sig="C",
                                max_span_semitones=12, max_accidental_ratio=0.25)
    assert hard and "조표" in hard
    # 목표가 낮으면 조언하지 않는다.
    assert key_signature_advice(target=3.0, tempo=100, key_sig="C",
                                max_span_semitones=12, max_accidental_ratio=0.25) is None
