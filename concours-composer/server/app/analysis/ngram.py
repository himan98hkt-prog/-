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
    return {gram: span[0] for gram, span in interval_ngram_spans(measures, n).items()}


def interval_ngram_spans(
    measures: list[Measure], n: int = DEFAULT_N
) -> dict[tuple[int, ...], tuple[int, int]]:
    """이조 불변 음정 n-gram → (시작 마디, 끝 마디).

    끝 마디를 함께 돌려주는 이유: 표절 보고에 "몇 마디가 겹치는가" 를 적으려면
    그 n-gram 이 **실제로 걸친 마디**를 알아야 한다. 시작 마디만 알면 길이를
    추측할 수밖에 없고, 원장은 그 숫자로 판단할 수 없다.
    """
    line = melody_line(measures)
    # 음정 i 는 line[i] 에서 line[i+1] 로 가는 움직임이므로 두 마디에 걸쳐 있다.
    intervals = [
        (line[i][0], line[i + 1][0], line[i + 1][1] - line[i][1]) for i in range(len(line) - 1)
    ]
    out: dict[tuple[int, ...], tuple[int, int]] = {}
    for i in range(len(intervals) - n + 1):
        window = intervals[i : i + n]
        key = tuple(v for _, _, v in window)
        out.setdefault(key, (window[0][0], window[-1][1]))
    return out


def build_corpus_index(corpus_measures: list[list[Measure]], n: int = DEFAULT_N) -> set[tuple[int, ...]]:
    index: set[tuple[int, ...]] = set()
    for ms in corpus_measures:
        index.update(interval_ngrams(ms, n))
    return index


def find_plagiarism(
    measures: list[Measure], corpus_index: set[tuple[int, ...]], n: int = DEFAULT_N
) -> list[PlagiarismHit]:
    """코퍼스와 겹치는 n-gram 을 찾는다. `length` 는 **실제로 걸친 마디 수**다.

    예전에는 시작 마디부터 곡 끝까지를 세서 길이가 늘 `n//2` 로 고정됐다 —
    48마디 곡을 자기 자신과 대조하면 195건이 전부 "8마디" 로 보고됐다.
    """
    hits = [
        PlagiarismHit(lo, hi - lo + 1, gram)
        for gram, (lo, hi) in interval_ngram_spans(measures, n).items()
        if gram in corpus_index
    ]
    return sorted(hits, key=lambda h: (h.start_measure, -h.length))
