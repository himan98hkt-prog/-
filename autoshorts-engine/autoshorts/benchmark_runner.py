"""벤치마크 실행기 — 기존 파이프라인을 샘플 매니페스트에 돌려 기준선을 만든다.

기존 :func:`autoshorts.pipeline.run_pipeline` 을 그대로 호출한다. 파이프라인을
고쳐 쓰지 않고 바깥에서 계측만 한다.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from . import pipeline
from .benchmark import (
    BenchmarkReport,
    BenchmarkSample,
    RunRecord,
    SampleManifest,
    StageTiming,
    measure_quality,
    peak_memory_mb,
)
from .config import Settings
from .utils import ensure_dir, get_logger

__all__ = ["run_sample", "run_manifest"]

LOG = get_logger("benchmark.runner")


def run_sample(
    sample: BenchmarkSample,
    settings: Settings,
    *,
    run_pipeline: Callable = None,
) -> RunRecord:
    """샘플 한 편을 처리하고 성능·품질을 기록한다.

    파이프라인이 실패해도 예외를 밖으로 내지 않는다. 실패 자체가 측정 대상이다.
    """
    run_pipeline = run_pipeline or pipeline.run_pipeline
    record = RunRecord(
        sample_id=sample.sample_id,
        content_mode=sample.content_mode,
        source_seconds=sample.duration_seconds,
    )

    # 권리 미확인 소스는 기록만 남기고 건너뛴다. 벤치마크라도 예외가 아니다.
    if sample.needs_rights_confirmation:
        record.error = "rights_status=unverified — 권리 확인 전에는 처리하지 않습니다."
        LOG.warning("%s 건너뜀: %s", sample.sample_id, record.error)
        return record

    timings: list[StageTiming] = []
    stage_marks: dict[str, float] = {}
    started = time.monotonic()

    def on_progress(stage: str, fraction: float, message: str) -> None:
        # 단계가 바뀌는 순간을 잡아 구간 소요를 누적한다.
        now = time.monotonic()
        if stage not in stage_marks:
            stage_marks[stage] = now

    settings.source = sample.source
    try:
        result = run_pipeline(settings, on_progress=on_progress)
    except Exception as exc:
        record.total_seconds = time.monotonic() - started
        record.peak_memory_mb = peak_memory_mb()
        record.error = f"{type(exc).__name__}: {exc}"
        LOG.error("%s 실패: %s", sample.sample_id, record.error)
        return record

    record.total_seconds = time.monotonic() - started
    record.peak_memory_mb = peak_memory_mb()

    # 단계 경계 시각으로 구간 소요를 복원한다.
    ordered = sorted(stage_marks.items(), key=lambda kv: kv[1])
    for index, (stage, mark) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else started + record.total_seconds
        timings.append(StageTiming(stage=stage, seconds=round(end - mark, 2)))
    record.stage_timings = timings

    renders = list(getattr(result, "renders", []))
    record.output_count = len(renders)
    record.output_bytes = sum(int(getattr(r, "size_bytes", 0) or 0) for r in renders)
    record.succeeded = bool(renders)
    if not renders:
        record.error = record.error or "생성된 쇼츠가 없습니다."

    transcript_path = getattr(result, "transcript_path", None)
    clips = list(getattr(result, "clips", []))
    if clips and transcript_path and Path(transcript_path).exists():
        from .models import Transcript

        transcript = Transcript.load(transcript_path)
        record.quality = measure_quality(
            clips,
            transcript,
            sample.gold_moments,
            min_seconds=settings.min_clip_seconds,
            max_seconds=settings.max_clip_seconds,
        )
        if not record.source_seconds:
            record.source_seconds = transcript.duration
    return record


def run_manifest(
    manifest: SampleManifest,
    settings: Settings,
    *,
    output_dir: str | Path | None = None,
    run_pipeline: Callable = None,
    baseline_label: str = "transcript-only",
) -> BenchmarkReport:
    """매니페스트 전체를 실행하고 보고서를 만든다."""
    from . import __version__

    problems = manifest.validate()
    for problem in problems:
        LOG.warning("매니페스트 경고: %s", problem)

    report = BenchmarkReport(
        manifest_name=manifest.name,
        engine_version=__version__,
        baseline_label=baseline_label,
    )
    for index, sample in enumerate(manifest.samples, start=1):
        LOG.info("[%d/%d] %s (%s)", index, len(manifest), sample.sample_id, sample.content_mode)
        report.runs.append(run_sample(sample, settings, run_pipeline=run_pipeline))

    if output_dir:
        destination = ensure_dir(output_dir)
        report.save(destination / "benchmark_report.json")
        (destination / "benchmark_report.md").write_text(
            report.to_markdown(), encoding="utf-8"
        )
        LOG.info("보고서 저장: %s", destination)
    return report
