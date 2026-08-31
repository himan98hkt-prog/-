"""테스트 공용 헬퍼. conftest 는 디렉터리마다 있으므로 이름 충돌을 피해 여기에 둔다."""
from __future__ import annotations

from app.schemas.music import Measure, ScoreEvent, Voice


def simple_measure(number: int, rh: list[str], lh: list[str], dur: float = 1.0, **kw) -> Measure:
    """테스트용 4/4 한 마디."""
    return Measure(
        number=number,
        rh=[Voice(events=[ScoreEvent(dur=dur, pitches=[p]) for p in rh])],
        lh=[Voice(events=[ScoreEvent(dur=4.0 / max(1, len(lh)), pitches=[p]) for p in lh])],
        **kw,
    )
