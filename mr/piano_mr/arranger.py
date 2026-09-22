# -*- coding: utf-8 -*-
"""자동 반주 엔진 — 분석된 화성 + 편성 스타일 -> 반주 MIDI.

프로토타입 `arranger2.py` 의 이식본. 지시서 12장이 "지키라"고 한 것:

  * 세그먼트 단위 분석 유지            (harmony.py 가 담당)
  * 베이스 가중 유지                   (harmony.py 가 담당)
  * 패드를 멜로디 최저음 아래로 보내는 보이싱 규칙 유지   <- `voice()`

저장 원칙(지시서 6장): 오디오가 아니라 **이 MIDI(2.4 KB)** 를 카탈로그에 저장한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from mido import MetaMessage, MidiFile, MidiTrack, Message, bpm2tempo

from . import harmony, orchestration as orch
from . import score_loader

TPB = 480                  # ticks per beat — render.combine 과 반드시 같아야 한다
PITCH_MIN, PITCH_MAX = 24, 103
PAD_FLOOR = 36             # 패드가 이보다 내려가면 웅웅거린다
CLICK_HI, CLICK_LO = 76, 77        # 카운트인 우드블록 (GM 드럼)


@dataclass
class Arrangement:
    midi: MidiFile
    used: Dict[str, dict]
    key: str
    time: str
    style: str
    level: str
    curve: str
    bpm: float
    bars: int
    segments: int
    lead_ql: float = 0.0
    plan: Dict[int, str] = field(default_factory=dict)

    def save(self, path: str) -> str:
        self.midi.save(path)
        return path

    def info(self) -> dict:
        return {'key': self.key, 'time': self.time, 'style': self.style,
                'level': self.level, 'curve': self.curve, 'bpm': self.bpm,
                'bars': self.bars, 'segments': self.segments,
                'lead_ql': self.lead_ql,
                'instruments': {r: v['instrument'] for r, v in self.used.items()}}


# --------------------------------------------------------------------------
# 보이싱 — 지시서 5장 모듈 ③
# --------------------------------------------------------------------------

def voice(root: int, qual: str, ceiling: int) -> List[int]:
    """화음을 **그 마디 멜로디 최저음 아래**에 배치한다.

    패드가 멜로디와 같은 높이에 있으면 아이의 선율이 묻힌다. 지시서의 규칙:
        while max(triad) >= melody_low - 1:  triad = [p-12 ...]
        while min(triad) < 36:               triad = [p+12 ...]
    """
    third = 3 if qual == 'm' else 4
    fifth = 6 if qual == 'd' else 7
    base = root + PAD_FLOOR
    guard = 0
    while base + 12 <= ceiling - 16 and guard < 8:
        base += 12
        guard += 1
    tri = [base, base + third, base + fifth]
    guard = 0
    while max(tri) >= ceiling - 1 and guard < 8:
        tri = [p - 12 for p in tri]
        guard += 1
    guard = 0
    while min(tri) < PAD_FLOOR and guard < 8:
        tri = [p + 12 for p in tri]
        guard += 1
    return tri


def _seventh_pitch(tri: Sequence[int], qual: str) -> Optional[int]:
    """딸림7화음일 때 color 파트가 덧붙일 b7."""
    return tri[0] + 10 if qual == '7' else None


# --------------------------------------------------------------------------
# 연출 곡선 — 지시서 5장 "감동은 반주가 들어오는 순간에서 나온다"
# --------------------------------------------------------------------------

def stage_plan(bars: Sequence[int], curve: str = 'build',
               top_level: str = 'rich') -> Dict[int, str]:
    """마디별 레벨 계획. 기본 `build` 는 곡을 4등분해 off -> simple -> normal -> rich."""
    orch.check_level(top_level)
    n = len(bars)
    if n == 0:
        return {}
    if curve == 'flat':
        return {b: top_level for b in bars}
    if curve in orch.LEVELS:            # 'simple'/'normal'/'rich' 를 곡선으로 준 경우
        return {b: curve for b in bars}
    if curve != 'build':
        raise ValueError(f"모르는 연출 곡선입니다: {curve!r} (가능: build, flat, "
                         + ', '.join(orch.LEVELS) + ')')

    top = orch.LEVEL_ORDER.index(top_level)          # off=0 simple=1 normal=2 rich=3
    stages = ['off'] + [orch.LEVEL_ORDER[min(i, top)] for i in (1, 2, 3)]
    q = max(1, n // 4)
    plan = {}
    for i, b in enumerate(bars):
        plan[b] = stages[min(3, i // q)]
    return plan


# --------------------------------------------------------------------------
# 반주 생성
# --------------------------------------------------------------------------

class _Events:
    def __init__(self):
        self.by_channel: Dict[int, List] = {}

    def put(self, ch: int, pitch: int, start_ql: float, dur_ql: float, vel: int):
        pitch = max(PITCH_MIN, min(PITCH_MAX, int(pitch)))
        vel = max(1, min(127, int(vel)))
        t0 = int(round(start_ql * TPB))
        t1 = int(round((start_ql + dur_ql) * TPB)) - 8
        lst = self.by_channel.setdefault(ch, [])
        lst.append((t0, Message('note_on', channel=ch, note=pitch, velocity=vel)))
        lst.append((max(t0 + 20, t1), Message('note_off', channel=ch, note=pitch, velocity=0)))


def build(segs: Sequence[dict], ls: score_loader.LoadedScore, style: str = 'strings',
          level: str = 'rich', curve: str = 'build', bpm: float = 120.0,
          count_in: int = 0) -> Arrangement:
    orch.check_style(style)
    orch.check_level(level)

    bar_ids = sorted({s['bar'] for s in segs if s.get('root') is not None})
    plan = stage_plan(bar_ids, curve, level)
    bar_info = {b.idx: b for b in ls.bars}

    lead_ql = 0.0
    if count_in > 0:
        first = ls.bars[0] if ls.bars else None
        lead_ql = (first.bar_length if first else 4.0) * count_in

    ev = _Events()
    used: Dict[str, dict] = {}
    merged = harmony.merge(segs)

    for s in merged:
        lvl = plan.get(s['bar'], 'off')
        if lvl == 'off':
            continue
        roles = orch.resolve(style, lvl)
        used.update(roles)

        bar = bar_info.get(s['bar'])
        ceil = (bar.melody_low if bar and bar.melody_low else None) or 72
        blen = bar.bar_length if bar else 4.0
        off = s['off'] + lead_ql
        tri = voice(s['root'], s['qual'], ceil)
        first_in_bar = bar is not None and abs(s['off'] - bar.offset) < .01

        if 'pad' in roles:
            r = roles['pad']
            for p in tri:
                ev.put(r['channel'], p, off, s['len'], r['velocity'])
        if 'bass' in roles:
            r = roles['bass']
            ev.put(r['channel'], max(28, tri[0] - 12), off, s['len'], r['velocity'])
        if 'color' in roles and s['len'] >= 1.0:
            r = roles['color']
            arp = list(tri)
            sev = _seventh_pitch(tri, s['qual'])
            if sev is not None:
                arp.append(sev)
            arp.append(tri[0] + 12)
            step = s['len'] / len(arp)
            for i, p in enumerate(arp):
                ev.put(r['channel'], p, off + i * step, min(s['len'], step * 2.5), r['velocity'])
        if 'counter' in roles and first_in_bar and s['len'] >= 1.0:
            r = roles['counter']
            ev.put(r['channel'], tri[2] + 12, off, s['len'], r['velocity'])
        if 'perc' in roles and first_in_bar:
            r = roles['perc']
            beats = max(1, int(round(blen)))
            for b in range(beats):
                drum = 36 if b == 0 else 42          # 베이스드럼 / 하이햇
                ev.put(9, drum, off + b, 0.4, r['velocity'] + (8 if b == 0 else 0))

    _add_accent(ev, merged, bar_info, plan, style, used, lead_ql)
    _add_count_in(ev, ls, count_in)

    mf = _to_midi(ev, used, ls, bpm, lead_ql, count_in)
    return Arrangement(midi=mf, used=used, key=str(ls.key),
                       time=ls.time_signature.ratioString, style=style, level=level,
                       curve=curve, bpm=bpm, bars=len(ls.bars), segments=len(segs),
                       lead_ql=lead_ql, plan=plan)


def _add_accent(ev, merged, bar_info, plan, style, used, lead_ql):
    """마지막 마디의 클라이맥스 한 방 (곡당 1~2회)."""
    rich = orch.resolve(style, 'rich')
    if 'accent' not in rich or not merged:
        return
    r = rich['accent']
    last_bar = max(s['bar'] for s in merged)
    if plan.get(last_bar) != 'rich':
        return
    last = [s for s in merged if s['bar'] == last_bar]
    if not last:
        return
    s = last[0]
    bar = bar_info.get(s['bar'])
    ceil = (bar.melody_low if bar and bar.melody_low else None) or 72
    tri = voice(s['root'], s['qual'], ceil)
    off = s['off'] + lead_ql
    if r['instrument'] == 'timpani':
        for i in range(6):                       # 팀파니 롤 크레셴도
            ev.put(r['channel'], tri[0] - 12, off + i * s['len'] / 6,
                   s['len'] / 6, r['velocity'] - 14 + i * 5)
    else:
        ev.put(r['channel'], tri[2], off, s['len'], r['velocity'])
    used['accent'] = r


def _add_count_in(ev, ls, count_in: int):
    """카운트인 N마디 (지시서 모듈 ⑤-4). 첫 박만 높은 우드블록."""
    if count_in <= 0 or not ls.bars:
        return
    first = ls.bars[0]
    beats = max(1, int(round(first.bar_length / first.beat_length)))
    for b in range(count_in):
        for i in range(beats):
            t = b * first.bar_length + i * first.beat_length
            ev.put(9, CLICK_HI if i == 0 else CLICK_LO, t, 0.2, 84 if i == 0 else 64)


def _to_midi(ev: _Events, used: Dict[str, dict], ls, bpm: float,
             lead_ql: float, count_in: int) -> MidiFile:
    mf = MidiFile(ticks_per_beat=TPB)
    meta = MidiTrack()
    mf.tracks.append(meta)
    meta.append(MetaMessage('set_tempo', tempo=bpm2tempo(bpm), time=0))
    ts = ls.time_signature
    meta.append(MetaMessage('time_signature', numerator=ts.numerator,
                            denominator=ts.denominator, time=0))
    meta.append(MetaMessage('end_of_track',
                            time=int(round((ls.total_ql + lead_ql) * TPB))))

    tracks = dict(used)
    if count_in > 0 and 'perc' not in tracks:
        tracks['count_in'] = {'program': 0, 'velocity': 84, 'channel': 9,
                              'instrument': 'drums'}

    for role, spec in tracks.items():
        ch = spec['channel']
        msgs = ev.by_channel.get(ch)
        if not msgs:
            continue
        tr = MidiTrack()
        mf.tracks.append(tr)
        tr.append(MetaMessage('track_name', name=role, time=0))
        if ch != 9:
            tr.append(Message('program_change', channel=ch, program=spec['program'], time=0))
        # 같은 시각이면 note_off 를 먼저 — 같은 음을 다시 칠 때 끊기지 않게
        msgs.sort(key=lambda x: (x[0], 0 if x[1].type == 'note_off' else 1))
        prev = 0
        for t, m in msgs:
            tr.append(m.copy(time=t - prev))
            prev = t
        tr.append(MetaMessage('end_of_track', time=0))
        ev.by_channel.pop(ch, None)     # 한 채널이 두 트랙에 쓰이지 않게
    return mf


def arrange(path_or_score, style: str = 'strings', level: str = 'rich',
            curve: str = 'build', bpm: float = 120.0, count_in: int = 0,
            transpose: int = 0, seg_target: float = 2.0,
            harmony_override: Optional[Sequence[dict]] = None):
    """악보 -> (Arrangement, LoadedScore, segments)."""
    if isinstance(path_or_score, score_loader.LoadedScore):
        ls = path_or_score
    elif isinstance(path_or_score, str):
        ls = score_loader.load(path_or_score, transpose=transpose)
    else:
        ls = score_loader.from_score(path_or_score, transpose=transpose)
    segs = list(harmony_override) if harmony_override else harmony.analyze_segments(
        ls, seg_target=seg_target)
    arr = build(segs, ls, style=style, level=level, curve=curve, bpm=bpm,
                count_in=count_in)
    return arr, ls, segs


def run(src: str, out: str, style: str = 'strings', curve: str = 'build',
        bpm: float = 120.0, level: str = 'rich') -> dict:
    """프로토타입 `arranger2.run` 호환 — 반주 MIDI 를 써 내고 요약을 돌려준다."""
    arr, _ls, _segs = arrange(src, style=style, level=level, curve=curve, bpm=bpm)
    arr.save(out)
    return arr.info()
