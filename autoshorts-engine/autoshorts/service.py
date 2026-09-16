"""Phase 1 — Engine Service Layer.

기존 :func:`autoshorts.pipeline.run_pipeline` 을 **감싸기만 한다.** 파이프라인은
한 줄도 바꾸지 않는다. 이 계층이 하는 일은 네 가지다.

1. :class:`~autoshorts.contracts.JobSpec` → 기존 ``Settings`` 번역
2. 취소·멱등성·오류 분류처럼 **서버가 필요로 하는 것**을 추가
3. 권리 미확인 소스를 렌더 전에 멈춤
4. 결과를 :class:`~autoshorts.contracts.JobResult` 로 정규화

CLI 와 Gradio 는 여전히 ``run_pipeline`` 을 직접 부른다. 이 계층은 그 위에
얹히는 것이지 대체가 아니다.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import Settings, SubtitleStyle
from .contracts import (
    CostEvent,
    ErrorCode,
    JobOutput,
    JobResult,
    JobSpec,
    JobStatus,
    ProgressEvent,
    QualityCheck,
    StageTiming,
    utc_now,
)
from .storage import LocalStorage, Storage, StorageError
from .utils import get_logger, sanitize_filename

__all__ = [
    "EngineService",
    "JobStore",
    "InMemoryJobStore",
    "CancellationToken",
    "JobCancelled",
    "JobRecord",
    "classify_error",
    "STAGE_IDEMPOTENCY",
]

LOG = get_logger("service")

# 단계별 멱등성 규약.
#   reusable  : 같은 work_dir 에서 재실행 시 기존 산출물을 그대로 쓴다
#   recompute : 매번 다시 계산한다(비용이 낮거나 결정적이지 않다)
STAGE_IDEMPOTENCY = {
    "ingest": "reusable",       # 같은 소스 → 같은 파일. work_dir 해시로 캐시됨
    "transcribe": "reusable",   # transcription.json 이 있으면 재사용
    "analyze": "recompute",     # LLM 응답이 결정적이지 않다. 비용은 낮다
    "render": "reusable",       # 같은 이름의 출력이 있으면 덮어쓰지 않는다
}


class JobCancelled(RuntimeError):
    """협조적 취소 지점에서 발생."""


class CancellationToken:
    """스레드 안전한 취소 신호.

    강제 종료가 아니다. 파이프라인이 **단계 경계에서 스스로 확인**하고 멈춘다.
    렌더링 도중 프로세스를 죽이면 반쯤 쓰인 파일이 남기 때문이다.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self, stage: str = "") -> None:
        if self._event.is_set():
            raise JobCancelled(f"작업이 취소됐습니다{f' ({stage} 단계)' if stage else ''}.")


def classify_error(exc: BaseException) -> tuple[ErrorCode, str]:
    """예외를 계약상의 오류 코드로 분류한다.

    재시도 가능/불가능 구분이 여기서 결정되므로, 모르는 예외는 보수적으로
    ``INTERNAL_ERROR``(재시도 불가)로 둔다.
    """
    from .ai_analyzer import AnalysisError
    from .downloader import IngestError
    from .transcriber import TranscriptionError
    from .utils import CommandError, ToolNotFoundError
    from .video_renderer import RenderError

    message = str(exc)

    if isinstance(exc, JobCancelled):
        return ErrorCode.CANCELLED, message
    if isinstance(exc, IngestError):
        if "찾을 수 없" in message or "없습니다" in message:
            return ErrorCode.SOURCE_NOT_FOUND, message
        if "지원하지 않는" in message:
            return ErrorCode.UNSUPPORTED_FORMAT, message
        return ErrorCode.INVALID_INPUT, message
    if isinstance(exc, TranscriptionError):
        if "추출하지 못했습니다" in message:
            return ErrorCode.NO_SPEECH_DETECTED, message
        return ErrorCode.PROVIDER_UNAVAILABLE, message
    if isinstance(exc, AnalysisError):
        return ErrorCode.NO_CANDIDATES, message
    if isinstance(exc, (RenderError, CommandError)):
        return ErrorCode.RENDER_FAILED, message
    if isinstance(exc, ToolNotFoundError):
        return ErrorCode.PROVIDER_UNAVAILABLE, message
    if isinstance(exc, StorageError):
        return ErrorCode.STORAGE_ERROR, message
    if isinstance(exc, TimeoutError):
        return ErrorCode.TIMEOUT, message
    if isinstance(exc, (ValueError, TypeError)):
        return ErrorCode.INVALID_INPUT, message
    return ErrorCode.INTERNAL_ERROR, f"{type(exc).__name__}: {message}"


# ── 저장소 ─────────────────────────────────────────────────


class JobRecord:
    """작업 하나의 전체 상태."""

    def __init__(self, spec: JobSpec, result: JobResult) -> None:
        self.spec = spec
        self.result = result
        self.token = CancellationToken()
        self.events: list[ProgressEvent] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "result": self.result.to_dict(),
            "events": [e.to_dict() for e in self.events[-50:]],
        }


class JobStore(ABC):
    """작업 저장소 인터페이스.

    Phase 2 에서 PostgreSQL 구현으로 교체한다. 그때 이 인터페이스만 만족하면 된다.
    """

    @abstractmethod
    def create(self, record: JobRecord) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> JobRecord | None: ...

    @abstractmethod
    def update(self, record: JobRecord) -> None: ...

    @abstractmethod
    def find_by_idempotency_key(self, key: str, workspace_id: str) -> JobRecord | None: ...

    @abstractmethod
    def list_jobs(self, workspace_id: str = "", limit: int = 50) -> list[JobRecord]: ...


class InMemoryJobStore(JobStore):
    """테스트·단일 프로세스용 구현. 스레드 안전."""

    def __init__(self) -> None:
        self._records: dict[str, JobRecord] = {}
        self._lock = threading.RLock()

    def create(self, record: JobRecord) -> None:
        with self._lock:
            self._records[record.spec.job_id] = record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._records.get(job_id)

    def update(self, record: JobRecord) -> None:
        with self._lock:
            self._records[record.spec.job_id] = record

    def find_by_idempotency_key(self, key: str, workspace_id: str) -> JobRecord | None:
        if not key:
            return None
        with self._lock:
            for record in self._records.values():
                if (
                    record.spec.idempotency_key == key
                    and record.spec.workspace_id == workspace_id
                    # 실패한 작업은 재사용하지 않는다. 다시 시도할 수 있어야 한다.
                    and record.result.status != JobStatus.FAILED
                ):
                    return record
        return None

    def list_jobs(self, workspace_id: str = "", limit: int = 50) -> list[JobRecord]:
        with self._lock:
            rows = list(self._records.values())
        if workspace_id:
            rows = [r for r in rows if r.spec.workspace_id == workspace_id]
        rows.sort(key=lambda r: r.spec.created_at, reverse=True)
        return rows[:limit]


# ── 서비스 ─────────────────────────────────────────────────

ProgressSink = Callable[[ProgressEvent], None]

# 단계별 진행률 구간. 파이프라인이 주는 0~1 을 전체 진행률로 환산한다.
_STAGE_RANGES = {
    "ingest": (0.0, 15.0),
    "transcribe": (15.0, 55.0),
    "analyze": (55.0, 70.0),
    "render": (70.0, 100.0),
}


class EngineService:
    """JobSpec 을 받아 기존 파이프라인을 돌리고 JobResult 를 돌려준다."""

    def __init__(
        self,
        store: JobStore | None = None,
        storage: Storage | None = None,
        *,
        default_work_dir: str | Path = "work",
        default_output_dir: str | Path = "output",
        run_pipeline: Callable | None = None,
    ) -> None:
        self.store = store or InMemoryJobStore()
        self.default_work_dir = Path(default_work_dir)
        self.default_output_dir = Path(default_output_dir)
        self.storage = storage or LocalStorage(self.default_output_dir)
        self._run_pipeline = run_pipeline

    # ── 번역 ───────────────────────────────────────────────
    def build_settings(self, spec: JobSpec) -> Settings:
        """JobSpec → 기존 Settings.

        경로는 spec 에 있으면 그대로 쓰고, 없으면 service 기본값을 쓴다.
        홈 디렉터리나 전역 상태에서 유추하지 않는다.
        """
        render = spec.render_options
        clips = spec.clip_options
        work_dir = Path(spec.work_dir) if spec.work_dir else self.default_work_dir
        output_dir = Path(spec.output_dir) if spec.output_dir else self.default_output_dir

        high = spec.quality_profile.value == "high"
        return Settings(
            source=spec.source,
            work_dir=work_dir,
            output_dir=output_dir,
            language=spec.language,
            min_clip_seconds=clips.min_seconds,
            max_clip_seconds=clips.max_seconds,
            min_clips=clips.min_clips,
            max_clips=clips.max_clips,
            reframe_mode=render.reframe_mode,
            width=render.width,
            height=render.height,
            fps=render.fps,
            crf=min(render.crf, 18) if high else render.crf,
            preset="slow" if high else render.preset,
            burn_subtitles=render.burn_subtitles,
            whisper_model="small" if high else "base",
            subtitle_style=SubtitleStyle(
                font_name=render.font_name, font_size=render.font_size
            ),
        )

    # ── 제출 ───────────────────────────────────────────────
    def submit(
        self,
        spec: JobSpec,
        *,
        on_progress: ProgressSink | None = None,
        execute: bool = True,
    ) -> JobResult:
        """작업을 받아 실행한다(동기).

        같은 ``idempotency_key`` 로 이미 성공한 작업이 있으면 **다시 실행하지 않고**
        그 결과를 돌려준다. 중복 클릭이나 큐 재전달이 credit 을 두 번 태우지 않게
        하기 위해서다.
        """
        existing = self.store.find_by_idempotency_key(
            spec.idempotency_key, spec.workspace_id
        )
        if existing is not None:
            LOG.info("멱등 재사용: %s ← %s", spec.job_id, existing.spec.job_id)
            reused = JobResult.from_dict(existing.result.to_dict())
            reused.job_id = spec.job_id
            reused.reused_from_job_id = existing.spec.job_id
            record = JobRecord(spec, reused)
            self.store.create(record)
            return reused

        result = JobResult(
            job_id=spec.job_id,
            status=JobStatus.QUEUED,
            idempotency_key=spec.idempotency_key,
        )
        record = JobRecord(spec, result)
        self.store.create(record)

        # 권리 게이트 — 렌더 전에 멈춘다. 실패가 아니라 승인 대기다.
        if spec.requires_rights_approval:
            result.status = JobStatus.NEEDS_APPROVAL
            result.add_warning(
                "rights_not_confirmed",
                "소스 권리가 확인되지 않았습니다. 승인 후 재개하세요.",
                stage="validate",
            )
            result.finished_at = utc_now()
            self.store.update(record)
            LOG.warning("권리 미확인으로 보류: %s", spec.job_id)
            return result

        if not execute:
            return result

        return self._execute(record, on_progress)

    # ── 실행 ───────────────────────────────────────────────
    def _execute(self, record: JobRecord, on_progress: ProgressSink | None) -> JobResult:
        spec, result = record.spec, record.result
        result.status = JobStatus.RUNNING
        result.started_at = utc_now()
        self.store.update(record)

        stage_started: dict[str, float] = {}
        last_stage: list[str] = []

        def emit(stage: str, fraction: float, message: str) -> None:
            # 단계 경계마다 취소를 확인한다(협조적 취소 지점).
            record.token.raise_if_cancelled(stage)

            low, high = _STAGE_RANGES.get(stage, (0.0, 100.0))
            percent = low + (high - low) * max(0.0, min(1.0, fraction))
            event = ProgressEvent(
                job_id=spec.job_id, stage=stage, percent=percent, message=message
            )
            record.events.append(event)
            if on_progress:
                try:
                    on_progress(event)
                except Exception as exc:       # 구독자 오류가 작업을 죽이지 않는다
                    LOG.debug("진행률 구독자 오류(무시): %s", exc)

            now = time.monotonic()
            if stage not in stage_started:
                stage_started[stage] = now
                if last_stage:
                    previous = last_stage[-1]
                    result.stage_timings.append(
                        StageTiming(stage=previous, seconds=round(now - stage_started[previous], 2))
                    )
                last_stage.append(stage)

        run_pipeline = self._run_pipeline
        if run_pipeline is None:
            from .pipeline import run_pipeline as _default

            run_pipeline = _default

        settings = self.build_settings(spec)
        started = time.monotonic()
        try:
            pipeline_result = run_pipeline(settings, on_progress=emit)
        except BaseException as exc:
            code, message = classify_error(exc)
            result.status = (
                JobStatus.CANCELLED if code is ErrorCode.CANCELLED else JobStatus.FAILED
            )
            result.error_code = code
            result.error_message = message
            result.finished_at = utc_now()
            self._close_last_stage(result, stage_started, last_stage, started)
            self.store.update(record)
            LOG.error("작업 실패 [%s] %s: %s", code.value, spec.job_id, message)
            return result

        self._close_last_stage(result, stage_started, last_stage, started)
        self._collect_outputs(record, pipeline_result)
        result.finished_at = utc_now()
        self.store.update(record)
        return result

    @staticmethod
    def _close_last_stage(result, stage_started, last_stage, started) -> None:
        if last_stage:
            stage = last_stage[-1]
            result.stage_timings.append(
                StageTiming(stage=stage, seconds=round(time.monotonic() - stage_started[stage], 2))
            )
        elif not result.stage_timings:
            result.stage_timings.append(
                StageTiming(stage="total", seconds=round(time.monotonic() - started, 2))
            )

    def _collect_outputs(self, record: JobRecord, pipeline_result: Any) -> None:
        """파이프라인 결과를 계약 형태로 옮기고 저장소에 등록한다."""
        spec, result = record.spec, record.result
        renders = list(getattr(pipeline_result, "renders", []))

        if not renders:
            result.status = JobStatus.FAILED
            result.error_code = ErrorCode.NO_CANDIDATES
            result.error_message = "생성된 클립이 없습니다."
            return

        prefix = f"{spec.workspace_id or 'local'}/{spec.project_id or spec.job_id}"
        for render in renders:
            clip = render.clip
            key = f"{prefix}/{Path(render.output_path).name}"
            try:
                stored = self.storage.put(render.output_path, key)
                uri, size = stored.uri, stored.size_bytes
            except StorageError as exc:
                result.add_warning("storage_failed", str(exc), stage="render")
                uri, size = str(render.output_path), int(getattr(render, "size_bytes", 0) or 0)

            subtitle_uri = ""
            subtitle_path = getattr(render, "subtitle_path", None)
            if subtitle_path and Path(subtitle_path).exists():
                try:
                    subtitle_uri = self.storage.put(
                        subtitle_path, f"{prefix}/{Path(subtitle_path).name}"
                    ).uri
                except StorageError:
                    subtitle_uri = str(subtitle_path)

            result.outputs.append(
                JobOutput(
                    clip_index=clip.index, title=clip.title, uri=uri,
                    start=clip.start, end=clip.end, score=clip.score,
                    reason=clip.reason, size_bytes=size, subtitle_uri=subtitle_uri,
                )
            )

        transcript_path = getattr(pipeline_result, "transcript_path", None)
        if transcript_path:
            result.transcript_uri = f"file://{transcript_path}"

        if getattr(pipeline_result, "used_offline_analysis", False):
            result.add_warning(
                "offline_highlight_analysis",
                "Gemini 키가 없어 오프라인 휴리스틱으로 구간을 선정했습니다.",
                stage="analyze",
            )

        self._add_quality_checks(result, spec)
        self._add_cost_events(result, spec, pipeline_result)
        result.status = JobStatus.SUCCEEDED

    @staticmethod
    def _add_quality_checks(result: JobResult, spec: JobSpec) -> None:
        options = spec.clip_options
        durations = [o.duration for o in result.outputs]
        outside = [d for d in durations if d < options.min_seconds - 0.5 or d > options.max_seconds + 0.5]
        result.quality_checks.append(
            QualityCheck(
                name="clip_length_in_range",
                passed=not outside,
                value=float(len(outside)),
                threshold=0.0,
                detail=f"{options.min_seconds:.0f}~{options.max_seconds:.0f}초 범위 밖 {len(outside)}개",
            )
        )
        result.quality_checks.append(
            QualityCheck(
                name="clip_count_meets_minimum",
                passed=len(result.outputs) >= options.min_clips,
                value=float(len(result.outputs)),
                threshold=float(options.min_clips),
            )
        )
        result.quality_checks.append(
            QualityCheck(
                name="vertical_output",
                passed=spec.render_options.height > spec.render_options.width,
                detail=f"{spec.render_options.width}x{spec.render_options.height}",
            )
        )

    @staticmethod
    def _add_cost_events(result: JobResult, spec: JobSpec, pipeline_result: Any) -> None:
        render_seconds = sum(o.duration for o in result.outputs)
        result.cost_events.append(
            CostEvent(kind="render", provider=spec.providers.render,
                      units=round(render_seconds, 2), unit_name="output_seconds")
        )
        result.cost_events.append(
            CostEvent(kind="storage", provider="local",
                      units=float(sum(o.size_bytes for o in result.outputs)), unit_name="bytes")
        )

    # ── 조회/취소 ──────────────────────────────────────────
    def get(self, job_id: str) -> JobResult | None:
        record = self.store.get(job_id)
        return record.result if record else None

    def get_record(self, job_id: str) -> JobRecord | None:
        return self.store.get(job_id)

    def cancel(self, job_id: str) -> JobResult | None:
        """취소를 요청한다. 이미 끝난 작업은 그대로 둔다."""
        record = self.store.get(job_id)
        if record is None:
            return None
        if record.result.is_terminal:
            LOG.info("이미 종료된 작업이라 취소하지 않습니다: %s", job_id)
            return record.result

        record.token.cancel()
        if record.result.status in (JobStatus.QUEUED, JobStatus.NEEDS_APPROVAL):
            # 아직 시작하지 않았으면 즉시 취소 상태로 확정한다.
            record.result.status = JobStatus.CANCELLED
            record.result.error_code = ErrorCode.CANCELLED
            record.result.error_message = "실행 전에 취소됐습니다."
            record.result.finished_at = utc_now()
            self.store.update(record)
        return record.result

    def approve_rights(self, job_id: str, approver: str,
                       *, on_progress: ProgressSink | None = None) -> JobResult | None:
        """권리 승인 후 작업을 재개한다."""
        record = self.store.get(job_id)
        if record is None:
            return None
        if record.result.status != JobStatus.NEEDS_APPROVAL:
            return record.result
        approved_spec = record.spec.approved(approver)
        approved_spec.job_id = record.spec.job_id
        record.spec = approved_spec
        record.result.warnings = [
            w for w in record.result.warnings if w.code != "rights_not_confirmed"
        ]
        record.result.status = JobStatus.QUEUED
        self.store.update(record)
        return self._execute(record, on_progress)

    def list_jobs(self, workspace_id: str = "", limit: int = 50) -> list[JobResult]:
        return [r.result for r in self.store.list_jobs(workspace_id, limit)]
