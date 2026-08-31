"""골든 20건 회귀 (§7.8).

프롬프트나 파이프라인을 바꾸면 이 결과를 PR 에 첨부한다(CLAUDE.md 절대 규칙 11).
기본 실행은 오프라인 스텁 엔진 — 파이프라인 자체의 회귀를 잡는다.
실제 모델 품질은 `--live` 로 별도 측정한다(비용이 든다).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pytest
from app.generation.engines.stub import StubComposerEngine
from app.generation.pipeline import CompositionPipeline
from golden_specs import make_context

# 파이프라인이 보장하는 것 — 엔진과 무관하게 항상 성립해야 한다.
MIN_PHRASE_COMPLETION = 1.0          # Plan 이 설계한 마디는 전부 실현된다
MIN_VALIDATION_PASS_RATE = 0.95      # M3b Acceptance: 하드 검증 통과 ≥ 95%

# 엔진에 따라 달라지는 것 — 목표 난이도를 맞추는 능력은 '작곡가' 의 능력이다.
# 규칙 기반 스텁은 표현 폭이 대략 난이도 3~7 이라 양 끝을 놓친다(문서: docs/STATUS.md).
# 실제 COMPOSER_MODEL 은 ±1 을 지켜야 하므로 기준선을 나눠 둔다.
DIFFICULTY_BASELINE = {"stub": 0.55, "claude": 0.90}

_RESULTS: list[dict] = []


@pytest.fixture(scope="module")
def engine_name() -> str:
    return os.environ.get("GOLDEN_ENGINE", "stub")


def _pipeline(engine_name: str) -> CompositionPipeline:
    if engine_name == "claude":
        from app.generation.engines.claude_engine import ClaudeComposerEngine

        return CompositionPipeline(ClaudeComposerEngine(), progress=lambda *_: None)
    return CompositionPipeline(StubComposerEngine(), progress=lambda *_: None)


def test_golden_case(golden_spec, engine_name):
    ctx = make_context(golden_spec)
    pipe = _pipeline(engine_name)

    motifs = pipe.motifs(ctx, 4)
    assert motifs, f"{golden_spec['id']}: 쓸 만한 모티브 후보가 하나도 없다"

    res = pipe.compose(ctx, motifs[0])
    row = {
        "id": golden_spec["id"],
        "engine": res.engine,
        "measures": len(res.measures),
        "planned": res.plan.total_measures,
        "validation_passed": res.validation.passed,
        "hard_failures": [i.rule for i in res.validation.hard_failures],
        "warnings": len(res.validation.warnings),
        "musicality": res.quality.musicality["score_10"],
        "critic_total": res.quality.critic["scores"] and round(
            sum(res.quality.critic["scores"].values()) / len(res.quality.critic["scores"]), 2
        ),
        "combined": res.quality.combined_score,
        "quality_passed": res.quality.passed,
        "revision_rounds": res.revision_rounds,
        "difficulty": res.difficulty,
        "difficulty_target": golden_spec["difficulty"],
        "unmet": res.quality.musicality["unmet"],
        "cost": res.cost.get("total_usd", 0.0),
    }
    _RESULTS.append(row)

    assert len(res.measures) == res.plan.total_measures, (
        f"{golden_spec['id']}: Plan 은 {res.plan.total_measures}마디인데 "
        f"{len(res.measures)}마디만 실현됐다 — 프레이즈 실패: {res.phrase_failures}"
    )
    # 난이도 목표는 엔진의 능력이므로 집계에서 따로 본다. 그 밖의 하드 규칙은
    # 어떤 엔진이든 통과해야 한다 — 파이프라인이 보장하는 부분이기 때문이다.
    structural = [i for i in res.validation.hard_failures if i.rule != "difficulty"]
    assert not structural, f"{golden_spec['id']}: {[i.message for i in structural]}"


def test_golden_aggregate(golden_report_path, engine_name):
    """개별 케이스 뒤에 돌아 전체 지표를 집계한다."""
    if len(_RESULTS) < 20:
        pytest.skip(f"개별 케이스가 먼저 돌아야 한다 (현재 {len(_RESULTS)}건)")

    n = len(_RESULTS)
    pass_rate = sum(
        1 for r in _RESULTS if not [x for x in r["hard_failures"] if x != "difficulty"]
    ) / n
    completion = sum(1 for r in _RESULTS if r["measures"] == r["planned"]) / n
    avg_musicality = round(sum(r["musicality"] for r in _RESULTS) / n, 3)
    avg_combined = round(sum(r["combined"] for r in _RESULTS) / n, 3)
    quality_rate = sum(1 for r in _RESULTS if r["quality_passed"]) / n
    diff_ok = sum(1 for r in _RESULTS if abs(r["difficulty"] - r["difficulty_target"]) <= 1.0) / n

    summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine": engine_name,
        "cases": n,
        "validation_pass_rate": round(pass_rate, 3),
        "phrase_completion_rate": round(completion, 3),
        "avg_musicality_10": avg_musicality,
        "avg_combined": avg_combined,
        "quality_threshold_pass_rate": round(quality_rate, 3),
        "difficulty_within_1": round(diff_ok, 3),
        "difficulty_baseline": DIFFICULTY_BASELINE.get(engine_name, 0.55),
        "total_cost_usd": round(sum(r["cost"] for r in _RESULTS), 4),
    }

    if golden_report_path:
        _write_report(golden_report_path, summary, _RESULTS)

    print("\n골든 회귀 요약:", json.dumps(summary, ensure_ascii=False, indent=2))
    assert pass_rate >= MIN_VALIDATION_PASS_RATE, summary
    assert completion >= MIN_PHRASE_COMPLETION, summary

    baseline = DIFFICULTY_BASELINE.get(engine_name, 0.55)
    assert diff_ok >= baseline, (
        f"난이도 ±1 적중률 {diff_ok:.0%} < 기준선 {baseline:.0%} ({engine_name} 엔진). "
        "작곡가가 목표 난이도를 맞추지 못하고 있다."
    )


def _write_report(path, summary: dict, rows: list[dict]) -> None:
    from app.generation.engines.claude_engine import prompt_version

    path.parent.mkdir(parents=True, exist_ok=True)
    versions = {n: prompt_version(n) for n in ("motif", "plan", "realize_phrase", "critic")}
    lines = [
        "# 골든 회귀 리포트",
        "",
        f"- 생성 시각: {summary['generated_at']}",
        f"- 엔진: `{summary['engine']}`",
        "- 프롬프트 버전: " + ", ".join(f"`{k}`={v}" for k, v in versions.items()),
        "",
        "## 요약",
        "",
        "| 지표 | 값 |",
        "|---|---|",
        f"| 케이스 | {summary['cases']} |",
        f"| 하드 검증 통과율 | {summary['validation_pass_rate']:.0%} |",
        f"| 프레이즈 완성률 | {summary['phrase_completion_rate']:.0%} |",
        f"| 평균 musicality(10점) | {summary['avg_musicality_10']} |",
        f"| 평균 종합점수 | {summary['avg_combined']} |",
        f"| 품질 문턱 통과율 | {summary['quality_threshold_pass_rate']:.0%} |",
        f"| 난이도 ±1 적중률 | {summary['difficulty_within_1']:.0%} "
        f"(기준선 {summary['difficulty_baseline']:.0%}) |",
        f"| 총 API 비용 | ${summary['total_cost_usd']} |",
        "",
        "## 케이스별",
        "",
        "| id | 마디 | 검증 | musicality | 비평 | 종합 | 라운드 | 난이도(목표) | 미달 지표 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['measures']}/{r['planned']} | "
            f"{'통과' if r['validation_passed'] else '실패 ' + ','.join(r['hard_failures'])} | "
            f"{r['musicality']} | {r['critic_total']} | {r['combined']} | {r['revision_rounds']} | "
            f"{r['difficulty']}({r['difficulty_target']}) | {', '.join(r['unmet']) or '-'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
