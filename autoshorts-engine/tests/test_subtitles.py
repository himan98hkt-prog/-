"""ASS 자막 생성: 청킹, 이스케이프, 줄바꿈, 강조 스타일."""

from __future__ import annotations

import re

import pytest

from autoshorts.config import SubtitleStyle
from autoshorts.models import Word
from autoshorts.subtitles import (
    _visible_length,
    build_ass,
    chunk_words,
    escape_ass_text,
    words_from_segments,
    wrap_text,
    write_clip_subtitles,
)


def words(*specs: tuple[float, float, str]) -> list[Word]:
    return [Word(start, end, text) for start, end, text in specs]


class TestEscaping:
    def test_escapes_ass_control_characters(self):
        assert escape_ass_text("{tag}") == "\\{tag\\}"
        assert escape_ass_text("a\\b") == "a\\\\b"

    def test_converts_newlines(self):
        assert escape_ass_text("a\nb") == "a\\Nb"
        assert escape_ass_text("a\r\nb") == "a\\Nb"


class TestWrapText:
    def test_wraps_at_limit(self):
        assert wrap_text("aaa bbb ccc", 7) == "aaa bbb\\Nccc"

    def test_does_not_split_long_words(self):
        assert wrap_text("aaaaaaaaaa bb", 5) == "aaaaaaaaaa\\Nbb"

    def test_zero_limit_disables_wrapping(self):
        assert wrap_text("a b c", 0) == "a b c"

    def test_visible_length_ignores_override_tags(self):
        assert _visible_length("{\\c&H00FFFF&}안녕{\\c&HFFFFFF&}") == 2


class TestChunking:
    def test_splits_on_long_silence(self):
        cues = chunk_words(words((0, 0.5, "가"), (0.6, 1.0, "나"), (5.0, 5.5, "다")), max_gap=0.8)
        assert len(cues) == 2
        assert cues[1].text == "다"

    def test_splits_on_word_count(self):
        cues = chunk_words(words(*[(i * 0.3, i * 0.3 + 0.25, f"w{i}") for i in range(9)]), max_words=4)
        assert all(len(cue.words) <= 4 for cue in cues)

    def test_splits_on_duration(self):
        cues = chunk_words(words(*[(i * 1.0, i * 1.0 + 0.9, f"w{i}") for i in range(6)]), max_duration=2.0, max_words=99)
        assert all(cue.duration <= 2.5 for cue in cues)

    def test_breaks_after_sentence_end(self):
        cues = chunk_words(words((0, 0.4, "끝났다."), (0.5, 0.9, "다음")))
        assert len(cues) == 2

    def test_ignores_blank_tokens(self):
        assert chunk_words(words((0, 0.4, "  "), (0.5, 0.9, "말")))[0].text == "말"

    def test_no_words_gives_no_cues(self):
        assert chunk_words([]) == []


class TestBuildAss:
    def test_has_required_sections(self):
        content = build_ass(words((0, 0.5, "하나"), (0.6, 1.2, "둘")))
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        assert "Style: Shorts," in content

    def test_declares_target_resolution(self):
        content = build_ass(words((0, 1, "가")), width=1080, height=1920)
        assert "PlayResX: 1080" in content and "PlayResY: 1920" in content

    def test_offset_shifts_to_clip_timeline(self):
        content = build_ass(words((100.0, 101.0, "가"), (101.2, 102.0, "나")), offset=100.0)
        times = re.findall(r"Dialogue: 0,(\d:\d\d:\d\d\.\d\d),", content)
        assert times and times[0] == "0:00:00.00"

    def test_no_negative_timestamps(self):
        content = build_ass(words((5.0, 6.0, "가")), offset=10.0)
        assert "-" not in content.split("[Events]")[1]

    def test_highlights_active_word(self):
        style = SubtitleStyle(highlight_active_word=True)
        content = build_ass(words((0, 0.5, "하나"), (0.6, 1.2, "둘")), style)
        dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        assert len(dialogues) == 2                     # 단어마다 한 줄
        assert style.highlight_color in dialogues[0]
        assert "하나" in dialogues[0] and "둘" in dialogues[0]

    def test_plain_mode_emits_one_line_per_cue(self):
        style = SubtitleStyle(highlight_active_word=False)
        content = build_ass(words((0, 0.5, "하나"), (0.6, 1.2, "둘")), style)
        dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        assert len(dialogues) == 1
        assert style.highlight_color not in dialogues[0]

    def test_uppercase_option(self):
        style = SubtitleStyle(highlight_active_word=False, uppercase=True)
        content = build_ass(words((0, 1.0, "hello")), style)
        assert "HELLO" in content

    def test_dialogue_events_are_ordered_and_non_empty(self):
        content = build_ass(words(*[(i * 0.5, i * 0.5 + 0.4, f"단어{i}") for i in range(12)]))
        times = re.findall(r"Dialogue: 0,(\d:\d\d:\d\d\.\d\d),(\d:\d\d:\d\d\.\d\d),", content)
        assert times
        assert all(end > start for start, end in times)
        assert times == sorted(times)

    def test_empty_input_still_valid_file(self):
        content = build_ass([])
        assert "[Events]" in content
        assert "Dialogue:" not in content


class TestWriteClipSubtitles:
    def test_writes_file_for_clip_window(self, transcript, tmp_path):
        path = write_clip_subtitles(transcript, 30.0, 60.0, tmp_path / "clip.ass")
        content = path.read_text(encoding="utf-8")
        assert path.exists() and "Dialogue:" in content
        # 클립 기준으로 0초부터 시작하고 30초를 넘지 않는다
        times = re.findall(r"Dialogue: 0,(\d):(\d\d):(\d\d)\.(\d\d),", content)
        seconds = [int(h) * 3600 + int(m) * 60 + int(s) for h, m, s, _ in times]
        assert min(seconds) < 2 and max(seconds) <= 30

    def test_window_without_speech_has_no_dialogue(self, tmp_path):
        from autoshorts.models import Transcript

        empty = Transcript(segments=[], duration=60.0)
        path = write_clip_subtitles(empty, 0.0, 30.0, tmp_path / "x.ass")
        assert "Dialogue:" not in path.read_text(encoding="utf-8")

    def test_words_from_segments_flattens(self, short_transcript):
        flattened = words_from_segments(short_transcript.segments)
        assert len(flattened) == sum(len(s.words) for s in short_transcript.segments)
