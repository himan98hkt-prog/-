"""작곡가 신원과 저작권 — 예명은 나가고 실명은 남는다.

이 테스트가 지키는 것은 두 가지다.

1. 밖으로 나가는 산출물(악보·음원)에는 **예명만** 찍힌다. 실명이 거기 섞이면
   콩쿨 심사표와 판매 악보에 본명이 노출된다.
2. 편곡을 원곡 권리 정리 없이 등록·판매하지 못하게 막는다. 여기서 막지 않으면
   등록 반려로 끝나지 않고 저작권 침해가 된다.
"""

from __future__ import annotations

from app.generation.assemble import AssembleOptions, measures_to_musicxml
from app.identity import DEFAULT_ALIAS, current_alias, set_alias
from app.schemas.music import Measure, ScoreEvent, Voice
from app.schemas.rights import ComposerIdentity, WorkRights

LEGAL = "이경실"


def _one_measure() -> list[Measure]:
    return [Measure(number=1, rh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C5"])])])]


def test_score_credits_the_alias_not_the_legal_name() -> None:
    """악보에 찍히는 이름은 예명 하나뿐이다."""
    set_alias(DEFAULT_ALIAS)
    xml = measures_to_musicxml(_one_measure(), AssembleOptions(title="작은 행진"))
    assert f'<creator type="composer">{DEFAULT_ALIAS}</creator>' in xml
    assert LEGAL not in xml


def test_alias_change_reaches_new_scores() -> None:
    try:
        set_alias("다른예명")
        assert current_alias() == "다른예명"
        assert "다른예명" in measures_to_musicxml(_one_measure(), AssembleOptions())
    finally:
        set_alias(DEFAULT_ALIAS)


def test_empty_alias_falls_back_rather_than_leaving_the_score_unsigned() -> None:
    try:
        set_alias("   ")
        assert current_alias() == DEFAULT_ALIAS
    finally:
        set_alias(DEFAULT_ALIAS)


def test_identity_knows_what_registration_still_needs() -> None:
    bare = ComposerIdentity()
    assert bare.display() == DEFAULT_ALIAS
    assert set(bare.missing_for_registration()) == {"실명", "생년월일", "주소", "이메일"}

    full = ComposerIdentity(
        legal_name=LEGAL, birth_date="1985-04-02", address="서울시", email="a@b.kr"
    )
    assert full.missing_for_registration() == []
    assert full.display() == DEFAULT_ALIAS  # 다 채워도 밖으로 나가는 이름은 예명


def test_original_work_needs_no_clearance() -> None:
    ok, blockers = WorkRights(work_type="original").clearance()
    assert ok and not blockers


def test_arrangement_of_a_protected_work_is_blocked() -> None:
    """보호 기간 중인 원곡을 허락 없이 편곡·판매하려 하면 막아야 한다."""
    ok, blockers = WorkRights(
        work_type="arrangement",
        original_title="어떤 곡",
        original_composer="어떤 사람",
        original_status="copyrighted",
    ).clearance()
    assert not ok
    assert any("침해" in b for b in blockers)


def test_arrangement_with_unknown_source_is_blocked() -> None:
    ok, blockers = WorkRights(
        work_type="arrangement", original_title="어떤 곡", original_composer="어떤 사람"
    ).clearance()
    assert not ok
    assert any("확인하지 않았" in b for b in blockers)


def test_arrangement_of_a_public_domain_work_passes() -> None:
    ok, blockers = WorkRights(
        work_type="arrangement",
        original_title="G선상의 아리아",
        original_composer="J.S. Bach",
        original_status="public_domain",
    ).clearance()
    assert ok and not blockers


def test_licensed_arrangement_must_record_its_basis() -> None:
    """허락받았다는 말만으로는 안 된다 — 근거를 남겨야 나중에 증빙이 된다."""
    without = WorkRights(
        work_type="arrangement",
        original_title="어떤 곡",
        original_composer="어떤 사람",
        original_status="licensed",
    )
    assert not without.clearance()[0]
    with_note = without.model_copy(update={"license_note": "2026-08-01 이메일 허락"})
    assert with_note.clearance()[0]
