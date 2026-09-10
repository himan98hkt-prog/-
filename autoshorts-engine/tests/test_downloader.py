"""입력 소스 판별과 yt-dlp 옵션 구성 테스트 (네트워크 불필요)."""

from __future__ import annotations

import pytest

from autoshorts import downloader
from autoshorts.downloader import IngestError, build_ydl_options, ingest, is_supported_media, is_url


class TestSourceDetection:
    @pytest.mark.parametrize(
        "source",
        ["https://youtu.be/abc", "http://example.com/v.mp4", "https://www.youtube.com/watch?v=x"],
    )
    def test_detects_urls(self, source):
        assert is_url(source)

    @pytest.mark.parametrize("source", ["/home/user/v.mp4", "video.mp4", "C:/videos/a.mkv", ""])
    def test_rejects_local_paths(self, source):
        assert not is_url(source)

    @pytest.mark.parametrize("name", ["a.mp4", "a.MKV", "a.mov", "a.webm", "a.wav", "a.m4a"])
    def test_supported_media(self, name):
        assert is_supported_media(name)

    @pytest.mark.parametrize("name", ["a.txt", "a.pdf", "a"])
    def test_unsupported_media(self, name):
        assert not is_supported_media(name)


class TestYdlOptions:
    def test_requests_best_video_and_audio_merged_to_mp4(self, tmp_path):
        options = build_ydl_options(tmp_path)
        assert "bestvideo" in options["format"] and "bestaudio" in options["format"]
        assert options["merge_output_format"] == "mp4"
        assert options["noplaylist"] is True
        assert str(tmp_path) in options["outtmpl"]

    def test_cookies_option_is_tuple(self, tmp_path):
        assert build_ydl_options(tmp_path, cookies_from_browser="chrome")["cookiesfrombrowser"] == ("chrome",)

    def test_progress_hook_registered(self, tmp_path):
        hook = lambda payload: None
        assert build_ydl_options(tmp_path, progress_hook=hook)["progress_hooks"] == [hook]


class TestIngest:
    def test_rejects_empty_source(self, tmp_path):
        with pytest.raises(IngestError, match="비어"):
            ingest("", tmp_path)

    def test_rejects_missing_file(self, tmp_path):
        with pytest.raises(IngestError, match="찾을 수 없"):
            ingest(str(tmp_path / "nope.mp4"), tmp_path)

    def test_rejects_directory(self, tmp_path):
        with pytest.raises(IngestError, match="디렉터리"):
            ingest(str(tmp_path), tmp_path)

    def test_rejects_unsupported_extension(self, tmp_path):
        bad = tmp_path / "notes.txt"
        bad.write_text("hi")
        with pytest.raises(IngestError, match="지원하지 않는"):
            ingest(str(bad), tmp_path)

    def test_local_file_extracts_audio_and_keeps_original(self, tmp_path, monkeypatch):
        video = tmp_path / "내 영상.mp4"
        video.write_bytes(b"fake")
        work = tmp_path / "work"

        def fake_extract(source, destination, **kwargs):
            from pathlib import Path

            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"RIFF")
            return destination

        monkeypatch.setattr(downloader, "extract_audio", fake_extract)
        monkeypatch.setattr(
            downloader.ffmpeg_tools, "probe_media",
            lambda path: type("Info", (), {"duration": 123.4, "has_audio": True})(),
        )

        result = ingest(str(video), work)
        assert result.video_path == video.resolve()      # 원본은 복사하지 않는다
        assert result.audio_path.exists()
        assert result.title == "내_영상"
        assert result.duration == pytest.approx(123.4)
        assert result.is_remote is False

    def test_remote_source_uses_downloader(self, tmp_path, monkeypatch):
        downloaded = tmp_path / "source.mp4"
        downloaded.write_bytes(b"fake")

        monkeypatch.setattr(
            downloader, "download_video",
            lambda url, out, **kwargs: (downloaded, {"title": "유튜브 제목", "duration": 600, "id": "abc"}),
        )
        monkeypatch.setattr(
            downloader, "extract_audio",
            lambda source, destination, **kwargs: (destination.write_bytes(b"RIFF"), destination)[1],
        )

        result = ingest("https://youtu.be/abc", tmp_path / "work")
        assert result.is_remote is True
        assert result.title == "유튜브_제목"
        assert result.duration == 600
        assert result.metadata["id"] == "abc"

    def test_missing_ytdlp_gives_actionable_message(self, monkeypatch, tmp_path):
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        with pytest.raises(IngestError, match="pip install yt-dlp"):
            downloader.download_video("https://youtu.be/x", tmp_path)
