"""업로드 모듈 테스트 — 실제 API 호출 없이 가짜 service 로 검증."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autoshorts import uploader
from autoshorts.uploader import (
    DAILY_UPLOAD_LIMIT,
    MAX_TITLE_CHARS,
    UPLOAD_QUOTA_COST,
    AuthRequiredError,
    QuotaExceededError,
    UploadError,
    UploadRequest,
    UploadResult,
    build_body,
    check_shorts_eligibility,
    normalise_tags,
    sanitize_description,
    sanitize_title,
    upload_video,
)


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "output_01_제목.mp4"
    path.write_bytes(b"fake video data")
    return path


class FakeInsert:
    def __init__(self, response, chunks=1, error=None):
        self._response = response
        self._chunks = chunks
        self._error = error
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        if self._error:
            raise self._error
        if self.calls < self._chunks:
            return type("Status", (), {"progress": lambda self: 0.5})(), None
        return None, self._response


class FakeService:
    """``service.videos().insert(...)`` 만 흉내 낸다."""

    def __init__(self, response=None, chunks=1, error=None):
        self.response = response if response is not None else {"id": "abc123"}
        self.chunks = chunks
        self.error = error
        self.body = None
        self.media = None

    def videos(self):
        return self

    def insert(self, *, part, body, media_body):
        self.part = part
        self.body = body
        self.media = media_body
        return FakeInsert(self.response, self.chunks, self.error)


class TestSanitising:
    def test_removes_angle_brackets(self):
        assert "<" not in sanitize_title("제목 <b>굵게</b>")
        assert ">" not in sanitize_description("설명 <script>")

    def test_appends_shorts_tag(self):
        assert sanitize_title("재테크 비밀").endswith("#Shorts")

    def test_does_not_duplicate_shorts_tag(self):
        assert sanitize_title("이미 #shorts 있음").lower().count("#shorts") == 1

    def test_respects_title_limit(self):
        title = sanitize_title("가" * 200)
        assert len(title) <= MAX_TITLE_CHARS
        assert title.endswith("#Shorts")      # 길어도 태그는 살린다

    def test_blank_title_gets_placeholder(self):
        title = sanitize_title("   ")
        assert title.startswith("무제")
        assert title.lower().count("#shorts") == 1     # 자리표시자와 태그가 겹치지 않는다

    def test_collapses_whitespace(self):
        assert sanitize_title("여러   공백\n포함", add_shorts_tag=False) == "여러 공백 포함"

    def test_description_limit(self):
        assert len(sanitize_description("가" * 9000)) == 5000

    def test_tags_deduplicate_case_insensitively(self):
        assert normalise_tags(["재테크", "재테크", "Shorts"]) == ["Shorts", "재테크"]

    def test_tags_respect_total_length(self):
        tags = normalise_tags([f"태그{i}" * 10 for i in range(50)])
        assert sum(len(t) + 1 for t in tags) <= 500

    def test_tags_drop_blanks(self):
        assert "" not in normalise_tags(["", "  ", "유효"])


class TestBuildBody:
    def _request(self, **kwargs):
        defaults = dict(video_path=Path("x.mp4"), title="제목", description="설명")
        defaults.update(kwargs)
        return UploadRequest(**defaults)

    def test_defaults_to_private(self):
        assert build_body(self._request())["status"]["privacyStatus"] == "private"

    def test_public_is_explicit(self):
        assert build_body(self._request(privacy="public"))["status"]["privacyStatus"] == "public"

    def test_rejects_unknown_privacy(self):
        with pytest.raises(ValueError, match="privacy"):
            self._request(privacy="secret")

    def test_publish_at_forces_private(self):
        moment = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
        body = build_body(self._request(privacy="public", publish_at=moment))
        assert body["status"]["privacyStatus"] == "private"      # YouTube 규칙
        assert body["status"]["publishAt"] == "2026-09-15T09:00:00Z"

    def test_naive_publish_at_is_treated_as_utc(self):
        request = self._request(publish_at=datetime(2026, 9, 15, 9, 0))
        assert request.publish_at.tzinfo is timezone.utc

    def test_made_for_kids_flag(self):
        assert build_body(self._request(made_for_kids=True))["status"]["selfDeclaredMadeForKids"] is True

    def test_category_is_string(self):
        assert build_body(self._request(category_id=24))["snippet"]["categoryId"] == "24"


class TestUploadVideo:
    def _request(self, video, **kwargs):
        defaults = dict(video_path=video, title="테스트 제목")
        defaults.update(kwargs)
        return UploadRequest(**defaults)

    def test_successful_upload(self, video):
        service = FakeService({"id": "vid789"})
        result = upload_video(self._request(video), service=service)
        assert isinstance(result, UploadResult)
        assert result.video_id == "vid789"
        assert result.shorts_url == "https://www.youtube.com/shorts/vid789"
        assert result.quota_used == UPLOAD_QUOTA_COST
        assert service.part == "snippet,status"

    def test_resumable_progress_is_reported(self, video):
        seen = []
        upload_video(self._request(video), service=FakeService(chunks=3), on_progress=seen.append)
        assert seen == [0.5, 0.5]

    def test_missing_file(self, tmp_path):
        with pytest.raises(UploadError, match="파일이 없습니다"):
            upload_video(UploadRequest(video_path=tmp_path / "nope.mp4", title="t"), service=FakeService())

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        with pytest.raises(UploadError, match="비어 있습니다"):
            upload_video(UploadRequest(video_path=empty, title="t"), service=FakeService())

    def test_response_without_id(self, video):
        with pytest.raises(UploadError, match="영상 id"):
            upload_video(self._request(video), service=FakeService({}))

    def test_quota_error_is_classified(self, video):
        service = FakeService(error=RuntimeError("quotaExceeded: daily limit"))
        with pytest.raises(QuotaExceededError, match="할당량"):
            upload_video(self._request(video), service=service)

    def test_quota_message_states_daily_cap(self, video):
        service = FakeService(error=RuntimeError("quotaExceeded"))
        try:
            upload_video(self._request(video), service=service)
        except QuotaExceededError as exc:
            assert str(DAILY_UPLOAD_LIMIT) in str(exc)

    def test_auth_error_is_classified(self, video):
        error = RuntimeError("authError: invalid credentials")
        error.resp = type("Resp", (), {"status": 401})()
        with pytest.raises(AuthRequiredError, match="로그인"):
            upload_video(self._request(video), service=FakeService(error=error))

    def test_bad_request_is_classified(self, video):
        error = RuntimeError("invalid title")
        error.resp = type("Resp", (), {"status": 400})()
        with pytest.raises(UploadError, match="거부"):
            upload_video(self._request(video), service=FakeService(error=error))


class TestCredentials:
    def test_missing_token_refuses_silently_in_unattended_mode(self, tmp_path):
        pytest.importorskip("google.oauth2", reason="google-auth 미설치 환경에서는 건너뜀")
        with pytest.raises(AuthRequiredError, match="autoshorts login"):
            uploader.load_credentials(tmp_path / "none.json", allow_interactive=False)

    def test_token_path_can_be_overridden(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_TOKEN_PATH", str(tmp_path / "t.json"))
        assert uploader.default_token_path() == tmp_path / "t.json"

    def test_default_token_path_is_in_home(self, monkeypatch):
        monkeypatch.delenv("AUTOSHORTS_TOKEN_PATH", raising=False)
        assert uploader.default_token_path().name == "youtube_token.json"


class TestShortsEligibility:
    def test_vertical_short_clip_is_fine(self):
        assert check_shorts_eligibility(45, 1080, 1920) == []

    def test_too_long_is_flagged(self):
        assert any("상한" in w for w in check_shorts_eligibility(400, 1080, 1920))

    def test_landscape_is_flagged(self):
        assert any("세로" in w for w in check_shorts_eligibility(45, 1920, 1080))
