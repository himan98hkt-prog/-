# -*- coding: utf-8 -*-
"""회귀 테스트용 정확도 측정 (지시서 9장 1단계 · 11장 검증 기준).

    "곡 20개에 대해 정답 화성을 사람이 입력해 두고, 엔진 출력과 비교하는 자동 테스트.
     엔진을 고칠 때마다 정확도가 떨어지지 않는지 확인"

측정 단위는 세그먼트가 아니라 **시간**이다. 엔진이 마디를 어떻게 쪼개든
"곡의 몇 %를 맞는 화음으로 반주했는가"가 실제 들리는 품질이기 때문이다.
지시서 2.2 표의 "32마디 중 틀린 마디"도 같이 센다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import harmony, score_loader

GRID = 0.25        # 16분음표 단위로 표본을 찍는다


def base_qual(q: Optional[str]) -> Optional[str]:
    """반주 품질 관점에서 G 와 G7 은 같은 화음으로 본다."""
    return 'M' if q == '7' else q


@dataclass
class Result:
    song_id: str
    title: str = ''
    key_expected: str = ''
    key_found: str = ''
    key_ok: bool = False
    samples: int = 0
    matched: int = 0
    matched_strict: int = 0
    bars_total: int = 0
    bars_wrong: int = 0
    wrong_bars: List[int] = field(default_factory=list)
    segments: int = 0
    seconds: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.matched / self.samples if self.samples else 0.0

    @property
    def accuracy_strict(self) -> float:
        return self.matched_strict / self.samples if self.samples else 0.0

    def row(self) -> str:
        return (f'{self.song_id:<24} {self.accuracy * 100:6.1f}%  '
                f'{self.accuracy_strict * 100:6.1f}%  '
                f'{"O" if self.key_ok else "X":^4} '
                f'{self.bars_wrong:>3}/{self.bars_total:<3}  {self.seconds:5.2f}s')


def _truth_by_bar(truth: Sequence[dict], bar_offsets: Dict[int, float]):
    """정답지를 {마디번호: [(마디 내 상대위치, 길이, root, qual)]} 로."""
    out: Dict[int, List[tuple]] = {}
    for t in truth:
        m = t['m']
        base = bar_offsets.get(m)
        rel = t['off'] - base if base is not None else t['off']
        out.setdefault(m, []).append((rel, t['len'], t['root'], t['qual']))
    for v in out.values():
        v.sort()
    return out


def _lookup(spans: Sequence[tuple], pos: float):
    for rel, ln, root, qual in spans:
        if rel - 1e-6 <= pos < rel + ln - 1e-6:
            return root, qual
    return (spans[-1][2], spans[-1][3]) if spans else (None, None)


def evaluate(score_path: str, truth_rec: dict, seg_target: float = 2.0,
             adaptive: bool = True, expand_repeats: bool = True,
             use_truth_key: bool = False, **kw) -> Result:
    """한 곡을 분석해 정답지와 대조한다."""
    import time
    t0 = time.time()
    ls = score_loader.load(score_path, expand_repeats=expand_repeats,
                           key_name=truth_rec.get('key') if use_truth_key else None)
    segs = harmony.analyze_segments(ls, seg_target=seg_target, adaptive=adaptive, **kw)
    elapsed = time.time() - t0

    res = Result(song_id=truth_rec['id'], title=truth_rec.get('title', ''),
                 key_expected=truth_rec.get('key', ''), key_found=str(ls.key),
                 segments=len(segs), seconds=round(elapsed, 3))
    res.key_ok = _key_matches(truth_rec.get('key', ''), ls.key)

    # 정답지는 반복을 펼치기 전 기준이므로 '마디 번호 + 마디 내 위치' 로 맞춘다.
    first_offset: Dict[int, float] = {}
    for b in ls.bars:
        first_offset.setdefault(b.number, b.offset)
    truth_bars = _truth_by_bar(truth_rec['truth'], first_offset)

    # 엔진 결과도 마디별로 모은다 (반복 전개로 같은 번호가 여러 번 나올 수 있다)
    eng: Dict[int, List[List[tuple]]] = {}
    bar_by_idx = {b.idx: b for b in ls.bars}
    seen: Dict[int, int] = {}
    for s in segs:
        bar = bar_by_idx.get(s['bar'])
        if bar is None:
            continue
        rel = s['off'] - bar.offset
        eng.setdefault(bar.number, [])
        slot = seen.get(bar.idx)
        if slot is None:
            eng[bar.number].append([])
            seen[bar.idx] = len(eng[bar.number]) - 1
            slot = seen[bar.idx]
        eng[bar.number][slot].append((rel, s['len'], s['root'], s['qual']))

    wrong_bars = set()
    for m, spans in truth_bars.items():
        length = max(r + l for r, l, _rt, _q in spans)
        passes = eng.get(m) or [[]]
        for pass_spans in passes:
            if not pass_spans:
                continue
            pass_spans = sorted(pass_spans)
            pos = 0.0
            bad = False
            while pos < length - 1e-9:
                tr, tq = _lookup(spans, pos)
                er, eq = _lookup(pass_spans, pos)
                res.samples += 1
                if er == tr and base_qual(eq) == base_qual(tq):
                    res.matched += 1
                    if eq == tq or (tq == '7' and eq == '7'):
                        res.matched_strict += 1
                else:
                    bad = True
                pos = round(pos + GRID, 6)
            if bad:
                wrong_bars.add(m)
    res.bars_total = len(truth_bars)
    res.bars_wrong = len(wrong_bars)
    res.wrong_bars = sorted(wrong_bars)
    return res


def _key_matches(expected: str, found) -> bool:
    if not expected:
        return True
    tonic_ok = str(found.tonic.name).replace('-', 'b').upper() == \
        expected.replace('-', 'b').upper()
    mode_ok = (found.mode == 'major') == expected[0].isupper()
    return tonic_ok and mode_ok


# --------------------------------------------------------------------------
# 전체 세트
# --------------------------------------------------------------------------

def load_suite(fixtures_dir: str):
    """(score_path, truth_rec) 목록."""
    scores = os.path.join(fixtures_dir, 'scores')
    truth = os.path.join(fixtures_dir, 'truth')
    out = []
    for name in sorted(os.listdir(truth)):
        if not name.endswith('.json'):
            continue
        with open(os.path.join(truth, name), encoding='utf-8') as f:
            rec = json.load(f)
        path = os.path.join(scores, rec['id'] + '.musicxml')
        if os.path.exists(path):
            out.append((path, rec))
    return out


@dataclass
class Suite:
    results: List[Result] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        s = sum(r.samples for r in self.results)
        return sum(r.matched for r in self.results) / s if s else 0.0

    @property
    def accuracy_strict(self) -> float:
        s = sum(r.samples for r in self.results)
        return sum(r.matched_strict for r in self.results) / s if s else 0.0

    @property
    def key_accuracy(self) -> float:
        return (sum(1 for r in self.results if r.key_ok) / len(self.results)
                if self.results else 0.0)

    @property
    def bars_wrong(self) -> int:
        return sum(r.bars_wrong for r in self.results)

    @property
    def bars_total(self) -> int:
        return sum(r.bars_total for r in self.results)

    @property
    def slowest(self) -> float:
        return max((r.seconds for r in self.results), default=0.0)

    def worst(self, n: int = 5):
        return sorted(self.results, key=lambda r: r.accuracy)[:n]

    def table(self) -> str:
        head = (f'{"곡":<24} {"화성":>7}  {"7화음까지":>7}  {"조성":^4} '
                f'{"틀린마디":>7}  {"시간":>6}')
        lines = [head, '-' * len(head) ]
        for r in self.results:
            lines.append(r.row())
        lines.append('-' * len(head))
        lines.append(f'{"전체":<24} {self.accuracy * 100:6.1f}%  '
                     f'{self.accuracy_strict * 100:6.1f}%  '
                     f'{self.key_accuracy * 100:3.0f}% '
                     f'{self.bars_wrong:>3}/{self.bars_total:<3}  '
                     f'{self.slowest:5.2f}s')
        return '\n'.join(lines)


def run_suite(fixtures_dir: str, **kw) -> Suite:
    suite = Suite()
    for path, rec in load_suite(fixtures_dir):
        suite.results.append(evaluate(path, rec, **kw))
    return suite
