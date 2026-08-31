"""§7.3 작곡 파이프라인 — Stage 0~5.

CLAUDE.md 절대 규칙 9: 모티브 잠금 → Plan → **프레이즈 단위** Realize → 비평 루프.
32마디를 한 호출로 만드는 경로는 존재하지 않는다(`PhraseTooLongError` 로 막는다).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.analysis import musicality as musicality_mod
from app.analysis.difficulty import difficulty_score
from app.config import Settings, get_settings
from app.generation.assemble import AssembleOptions, measures_to_musicxml
from app.generation.context import ComposerContext
from app.generation.engines.base import ComposerEngine, PhraseRequest
from app.generation.plan_rules import check_plan
from app.schemas.music import CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import CriticReport, QualityReport
from app.validate.validator import ValidationReport, validate_score

log = logging.getLogger(__name__)

# 한 번의 Realize 호출이 만들 수 있는 최대 마디 수. 프레이즈는 4마디가 기본이다.
MAX_PHRASE_MEASURES = 8

ProgressFn = Callable[[str, float, str], None]


class PhraseTooLongError(RuntimeError):
    """절대 규칙 9 위반 — 한 호출이 프레이즈보다 큰 범위를 만들려 했다."""


class PlanRejected(RuntimeError):
    pass


@dataclass
class CompositionResult:
    measures: list[Measure]
    plan: CompositionPlan
    motif: MotifCandidate
    musicxml: str
    validation: ValidationReport
    quality: QualityReport
    difficulty: float
    engine: str
    revision_rounds: int = 0
    phrase_failures: list[str] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)

    @property
    def savable(self) -> bool:
        """검증기를 통과해야만 저장한다(절대 규칙 2)."""
        return self.validation.passed

    @property
    def shown_as_draft(self) -> bool:
        """비평 문턱 미달이면 '초안(미통과)' 으로만 보인다(절대 규칙 10)."""
        return self.savable and not self.quality.passed


def _noop(stage: str, pct: float, msg: str) -> None:
    log.info("[%s %3.0f%%] %s", stage, pct * 100, msg)


class CompositionPipeline:
    def __init__(
        self,
        engine: ComposerEngine,
        settings: Settings | None = None,
        *,
        progress: ProgressFn | None = None,
    ) -> None:
        self.engine = engine
        self.settings = settings or get_settings()
        self.progress = progress or _noop

    # ── Stage 1 ──────────────────────────────────────────────────────────
    def motifs(self, ctx: ComposerContext, n: int = 4, feedback: str = "") -> list[MotifCandidate]:
        self.progress("motif", 0.0, f"모티브 후보 {n}개 생성")
        cands = self.engine.motifs(ctx, n, feedback)
        # 후보도 손 스팬·음역을 지켜야 한다 — 원장이 못 쓸 모티브를 보여주지 않는다.
        ok: list[MotifCandidate] = []
        for c in cands:
            rep = validate_score(
                list(c.measures), ctx.student, meter=c.meter, tempo=c.tempo, key_sig=c.key,
                max_accidental_ratio=ctx.hard.max_accidental_ratio,
            )
            hard = [i for i in rep.hard_failures if i.rule in ("hand_span", "range", "measure_length")]
            if hard:
                log.warning("모티브 %s 탈락: %s", c.id, hard[0].message)
                continue
            ok.append(c)
        self.progress("motif", 1.0, f"후보 {len(ok)}개 통과 / {len(cands)}개 생성")
        return ok

    # ── Stage 2 ──────────────────────────────────────────────────────────
    def plan(self, ctx: ComposerContext, motif: MotifCandidate) -> tuple[CompositionPlan, ValidationReport]:
        if not motif.selected:
            motif = motif.model_copy(update={"selected": True})   # motif_locked
        self.progress("plan", 0.0, "설계도 생성")
        plan = self.engine.plan(ctx, motif)
        report = check_plan(plan, ctx.student, time_limit_sec=ctx.hard.time_limit_sec)
        self.progress("plan", 1.0, f"Plan 규칙 검사: {report.summary()}")
        return plan, report

    # ── Stage 3~4 ────────────────────────────────────────────────────────
    def realize(
        self, ctx: ComposerContext, plan: CompositionPlan, motif: MotifCandidate
    ) -> tuple[list[Measure], list[str]]:
        phrases = plan.phrases()
        produced: dict[int, Measure] = {}
        failures: list[str] = []

        for i, p in enumerate(phrases):
            lo, hi = p.measures
            if hi - lo + 1 > MAX_PHRASE_MEASURES:
                raise PhraseTooLongError(
                    f"프레이즈 {i}({lo}-{hi})가 {MAX_PHRASE_MEASURES}마디를 넘는다. "
                    "한 호출로 곡 전체를 만드는 것은 금지다(CLAUDE.md 절대 규칙 9)."
                )
            prev = [produced[n] for n in sorted(produced) if n < lo][-8:]
            req = PhraseRequest(motif=motif, plan=plan, phrase_index=i, previous_measures=prev)

            realized: list[Measure] | None = None
            last_reason = ""
            for attempt in range(3):    # 즉시 검증 → 실패 시 재시도 2회(§7.3 Stage 3)
                if last_reason:
                    # 같은 요청을 그대로 다시 보내면 같은 실패가 돌아온다.
                    # 실패 사유를 지시로 넘겨 엔진이 고칠 수 있게 한다.
                    req = PhraseRequest(
                        motif=motif, plan=plan, phrase_index=i, previous_measures=prev,
                        instruction=f"직전 시도가 검증에 걸렸다: {last_reason}. 이 문제를 피해서 다시 써라.",
                    )
                out = self.engine.realize_phrase(ctx, req)
                if len(out.measures) > MAX_PHRASE_MEASURES:
                    raise PhraseTooLongError(
                        f"엔진이 프레이즈 하나에 {len(out.measures)}마디를 반환했다"
                    )
                rep = validate_score(
                    out.measures, ctx.student, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key,
                    max_accidental_ratio=ctx.hard.max_accidental_ratio,
                )
                # 프레이즈 단위에서는 곡 전체 규칙(종지·시간제한)을 적용하지 않는다.
                blocking = [
                    i2 for i2 in rep.hard_failures
                    if i2.rule in (
                        "measure_length", "notatable_duration", "hand_span", "range",
                        "hand_crossing", "accidental_ratio",
                    )
                ]
                if not blocking:
                    realized = out.measures
                    break
                last_reason = blocking[0].message
                log.warning("프레이즈 %d 재시도 %d: %s", i, attempt + 1, last_reason)

            if realized is None:
                failures.append(f"프레이즈 {i}({lo}-{hi}) 실패: {last_reason}")
                continue
            for m in realized:
                produced[m.number] = m
            self.progress("realize", (i + 1) / len(phrases), f"{lo}-{hi}마디 완료")

        return [produced[n] for n in sorted(produced)], failures

    # ── Stage 5 ──────────────────────────────────────────────────────────
    def evaluate(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate,
    ) -> tuple[dict, CriticReport]:
        musicality = musicality_mod.evaluate(
            measures, motif=motif, plan=plan, max_span_semitones=ctx.hard.max_span_semitones
        ).as_dict()
        critic = self.engine.critique(ctx, measures, plan, motif, musicality)
        return musicality, critic

    def _combined(self, musicality: dict, critic: CriticReport) -> float:
        """규칙 지표(0~10 환산)와 비평 총점의 가중 평균. 지표가 뒤집히지 않게 40:60."""
        return round(0.4 * float(musicality["score_10"]) + 0.6 * critic.total, 2)

    def revise(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, critic: CriticReport,
    ) -> list[Measure]:
        """비평의 revision_requests 를 해당 프레이즈 재생성으로 실행한다."""
        by_number = {m.number: m for m in measures}
        phrases = plan.phrases()

        targets: set[int] = set()
        for rr in critic.revision_requests:
            lo, hi = rr.measures
            for i, p in enumerate(phrases):
                if not (p.measures[1] < lo or p.measures[0] > hi):
                    targets.add(i)

        for i in sorted(targets):
            p = phrases[i]
            lo, hi = p.measures
            instruction = " / ".join(
                rr.instruction for rr in critic.revision_requests
                if not (rr.measures[1] < lo or rr.measures[0] > hi)
            )
            prev = [by_number[n] for n in sorted(by_number) if n < lo][-8:]
            req = PhraseRequest(
                motif=motif, plan=plan, phrase_index=i, previous_measures=prev, instruction=instruction
            )
            out = self.engine.realize_phrase(ctx, req)
            rep = validate_score(
                out.measures, ctx.student, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key,
                max_accidental_ratio=ctx.hard.max_accidental_ratio,
            )
            blocking = [
                x for x in rep.hard_failures
                if x.rule in (
                    "measure_length", "notatable_duration", "hand_span", "range", "hand_crossing",
                )
            ]
            if blocking:
                log.warning("재생성 %d-%d 실패, 원본 유지: %s", lo, hi, blocking[0].message)
                continue
            for m in out.measures:
                by_number[m.number] = m
            self.progress("revise", 0.5, f"{lo}-{hi}마디 재생성")

        return [by_number[n] for n in sorted(by_number)]

    # ── 전체 ─────────────────────────────────────────────────────────────
    def compose(
        self,
        ctx: ComposerContext,
        motif: MotifCandidate,
        plan: CompositionPlan | None = None,
        *,
        corpus_ngrams: set[tuple[int, ...]] | None = None,
        title: str = "",
    ) -> CompositionResult:
        """Stage 2~5 를 한 번에. 모티브는 이미 잠긴 상태로 들어온다."""
        if plan is None:
            plan, plan_report = self.plan(ctx, motif)
            if not plan_report.passed:
                raise PlanRejected(
                    "Plan 규칙 검사 실패: "
                    + "; ".join(i.message for i in plan_report.hard_failures[:3])
                )

        measures, failures = self.realize(ctx, plan, motif)
        musicality, critic = self.evaluate(ctx, measures, plan, motif)
        combined = self._combined(musicality, critic)
        rounds = 0

        while combined < self.settings.quality_threshold and rounds < self.settings.max_revision_rounds:
            rounds += 1
            self.progress("critic", rounds / (self.settings.max_revision_rounds + 1),
                          f"{rounds}라운드 수정 — 현재 {combined:.2f} / 문턱 {self.settings.quality_threshold}")
            measures = self.revise(ctx, measures, plan, motif, critic)
            musicality, critic = self.evaluate(ctx, measures, plan, motif)
            new_combined = self._combined(musicality, critic)
            if new_combined <= combined:
                log.info("비평 루프가 더 나아지지 않는다(%.2f → %.2f). 중단.", combined, new_combined)
                combined = new_combined
                break
            combined = new_combined

        validation = validate_score(
            measures, ctx.student,
            meter=plan.meter, tempo=plan.tempo, key_sig=plan.key, plan=plan,
            competition=ctx.competition,
            target_difficulty=ctx.hard.target_difficulty,
            corpus_ngrams=corpus_ngrams,
            max_accidental_ratio=ctx.hard.max_accidental_ratio,
        )

        diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
        opts = AssembleOptions(
            title=title or (plan.title_candidates[0] if plan.title_candidates else "무제"),
            composer="AI 초안 · 원장 편곡",
            key_sig=plan.key, meter=plan.meter, tempo=plan.tempo,
        )
        xml = measures_to_musicxml(measures, opts)

        quality = QualityReport(
            musicality=musicality,
            critic=critic.model_dump(),
            revision_round=rounds,
            passed=combined >= self.settings.quality_threshold,
            threshold=self.settings.quality_threshold,
            combined_score=combined,
            notes=failures,
        )

        cost: dict[str, Any] = {}
        ledger = getattr(self.engine, "ledger", None)
        if ledger is not None:
            cost = ledger.summary()

        self.progress("done", 1.0,
                      f"완료 · 검증 {validation.summary()} · 품질 {combined:.2f} · 난이도 {diff.score}")

        return CompositionResult(
            measures=measures, plan=plan, motif=motif, musicxml=xml,
            validation=validation, quality=quality, difficulty=diff.score,
            engine=getattr(self.engine, "name", "unknown"),
            revision_rounds=rounds, phrase_failures=failures, cost=cost,
        )
