"""§7.6 검증기 — 하드 규칙은 하나라도 깨지면 저장 불가."""
from __future__ import annotations

from app.schemas.music import Measure, ScoreEvent, Voice
from app.validate.validator import validate_score
from helpers import simple_measure


def test_valid_score_passes(student):
    ms = [simple_measure(i, ["C5", "D5", "E5", "F5"], ["C3", "G3"]) for i in range(1, 5)]
    ms[-1] = Measure(
        number=4,
        rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])],
        lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])],
    )
    r = validate_score(ms, student, meter="4/4", tempo=100)
    assert r.passed, [i.message for i in r.hard_failures]


def test_measure_length_mismatch_is_hard_failure(student):
    bad = Measure(number=1, rh=[Voice(events=[ScoreEvent(dur=1, pitches=["C5"])])])
    r = validate_score([bad], student, meter="4/4", tempo=100)
    assert not r.passed
    assert any(i.rule == "measure_length" for i in r.hard_failures)


def test_hand_span_over_student_limit_is_blocked(student):
    # 학생 스팬 7도 = 11반음. 옥타브(12반음) 동시 타건은 막혀야 한다.
    m = Measure(number=1, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C4", "C5"])])])
    r = validate_score([m], student, meter="4/4", tempo=100)
    assert any(i.rule == "hand_span" for i in r.hard_failures)


def test_range_outside_student_is_blocked(student):
    m = Measure(number=1, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C8"])])])
    r = validate_score([m], student, meter="4/4", tempo=100)
    assert any(i.rule == "range" for i in r.hard_failures)


def test_hand_crossing_is_blocked(student):
    m = Measure(
        number=1,
        rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C4"])])],
        lh=[Voice(events=[ScoreEvent(dur=4, pitches=["G5"])])],
    )
    r = validate_score([m], student, meter="4/4", tempo=100)
    assert any(i.rule == "hand_crossing" for i in r.hard_failures)


def test_four_identical_measures_in_a_row_blocked(student):
    ms = [simple_measure(i, ["C5", "D5", "E5", "F5"], ["C3"]) for i in range(1, 6)]
    r = validate_score(ms, student, meter="4/4", tempo=100)
    assert any(i.rule == "repeat_limit" for i in r.hard_failures)


def test_time_limit_enforced_at_95_percent(student, competition):
    # 150초 제한 · 4/4 · 100bpm → 한 마디 2.4초. 60마디 = 144초 > 142.5초
    ms = [simple_measure(i, ["C5", "D5", "E5", "F5"], ["C3"]) for i in range(1, 61)]
    r = validate_score(ms, student, meter="4/4", tempo=100, competition=competition)
    assert any(i.rule == "time_limit" for i in r.hard_failures)


def test_tempo_over_student_comfort_blocked(student):
    ms = [simple_measure(1, ["C5", "D5", "E5", "F5"], ["C3"])]
    r = validate_score(ms, student, meter="4/4", tempo=160)
    assert any(i.rule == "tempo" for i in r.hard_failures)


def test_key_signature_notes_are_not_counted_as_accidentals(student):
    """A장조의 F#/C#/G# 는 조표이지 임시표가 아니다."""
    ms = [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["A4", "C#5", "E5", "F#5"]])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["A2"])])],
        )
        for i in range(1, 4)
    ]
    in_key = validate_score(ms, student, meter="4/4", tempo=100, key_sig="A",
                            max_accidental_ratio=0.10)
    assert not any(i.rule == "accidental_ratio" for i in in_key.hard_failures)

    # 같은 음을 C장조로 읽으면 임시표가 넘친다.
    in_c = validate_score(ms, student, meter="4/4", tempo=100, key_sig="C",
                          max_accidental_ratio=0.10)
    assert any(i.rule == "accidental_ratio" for i in in_c.hard_failures)


def test_competition_forbidding_original_blocks_save(student, competition):
    profile = competition.model_copy(update={"original_allowed": False})
    ms = [simple_measure(1, ["C5", "D5", "E5", "F5"], ["C3"])]
    r = validate_score(ms, student, meter="4/4", tempo=100, competition=profile)
    assert any(i.rule == "competition_original" for i in r.hard_failures)


def test_soft_rules_do_not_block_save(student):
    tops = ["C5", "D5", "E5", "F5", "G5", "A5", "B5"]
    ms = [
        simple_measure(i, ["C5", "D5", "E5", tops[i % len(tops)]], ["C3"])
        for i in range(1, 9)
    ]
    ms[-1] = Measure(
        number=8,
        rh=[Voice(events=[ScoreEvent(dur=0.5, pitches=["C5"]), ScoreEvent(dur=3.5, pitches=["D5"])])],
        lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])],
    )
    r = validate_score(ms, student, meter="4/4", tempo=100)
    assert r.warnings
    assert r.passed
