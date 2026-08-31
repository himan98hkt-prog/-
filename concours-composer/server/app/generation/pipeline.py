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
from app.schemas.music import MAX_PHRASE_MEASURES, CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import CriticReport, QualityReport
from app.validate.validator import Issue, ValidationReport, validate_score

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, float, str], None]


class PhraseTooLongError(RuntimeError):
    """절대 규칙 9 위반 — 한 호출이 프레이즈보다 큰 범위를 만들려 했다."""


class PlanRejected(RuntimeError):
    pass


@dataclass
class CompositionResult:
    request_id: str
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
    def soft_warning_issues(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan
    ) -> list[Issue]:
        """검증기의 소프트 규칙 위반. 저장은 막지 않지만 음악적으로는 흠이다.

        비평가에게 넘기지 않으면 아무도 고치지 않는다 — 병행 5·8도가 매 곡 대여섯 건씩
        남아 있던 이유가 이것이었다.
        """
        report = validate_score(
            measures, ctx.student, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key,
            plan=plan, competition=ctx.competition,
            max_accidental_ratio=ctx.hard.max_accidental_ratio,
        )
        return report.warnings

    def soft_warnings(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan
    ) -> list[str]:
        return [
            f"[{i.rule}] {i.message}" for i in self.soft_warning_issues(ctx, measures, plan)
        ]

    def evaluate(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate,
    ) -> tuple[dict, CriticReport]:
        musicality = musicality_mod.evaluate(
            measures, motif=motif, plan=plan, max_span_semitones=ctx.hard.max_span_semitones,
            difficulty_target=ctx.hard.target_difficulty,
        ).as_dict()
        warnings = self.soft_warnings(ctx, measures, plan)
        critic = self.engine.critique(ctx, measures, plan, motif, musicality, warnings)
        return musicality, critic

    def _combined(self, musicality: dict, critic: CriticReport) -> float:
        """규칙 지표(0~10 환산)와 비평 총점의 가중 평균. 지표가 뒤집히지 않게 40:60."""
        return round(0.4 * float(musicality["score_10"]) + 0.6 * critic.total, 2)

    def revise(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, critic: CriticReport,
        only_measures: set[int] | None = None,
    ) -> list[Measure]:
        """비평의 revision_requests 를 해당 프레이즈 재생성으로 실행한다.

        `only_measures` 를 주면 그 마디를 품은 프레이즈만 다시 쓴다. 비평가가 "곡이
        너무 짧다" 처럼 곡 전체를 가리키는 지적을 하면 범위가 1~마지막마디가 되는데,
        그것 때문에 멀쩡한 프레이즈까지 다시 쓰면 손해다.
        """
        by_number = {m.number: m for m in measures}
        phrases = plan.phrases()

        targets: set[int] = set()
        for rr in critic.revision_requests:
            lo, hi = rr.measures
            for i, p in enumerate(phrases):
                if p.measures[1] < lo or p.measures[0] > hi:
                    continue
                if only_measures is not None and not any(
                    p.measures[0] <= n <= p.measures[1] for n in only_measures
                ):
                    continue
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

    def _polish(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, critic: CriticReport, combined: float,
    ) -> tuple[list[Measure], tuple[dict, CriticReport, float] | None]:
        """마무리 다듬기 — 검증기 경고가 실제로 난 **마디를 겨냥한** 수정만 실행한다.

        예전에는 비평문에 '병행'·'마무리' 같은 낱말이 있는지로 골랐는데, 경고가 하나도
        없는 곡도 비평가가 그 단어를 쓰기만 하면 다듬기가 돌았다. 경고의 마디 번호와
        수정 지시의 마디 범위가 겹치는지로 판단해야 겨냥이 맞는다.

        점수가 떨어지거나 경고가 줄지 않으면 **원본을 유지한다**. 다듬기가 곡을
        나쁘게 만드는 일은 없어야 한다.
        """
        issues = self.soft_warning_issues(ctx, measures, plan)
        flagged = {n for i in issues for n in i.measures}
        if not flagged:
            return measures, None

        targeted = [
            rr for rr in critic.revision_requests
            if any(rr.measures[0] <= n <= rr.measures[1] for n in flagged)
        ]
        if not targeted:
            return measures, None

        before = len(issues)
        trimmed = critic.model_copy(update={"revision_requests": targeted})
        self.progress("polish", 0.5, f"검증기 경고 {before}건을 겨냥해 다듬는 중")

        candidate = self.revise(ctx, measures, plan, motif, trimmed, only_measures=flagged)
        new_musicality, new_critic = self.evaluate(ctx, candidate, plan, motif)
        new_combined = self._combined(new_musicality, new_critic)
        after = len(self.soft_warnings(ctx, candidate, plan))

        if new_combined < combined or after >= before:
            self.progress(
                "polish", 1.0,
                f"다듬기 폐기 (경고 {before}→{after}, 점수 {combined:.2f}→{new_combined:.2f})",
            )
            return measures, None

        self.progress(
            "polish", 1.0,
            f"다듬기 채택 (경고 {before}→{after}, 점수 {combined:.2f}→{new_combined:.2f})",
        )
        return candidate, (new_musicality, new_critic, new_combined)

    # ── 3안 생성 (§7.9 원칙 5) ───────────────────────────────────────────
    def compose_candidates(
        self,
        ctx: ComposerContext,
        motif: MotifCandidate,
        plan: CompositionPlan | None = None,
        *,
        n: int = 1,
        corpus_ngrams: set[tuple[int, ...]] | None = None,
        title: str = "",
    ) -> list[CompositionResult]:
        """같은 모티브·설계로 여러 안을 만들고 **종합 점수 내림차순**으로 돌려준다.

        §7.9 원칙 5: 3안 생성 후 최고 점수안을 기본 표시하고 나머지는 비교 청취.
        안마다 설계를 새로 뽑는 게 아니라 **같은 잠긴 모티브**를 공유한다 — 모티브가
        바뀌면 비교가 성립하지 않는다.
        """
        n = max(1, min(3, n))
        results: list[CompositionResult] = []
        for i in range(n):
            self.progress("candidates", (i + 1) / n, f"{i + 1}/{n} 안 생성")
            # 안마다 Plan 을 새로 뽑으면 형식이 달라져 비교가 어렵다. 첫 안의 Plan 을
            # 공유하되, 두 번째 안부터는 텍스처 지시를 바꿔 실제로 다른 곡이 나오게 한다.
            variant_plan = plan if i == 0 else self._variant_plan(plan, i)
            try:
                res = self.compose(
                    ctx, motif, variant_plan, corpus_ngrams=corpus_ngrams, title=title
                )
            except (PlanRejected, PhraseTooLongError) as e:
                log.warning("%d번째 안 실패: %s", i + 1, e)
                continue
            results.append(res)
            if plan is None:
                plan = res.plan       # 첫 안의 Plan 을 이후 안이 공유한다

        if not results:
            raise PlanRejected("어떤 안도 만들지 못했다")
        results.sort(key=lambda r: (r.savable, r.quality.combined_score), reverse=True)
        return results

    @staticmethod
    def _variant_plan(plan: CompositionPlan | None, index: int) -> CompositionPlan | None:
        """두 번째 안부터 텍스처와 모티브 처리를 돌려 다른 성격의 곡을 만든다."""
        if plan is None:
            return None
        rotations = [
            ("분산화음 반주(알베르티), 4분음표 단위", "지속 화음 + 저음역 이동, 온음표 단위"),
            ("지속 화음 + 저음역 이동, 온음표 단위", "분산화음 반주, 마지막 4마디는 화음 두껍게"),
        ]
        src, dst = rotations[(index - 1) % len(rotations)]
        form = [s.model_copy(deep=True) for s in plan.form]
        for sec in form:
            for ph in sec.phrases:
                if ph.texture_lh == src:
                    ph.texture_lh = dst
        return plan.model_copy(update={"form": form})

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
            self.progress(
                "critic",
                rounds / (self.settings.max_revision_rounds + 1),
                f"{rounds}라운드 수정 — 현재 {combined:.2f} / 문턱 {self.settings.quality_threshold}",
            )
            measures = self.revise(ctx, measures, plan, motif, critic)
            musicality, critic = self.evaluate(ctx, measures, plan, motif)
            new_combined = self._combined(musicality, critic)
            if new_combined <= combined:
                log.info("비평 루프가 더 나아지지 않는다(%.2f → %.2f). 중단.", combined, new_combined)
                combined = new_combined
                break
            combined = new_combined

        # 문턱을 넘었더라도 검증기가 잡아낸 흠(병행 5·8도, 밋밋한 첫 8마디, 약한 마무리)이
        # 남아 있으면 한 번 더 다듬는다. 문턱 통과가 '고칠 게 없다' 는 뜻은 아니다.
        if rounds < self.settings.max_revision_rounds:
            measures, polished = self._polish(ctx, measures, plan, motif, critic, combined)
            if polished is not None:
                musicality, critic, combined = polished
                rounds += 1

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
            request_id=ctx.request.id,
            measures=measures, plan=plan, motif=motif, musicxml=xml,
            validation=validation, quality=quality, difficulty=diff.score,
            engine=getattr(self.engine, "name", "unknown"),
            revision_rounds=rounds, phrase_failures=failures, cost=cost,
        )
