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
