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


def _bar(n: int, rh: list[tuple[float, list[str]]], lh: list[tuple[float, list[str]]],
         *, rh_ties: list[str | None] | None = None) -> Measure:
    ties = rh_ties or [None] * len(rh)
    return Measure(
        number=n,
        rh=[Voice(events=[ScoreEvent(dur=d, pitches=p, tie=t)
                          for (d, p), t in zip(rh, ties, strict=True)])],
        lh=[Voice(events=[ScoreEvent(dur=d, pitches=p) for d, p in lh])],
    )


def test_parallel_octaves_inside_a_measure_are_caught(student):
    """마디 첫 음만 보던 검사는 이것을 통째로 놓쳤다 — 2·3박에서 두 손이 나란히 8도로 걷는다."""
    m = _bar(1,
             [(1.0, ["C5"]), (1.0, ["D5"]), (1.0, ["E5"]), (1.0, ["C5"])],
             [(1.0, ["C3"]), (1.0, ["D3"]), (1.0, ["E3"]), (1.0, ["C3"])])
    r = validate_score([m], student, meter="4/4", tempo=100)
    msgs = [i.message for i in r.warnings if i.rule == "parallels"]
    assert msgs and "1마디" in msgs[0] and "8도" in msgs[0], msgs


def test_parallel_fifths_inside_a_measure_are_caught(student):
    m = _bar(1,
             [(2.0, ["G4"]), (2.0, ["A4"])],
             [(2.0, ["C3"]), (2.0, ["D3"])])
    r = validate_score([m], student, meter="4/4", tempo=100)
    assert any("5도" in i.message for i in r.warnings if i.rule == "parallels")


def test_one_hand_holding_is_not_a_parallel(student):
    """오른손이 붙잡고 있는 동안 왼손만 움직이면 병행이 아니다."""
    m = _bar(1,
             [(4.0, ["C5"])],
             [(1.0, ["C3"]), (1.0, ["D3"]), (1.0, ["E3"]), (1.0, ["F3"])])
    r = validate_score([m], student, meter="4/4", tempo=100)
    assert not [i for i in r.warnings if i.rule == "parallels"]


def test_tied_note_is_not_a_new_attack(student):
    """이어짐표로 묶인 뒷마디 음은 새로 친 것이 아니므로 병행의 출발점이 될 수 없다."""
    ms = [
        _bar(1, [(2.0, ["C5"]), (2.0, ["D5"])], [(2.0, ["C3"]), (2.0, ["D3"])],
             rh_ties=[None, "start"]),
        _bar(2, [(2.0, ["D5"]), (2.0, ["E5"])], [(2.0, ["D3"]), (2.0, ["E3"])],
             rh_ties=["stop", None]),
    ]
    r = validate_score(ms, student, meter="4/4", tempo=100)
    # 1마디 안(도→레)과 2마디 안(레→미)은 잡히지만, 이어짐표 자리는 새 타건이 아니다.
    hits = [i.message for i in r.warnings if i.rule == "parallels"]
    assert all("1→2마디" not in m for m in hits), hits
