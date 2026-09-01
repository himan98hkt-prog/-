"""Claude 작곡 엔진 — 실제 품질을 만드는 곳.

프롬프트는 `generation/prompts/*.md` 에서만 읽는다(CLAUDE.md 코드 규칙).
모든 호출은 Structured Outputs 이므로 모델은 스키마 밖으로 나갈 수 없다.
작곡가(realize)와 비평가(critique)는 프롬프트도 호출도 분리한다(절대 규칙 10).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.musicality import describe_texture
from app.config import Settings, get_settings
from app.generation.client import ClaudeClient, CostLedger
from app.generation.context import ComposerContext, estimate_measures
from app.generation.engines.base import PhraseRequest
from app.schemas.music import CompositionPlan, Measure, MotifCandidate, PhraseRealization
from app.schemas.quality import CriticReport

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"프롬프트가 없다: {path}")
    return path.read_text(encoding="utf-8")


def prompt_version(name: str) -> str:
    """프롬프트 첫 줄의 version 태그. 골든 회귀 리포트에 남긴다."""
    head = load_prompt(name).splitlines()[0]
    if "version:" not in head:
        return "untagged"
    # 예: "<!-- version: motif-v3.1 · Stage 1 · COMPOSER_MODEL -->"
    tag = head.split("version:", 1)[1].split("·", 1)[0]
    return tag.replace("-->", "").strip()


class MotifBatch(BaseModel):
    """Stage 1 출력 래퍼 — 최상위가 배열이면 스키마로 고정하기 어렵다."""

    model_config = ConfigDict(extra="forbid")
    candidates: list[MotifCandidate] = Field(min_length=1, max_length=5)


def _j(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)


def fixed_context(ctx: ComposerContext) -> str:
    """곡 하나를 만드는 동안 **한 글자도 바뀌지 않는** 부분.

    학생 프로필·하드 제약·콩쿨 규정·코퍼스 요약·학원 실전 데이터가 여기 들어간다.
    프레이즈마다 이것을 다시 과금할 이유가 없으므로 프롬프트 캐시 접두사로 보낸다.
    바뀌는 것(이번 프레이즈의 plan·직전 마디)은 user 메시지로 가야 캐시가 깨지지 않는다.
    """
    payload = ctx.prompt_payload()
    return _j({
        "student": payload["student"],
        "constraints": payload["constraints"],
        "competition": payload["competition"],
        "style_context": payload["style_context"],
        "academy_data": payload["academy_data"],
        "request": payload["request"],
    })


class ClaudeComposerEngine:
    name = "claude"

    def __init__(self, settings: Settings | None = None, ledger: CostLedger | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = ClaudeClient(self.settings, ledger)

    @property
    def ledger(self) -> CostLedger:
        return self.client.ledger

    def versions(self) -> dict[str, str]:
        return {n: prompt_version(n) for n in ("motif", "plan", "realize_phrase", "critic")}

    # ── Stage 1 ──────────────────────────────────────────────────────────
    def motifs(self, ctx: ComposerContext, n: int, feedback: str = "") -> list[MotifCandidate]:
        payload: dict[str, object] = {"n": n}
        if feedback:
            payload["director_feedback"] = feedback
        batch = self.client.parse(
            stage="motif",
            system=load_prompt("motif"),
            user=_j(payload),
            output_model=MotifBatch,
            model=self.settings.composer_model,
            fixed_context=fixed_context(ctx),
        )
        out: list[MotifCandidate] = []
        for i, c in enumerate(batch.candidates):
            out.append(c.model_copy(update={"id": c.id or f"motif-{i + 1}"}))
        return out

    # ── Stage 2 ──────────────────────────────────────────────────────────
    def plan(self, ctx: ComposerContext, motif: MotifCandidate) -> CompositionPlan:
        payload = {
            "locked_motif": motif.model_dump(),
            "suggested_total_measures": estimate_measures(ctx.request, motif.meter, motif.tempo),
        }
        return self.client.parse(
            stage="plan",
            system=load_prompt("plan"),
            user=_j(payload),
            output_model=CompositionPlan,
            model=self.settings.composer_model,
            fixed_context=fixed_context(ctx),
        )

    # ── Stage 3 ──────────────────────────────────────────────────────────
    def realize_phrase(self, ctx: ComposerContext, req: PhraseRequest) -> PhraseRealization:
        lo, hi = req.measure_range
        payload = {
            "motif": req.motif.model_dump(),
            "phrase_plan": req.phrase.model_dump(),
            "measure_range": [lo, hi],
            "harmony": [{"measure": m, "roman": r} for m, r in req.harmony_for_range()],
            "next_harmony": req.next_harmony(),
            "key": req.plan.key,
            "meter": req.plan.meter,
            "tempo": req.plan.tempo,
            "previous_measures": [m.model_dump() for m in req.previous_measures],
        }
        # 구간 재생성이면 지시가 붙는다 — 프롬프트도 바뀐다.
        name = "regenerate_region" if req.instruction else "realize_phrase"
        if req.instruction:
            payload["instruction"] = req.instruction
            payload["region"] = [lo, hi]
        return self.client.parse(
            stage=f"realize[{lo}-{hi}]",
            system=load_prompt(name),
            user=_j(payload),
            output_model=PhraseRealization,
            model=self.settings.composer_model,
            fixed_context=fixed_context(ctx),
        )

    # ── Stage 5 ──────────────────────────────────────────────────────────
    def critique(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, musicality: dict, warnings: list[str] | None = None,
    ) -> CriticReport:
        payload = {
            "score_text": score_to_text(measures, plan),
            "plan": plan.model_dump(),
            "locked_motif": motif.model_dump(),
            "rule_based_musicality": musicality,
            "measured_texture": describe_texture(measures, plan),
            "validator_warnings": warnings or [],
            "total_measures": len(measures),
        }
        return self.client.parse(
            stage="critic",
            system=load_prompt("critic"),
            user=_j(payload),
            output_model=CriticReport,
            model=self.settings.composer_model,
            fixed_context=fixed_context(ctx),
        )


def score_to_text(measures: list[Measure], plan: CompositionPlan | None = None) -> str:
    """악보를 비평가가 읽을 텍스트로. MusicXML 을 그대로 주면 토큰만 먹고 읽히지 않는다."""
    harmony = {h.measure: h.roman for h in plan.harmony} if plan else {}
    lines: list[str] = []
    for m in sorted(measures, key=lambda x: x.number):
        parts = [f"m{m.number}"]
        if m.number in harmony:
            parts.append(f"[{harmony[m.number]}]")
        if m.dynamics:
            parts.append(f"({m.dynamics})")
        for label, voices in (("RH", m.rh), ("LH", m.lh)):
            chunks: list[str] = []
            for v in voices:
                for e in v.events:
                    head = "r" if e.is_rest else "+".join(e.pitches)
                    art = f".{e.artic}" if e.artic != "none" else ""
                    chunks.append(f"{head}/{e.dur:g}{art}")
            if chunks:
                parts.append(f"{label} " + " ".join(chunks))
        if m.pedal:
            parts.append("ped")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
