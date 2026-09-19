"""기준선 측정 도구 테스트 — 실제 영상 없이 검증한다."""

from __future__ import annotations

import json

import pytest

from autoshorts.benchmark import (
    CONTENT_MODES,
    MANIFEST_VERSION,
    BenchmarkManifest,
    BenchmarkReport,
    BenchmarkSample,
    GoldMoment,
    SampleRun,
    StageTimer,
    clip_boundary_flags,
    duplicate_overlap_rate,
    gold_acceptance,
    load_manifest,
    mid_sentence_cut_rate,
    peak_memory_mb,
    run_benchmark,
    run_sample,
)
from autoshorts.models import Clip, Segment, Transcript, Word


def words(*pairs) -> list[Word]:
    """``(시작, 끝, 글자)`` 묶음을 Word 목록으로."""
    return [Word(start=s, end=e, text=t) for s, e, t in pairs]


def transcript_of(*segments: Segment) -> Transcript:
    return Transcript(segments=list(segments))


# 두 문장. "첫 문장이다." (0~4초) / "둘째 문장이다." (4~8초)
TWO_SENTENCES = transcript_of(
    Segment(start=0.0, end=4.0, text="첫 문장이다.", words=words(
        (0.0, 2.0, "첫"), (2.0, 4.0, "문장이다."),
    )),
    Segment(start=4.0, end=8.0, text="둘째 문장이다.", words=words(
        (4.0, 6.0, "둘째"), (6.0, 8.0, "문장이다."),
    )),
)


class TestManifest:
    def test_round_trip_through_json(self, tmp_path):
        manifest = BenchmarkManifest(
            name="phase0",
            samples=(
                BenchmarkSample(
                    id="pod-01", source="https://youtu.be/x", duration_bucket=30,
                    content_mode="podcast", rights_status="owned",
                    gold_moments=(GoldMoment(10.0, 45.0, "핵심 주장"),),
                ),
            ),
        )
        path = manifest.save(tmp_path / "m.json")
        again = load_manifest(path)
        assert again.name == "phase0"
        assert again.samples[0].id == "pod-01"
        assert again.samples[0].content_mode == "podcast"
        assert again.samples[0].gold_moments[0].label == "핵심 주장"
        assert again.samples[0].duration_bucket == 30

    def test_saved_json_is_human_readable(self, tmp_path):
        path = BenchmarkManifest(name="한글").save(tmp_path / "m.json")
        raw = path.read_text(encoding="utf-8")
        assert "한글" in raw                      # ensure_ascii=False
        assert raw.endswith("\n")

    def test_version_is_recorded(self, tmp_path):
        path = BenchmarkManifest().save(tmp_path / "m.json")
        assert json.loads(path.read_text(encoding="utf-8"))["version"] == MANIFEST_VERSION

    def test_validate_flags_bad_mode_and_rights(self):
        sample = BenchmarkSample(id="a", source="s", content_mode="asmr", rights_status="stolen")
        problems = sample.validate()
        assert any("content_mode" in p for p in problems)
        assert any("rights_status" in p for p in problems)

    def test_validate_flags_missing_fields(self):
        assert any("source" in p for p in BenchmarkSample(id="a", source="").validate())
        assert any("id" in p for p in BenchmarkSample(id="", source="s").validate())

    def test_validate_flags_reversed_gold_moment(self):
        sample = BenchmarkSample(id="a", source="s", gold_moments=(GoldMoment(9.0, 3.0),))
        assert any("뒤집" in p for p in sample.validate())

    def test_validate_flags_duplicate_ids(self):
        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="dup", source="a"),
            BenchmarkSample(id="dup", source="b"),
        ))
        assert any("중복" in p for p in manifest.validate())

    def test_validate_flags_unknown_version(self):
        assert any("version" in p for p in BenchmarkManifest(version=999).validate())

    def test_clean_manifest_has_no_problems(self):
        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="a", source="s1", content_mode="lecture", rights_status="owned"),
            BenchmarkSample(id="b", source="s2", content_mode="gaming", rights_status="licensed"),
        ))
        assert manifest.validate() == []

    def test_by_bucket_groups_samples(self):
        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="a", source="s", duration_bucket=10),
            BenchmarkSample(id="b", source="s", duration_bucket=10),
            BenchmarkSample(id="c", source="s", duration_bucket=60),
        ))
        grouped = manifest.by_bucket()
        assert [s.id for s in grouped[10]] == ["a", "b"]
        assert [s.id for s in grouped[60]] == ["c"]

    def test_content_modes_match_jobspec_vocabulary(self):
        """MASTER_V3 JobSpec 의 content_mode 어휘와 같아야 한다."""
        assert CONTENT_MODES == ("auto", "podcast", "lecture", "gaming", "sports", "news", "vlog")


class TestStageTimer:
    def test_measures_each_stage(self):
        ticks = iter([0.0, 1.0, 5.0, 11.0, 20.0])
        timer = StageTimer(clock=lambda: next(ticks))
        timer.observe("ingest", 0.0, "")        # t=0
        timer.observe("transcribe", 0.3, "")    # t=1  → ingest 1초
        timer.observe("analyze", 0.6, "")       # t=5  → transcribe 4초
        timer.observe("render", 0.9, "")        # t=11 → analyze 6초
        result = timer.finish()                 # t=20 → render 9초
        assert result == {"ingest": 1.0, "transcribe": 4.0, "analyze": 6.0, "render": 9.0}

    def test_repeated_stage_updates_do_not_split(self):
        ticks = iter([0.0, 7.0, 12.0])
        timer = StageTimer(clock=lambda: next(ticks))
        timer.observe("transcribe", 0.1, "")
        timer.observe("transcribe", 0.5, "")    # 같은 스테이지 — 시계를 쓰지 않는다
        timer.observe("render", 0.9, "")        # t=7 → transcribe 7초
        assert timer.finish() == {"transcribe": 7.0, "render": 5.0}

    def test_finish_without_any_stage_is_empty(self):
        assert StageTimer().finish() == {}

    def test_revisited_stage_accumulates(self):
        ticks = iter([0.0, 2.0, 5.0, 9.0])
        timer = StageTimer(clock=lambda: next(ticks))
        timer.observe("render", 0.1, "")
        timer.observe("analyze", 0.2, "")       # render 2초
        timer.observe("render", 0.3, "")        # analyze 3초
        assert timer.finish()["render"] == 6.0  # 2 + 4


class TestPeakMemory:
    def test_returns_positive_number(self):
        assert peak_memory_mb() > 0


class TestMidSentenceCut:
    def test_clean_sentence_boundaries_are_not_cuts(self):
        clip = Clip(start=0.0, end=4.0, title="t")
        flags = clip_boundary_flags(clip, TWO_SENTENCES)
        assert flags == {"start_mid_sentence": False, "end_mid_sentence": False}

    def test_boundary_inside_a_word_is_a_cut(self):
        clip = Clip(start=1.0, end=3.0, title="t")     # 두 경계 모두 단어 내부
        flags = clip_boundary_flags(clip, TWO_SENTENCES)
        assert flags["start_mid_sentence"] is True
        assert flags["end_mid_sentence"] is True

    def test_ending_mid_sentence_is_a_cut(self):
        clip = Clip(start=0.0, end=6.0, title="t")     # "둘째" 뒤에서 끊긴다
        assert clip_boundary_flags(clip, TWO_SENTENCES)["end_mid_sentence"] is True

    def test_end_of_transcript_is_not_a_cut(self):
        """뒤에 말이 없으면 문장을 자른 게 아니다."""
        clip = Clip(start=0.0, end=8.0, title="t")
        assert clip_boundary_flags(clip, TWO_SENTENCES)["end_mid_sentence"] is False

    def test_rate_counts_both_boundaries(self):
        clips = [Clip(start=0.0, end=4.0, title="a"), Clip(start=1.0, end=3.0, title="b")]
        # 첫 클립 경계 0/2 + 둘째 클립 2/2 = 2/4
        assert mid_sentence_cut_rate(clips, TWO_SENTENCES) == 0.5

    def test_rate_is_zero_without_clips(self):
        assert mid_sentence_cut_rate([], TWO_SENTENCES) == 0.0

    def test_empty_transcript_reports_no_cuts(self):
        """전사가 없으면 판정 근거가 없으므로 자른 것으로 몰지 않는다."""
        clip = Clip(start=1.0, end=3.0, title="t")
        assert clip_boundary_flags(clip, transcript_of()) == {
            "start_mid_sentence": False, "end_mid_sentence": False,
        }


class TestDuplicateOverlap:
    def test_disjoint_clips_have_no_overlap(self):
        clips = [Clip(start=0, end=30, title="a"), Clip(start=40, end=70, title="b")]
        assert duplicate_overlap_rate(clips) == 0.0

    def test_half_overlap_is_measured(self):
        # 30초 + 30초 = 60초 중 15초가 겹친다
        clips = [Clip(start=0, end=30, title="a"), Clip(start=15, end=45, title="b")]
        assert duplicate_overlap_rate(clips) == pytest.approx(0.25)

    def test_identical_clips_saturate_at_one(self):
        clips = [Clip(start=0, end=30, title="a")] * 3
        assert duplicate_overlap_rate(clips) == 1.0

    def test_empty_is_zero(self):
        assert duplicate_overlap_rate([]) == 0.0


class TestGoldAcceptance:
    def test_none_without_gold_moments(self):
        assert gold_acceptance([Clip(start=0, end=30, title="a")], []) is None

    def test_full_hit(self):
        gold = [GoldMoment(10.0, 20.0)]
        clips = [Clip(start=5, end=35, title="a")]
        assert gold_acceptance(clips, gold) == 1.0

    def test_miss_when_overlap_too_small(self):
        gold = [GoldMoment(0.0, 100.0)]
        clips = [Clip(start=90, end=100, title="a")]     # 10% 만 덮는다
        assert gold_acceptance(clips, gold) == 0.0

    def test_partial_hit_rate(self):
        gold = [GoldMoment(0.0, 10.0), GoldMoment(100.0, 110.0)]
        clips = [Clip(start=0, end=10, title="a")]
        assert gold_acceptance(clips, gold) == 0.5

    def test_top_n_limits_considered_clips(self):
        gold = [GoldMoment(100.0, 110.0)]
        clips = [Clip(start=0, end=10, title="a"), Clip(start=100, end=110, title="b")]
        assert gold_acceptance(clips, gold, top_n=1) == 0.0
        assert gold_acceptance(clips, gold, top_n=2) == 1.0

    def test_no_clips_is_zero_not_none(self):
        assert gold_acceptance([], [GoldMoment(0.0, 5.0)]) == 0.0


class FakeResult:
    """run_pipeline 반환값 흉내."""

    def __init__(self, outputs=(), clips=(), transcript_path=None, offline=False):
        self.output_paths = list(outputs)
        self.clips = list(clips)
        self.transcript_path = transcript_path
        self.used_offline_analysis = offline


class TestRunSample:
    def test_records_outputs_and_stages(self, tmp_path):
        out = tmp_path / "o.mp4"
        out.write_bytes(b"x" * 2048)
        sample = BenchmarkSample(id="s1", source="src")
        # run_sample 이 전체 시간용으로 앞에서 한 번, StageTimer 가 전환마다 한 번,
        # 마지막에 run_sample 과 finish 가 각각 한 번 읽는다.
        ticks = iter([0.0, 0.0, 3.0, 10.0, 10.0])

        def runner(settings, on_progress=None):
            on_progress("ingest", 0.0, "")
            on_progress("render", 0.9, "")
            return FakeResult(outputs=[out], clips=[Clip(start=0, end=30, title="t")])

        run = run_sample(object(), sample, runner=runner, clock=lambda: next(ticks))
        assert run.ok is True
        assert run.output_count == 1
        assert run.output_bytes == 2048
        assert run.clip_count == 1
        assert run.stage_seconds["ingest"] == 3.0
        assert run.peak_memory_mb > 0

    def test_failure_is_captured_not_raised(self, tmp_path):
        def runner(settings, on_progress=None):
            raise RuntimeError("ffmpeg 없음")

        run = run_sample(object(), BenchmarkSample(id="bad", source="s"), runner=runner)
        assert run.ok is False
        assert "ffmpeg 없음" in run.error
        assert "RuntimeError" in run.error

    def test_no_outputs_is_not_success(self):
        run = run_sample(
            object(), BenchmarkSample(id="empty", source="s"),
            runner=lambda settings, on_progress=None: FakeResult(),
        )
        assert run.ok is False
        assert "산출물" in run.error

    def test_missing_output_file_is_tolerated(self, tmp_path):
        """렌더 후 파일이 사라져 있어도 측정이 죽지 않는다."""
        run = run_sample(
            object(), BenchmarkSample(id="gone", source="s"),
            runner=lambda settings, on_progress=None: FakeResult(outputs=[tmp_path / "nope.mp4"]),
        )
        assert run.ok is False
        assert run.output_bytes == 0

    def test_quality_metrics_from_transcript(self, tmp_path):
        out = tmp_path / "o.mp4"
        out.write_bytes(b"x")
        tpath = tmp_path / "transcription.json"
        tpath.write_text(json.dumps(TWO_SENTENCES.to_dict(), ensure_ascii=False), encoding="utf-8")
        clips = [Clip(start=1.0, end=3.0, title="t")]      # 양쪽 경계가 단어 내부
        # gold 4초 중 2초(50%)를 덮으므로 min_overlap_ratio 0.5 기준으로 적중이다.
        sample = BenchmarkSample(id="q", source="s", gold_moments=(GoldMoment(0.0, 4.0),))

        run = run_sample(
            object(), sample,
            runner=lambda settings, on_progress=None: FakeResult(
                outputs=[out], clips=clips, transcript_path=tpath),
        )
        assert run.mid_sentence_cut_rate == 1.0
        assert run.duplicate_overlap_rate == 0.0
        assert run.gold_acceptance == 1.0
        assert run.source_seconds == pytest.approx(8.0)

    def test_unreadable_transcript_skips_quality_only(self, tmp_path):
        out = tmp_path / "o.mp4"
        out.write_bytes(b"x")
        bad = tmp_path / "t.json"
        bad.write_text("{ not json", encoding="utf-8")
        run = run_sample(
            object(), BenchmarkSample(id="q", source="s"),
            runner=lambda settings, on_progress=None: FakeResult(
                outputs=[out], clips=[Clip(start=0, end=5, title="t")], transcript_path=bad),
        )
        assert run.ok is True                               # 렌더는 성공했다
        assert run.mid_sentence_cut_rate is None            # 품질만 건너뛴다
        assert run.duplicate_overlap_rate == 0.0


class TestReport:
    def _report(self):
        return BenchmarkReport(runs=[
            SampleRun(sample_id="a", ok=True, source_seconds=600, elapsed_seconds=300,
                      peak_memory_mb=900.0, output_bytes=1000, clip_count=4,
                      mid_sentence_cut_rate=0.1, duplicate_overlap_rate=0.0,
                      gold_acceptance=0.75),
            SampleRun(sample_id="b", ok=False, error="터졌다", peak_memory_mb=1200.0),
        ])

    def test_success_rate(self):
        assert self._report().render_success_rate == 0.5

    def test_aggregate_ignores_failures_in_quality(self):
        agg = self._report().aggregate()
        assert agg["samples"] == 2 and agg["succeeded"] == 1
        assert agg["mean_mid_sentence_cut_rate"] == 0.1
        assert agg["mean_gold_acceptance"] == 0.75
        assert agg["peak_memory_mb"] == 1200.0            # 실패 건도 자원은 센다
        assert agg["total_output_bytes"] == 1000

    def test_seconds_per_source_minute(self):
        run = SampleRun(sample_id="a", ok=True, source_seconds=600, elapsed_seconds=300)
        assert run.realtime_factor == 0.5
        assert run.seconds_per_source_minute == 30.0

    def test_unknown_source_length_gives_none(self):
        run = SampleRun(sample_id="a", ok=True, source_seconds=0, elapsed_seconds=300)
        assert run.realtime_factor is None
        assert run.seconds_per_source_minute is None

    def test_empty_report_has_no_success_rate(self):
        assert BenchmarkReport().render_success_rate is None

    def test_markdown_lists_failures(self):
        text = self._report().to_markdown()
        assert "터졌다" in text
        assert "| a | OK |" in text
        assert "| b | FAIL |" in text

    def test_markdown_renders_missing_metrics_as_dash(self):
        text = BenchmarkReport(runs=[SampleRun(sample_id="x", ok=True)]).to_markdown()
        assert "—" in text

    def test_saved_json_has_aggregate(self, tmp_path):
        path = self._report().save(tmp_path / "r.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["aggregate"]["render_success_rate"] == 0.5
        assert len(data["runs"]) == 2


class TestRunBenchmark:
    def test_runs_every_sample_and_records_environment(self, tmp_path):
        out = tmp_path / "o.mp4"
        out.write_bytes(b"x")
        manifest = BenchmarkManifest(name="set", samples=(
            BenchmarkSample(id="a", source="s1"),
            BenchmarkSample(id="b", source="s2"),
        ))
        report = run_benchmark(
            lambda sample: object(), manifest,
            runner=lambda settings, on_progress=None: FakeResult(outputs=[out]),
        )
        assert [r.sample_id for r in report.runs] == ["a", "b"]
        assert report.render_success_rate == 1.0
        assert report.manifest_name == "set"
        assert report.environment["python"]
        assert report.started_at and report.finished_at

    def test_one_failure_does_not_stop_the_set(self, tmp_path):
        out = tmp_path / "o.mp4"
        out.write_bytes(b"x")

        def runner(settings, on_progress=None):
            if getattr(settings, "boom", False):
                raise RuntimeError("실패")
            return FakeResult(outputs=[out])

        class S:
            def __init__(self, boom):
                self.boom = boom

        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="ok1", source="s"),
            BenchmarkSample(id="bad", source="s"),
            BenchmarkSample(id="ok2", source="s"),
        ))
        report = run_benchmark(
            lambda sample: S(sample.id == "bad"), manifest, runner=runner,
        )
        assert [r.ok for r in report.runs] == [True, False, True]
        assert report.render_success_rate == pytest.approx(0.6667, abs=1e-4)


class TestCli:
    """`autoshorts benchmark` / `autoshorts quota` 배선 검증."""

    def test_quota_command_prints_policy(self, capsys):
        from autoshorts.cli import main

        assert main(["quota"]) == 0
        out = capsys.readouterr().out
        assert "최종 진실" in out
        assert "1600" not in out                        # 낡은 가정이 출력되지 않는다

    def test_benchmark_runs_manifest(self, tmp_path, capsys, monkeypatch):
        from autoshorts import cli

        out = tmp_path / "o.mp4"
        out.write_bytes(b"x" * 10)
        manifest = BenchmarkManifest(name="t", samples=(
            BenchmarkSample(id="a", source="s1", duration_bucket=10),
        ))
        path = manifest.save(tmp_path / "m.json")

        import autoshorts.pipeline as pipeline_mod
        monkeypatch.setattr(
            pipeline_mod, "run_pipeline",
            lambda settings, on_progress=None: FakeResult(outputs=[out]),
        )
        report_path = tmp_path / "r.json"
        code = cli.main([
            "benchmark", str(path), "--report", str(report_path),
            "--work-dir", str(tmp_path / "w"),
        ])
        assert code == 0
        assert report_path.exists()
        assert "render success 100.0%" in capsys.readouterr().out

    def test_benchmark_returns_nonzero_on_failure(self, tmp_path, monkeypatch):
        from autoshorts import cli

        manifest = BenchmarkManifest(samples=(BenchmarkSample(id="a", source="s"),))
        path = manifest.save(tmp_path / "m.json")

        import autoshorts.pipeline as pipeline_mod
        monkeypatch.setattr(
            pipeline_mod, "run_pipeline",
            lambda settings, on_progress=None: FakeResult(),      # 산출물 없음
        )
        assert cli.main(["benchmark", str(path), "--work-dir", str(tmp_path / "w")]) == 1

    def test_only_filters_by_duration_bucket(self, tmp_path, monkeypatch):
        from autoshorts import cli

        out = tmp_path / "o.mp4"
        out.write_bytes(b"x")
        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="short", source="s", duration_bucket=10),
            BenchmarkSample(id="long", source="s", duration_bucket=60),
        ))
        path = manifest.save(tmp_path / "m.json")

        seen = []
        import autoshorts.pipeline as pipeline_mod

        def runner(settings, on_progress=None):
            seen.append(settings.work_dir.name)
            return FakeResult(outputs=[out])

        monkeypatch.setattr(pipeline_mod, "run_pipeline", runner)
        assert cli.main([
            "benchmark", str(path), "--only", "60", "--work-dir", str(tmp_path / "w"),
        ]) == 0
        assert seen == ["long"]

    def test_unknown_bucket_filter_is_an_error(self, tmp_path):
        from autoshorts import cli

        manifest = BenchmarkManifest(samples=(
            BenchmarkSample(id="a", source="s", duration_bucket=10),
        ))
        path = manifest.save(tmp_path / "m.json")
        assert cli.main(["benchmark", str(path), "--only", "30"]) == 1

    def test_benchmark_is_a_known_subcommand(self):
        """서브커맨드가 run 으로 오인되지 않는다."""
        from autoshorts.cli import build_parser

        names = build_parser().subcommand_names
        assert "benchmark" in names and "quota" in names
