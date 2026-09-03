"""§6.13 모의 심사 — 성향이 다른 심사위원 3인.

목적은 점수가 아니라 **약점을 미리 찾는 것**이다. 세 페르소나는 서로 다른 것을 본다.
`fix_in_score`(곡을 고칠 것)와 `fix_in_practice`(연습에서 보완할 것)를 분리하는 것이
이 기능의 핵심이다 — 원장은 전자를 작곡에, 후자를 레슨에 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from app.analysis import musicality as musicality_mod
from app.analysis.difficulty import difficulty_score
from app.config import Settings, get_settings
from app.generation.client import ClaudeClient, CostLedger
from app.generation.context import ComposerContext
from app.generation.engines.claude_engine import score_to_text
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import JudgePanel, JudgeVerdict

PROMPT = Path(__file__).resolve().parent / "prompts" / "judge.md"
PERSONAS = ("technique", "musicality", "structure")
PERSONA_KO = {"technique": "테크닉 중시", "musicality": "음악성 중시", "structure": "구조·형식 중시"}


def run_panel_claude(
    ctx: ComposerContext,
    measures: list[Measure],
    plan: CompositionPlan,
    *,
    settings: Settings | None = None,
    ledger: CostLedger | None = None,
) -> JudgePanel:
    """페르소나마다 별도 호출. 한 번에 3인을 요청하면 세 목소리가 뭉개진다."""
    import json

    s = settings or get_settings()
    client = ClaudeClient(s, ledger)
    system = PROMPT.read_text(encoding="utf-8")

    verdicts: list[JudgeVerdict] = []
    # 셋 다 부르는 것이 기본이다. 아껴 쓰기 등급에서는 첫 한 사람만 부른다 —
    # 심사위원 한 사람도 악보 전체를 읽으므로, 인원이 곧 비용이다.
    for persona in PERSONAS[: max(1, s.judge_count)]:
        payload = {
            "assigned_persona": persona,
            "score_text": score_to_text(measures, plan),
            "plan": plan.model_dump(),
            "student": ctx.prompt_payload()["student"],
            "competition": ctx.prompt_payload()["competition"],
            "difficulty": difficulty_score(
                measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key
            ).score,
        }
        v = client.parse(
            stage=f"judge[{persona}]",
            system=system,
            user=json.dumps(payload, ensure_ascii=False, indent=1, default=str),
            output_model=JudgeVerdict,
            model=s.judge_model or s.composer_model,
        )
        verdicts.append(v.model_copy(update={"persona": persona}))
    return JudgePanel(verdicts=verdicts)


def run_panel_rules(
    ctx: ComposerContext,
    measures: list[Measure],
    plan: CompositionPlan,
    motif: MotifCandidate | None = None,
) -> JudgePanel:
    """규칙 기반 대역. API 키 없이 화면·테스트를 돌리기 위한 것이며,
    실제 심사 판단은 COMPOSER_MODEL 이 한다."""
    mus = musicality_mod.evaluate(
        measures, motif=motif, plan=plan, max_span_semitones=ctx.hard.max_span_semitones
    )
    diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
    target = ctx.hard.target_difficulty
    fit = max(0.0, 10.0 - abs(diff.score - target) * 2.5)

    def m(key: str) -> float:
        return mus.metrics[key].value if key in mus.metrics else 0.0

    total_measures = len(measures)
    verdicts = [
        JudgeVerdict(
            persona="technique",
            accuracy=round(2 + 8 * m("playability"), 1),
            expression=round(3 + 6 * m("dynamic_curve"), 1),
            structure=round(3 + 6 * m("texture_contrast"), 1),
            difficulty_fit=round(fit, 1),
            impression=round(3 + 6 * m("melodic_contour"), 1),
            comment=(
                f"난이도 {diff.score:.1f}({diff.division_hint()})로 목표 {target:.1f} 대비 "
                f"{'적절' if abs(diff.score - target) <= 1 else '어긋남'}. "
                f"{mus.metrics['playability'].detail}."
            ),
            fix_in_score=(
                [] if m("playability") >= 0.7
                else [f"1~{min(8, total_measures)}마디 도약 폭을 줄이고 손 이동을 순차로 메울 것"]
            ),
            fix_in_practice=["느린 템포에서 손 이동 구간만 분리 연습", "메트로놈으로 템포 유지 확인"],
        ),
        JudgeVerdict(
            persona="musicality",
            accuracy=round(4 + 5 * m("phrase_balance"), 1),
            expression=round(2 + 8 * m("dynamic_curve"), 1),
            structure=round(3 + 6 * m("phrase_balance"), 1),
            difficulty_fit=round(fit, 1),
            impression=round(2 + 8 * m("melodic_contour"), 1),
            comment=f"프레이즈 호흡 — {mus.metrics['phrase_balance'].detail}. "
                    f"다이내믹 — {mus.metrics['dynamic_curve'].detail}.",
            fix_in_score=(
                [] if m("dynamic_curve") >= 0.7
                else ["Plan 의 dynamics_curve 지점마다 다이내믹 표기를 실제 악보에 넣을 것"]
            ),
            fix_in_practice=["프레이즈 끝을 손목으로 놓아주는 연습", "노래하듯 선율만 따로 쳐보기"],
        ),
        JudgeVerdict(
            persona="structure",
            accuracy=round(4 + 5 * m("harmonic_consistency"), 1),
            expression=round(3 + 6 * m("texture_contrast"), 1),
            structure=round(1 + 9 * m("motif_consistency"), 1),
            difficulty_fit=round(fit, 1),
            impression=round(3 + 6 * m("repetition_balance"), 1),
            comment=f"모티브 통일성 — {mus.metrics['motif_consistency'].detail}. "
                    f"화성 — {mus.metrics['harmonic_consistency'].detail}.",
            fix_in_score=(
                [] if m("motif_consistency") >= 0.7
                else [f"{plan.form[-1].measures[0]}마디 이후에 모티브의 흔적이 남도록 재현부를 다시 쓸 것"]
            ),
            fix_in_practice=["섹션 경계를 의식하며 암보 구획 나누기"],
        ),
    ]
    return JudgePanel(verdicts=verdicts)
