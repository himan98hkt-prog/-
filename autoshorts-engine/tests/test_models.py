"""데이터 모델·직렬화·시간 포맷 테스트."""

from __future__ import annotations

import json

import pytest

from autoshorts.models import (
    Clip,
    Segment,
    Transcript,
    Word,
    _coerce_time,
    format_ass_timestamp,
    format_srt_timestamp,
)


class TestTimestampFormatting:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "00:00:00,000"),
            (1.5, "00:00:01,500"),
            (61.25, "00:01:01,250"),
            (3661.007, "01:01:01,007"),
            (-5, "00:00:00,000"),
        ],
    )
    def test_srt(self, seconds, expected):
        assert format_srt_timestamp(seconds) == expected

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "0:00:00.00"),
            (1.5, "0:00:01.50"),
            (61.25, "0:01:01.25"),
            (3661.0, "1:01:01.00"),
        ],
    )
    def test_ass(self, seconds, expected):
        assert format_ass_timestamp(seconds) == expected


class TestWordAndSegment:
    def test_end_never_precedes_start(self):
        assert Word(5.0, 3.0, "x").end == 5.0

    def test_shift_moves_timeline(self):
        shifted = Word(10.0, 12.0, "hello").shifted(4.0)
        assert (shifted.start, shifted.end) == (6.0, 8.0)

    def test_overlap_detection(self):
        segment = Segment(10.0, 20.0, "text")
        assert segment.overlaps(15.0, 25.0)
        assert segment.overlaps(0.0, 11.0)
        assert not segment.overlaps(20.0, 30.0)   # 경계는 겹치지 않는 것으로 본다
        assert not segment.overlaps(0.0, 10.0)


class TestTranscript:
    def test_duration_derived_from_segments(self):
        transcript = Transcript(segments=[Segment(0, 12.0, "a"), Segment(12.0, 30.0, "b")])
        assert transcript.duration == 30.0

    def test_roundtrip_json(self, transcript, tmp_path):
        path = transcript.save(tmp_path / "t.json")
        loaded = Transcript.load(path)
        assert loaded.language == "ko"
        assert len(loaded) == len(transcript)
        assert loaded.segments[3].words[0].text == transcript.segments[3].words[0].text

    def test_slice_trims_to_window(self, transcript):
        sliced = transcript.slice(30.0, 60.0)
        assert sliced
        assert all(s.start >= 30.0 and s.end <= 60.0 for s in sliced)

    def test_slice_synthesizes_words_when_missing(self):
        transcript = Transcript(segments=[Segment(0.0, 10.0, "하나 둘 셋 넷")])
        words = transcript.slice(0.0, 10.0)[0].words
        assert [w.text for w in words] == ["하나", "둘", "셋", "넷"]
        assert words[0].start == 0.0
        assert words[-1].end <= 10.0

    def test_timestamped_text_has_time_markers(self, short_transcript):
        body = short_transcript.timestamped_text()
        assert body.startswith("[0.0-12.0]")
        assert body.count("\n") == 2

    def test_timestamped_text_truncates(self, transcript):
        body = transcript.timestamped_text(max_chars=200)
        assert len(body) < 400
        assert "생략" in body

    def test_srt_export_is_well_formed(self, short_transcript):
        srt = short_transcript.to_srt()
        assert srt.startswith("1\n00:00:00,000 --> 00:00:12,000\n")
        assert "3\n00:00:26,500 --> 00:00:40,000" in srt


class TestClip:
    def test_filename_matches_spec(self):
        clip = Clip(start=10, end=45, title="충격적인 진실", index=3)
        assert clip.output_filename() == "output_03_충격적인_진실.mp4"

    def test_filename_strips_path_separators(self):
        clip = Clip(start=0, end=30, title="a/b:c*d?e", index=1)
        name = clip.output_filename()
        assert "/" not in name and ":" not in name and "?" not in name
        assert name.startswith("output_01_")

    def test_filename_falls_back_when_title_unusable(self):
        assert Clip(start=0, end=30, title="///", index=7).output_filename() == "output_07_highlight.mp4"

    def test_from_dict_accepts_api_field_names(self):
        clip = Clip.from_dict(
            {"start_time": 12.5, "end_time": 55.0, "title": "제목", "reason": "이유", "score": 88}
        )
        assert (clip.start, clip.end, clip.score) == (12.5, 55.0, 88.0)
        assert clip.duration == 42.5

    def test_json_roundtrip(self):
        clip = Clip(start=1, end=31, title="t", reason="r", score=50, index=2)
        restored = Clip.from_dict(json.loads(json.dumps(clip.to_dict())))
        assert restored.to_dict() == clip.to_dict()


class TestTimeCoercion:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (12.5, 12.5),
            ("12.5", 12.5),
            ("01:23", 83.0),
            ("00:01:23.500", 83.5),
            ("1:00:00", 3600.0),
            ("12,5", 12.5),
            (None, 0.0),
            ("", 0.0),
            ("헛소리", 0.0),
        ],
    )
    def test_coerce(self, value, expected):
        assert _coerce_time(value) == expected
