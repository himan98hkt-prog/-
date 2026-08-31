"""§6.13 결과 학습 — 콩쿨 결과와 곡 특성의 상관을 요약해 Plan 프롬프트에 주입한다.

'대상을 받았다' 는 사실만으로는 다음 곡에 쓸 수 없다. 상위 결과 곡들이 **공통으로**
가진 Plan 특성(조성·템포·형식·쇼케이스 유형·난이도)을 뽑아 문장으로 만든다.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

RANK = {"grand": 5, "first": 4, "second": 3, "third": 2, "honorable": 1, "none": 0}
TOP = {"grand", "first", "second"}


def summarize_results(results: list[dict[str, Any]], compositions: dict[str, Any]) -> str:
    if not results:
        return ""

    top = [r for r in results if r.get("result") in TOP]
    if not top:
        return f"기록 {len(results)}건 — 아직 상위 입상 사례가 없다."

    keys: Counter[str] = Counter()
    forms: Counter[str] = Counter()
    treatments: Counter[str] = Counter()
    showcases: Counter[str] = Counter()
    tempos: list[int] = []
    difficulties: list[float] = []

    for r in top:
        res = compositions.get(r["composition_id"])
        if res is None:
            continue
        plan = res.plan
        keys[plan.key] += 1
        forms["-".join(s.label for s in plan.form)] += 1
        for p in plan.phrases():
            treatments[p.motif_treatment] += 1
        for sc in plan.showcase_measures:
            showcases[sc.strength_used] += 1
        tempos.append(plan.tempo)
        difficulties.append(res.difficulty)

    if not tempos:
        return f"상위 입상 {len(top)}건 — 곡 데이터가 남아 있지 않다."

    parts = [f"학원 실전 데이터: 상위 입상 {len(top)}건 / 전체 {len(results)}건."]
    parts.append(f"자주 통한 조성 {', '.join(k for k, _ in keys.most_common(3))}.")
    parts.append(f"형식 {', '.join(f for f, _ in forms.most_common(2))}.")
    parts.append(
        f"템포 {min(tempos)}~{max(tempos)}bpm, 난이도 "
        f"{min(difficulties):.1f}~{max(difficulties):.1f}."
    )
    if treatments:
        parts.append(
            "자주 쓰인 모티브 처리 " + ", ".join(t for t, _ in treatments.most_common(3)) + "."
        )
    if showcases:
        parts.append("드러낸 강점 " + ", ".join(s for s, _ in showcases.most_common(3)) + ".")
    return " ".join(parts)
