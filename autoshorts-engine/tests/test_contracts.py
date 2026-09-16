"""JobSpec/JobResult/ProgressEvent 계약 테스트."""

from __future__ import annotations

import json

import pytest

from autoshorts.contracts import (
    RETRYABLE_ERRORS,
    ClipOptions,
    ContentMode,
    CostEvent,
    ErrorCode,
    JobOutput,
    JobResult,
    JobSpec,
    JobStatus,
    ProgressEvent,
    ProviderSettings,
    QualityCheck,
    QualityProfile,
    RenderOptions,
    RightsStatus,
    StageTiming,
)


class TestJobSpecBasics:
    def test_requires_source(self):
        with pytest.raises(ValueError, match="source"):
            JobSpec(source="  ")

    def test_generates_job_id(self):
        assert JobSpec(source="a.mp4").job_id.startswith("job_")

    def test_ids_are_unique(self):
        assert JobSpec(source="a.mp4").job_id != JobSpec(source="a.mp4").job_id

    def test_accepts_string_enums(self):
        spec = JobSpec(source="a.mp4", content_mode="podcast",
                       rights_status="owned", quality_profile="high")
        assert spec.content_mode is ContentMode.PODCAST
        assert spec.rights_status is RightsStatus.OWNED
        assert spec.quality_profile is QualityProfile.HIGH

    @pytest.mark.parametrize(("field", "value"), [
        ("content_mode", "asmr"), ("rights_status", "probably_ok"), ("quality_profile", "ultra"),
    ])
    def test_rejects_unknown_enum(self, field, value):
        with pytest.raises(ValueError, match=field):
            JobSpec(source="a.mp4", **{field: value})

    def test_json_roundtrip(self):
        spec = JobSpec(source="a.mp4", workspace_id="w1", project_id="p1",
                       content_mode="lecture", language="ko")
        restored = JobSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
        assert restored.to_dict() == spec.to_dict()

    def test_nested_dicts_are_coerced(self):
        spec = JobSpec(source="a.mp4", clip_options={"min_seconds": 20, "max_seconds": 40},
                       render_options={"reframe_mode": "crop"})
        assert spec.clip_options.min_seconds == 20
        assert spec.render_options.reframe_mode == "crop"


class TestRightsGate:
    def test_default_is_unverified(self):
        assert JobSpec(source="a.mp4").rights_status is RightsStatus.UNVERIFIED

    def test_unverified_requires_approval(self):
        assert JobSpec(source="a.mp4").requires_rights_approval is True

    @pytest.mark.parametrize("status", ["owned", "licensed", "creative_commons"])
    def test_confirmed_rights_need_no_approval(self, status):
        assert JobSpec(source="a.mp4", rights_status=status).requires_rights_approval is False

    def test_approval_records_approver_without_mutating(self):
        original = JobSpec(source="a.mp4")
        approved = original.approved("user:42")
        assert approved.rights_approved_by == "user:42"
        assert approved.requires_rights_approval is False
        assert original.rights_approved_by == ""      # 원본 불변

    def test_approval_needs_identity(self):
        with pytest.raises(ValueError, match="승인자"):
            JobSpec(source="a.mp4").approved("")


class TestIdempotencyKey:
    def test_same_inputs_same_key(self):
        a = JobSpec(source="a.mp4", workspace_id="w1")
        b = JobSpec(source="a.mp4", workspace_id="w1")
        assert a.idempotency_key == b.idempotency_key
        assert a.job_id != b.job_id                   # 작업 id 는 달라도

    def test_different_source_differs(self):
        assert (JobSpec(source="a.mp4").idempotency_key
                != JobSpec(source="b.mp4").idempotency_key)

    def test_different_render_options_differ(self):
        a = JobSpec(source="a.mp4", render_options={"reframe_mode": "blur"})
        b = JobSpec(source="a.mp4", render_options={"reframe_mode": "crop"})
        assert a.idempotency_key != b.idempotency_key

    def test_workspace_isolation(self):
        assert (JobSpec(source="a.mp4", workspace_id="w1").idempotency_key
                != JobSpec(source="a.mp4", workspace_id="w2").idempotency_key)

    def test_explicit_key_wins(self):
        assert JobSpec(source="a.mp4", idempotency_key="custom").idempotency_key == "custom"

    def test_rights_status_does_not_change_key(self):
        """권리 승인은 결과물을 바꾸지 않으므로 키에 포함하지 않는다."""
        a = JobSpec(source="a.mp4", rights_status="owned")
        b = JobSpec(source="a.mp4", rights_status="licensed")
        assert a.idempotency_key == b.idempotency_key


class TestProviderSettings:
    def test_defaults(self):
        settings = ProviderSettings()
        assert settings.transcription == "faster-whisper"
        assert settings.credentials_ref is None

    def test_rejects_embedded_api_key(self):
        """JobSpec 은 큐·DB·로그를 지나므로 비밀값이 들어가면 안 된다."""
        with pytest.raises(ValueError, match="비밀값"):
            ProviderSettings(model_overrides={"gemini": "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345"})

    def test_allows_plain_model_names(self):
        assert ProviderSettings(model_overrides={"gemini": "gemini-2.0-flash"})


class TestOptionValidation:
    def test_clip_options_reject_inverted_range(self):
        with pytest.raises(ValueError, match="max_seconds"):
            ClipOptions(min_seconds=60, max_seconds=30)

    def test_clip_options_reject_inverted_counts(self):
        with pytest.raises(ValueError, match="max_clips"):
            ClipOptions(min_clips=9, max_clips=2)

    def test_render_options_reject_unknown_mode(self):
        with pytest.raises(ValueError, match="reframe_mode"):
            RenderOptions(reframe_mode="zoom")

    def test_render_options_reject_bad_size(self):
        with pytest.raises(ValueError, match="양수"):
            RenderOptions(width=0)


class TestJobResult:
    def test_default_is_queued(self):
        assert JobResult(job_id="j1").status is JobStatus.QUEUED

    def test_terminal_detection(self):
        for status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
            assert JobResult(job_id="j", status=status).is_terminal
        for status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.NEEDS_APPROVAL):
            assert not JobResult(job_id="j", status=status).is_terminal

    @pytest.mark.parametrize("code", sorted(RETRYABLE_ERRORS, key=lambda c: c.value))
    def test_retryable_errors(self, code):
        assert JobResult(job_id="j", error_code=code).is_retryable

    @pytest.mark.parametrize("code", [
        ErrorCode.INVALID_INPUT, ErrorCode.SOURCE_NOT_FOUND,
        ErrorCode.RIGHTS_NOT_CONFIRMED, ErrorCode.CANCELLED, ErrorCode.NO_SPEECH_DETECTED,
    ])
    def test_non_retryable_errors(self, code):
        assert not JobResult(job_id="j", error_code=code).is_retryable

    def test_no_error_is_not_retryable(self):
        assert not JobResult(job_id="j").is_retryable

    def test_total_seconds_sums_stages(self):
        result = JobResult(job_id="j", stage_timings=[
            StageTiming("ingest", 2.0), StageTiming("render", 10.5),
        ])
        assert result.total_seconds == 12.5

    def test_add_warning(self):
        result = JobResult(job_id="j")
        result.add_warning("code", "메시지", stage="analyze")
        assert result.warnings[0].stage == "analyze"

    def test_json_roundtrip(self):
        result = JobResult(
            job_id="j1", status=JobStatus.SUCCEEDED,
            outputs=[JobOutput(clip_index=1, title="t", uri="file:///a.mp4", start=0, end=40)],
            stage_timings=[StageTiming("render", 5.0)],
            quality_checks=[QualityCheck(name="q", passed=True)],
            cost_events=[CostEvent(kind="render", units=40)],
        )
        restored = JobResult.from_dict(json.loads(json.dumps(result.to_dict())))
        assert restored.status is JobStatus.SUCCEEDED
        assert restored.outputs[0].duration == 40.0
        assert restored.quality_checks[0].passed is True

    def test_dict_exposes_retryable(self):
        data = JobResult(job_id="j", error_code=ErrorCode.TIMEOUT).to_dict()
        assert data["is_retryable"] is True
        assert data["error_code"] == "timeout"


class TestProgressEvent:
    def test_percent_clamped(self):
        assert ProgressEvent(job_id="j", stage="s", percent=150).percent == 100.0
        assert ProgressEvent(job_id="j", stage="s", percent=-5).percent == 0.0

    def test_has_timestamp(self):
        assert ProgressEvent(job_id="j", stage="s").timestamp

    def test_json_roundtrip(self):
        event = ProgressEvent(job_id="j", stage="render", percent=42.5, message="m")
        restored = ProgressEvent.from_dict(json.loads(json.dumps(event.to_dict())))
        assert restored.percent == 42.5 and restored.stage == "render"
