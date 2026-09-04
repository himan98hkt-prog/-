"""설계도를 짧게 쓰고, 쓰기 전에 규칙 검사·다양성 검사를 돌려 본다."""
from __future__ import annotations

from _paths import ROOT, RUNS
import json


from app.generation.diversity import FormFingerprint, compare
from app.generation.plan_rules import check_plan
from app.schemas.music import CompositionPlan
from golden_specs import GOLDEN, make_context



def previous(exclude: str):
    out = []
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir() or d.name == exclude:
            continue
        f = d / "plan.json"
        if f.exists():
            out.append((d.name, CompositionPlan.model_validate(json.loads(f.read_text()))))
    return out


def sections(spec: list[tuple[str, list[tuple[int, str, str, str, str]]]]):
    """[(라벨, [(마디수, 처리, rh, lh, dyn), ...])] → form 리스트 + 총 마디."""
    form, n = [], 1
    for label, phrases in spec:
        lo = n
        ps = []
        for length, tr, rh, lh, dyn in phrases:
            ps.append({"measures": [n, n + length - 1], "motif_treatment": tr,
                       "texture_rh": rh, "texture_lh": lh, "dynamic": dyn})
            n += length
        form.append({"label": label, "measures": [lo, n - 1], "phrases": ps})
    return form, n - 1


def harmony(romans: list[str], basses: dict[int, str] | None = None):
    basses = basses or {}
    out = []
    for i, r in enumerate(romans, 1):
        h = {"measure": i, "roman": r}
        if i in basses:
            h["bass_note"] = basses[i]
        out.append(h)
    return out


def finish(gid: str, plan: dict, *, write: bool = True):
    spec = next(s for s in GOLDEN if s["id"] == gid)
    ctx = make_context(spec)
    p = CompositionPlan.model_validate(plan)
    rep = check_plan(p, ctx.student, time_limit_sec=ctx.hard.time_limit_sec,
                     previous_plans=previous(gid))
    for i in rep.issues:
        print(f"  [{i.severity}] {i.rule}: {i.message}")
    me = FormFingerprint.of(p)
    for oid, other in previous(gid):
        sim, sh = compare(me, FormFingerprint.of(other))
        if sim >= 0.4:
            print(f"  ~ {oid}: {sim:.2f} {sh}")
    print(f"  총 {p.total_measures}마디 · {p.duration_est}초 · 통과={rep.passed}")
    if write and rep.passed:
        path = RUNS / gid / "plan_response.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print("  wrote", path)
    return rep.passed
