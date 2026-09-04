"""짧은 표기 → ScoreEvent JSON. 마디 길이를 강제 검사한다.

토큰:  C4/0.5   C4+E4/1.0   r/0.5
접미:  .(스타카토) >(액센트) =(테누토) ^(마르카토)
       ((슬러 시작) )(슬러 끝)  ~(타이 시작) _(타이 끝) +(타이 계속)
"""
from __future__ import annotations

from _paths import ROOT, RUNS
import json
import sys
from pathlib import Path
from fractions import Fraction

ART = {".": "staccato", ">": "accent", "=": "tenuto", "^": "marcato"}
SLUR = {"(": "start", ")": "stop"}
TIE = {"~": "start", "_": "stop", "&": "continue"}
OK_DUR = {0.125, 0.1875, 0.25, 0.375, 0.4375, 0.5, 0.75, 0.875, 1.0,
          1.5, 1.75, 2.0, 3.0, 3.5, 4.0, 6.0, 7.0, 8.0}


def ev(tok: str) -> dict:
    art = slur = tie = None
    while tok and tok[-1] in ".>=^()~_&":
        c = tok[-1]; tok = tok[:-1]
        if c in ART: art = ART[c]
        elif c in SLUR: slur = SLUR[c]
        else: tie = TIE[c]
    head, _, d = tok.rpartition("/")
    dur = float(Fraction(d))
    if dur not in OK_DUR:
        raise SystemExit(f"기보할 수 없는 길이 {dur} ({tok})")
    o: dict = {"dur": dur, "pitches": [] if head == "r" else head.split("+")}
    if art: o["artic"] = art
    if slur: o["slur"] = slur
    if tie: o["tie"] = tie
    return o


def voice(s: str, want: float, where: str) -> list[dict]:
    evs = [ev(t) for t in s.split()]
    tot = round(sum(e["dur"] for e in evs), 6)
    if abs(tot - want) > 1e-6:
        raise SystemExit(f"{where}: 길이 {tot} != {want}  ({s})")
    return evs


def bars(spec: list, beats: float, start: int = 1) -> list[dict]:
    """spec: [(rh, lh) | (rh, lh, opts)] — opts 는 dynamics/pedal/text."""
    out = []
    for i, row in enumerate(spec):
        rh, lh = row[0], row[1]
        opts = row[2] if len(row) > 2 else {}
        n = start + i
        m: dict = {"number": n}
        if rh is not None:
            m["rh"] = [{"voice": 1, "events": voice(rh, beats, f"m{n} rh")}]
        if lh is not None:
            m["lh"] = [{"voice": 1, "events": voice(lh, beats, f"m{n} lh")}]
        m.update(opts)
        out.append(m)
    return out


def write(path: str, obj) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("wrote", path, file=sys.stderr)
