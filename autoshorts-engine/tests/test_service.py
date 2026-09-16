"""EngineService — 멱등성·취소·권리 게이트·오류 전파 테스트.

파이프라인은 주입해 대체한다. 서비스 계층의 책임만 검증한다.
"""

from __future__ import annotations

import threading

import pytest

from autoshorts.ai_analyzer import AnalysisError
from autoshorts.contracts import ErrorCode, JobSpec, JobStatus
from autoshorts.downloader import IngestError
from autoshorts.models import Clip
from autoshorts.pipeline import PipelineResult
from autoshorts.service import (
    STAGE_IDEMPOTENCY,
    CancellationToken,
    EngineService,
    InMemoryJobStore,
    JobCancelled,
    classify_error,
)
from autoshorts.storage import LocalStorage
from autoshorts.transcriber import TranscriptionError
from autoshorts.video_renderer import RenderError


def make_render(tmp_path, index=1, title="클립", start=0.0, end=40.0):
    path = tmp_path / f"output_{index:02d}_{title}.mp4"
    path.write_bytes(b"video-bytes")
    return type("R", (), {
        "clip": Clip(start=start, end=end, title=title, reason="이유", score=80, index=index),
        "output_path": path,
        "size_bytes": path.stat().st_size,
        "subtitle_path": None,
    })()


@pytest.fixture
def service(tmp_path):
    return EngineService(
        store=InMemoryJobStore(),
        storage=LocalStorage(tmp_path / "storage"),
        default_work_dir=tmp_path / "work",
        default_output_dir=tmp_path / "out",
    )


@pytest.fixture
def ok_pipeline(tmp_path):
    def run(settings, on_progress=None, **kwargs):
        for stage, fraction in (("ingest", 1.0), ("transcribe", 1.0), ("analyze", 1.0), ("render", 1.0)):
            if on_progress:
                on_progress(stage, fraction, f"{stage} 완료")
        return PipelineResult(source=settings.source, title="원본",
                              renders=[make_render(tmp_path, 1), make_render(tmp_path, 2)])
    return run


def owned(**kwargs):
    defaults = dict(source="a.mp4", workspace_id="w1", rights_status="owned")
    defaults.update(kwargs)
    return JobSpec(**defaults)


class TestSettingsTranslation:
    def test_maps_options(self, service):
        spec = owned(language="ko",
                     clip_options={"min_seconds": 20, "max_seconds": 45, "max_clips": 4},
                     render_options={"reframe_mode": "crop", "crf": 22})
        settings = service.build_settings(spec)
        assert settings.language == "ko"
        assert settings.min_clip_seconds == 20
        assert settings.max_clips == 4
        assert settings.reframe_mode == "crop"

    def test_high_profile_raises_quality(self, service):
        standard = service.build_settings(owned(quality_profile="standard"))
        high = service.build_settings(owned(quality_profile="high"))
        assert high.crf <= standard.crf
        assert high.whisper_model == "small"

    def test_paths_are_injected_not_inferred(self, service, tmp_path):
        spec = owned(work_dir=str(tmp_path / "custom-work"),
                     output_dir=str(tmp_path / "custom-out"))
        settings = service.build_settings(spec)
        assert settings.work_dir == tmp_path / "custom-work"
        assert settings.output_dir == tmp_path / "custom-out"

    def test_falls_back_to_service_defaults(self, service, tmp_path):
        settings = service.build_settings(owned())
        assert settings.work_dir == tmp_path / "work"


class TestSuccessPath:
    def test_succeeds_and_collects_outputs(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        result = service.submit(owned())
        assert result.status is JobStatus.SUCCEEDED
        assert len(result.outputs) == 2
        assert result.outputs[0].uri.startswith("file://")
        assert result.outputs[0].duration == 40.0

    def test_records_stage_timings(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        result = service.submit(owned())
        assert [t.stage for t in result.stage_timings] == ["ingest", "transcribe", "analyze", "render"]
        assert result.total_seconds >= 0

    def test_emits_progress_events(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        events = []
        service.submit(owned(), on_progress=events.append)
        assert [e.stage for e in events] == ["ingest", "transcribe", "analyze", "render"]
        assert all(0 <= e.percent <= 100 for e in events)
        assert events[-1].percent == 100.0

    def test_progress_subscriber_error_does_not_kill_job(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        def boom(event):
            raise RuntimeError("구독자 폭발")
        assert service.submit(owned(), on_progress=boom).status is JobStatus.SUCCEEDED

    def test_adds_quality_checks(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        names = {q.name for q in service.submit(owned()).quality_checks}
        assert {"clip_length_in_range", "clip_count_meets_minimum", "vertical_output"} <= names

    def test_adds_cost_events(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        kinds = {c.kind for c in service.submit(owned()).cost_events}
        assert "render" in kinds and "storage" in kinds

    def test_offline_analysis_is_warned(self, service, tmp_path):
        def run(settings, on_progress=None, **kwargs):
            return PipelineResult(source="a", renders=[make_render(tmp_path)],
                                  used_offline_analysis=True)
        service._run_pipeline = run
        codes = {w.code for w in service.submit(owned()).warnings}
        assert "offline_highlight_analysis" in codes


class TestRightsGate:
    def test_unverified_stops_before_render(self, service):
        service._run_pipeline = lambda *a, **k: pytest.fail("권리 확인 전에 렌더하면 안 된다")
        result = service.submit(JobSpec(source="a.mp4", workspace_id="w1"))
        assert result.status is JobStatus.NEEDS_APPROVAL
        assert result.outputs == []
        assert any(w.code == "rights_not_confirmed" for w in result.warnings)

    def test_needs_approval_is_not_terminal(self, service):
        result = service.submit(JobSpec(source="a.mp4"))
        assert result.is_terminal is False        # 승인하면 재개할 수 있다

    def test_approval_resumes_job(self, service, ok_pipeline):
        result = service.submit(JobSpec(source="a.mp4", workspace_id="w1"))
        assert result.status is JobStatus.NEEDS_APPROVAL
        service._run_pipeline = ok_pipeline
        resumed = service.approve_rights(result.job_id, "user:42")
        assert resumed.status is JobStatus.SUCCEEDED
        assert not any(w.code == "rights_not_confirmed" for w in resumed.warnings)

    def test_approval_of_unknown_job(self, service):
        assert service.approve_rights("nope", "user:1") is None

    def test_pre_approved_spec_runs_immediately(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        spec = JobSpec(source="a.mp4", workspace_id="w1").approved("user:9")
        assert service.submit(spec).status is JobStatus.SUCCEEDED


class TestIdempotency:
    def test_same_spec_is_not_rerun(self, service, tmp_path):
        calls = {"n": 0}

        def counting(settings, on_progress=None, **kwargs):
            calls["n"] += 1
            return PipelineResult(source="a", renders=[make_render(tmp_path)])

        service._run_pipeline = counting
        first = service.submit(owned())
        second = service.submit(owned())
        assert calls["n"] == 1                       # 두 번째는 실행하지 않는다
        assert second.reused_from_job_id == first.job_id
        assert second.job_id != first.job_id
        assert second.status is JobStatus.SUCCEEDED

    def test_different_options_rerun(self, service, tmp_path):
        calls = {"n": 0}

        def counting(settings, on_progress=None, **kwargs):
            calls["n"] += 1
            return PipelineResult(source="a", renders=[make_render(tmp_path)])

        service._run_pipeline = counting
        service.submit(owned())
        service.submit(owned(render_options={"reframe_mode": "crop"}))
        assert calls["n"] == 2

    def test_other_workspace_is_isolated(self, service, tmp_path):
        calls = {"n": 0}

        def counting(settings, on_progress=None, **kwargs):
            calls["n"] += 1
            return PipelineResult(source="a", renders=[make_render(tmp_path)])

        service._run_pipeline = counting
        service.submit(owned(workspace_id="w1"))
        service.submit(owned(workspace_id="w2"))
        assert calls["n"] == 2                       # 워크스페이스가 다르면 공유하지 않는다

    def test_failed_job_is_retryable(self, service, tmp_path):
        """실패한 작업을 멱등 재사용하면 영영 재시도할 수 없게 된다."""
        calls = {"n": 0}

        def flaky(settings, on_progress=None, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RenderError("ffmpeg died")
            return PipelineResult(source="a", renders=[make_render(tmp_path)])

        service._run_pipeline = flaky
        first = service.submit(owned())
        assert first.status is JobStatus.FAILED
        second = service.submit(owned())
        assert calls["n"] == 2
        assert second.status is JobStatus.SUCCEEDED


class TestCancellation:
    def test_token_is_thread_safe(self):
        token = CancellationToken()
        assert token.cancelled is False
        threading.Thread(target=token.cancel).start()
        for _ in range(100):
            if token.cancelled:
                break
        assert token.cancelled is True

    def test_raises_at_checkpoint(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(JobCancelled, match="render"):
            token.raise_if_cancelled("render")

    def test_cancel_before_start(self, service, ok_pipeline):
        result = service.submit(owned(), execute=False)
        cancelled = service.cancel(result.job_id)
        assert cancelled.status is JobStatus.CANCELLED
        assert cancelled.error_code is ErrorCode.CANCELLED

    def test_cancel_during_run_stops_at_stage_boundary(self, service, tmp_path):
        """취소는 강제 종료가 아니라 단계 경계에서 협조적으로 멈춘다."""
        job_id_holder = {}

        def slow(settings, on_progress=None, **kwargs):
            on_progress("ingest", 1.0, "")
            service.cancel(job_id_holder["id"])     # 진행 중 취소 요청
            on_progress("transcribe", 1.0, "")      # 여기서 멈춰야 한다
            pytest.fail("취소 후에도 계속 진행됐다")

        service._run_pipeline = slow
        spec = owned()
        job_id_holder["id"] = spec.job_id
        result = service.submit(spec)
        assert result.status is JobStatus.CANCELLED
        assert result.error_code is ErrorCode.CANCELLED

    def test_cancel_finished_job_is_noop(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        result = service.submit(owned())
        assert service.cancel(result.job_id).status is JobStatus.SUCCEEDED

    def test_cancel_unknown_job(self, service):
        assert service.cancel("nope") is None


class TestErrorPropagation:
    @pytest.mark.parametrize(("exc", "code", "retryable"), [
        (IngestError("파일을 찾을 수 없습니다: x"), ErrorCode.SOURCE_NOT_FOUND, False),
        (IngestError("지원하지 않는 형식입니다"), ErrorCode.UNSUPPORTED_FORMAT, False),
        (TranscriptionError("텍스트를 추출하지 못했습니다"), ErrorCode.NO_SPEECH_DETECTED, False),
        (TranscriptionError("모델 로드 실패"), ErrorCode.PROVIDER_UNAVAILABLE, True),
        (AnalysisError("클립 없음"), ErrorCode.NO_CANDIDATES, False),
        (RenderError("ffmpeg 실패"), ErrorCode.RENDER_FAILED, True),
        (TimeoutError("시간 초과"), ErrorCode.TIMEOUT, True),
        (ValueError("잘못된 입력"), ErrorCode.INVALID_INPUT, False),
        (RuntimeError("알 수 없음"), ErrorCode.INTERNAL_ERROR, False),
    ])
    def test_classification(self, exc, code, retryable):
        got, _ = classify_error(exc)
        assert got is code
        from autoshorts.contracts import RETRYABLE_ERRORS
        assert (got in RETRYABLE_ERRORS) is retryable

    def test_failure_is_recorded_not_raised(self, service):
        service._run_pipeline = lambda *a, **k: (_ for _ in ()).throw(RenderError("boom"))
        result = service.submit(owned())
        assert result.status is JobStatus.FAILED
        assert result.error_code is ErrorCode.RENDER_FAILED
        assert result.is_retryable is True
        assert result.finished_at

    def test_no_renders_is_failure(self, service):
        service._run_pipeline = lambda *a, **k: PipelineResult(source="a", renders=[])
        result = service.submit(owned())
        assert result.status is JobStatus.FAILED
        assert result.error_code is ErrorCode.NO_CANDIDATES


class TestStoreAndLookup:
    def test_get_returns_result(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        job_id = service.submit(owned()).job_id
        assert service.get(job_id).status is JobStatus.SUCCEEDED

    def test_get_unknown(self, service):
        assert service.get("nope") is None

    def test_list_filters_by_workspace(self, service, ok_pipeline):
        service._run_pipeline = ok_pipeline
        service.submit(owned(workspace_id="w1"))
        service.submit(owned(workspace_id="w2", source="b.mp4"))
        assert len(service.list_jobs("w1")) == 1
        assert len(service.list_jobs()) == 2

    def test_stage_idempotency_is_declared(self):
        assert set(STAGE_IDEMPOTENCY) == {"ingest", "transcribe", "analyze", "render"}
        assert STAGE_IDEMPOTENCY["analyze"] == "recompute"
