"""병행 5·8도가 난 자리의 왼손 화음을 자리바꿈해 없앤다.

바깥 두 성부가 같은 방향으로 완전음정을 유지하는 것이 문제이므로, **두 번째 타건의
왼손 최저음**만 옮긴다(옥타브 위로, 안 되면 화음 안의 다른 음을 바닥으로). 오른손 선율과
화성은 한 음도 건드리지 않는다 — 반주의 자리바꿈은 작곡가가 실제로 쓰는 손질이다.
"""
from __future__ import annotations

from _paths import ROOT, RUNS
import json

from app.analysis.musicality import _roman_chord_tones
from app.analysis.pitch import midi_to_pitch, pitch_to_midi
from app.analysis.theory import is_minor
from app.schemas.music import CompositionPlan, Measure
from app.validate.validator import _outer_voice_points



def _pairs(ms: list[Measure]) -> list[tuple[int, float, int, float]]:
    """병행이 난 (앞 마디, 앞 위치, 뒷 마디, 뒷 위치)."""
    pts = _outer_voice_points(ms)
    out = []
    for (m1, o1, t1, b1), (m2, o2, t2, b2) in zip(pts, pts[1:]):
        i1, i2 = (t1 - b1) % 12, (t2 - b2) % 12
        if t1 != t2 and b1 != b2 and (t2 - t1) * (b2 - b1) > 0 and i1 == i2 and i1 in (0, 7):
            out.append((m1, o1, m2, o2))
    return out


def _event_at(m: Measure, off: float):
    for v in m.lh:
        t = 0.0
        for e in v.events:
            if abs(t - off) < 1e-6 and e.pitches:
                return e
            t += e.dur
    return None


def fix(ms: list[Measure], plan: CompositionPlan, *,
        lo: int = 36, span: int = 12, rounds: int = 8) -> int:
    """병행이 난 자리의 왼손 바닥음을 **다른 화음음**으로 바꾼다.

    옥타브로 옮기는 것만으로는 음정 종류(mod 12)가 그대로라 병행이 사라지지 않는다.
    화성이 허락하는 다른 구성음을 바닥에 놓아야 바깥 음정이 3·6도로 바뀐다.
    """
    by = {m.number: m for m in ms}
    try:
        tonic = pitch_to_midi(plan.key.split()[0] + "4") % 12
    except ValueError:
        tonic = 0
    minor = is_minor(plan.key)
    roman_of = {h.measure: h.roman for h in plan.harmony}
    fixed = 0
    for _ in range(rounds):
        bad = _pairs(ms)
        if not bad:
            break
        moved = False
        for _m1, _o1, m2, o2 in bad:
            m = by.get(m2)
            e = _event_at(m, o2) if m else None
            if m is None or e is None or not e.pitches:
                continue
            tones = _roman_chord_tones(roman_of.get(m2, ""), tonic, minor)
            if not tones:
                continue
            midis = sorted(pitch_to_midi(x) for x in e.pitches)
            rmin = min((pitch_to_midi(x) for v in m.rh for ev in v.events for x in ev.pitches),
                       default=127)
            top = max((pitch_to_midi(x) for v in m.rh for ev in v.events
                       for x in ev.pitches), default=None)
            upper = midis[1:]
            # 원래 바닥음에서 가까운 순으로 다른 화음음을 시도한다.
            for nb in sorted(range(lo, min(rmin, 96) + 1),
                             key=lambda x: (abs(x - midis[0]), x)):
                if nb % 12 not in tones or nb == midis[0]:
                    continue
                cand = sorted([nb, *upper])
                if max(cand) - min(cand) > span or max(cand) > rmin:
                    continue
                if top is not None and (top - nb) % 12 in (0, 7):
                    continue                       # 같은 완전음정이면 소용없다
                e.pitches = [midi_to_pitch(x) for x in cand]
                fixed += 1
                moved = True
                break
        if not moved:
            break
    return fixed


def write(gid: str, name: str, first: int, last: int, *, lo: int = 36, span: int = 12) -> None:
    """곡 **전체**에서 병행을 없앤 뒤, 요청받은 마디 범위만 잘라 쓴다.

    병행은 프레이즈 경계를 넘어 생기므로 구간만 보고 고칠 수 없다.
    """
    from score import load
    plan, _motif, ms = load(gid)
    n = fix(ms, plan, lo=lo, span=span)
    left = [(a, c) for a, _b, c, _d in _pairs(ms)]
    sub = [m for m in ms if first <= m.number <= last]
    p = RUNS / gid / f"{name}_response.json"
    p.write_text(json.dumps({"measures": [m.model_dump() for m in sub]},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {gid} {name}: 곡 전체 {n}곳 자리바꿈, 남은 병행 {len(left)}건 → {p.name}")
