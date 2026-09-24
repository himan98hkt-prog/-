# -*- coding: utf-8 -*-
"""모듈 ② 화성 분석 엔진 — 조성 기반 후보 매칭 + 마디 하위 분할(세그먼트) 분석.

개발지시서 5장 모듈 ② / 12장의 경고를 그대로 지킨다.

  * `chordify().root()` 를 쓰지 않는다 — 실측에서 F장조를 A장조로 오판했다.
  * 마디 단위(1화성/마디)로 하지 않는다 — K.545 처럼 2박마다 바뀌는 곡을 놓친다.
  * 베이스(최저음) 가중을 유지한다. 상성부 가중은 넣지 않는다.
  * 점수 계산식의 상수(miss 0.9 / 베이스 0.30·0.10 / 연속성 0.06)는 건드리지 않는다.

1단계에서 보강한 것 (지시서 9장 "취약 케이스 보강") — 전부 **세그먼트를 어디서
자를지**의 문제이고, 점수식 자체는 손대지 않았다.

  1. 박(beat)에 맞춘 분할   3박자 곡이 1.5박씩 잘리던 것을 고친다.
  2. 적응형 분할           화성이 잦게 바뀌면 더 잘게, 아니면 더 크게 잡는다.
  3. 못갖춘마디            실제 길이로 창을 잡는다 (옆 마디로 밀리지 않게).
  4. 단조 보강             화성단음계의 vii°(이끔음 감삼화음)을 후보에 넣는다.
  5. 이음줄(tie)           이어진 음의 뒷부분에는 첫 박 가중 ×1.5 를 주지 않는다.
  6. 딸림7화음             V·부속화음에 b7 이 실제로 울리면 G -> G7 로 올린다.
"""
from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from music21 import stream

# 화음 구성음 (근음 기준 반음 간격)
TRIAD = {'M': (0, 4, 7), 'm': (0, 3, 7), 'd': (0, 3, 6)}
CHORD_TONES = dict(TRIAD, **{'7': (0, 4, 7, 10)})
NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
QUAL_SUFFIX = {'M': '', 'm': 'm', 'd': 'dim', '7': '7'}
LETTER_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
QUAL_ALIAS = {'': 'M', 'maj': 'M', 'major': 'M', 'M': 'M',
              'm': 'm', 'min': 'm', 'minor': 'm', '-': 'm',
              'dim': 'd', 'o': 'd', '\u00b0': 'd', 'dim7': 'd',
              '7': '7', 'dom7': '7'}

# --- 점수식 상수 (지시서 12장: 실패를 거쳐 나온 값. 바꾸지 말 것) -------------
W_MISS = 0.9           # 화음 밖 음에 대한 벌점
W_BASS_ROOT = 0.30     # 근음이 그 세그먼트의 최저음일 때
W_BASS_TONE = 0.10     # 최저음이 화음 구성음일 때 (자리바꿈)
W_CONTINUITY = 0.06    # 직전 세그먼트와 같은 화음일 때 (과도한 변화 억제)
ONSET_BOOST = 1.5      # 세그먼트 첫 박에 울린 음

# --- 1단계에서 새로 들어온 값 (점수식 밖. 분할·후처리 전용) -------------------
# 20곡 회귀 세트로 고른 값. 셋 다 넓은 평지 안이라 한두 곡 때문에 흔들리는
# 값이 아니다 (pen 0.10~0.12 × sev 0.08~0.12 × third 0.08~0.12 가 전부 98.6% 이상).
SPLIT_PENALTY = 0.10   # 세그먼트를 하나 더 늘릴 때 치러야 하는 설명력
SEVENTH_MIN = 0.10     # b7 이 이 비율 이상 울려야 7화음 후보로 인정한다
SEVENTH_THIRD = 0.08   # 3음(트라이톤의 다른 한쪽)도 이만큼은 울려야 한다


def base_qual(q: Optional[str]) -> Optional[str]:
    """G 와 G7 은 반주 관점에서 같은 화음 — 연속성 판정에 쓴다."""
    return 'M' if q == '7' else q


def label(root: Optional[int], qual: Optional[str]) -> str:
    """(9, 'M') -> 'A'  /  (7, '7') -> 'G7'  /  (None, None) -> '—'"""
    if root is None or qual is None:
        return '—'
    return NAMES[root % 12] + QUAL_SUFFIX.get(qual, '')


def parse_label(text: str) -> Optional[Tuple[int, str]]:
    """'G7' -> (7, '7'). 화성 확인 화면에서 사람이 고친 값을 되읽을 때 쓴다.

    이명동음(G#/Ab, Db/C#)과 겹올림/겹내림도 받는다. 원장님이 드롭다운 대신
    직접 타이핑하는 경우가 있기 때문이다.
    """
    if not text:
        return None
    t = text.strip().replace('\u266f', '#').replace('\u266d', 'b')
    if not t or t in ('\u2014', '-'):
        return None
    m = re.match(r'^([A-Ga-g])([#b]{0,2})(.*)$', t)
    if not m:
        return None
    letter, acc, rest = m.groups()
    root = LETTER_PC[letter.upper()]
    for ch in acc:
        root += 1 if ch == '#' else -1
    root %= 12
    rest = rest.strip()
    qual = QUAL_ALIAS.get(rest.lower())
    return (root, qual) if qual else None


def key_candidates(k, sevenths: bool = True) -> List[Tuple[int, str]]:
    """조성의 다이어토닉 3화음 + 부속화음을 후보로."""
    tonic = k.tonic.pitchClass
    major = k.mode == 'major'
    deg = [0, 2, 4, 5, 7, 9, 11] if major else [0, 2, 3, 5, 7, 8, 10]
    qual = (['M', 'm', 'm', 'M', 'M', 'm', 'd'] if major
            else ['m', 'd', 'M', 'm', 'M', 'M', 'M'])
    c = [((tonic + d) % 12, q) for d, q in zip(deg, qual)]
    for d in ([2, 9, 4, 0] if major else [2, 7, 5]):  # V/V, V/ii, V/vi, V/IV
        c.append(((tonic + d) % 12, 'M'))
    if not major:
        c.append(((tonic + 7) % 12, 'M'))             # 화성단음계의 V
        c.append(((tonic + 11) % 12, 'd'))            # 화성단음계의 vii° — 1단계 보강
    c = list(dict.fromkeys(c))
    if sevenths:
        # 장3화음 후보마다 딸림7화음 짝을 붙인다. b7 이 실제로 울리지 않으면
        # `score_candidates` 가 후보에서 빼므로 G 가 G7 로 부풀지 않는다.
        c += [(r, '7') for r, q in c if q == 'M']
    return c


# --------------------------------------------------------------------------
# 음 수집
# --------------------------------------------------------------------------

@dataclass
class SoundingNote:
    off: float
    ql: float
    pc: int
    midi: int
    onset: bool       # 새로 시작하는 음인가 (이음줄 뒷부분이면 False)


def collect(sc: stream.Score) -> List[SoundingNote]:
    """악보에서 울리는 음을 (위치, 길이, pitch class, MIDI번호) 로 모은다."""
    out: List[SoundingNote] = []
    parts = list(sc.parts) or [sc]
    for p in parts:
        for n in p.flatten().notes:
            ql = float(n.quarterLength) or 0.25
            off = float(n.offset)
            onset = True
            tie = getattr(n, 'tie', None)
            if tie is not None and getattr(tie, 'type', None) in ('stop', 'continue'):
                onset = False
            for pi in n.pitches:
                out.append(SoundingNote(off, ql, pi.pitchClass, pi.midi, onset))
    out.sort(key=lambda s: s.off)
    return out


class _NoteIndex:
    """세그먼트마다 전체 음을 훑지 않도록 하는 가벼운 색인."""

    def __init__(self, notes: Sequence[SoundingNote]):
        self.notes = list(notes)
        self.offs = [n.off for n in self.notes]
        self.max_ql = max((n.ql for n in self.notes), default=0.0)

    def window(self, s0: float, s1: float):
        lo = bisect_left(self.offs, s0 - self.max_ql - 1e-6)
        for n in self.notes[lo:]:
            if n.off >= s1 - 1e-9:
                break
            if n.off + n.ql <= s0 + 1e-9:
                continue
            yield n


def segment_weights(index: _NoteIndex, s0: float, s1: float):
    """세그먼트 안에서 울린 pitch class 를 지속시간으로 가중 집계.

    세그먼트 안쪽의 박 머리에도 가중을 주는 안을 시험했지만 20곡 전체에서
    ±0.3%p (165마디 중 1마디) 안쪽으로만 움직였고 가중치를 키우면 다시
    나빠졌다. 노이즈 수준의 이득을 위해 검증된 가중식에 상수를 더 붙이지
    않는다 (지시서 12장).
    """
    w: Dict[int, float] = {}
    lowest: Optional[int] = None
    for n in index.window(s0, s1):
        ov = min(n.off + n.ql, s1) - max(n.off, s0)
        if ov <= 0:
            continue
        boost = ONSET_BOOST if (n.onset and abs(n.off - s0) < 0.01) else 1.0
        w[n.pc] = w.get(n.pc, 0.0) + ov * boost
        if lowest is None or n.midi < lowest:
            lowest = n.midi
    return w, lowest


# --------------------------------------------------------------------------
# 점수 계산 — 지시서 5장의 식 그대로
# --------------------------------------------------------------------------

def score_candidates(w: Dict[int, float], cands: Sequence[Tuple[int, str]],
                     prev=None, bass_pc: Optional[int] = None):
    """후보 화음을 점수순으로. [( (root,qual), score, purity ), ...]"""
    if not w:
        return []
    total = sum(w.values())
    rows = []
    prev_base = (prev[0], base_qual(prev[1])) if prev else None
    for root, q in cands:
        if q == '7':
            # 딸림7화음의 정체는 **3음과 b7 사이의 트라이톤**이다. 둘 중 하나라도
            # 안 울리면 그건 7화음이 아니라, 마침 그 음들을 품고 있는 유령이다.
            # (실측: 이 조건이 없으면 Bb장조에서 B♮ 없는 'G7' 이 정답을 밀어냈다)
            if (w.get((root + 10) % 12, 0.0) < total * SEVENTH_MIN
                    or w.get((root + 4) % 12, 0.0) < total * SEVENTH_THIRD):
                continue
        tones = {(root + i) % 12 for i in CHORD_TONES[q]}
        hit = sum(v for pc, v in w.items() if pc in tones)
        s = hit - (total - hit) * W_MISS
        purity = s / total if total else 0.0
        if bass_pc is not None:
            if root == bass_pc:
                s += total * W_BASS_ROOT       # 근음이 베이스에 있으면 강하게 우대
            elif bass_pc in tones:
                s += total * W_BASS_TONE       # 자리바꿈도 인정
        if prev_base and (root, base_qual(q)) == prev_base:
            s += total * W_CONTINUITY          # 과도한 화성 변화 억제 (G -> G7 도 같은 화음)
        rows.append(((root, q), s, purity))
    rows.sort(key=lambda r: -r[1])
    return rows


def best_chord(w, cands, prev=None, bass_pc=None):
    """프로토타입과 같은 서명 — 최고점 화음만 돌려준다."""
    rows = score_candidates(w, cands, prev, bass_pc)
    return rows[0][0] if rows else None


# --------------------------------------------------------------------------
# 세그먼트 분할
# --------------------------------------------------------------------------

def split_options(bar_ql: float, beat_ql: float) -> List[int]:
    """박에 맞아떨어지는 분할 수만 후보로.

    3/4  -> 박 3개 -> [1, 3]        (1.5 박씩 자르던 버그가 여기서 사라진다)
    4/4  -> 박 4개 -> [1, 2, 4]
    6/8  -> 박 2개 -> [1, 2]        (점4분음표 = 1.5ql 단위)
    12/8 -> 박 4개 -> [1, 2, 4]
    """
    if beat_ql <= 0:
        return [1]
    nbeats = int(round(bar_ql / beat_ql))
    if nbeats < 1:
        return [1]
    return [n for n in range(1, nbeats + 1) if nbeats % n == 0]


def base_split(bar_ql: float, beat_ql: float, seg_target: float) -> int:
    """seg_target(기본 2박)에 가장 가까운 분할. 같으면 더 성긴 쪽."""
    opts = split_options(bar_ql, beat_ql)
    return min(opts, key=lambda n: (abs(bar_ql / n - seg_target), n))


def legacy_split(bar_ql: float, seg_target: float) -> int:
    """프로토타입의 분할 규칙. 비교용으로만 남긴다.

    박을 보지 않기 때문에 3/4 마디가 1.5박씩 잘려 박을 가로지른다.
    """
    return max(1, round(bar_ql / seg_target)) if bar_ql > seg_target * 1.2 else 1


def _evaluate(index: _NoteIndex, cands, start: float, length: float, nseg: int, prev):
    """주어진 분할로 잘라 봤을 때의 결과와 평균 설명력(purity)."""
    slen = length / nseg
    rows_out, wsum, psum, cur = [], 0.0, 0.0, prev
    for i in range(nseg):
        s0 = start + i * slen
        s1 = s0 + slen
        w, lowest = segment_weights(index, s0, s1)
        rows = score_candidates(w, cands, cur, None if lowest is None else lowest % 12)
        rows_out.append((s0, slen, w, lowest, rows))
        if rows:
            cur = rows[0][0]
            tw = sum(w.values())
            wsum += tw
            psum += rows[0][2] * tw
    purity = (psum / wsum) if wsum else -1e9
    return rows_out, purity, cur


def analyze_segments(src, k=None, seg_target: float = 2.0,
                     adaptive: bool = True,
                     split_penalty: Optional[float] = None,
                     split_mode: Optional[str] = None,
                     sevenths: bool = True) -> List[dict]:
    """마디를 seg_target(4분음표 단위) 길이로 쪼개 화성 추정.

    src 는 `score_loader.LoadedScore` 이거나 music21 Score.
    Score 를 주면 k(조성)도 같이 줘야 한다 (프로토타입 호환).
    """
    from . import score_loader

    if isinstance(src, score_loader.LoadedScore):
        ls = src
        if k is not None:
            ls.key = k
    else:
        ls = score_loader.from_score(src, expand_repeats=False)
        if k is not None:
            ls.key = k
    k = ls.key

    mode = split_mode or ('adaptive' if adaptive else 'fixed')
    if mode not in ('adaptive', 'fixed', 'legacy'):
        raise ValueError(f"모르는 분할 방식입니다: {mode!r} "
                         '(가능: adaptive, fixed, legacy)')
    cands = key_candidates(k, sevenths=sevenths)
    index = _NoteIndex(collect(ls.score))
    penalty = SPLIT_PENALTY if split_penalty is None else split_penalty

    segs: List[dict] = []
    prev = None
    for bar in ls.bars:
        opts = split_options(bar.length, bar.beat_length)

        if mode != 'adaptive':
            chosen = (legacy_split(bar.length, seg_target) if mode == 'legacy'
                      else base_split(bar.length, bar.beat_length, seg_target))
            rows_out, _purity, _nxt = _evaluate(
                index, cands, bar.offset, bar.length, chosen, prev)
        else:
            # 이 마디를 몇 조각으로 자를지 스스로 고른다.
            #
            #     점수 = 설명력(purity) - 조각을 늘린 대가
            #
            # 조각을 늘리면 각 조각은 언제나 더 잘 맞는다. 그래서 대가를 물리지
            # 않으면 베이스가 움직일 때마다(알베르티·왈츠) 그 음을 근음으로
            # 착각해 화성이 잘게 흔들린다. 반대로 대가가 너무 크면 K.545 처럼
            # 2박마다 바뀌는 곡을 통째로 뭉갠다. 20곡 회귀 세트로 고른 값이 0.10.
            rows_out, best = None, None
            for n in opts:
                r2, p2, _nx = _evaluate(index, cands, bar.offset, bar.length, n, prev)
                sc2 = p2 - penalty * (n - 1)
                if best is None or sc2 > best + 1e-9:
                    rows_out, best = r2, sc2

        for i, (s0, slen, w, lowest, rows) in enumerate(rows_out):
            if rows:
                (root, qual), sc_, _pu = rows[0]
                margin = sc_ - rows[1][1] if len(rows) > 1 else sc_
                alts = [{'root': r, 'qual': q, 'score': round(s, 3)}
                        for (r, q), s, _p in rows[1:4]]
                prev = (root, qual)
            else:
                # 음이 없는 구간은 직전 화성 유지 (지시서 5장 6번)
                if prev is None:
                    root = qual = None
                else:
                    root, qual = prev
                sc_, margin, alts = 0.0, 0.0, []
            segs.append({
                'bar': bar.idx, 'm': bar.number, 'i': i,
                'off': round(s0, 6), 'len': round(slen, 6),
                'root': root, 'qual': qual,
                'label': label(root, qual),
                'score': round(sc_, 3), 'margin': round(margin, 3),
                'conf': _confidence(margin, w), 'alts': alts,
            })
    return segs


def _confidence(margin: float, w: Dict[int, float]) -> float:
    """0~1. 화성 확인 화면에서 노란색으로 강조할 구간을 고르는 데 쓴다."""
    total = sum(w.values()) if w else 0.0
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, margin / total)), 3)


def low_confidence(segs: Sequence[dict], threshold: float = 0.15) -> List[dict]:
    """확신이 약한 세그먼트 — 지시서 10장 '노란색 강조' 대상."""
    return [s for s in segs if s.get('conf', 1.0) < threshold]


def to_grid(segs: Sequence[dict], per_row: int = 4) -> str:
    """지시서 10장 화성 확인 화면과 같은 모양의 텍스트 표."""
    rows, cur, num = [], [], None
    cells: List[Tuple[int, str]] = []
    for s in segs:
        if s['m'] != num:
            num = s['m']
            cells.append((num, []))
        cells[-1][1].append(s['label'])
    for i, (m, labels) in enumerate(cells):
        cur.append(f"m{m:<3d} " + ' '.join(f'{x:<4}' for x in labels))
        if len(cur) == per_row:
            rows.append(' │ '.join(cur))
            cur = []
    if cur:
        rows.append(' │ '.join(cur))
    return '\n'.join(rows)


def merge(segs: Sequence[dict]) -> List[dict]:
    """붙어 있는 같은 화음을 하나로 — 반주에서 패드가 끊기지 않게."""
    out: List[dict] = []
    for s in segs:
        if s.get('root') is None:
            continue
        if (out and out[-1]['root'] == s['root'] and out[-1]['qual'] == s['qual']
                and abs(out[-1]['off'] + out[-1]['len'] - s['off']) < .01):
            out[-1]['len'] += s['len']
        else:
            out.append(dict(s))
    return out
