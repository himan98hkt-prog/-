"""전사 어댑터 테스트 — faster-whisper 설치 없이 가짜 모델로 검증."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field

import pytest

from autoshorts import transcriber
from autoshorts.models import Transcript
from autoshorts.transcriber import TranscriptionError, resolve_device, segments_from_whisper, transcribe


@dataclass
class FakeWord:
    start: float
    end: float
    word: str                     # faster-whisper 는 `word` 필드를 쓴다
    probability: float = 0.9


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    words: list = field(default_factory=list)


@dataclass
class FakeInfo:
    language: str = "ko"
    duration: float = 30.0


class TestResolveDevice:
    def test_cpu_falls_back_to_int8(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "torch", None)
        assert resolve_device("cpu", "auto") == ("cpu", "int8")

    def test_explicit_settings_pass_through(self):
        assert resolve_device("cuda", "float32") == ("cuda", "float32")

    def test_auto_picks_cuda_when_available(self, monkeypatch):
        fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        assert resolve_device("auto", "auto") == ("cuda", "float16")

    def test_auto_falls_back_when_torch_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "torch", None)
        assert resolve_device("auto", "auto") == ("cpu", "int8")


class TestSegmentConversion:
    def test_maps_word_field(self):
        segments = segments_from_whisper(
            [FakeSegment(0.0, 2.0, "안녕 하세요", [FakeWord(0.0, 1.0, "안녕"), FakeWord(1.1, 2.0, "하세요")])]
        )
        assert segments[0].words[0].text == "안녕"
        assert segments[0].words[1].probability == 0.9

    def test_drops_blank_words(self):
        segments = segments_from_whisper([FakeSegment(0, 1, "말", [FakeWord(0, 0.5, "  "), FakeWord(0.5, 1, "말")])])
        assert [w.text for w in segments[0].words] == ["말"]

    def test_skips_entirely_empty_segments(self):
        assert segments_from_whisper([FakeSegment(0, 1, "", [])]) == []

    def test_recovers_text_from_words(self):
        segments = segments_from_whisper([FakeSegment(0, 2, "", [FakeWord(0, 1, "가"), FakeWord(1, 2, "나")])])
        assert segments[0].text == "가 나"

    def test_handles_missing_words_attribute(self):
        class Bare:
            start, end, text = 0.0, 3.0, "단어 없음"

        segments = segments_from_whisper([Bare()])
        assert segments[0].text == "단어 없음" and segments[0].words == []


def install_fake_whisper(monkeypatch, segments, info=None, fail_on_cuda=False):
    """``faster_whisper`` 모듈을 가짜로 주입한다."""
    calls = {}

    class FakeModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            if fail_on_cuda and device == "cuda":
                raise RuntimeError("CUDA driver not found")
            calls["init"] = {"model_size": model_size, "device": device, "compute_type": compute_type}

        def transcribe(self, audio, **kwargs):
            calls["transcribe"] = {"audio": audio, **kwargs}
            return iter(segments), (info or FakeInfo())

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    return calls


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"RIFF0000WAVE")
    return path


class TestTranscribe:
    def test_returns_transcript_and_saves_files(self, audio, tmp_path, monkeypatch):
        install_fake_whisper(
            monkeypatch,
            [
                FakeSegment(0.0, 2.0, "첫 문장", [FakeWord(0.0, 1.0, "첫"), FakeWord(1.0, 2.0, "문장")]),
                FakeSegment(2.5, 5.0, "둘째 문장", [FakeWord(2.5, 3.5, "둘째"), FakeWord(3.5, 5.0, "문장")]),
            ],
        )
        output = tmp_path / "transcription.json"
        transcript = transcribe(audio, model_size="base", device="cpu", output_path=output)

        assert len(transcript) == 2
        assert transcript.language == "ko"
        assert transcript.model == "faster-whisper/base"
        assert output.exists()
        assert output.with_suffix(".srt").exists()
        assert "첫 문장" in output.with_suffix(".srt").read_text(encoding="utf-8")
        assert Transcript.load(output).segments[1].text == "둘째 문장"

    def test_requests_word_timestamps(self, audio, monkeypatch):
        calls = install_fake_whisper(monkeypatch, [FakeSegment(0, 1, "가", [FakeWord(0, 1, "가")])])
        transcribe(audio, device="cpu")
        assert calls["transcribe"]["word_timestamps"] is True
        assert calls["transcribe"]["vad_filter"] is True
        assert calls["transcribe"]["condition_on_previous_text"] is False

    def test_reports_progress(self, audio, monkeypatch):
        install_fake_whisper(
            monkeypatch,
            [FakeSegment(0, 15, "가", [FakeWord(0, 15, "가")]), FakeSegment(15, 30, "나", [FakeWord(15, 30, "나")])],
            info=FakeInfo(duration=30.0),
        )
        seen = []
        transcribe(audio, device="cpu", progress=lambda fraction, text: seen.append(fraction))
        assert seen == [0.5, 1.0]

    def test_falls_back_to_cpu_when_gpu_init_fails(self, audio, monkeypatch):
        calls = install_fake_whisper(
            monkeypatch, [FakeSegment(0, 1, "가", [FakeWord(0, 1, "가")])], fail_on_cuda=True
        )
        transcribe(audio, device="cuda", compute_type="float16")
        assert calls["init"]["device"] == "cpu"

    def test_missing_audio_file(self, tmp_path):
        with pytest.raises(TranscriptionError, match="오디오 파일이 없습니다"):
            transcribe(tmp_path / "nope.wav")

    def test_empty_result_raises(self, audio, monkeypatch):
        install_fake_whisper(monkeypatch, [])
        with pytest.raises(TranscriptionError, match="추출하지 못했습니다"):
            transcribe(audio, device="cpu")

    def test_missing_dependency_message(self, audio, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("nope")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        with pytest.raises(TranscriptionError, match="pip install faster-whisper"):
            transcribe(audio)


class TestCache:
    def test_reuses_existing_transcript(self, audio, tmp_path, short_transcript, monkeypatch):
        cache = short_transcript.save(tmp_path / "transcription.json")
        monkeypatch.setattr(
            transcriber, "transcribe",
            lambda *a, **k: pytest.fail("캐시가 있으면 다시 전사하면 안 된다"),
        )
        assert len(transcriber.load_or_transcribe(audio, cache)) == 3
