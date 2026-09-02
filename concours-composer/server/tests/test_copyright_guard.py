"""CLAUDE.md 절대 규칙 3 — 저작권곡의 음표열은 어떤 프롬프트에도 들어가지 않는다."""
from __future__ import annotations

import json

import pytest
from app.generation.context import build_context
from app.generation.copyright_guard import (
    MAX_EXCERPT_MEASURES,
    CopyrightViolation,
    CorpusEntry,
    assert_no_copyrighted_notes,
    sanitize_corpus,
)


def _entry(cid: str, status: str) -> CorpusEntry:
    return CorpusEntry(
        id=cid, title=f"곡 {cid}", composer="X", copyright_status=status,  # type: ignore[arg-type]
        style_profile={"difficulty_score": 4.0, "rh_density": 3.1},
        excerpt_measures=[{"number": i, "rh": ["C5"]} for i in range(1, 21)],
    )


def test_copyrighted_notes_are_stripped():
    out = sanitize_corpus([_entry("pd", "public_domain"), _entry("cr", "copyrighted")])
    by_id = {o["id"]: o for o in out}
    assert "excerpt_measures" in by_id["pd"]
    assert "excerpt_measures" not in by_id["cr"]
    # 통계는 남는다 — 스타일 학습은 계속 가능해야 한다.
    assert by_id["cr"]["style_profile"]["difficulty_score"] == 4.0


def test_public_domain_excerpt_is_capped():
    out = sanitize_corpus([_entry("pd", "public_domain")])
    assert len(out[0]["excerpt_measures"]) == MAX_EXCERPT_MEASURES


def test_at_most_three_excerpts_total():
    entries = [_entry(f"pd{i}", "public_domain") for i in range(6)]
    out = sanitize_corpus(entries)
    assert sum(1 for o in out if "excerpt_measures" in o) == 3


def test_guard_raises_if_copyrighted_notes_leak():
    entries = [_entry("cr", "copyrighted")]
    leaked = [{"id": "cr", "excerpt_measures": [{"number": 1}]}]
    with pytest.raises(CopyrightViolation):
        assert_no_copyrighted_notes(leaked, entries)


def test_prompt_payload_never_contains_copyrighted_notes(request_obj):
    entries = [_entry("cr", "copyrighted"), _entry("own", "own")]
    ctx = build_context(request_obj, corpus=entries)
    payload = ctx.prompt_payload()          # 위반이면 여기서 예외
    text = json.dumps(payload, ensure_ascii=False)
    # 저작권곡 발췌의 흔적이 직렬화된 프롬프트 어디에도 없어야 한다.
    cr = next(o for o in payload["style_context"] if o["id"] == "cr")
    assert "excerpt_measures" not in cr
    assert text.count('"excerpt_measures"') <= 1     # own 곡 하나만


def test_imported_copyrighted_score_keeps_no_notes():
    """폴더에서 읽은 저작권곡은 음표열을 아예 보관하지 않는다.

    프롬프트에 안 넣는 것만으로는 부족하다 — 저장하지 않으면 새어 나갈 데가 없다.
    저작권 표시가 없는 파일은 안전한 쪽(저작권곡)으로 간주해야 한다.
    """
    from app.ingest.corpus import Corpus
    from app.schemas.music import Measure, ScoreEvent, Voice

    measures = [
        Measure(number=i + 1, rh=[Voice(events=[ScoreEvent(dur=1.0, pitches=["C5"])])])
        for i in range(8)
    ]
    corpus = Corpus()
    protected = corpus.add(
        measures, score_id="ref-protected", title="보호 중인 곡",
        copyright_status="copyrighted",
    )
    free = corpus.add(
        measures, score_id="ref-free", title="옛 곡", copyright_status="public_domain",
    )

    assert protected.measures is None, "저작권곡의 음표열을 들고 있으면 안 된다"
    assert protected.summary()["has_notes"] is False
    # 통계는 남는다 — 길이·난이도는 참고해도 되는 정보다.
    assert protected.profile.measures == 8

    assert free.measures is not None, "보호 기간이 끝난 곡은 선율까지 참고한다"
    assert free.summary()["has_notes"] is True
