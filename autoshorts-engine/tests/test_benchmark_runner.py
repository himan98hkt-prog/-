"""벤치마크 실행기 — 파이프라인을 가짜로 주입해 계측 동작만 검증한다."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoshorts.benchmark import BenchmarkSample, GoldMoment, SampleManifest
from autoshorts.benchmark_runner import run_manifest, run_sample
from autoshorts.config import Settings
from autoshorts.models import Clip, Segment, Transcript
from autoshorts.pipeline import PipelineResult


@pytest.fixture
def settings(tmp_path):
    return Settings(source="", work_dir=tmp_path / "work", output_dir=tmp_path / "out")


@pytest.fixture
def transcript_file(tmp_path):
    transcript = Transcript(
        segments=[
            Segment(0.0, 20.0, "첫 문장입니다 여기에 핵심이 있습니다"),
            Segment(20.5, 45.0, "두 번째 문장으로 이어집니다"),
        ],
        duration=45.0,
    )
    path = tmp_path / "transcription.json"
    transcript.save(path)
    return path


def owned_sample(**kwargs):
    defaults = dict(sample_id="s1", source="a.mp4", content_mode="podcast",
                    rights_status="owned", duration_seconds=600)
    defaults.update(kwargs)
    return BenchmarkSample(**defaults)


def fake_result(tmp_path, transcript_file, clip_count=2):
    renders = []
    for index in range(1, clip_count + 1):
        path = tmp_path / f"out_{index}.mp4"
        path.write_bytes(b"x" * 1024)
        renders.append(type("R", (), {"output_path": path, "size_bytes": 1024})())
    return PipelineResult(
        source="a.mp4", title="샘플",
        transcript_path=transcript_file,
        clips=[Clip(start=0.0, end=20.0, title="t", index=i) for i in range(1, clip_count + 1)],
        renders=renders,
    )


class TestRunSample:
    def test_records_success_and_outputs(self, settings, tmp_path, transcript_file):
        record = run_sample(
            owned_sample(), settings,
            run_pipeline=lambda s, **k: fake_result(tmp_path, transcript_file, 2),
        )
        assert record.succeeded is True
        assert record.output_count == 2
        assert record.output_bytes == 2048
        assert record.peak_memory_mb > 0
        assert record.total_seconds >= 0

    def test_computes_quality_from_transcript(self, settings, tmp_path, transcript_file):
        sample = owned_sample(gold_moments=[GoldMoment(0, 20)])
        record = run_sample(
            sample, settings,
            run_pipeline=lambda s, **k: fake_result(tmp_path, transcript_file, 1),
        )
        assert record.quality is not None
        assert record.quality.clip_count == 1
        assert record.quality.gold_acceptance == 1.0

    def test_skips_unverified_rights(self, settings):
        """권리 미확인 소스는 벤치마크에서도 처리하지 않는다."""
        record = run_sample(
            owned_sample(rights_status="unverified"), settings,
            run_pipeline=lambda s, **k: pytest.fail("권리 확인 전에 처리하면 안 된다"),
        )
        assert record.succeeded is False
        assert "rights_status=unverified" in record.error

    def test_pipeline_exception_is_recorded_not_raised(self, settings):
        def boom(s, **k):
            raise RuntimeError("ffmpeg died")

        record = run_sample(owned_sample(), settings, run_pipeline=boom)
        assert record.succeeded is False
        assert "RuntimeError: ffmpeg died" in record.error
        assert record.peak_memory_mb > 0        # 실패해도 계측은 남는다

    def test_no_renders_is_failure(self, settings, transcript_file):
        record = run_sample(
            owned_sample(), settings,
            run_pipeline=lambda s, **k: PipelineResult(source="a", renders=[]),
        )
        assert record.succeeded is False
        assert "생성된 쇼츠가 없습니다" in record.error

    def test_source_seconds_backfilled_from_transcript(self, settings, tmp_path, transcript_file):
        record = run_sample(
            owned_sample(duration_seconds=0), settings,
            run_pipeline=lambda s, **k: fake_result(tmp_path, transcript_file, 1),
        )
        assert record.source_seconds == 45.0

    def test_stage_timings_captured_from_progress(self, settings, tmp_path, transcript_file):
        def with_progress(s, on_progress=None, **k):
            for stage in ("ingest", "transcribe", "analyze", "render"):
                if on_progress:
                    on_progress(stage, 0.5, "")
            return fake_result(tmp_path, transcript_file, 1)

        record = run_sample(owned_sample(), settings, run_pipeline=with_progress)
        assert [t.stage for t in record.stage_timings] == ["ingest", "transcribe", "analyze", "render"]


class TestRunManifest:
    def test_runs_every_sample_and_reports(self, settings, tmp_path, transcript_file):
        manifest = SampleManifest(name="set", samples=[
            owned_sample(sample_id="a", gold_moments=[GoldMoment(0, 20)]),
            owned_sample(sample_id="b", gold_moments=[GoldMoment(0, 20)]),
        ])
        report = run_manifest(
            manifest, settings, output_dir=tmp_path / "report",
            run_pipeline=lambda s, **k: fake_result(tmp_path, transcript_file, 1),
        )
        assert len(report.runs) == 2
        assert report.render_success_rate == 1.0
        assert (tmp_path / "report" / "benchmark_report.json").exists()
        assert (tmp_path / "report" / "benchmark_report.md").exists()

    def test_mixed_success_reflected(self, settings, tmp_path, transcript_file):
        calls = {"n": 0}

        def flaky(s, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("fail")
            return fake_result(tmp_path, transcript_file, 1)

        manifest = SampleManifest(samples=[
            owned_sample(sample_id="a", gold_moments=[GoldMoment(0, 20)]),
            owned_sample(sample_id="b", gold_moments=[GoldMoment(0, 20)]),
        ])
        report = run_manifest(manifest, settings, run_pipeline=flaky)
        assert report.render_success_rate == 0.5

    def test_records_engine_version(self, settings, tmp_path, transcript_file):
        from autoshorts import __version__

        report = run_manifest(
            SampleManifest(samples=[owned_sample(gold_moments=[GoldMoment(0, 20)])]),
            settings, run_pipeline=lambda s, **k: fake_result(tmp_path, transcript_file, 1),
        )
        assert report.engine_version == __version__
        assert report.baseline_label == "transcript-only"
