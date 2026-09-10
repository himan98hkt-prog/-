"""파이프라인 오케스트레이션과 CLI 인자 처리 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoshorts import cli, pipeline
from autoshorts.config import Settings
from autoshorts.downloader import IngestResult
from autoshorts.models import Clip, Transcript
from autoshorts.video_renderer import RenderResult


@pytest.fixture
def stubbed(monkeypatch, tmp_path, short_transcript):
    """4단계를 모두 가짜로 교체하고 호출 내역을 기록한다."""
    calls: dict[str, object] = {}
    video = tmp_path / "source.mp4"
    video.write_bytes(b"fake")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")

    def fake_ingest(source, work_dir, **kwargs):
        calls["ingest"] = {"source": source, "work_dir": Path(work_dir)}
        return IngestResult(
            video_path=video, audio_path=audio, title="테스트 영상", source=source, duration=180.0
        )

    def fake_transcribe(audio_path, **kwargs):
        calls["transcribe"] = kwargs
        if kwargs.get("output_path"):
            short_transcript.save(kwargs["output_path"])
        return short_transcript

    def fake_analyze(transcript, **kwargs):
        calls["analyze"] = kwargs
        return [
            Clip(start=0, end=35, title="첫 클립", reason="r", score=90, index=1),
            Clip(start=40, end=78, title="둘째 클립", reason="r", score=80, index=2),
        ]

    def fake_render_clips(video_path, clips, transcript, settings, on_progress=None, **kwargs):
        calls["render"] = {"clips": list(clips), "settings": settings}
        results = []
        for index, clip in enumerate(clips, start=1):
            if on_progress:
                on_progress(index, len(clips), clip)
            out = Path(settings.output_dir) / clip.output_filename()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"rendered")
            results.append(
                RenderResult(clip=clip, output_path=out, duration=clip.duration, size_bytes=8)
            )
        return results

    monkeypatch.setattr(pipeline.downloader, "ingest", fake_ingest)
    monkeypatch.setattr(pipeline.transcriber, "transcribe", fake_transcribe)
    monkeypatch.setattr(pipeline.ai_analyzer, "analyze", fake_analyze)
    monkeypatch.setattr(pipeline.video_renderer, "render_clips", fake_render_clips)
    return calls


@pytest.fixture
def settings(tmp_path):
    return Settings(source="https://youtu.be/abc", work_dir=tmp_path / "work", output_dir=tmp_path / "out")


class TestPipeline:
    def test_runs_all_stages_in_order(self, settings, stubbed):
        stages = []
        result = pipeline.run_pipeline(settings, on_progress=lambda stage, f, m: stages.append(stage))
        assert [s for s in dict.fromkeys(stages)] == ["ingest", "transcribe", "analyze", "render"]
        assert len(result.renders) == 2
        assert result.title == "테스트 영상"
        assert all(path.exists() for path in result.output_paths)

    def test_progress_is_monotonic_and_bounded(self, settings, stubbed):
        fractions = []
        pipeline.run_pipeline(settings, on_progress=lambda stage, f, m: fractions.append(f))
        assert fractions == sorted(fractions)
        assert 0.0 <= fractions[0] and fractions[-1] == 1.0

    def test_writes_manifest_and_clip_files(self, settings, stubbed):
        result = pipeline.run_pipeline(settings)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert manifest["title"] == "테스트 영상"
        assert len(manifest["outputs"]) == 2
        assert manifest["settings"]["gemini_api_key"] in (None, "***")
        clips_json = list(Path(settings.work_dir).rglob("clips.json"))
        assert clips_json and len(json.loads(clips_json[0].read_text(encoding="utf-8"))) == 2

    def test_reuses_cached_transcript(self, settings, stubbed, short_transcript, monkeypatch):
        pipeline.run_pipeline(settings)
        monkeypatch.setattr(
            pipeline.transcriber, "transcribe",
            lambda *a, **k: pytest.fail("캐시가 있으면 다시 전사하면 안 된다"),
        )
        assert len(pipeline.run_pipeline(settings).renders) == 2

    def test_overwrite_forces_retranscription(self, settings, stubbed):
        pipeline.run_pipeline(settings)
        settings.overwrite = True
        stubbed.pop("transcribe")
        pipeline.run_pipeline(settings)
        assert "transcribe" in stubbed

    def test_same_source_shares_work_dir(self, settings, stubbed, tmp_path):
        first = pipeline.run_pipeline(settings)
        used = stubbed["ingest"]["work_dir"]
        pipeline.run_pipeline(settings)
        assert stubbed["ingest"]["work_dir"] == used
        assert first.transcript_path.parent == used

    def test_different_sources_get_separate_work_dirs(self, settings, stubbed, tmp_path):
        pipeline.run_pipeline(settings)
        first = stubbed["ingest"]["work_dir"]
        settings.source = "https://youtu.be/other"
        pipeline.run_pipeline(settings)
        assert stubbed["ingest"]["work_dir"] != first

    def test_clips_override_skips_analysis(self, settings, stubbed):
        override = [Clip(start=5, end=40, title="수동 지정")]
        result = pipeline.run_pipeline(settings, clips_override=override)
        assert "analyze" not in stubbed
        assert [c.title for c in result.clips] == ["수동 지정"]
        assert result.clips[0].index == 1

    def test_marks_offline_analysis(self, settings, stubbed, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        settings.gemini_api_key = None
        assert pipeline.run_pipeline(settings).used_offline_analysis is True

    def test_no_clips_ends_early(self, settings, stubbed, monkeypatch):
        monkeypatch.setattr(pipeline.ai_analyzer, "analyze", lambda transcript, **kwargs: [])
        result = pipeline.run_pipeline(settings)
        assert result.clips == [] and result.renders == []

    def test_empty_source_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="source"):
            pipeline.run_pipeline(Settings(source="", work_dir=tmp_path))

    def test_progress_callback_errors_are_swallowed(self, settings, stubbed):
        def boom(stage, fraction, message):
            raise RuntimeError("UI 죽음")

        assert len(pipeline.run_pipeline(settings, on_progress=boom).renders) == 2


class TestCliParsing:
    def test_bare_source_defaults_to_run(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(cli, "_cmd_run", lambda args: captured.setdefault("source", args.source) and 0 or 0)
        cli.main(["https://youtu.be/abc"])
        assert captured["source"] == "https://youtu.be/abc"

    def test_settings_from_run_arguments(self):
        args = cli.build_parser().parse_args(
            ["run", "video.mp4", "--mode", "crop", "--model", "small", "--min-seconds", "20",
             "--max-seconds", "45", "--max-clips", "4", "--crf", "18", "--no-subtitles",
             "--font-size", "90", "-o", "shorts"]
        )
        settings = cli.settings_from_args(args)
        assert settings.source == "video.mp4"
        assert settings.reframe_mode == "crop"
        assert settings.whisper_model == "small"
        assert (settings.min_clip_seconds, settings.max_clip_seconds) == (20.0, 45.0)
        assert settings.max_clips == 4
        assert settings.crf == 18
        assert settings.burn_subtitles is False
        assert settings.subtitle_style.font_size == 90
        assert settings.output_dir == Path("shorts")

    def test_defaults_match_specification(self):
        settings = cli.settings_from_args(cli.build_parser().parse_args(["run", "v.mp4"]))
        assert (settings.width, settings.height) == (1080, 1920)
        assert (settings.min_clip_seconds, settings.max_clip_seconds) == (30.0, 60.0)
        assert (settings.min_clips, settings.max_clips) == (3, 5)
        assert settings.reframe_mode == "blur" and settings.burn_subtitles is True

    def test_negation_flags(self):
        args = cli.build_parser().parse_args(
            ["run", "v.mp4", "--no-vad", "--no-word-highlight", "--no-offline-fallback"]
        )
        settings = cli.settings_from_args(args)
        assert settings.vad_filter is False
        assert settings.subtitle_style.highlight_active_word is False
        assert settings.allow_offline_fallback is False

    def test_rejects_unknown_mode(self, capsys):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["run", "v.mp4", "--mode", "zoom"])

    def test_no_arguments_prints_help(self, capsys):
        assert cli.main([]) == 0
        assert "autoshorts" in capsys.readouterr().out

    def test_run_reports_failure_when_nothing_rendered(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli, "_cmd_run", lambda args: 1
        )
        assert cli.main(["run", "v.mp4"]) == 1

    def test_errors_become_exit_code_one(self, monkeypatch, capsys):
        monkeypatch.setattr(
            cli, "_cmd_run", lambda args: (_ for _ in ()).throw(RuntimeError("파일 없음"))
        )
        assert cli.main(["run", "v.mp4"]) == 1
        assert "파일 없음" in capsys.readouterr().err


class TestCliCommands:
    def test_analyze_writes_clips_json(self, tmp_path, short_transcript, monkeypatch, capsys):
        transcript_path = short_transcript.save(tmp_path / "transcription.json")
        monkeypatch.setattr(
            cli, "Transcript", Transcript
        )
        assert cli.main(["analyze", str(transcript_path), "--min-seconds", "10", "--max-seconds", "40"]) == 0
        clips = json.loads((tmp_path / "clips.json").read_text(encoding="utf-8"))
        assert clips and clips[0]["title"]

    def test_render_uses_existing_clips(self, tmp_path, short_transcript, monkeypatch, capsys):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"fake")
        clips_path = tmp_path / "clips.json"
        clips_path.write_text(
            json.dumps([{"start": 0, "end": 30, "title": "수동", "score": 50}]), encoding="utf-8"
        )
        transcript_path = short_transcript.save(tmp_path / "t.json")
        rendered = {}

        def fake_render_clips(video_path, clips, transcript, settings, **kwargs):
            rendered["clips"] = list(clips)
            rendered["has_transcript"] = transcript is not None
            return [RenderResult(clip=clips[0], output_path=tmp_path / "out.mp4")]

        monkeypatch.setattr("autoshorts.video_renderer.render_clips", fake_render_clips)
        code = cli.main(
            ["render", str(video), "--clips", str(clips_path), "--transcript", str(transcript_path),
             "-o", str(tmp_path / "out")]
        )
        assert code == 0
        assert rendered["clips"][0].index == 1
        assert rendered["has_transcript"] is True


class TestTrendCli:
    """급상승 탐색 CLI 와 원클릭 연동."""

    def _videos(self):
        from autoshorts.trend_finder import TrendVideo

        return [
            TrendVideo(video_id="top", title="1위 영상", channel_title="채널",
                       view_count=90_000, subscriber_count=10_000, duration_seconds=600, rank=1),
            TrendVideo(video_id="second", title="2위 영상", channel_title="채널",
                       view_count=30_000, subscriber_count=10_000, duration_seconds=600, rank=2),
        ]

    def test_parses_trend_arguments(self):
        args = cli.build_parser().parse_args(
            ["trend", "재테크", "--days", "7", "--top", "5", "--min-vs", "2.5",
             "--min-subscribers", "5000", "--region", "KR", "--lang", "ko", "--channel"]
        )
        assert args.target == "재테크"
        assert (args.days, args.top, args.min_vs) == (7.0, 5, 2.5)
        assert args.min_subscribers == 5000
        assert (args.region, args.lang) == ("KR", "ko")
        assert args.channel is True and args.run is False

    def test_trend_defaults(self):
        args = cli.build_parser().parse_args(["trend", "키워드"])
        assert (args.days, args.top, args.min_vs) == (14.0, 10, 1.0)
        assert args.min_duration == 180.0          # 쇼츠·짧은 영상 제외
        assert args.min_subscribers == 1000

    def test_youtube_key_flows_into_settings(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        args = cli.build_parser().parse_args(["trend", "키워드", "--youtube-api-key", "yt-key"])
        assert cli.settings_from_args(args).youtube_api_key == "yt-key"

    def test_lists_without_running_pipeline(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "autoshorts.trend_finder.find_trending", lambda *a, **k: (self._videos(), 102)
        )
        monkeypatch.setattr(
            "autoshorts.pipeline.run_pipeline",
            lambda *a, **k: pytest.fail("--run 없이는 파이프라인을 돌리면 안 된다"),
        )
        assert cli.main(["trend", "재테크", "--youtube-api-key", "k"]) == 0
        out = capsys.readouterr().out
        assert "https://www.youtube.com/watch?v=top" in out
        assert "102 유닛" in out

    def test_run_flag_hands_top_url_to_pipeline(self, monkeypatch, capsys, tmp_path):
        from autoshorts.pipeline import PipelineResult

        monkeypatch.setattr(
            "autoshorts.trend_finder.find_trending", lambda *a, **k: (self._videos(), 102)
        )
        captured = {}

        def fake_run(settings, **kwargs):
            captured["source"] = settings.source
            return PipelineResult(source=settings.source, title="1위 영상", renders=[])

        monkeypatch.setattr("autoshorts.pipeline.run_pipeline", fake_run)
        cli.main(["trend", "재테크", "--youtube-api-key", "k", "--run", "-o", str(tmp_path)])
        assert captured["source"] == "https://www.youtube.com/watch?v=top"

    def test_run_passes_render_options_through(self, monkeypatch, tmp_path):
        from autoshorts.pipeline import PipelineResult

        monkeypatch.setattr(
            "autoshorts.trend_finder.find_trending", lambda *a, **k: (self._videos(), 102)
        )
        captured = {}

        def fake_run(settings, **kwargs):
            captured["settings"] = settings
            return PipelineResult(source=settings.source, renders=[])

        monkeypatch.setattr("autoshorts.pipeline.run_pipeline", fake_run)
        cli.main(["trend", "키워드", "--youtube-api-key", "k", "--run", "--mode", "crop",
                  "--model", "small", "--max-clips", "4", "-o", str(tmp_path)])
        settings = captured["settings"]
        assert settings.reframe_mode == "crop"
        assert settings.whisper_model == "small"
        assert settings.max_clips == 4

    def test_search_filters_reach_the_finder(self, monkeypatch, capsys):
        captured = {}

        def fake_find(target, **kwargs):
            captured.update(kwargs)
            captured["target"] = target
            return self._videos(), 102

        monkeypatch.setattr("autoshorts.trend_finder.find_trending", fake_find)
        cli.main(["trend", "@어떤채널", "--youtube-api-key", "k", "--days", "3",
                  "--top", "2", "--min-vs", "4", "--min-duration", "300"])
        assert captured["target"] == "@어떤채널"
        assert captured["days"] == 3.0
        assert captured["limit"] == 2
        assert captured["min_vs_ratio"] == 4.0
        assert captured["min_duration"] == 300.0

    def test_writes_json_when_asked(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(
            "autoshorts.trend_finder.find_trending", lambda *a, **k: (self._videos(), 102)
        )
        destination = tmp_path / "trend.json"
        cli.main(["trend", "키워드", "--youtube-api-key", "k", "--json", str(destination)])
        data = json.loads(destination.read_text(encoding="utf-8"))
        assert [row["rank"] for row in data] == [1, 2]
        assert data[0]["url"].endswith("v=top")

    def test_empty_result_exits_nonzero_with_guidance(self, monkeypatch, capsys):
        monkeypatch.setattr("autoshorts.trend_finder.find_trending", lambda *a, **k: ([], 100))
        assert cli.main(["trend", "없는키워드", "--youtube-api-key", "k"]) == 1
        assert "--days" in capsys.readouterr().err

    def test_api_errors_surface_as_exit_one(self, monkeypatch, capsys):
        from autoshorts.trend_finder import QuotaExceededError

        def boom(*a, **k):
            raise QuotaExceededError("일일 할당량을 초과했습니다.")

        monkeypatch.setattr("autoshorts.trend_finder.find_trending", boom)
        assert cli.main(["trend", "키워드", "--youtube-api-key", "k"]) == 1
        assert "할당량" in capsys.readouterr().err


class TestAutoAndUploadCli:
    """자동 실행·업로드·예약 CLI."""

    def test_auto_parses_upload_options(self):
        args = cli.build_parser().parse_args(
            ["auto", "재테크", "--upload", "--privacy", "unlisted", "--upload-count", "2",
             "--tags", "재테크, 부업", "--publish-in", "6h"]
        )
        options = cli._auto_options_from_args(args)
        assert options.upload is True
        assert options.privacy == "unlisted"
        assert options.upload_count == 2
        assert options.tags == ["재테크", "부업"]
        assert options.publish_at is not None

    def test_auto_defaults_to_private(self):
        args = cli.build_parser().parse_args(["auto", "재테크"])
        options = cli._auto_options_from_args(args)
        assert options.privacy == "private"      # 안전 기본값
        assert options.upload is False

    def test_publish_in_units(self):
        from datetime import datetime, timezone

        for text, hours in [("90m", 1.5), ("6h", 6), ("2d", 48)]:
            args = cli.build_parser().parse_args(["auto", "x", "--publish-in", text])
            moment = cli._parse_publish_moment(args)
            delta = (moment - datetime.now(timezone.utc)).total_seconds() / 3600
            assert abs(delta - hours) < 0.1

    def test_publish_at_absolute(self):
        args = cli.build_parser().parse_args(["auto", "x", "--publish-at", "2026-09-15T09:00:00+09:00"])
        moment = cli._parse_publish_moment(args)
        assert moment.year == 2026 and moment.hour == 9

    def test_publish_flags_are_mutually_exclusive(self):
        args = cli.build_parser().parse_args(["auto", "x", "--publish-at", "2026-09-15T09:00:00Z",
                                              "--publish-in", "6h"])
        with pytest.raises(ValueError, match="함께"):
            cli._parse_publish_moment(args)

    def test_bad_publish_in_is_rejected(self):
        args = cli.build_parser().parse_args(["auto", "x", "--publish-in", "곧"])
        with pytest.raises(ValueError, match="publish-in"):
            cli._parse_publish_moment(args)

    def test_auto_runs_and_reports(self, monkeypatch, capsys, tmp_path):
        from autoshorts.automation import AutoResult
        from autoshorts.uploader import UploadResult

        render = type("R", (), {"output_path": tmp_path / "a.mp4"})()
        result = AutoResult(target="재테크", source_url="https://youtu.be/x", title="원본",
                            renders=[render],
                            uploads=[UploadResult(video_id="up1", privacy="private")],
                            quota_used=1702)
        monkeypatch.setattr("autoshorts.automation.run_auto", lambda *a, **k: result)
        assert cli.main(["auto", "재테크", "--upload"]) == 0
        out = capsys.readouterr().out
        assert "youtube.com/shorts/up1" in out
        assert "1702" in out

    def test_auto_skipped_is_not_an_error(self, monkeypatch, capsys):
        from autoshorts.automation import AutoResult

        monkeypatch.setattr(
            "autoshorts.automation.run_auto",
            lambda *a, **k: AutoResult(target="x", skipped_reason="이미 처리한 원본입니다"),
        )
        assert cli.main(["auto", "재테크"]) == 0
        assert "건너뜀" in capsys.readouterr().out

    def test_public_upload_prints_copyright_warning(self, monkeypatch, capsys, tmp_path):
        from autoshorts.automation import AutoResult

        monkeypatch.setattr("autoshorts.automation.run_auto",
                            lambda *a, **k: AutoResult(target="x", skipped_reason="없음"))
        cli.main(["auto", "재테크", "--upload", "--privacy", "public"])
        assert "저작권" in capsys.readouterr().out

    def test_dry_run_upload_is_distinct_from_dry_run(self):
        """--dry-run-upload 는 렌더는 하고 업로드만 멈춘다."""
        upload_only = cli.build_parser().parse_args(["auto", "x", "--upload", "--dry-run-upload"])
        options = cli._auto_options_from_args(upload_only)
        assert options.dry_run_upload is True
        assert cli.settings_from_args(upload_only).dry_run is False   # 렌더는 진행

        full = cli.build_parser().parse_args(["auto", "x", "--upload", "--dry-run"])
        assert cli._auto_options_from_args(full).dry_run_upload is True
        assert cli.settings_from_args(full).dry_run is True           # 렌더도 건너뜀

    def test_title_from_output_filename(self, tmp_path):
        assert cli._title_from_filename(Path("output_03_충격_실화.mp4")) == "충격 실화"
        assert cli._title_from_filename(Path("그냥이름.mp4")) == "그냥이름"

    def test_upload_command_reports_each_file(self, monkeypatch, capsys, tmp_path):
        from autoshorts.uploader import UploadResult

        video = tmp_path / "output_01_제목.mp4"
        video.write_bytes(b"x")
        monkeypatch.setattr("autoshorts.uploader.upload_video",
                            lambda request, **k: UploadResult(video_id="v1", title=request.title))
        assert cli.main(["upload", str(video)]) == 0
        assert "shorts/v1" in capsys.readouterr().out

    def test_upload_missing_file_is_error(self, capsys, tmp_path):
        assert cli.main(["upload", str(tmp_path / "nope.mp4")]) == 1
        assert "파일 없음" in capsys.readouterr().err

    def test_upload_failure_is_error(self, monkeypatch, capsys, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"x")
        monkeypatch.setattr(
            "autoshorts.uploader.upload_video",
            lambda request, **k: (_ for _ in ()).throw(RuntimeError("할당량 초과")),
        )
        assert cli.main(["upload", str(video)]) == 1
        assert "할당량" in capsys.readouterr().err


class TestScheduleCli:
    def test_dry_run_shows_what_would_be_registered(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        assert cli.main(["schedule", "add", "재테크", "--at", "09:30", "--dry-run",
                         "--auto-args", "--upload --max-clips 2"]) == 0
        out = capsys.readouterr().out
        assert "30 9 * * *" in out
        assert "--upload" in out
        assert "매일 09:30" in out

    def test_weekly_schedule(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        cli.main(["schedule", "add", "재테크", "--at", "21:00", "--weekday", "mon", "--dry-run"])
        assert "매주 월요일 21:00" in capsys.readouterr().out

    def test_every_hours_schedule(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        cli.main(["schedule", "add", "재테크", "--every-hours", "6", "--dry-run"])
        assert "6시간마다" in capsys.readouterr().out

    def test_add_without_target_is_error(self, capsys):
        assert cli.main(["schedule", "add"]) == 1
        assert "대상을 지정" in capsys.readouterr().err

    def test_bad_time_is_error(self, capsys):
        assert cli.main(["schedule", "add", "x", "--at", "아침"]) == 1
        assert "해석할 수 없습니다" in capsys.readouterr().err

    def test_show_prints_current(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.show_schedule", lambda **k: "등록된 예약이 없습니다.")
        assert cli.main(["schedule", "show"]) == 0
        assert "등록된 예약이 없습니다" in capsys.readouterr().out

    def test_remove_reports_result(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.remove_schedule", lambda **k: True)
        assert cli.main(["schedule", "remove"]) == 0
        assert "해제" in capsys.readouterr().out

    def test_upload_in_schedule_warns_about_login(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        monkeypatch.setattr("autoshorts.scheduler.install_schedule", lambda *a, **k: "0 9 * * * cmd")
        cli.main(["schedule", "add", "x", "--auto-args=--upload"])
        assert "login" in capsys.readouterr().out

    def test_args_after_double_dash_reach_auto(self, capsys, monkeypatch):
        """`--auto-args "--upload"` 는 argparse 가 옵션으로 오인하므로 `--` 형태도 지원한다."""
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        assert cli.main(["schedule", "add", "재테크", "--at", "09:00", "--dry-run",
                         "--", "--upload", "--max-clips", "2"]) == 0
        out = capsys.readouterr().out
        assert "--upload" in out and "--max-clips" in out

    def test_single_flag_via_equals_form(self, capsys, monkeypatch):
        monkeypatch.setattr("autoshorts.scheduler.detect_platform", lambda: "linux")
        cli.main(["schedule", "add", "x", "--dry-run", "--auto-args=--upload"])
        assert "--upload" in capsys.readouterr().out


class TestDoctorCli:
    def test_doctor_runs_and_reports(self, capsys):
        code = cli.main(["doctor"])
        out = capsys.readouterr().out
        assert code in (0, 1)
        assert "설치 상태 점검" in out
        assert "FFmpeg" in out

    def test_setup_non_interactive_falls_back_to_doctor(self, capsys, tmp_path):
        code = cli.main(["setup", "--non-interactive", "--env-path", str(tmp_path / ".env")])
        assert code in (0, 1)
        assert "설치 상태 점검" in capsys.readouterr().out
