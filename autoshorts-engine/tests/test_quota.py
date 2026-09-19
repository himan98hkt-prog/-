"""할당량 정책 계층 테스트.

이 모듈의 존재 이유가 곧 테스트의 목적이다 — 할당량 숫자가 **코드 상수가 아니라
설정**이어야 하고, 정책이 바뀌어도 호출부가 따라 움직여야 한다.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from autoshorts import trend_finder, uploader
from autoshorts.quota import (
    DEFAULT_POLICY,
    ENDPOINT_BUCKETS,
    QuotaBucket,
    QuotaPolicy,
    describe_policy,
    load_policy,
    policy_from_env,
)


class TestBucket:
    def test_calls_from_explicit_limit(self):
        bucket = QuotaBucket("uploads", unit_cost=1, daily_calls=100)
        assert bucket.calls_allowed() == 100

    def test_calls_derived_from_units(self):
        bucket = QuotaBucket("queries", unit_cost=100, daily_units=10_000)
        assert bucket.calls_allowed() == 100

    def test_unknown_limit_is_none(self):
        assert QuotaBucket("mystery").calls_allowed() is None

    def test_zero_cost_does_not_divide(self):
        """유닛 비용이 0 이면 나눗셈으로 호출 수를 만들지 않는다."""
        assert QuotaBucket("odd", unit_cost=0, daily_units=500).calls_allowed() is None


class TestDefaultPolicy:
    def test_upload_is_its_own_bucket(self):
        """2026 granular quota — videos.insert 는 전용 버킷이다."""
        assert DEFAULT_POLICY.bucket_for("videos.insert").name == "uploads"

    def test_search_is_its_own_bucket(self):
        assert DEFAULT_POLICY.bucket_for("search").name == "search"
        assert DEFAULT_POLICY.bucket_for("search.list").name == "search"

    def test_other_endpoints_share_the_common_bucket(self):
        for endpoint in ("videos", "channels", "playlistItems", "captions"):
            assert DEFAULT_POLICY.bucket_for(endpoint).name == "queries"

    def test_stale_1600_assumption_is_gone(self):
        """예전 하드코딩(1,600 유닛 / 하루 6건)이 남아 있지 않다."""
        assert DEFAULT_POLICY.upload_unit_cost != 1600
        assert DEFAULT_POLICY.daily_upload_limit != 6
        assert DEFAULT_POLICY.daily_upload_limit == 100

    def test_stale_search_100_assumption_is_gone(self):
        assert DEFAULT_POLICY.search_unit_cost != 100

    def test_daily_upload_limit_never_zero(self):
        """정책에 상한이 없으면 보수적으로 1 을 준다 — 0 으로 막아 버리지 않는다."""
        empty = QuotaPolicy(buckets={"queries": QuotaBucket("queries")})
        assert empty.daily_upload_limit == 1

    def test_provenance_is_recorded(self):
        assert DEFAULT_POLICY.verified_on
        assert all(url.startswith("https://") for url in DEFAULT_POLICY.sources)

    def test_to_dict_round_trips_buckets(self):
        payload = DEFAULT_POLICY.to_dict()
        assert set(payload["buckets"]) == {"uploads", "search", "queries"}
        assert payload["buckets"]["uploads"]["calls_allowed"] == 100


class TestEnvOverride:
    def test_daily_calls_override(self):
        policy = policy_from_env({"AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": "500"})
        assert policy.daily_upload_limit == 500
        assert "AUTOSHORTS_YT_UPLOAD_DAILY_CALLS" in policy.overrides

    def test_unit_cost_override(self):
        policy = policy_from_env({"AUTOSHORTS_YT_SEARCH_UNIT_COST": "7"})
        assert policy.cost_for("search") == 7

    def test_queries_units_override(self):
        policy = policy_from_env({"AUTOSHORTS_YT_QUERIES_DAILY_UNITS": "1000000"})
        assert policy.buckets["queries"].daily_units == 1_000_000

    def test_explicit_calls_clears_unit_budget(self):
        """호출 수를 직접 주면 유닛 상한은 의미가 없어 비운다."""
        # queries 버킷은 호출 수 오버라이드를 노출하지 않으므로 uploads 로 확인한다.
        policy = policy_from_env({"AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": "50"})
        bucket = policy.buckets["uploads"]
        assert bucket.daily_calls == 50
        assert bucket.daily_units is None

    def test_garbage_is_ignored(self):
        policy = policy_from_env({"AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": "많이"})
        assert policy.daily_upload_limit == DEFAULT_POLICY.daily_upload_limit
        assert policy.overrides == ()

    def test_non_positive_is_ignored(self):
        for value in ("0", "-3"):
            policy = policy_from_env({"AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": value})
            assert policy.daily_upload_limit == DEFAULT_POLICY.daily_upload_limit

    def test_empty_env_is_default(self):
        assert policy_from_env({}).to_dict()["buckets"] == DEFAULT_POLICY.to_dict()["buckets"]

    def test_load_policy_passes_through(self):
        custom = QuotaPolicy(buckets={"queries": QuotaBucket("queries", daily_units=5)})
        assert load_policy(custom) is custom


class TestDescribe:
    def test_mentions_api_is_source_of_truth(self):
        text = describe_policy(DEFAULT_POLICY)
        assert "API" in text and "최종 진실" in text

    def test_lists_sources_and_date(self):
        text = describe_policy(DEFAULT_POLICY)
        assert DEFAULT_POLICY.verified_on in text
        for url in DEFAULT_POLICY.sources:
            assert url in text

    def test_shows_overrides(self):
        policy = policy_from_env({"AUTOSHORTS_YT_UPLOAD_DAILY_CALLS": "12"})
        assert "AUTOSHORTS_YT_UPLOAD_DAILY_CALLS" in describe_policy(policy)


class TestCallSitesUsePolicy:
    """호출부가 상수를 박지 않고 정책을 읽는지 확인한다."""

    def test_uploader_constants_track_policy(self):
        assert uploader.UPLOAD_QUOTA_COST == DEFAULT_POLICY.upload_unit_cost
        assert uploader.DAILY_UPLOAD_LIMIT == DEFAULT_POLICY.daily_upload_limit

    def test_trend_finder_costs_track_policy(self):
        assert trend_finder.API_COSTS["search"] == DEFAULT_POLICY.cost_for("search")
        assert trend_finder.API_COSTS["videos"] == DEFAULT_POLICY.cost_for("videos")

    def test_client_accounting_follows_injected_policy(self):
        """정책을 바꿔 주면 소모 유닛 집계가 따라 바뀐다."""
        expensive = QuotaPolicy(buckets={
            **DEFAULT_POLICY.buckets,
            "search": replace(DEFAULT_POLICY.buckets["search"], unit_cost=100),
        })

        def transport(url, timeout):
            return 200, b'{"items": []}'

        client = trend_finder.YouTubeClient("k", transport=transport, policy=expensive)
        client.search_video_ids("x", published_after=datetime.now(timezone.utc), max_results=5)
        assert client.quota_used == 100

    def test_quota_error_message_uses_policy_numbers(self):
        narrow = QuotaPolicy(buckets={
            **DEFAULT_POLICY.buckets,
            "uploads": replace(DEFAULT_POLICY.buckets["uploads"], daily_calls=3),
        })
        err = uploader._classify_http_error(RuntimeError("quotaExceeded"), policy=narrow)
        assert isinstance(err, uploader.QuotaExceededError)
        assert "3건" in str(err)
        assert "1600" not in str(err)

    def test_quota_error_says_api_is_the_judge(self):
        err = uploader._classify_http_error(RuntimeError("uploadLimitExceeded"))
        assert "API 응답 기준" in str(err)


def test_endpoint_bucket_table_covers_granular_methods():
    """granular quota 로 분리된 두 메서드가 표에 있어야 한다."""
    assert ENDPOINT_BUCKETS["videos.insert"] == "uploads"
    assert ENDPOINT_BUCKETS["search.list"] == "search"
