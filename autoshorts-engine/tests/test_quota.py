"""할당량 정책 계층 테스트.

여기서 지키려는 성질은 "숫자가 얼마냐" 가 아니라 다음 두 가지다.
  1. 할당량이 코드에 박히지 않고 설정으로 바뀐다.
  2. 최종 판정은 API 응답이며, 클라이언트 추정치를 단정하지 않는다.
"""

from __future__ import annotations

import pytest

from autoshorts import quota, uploader
from autoshorts.quota import (
    QUOTA_DOC_URLS,
    QuotaPolicy,
    SearchQuotaPolicy,
    UploadQuotaPolicy,
    load_quota_policy,
)
from autoshorts.uploader import QuotaExceededError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "AUTOSHORTS_UPLOAD_COST_PER_CALL",
        "AUTOSHORTS_UPLOAD_DAILY_LIMIT",
        "AUTOSHORTS_UPLOAD_LOCAL_GUARD",
        "AUTOSHORTS_SEARCH_DAILY_UNITS",
        "AUTOSHORTS_QUOTA_VERIFIED",
    ):
        monkeypatch.delenv(name, raising=False)


class TestDefaults:
    def test_upload_is_not_derived_from_query_quota(self):
        """업로드는 별도 버킷이다. 10,000÷1,600 식 계산을 하지 않는다."""
        policy = load_quota_policy()
        assert policy.upload.cost_per_call == 1
        assert policy.upload.daily_uploads == 100
        # 과거의 잘못된 모델(하루 6건)이 되살아나지 않도록 고정한다
        assert policy.upload.daily_uploads != policy.search.daily_units // 1600

    def test_defaults_are_marked_unverified(self):
        policy = load_quota_policy()
        assert policy.verified is False
        assert "미재검증" in policy.source
        assert "미검증" in policy.describe_upload_limit()

    def test_doc_urls_recorded_for_manual_verification(self):
        assert any("determine_quota_cost" in url for url in QUOTA_DOC_URLS)
        assert any("videos/insert" in url for url in QUOTA_DOC_URLS)


class TestEnvironmentOverride:
    def test_daily_limit_is_configurable(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_DAILY_LIMIT", "42")
        assert load_quota_policy().upload.daily_uploads == 42

    def test_override_marks_source(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_DAILY_LIMIT", "42")
        assert "환경변수" in load_quota_policy().source

    def test_cost_per_call_is_configurable(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_COST_PER_CALL", "1600")
        assert load_quota_policy().upload.cost_per_call == 1600

    def test_local_guard_can_be_disabled(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_LOCAL_GUARD", "false")
        assert load_quota_policy().upload.enforce_local_guard is False

    def test_guard_enabled_by_default(self):
        assert load_quota_policy().upload.enforce_local_guard is True

    def test_verified_flag_can_be_set(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_QUOTA_VERIFIED", "1")
        policy = load_quota_policy()
        assert policy.verified is True
        assert "미검증" not in policy.describe_upload_limit()

    @pytest.mark.parametrize("bad", ["", "abc", "0", "-5"])
    def test_bad_values_fall_back_to_default(self, monkeypatch, bad):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_DAILY_LIMIT", bad)
        assert load_quota_policy().upload.daily_uploads == 100


class TestSerialisation:
    def test_to_dict_is_reportable(self):
        data = load_quota_policy().to_dict()
        assert data["upload"]["daily_uploads"] == 100
        assert data["verified"] is False
        assert "source" in data


class TestUploaderIntegration:
    def test_module_constants_come_from_policy(self):
        assert uploader.UPLOAD_QUOTA_COST == load_quota_policy().upload.cost_per_call
        assert uploader.DAILY_UPLOAD_LIMIT == load_quota_policy().upload.daily_uploads

    def test_accessor_reflects_environment(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_DAILY_LIMIT", "7")
        assert uploader.upload_quota_policy().daily_uploads == 7

    def test_quota_error_defers_to_api_response(self):
        error = uploader._classify_http_error(RuntimeError("quotaExceeded"))
        assert isinstance(error, QuotaExceededError)
        message = str(error)
        assert "API 가 응답" in message
        assert "프로젝트마다 다를 수 있습니다" in message
        # 낡은 모델을 단정하던 문구가 남아 있지 않아야 한다
        assert "1600" not in message and "하루 6건" not in message

    def test_error_message_follows_policy_override(self, monkeypatch):
        monkeypatch.setenv("AUTOSHORTS_UPLOAD_DAILY_LIMIT", "250")
        assert "250" in str(uploader._classify_http_error(RuntimeError("quotaExceeded")))


class TestNoStaleConstantsInSource:
    """소스와 사용자 문서에 낡은 가정이 되살아나지 않도록 고정한다."""

    def test_uploader_has_no_hardcoded_1600(self):
        from pathlib import Path

        source = Path(uploader.__file__).read_text(encoding="utf-8")
        assert "1600" not in source
        assert "10_000 //" not in source

    def test_user_docs_do_not_claim_six_per_day(self):
        from pathlib import Path

        root = Path(uploader.__file__).resolve().parents[1]
        for name in ("README.md", "시작하기.txt"):
            path = root / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            assert "하루 6건" not in text, f"{name} 에 낡은 한도 문구가 남아 있습니다"
            assert "1,600 유닛" not in text, f"{name} 에 낡은 비용 문구가 남아 있습니다"
