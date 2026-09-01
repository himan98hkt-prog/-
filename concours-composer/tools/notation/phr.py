"""프레이즈 응답을 쓰기 전에 스팬·교차·음역을 먼저 본다."""
from __future__ import annotations

from _paths import ROOT, RUNS
import json
from nota import bars
from app.analysis.pitch import pitch_to_midi



def check(ms: list[dict], span: int, lo: int, hi: int) -> list[str]:
    bad = []
    for m in ms:
        n = m["number"]
        rmin, lmax = 999, -999
        for hand, key in (("rh", "rh"), ("lh", "lh")):
            for v in m.get(key, []):
                for e in v["events"]:
                    ps = [pitch_to_midi(p) for p in e["pitches"]]
                    if not ps:
                        continue
                    if max(ps) - min(ps) > span:
                        bad.append(f"m{n} {hand} 스팬 {max(ps)-min(ps)}>{span}: {e['pitches']}")
                    for p in ps:
                        if not lo <= p <= hi:
                            bad.append(f"m{n} {hand} 음역 밖 {p}")
                    if key == "rh":
                        rmin = min(rmin, *ps)
                    else:
                        lmax = max(lmax, *ps)
        if rmin < 999 and lmax > -999 and lmax > rmin:
            bad.append(f"m{n} 손 교차: 왼손 최고 {lmax} > 오른손 최저 {rmin}")
    return bad


def write(gid: str, name: str, spec: list, beats: float, start: int,
          *, span: int, lo: int = 36, hi: int = 96) -> None:
    ms = bars(spec, beats, start)
    bad = check(ms, span, lo, hi)
    for b in bad:
        print("  !", b)
    if bad:
        raise SystemExit("고칠 것이 남았다")
    p = RUNS / gid / f"{name}_response.json"
    p.write_text(json.dumps({"measures": ms}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  wrote", p.name)
