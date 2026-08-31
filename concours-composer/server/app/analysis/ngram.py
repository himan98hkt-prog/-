"""멜로디 n-gram 인덱스와 표절 검사.

지표(§1.2): 코퍼스 대비 8마디 이상 동일 멜로디 n-gram 0건.
음정열(전위 불변이 아닌 이조 불변)로 비교하므로 단순 이조한 베끼기도 잡는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.pitch import pitch_to_midi
from app.schemas.music import Measure

# 8마디 ≈ 4/4 기준 멜로디 음 32개. 마디당 최소 2음을 가정해 16음을 임계 n-gram 으로 쓴다.
DEFAULT_N = 16


@dataclass(frozen=True)
class PlagiarismHit:
    start_measure: int
    length: int          # 일치가 걸친 마디 수
    ngram: tuple[int, ...]


def melody_line(measures: list[Measure]) -> list[tuple[int, int]]:
    """오른손 최고음 선율을 (마디번호, midi) 로 뽑는다."""
    out: list[tuple[int, int]] = []
    for m in sorted(measures, key=lambda x: x.number):
        for v in m.rh:
            for e in v.events:
                if e.pitches:
                    out.append((m.number, max(pitch_to_midi(p) for p in e.pitches)))
    return out


def interval_ngrams(measures: list[Measure], n: int = DEFAULT_N) -> dict[tuple[int, ...], int]:
    """이조 불변 음정 n-gram → 시작 마디번호."""
    line = melody_line(measures)
    intervals = [(line[i][0], line[i + 1][1] - line[i][1]) for i in range(len(line) - 1)]
    out: dict[tuple[int, ...], int] = {}
    for i in range(len(intervals) - n + 1):
        window = intervals[i : i + n]
        key = tuple(v for _, v in window)
        out.setdefault(key, window[0][0])
    return out


def build_corpus_index(corpus_measures: list[list[Measure]], n: int = DEFAULT_N) -> set[tuple[int, ...]]:
    index: set[tuple[int, ...]] = set()
    for ms in corpus_measures:
        index.update(interval_ngrams(ms, n))
    return index


def find_plagiarism(
    measures: list[Measure], corpus_index: set[tuple[int, ...]], n: int = DEFAULT_N
) -> list[PlagiarismHit]:
    hits: list[PlagiarismHit] = []
    line = melody_line(measures)
    for gram, start_measure in interval_ngrams(measures, n).items():
        if gram in corpus_index:
            spanned = {mn for mn, _ in line if mn >= start_measure}
            hits.append(PlagiarismHit(start_measure, min(len(spanned), n // 2), gram))
    return sorted(hits, key=lambda h: h.start_measure)
