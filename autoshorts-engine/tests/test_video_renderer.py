"""렌더러 테스트 — FFmpeg 실행은 가로채고 명령/산출물 규격만 검증."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoshorts import ffmpeg_tools, video_renderer
from autoshorts.config import Settings, SubtitleStyle
from autoshorts.models import Clip
from autoshorts.utils import CommandError
from autoshorts.video_renderer import RenderError, render_clip, render_clips


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "source.mp4"
    path.write_bytes(b"fake video")
    return path


@pytest.fixture
def settings(tmp_path):
    return Settings(
        source="x",
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "out",
        subtitle_style=SubtitleStyle(),
    )


@pytest.fixture
def captured(monkeypatch):
    """FFmpeg 호출을 가로채 명령을 기록하고 빈 결과 파일을 만든다."""
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        Path(command[-1]).write_bytes(b"rendered")

    monkeypatch.setattr(video_renderer.ffmpeg_tools, "run_ffmpeg", fake_run)
    monkeypatch.setattr(ffmpeg_tools, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        video_renderer.ffmpeg_tools, "probe_media",
        lambda path: type("Info", (), {"has_audio": True, "duration": 600.0})(),
    )
    return commands


class TestRenderClip:
    def test_output_filename_follows_spec(self, video, settings, transcript, captured):
        clip = Clip(start=30, end=70, title="충격 실화", index=2)
        result = render_clip(video, clip, transcript, settings)
        assert result.output_path.name == "output_02_충격_실화.mp4"
        assert result.output_path.exists()
        assert result.size_bytes > 0

    def test_burns_subtitles_for_the_clip_window(self, video, settings, transcript, captured):
        clip = Clip(start=30, end=70, title="자막", index=1)
        result = render_clip(video, clip, transcript, settings)
        assert result.subtitle_path is not None and result.subtitle_path.exists()
        graph = captured[0][captured[0].index("-filter_complex") + 1]
        assert "subtitles=" in graph
        assert "Dialogue:" in result.subtitle_path.read_text(encoding="utf-8")

    def test_subtitles_disabled(self, video, settings, transcript, captured):
        settings.burn_subtitles = False
        result = render_clip(video, Clip(start=0, end=40, title="t", index=1), transcript, settings)
        assert result.subtitle_path is None
        assert "subtitles=" not in captured[0][captured[0].index("-filter_complex") + 1]

    def test_silent_window_skips_subtitle_file(self, video, settings, transcript, captured):
        # 전사본(180초) 밖 구간이라 자막으로 쓸 발화가 없다
        result = render_clip(video, Clip(start=300, end=340, title="무음", index=1), transcript, settings)
        assert result.subtitle_path is None

    def test_seeks_to_clip_start_with_duration(self, video, settings, transcript, captured):
        render_clip(video, Clip(start=42.5, end=90.0, title="t", index=1), transcript, settings)
        command = captured[0]
        assert command[command.index("-ss") + 1] == "42.500"
        assert command[command.index("-t") + 1] == "47.500"

    def test_reframe_mode_selects_filter(self, video, settings, transcript, captured):
        settings.reframe_mode = "crop"
        render_clip(video, Clip(start=0, end=40, title="t", index=1), transcript, settings)
        graph = captured[0][captured[0].index("-filter_complex") + 1]
        assert "gblur" not in graph and "crop=" in graph

    def test_target_resolution_is_vertical(self, video, settings, transcript, captured):
        render_clip(video, Clip(start=0, end=40, title="t", index=1), transcript, settings)
        graph = captured[0][captured[0].index("-filter_complex") + 1]
        assert "1080:1920" in graph

    def test_lossless_cut_runs_two_stages(self, video, settings, transcript, captured):
        settings.lossless_cut = True
        render_clip(video, Clip(start=100, end=140, title="t", index=1), transcript, settings)
        assert len(captured) == 2
        assert captured[0][captured[0].index("-c") + 1] == "copy"
        # 2단계는 이미 잘린 조각을 쓰므로 다시 탐색하지 않는다
        assert "-ss" not in captured[1]

    def test_does_not_overwrite_existing_output_by_default(self, video, settings, transcript, captured):
        clip = Clip(start=0, end=40, title="같은제목", index=1)
        first = render_clip(video, clip, transcript, settings).output_path
        second = render_clip(video, clip, transcript, settings).output_path
        assert first != second
        assert second.name == "output_01_같은제목-2.mp4"

    def test_overwrite_flag_reuses_path(self, video, settings, transcript, captured):
        settings.overwrite = True
        clip = Clip(start=0, end=40, title="같은제목", index=1)
        assert render_clip(video, clip, transcript, settings).output_path == render_clip(
            video, clip, transcript, settings
        ).output_path

    def test_dry_run_skips_execution(self, video, settings, transcript, captured):
        settings.dry_run = True
        result = render_clip(video, Clip(start=0, end=40, title="t", index=1), transcript, settings)
        assert captured == []
        assert result.extras["dry_run"] is True
        assert "-filter_complex" in result.extras["command"]

    def test_missing_source_raises(self, settings, transcript, tmp_path):
        with pytest.raises(RenderError, match="원본 영상이 없습니다"):
            render_clip(tmp_path / "nope.mp4", Clip(start=0, end=30, title="t", index=1), transcript, settings)

    def test_zero_length_clip_raises(self, video, settings, transcript):
        with pytest.raises(RenderError, match="길이가 0"):
            render_clip(video, Clip(start=10, end=10, title="t", index=1), transcript, settings)

    def test_ffmpeg_failure_is_wrapped(self, video, settings, transcript, monkeypatch):
        monkeypatch.setattr(ffmpeg_tools, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
        monkeypatch.setattr(
            video_renderer.ffmpeg_tools, "run_ffmpeg",
            lambda command, **kwargs: (_ for _ in ()).throw(CommandError(command, 1, "Invalid argument")),
        )
        with pytest.raises(RenderError, match="렌더링 실패"):
            render_clip(video, Clip(start=0, end=40, title="t", index=1), transcript, settings)


class TestRenderClips:
    def test_renders_every_clip_and_reports_progress(self, video, settings, transcript, captured):
        clips = [Clip(start=0, end=40, title="A", index=1), Clip(start=60, end=100, title="B", index=2)]
        seen = []
        results = render_clips(
            video, clips, transcript, settings, on_progress=lambda i, total, clip: seen.append((i, total))
        )
        assert len(results) == 2
        assert seen == [(1, 2), (2, 2)]
        assert [r.output_path.name for r in results] == ["output_01_A.mp4", "output_02_B.mp4"]

    def test_one_failure_does_not_stop_the_batch(self, video, settings, transcript, monkeypatch):
        monkeypatch.setattr(ffmpeg_tools, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
        monkeypatch.setattr(
            video_renderer.ffmpeg_tools, "probe_media",
            lambda path: type("Info", (), {"has_audio": True, "duration": 600.0})(),
        )
        calls = {"n": 0}

        def flaky(command, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise CommandError(command, 1, "boom")
            Path(command[-1]).write_bytes(b"ok")

        monkeypatch.setattr(video_renderer.ffmpeg_tools, "run_ffmpeg", flaky)
        results = render_clips(
            video,
            [Clip(start=0, end=40, title="A", index=1), Clip(start=60, end=100, title="B", index=2)],
            transcript,
            settings,
        )
        assert [r.clip.title for r in results] == ["B"]

    def test_continue_on_error_disabled_propagates(self, video, settings, transcript, monkeypatch):
        monkeypatch.setattr(ffmpeg_tools, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
        monkeypatch.setattr(
            video_renderer.ffmpeg_tools, "probe_media",
            lambda path: type("Info", (), {"has_audio": True, "duration": 600.0})(),
        )
        monkeypatch.setattr(
            video_renderer.ffmpeg_tools, "run_ffmpeg",
            lambda command, **kwargs: (_ for _ in ()).throw(CommandError(command, 1, "boom")),
        )
        with pytest.raises(RenderError):
            render_clips(
                video, [Clip(start=0, end=40, title="A", index=1)], transcript, settings,
                continue_on_error=False,
            )

    def test_silent_source_renders_without_audio(self, video, settings, transcript, monkeypatch, captured):
        monkeypatch.setattr(
            video_renderer.ffmpeg_tools, "probe_media",
            lambda path: type("Info", (), {"has_audio": False, "duration": 600.0})(),
        )
        render_clips(video, [Clip(start=0, end=40, title="A", index=1)], transcript, settings)
        assert "-an" in captured[0]
