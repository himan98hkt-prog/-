# -*- coding: utf-8 -*-
"""회귀 테스트용 오리지널 악보 생성기.

`pieces.PIECES` 의 사양 -> MusicXML(`scores/`) + 정답 화성(`truth/`).

정답지를 사람이 받아 적는 대신 **정답에서 악보를 만든다.** 그래서 정답지에
오류가 섞일 수 없다. 대신 곡이 너무 쉬워지지 않도록 화음 밖의 음(경과음·보조음)을
일부러 섞는다 — 화성 분석이 실제로 해야 하는 일이 그것이기 때문이다.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from music21 import bar, chord, clef, key, layout, meter, note, stream

from piano_mr.harmony import CHORD_TONES, parse_label
import pieces as piece_specs

HERE = os.path.dirname(os.path.abspath(__file__))
SCORES = os.path.join(HERE, 'scores')
TRUTH = os.path.join(HERE, 'truth')

RH_CENTER, RH_LO, RH_HI = 72, 62, 86
LH_CENTER, LH_LO, LH_HI = 48, 33, 62

MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11]
MINOR_STEPS = [0, 2, 3, 5, 7, 8, 10]


def scale_pcs(key_name: str):
    tonic = parse_label(key_name[0].upper() + key_name[1:])[0]
    steps = MAJOR_STEPS if key_name[0].isupper() else MINOR_STEPS
    return tonic, [(tonic + s) % 12 for s in steps]


def chord_pitches(label: str):
    root, qual = parse_label(label)
    return root, qual, [(root + i) % 12 for i in CHORD_TONES[qual]]


def nearest(pc_set, target: int, lo: int, hi: int) -> int:
    """target 에 가장 가까우면서 pc_set 에 속하는 MIDI 음."""
    best, bd = None, 1e9
    for p in range(lo, hi + 1):
        if p % 12 in pc_set:
            d = abs(p - target)
            if d < bd:
                best, bd = p, d
    return best if best is not None else target


def step_in_scale(p: int, sc_pcs, direction: int, lo: int, hi: int) -> int:
    q = p + direction
    for _ in range(3):
        if lo <= q <= hi and q % 12 in sc_pcs:
            return q
        q += direction
    return max(lo, min(hi, p + direction))


# --------------------------------------------------------------------------
# 리듬
# --------------------------------------------------------------------------

RH_RHYTHM = {
    'quarter':       [1.0],
    'eighth':        [0.5],
    'sixteenth':     [0.25],
    'waltz_melody':  [1.0, 0.5, 0.5, 1.0],
    'minuet':        [1.0, 0.5, 0.5, 1.0],
    'compound':      [0.5],
}


def rhythm_for(pattern: str, length: float):
    """span 길이를 패턴 리듬으로 채운다."""
    base = RH_RHYTHM.get(pattern, [1.0])
    out, t, i = [], 0.0, 0
    while t < length - 1e-9:
        d = base[i % len(base)]
        if t + d > length + 1e-9:
            d = length - t
        out.append((t, round(d, 4)))
        t = round(t + d, 6)
        i += 1
    return out


# --------------------------------------------------------------------------
# 오른손 선율 — 강박은 화음음, 약박은 경과음
# --------------------------------------------------------------------------

def melody_for_span(label: str, length: float, pattern: str, sc_pcs,
                    cur: int, beat: float, seq: int):
    """강박은 화음음, 약박은 음계로 이어지는 경과음.

    실제 대상 레퍼토리(체르니·하농·부르크뮐러)의 짜임새가 그렇고, 무엇보다
    **정답지가 애매해지지 않는다.** 강박까지 화음 밖 음으로 채우면 "이 마디의
    화음이 무엇인가"에 정답이 둘 이상 생겨서, 회귀 테스트가 엔진이 아니라
    정답지를 재는 시험이 되어 버린다.

    선율은 한 방향으로 계속 걸어가다가 박 머리에서 가장 가까운 화음음으로
    내려앉는다. 16분음표 연습곡이면 자연스러운 음계 주행이 되고,
    4분음표 곡이면 화음음 사이를 오가는 분산화음이 된다.
    """
    root, qual, pcs = chord_pitches(label)
    slots = rhythm_for(pattern, length)
    pcset = set(pcs)
    direction = 1 if seq % 2 == 0 else -1

    strong = {i for i, (t, _d) in enumerate(slots)
              if abs((t / beat) - round(t / beat)) < 1e-6}
    if not strong:
        strong = {0}

    out = []
    p = cur
    for i, (t, d) in enumerate(slots):
        if i in strong:
            p = nearest(pcset, p + direction * 2, RH_LO, RH_HI)
            if out and p == out[-1][2]:
                p = nearest(pcset, p + direction * 3, RH_LO, RH_HI)
        else:
            p = step_in_scale(p, sc_pcs, direction, RH_LO, RH_HI)
        if p <= RH_LO + 2 or p >= RH_HI - 2:
            direction = -direction
        out.append((t, d, p))

    return out, out[-1][2] if out else cur


# --------------------------------------------------------------------------
# 왼손 텍스처
# --------------------------------------------------------------------------

def lh_for_span(label: str, length: float, texture: str, beat: float, idx: int):
    """[(offset, ql, [midi...]), ...]"""
    root, qual, pcs = chord_pitches(label)
    base = nearest({root}, LH_CENTER - 6, LH_LO, LH_HI)
    tri = [base]
    for pc in pcs[1:]:                     # 7화음이면 b7 까지 실제로 울린다
        tri.append(nearest({pc}, tri[-1] + 3, LH_LO, LH_HI))

    if texture == 'block':
        return [(0.0, length, tri)]

    if texture == 'inversion':
        n = len(tri)
        rot = [tri[(i + 1 + idx % 2) % n] for i in range(n)]
        rot = sorted(nearest({p % 12}, LH_CENTER - 4 + i * 4, LH_LO, LH_HI)
                     for i, p in enumerate(rot))
        return [(0.0, length, rot)]

    if texture == 'two_voice':
        half = length / 2
        if half < 0.5:
            return [(0.0, length, [tri[0]])]
        second = tri[3] if len(tri) > 3 else tri[2]
        return [(0.0, half, [tri[0]]), (half, half, [second])]

    if texture == 'waltz':
        if length >= 3.0 - 1e-6:
            return [(0.0, 1.0, [tri[0]]), (1.0, 1.0, tri[1:]), (2.0, 1.0, tri[1:])]
        if length >= 2.0 - 1e-6:
            return [(0.0, 1.0, [tri[0]]), (1.0, 1.0, tri[1:])]
        return [(0.0, length, [tri[0]])]

    if texture == 'octave':
        out, t, up = [], 0.0, False
        while t < length - 1e-9:
            d = min(0.5, length - t)
            out.append((t, d, [tri[0] + (12 if up else 0)]))
            up = not up
            t = round(t + d, 6)
        return out

    if texture == 'alberti':
        order = ([tri[0], tri[2], tri[1], tri[3]] if len(tri) > 3
                 else [tri[0], tri[2], tri[1], tri[2]])
        out, t, i = [], 0.0, 0
        while t < length - 1e-9:
            d = min(0.5, length - t)
            out.append((t, d, [order[i % 4]]))
            t = round(t + d, 6)
            i += 1
        return out

    if texture == 'arp':
        order = (list(tri) if len(tri) > 3 else [tri[0], tri[1], tri[2], tri[0] + 12])
        out, t, i = [], 0.0, 0
        step = 0.5 if beat >= 1.0 else 0.5
        while t < length - 1e-9:
            d = min(step, length - t)
            out.append((t, d, [order[i % 4]]))
            t = round(t + d, 6)
            i += 1
        return out

    raise ValueError(f'모르는 왼손 텍스처: {texture}')


# --------------------------------------------------------------------------
# 악보 조립
# --------------------------------------------------------------------------

def build_piece(spec: dict):
    ts = meter.TimeSignature(spec['ts'])
    beat = float(ts.beatDuration.quarterLength)
    bar_ql = float(ts.barDuration.quarterLength)
    tonic, sc_pcs = scale_pcs(spec['key'])
    ks = key.Key(spec['key'])

    sc = stream.Score()
    rh = stream.Part(id='RH')
    lh = stream.Part(id='LH')
    rh.insert(0, clef.TrebleClef())
    lh.insert(0, clef.BassClef())

    all_bars = list(spec['bars'])
    pickup = spec.get('pickup')
    truth = []
    cur = RH_CENTER
    seq = 0
    offset = 0.0
    mnum = 1

    def emit(bar_spec, is_pickup=False):
        nonlocal cur, seq, offset, mnum
        mr = stream.Measure(number=mnum)
        ml = stream.Measure(number=mnum)
        if mnum == 1 or (is_pickup and mnum == 0):
            mr.insert(0, ks)
            ml.insert(0, ks)
            mr.insert(0, ts)
            ml.insert(0, ts)
        if is_pickup:
            total = sum(d for _l, d in bar_spec)
            mr.paddingLeft = bar_ql - total
            ml.paddingLeft = bar_ql - total
        t = 0.0
        for label, dur in bar_spec:
            dur = float(dur)
            mel, cur = melody_for_span(label, dur, spec['rh'], sc_pcs, cur, beat, seq)
            for (mt, md, p) in mel:
                n = note.Note(p)
                n.quarterLength = md
                mr.insert(t + mt, n)
            for (lt, ld, ps) in lh_for_span(label, dur, spec['lh'], beat, seq):
                el = note.Note(ps[0]) if len(ps) == 1 else chord.Chord(ps)
                el.quarterLength = ld
                ml.insert(t + lt, el)
            root, qual, _ = chord_pitches(label)
            truth.append({'m': mnum, 'off': round(offset + t, 6), 'len': dur,
                          'root': root, 'qual': qual, 'label': label})
            t += dur
            seq += 1
        rh.append(mr)
        lh.append(ml)
        offset += t
        mnum += 1
        return mr, ml

    if pickup:
        mnum = 0
        emit(pickup, is_pickup=True)
        mnum = 1
    for i, b in enumerate(all_bars):
        mr, ml = emit(b)
        if spec.get('repeat') and i == 0:
            mr.leftBarline = bar.Repeat(direction='start')
            ml.leftBarline = bar.Repeat(direction='start')
        if spec.get('repeat') and i == len(all_bars) // 2 - 1:
            mr.rightBarline = bar.Repeat(direction='end')
            ml.rightBarline = bar.Repeat(direction='end')

    sc.insert(0, layout.StaffGroup([rh, lh], symbol='brace'))
    sc.insert(0, rh)
    sc.insert(0, lh)
    sc.metadata = None
    return sc, truth


def main():
    os.makedirs(SCORES, exist_ok=True)
    os.makedirs(TRUTH, exist_ok=True)
    made = []
    for spec in piece_specs.PIECES:
        sc, truth = build_piece(spec)
        xml = os.path.join(SCORES, spec['id'] + '.musicxml')
        sc.write('musicxml', fp=xml)
        rec = {'id': spec['id'], 'title': spec['title'], 'key': spec['key'],
               'time': spec['ts'], 'level': spec.get('level', 1),
               'default_style': spec.get('style', 'strings'),
               'lh': spec['lh'], 'rh': spec['rh'],
               'pickup': bool(spec.get('pickup')), 'repeat': bool(spec.get('repeat')),
               'measures': len(spec['bars']), 'truth': truth}
        with open(os.path.join(TRUTH, spec['id'] + '.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        made.append(spec['id'])
        print(f"  {spec['id']:<24} {len(truth):3d} spans  {spec['ts']:<4} {spec['key']}")
    print(f'\n{len(made)}곡 생성 -> {SCORES}')


if __name__ == '__main__':
    main()
