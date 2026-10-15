"""FFmpeg 필터 그래프와 명령 구성 테스트 (FFmpeg 설치 불필요)."""

from __future__ import annotations

import pytest

from autoshorts.ffmpeg_tools import (
    _parse_fps,
    build_audio_extract_command,
    build_lossless_cut_command,
    build_reframe_filter,
    build_render_command,
    escape_filter_path,
)

FFMPEG = "/usr/bin/ffmpeg"


class TestEscapeFilterPath:
    def test_escapes_windows_drive_colon(self):
        assert escape_filter_path(r"C:\work\clip.ass") == r"C\:/work/clip.ass"

    def test_escapes_single_quotes(self):
        assert "\\'" in escape_filter_path("/tmp/it's.ass")


class TestReframeFilter:
    def test_crop_targets_output_resolution(self):
        graph = build_reframe_filter("crop", 1080, 1920)
        assert "crop=" in graph
        assert "scale=1080:1920" in graph
        assert graph.endswith("[vout]")

    def test_blur_composites_background_and_foreground(self):
        graph = build_reframe_filter("blur", 1080, 1920, blur_sigma=25)
        assert "split=2" in graph
        assert "gblur=sigma=25" in graph
        assert "force_original_aspect_ratio=increase" in graph   # 배경은 화면을 채운다
        assert "force_original_aspect_ratio=decrease" in graph   # 전경은 잘리지 않는다
        assert "overlay=(W-w)/2:(H-h)/2" in graph

    def test_always_ends_with_pixel_format(self):
        for mode in ("crop", "blur"):
            assert "format=yuv420p[vout]" in build_reframe_filter(mode, 1080, 1920)

    def test_appends_subtitles_filter(self):
        graph = build_reframe_filter("blur", 1080, 1920, subtitles_path="/tmp/a b/clip.ass")
        assert "subtitles='/tmp/a b/clip.ass'" in graph

    def test_optional_fps_filter(self):
        assert "fps=30" in build_reframe_filter("crop", 1080, 1920, fps=30)
        assert "fps=" not in build_reframe_filter("crop", 1080, 1920)

    def test_rejects_unknown_mode(self):
        with pytest.raises(ValueError, match="리프레이밍"):
            build_reframe_filter("zoom", 1080, 1920)

    def test_rejects_bad_resolution(self):
        with pytest.raises(ValueError, match="양수"):
            build_reframe_filter("crop", 0, 1920)


class TestAudioExtractCommand:
    def test_matches_whisper_input_spec(self):
        command = build_audio_extract_command("in.mp4", "out.wav", executable=FFMPEG)
        assert command[0] == FFMPEG
        assert "-vn" in command
        assert command[command.index("-ar") + 1] == "16000"
        assert command[command.index("-ac") + 1] == "1"
        assert command[command.index("-acodec") + 1] == "pcm_s16le"
        assert command[-1] == "out.wav"


class TestLosslessCutCommand:
    def test_copies_streams_without_reencoding(self):
        command = build_lossless_cut_command("in.mp4", "out.mp4", 12.5, 30.0, executable=FFMPEG)
        assert command[command.index("-c") + 1] == "copy"
        assert command[command.index("-ss") + 1] == "12.500"
        assert command[command.index("-t") + 1] == "30.000"
        assert command.index("-ss") < command.index("-i")   # 빠른 탐색


class TestRenderCommand:
    def _command(self, **kwargs):
        defaults = dict(
            start=10.0, duration=45.0, filtergraph="[0:v]null[vout]", executable=FFMPEG
        )
        defaults.update(kwargs)
        return build_render_command("in.mp4", "out.mp4", **defaults)

    def test_seeks_before_input_for_speed(self):
        command = self._command()
        assert command.index("-ss") < command.index("-i") < command.index("-t")

    def test_omits_seek_when_starting_at_zero(self):
        assert "-ss" not in self._command(start=0)

    def test_maps_filtered_video_output(self):
        command = self._command()
        assert command[command.index("-filter_complex") + 1] == "[0:v]null[vout]"
        assert command[command.index("-map") + 1] == "[vout]"

    def test_produces_h264_aac_mp4_for_shorts(self):
        command = self._command()
        assert command[command.index("-c:v") + 1] == "libx264"
        assert command[command.index("-c:a") + 1] == "aac"
        assert command[command.index("-pix_fmt") + 1] == "yuv420p"
        assert command[command.index("-movflags") + 1] == "+faststart"

    def test_silent_source_disables_audio(self):
        command = self._command(has_audio=False)
        assert "-an" in command
        assert "-c:a" not in command

    def test_quality_knobs_are_passed_through(self):
        command = self._command(crf=18, preset="slow", audio_bitrate="256k")
        assert command[command.index("-crf") + 1] == "18"
        assert command[command.index("-preset") + 1] == "slow"
        assert command[command.index("-b:a") + 1] == "256k"

    def test_overwrite_flag(self):
        assert "-y" in self._command(overwrite=True)
        assert "-n" in self._command(overwrite=False)


class TestFpsParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("30000/1001", pytest.approx(29.97, abs=0.01)), ("25/1", 25.0), ("0/0", 0.0), (None, 0.0), ("N/A", 0.0)],
    )
    def test_parse(self, value, expected):
        assert _parse_fps(value) == expected
