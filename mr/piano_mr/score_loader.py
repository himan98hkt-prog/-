# -*- coding: utf-8 -*-
"""모듈 ① 악보 파서 — MusicXML/MIDI 를 읽어 분석에 필요한 것만 추려 낸다.

개발지시서 5장 모듈 ① 사양:
    load(path) -> (score, key, time_signature, segments, melody_low, bar_len, total_ql)

여기서는 화성 분석(모듈 ②)과의 결합을 끊기 위해 `segments` 를 빼고
`LoadedScore` 를 돌려준다. 세그먼트는 `harmony.analyze_segments()` 가 만든다.
지시서 서명과의 호환은 `load_legacy()` 가 유지한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from music21 import converter, meter, stream
from music21 import key as m21key

SUPPORTED_SUFFIXES = ('.xml', '.musicxml', '.mxl', '.mid', '.midi', '.krn', '.abc')


@dataclass
class Bar:
    """전개(expand)된 흐름 상의 한 마디."""
    idx: int                 # 1부터 시작하는 연주 순서 (반복 전개 후)
    number: int              # 악보에 인쇄된 마디 번호 (반복하면 같은 번호가 또 나온다)
    offset: float            # 곡 전체 기준 시작 위치 (4분음표 단위)
    length: float            # 실제 울리는 길이 — 못갖춘마디면 한 마디보다 짧다
    bar_length: float        # 박자표상 한 마디 길이
    beat_length: float       # 한 박 길이 (6/8 이면 1.5)
    melody_low: Optional[int] = None   # 마디별 멜로디 최저음 (MIDI 번호)


@dataclass
class LoadedScore:
    score: stream.Score
    key: object
    time_signature: meter.TimeSignature
    bars: List[Bar]
    total_ql: float
    path: str = ''
    repeats_expanded: bool = False
    part_count: int = 0
    note_count: int = 0

    # ---- 지시서 서명 호환용 뷰 -------------------------------------------
    @property
    def melody_low(self) -> Dict[int, int]:
        """마디 번호 -> 멜로디 최저음. 반복 전개로 번호가 겹치면 더 낮은 쪽을 쓴다."""
        out: Dict[int, int] = {}
        for b in self.bars:
            if b.melody_low is None:
                continue
            cur = out.get(b.number)
            out[b.number] = b.melody_low if cur is None else min(cur, b.melody_low)
        return out

    @property
    def bar_len(self) -> Dict[int, float]:
        return {b.number: b.bar_length for b in self.bars}

    def bar_by_idx(self, idx: int) -> Optional[Bar]:
        return self.bars[idx - 1] if 1 <= idx <= len(self.bars) else None


def _measure_stream(sc: stream.Score) -> List[stream.Measure]:
    """마디 격자를 가장 잘 가진 파트의 Measure 목록."""
    best: List[stream.Measure] = []
    for p in sc.parts:
        ms = list(p.getElementsByClass(stream.Measure))
        if len(ms) > len(best):
            best = ms
    if not best:
        ms = list(sc.recurse().getElementsByClass(stream.Measure))
        best = ms
    return best


def _top_note_per_onset(sc: stream.Score) -> List[Tuple[float, int]]:
    """(onset, 그 시점 최고음) — 파트 구성과 무관하게 멜로디 선을 뽑는 근사."""
    tops: Dict[float, int] = {}
    for p in sc.parts:
        for n in p.flatten().notes:
            off = round(float(n.offset), 4)
            hi = max(pi.midi for pi in n.pitches)
            if off not in tops or hi > tops[off]:
                tops[off] = hi
    return sorted(tops.items())


def _melody_low_per_bar(sc: stream.Score, bars: List[Bar]) -> None:
    """마디별 멜로디 최저음을 채운다.

    `sc.parts[0]` 을 멜로디로 가정하면 그랜드스태프가 한 파트로 들어온 악보에서
    왼손 저음까지 멜로디로 세어 패드가 지하실로 내려간다. 그래서 파트가 아니라
    **매 시점의 최고음(= 들리는 멜로디)** 을 모은 뒤 그 마디 최솟값을 쓴다.
    """
    tops = _top_note_per_onset(sc)
    if not tops:
        return
    i = 0
    for b in bars:
        lo = None
        while i < len(tops) and tops[i][0] < b.offset - 1e-6:
            i += 1
        j = i
        while j < len(tops) and tops[j][0] < b.offset + b.length - 1e-6:
            lo = tops[j][1] if lo is None else min(lo, tops[j][1])
            j += 1
        b.melody_low = lo


def _expand_repeats(sc: stream.Score) -> Tuple[stream.Score, bool]:
    """반복기호를 펼친다. 악보가 깨져 있으면 원본을 그대로 쓴다 (지시서 모듈 ①)."""
    try:
        ex = sc.expandRepeats()
    except Exception:
        return sc, False
    if ex is None or not ex.parts:
        return sc, False
    if len(ex.recurse().notes) < len(sc.recurse().notes):
        return sc, False          # 펼치다 음을 잃었으면 신뢰하지 않는다
    return ex, True


def load(path: str, expand_repeats: bool = True, transpose: int = 0,
         key_name: Optional[str] = None) -> LoadedScore:
    """악보 파일 -> LoadedScore.

    `key_name` 을 주면 자동 판정 대신 그 조성을 쓴다 ('C', 'a', 'Bb', 'f#').
    짧고 성긴 악보(8마디 이하, 왼손이 근음뿐)에서는 자동 판정이 흔들릴 수 있어
    카탈로그에 확정된 조성이 있으면 그것을 쓰는 편이 안전하다.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'악보 파일을 찾을 수 없습니다: {path}')
    suffix = os.path.splitext(path)[1].lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f'지원하지 않는 확장자입니다: {suffix} (지원: {", ".join(SUPPORTED_SUFFIXES)})')

    sc = converter.parse(path)
    return from_score(sc, expand_repeats=expand_repeats, transpose=transpose,
                      path=path, key_name=key_name)


def from_score(sc: stream.Score, expand_repeats: bool = True,
               transpose: int = 0, path: str = '',
               key_name: Optional[str] = None) -> LoadedScore:
    """이미 파싱된 music21 Score -> LoadedScore (코퍼스·테스트용)."""
    if not isinstance(sc, stream.Score):
        s = stream.Score()
        s.insert(0, sc)
        sc = s
    if transpose:
        sc = sc.transpose(transpose)

    expanded = False
    if expand_repeats:
        sc, expanded = _expand_repeats(sc)

    if key_name:
        k = m21key.Key(key_name)
        if transpose:
            k = k.transpose(transpose)
    else:
        k = sc.analyze('key')

    tsl = list(sc.recurse().getElementsByClass(meter.TimeSignature))
    ts = tsl[0] if tsl else meter.TimeSignature('4/4')

    bars: List[Bar] = []
    for i, m in enumerate(_measure_stream(sc), start=1):
        bar_ql = float(m.barDuration.quarterLength) or 4.0
        actual = float(m.duration.quarterLength)
        # 못갖춘마디(pickup)는 실제 길이가 짧다. barDuration 을 쓰면 분석 창이
        # 다음 마디로 넘어가 화성이 옆으로 밀린다.
        if actual <= 0 or actual > bar_ql + 1e-6:
            actual = bar_ql
        beat_ql = _beat_length(m, ts, bar_ql)
        bars.append(Bar(idx=i, number=m.number if m.number is not None else i,
                        offset=float(m.offset), length=actual,
                        bar_length=bar_ql, beat_length=beat_ql))

    _melody_low_per_bar(sc, bars)

    total = float(sc.duration.quarterLength)
    if bars:
        total = max(total, bars[-1].offset + bars[-1].length)

    return LoadedScore(score=sc, key=k, time_signature=ts, bars=bars,
                       total_ql=total, path=path, repeats_expanded=expanded,
                       part_count=len(sc.parts), note_count=len(sc.recurse().notes))


def _beat_length(m: stream.Measure, fallback_ts: meter.TimeSignature, bar_ql: float) -> float:
    """그 마디에 적용되는 한 박의 길이 (6/8 = 1.5, 3/4 = 1.0)."""
    ts = None
    tsl = list(m.getElementsByClass(meter.TimeSignature))
    if tsl:
        ts = tsl[0]
    else:
        try:
            ts = m.timeSignature or fallback_ts
        except Exception:
            ts = fallback_ts
    try:
        bl = float(ts.beatDuration.quarterLength)
    except Exception:
        bl = 1.0
    if bl <= 0 or bl > bar_ql:
        bl = bar_ql
    return bl


def load_legacy(path: str):
    """개발지시서 5장 모듈 ① 서명 그대로 돌려주는 호환 함수."""
    from . import harmony
    ls = load(path)
    segs = harmony.analyze_segments(ls)
    return (ls.score, ls.key, ls.time_signature, segs,
            ls.melody_low, ls.bar_len, ls.total_ql)
