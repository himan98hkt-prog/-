"""§7.3 작곡 파이프라인 — Stage 0~5.

CLAUDE.md 절대 규칙 9: 모티브 잠금 → Plan → **프레이즈 단위** Realize → 비평 루프.
32마디를 한 호출로 만드는 경로는 존재하지 않는다(`PhraseTooLongError` 로 막는다).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.analysis import musicality as musicality_mod
from app.analysis.difficulty import difficulty_advice, difficulty_score
from app.config import Settings, get_settings
from app.generation.apierrors import ClaudeUnavailable
from app.generation.assemble import AssembleOptions, measures_to_musicxml
from app.generation.client import CostLimitExceeded
from app.generation.context import ComposerContext
from app.generation.engines.base import ComposerEngine, PhraseRequest
from app.generation.plan_rules import check_plan
from app.schemas.music import MAX_PHRASE_MEASURES, CompositionPlan, Measure, MotifCandidate
from app.schemas.quality import CriticReport, QualityReport, RevisionRequest, RubricScores
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


def _critic_with(
    critic_dump: dict[str, Any] | None, requests: list[RevisionRequest]
) -> CriticReport:
    """저장된 비평 결과에 수정 지시만 갈아 끼운다.

    `CriticReport.total` 은 계산 필드라 직렬화에는 들어가지만 다시 넣을 수는 없다.
    되돌려 읽을 때 그것을 빼 주지 않으면 extra_forbidden 으로 막힌다.
    """
    body = {k: v for k, v in (critic_dump or {}).items() if k != "total"}
    body["revision_requests"] = []
    return CriticReport.model_validate(body).model_copy(update={"revision_requests": requests})


_MEASURE_RE = re.compile(r"(\d{1,3})\s*(?:~|-|–|—|부터)\s*(\d{1,3})\s*마디|(\d{1,3})\s*마디")


def _measure_hints(text: str, total: int) -> list[tuple[int, int]]:
    """심사평에서 마디 번호를 뽑는다 — "13~16마디", "25마디" 둘 다 받는다.

    번호가 없는 지적("전체적으로 밋밋하다")은 겨냥할 곳이 없으므로 빈 목록이다.
    곡 밖을 가리키는 번호도 버린다 — 심사위원이 헷갈린 것이지 고칠 곳이 아니다.
    """
    out: list[tuple[int, int]] = []
    for a, b, single in _MEASURE_RE.findall(text):
        lo, hi = (int(a), int(b)) if a else (int(single), int(single))
        if lo > hi:
            lo, hi = hi, lo
        if 1 <= lo <= total:
            out.append((lo, min(hi, total)))
    return out


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
    def plan(
        self,
        ctx: ComposerContext,
        motif: MotifCandidate,
        *,
        previous_plans: Sequence[tuple[str, CompositionPlan]] = (),
    ) -> tuple[CompositionPlan, ValidationReport]:
        """설계도 생성 + 규칙 검사.

        `previous_plans` 는 같은 학원이 이미 만든 곡들의 설계도다. 형식이 겹치면
        여기서 막는다 — 음표를 쓰기 전이라 가장 싸다.
        """
        if not motif.selected:
            motif = motif.model_copy(update={"selected": True})   # motif_locked
        self.progress("plan", 0.0, "설계도 생성")
        plan = self.engine.plan(ctx, motif)
        report = check_plan(
            plan, ctx.student,
            time_limit_sec=ctx.hard.time_limit_sec, previous_plans=previous_plans,
        )
        self.progress("plan", 1.0, f"Plan 규칙 검사: {report.summary()}")
        return plan, report

    # ── Stage 3~4 ────────────────────────────────────────────────────────
    def realize(
        self, ctx: ComposerContext, plan: CompositionPlan, motif: MotifCandidate
    ) -> tuple[list[Measure], list[str]]:
        phrases = plan.phrases()
        produced: dict[int, Measure] = {}
        failures: list[str] = []
        budget_gone = ""

        for i, p in enumerate(phrases):
            if budget_gone:
                break
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
                try:
                    out = self.engine.realize_phrase(ctx, req)
                except CostLimitExceeded as e:
                    # 예산이 바닥났다. 남은 프레이즈는 부를 수 없다 — 불러 봐야 같은
                    # 자리에서 막힌다. 그렇다고 **여기까지 만든 마디를 버리면 안 된다.**
                    # 그것은 이미 값을 치른 것이고, 버리는 순간 원장님 눈에는
                    # "돈만 나가고 결과물은 없다" 가 된다.
                    log.warning("프레이즈 %d 에서 예산이 바닥났다 — 만든 데까지 지킨다: %s", i, e)
                    budget_gone = str(e)
                    break
                except ClaudeUnavailable as e:
                    # **여기서 곡 전체를 버리면 안 된다.**
                    #
                    # 앞선 프레이즈들은 이미 만들어졌고 이미 값을 치렀다. 프레이즈 하나가
                    # 안 됐다고 통째로 던지면 그 돈이 전부 사라진다 — 원장님이 "비용은
                    # 엄청 나왔는데 결과물은 없다" 고 하신 손해가 바로 이것이다.
                    #
                    # 단, 키가 거절됐거나 잔액이 없는 것은 다음 프레이즈도 똑같이 막힌다.
                    # 그때는 계속 부르는 것이 시간 낭비이므로 그대로 올려 보낸다.
                    if not getattr(e, "per_request", False):
                        raise
                    last_reason = e.message
                    log.warning("프레이즈 %d 를 만들지 못했다 — 나머지는 계속한다: %s", i, e.message)
                    break
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

            if budget_gone:
                break
            if realized is None:
                failures.append(f"프레이즈 {i}({lo}-{hi}) 실패: {last_reason}")
                continue
            for m in realized:
                produced[m.number] = m
            self.progress("realize", (i + 1) / len(phrases), f"{lo}-{hi}마디 완료")

        if budget_gone:
            done = len(produced)
            failures.append(
                f"정한 비용 상한에 닿아 {done}마디까지만 만들었습니다. "
                "'작곡 비용' 에서 '넘더라도 끝까지' 를 고르시면 끝까지 만듭니다."
            )
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

    def _unjudged(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate,
    ) -> tuple[dict, CriticReport]:
        """비평가를 부를 돈이 없을 때 쓰는 **채점 없는 성적표**.

        규칙 지표(musicality)는 코드가 계산하므로 공짜다 — 그것만 낸다. 비평 점수는
        0 으로 두어 곡이 자동으로 '통과' 로 표시되지 않게 한다. 곡은 초안으로 남고,
        원장님은 화면에서 왜 채점이 없는지 함께 보시게 된다.
        """
        musicality = musicality_mod.evaluate(
            measures, motif=motif, plan=plan, max_span_semitones=ctx.hard.max_span_semitones,
            difficulty_target=ctx.hard.target_difficulty,
        ).as_dict()
        blank = RubricScores(
            motif_development=0, form_clarity=0, harmony=0, voice_leading=0, phrasing=0,
            climax_ending=0, student_fit=0, competition_effect=0, notation=0, originality=0,
        )
        critic = CriticReport(
            scores=blank,
            overall_comment=(
                "비용 상한에 닿아 비평을 하지 못했습니다 — "
                "점수가 없는 것이지 곡이 나쁜 것이 아닙니다."
            ),
        )
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
        # 구간은 **경고가 난 마디**로 고르면서 지시는 비평가의 넓은 지적을 그대로 넘기면,
        # 작곡가는 1~4마디를 받아 들고 27마디에 대한 지시를 읽는다. 무엇을 없애야 하는지를
        # 지시 맨 앞에 붙여 준다.
        note = "검증기 경고를 없애는 것이 이번 수정의 목적이다 — " + "; ".join(
            sorted({i.message for i in issues})[:8]
        )
        targeted = [
            rr.model_copy(update={"instruction": f"{note} · (비평가 지적) {rr.instruction}"})
            for rr in targeted
        ]
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

    # 한 번의 겨냥 수정이 손댈 수 있는 최대 구간. 이보다 넓은 지적("곡 전체가
    # 평범하다")은 프레이즈 재생성으로 실행할 수 없다 — 원장에게 글로 넘긴다.
    TARGETED_SPAN_LIMIT = 12

    def _objective(self, combined: float, difficulty: float, target: float) -> float:
        """종합 점수와 난이도를 하나의 값으로. 난이도는 허용 오차 밖의 초과분만 벌한다."""
        over = max(0.0, abs(difficulty - target) - self.settings.difficulty_tolerance)
        return combined - 2.0 * over

    def _targeted(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, critic: CriticReport, combined: float,
    ) -> tuple[list[Measure], tuple[dict, CriticReport, float] | None, list[str]]:
        """종합 점수가 문턱을 넘어도 **약한 루브릭 항목과 빗나간 난이도**는 고친다.

        이 패스가 없으면 비평가가 낸 수정 지시가 한 건도 실행되지 않는다. 실제로
        다섯 곡에서 지시 15건이 나왔는데 종합 8.4~8.6 이 문턱 7.0 을 넘는다는
        이유로 전부 버려졌다 — 곡이 좋았던 것은 루프가 아니라 사람이 고쳐서였다.

        돌려주는 셋째 값은 **실행하지 못한 지적**이다. 곡 전체를 가리키는 말은
        프레이즈 재생성으로 옮길 수 없으므로 원장에게 글로 남긴다.
        """
        notes: list[str] = []
        weak = [
            f"{k} {v}" for k, v in critic.scores.as_dict().items()
            if v < self.settings.rubric_floor
        ]
        diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
        target = ctx.hard.target_difficulty
        advice = (
            difficulty_advice(diff, target)
            if abs(diff.score - target) > self.settings.difficulty_tolerance
            else []
        )
        if not weak and not advice:
            return measures, None, notes

        if weak:
            notes.append("약한 루브릭: " + ", ".join(weak))
        notes.extend(advice)

        actionable: list[RevisionRequest] = []
        too_broad: list[RevisionRequest] = []
        # 모티브가 처음 제시되는 마디는 손대지 않는다. 모티브는 원장이 듣고 고른
        # 뒤 **잠긴** 것이고(절대 규칙 9), 머리를 바꾸면 그것을 되풀이하는 모든
        # 자리가 함께 바뀌어야 하는데 프레이즈 단위 재생성으로는 그럴 수 없다.
        locked_until = len(motif.measures)
        for rr in critic.revision_requests:
            span = rr.measures[1] - rr.measures[0] + 1
            touches_motif = rr.measures[0] <= locked_until
            (too_broad if span > self.TARGETED_SPAN_LIMIT or touches_motif
             else actionable).append(rr)
        for rr in too_broad:
            span = rr.measures[1] - rr.measures[0] + 1
            why = (
                "곡 전체" if span > self.TARGETED_SPAN_LIMIT
                else "모티브 잠금 구간"
            )
            notes.append(
                f"[{rr.measures[0]}-{rr.measures[1]}] ({why}) {rr.issue} → {rr.instruction}"
            )
        if not actionable:
            notes.append("겨냥해서 고칠 수 있는 지시가 없다 — 원장 판단이 필요하다")
            return measures, None, notes

        if advice:
            hint = " / ".join(advice[1:])
            actionable = [
                rr.model_copy(update={"instruction": f"{rr.instruction} · 난이도 조정: {hint}"})
                for rr in actionable
            ]
        self.progress("targeted", 0.3, f"겨냥 수정 {len(actionable)}건 ({', '.join(weak) or '난이도'})")

        trimmed = critic.model_copy(update={"revision_requests": actionable})
        candidate = self.revise(ctx, measures, plan, motif, trimmed)
        new_musicality, new_critic = self.evaluate(ctx, candidate, plan, motif)
        new_combined = self._combined(new_musicality, new_critic)
        new_diff = difficulty_score(
            candidate, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key
        )
        # 채택 기준은 두 값을 합친 하나의 목표다. 난이도는 **허용 오차를 벗어난 만큼만**
        # 벌점이 된다 — 이미 오차 안에 있는 곡을 0.01 흔들렸다고 버리면, 점수가 오른
        # 수정도 통째로 날아간다(실제로 g02 에서 8.60→8.66 이 그렇게 버려졌다).
        if self._objective(new_combined, new_diff.score, target) < self._objective(
            combined, diff.score, target
        ):
            self.progress(
                "targeted", 1.0,
                f"겨냥 수정 폐기 (점수 {combined:.2f}→{new_combined:.2f}, "
                f"난이도 {diff.score:.2f}→{new_diff.score:.2f})",
            )
            notes.append("겨냥 수정을 시도했으나 더 나아지지 않아 원본을 유지했다")
            return measures, None, notes

        self.progress(
            "targeted", 1.0,
            f"겨냥 수정 채택 (점수 {combined:.2f}→{new_combined:.2f}, "
            f"난이도 {diff.score:.2f}→{new_diff.score:.2f})",
        )
        return candidate, (new_musicality, new_critic, new_combined), notes

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
    # ── 곡이 나온 뒤에 고치는 두 길 ──────────────────────────────────────────

    def finish_edited(
        self, ctx: ComposerContext, measures: list[Measure], plan: CompositionPlan,
        motif: MotifCandidate, *, rounds: int, notes: list[str],
        corpus_ngrams: set[tuple[int, ...]] | None = None, title: str = "",
    ) -> CompositionResult:
        """고쳐진 마디를 받아 채점·검증·조립까지 끝낸 결과로 만든다.

        `compose` 의 뒤쪽 절반과 같은 일을 한다 — 심사 되먹임·원장 편곡·직접 편집처럼
        **이미 있는 곡을 고친 뒤**에도 같은 관문을 그대로 통과시키기 위해서다.
        작곡 엔진을 부르지 않으므로 사람이 직접 고친 마디에도 그대로 쓸 수 있다.
        """
        musicality, critic = self.evaluate(ctx, measures, plan, motif)
        combined = self._combined(musicality, critic)
        validation = validate_score(
            measures, ctx.student,
            meter=plan.meter, tempo=plan.tempo, key_sig=plan.key, plan=plan,
            competition=ctx.competition,
            target_difficulty=ctx.hard.target_difficulty,
            corpus_ngrams=corpus_ngrams,
            max_accidental_ratio=ctx.hard.max_accidental_ratio,
        )
        diff = difficulty_score(measures, meter=plan.meter, tempo=plan.tempo, key_sig=plan.key)
        sat = diff.saturated()
        extra = list(notes)
        if sat:
            extra.append(
                "난이도 특징이 상한에 걸렸다(더 밀어도 점수가 오르지 않는다): "
                + ", ".join(f"{k} {d}" for k, d in sat.items())
            )
        opts = AssembleOptions(
            title=title or (plan.title_candidates[0] if plan.title_candidates else "무제"),
            key_sig=plan.key, meter=plan.meter, tempo=plan.tempo,
        )
        quality = QualityReport(
            musicality=musicality, critic=critic.model_dump(), revision_round=rounds,
            passed=combined >= self.settings.quality_threshold,
            threshold=self.settings.quality_threshold,
            combined_score=combined, notes=extra,
        )
        cost: dict[str, Any] = {}
        ledger = getattr(self.engine, "ledger", None)
        if ledger is not None:
            cost = ledger.summary()
        return CompositionResult(
            request_id=ctx.request.id, measures=measures, plan=plan, motif=motif,
            musicxml=measures_to_musicxml(measures, opts),
            validation=validation, quality=quality, difficulty=diff.score,
            engine=getattr(self.engine, "name", "unknown"),
            revision_rounds=rounds, phrase_failures=[], cost=cost,
        )

    def revise_with_notes(
        self, ctx: ComposerContext, result: CompositionResult, notes: list[str],
    ) -> CompositionResult | None:
        """모의 심사위원 여럿이 공통으로 지적한 것을 겨냥해 다시 쓴다.

        지적에 마디 번호가 없으면 실행할 수 없다 — 어디를 고치라는 말인지 모르는 지시로
        곡 전체를 다시 쓰면 좋아진 것인지 나빠진 것인지도 알 수 없다. 그런 지적은
        돌려주지 않고 None 을 낸다(원장에게 글로 넘어간다).

        점수가 떨어지면 **원본을 유지한다**. 심사 되먹임이 곡을 나쁘게 만드는 일은 없어야 한다.
        """
        spans = [m for n in notes for m in _measure_hints(n, len(result.measures))]
        if not spans:
            return None
        targets = {n for lo, hi in spans for n in range(lo, hi + 1)}
        requests = [
            RevisionRequest(measures=[lo, hi], issue="모의 심사 공통 지적", instruction=note)
            for note, (lo, hi) in zip(notes, spans, strict=False)
        ]
        trimmed = _critic_with(result.quality.critic, requests)
        candidate = self.revise(
            ctx, result.measures, result.plan, result.motif, trimmed, only_measures=targets
        )
        out = self.finish_edited(
            ctx, candidate, result.plan, result.motif,
            rounds=result.revision_rounds + 1,
            notes=[*result.quality.notes, "모의 심사 되먹임 1회"],
        )
        if out.quality.combined_score < result.quality.combined_score or not out.savable:
            return None
        return out

    def rearrange(
        self, ctx: ComposerContext, result: CompositionResult,
        region: tuple[int, int], instruction: str,
    ) -> CompositionResult:
        """원장이 지정한 구간만 다시 쓴다(§7.3 Stage 7).

        비평가를 거치지 않는다 — 이것은 채점이 아니라 **원장의 결정**이다. 다만 검증기와
        지표는 그대로 돌려서, 고친 결과가 학생 제약을 벗어나면 화면에 보이게 한다.
        """
        lo, hi = region
        rq = RevisionRequest(measures=[lo, hi], issue="원장 편곡 요청", instruction=instruction)
        trimmed = _critic_with(result.quality.critic, [rq])
        measures = self.revise(
            ctx, result.measures, result.plan, result.motif, trimmed,
            only_measures=set(range(lo, hi + 1)),
        )
        return self.finish_edited(
            ctx, measures, result.plan, result.motif,
            rounds=result.revision_rounds,
            notes=[*result.quality.notes, f"원장 편곡 {lo}~{hi}마디: {instruction}"],
        )

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

        # **여기서부터는 전부 '더 좋게 만드는' 일이다 — 곡은 이미 있다.**
        # 채점·비평·수정은 모두 돈이 드는 호출이고, 예산이 바닥나면 그 자리에서
        # 예외가 난다. 그때 예외를 그대로 올려 보내면 방금 만든 마디가 통째로
        # 사라진다. 값은 이미 치렀는데 곡은 못 얻는 — 가장 나쁜 결과다.
        # 그래서 여기서부터는 예산 부족을 **실패가 아니라 '여기까지'** 로 다룬다.
        try:
            musicality, critic = self.evaluate(ctx, measures, plan, motif)
        except CostLimitExceeded as e:
            log.warning("채점 전에 예산이 바닥났다 — 곡은 그대로 두고 마무리한다: %s", e)
            musicality, critic = self._unjudged(ctx, measures, plan, motif)
            failures.append(
                "정한 비용 상한에 닿아 비평(채점)까지는 하지 못했습니다. "
                "곡은 그대로 있습니다 — 4단계에서 직접 고치시거나, "
                "'작곡 비용' 을 올려 다시 만들어 보십시오."
            )
        combined = self._combined(musicality, critic)
        rounds = 0

        while combined < self.settings.quality_threshold and rounds < self.settings.max_revision_rounds:
            rounds += 1
            self.progress(
                "critic",
                rounds / (self.settings.max_revision_rounds + 1),
                f"{rounds}라운드 수정 — 현재 {combined:.2f} / 문턱 {self.settings.quality_threshold}",
            )
            try:
                measures = self.revise(ctx, measures, plan, motif, critic)
                musicality, critic = self.evaluate(ctx, measures, plan, motif)
            except CostLimitExceeded as e:
                log.warning("수정 라운드 중 예산이 바닥났다 — 직전 상태로 마무리한다: %s", e)
                failures.append("정한 비용 상한에 닿아 고쳐 쓰기를 멈췄습니다. 곡은 그대로 있습니다.")
                rounds -= 1
                break
            new_combined = self._combined(musicality, critic)
            if new_combined <= combined:
                log.info("비평 루프가 더 나아지지 않는다(%.2f → %.2f). 중단.", combined, new_combined)
                combined = new_combined
                break
            combined = new_combined

        # 문턱을 넘었더라도 검증기가 잡아낸 흠(병행 5·8도, 밋밋한 첫 8마디, 약한 마무리)이
        # 남아 있으면 한 번 더 다듬는다. 문턱 통과가 '고칠 게 없다' 는 뜻은 아니다.
        if rounds < self.settings.max_revision_rounds:
            try:
                measures, polished = self._polish(ctx, measures, plan, motif, critic, combined)
            except CostLimitExceeded:
                polished = None          # 다듬기는 없어도 곡은 곡이다
            if polished is not None:
                musicality, critic, combined = polished
                rounds += 1

        # 종합 점수가 문턱을 넘어도 약한 루브릭 항목과 빗나간 난이도는 남는다.
        advisory: list[str] = []
        if rounds < self.settings.max_revision_rounds:
            try:
                measures, tuned, advisory = self._targeted(
                    ctx, measures, plan, motif, critic, combined
                )
            except CostLimitExceeded:
                tuned = None             # 겨냥 수정도 마찬가지다
            if tuned is not None:
                musicality, critic, combined = tuned
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
        # 상한에 걸린 특징은 난이도가 목표에 맞아도 알려 준다 — 다음 곡의 조성·템포 선택이
        # 달라져야 하는 신호이기 때문이다.
        sat = diff.saturated()
        if sat:
            advisory.append(
                "난이도 특징이 상한에 걸렸다(더 밀어도 점수가 오르지 않는다): "
                + ", ".join(f"{k} {d}" for k, d in sat.items())
            )
        opts = AssembleOptions(
            title=title or (plan.title_candidates[0] if plan.title_candidates else "무제"),
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
            notes=failures + advisory,
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
