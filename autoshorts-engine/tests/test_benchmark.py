"""벤치마크 매니페스트·품질 지표·실행기 테스트 (FFmpeg·네트워크 불필요)."""

from __future__ import annotations

import json

import pytest

from autoshorts.benchmark import (
    CONTENT_MODES,
    RIGHTS_STATUSES,
    BenchmarkReport,
    BenchmarkSample,
    GoldMoment,
    QualityMetrics,
    RunRecord,
    SampleManifest,
    StageTiming,
    context_dependency_flags,
    duplicate_overlap_rate,
    gold_acceptance,
    measure_quality,
    mid_sentence_cut_rate,
    peak_memory_mb,
    track_stage,
)
from autoshorts.models import Clip, Segment, Transcript


def clip(start, end, index=1, title="제목"):
    return Clip(start=start, end=end, title=title, index=index)


@pytest.fixture
def simple_transcript():
    """0~40초, 발화 경계가 명확한 전사본."""
    return Transcript(
        segments=[
            Segment(0.0, 12.0, "첫 번째 문장입니다 아주 중요한 내용이 있습니다"),
            Segment(12.5, 26.0, "두 번째 문장은 조금 더 길게 이어집니다"),
            Segment(26.5, 40.0, "마지막 문장으로 정리하겠습니다"),
        ],
        duration=40.0,
    )


class TestSampleSchema:
    def test_valid_sample(self):
        sample = BenchmarkSample(sample_id="s1", source="a.mp4", content_mode="podcast",
                                 rights_status="owned", duration_seconds=600)
        assert sample.content_mode == "podcast"
        assert sample.needs_rights_confirmation is False

    def test_unverified_rights_needs_confirmation(self):
        sample = BenchmarkSample(sample_id="s1", source="a.mp4")
        assert sample.rights_status == "unverified"       # 안전한 기본값
        assert sample.needs_rights_confirmation is True

    @pytest.mark.parametrize("mode", CONTENT_MODES)
    def test_all_declared_modes_accepted(self, mode):
        assert BenchmarkSample(sample_id="s", source="a", content_mode=mode).content_mode == mode

    @pytest.mark.parametrize("status", RIGHTS_STATUSES)
    def test_all_declared_rights_accepted(self, status):
        assert BenchmarkSample(sample_id="s", source="a", rights_status=status)

    def test_rejects_unknown_mode(self):
        with pytest.raises(ValueError, match="content_mode"):
            BenchmarkSample(sample_id="s", source="a", content_mode="asmr")

    def test_rejects_unknown_rights(self):
        with pytest.raises(ValueError, match="rights_status"):
            BenchmarkSample(sample_id="s", source="a", rights_status="probably_fine")

    def test_rejects_blank_id(self):
        with pytest.raises(ValueError, match="sample_id"):
            BenchmarkSample(sample_id="  ", source="a")

    def test_gold_moment_normalises(self):
        gold = GoldMoment(start=-5, end=-1)
        assert gold.start == 0.0 and gold.end >= gold.start


class TestManifest:
    def _manifest(self):
        return SampleManifest(
            name="test-set",
            samples=[
                BenchmarkSample(sample_id="p1", source="a.mp4", content_mode="podcast",
                                rights_status="owned", duration_seconds=600,
                                gold_moments=[GoldMoment(10, 50)]),
                BenchmarkSample(sample_id="l1", source="b.mp4", content_mode="lecture",
                                rights_status="owned", duration_seconds=1200,
                                gold_moments=[GoldMoment(100, 150)]),
            ],
        )

    def test_roundtrip(self, tmp_path):
        path = self._manifest().save(tmp_path / "m.json")
        loaded = SampleManifest.load(path)
        assert len(loaded) == 2
        assert loaded.samples[0].gold_moments[0].end == 50

    def test_json_is_human_editable(self, tmp_path):
        path = self._manifest().save(tmp_path / "m.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["samples"][0]["sample_id"] == "p1"
        assert "gold_moments" in data["samples"][0]

    def test_mode_distribution(self):
        assert self._manifest().mode_distribution() == {"podcast": 1, "lecture": 1}

    def test_by_mode(self):
        assert len(self._manifest().by_mode("podcast")) == 1

    def test_validate_flags_missing_gold(self):
        manifest = SampleManifest(samples=[BenchmarkSample(sample_id="x", source="a")])
        assert any("gold_moment" in p for p in manifest.validate())

    def test_validate_flags_duplicate_ids(self):
        manifest = SampleManifest(samples=[
            BenchmarkSample(sample_id="x", source="a", gold_moments=[GoldMoment(0, 5)]),
            BenchmarkSample(sample_id="x", source="b", gold_moments=[GoldMoment(0, 5)]),
        ])
        assert any("중복" in p for p in manifest.validate())

    def test_validate_flags_gold_beyond_duration(self):
        manifest = SampleManifest(samples=[
            BenchmarkSample(sample_id="x", source="a", duration_seconds=60,
                            gold_moments=[GoldMoment(10, 500)]),
        ])
        assert any("영상 길이" in p for p in manifest.validate())

    def test_validate_returns_empty_when_clean(self):
        assert self._manifest().validate() == []


class TestMidSentenceCut:
    def test_clean_boundaries_score_zero(self, simple_transcript):
        clips = [clip(0.0, 26.0)]          # 문장 시작과 문장 끝에 정확히 맞음
        assert mid_sentence_cut_rate(clips, simple_transcript) == 0.0

    def test_cut_inside_sentence_is_flagged(self, simple_transcript):
        clips = [clip(5.0, 20.0)]          # 양쪽 다 문장 한가운데
        assert mid_sentence_cut_rate(clips, simple_transcript) == 1.0

    def test_one_bad_boundary_counts(self, simple_transcript):
        clips = [clip(0.0, 20.0)]          # 시작은 맞고 끝이 틀림
        assert mid_sentence_cut_rate(clips, simple_transcript) == 1.0

    def test_tolerance_allows_snap_slack(self, simple_transcript):
        clips = [clip(0.3, 25.7)]          # 0.6초 허용치 안
        assert mid_sentence_cut_rate(clips, simple_transcript) == 0.0

    def test_partial_rate(self, simple_transcript):
        clips = [clip(0.0, 12.0, 1), clip(5.0, 20.0, 2)]
        assert mid_sentence_cut_rate(clips, simple_transcript) == 0.5

    def test_empty_inputs_are_zero(self, simple_transcript):
        assert mid_sentence_cut_rate([], simple_transcript) == 0.0
        assert mid_sentence_cut_rate([clip(0, 10)], Transcript(segments=[])) == 0.0


class TestDuplicateOverlap:
    def test_no_overlap(self):
        assert duplicate_overlap_rate([clip(0, 30, 1), clip(40, 70, 2)]) == 0.0

    def test_full_overlap(self):
        assert duplicate_overlap_rate([clip(0, 30, 1), clip(10, 40, 2)]) == 1.0

    def test_tiny_touch_is_tolerated(self):
        assert duplicate_overlap_rate([clip(0, 30, 1), clip(29.5, 60, 2)]) == 0.0

    def test_single_clip_is_zero(self):
        assert duplicate_overlap_rate([clip(0, 30)]) == 0.0

    def test_partial_pairs(self):
        clips = [clip(0, 30, 1), clip(10, 40, 2), clip(100, 130, 3)]
        assert duplicate_overlap_rate(clips) == pytest.approx(1 / 3, abs=0.01)


class TestGoldAcceptance:
    def test_exact_match(self):
        assert gold_acceptance([clip(10, 50)], [GoldMoment(10, 50)]) == 1.0

    def test_near_miss_counts_with_iou(self):
        assert gold_acceptance([clip(12, 48)], [GoldMoment(10, 50)]) == 1.0

    def test_disjoint_is_zero(self):
        assert gold_acceptance([clip(200, 240)], [GoldMoment(10, 50)]) == 0.0

    def test_missing_gold_is_unmeasurable(self):
        # 0 과 구분되어야 한다 — 측정 불가와 전부 놓침은 다르다
        assert gold_acceptance([clip(0, 30)], []) == -1.0

    def test_no_clips_misses_everything(self):
        assert gold_acceptance([], [GoldMoment(10, 50)]) == 0.0

    def test_partial(self):
        clips = [clip(10, 50, 1)]
        golds = [GoldMoment(10, 50), GoldMoment(300, 340)]
        assert gold_acceptance(clips, golds) == 0.5


class TestContextDependency:
    def test_flags_dependent_opener(self):
        transcript = Transcript(segments=[Segment(0, 30, "그래서 제가 그걸 했습니다")], duration=30)
        assert context_dependency_flags([clip(0, 30)], transcript) == ["clip_01"]

    def test_standalone_opener_not_flagged(self):
        transcript = Transcript(segments=[Segment(0, 30, "월 300만원 버는 방법은 이렇습니다")], duration=30)
        assert context_dependency_flags([clip(0, 30)], transcript) == []

    def test_english_opener(self):
        transcript = Transcript(segments=[Segment(0, 30, "So that is what happened")], duration=30)
        assert context_dependency_flags([clip(0, 30)], transcript) == ["clip_01"]

    def test_empty_window_is_skipped(self):
        assert context_dependency_flags([clip(500, 530)], Transcript(segments=[])) == []


class TestMeasureQuality:
    def test_combines_metrics(self, simple_transcript):
        clips = [clip(0.0, 26.0, 1)]
        metrics = measure_quality(clips, simple_transcript, [GoldMoment(0, 26)],
                                  min_seconds=20, max_seconds=40)
        assert metrics.clip_count == 1
        assert metrics.mid_sentence_cut_rate == 0.0
        assert metrics.gold_acceptance == 1.0
        assert metrics.clips_outside_length_range == 0

    def test_flags_length_violations(self, simple_transcript):
        metrics = measure_quality([clip(0.0, 12.0)], simple_transcript,
                                  min_seconds=30, max_seconds=60)
        assert metrics.clips_outside_length_range == 1

    def test_human_fields_stay_unset(self, simple_transcript):
        """사람 평가는 자동 계산하지 않는다."""
        metrics = measure_quality([clip(0, 26)], simple_transcript)
        assert metrics.human_standalone_rate is None

    def test_context_rate_derived(self, simple_transcript):
        metrics = measure_quality([clip(0, 26)], simple_transcript)
        assert 0.0 <= metrics.context_dependency_rate <= 1.0

    def test_to_dict_includes_derived_rate(self, simple_transcript):
        data = measure_quality([clip(0, 26)], simple_transcript).to_dict()
        assert "context_dependency_rate" in data


class TestPerformanceMeasurement:
    def test_peak_memory_is_positive(self):
        assert peak_memory_mb() > 0

    def test_track_stage_records_timing(self):
        timings: list[StageTiming] = []
        with track_stage("transcribe", timings):
            pass
        assert len(timings) == 1
        assert timings[0].stage == "transcribe"
        assert timings[0].seconds >= 0

    def test_track_stage_records_on_exception(self):
        timings: list[StageTiming] = []
        with pytest.raises(RuntimeError):
            with track_stage("render", timings):
                raise RuntimeError("boom")
        assert timings[0].stage == "render"      # 실패해도 계측은 남는다


class TestRunRecord:
    def test_seconds_per_source_minute(self):
        record = RunRecord(sample_id="s", source_seconds=600, total_seconds=300)
        assert record.seconds_per_source_minute == 30.0

    def test_zero_source_is_safe(self):
        assert RunRecord(sample_id="s", total_seconds=10).seconds_per_source_minute == 0.0

    def test_output_mb(self):
        assert RunRecord(sample_id="s", output_bytes=2_097_152).output_mb == 2.0

    def test_to_dict_serialisable(self):
        record = RunRecord(sample_id="s", source_seconds=60, total_seconds=30, succeeded=True)
        assert json.loads(json.dumps(record.to_dict()))["sample_id"] == "s"


class TestReport:
    def _report(self):
        good = RunRecord(sample_id="a", source_seconds=600, total_seconds=300, succeeded=True,
                         output_bytes=1_048_576,
                         quality=QualityMetrics(clip_count=3, mid_sentence_cut_rate=0.0,
                                                duplicate_overlap_rate=0.0,
                                                gold_acceptance=0.8, mean_clip_seconds=45.0))
        bad = RunRecord(sample_id="b", source_seconds=600, total_seconds=100, succeeded=False,
                        error="render failed")
        return BenchmarkReport(manifest_name="test", runs=[good, bad])

    def test_success_rate(self):
        assert self._report().render_success_rate == 0.5

    def test_quality_uses_successful_runs_only(self):
        quality = self._report().aggregate_quality()
        assert quality["mid_sentence_cut_rate"] == 0.0
        assert quality["gold_acceptance"] == 0.8

    def test_performance_aggregate(self):
        performance = self._report().aggregate_performance()
        assert performance["mean_seconds_per_source_minute"] == 30.0

    def test_empty_report_is_safe(self):
        empty = BenchmarkReport()
        assert empty.render_success_rate == 0.0
        assert empty.aggregate_quality() == {}
        assert empty.aggregate_performance() == {}

    def test_gold_omitted_when_unmeasured(self):
        run = RunRecord(sample_id="a", succeeded=True, source_seconds=60, total_seconds=30,
                        quality=QualityMetrics(clip_count=1, gold_acceptance=-1.0))
        assert "gold_acceptance" not in BenchmarkReport(runs=[run]).aggregate_quality()

    def test_markdown_renders(self):
        markdown = self._report().to_markdown()
        assert "렌더 성공률" in markdown
        assert "| a |" in markdown and "| b |" in markdown

    def test_save(self, tmp_path):
        path = self._report().save(tmp_path / "r.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["sample_count"] == 2
        assert data["render_success_rate"] == 0.5
