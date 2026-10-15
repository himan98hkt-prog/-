"""파일명 정리·설정 검증·.env 로딩 테스트."""

from __future__ import annotations

import os

import pytest

from autoshorts.config import Settings, SubtitleStyle, load_dotenv
from autoshorts.utils import CommandError, ToolNotFoundError, human_duration, sanitize_filename, which_or_raise


class TestSanitizeFilename:
    def test_keeps_korean(self):
        assert sanitize_filename("월 300만원 버는 법") == "월_300만원_버는_법"

    @pytest.mark.parametrize("char", list('<>:"/\\|?*'))
    def test_removes_illegal_characters(self, char):
        assert char not in sanitize_filename(f"제목{char}입니다")

    def test_collapses_whitespace_and_separators(self):
        assert sanitize_filename("a   b \n c") == "a_b_c"

    def test_truncates_to_max_length(self):
        assert len(sanitize_filename("가" * 100, max_length=20)) == 20

    def test_strips_control_characters(self):
        assert sanitize_filename("ab\x00\x1fcd") == "abcd"

    def test_drops_emoji(self):
        assert sanitize_filename("충격 😱 실화") == "충격_실화"

    def test_avoids_windows_reserved_names(self):
        assert sanitize_filename("CON") == "CON_"

    def test_empty_input(self):
        assert sanitize_filename("") == ""
        assert sanitize_filename(None) == ""

    def test_no_leading_or_trailing_separators(self):
        result = sanitize_filename("  ...제목...  ")
        assert not result.startswith(("_", ".")) and not result.endswith(("_", "."))


class TestHumanDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(0, "0초"), (45, "45초"), (95.4, "1분 35초"), (3725, "1시간 2분 5초"), (None, "0초")],
    )
    def test_formats(self, seconds, expected):
        assert human_duration(seconds) == expected


class TestSettings:
    def test_defaults_match_spec(self):
        settings = Settings(source="x")
        assert (settings.width, settings.height) == (1080, 1920)
        assert (settings.min_clip_seconds, settings.max_clip_seconds) == (30.0, 60.0)
        assert (settings.min_clips, settings.max_clips) == (3, 5)
        assert settings.reframe_mode == "blur"

    def test_rejects_unknown_reframe_mode(self):
        with pytest.raises(ValueError, match="reframe_mode"):
            Settings(source="x", reframe_mode="zoom")

    def test_rejects_inverted_clip_bounds(self):
        with pytest.raises(ValueError, match="max_clip_seconds"):
            Settings(source="x", min_clip_seconds=60, max_clip_seconds=30)

    def test_rejects_inverted_clip_counts(self):
        with pytest.raises(ValueError, match="max_clips"):
            Settings(source="x", min_clips=9, max_clips=2)

    def test_rejects_non_positive_resolution(self):
        with pytest.raises(ValueError, match="width/height"):
            Settings(source="x", width=0)

    def test_reads_api_key_from_environment(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        settings = Settings(source="x")
        assert settings.has_gemini and settings.gemini_api_key == "test-key-123"

    def test_to_dict_masks_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
        data = Settings(source="x").to_dict()
        assert data["gemini_api_key"] == "***"
        assert "super-secret" not in str(data)

    def test_resolved_makes_paths_absolute(self, tmp_path):
        settings = Settings(source="x").resolved(tmp_path)
        assert settings.work_dir.is_absolute() and settings.output_dir.is_absolute()
        assert settings.work_dir.parent == tmp_path

    def test_subtitle_style_defaults_are_shorts_friendly(self):
        style = SubtitleStyle()
        assert style.bold and style.font_size >= 60
        assert style.margin_v > 200          # 하단 UI 를 피한다
        assert style.highlight_active_word


class TestDotenv:
    def test_parses_without_dependency(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            '# 주석\nexport GEMINI_API_KEY="abc123"\nGEMINI_MODEL=gemini-2.0-flash\nBROKEN\n',
            encoding="utf-8",
        )
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        loaded = load_dotenv(env)
        assert loaded["GEMINI_API_KEY"] == "abc123"
        assert os.environ["GEMINI_MODEL"] == "gemini-2.0-flash"
        assert "BROKEN" not in loaded

    def test_does_not_override_existing_by_default(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
        monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
        load_dotenv(env)
        assert os.environ["GEMINI_API_KEY"] == "from-shell"

    def test_missing_file_is_noop(self, tmp_path):
        assert load_dotenv(tmp_path / "nope.env") == {}


class TestToolLookup:
    def test_raises_with_install_hint(self):
        with pytest.raises(ToolNotFoundError, match="설치"):
            which_or_raise("definitely-not-a-real-binary", "설치 안내")

    def test_honours_environment_override(self, tmp_path, monkeypatch):
        fake = tmp_path / "ffmpeg"
        fake.write_text("#!/bin/sh\n")
        monkeypatch.setenv("AUTOSHORTS_FFMPEG", str(fake))
        assert which_or_raise("ffmpeg") == str(fake)

    def test_command_error_keeps_stderr_tail(self):
        error = CommandError(["ffmpeg", "-i", "x"], 1, "line1\nline2\nfatal: boom")
        assert "fatal: boom" in str(error)
        assert error.returncode == 1
