#!/usr/bin/env python3
"""세션 엔진으로 골든 요청을 작곡한다 (GOLDEN_ENGINE=session).

API 를 호출하지 않는다. 각 단계의 프롬프트를 `runs/golden/<요청id>/` 에 내놓고
같은 폴더의 `<단계>_response.json` 을 기다린다. 이 세션의 Claude 가 그 파일을 쓴다.

    python scripts/session_golden.py --ids g01 g02 g03 g04 g05 --measures 24
    python scripts/session_golden.py --ids g01 --no-wait      # 대기하지 않고 다음 프롬프트만 내놓는다

곡마다 남기는 것:
    score.musicxml · score.mid · validation.json · quality.json · plan.json
    measures.json  · cost.json  · summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "tests" / "golden"))

from app.analysis.difficulty import difficulty_score  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.export.midi import measures_to_midi  # noqa: E402
from app.generation.client import CostLedger  # noqa: E402
from app.generation.engines.session import AwaitingResponse, SessionComposerEngine  # noqa: E402
from app.generation.pipeline import CompositionPipeline  # noqa: E402
from app.guide.writer import rule_based_guide  # noqa: E402
from app.ingest.corpus import Corpus  # noqa: E402
from app.judge.panel import run_panel_rules  # noqa: E402
from app.schemas.music import CompositionPlan, Measure  # noqa: E402
from golden_specs import GOLDEN, make_context  # noqa: E402

RUNS = ROOT / "runs" / "golden"


def _dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _already_made(exclude: str) -> tuple[list[tuple[str, CompositionPlan]], Corpus]:
    """이미 만든 곡들의 설계도와, 그 곡들이 들어간 표절 코퍼스.

    이게 없으면 새 곡이 앞서 만든 곡과 형식이 같아도, 선율이 겹쳐도 아무도 모른다.
    골든은 품질을 재는 유일한 자리인데 지금까지 이 두 관문이 비어 있었다.
    """
    plans: list[tuple[str, CompositionPlan]] = []
    corpus = Corpus()
    for d in sorted(RUNS.iterdir()) if RUNS.exists() else []:
        if not d.is_dir() or d.name == exclude:
            continue
        pf, mf = d / "plan.json", d / "measures.json"
        if not (pf.exists() and mf.exists()):
            continue
        plan = CompositionPlan.model_validate(json.loads(pf.read_text(encoding="utf-8")))
        plans.append((d.name, plan))
        corpus.register_generated(
            [Measure.model_validate(x) for x in json.loads(mf.read_text(encoding="utf-8"))],
            score_id=d.name, title=(plan.title_candidates or [d.name])[0],
            key=plan.key, meter=plan.meter, tempo=plan.tempo,
        )
    return plans, corpus


def run_one(spec: dict, *, measures_override: int | None, wait: bool) -> dict:
    """요청 하나를 끝까지. 응답 파일이 없으면 AwaitingResponse 로 멈춘다."""
    if measures_override:
        spec = {**spec, "measures_override": measures_override}
    ctx = make_context(spec)
    if measures_override:
        ctx.request.total_measures = measures_override

    run_dir = RUNS / spec["id"]
    ledger = CostLedger(
        limit_usd=get_settings().max_cost_per_composition,
        composition_id=spec["id"],
        engine="session",
    )
    engine = SessionComposerEngine(run_dir, ledger=ledger, wait=wait)
    pipe = CompositionPipeline(
        engine, progress=lambda st, _p, m: print(f"    [{st:9s}] {m}", flush=True)
    )

    _dump(run_dir / "request.json", {
        "spec": spec,
        "constraints": ctx.hard.as_dict(),
        "student": ctx.prompt_payload()["student"],
        "competition": ctx.prompt_payload()["competition"],
    })

    motifs = pipe.motifs(ctx, 4)
    if not motifs:
        raise RuntimeError(f"{spec['id']}: 학생 제약을 지키는 모티브 후보가 없다")
    _dump(run_dir / "motifs.json", [m.model_dump() for m in motifs])

    # 원장 선택 파일이 있으면 그것을, 없으면 첫 후보를 쓴다.
    choice_path = run_dir / "motif_choice.json"
    chosen_id = motifs[0].id
    if choice_path.exists():
        chosen_id = json.loads(choice_path.read_text(encoding="utf-8"))["motif_id"]
    motif = next((m for m in motifs if m.id == chosen_id), motifs[0])

    previous, made_corpus = _already_made(spec["id"])
    plan, plan_report = pipe.plan(ctx, motif, previous_plans=previous)
    _dump(run_dir / "plan.json", plan.model_dump())
    _dump(run_dir / "plan_check.json", {
        "passed": plan_report.passed,
        "issues": [asdict(i) for i in plan_report.issues],
    })
    if not plan_report.passed:
        raise RuntimeError(
            f"{spec['id']}: Plan 규칙 검사 실패 — "
            + "; ".join(i.message for i in plan_report.hard_failures)
        )

    res = pipe.compose(ctx, motif, plan, corpus_ngrams=made_corpus.ngram_index() or None)

    (run_dir / "score.musicxml").write_text(res.musicxml, encoding="utf-8")
    (run_dir / "score.mid").write_bytes(
        measures_to_midi(res.measures, plan.tempo, plan.meter)
    )
    (run_dir / "motif_preview.mid").write_bytes(
        measures_to_midi(list(motif.measures), motif.tempo, motif.meter)
    )
    _dump(run_dir / "measures.json", [m.model_dump() for m in res.measures])
    _dump(run_dir / "validation.json", {
        "passed": res.validation.passed,
        "summary": res.validation.summary(),
        "issues": [asdict(i) for i in res.validation.issues],
    })
    _dump(run_dir / "quality.json", res.quality.model_dump())

    # 모의 심사(§6.13)와 연주법 해설(§6.6)은 품질 층인데 지금까지 골든에서 한 번도
    # 돌지 않았다. 규칙 기반 대역을 돌려 산출물로 남긴다 — 모델이 쓰는 판은 별개다.
    panel = run_panel_rules(ctx, res.measures, plan, motif)
    _dump(run_dir / "judge.json", panel.model_dump())
    guide = rule_based_guide(ctx, res.measures, plan)
    _dump(run_dir / "guide.json", guide.model_dump())
    ledger.write(run_dir / "cost.json", model=get_settings().composer_model)

    diff = difficulty_score(res.measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
    critic_scores = (res.quality.critic or {}).get("scores", {})
    row = {
        "id": spec["id"],
        "title": (plan.title_candidates or ["무제"])[0],
        "motif": f"{motif.id} · {motif.character_label}",
        "key": plan.key,
        "meter": plan.meter,
        "tempo": plan.tempo,
        "measures": len(res.measures),
        "planned_measures": plan.total_measures,
        "duration_sec": round(plan.duration_est, 1),
        "time_limit_sec": ctx.hard.time_limit_sec,
        "validation_passed": res.validation.passed,
        "hard_failures": [i.rule for i in res.validation.hard_failures],
        "warnings": len(res.validation.warnings),
        "parallels": sum(1 for i in res.validation.warnings if i.rule == "parallels"),
        "musicality": res.quality.musicality["score_10"],
        "unmet": res.quality.musicality["unmet"],
        "critic_total": round(sum(critic_scores.values()) / len(critic_scores), 2)
        if critic_scores else None,
        "combined": res.quality.combined_score,
        "quality_passed": res.quality.passed,
        "revision_rounds": res.revision_rounds,
        "difficulty": diff.score,
        "difficulty_target": spec["difficulty"],
        "difficulty_division": diff.division_hint(),
        "judge_average": panel.average,
        "judge_consensus_fixes": panel.consensus_fixes(),
        "guide_sections": len(guide.sections),
        "advisory": [n for n in res.quality.notes if not n.startswith("프레이즈")],
        "prompts": engine.stats.prompts_written,
        "responses": engine.stats.responses_read,
        "projection": ledger.projected_cost(get_settings().composer_model),
    }
    _dump(run_dir / "summary.json", row)
    return row


def write_summary_table(rows: list[dict]) -> Path:
    path = RUNS / "SUMMARY.md"
    lines = [
        "# 세션 작곡 결과 요약",
        "",
        f"- 생성 시각: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "- 엔진: `session` — 이 Claude Code 세션이 작곡가·비평가를 맡았다 (API 미호출)",
        "- 검증기·음악성 지표·표절 검사는 코드가 그대로 실행했다",
        "",
        "| id | 제목 | 조성/박자/템포 | 마디 | 연주시간 | 검증 | 병행 |"
        " musicality | 비평 | 심사 | 종합 | 난이도(목표) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        verdict = "통과" if r["validation_passed"] else "실패 " + ",".join(r["hard_failures"])
        limit = f" / {r['time_limit_sec']}초" if r["time_limit_sec"] else ""
        lines.append(
            f"| {r['id']} | {r['title']} | {r['key']} {r['meter']} ♩={r['tempo']} | "
            f"{r['measures']} | {r['duration_sec']}초{limit} | {verdict} | {r['parallels']} | "
            f"{r['musicality']} | {r['critic_total']} | {r.get('judge_average', '-')} | "
            f"{r['combined']} | {r['difficulty']}({r['difficulty_target']}) |"
        )

    prev = RUNS.parent / "golden-v1"
    if prev.exists():
        lines += [
            "", "## 이전 판과 비교", "",
            "`runs/golden-v1/` 에 개선 전 다섯 곡이 그대로 있다. 길이 확대·프레이즈 길이 가변화·",
            "표현 다양성 지표를 반영하기 전 결과다.", "",
            "| id | 마디 (전→후) | 연주시간 (전→후) | 제한 시간 사용률 (전→후) |",
            "|---|---|---|---|",
        ]
        for r in rows:
            old_path = prev / r["id"] / "summary.json"
            if not old_path.exists():
                continue
            o = json.loads(old_path.read_text(encoding="utf-8"))
            limit = r["time_limit_sec"] or 1
            lines.append(
                f"| {r['id']} | {o['measures']} → {r['measures']} | "
                f"{o['duration_sec']}초 → {r['duration_sec']}초 | "
                f"{o['duration_sec'] / limit:.0%} → {r['duration_sec'] / limit:.0%} |"
            )
        lines += [
            "",
            "> 음악성 점수는 지표 자체가 바뀌었으므로(표현 다양성 추가 + 가중치 재배분)",
            "> 두 판을 직접 비교하지 않는다. 같은 잣대로 비교하려면 개선 후 코드로",
            "> 이전 판을 다시 채점해야 한다.",
        ]

    lines += ["", "## 미달 지표", ""]
    for r in rows:
        lines.append(f"- **{r['id']}** {r['title']}: {', '.join(r['unmet']) or '없음'}")

    advisory_rows = [(r["id"], r.get("advisory") or []) for r in rows]
    if any(a for _, a in advisory_rows):
        lines += ["", "## 파이프라인이 실행하지 못하고 넘긴 지적", "",
                  "프레이즈 재생성으로 옮길 수 없는 지적(곡 전체를 가리키는 말, 재료 선택)은",
                  "코드가 고치지 않고 원장에게 넘긴다.", ""]
        for gid, adv in advisory_rows:
            if adv:
                lines.append(f"- **{gid}**")
                lines += [f"  - {a}" for a in adv]

    lines += ["", "## API 전환 시 예상 비용 (토큰 실측 기반)", "",
              "| id | 호출 | 입력 토큰 | 출력 토큰 | 캐시 없이 | 캐시 적용 |", "|---|---|---|---|---|---|"]
    total_no, total_yes = 0.0, 0.0
    for r in rows:
        p = r["projection"]
        total_no += p["cost_usd_no_cache"]
        total_yes += p["cost_usd_with_cache"]
        lines.append(
            f"| {r['id']} | {p['calls']} | {p['input_tokens']:,} | {p['output_tokens']:,} | "
            f"${p['cost_usd_no_cache']} | ${p['cost_usd_with_cache']} |"
        )
    lines.append(
        f"| **합계** | | | | **${round(total_no, 4)}** | **${round(total_yes, 4)}** |"
    )
    lines += [
        "",
        f"곡당 평균: 캐시 없이 ${round(total_no / max(1, len(rows)), 4)} · "
        f"캐시 적용 ${round(total_yes / max(1, len(rows)), 4)}",
        "",
        "> 토큰은 문자 수 기반 근사(1토큰 ≈ 2.2자)다. 실제 API 전환 시",
        "> `messages.count_tokens` 로 재측정하면 정확해진다.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", default=["g01", "g02", "g03", "g04", "g05"])
    ap.add_argument("--measures", type=int, default=None,
                    help="총 마디 수 고정(세션 작곡 분량 조절)")
    ap.add_argument("--no-wait", action="store_true",
                    help="응답 파일이 없으면 기다리지 않고 멈춘다")
    args = ap.parse_args()

    specs = {g["id"]: g for g in GOLDEN}
    unknown = [i for i in args.ids if i not in specs]
    if unknown:
        print(f"알 수 없는 요청 id: {unknown}", file=sys.stderr)
        return 2

    RUNS.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    pending: list[str] = []

    for rid in args.ids:
        print(f"\n=== {rid} ===", flush=True)
        try:
            rows.append(run_one(specs[rid], measures_override=args.measures, wait=not args.no_wait))
            print(f"    완료: {rows[-1]['measures']}마디 · 종합 {rows[-1]['combined']}")
        except AwaitingResponse as e:
            print(f"    대기: {e.stage}")
            print(f"      프롬프트 {e.prompt_path.relative_to(ROOT)}")
            print(f"      응답을  {e.response_path.relative_to(ROOT)} 에 써라")
            pending.append(f"{rid}:{e.stage}")
        except Exception as e:  # 한 곡이 막혀도 나머지는 진행한다
            print(f"    실패: {type(e).__name__}: {e}")
            pending.append(f"{rid}:ERROR")

    if rows:
        path = write_summary_table(rows)
        print(f"\n요약표: {path.relative_to(ROOT)}")
    if pending:
        print(f"\n남은 작업 {len(pending)}건: {', '.join(pending)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
