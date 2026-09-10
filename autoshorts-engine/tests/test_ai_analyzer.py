"""하이라이트 분석: 프롬프트, 응답 파싱, 구간 교정, 오프라인 대체."""

from __future__ import annotations

import json

import pytest

from autoshorts import ai_analyzer
from autoshorts.ai_analyzer import (
    AnalysisError,
    analyze,
    build_prompt,
    heuristic_highlights,
    normalize_clips,
    parse_response_json,
    snap_to_segments,
)
from autoshorts.ai_analyzer import _shorten_title
from autoshorts.models import Clip, Transcript


class TestPrompt:
    def test_contains_constraints_and_body(self, short_transcript):
        prompt = build_prompt(
            short_transcript, min_seconds=30, max_seconds=60, min_clips=3, max_clips=5,
            video_title="테스트 영상",
        )
        assert "30~60초" in prompt
        assert "3~5개" in prompt
        assert "테스트 영상" in prompt
        assert "start_time" in prompt and "end_time" in prompt
        assert "첫 번째 문장입니다" in prompt

    def test_respects_char_budget(self, transcript):
        prompt = build_prompt(transcript, max_chars=500)
        assert len(prompt) < len(ai_analyzer.SYSTEM_PROMPT) + 1500


class TestResponseParsing:
    def test_plain_object(self):
        payload = '{"clips": [{"start_time": 1, "end_time": 31, "title": "t"}]}'
        assert parse_response_json(payload)[0]["title"] == "t"

    def test_code_fenced(self):
        payload = '설명입니다\n```json\n{"clips": [{"start_time": 0, "end_time": 30}]}\n```\n끝'
        assert len(parse_response_json(payload)) == 1

    def test_bare_array(self):
        assert len(parse_response_json('[{"start_time": 0, "end_time": 30}]')) == 1

    def test_alternative_key_names(self):
        assert parse_response_json('{"highlights": [{"start_time": 0, "end_time": 30}]}')

    def test_leading_prose(self):
        payload = 'Here you go:\n{"clips": [{"start_time": 5, "end_time": 40}]}'
        assert parse_response_json(payload)[0]["start_time"] == 5

    @pytest.mark.parametrize("payload", ["", "   ", "그냥 텍스트입니다", "{broken json"])
    def test_rejects_unparseable(self, payload):
        with pytest.raises(AnalysisError):
            parse_response_json(payload)


class TestSnapping:
    def test_snaps_to_nearby_speech_boundaries(self, short_transcript):
        start, end = snap_to_segments(1.0, 25.0, short_transcript.segments, tolerance=2.5)
        assert start == 0.0
        assert end == 26.0

    def test_leaves_distant_boundaries_alone(self, short_transcript):
        start, end = snap_to_segments(6.0, 20.0, short_transcript.segments, tolerance=1.0)
        assert (start, end) == (6.0, 20.0)

    def test_empty_segments_are_noop(self):
        assert snap_to_segments(3.0, 9.0, []) == (3.0, 9.0)


class TestNormalizeClips:
    def test_enforces_maximum_duration(self, transcript):
        clips = normalize_clips(
            [{"start_time": 10, "end_time": 150, "title": "너무 김", "score": 90}],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert clips[0].duration <= 60.0

    def test_extends_short_clips(self, transcript):
        clips = normalize_clips(
            [{"start_time": 20, "end_time": 28, "title": "너무 짧음", "score": 90}],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert clips[0].duration >= 30.0

    def test_clamps_to_video_duration(self, transcript):
        clips = normalize_clips(
            [{"start_time": 170, "end_time": 260, "title": "범위 밖", "score": 90}],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert clips[0].end <= transcript.duration
        assert clips[0].duration >= 30.0

    def test_drops_inverted_ranges(self, transcript):
        assert normalize_clips([{"start_time": 90, "end_time": 30, "title": "역전"}], transcript) == []

    def test_removes_heavy_overlaps_keeping_best_score(self, transcript):
        clips = normalize_clips(
            [
                {"start_time": 0, "end_time": 40, "title": "낮은 점수", "score": 10},
                {"start_time": 5, "end_time": 45, "title": "높은 점수", "score": 95},
            ],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert len(clips) == 1
        assert clips[0].title == "높은 점수"

    def test_rejects_partial_overlap(self, transcript):
        # 같은 발화가 두 쇼츠에 중복되면 안 된다 — 5초 겹침도 거부
        clips = normalize_clips(
            [
                {"start_time": 0, "end_time": 45, "title": "앞", "score": 90},
                {"start_time": 40, "end_time": 85, "title": "뒤", "score": 80},
            ],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert len(clips) == 1 and clips[0].title == "앞"

    def test_tolerates_boundary_snap_slack(self, transcript):
        # 경계 스냅으로 생긴 1초 이하의 접점은 허용한다
        clips = normalize_clips(
            [
                {"start_time": 0, "end_time": 40, "title": "앞", "score": 90},
                {"start_time": 39.5, "end_time": 80, "title": "뒤", "score": 80},
            ],
            transcript, min_seconds=30, max_seconds=60, snap_tolerance=0.0,
        )
        assert [c.title for c in clips] == ["앞", "뒤"]

    def test_keeps_separate_clips(self, transcript):
        clips = normalize_clips(
            [
                {"start_time": 0, "end_time": 40, "title": "A", "score": 80},
                {"start_time": 100, "end_time": 140, "title": "B", "score": 70},
            ],
            transcript, min_seconds=30, max_seconds=60,
        )
        assert [c.title for c in clips] == ["A", "B"]

    def test_caps_clip_count(self, transcript):
        raw = [
            {"start_time": index * 35, "end_time": index * 35 + 34, "title": f"C{index}", "score": 50 + index}
            for index in range(5)
        ]
        assert len(normalize_clips(raw, transcript, max_clips=3)) == 3

    def test_indexes_sequentially_in_time_order(self, transcript):
        clips = normalize_clips(
            [
                {"start_time": 120, "end_time": 155, "title": "뒤", "score": 99},
                {"start_time": 0, "end_time": 35, "title": "앞", "score": 10},
            ],
            transcript,
        )
        assert [c.index for c in clips] == [1, 2]
        assert [c.title for c in clips] == ["앞", "뒤"]

    def test_fills_missing_title_from_transcript(self, transcript):
        clips = normalize_clips([{"start_time": 0, "end_time": 35, "score": 50}], transcript)
        assert clips[0].title

    def test_generated_title_does_not_cut_mid_word(self, transcript):
        clips = normalize_clips([{"start_time": 0, "end_time": 35, "score": 50}], transcript)
        title = clips[0].title
        first_line = transcript.segments[0].text
        assert title in " ".join(first_line.split())
        # 잘린 지점이 원문에서 단어 경계여야 한다
        assert first_line.startswith(title) and (
            len(title) == len(first_line) or first_line[len(title)] in " ,."
        )

    def test_accepts_string_timestamps(self, transcript):
        clips = normalize_clips(
            [{"start_time": "00:00:10", "end_time": "00:00:55", "title": "문자열", "score": 50}],
            transcript,
            snap_tolerance=0.0,   # 스냅을 끄고 시간 문자열 해석만 확인한다
        )
        assert clips[0].start == 10.0 and clips[0].end == 55.0

    def test_accepts_clip_objects(self, transcript):
        clips = normalize_clips([Clip(start=10, end=50, title="객체", score=50)], transcript)
        assert clips[0].title == "객체"


class TestShortenTitle:
    def test_keeps_short_text_as_is(self):
        assert _shorten_title("짧은 제목", 25) == "짧은 제목"

    def test_cuts_at_word_boundary(self):
        text = "결론부터 말씀드리면, 대부분의 사람들이 첫 단계에서 이미 실패합니다"
        title = _shorten_title(text, 25)
        assert len(title) <= 25
        assert not title.endswith("첫 단")          # 단어 중간 절단 금지
        assert text.startswith(title)

    def test_hard_cuts_a_single_long_word(self):
        assert _shorten_title("가" * 60, 10) == "가" * 10

    def test_strips_trailing_punctuation(self):
        assert _shorten_title("문장입니다.", 25) == "문장입니다"
        assert not _shorten_title("앞 부분, 뒷부분입니다", 8).endswith(",")

    def test_collapses_whitespace(self):
        assert _shorten_title("여러   공백\n포함", 25) == "여러 공백 포함"


class TestHeuristicFallback:
    def test_returns_valid_clips_without_api(self, transcript):
        clips = heuristic_highlights(transcript, min_seconds=30, max_seconds=60, max_clips=5)
        assert clips
        assert all(30.0 <= c.duration <= 60.0 for c in clips)
        assert all(c.end <= transcript.duration for c in clips)
        assert all(c.title for c in clips)
        assert [c.index for c in clips] == list(range(1, len(clips) + 1))

    def test_clips_do_not_overlap(self, transcript):
        clips = heuristic_highlights(transcript)
        for earlier, later in zip(clips, clips[1:]):
            assert later.start >= earlier.start
            overlap = min(earlier.end, later.end) - max(earlier.start, later.start)
            assert overlap <= 1.0, f"클립이 {overlap:.1f}초 겹칩니다"

    def test_penalises_promotional_talk(self, transcript):
        from autoshorts.ai_analyzer import _window_score
        from autoshorts.models import Segment

        promo = [Segment(0, 30, "구독 좋아요 알림설정 부탁드립니다 광고 협찬")]
        content = [Segment(0, 30, "사실 이 방법의 핵심은 30퍼센트를 아끼는 것입니다 왜 그럴까요")]
        assert _window_score(promo, 0, 30)[0] < _window_score(content, 0, 30)[0]

    def test_empty_transcript_yields_nothing(self):
        assert heuristic_highlights(Transcript(segments=[])) == []


class TestAnalyze:
    def test_falls_back_offline_without_key(self, transcript):
        clips = analyze(transcript, api_key=None, allow_offline_fallback=True)
        assert clips and all(c.duration >= 30.0 for c in clips)

    def test_raises_without_key_when_fallback_disabled(self, transcript):
        with pytest.raises(AnalysisError, match="GEMINI_API_KEY"):
            analyze(transcript, api_key=None, allow_offline_fallback=False)

    def test_uses_gemini_response(self, transcript, monkeypatch):
        captured = {}

        def fake_call(prompt, *, api_key, model, timeout=180.0):
            captured["prompt"] = prompt
            captured["model"] = model
            return json.dumps(
                {"clips": [
                    {"start_time": 0, "end_time": 40, "title": "AI 제목", "reason": "이유", "score": 91},
                    {"start_time": 100, "end_time": 145, "title": "두번째", "reason": "이유2", "score": 77},
                ]}
            )

        monkeypatch.setattr(ai_analyzer, "_call_gemini", fake_call)
        clips = analyze(transcript, api_key="k", model="gemini-2.0-flash")
        assert [c.title for c in clips] == ["AI 제목", "두번째"]
        assert captured["model"] == "gemini-2.0-flash"
        assert "전사본" in captured["prompt"]

    def test_falls_back_when_gemini_raises(self, transcript, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("429 quota exceeded")

        monkeypatch.setattr(ai_analyzer, "_call_gemini", boom)
        clips = analyze(transcript, api_key="k", allow_offline_fallback=True)
        assert clips and "오프라인" in clips[0].reason

    def test_propagates_failure_when_fallback_disabled(self, transcript, monkeypatch):
        monkeypatch.setattr(
            ai_analyzer, "_call_gemini", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        with pytest.raises(AnalysisError, match="Gemini 분석 실패"):
            analyze(transcript, api_key="k", allow_offline_fallback=False)

    def test_rejects_empty_transcript(self):
        with pytest.raises(AnalysisError, match="비어"):
            analyze(Transcript(segments=[]), api_key="k")
