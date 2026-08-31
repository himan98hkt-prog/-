"""세션 엔진 — 이 Claude Code 세션이 직접 작곡가·비평가를 맡는다.

API 를 호출하지 않는다. 대신 각 단계의 프롬프트를 파일로 내놓고, 사람(또는 이 세션의
Claude)이 같은 폴더에 `<단계>_response.json` 을 써 주면 그것을 읽어 파이프라인을 잇는다.

    runs/golden/<요청id>/
      motif_prompt.md        motif_response.json
      plan_prompt.md         plan_response.json
      phrase_01_prompt.md    phrase_01_response.json
      ...
      critic_prompt.md       critic_response.json

검증기·음악성 지표·표절 검사는 **코드가 그대로** 돌린다. 즉 이 모드에서 나온 곡도
StubComposerEngine 이나 ClaudeComposerEngine 으로 만든 곡과 똑같은 관문을 통과해야 한다.

토큰 수는 실제로 세어 원장(CostLedger)에 남긴다 — 나중에 API 로 전환할 때 곡당 비용을
그대로 계산하기 위해서다(원장 지시 5).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.generation.client import CallRecord, CostLedger, estimate_cost
from app.generation.context import ComposerContext, estimate_measures
from app.generation.engines.base import PhraseRequest
from app.generation.engines.claude_engine import (
    MotifBatch,
    fixed_context,
    load_prompt,
    prompt_version,
    score_to_text,
)
from app.schemas.music import CompositionPlan, Measure, MotifCandidate, PhraseRealization
from app.schemas.quality import CriticReport

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# 응답 파일을 기다리는 기본 시간. 사람이 손으로 쓰는 시간을 고려한다.
DEFAULT_WAIT_SECONDS = 1800
POLL_SECONDS = 2

# 토큰 근사: 한국어·JSON 혼합에서 1토큰 ≈ 2.2자. count_tokens 를 쓸 수 없으므로
# 보수적으로 잡는다. 실제 API 전환 시 이 상수만 실측값으로 바꾸면 된다.
CHARS_PER_TOKEN = 2.2


class AwaitingResponse(RuntimeError):
    """응답 파일이 아직 없다. 프롬프트를 읽고 JSON 을 써 넣은 뒤 다시 실행하라."""

    def __init__(self, stage: str, prompt_path: Path, response_path: Path) -> None:
        self.stage = stage
        self.prompt_path = prompt_path
        self.response_path = response_path
        super().__init__(
            f"[{stage}] 응답 대기 중\n"
            f"  프롬프트: {prompt_path}\n"
            f"  여기에 써라: {response_path}"
        )


@dataclass
class SessionStats:
    prompts_written: int = 0
    responses_read: int = 0


def approx_tokens(text: str) -> int:
    return max(1, int(len(text) / CHARS_PER_TOKEN))


class SessionComposerEngine:
    """`GOLDEN_ENGINE=session`. 프롬프트를 내놓고 응답 파일을 기다린다."""

    name = "session"

    def __init__(
        self,
        run_dir: Path,
        *,
        settings: Settings | None = None,
        ledger: CostLedger | None = None,
        wait: bool = True,
        wait_seconds: int = DEFAULT_WAIT_SECONDS,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings or get_settings()
        self.ledger = ledger or CostLedger(
            limit_usd=self.settings.max_cost_per_composition, engine=self.name
        )
        self.wait = wait
        self.wait_seconds = wait_seconds
        self.stats = SessionStats()
        self._phrase_seq = 0

    # ── 프롬프트 파일 ────────────────────────────────────────────────────
    def _write_prompt(
        self,
        stage: str,
        *,
        system: str,
        fixed: str,
        user: str,
        output_model: type[BaseModel],
        note: str = "",
    ) -> Path:
        path = self.run_dir / f"{stage}_prompt.md"
        schema = json.dumps(output_model.model_json_schema(), ensure_ascii=False, indent=2)
        body = f"""<!-- 단계: {stage} · 응답 파일: {stage}_response.json -->
# 작업

아래 시스템 지시를 따르고, **맨 아래 JSON 스키마에 맞는 JSON 하나만** 다음 파일에 써라.

    {self.run_dir / f"{stage}_response.json"}

{note}

---

## 시스템 지시

{system}

---

## 고정 컨텍스트 (곡 하나 동안 바뀌지 않는다 — 실제 API 에서는 캐시된다)

```json
{fixed}
```

---

## 이번 요청

```json
{user}
```

---

## 출력 JSON 스키마

```json
{schema}
```
"""
        path.write_text(body, encoding="utf-8")
        self.stats.prompts_written += 1
        return path

    def _ask(
        self,
        stage: str,
        *,
        system: str,
        fixed: str,
        user: str,
        output_model: type[T],
        note: str = "",
    ) -> T:
        prompt_path = self._write_prompt(
            stage, system=system, fixed=fixed, user=user, output_model=output_model, note=note
        )
        response_path = self.run_dir / f"{stage}_response.json"

        started = time.monotonic()
        if not response_path.exists():
            if not self.wait:
                raise AwaitingResponse(stage, prompt_path, response_path)
            log.info("[%s] 응답 대기: %s", stage, response_path)
            deadline = time.monotonic() + self.wait_seconds
            while not response_path.exists():
                if time.monotonic() > deadline:
                    raise AwaitingResponse(stage, prompt_path, response_path)
                time.sleep(POLL_SECONDS)

        raw = response_path.read_text(encoding="utf-8")
        try:
            parsed = output_model.model_validate_json(raw)
        except ValidationError as e:
            # 스키마를 벗어난 응답은 조용히 넘기지 않는다 — 무엇이 틀렸는지 파일로 남긴다.
            err_path = self.run_dir / f"{stage}_error.txt"
            err_path.write_text(str(e), encoding="utf-8")
            raise ValueError(
                f"[{stage}] 응답이 스키마를 벗어났다. 자세한 내용: {err_path}\n{e}"
            ) from e

        self.stats.responses_read += 1
        self._record(stage, system + fixed + user, raw, started)
        return parsed

    def _record(self, stage: str, prompt_text: str, response_text: str, started: float) -> None:
        """실제 호출은 없지만 토큰은 센다 — API 전환 비용 계산용(원장 지시 5)."""
        model_id = self.settings.composer_model
        rec = CallRecord(
            stage=stage,
            model=model_id,
            input_tokens=approx_tokens(prompt_text),
            output_tokens=approx_tokens(response_text),
            cache_read_tokens=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        # 세션 모드는 실제 지출이 0 이다. 비용은 '전환했다면' 값으로 따로 계산한다.
        rec.cost_usd = 0.0
        self.ledger.calls.append(rec)
        log.info(
            "[%s] 입력 ~%d토큰 · 출력 ~%d토큰 (전환 시 $%.4f)",
            stage, rec.input_tokens, rec.output_tokens,
            estimate_cost(model_id, rec.input_tokens, rec.output_tokens),
        )

    # ── ComposerEngine ───────────────────────────────────────────────────
    def motifs(self, ctx: ComposerContext, n: int, feedback: str = "") -> list[MotifCandidate]:
        payload: dict[str, Any] = {"n": n}
        if feedback:
            payload["director_feedback"] = feedback
        batch = self._ask(
            "motif",
            system=load_prompt("motif"),
            fixed=fixed_context(ctx),
            user=json.dumps(payload, ensure_ascii=False, indent=1),
            output_model=MotifBatch,
            note=(
                f"후보 {n}개를 만든다. 서로 성격이 확실히 달라야 한다. "
                "각 후보의 모든 마디는 박자표 한 마디를 정확히 채운다."
            ),
        )
        return [
            c.model_copy(update={"id": c.id or f"motif-{i + 1}"})
            for i, c in enumerate(batch.candidates)
        ]

    def plan(self, ctx: ComposerContext, motif: MotifCandidate) -> CompositionPlan:
        suggested = estimate_measures(ctx.request, motif.meter, motif.tempo)
        return self._ask(
            "plan",
            system=load_prompt("plan"),
            fixed=fixed_context(ctx),
            user=json.dumps(
                {
                    "locked_motif": motif.model_dump(),
                    "suggested_total_measures": suggested,
                },
                ensure_ascii=False, indent=1, default=str,
            ),
            output_model=CompositionPlan,
            note=(
                f"제안 마디 수 {suggested}. 프레이즈는 4마디 단위로 끊고 total_measures 를 "
                "빠짐없이 덮어야 한다. 클라이맥스는 전체의 60~80% 지점."
            ),
        )

    def realize_phrase(self, ctx: ComposerContext, req: PhraseRequest) -> PhraseRealization:
        lo, hi = req.measure_range
        self._phrase_seq += 1
        stage = f"phrase_{lo:02d}_{hi:02d}"
        if req.instruction:
            stage += "_fix"

        payload: dict[str, Any] = {
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
        name = "realize_phrase"
        if req.instruction:
            name = "regenerate_region"
            payload["instruction"] = req.instruction
            payload["region"] = [lo, hi]

        return self._ask(
            stage,
            system=load_prompt(name),
            fixed=fixed_context(ctx),
            user=json.dumps(payload, ensure_ascii=False, indent=1, default=str),
            output_model=PhraseRealization,
            note=(
                f"{lo}~{hi}마디만 만든다. 각 성부의 dur 합계는 정확히 한 마디여야 하고, "
                f"동시 타건 폭은 {ctx.hard.max_span_semitones}반음 이하, "
                f"음역은 {ctx.hard.lowest_midi}~{ctx.hard.highest_midi} 안이어야 한다. "
                "왼손 최고음이 오른손 최저음을 넘으면 안 된다."
            ),
        )

    def critique(
        self,
        ctx: ComposerContext,
        measures: list[Measure],
        plan: CompositionPlan,
        motif: MotifCandidate,
        musicality: dict,
        warnings: list[str] | None = None,
    ) -> CriticReport:
        return self._ask(
            "critic",
            system=load_prompt("critic"),
            fixed=fixed_context(ctx),
            user=json.dumps(
                {
                    "score_text": score_to_text(measures, plan),
                    "plan": plan.model_dump(),
                    "locked_motif": motif.model_dump(),
                    "rule_based_musicality": musicality,
                    "validator_warnings": warnings or [],
                    "total_measures": len(measures),
                },
                ensure_ascii=False, indent=1, default=str,
            ),
            output_model=CriticReport,
            note=(
                "당신은 이 곡을 쓰지 않았다. 후하게 주지 마라. "
                f"마디 참조는 1~{len(measures)} 안이어야 한다."
            ),
        )

    def versions(self) -> dict[str, str]:
        return {n: prompt_version(n) for n in ("motif", "plan", "realize_phrase", "critic")}
