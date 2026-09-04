"""파이프라인을 돌리기 전에 지표를 미리 본다 — 응답 파일에서 바로 조립한다."""
from __future__ import annotations

from _paths import ROOT, RUNS
import json
import sys
from app.analysis.difficulty import difficulty_score
from app.analysis.musicality import evaluate
from app.schemas.music import CompositionPlan, Measure, MotifCandidate



def load(gid: str):
    d = RUNS / gid
    plan = CompositionPlan.model_validate(json.loads((d / "plan_response.json").read_text()))
    cands = json.loads((d / "motif_response.json").read_text())["candidates"]
    motif = MotifCandidate.model_validate(cands[0])
    by: dict[int, Measure] = {}
    for f in sorted(d.glob("phrase_*_response.json")):
        fix = f.name.endswith("_fix_response.json")
        for x in json.loads(f.read_text())["measures"]:
            m = Measure.model_validate(x)
            if fix or m.number not in by:
                by[m.number] = m
    return plan, motif, [by[n] for n in sorted(by)]


def report(gid: str, span: int) -> None:
    plan, motif, ms = load(gid)
    missing = set(range(1, plan.total_measures + 1)) - {m.number for m in ms}
    if missing:
        print("빠진 마디", sorted(missing)[:10])
    r = evaluate(ms, motif=motif, plan=plan, max_span_semitones=span)
    print(f"[{gid}] musicality {r.score_10}  unmet {[k for k,v in r.metrics.items() if not v.met]}")
    for k, v in r.metrics.items():
        flag = " " if v.met else "!"
        print(f" {flag}{k:22s} {v.value:<7} {v.detail[:120]}")
    d = difficulty_score(ms, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
    print(f" 난이도 {d.score} (목표 {plan.difficulty_target})")
    print("  " + "  ".join(f"{k}={v:.2f}" for k, v in sorted(d.features.items(), key=lambda kv: kv[1])))


if __name__ == "__main__":
    report(sys.argv[1], int(sys.argv[2]))
