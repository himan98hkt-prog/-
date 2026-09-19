#!/usr/bin/env python3
"""클립 경계 품질 기준선 probe — 영상도 API 키도 없이 도는 재현 가능한 측정.

왜 필요한가
----------
실영상 벤치마크(`autoshorts benchmark`)는 권리 확인이 끝난 30~50편과 사람이 지정한
gold moment 가 있어야 돌아간다. 그게 준비되기 전에도 **현재 하이라이트 선정기의
경계 품질**은 합성 전사로 재현 가능하게 잴 수 있다.

무엇을 보여 주는가
----------------
`snap_to_segments` 는 클립 경계를 **세그먼트** 경계로 당긴다. 그런데 Whisper 세그먼트는
문장 단위가 아니다 — 침묵과 길이로 끊기므로 문장 중간에서 갈리는 일이 흔하다.
그래서 세그먼트에 붙여도 **문장은 그대로 잘린다.**

이 스크립트는 두 경우를 비교한다.

- ``aligned``: 세그먼트 하나 = 문장 하나 (인위적으로 깔끔한 경우)
- ``unaligned``: 문장을 이어 붙인 단어 흐름을 고정 개수로 자른 세그먼트
  (실제 Whisper 와 같은 상황)

실행:

    python benchmarks/probe_boundary_baseline.py

주의: 합성 전사이므로 절대값을 실영상 성적으로 읽지 말 것. 두 경우의 **차이**와
그 원인이 이 probe 의 결론이다.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# 저장소 루트를 경로에 넣어 설치 없이도 돌게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoshorts.ai_analyzer import heuristic_highlights           # noqa: E402
from autoshorts.benchmark import duplicate_overlap_rate, mid_sentence_cut_rate  # noqa: E402
from autoshorts.models import Segment, Transcript, Word           # noqa: E402

#: 훅 신호어가 섞인 한국어 문장들. 휴리스틱이 점수를 매길 재료.
SENTENCES = (
    "사실 이건 아무도 모르는 이야기입니다.",
    "그런데 문제는 여기서 시작됩니다.",
    "제가 처음 시작했을 때는 백만원도 없었어요.",
    "핵심은 결국 습관입니다.",
    "왜 그럴까요?",
    "놀랍게도 결과는 정반대였습니다.",
    "구독과 좋아요 부탁드립니다.",
    "그래서 저는 방법을 바꿨습니다.",
    "충격적인 사실은 이겁니다.",
    "마지막으로 정리하면 이렇습니다.",
)


def _word_stream(minutes: float, rng: random.Random) -> list[Word]:
    """문장을 이어 붙인 단어 흐름."""
    stream: list[Word] = []
    clock = 0.0
    while clock < minutes * 60:
        for token in SENTENCES[rng.randrange(len(SENTENCES))].split():
            span = rng.uniform(0.25, 0.55)
            stream.append(Word(start=round(clock, 2), end=round(clock + span, 2), text=token))
            clock += span
    return stream


def aligned_transcript(minutes: float, seed: int) -> Transcript:
    """세그먼트 하나가 문장 하나인 전사 (인위적으로 깔끔)."""
    rng = random.Random(seed)
    segments: list[Segment] = []
    clock = 0.0
    while clock < minutes * 60:
        text = SENTENCES[rng.randrange(len(SENTENCES))]
        tokens = text.split()
        span = rng.uniform(2.5, 5.0)
        step = span / len(tokens)
        words, cursor = [], clock
        for token in tokens:
            words.append(Word(start=round(cursor, 2), end=round(cursor + step, 2), text=token))
            cursor += step
        segments.append(
            Segment(start=round(clock, 2), end=round(clock + span, 2), text=text, words=words)
        )
        clock += span
    return Transcript(segments=segments)


def unaligned_transcript(minutes: float, seed: int, words_per_segment: int) -> Transcript:
    """문장 경계를 무시하고 고정 단어 수로 자른 전사 (실제 Whisper 와 같은 상황)."""
    stream = _word_stream(minutes, random.Random(seed))
    segments: list[Segment] = []
    for index in range(0, len(stream), words_per_segment):
        chunk = stream[index:index + words_per_segment]
        if not chunk:
            continue
        segments.append(Segment(
            start=chunk[0].start, end=chunk[-1].end,
            text=" ".join(w.text for w in chunk), words=chunk,
        ))
    return Transcript(segments=segments)


def measure(transcript: Transcript) -> tuple[int, float, float]:
    clips = heuristic_highlights(
        transcript, min_seconds=30.0, max_seconds=60.0, max_clips=5,
    )
    return (
        len(clips),
        mid_sentence_cut_rate(clips, transcript),
        duplicate_overlap_rate(clips),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=5, help="구성마다 반복 횟수(시드)")
    parser.add_argument(
        "--minutes", default="10,30,60", help="측정할 원본 길이(분), 쉼표 구분")
    args = parser.parse_args(argv)

    lengths = [float(v.strip()) for v in args.minutes.split(",") if v.strip()]

    print("클립 경계 기준선 probe — 합성 전사 (절대값이 아니라 두 경우의 차이를 보라)")
    print()
    print(f"{'전사 구성':<26}{'길이':>6}{'클립':>6}{'문장중간절단률':>16}{'중복률':>10}")
    print("-" * 66)

    for minutes in lengths:
        cuts = [measure(aligned_transcript(minutes, seed))
                for seed in range(args.repeats)]
        _report("세그먼트 = 문장 (이상적)", minutes, cuts)

    for words_per_segment in (4, 8, 12):
        for minutes in lengths:
            cuts = [measure(unaligned_transcript(minutes, seed, words_per_segment))
                    for seed in range(args.repeats)]
            _report(f"문장 무시, {words_per_segment}단어씩", minutes, cuts)

    print()
    print("해석: 아래쪽(문장 경계와 어긋난 세그먼트)에서 절단률이 크게 오른다면,")
    print("      원인은 snap_to_segments 가 '문장'이 아니라 '세그먼트'에 붙기 때문이다.")
    print("      Beta 목표는 5% 이하다 (COMPETITIVE_BENCHMARK_2026.md §6).")
    return 0


def _report(label: str, minutes: float, results: list[tuple[int, float, float]]) -> None:
    n = len(results)
    clips = sum(r[0] for r in results) / n
    cut = sum(r[1] for r in results) / n
    dup = sum(r[2] for r in results) / n
    print(f"{label:<26}{minutes:>5.0f}분{clips:>6.1f}{cut * 100:>15.1f}%{dup * 100:>9.1f}%")


if __name__ == "__main__":
    raise SystemExit(main())
