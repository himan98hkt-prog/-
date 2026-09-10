"""공용 테스트 픽스처."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autoshorts.models import Segment, Transcript, Word  # noqa: E402


def make_segment(start: float, end: float, text: str) -> Segment:
    """텍스트를 공백 단위로 균등 분할해 단어 타임스탬프를 붙인 세그먼트."""
    tokens = text.split()
    span = (end - start) / max(len(tokens), 1)
    words = [
        Word(start + index * span, start + (index + 1) * span, token)
        for index, token in enumerate(tokens)
    ]
    return Segment(start=start, end=end, text=text, words=words)


@pytest.fixture
def transcript() -> Transcript:
    """5초 단위 발화 36개 = 180초짜리 전사본."""
    lines = [
        "안녕하세요 오늘은 아주 중요한 이야기를 해보려고 합니다",
        "사실 이 방법은 아무도 알려주지 않는 비밀입니다",
        "제가 처음 시작했을 때는 정말 막막했어요",
        "그런데 한 가지 원칙을 지키니까 결과가 달라졌습니다",
        "왜냐하면 사람들은 대부분 이 단계를 건너뛰기 때문입니다",
        "구독과 좋아요 부탁드립니다",
    ]
    segments = []
    for index in range(36):
        start = index * 5.0
        segments.append(make_segment(start, start + 4.5, lines[index % len(lines)]))
    return Transcript(segments=segments, language="ko", duration=180.0)


@pytest.fixture
def short_transcript() -> Transcript:
    """40초짜리 짧은 전사본."""
    segments = [
        make_segment(0.0, 12.0, "첫 번째 문장입니다 아주 중요한 내용이 여기 있습니다"),
        make_segment(12.5, 26.0, "두 번째 문장은 조금 더 길게 이어집니다 진짜 핵심은 이것입니다"),
        make_segment(26.5, 40.0, "마지막 문장으로 이야기를 정리하겠습니다 감사합니다"),
    ]
    return Transcript(segments=segments, language="ko", duration=40.0)
