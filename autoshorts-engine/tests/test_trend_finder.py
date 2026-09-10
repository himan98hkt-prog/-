"""급상승 탐색 모듈 테스트 — 네트워크·API 키 없이 가짜 transport 로 검증."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from autoshorts import trend_finder
from autoshorts.trend_finder import (
    ChannelNotFoundError,
    InvalidApiKeyError,
    QuotaExceededError,
    TrendVideo,
    YouTubeApiError,
    YouTubeClient,
    build_candidates,
    filter_and_rank,
    find_trending,
    parse_channel_reference,
    parse_iso8601_duration,
    score_video,
    watch_url,
)

NOW = datetime.now(timezone.utc)


def iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeTransport:
    """엔드포인트별 응답을 미리 심어 두는 가짜 HTTP 계층."""

    def __init__(self, responses: dict[str, list | dict], status: int = 200):
        self.responses = responses
        self.status = status
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, timeout: float):
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        endpoint = parsed.path.rsplit("/", 1)[-1]
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        self.calls.append((endpoint, params))

        payload = self.responses.get(endpoint, {})
        if isinstance(payload, list):          # 페이지가 여러 개인 경우 순차 반환
            index = sum(1 for e, _ in self.calls if e == endpoint) - 1
            payload = payload[min(index, len(payload) - 1)]
        return self.status, json.dumps(payload).encode("utf-8")

    def params_for(self, endpoint: str) -> dict[str, str]:
        for name, params in self.calls:
            if name == endpoint:
                return params
        return {}

    def count(self, endpoint: str) -> int:
        return sum(1 for name, _ in self.calls if name == endpoint)


def video_item(video_id, *, views=10000, subs_channel="UC" + "a" * 22, duration="PT10M",
               hours_ago=24, likes=500, live="none", title=None):
    return {
        "id": video_id,
        "snippet": {
            "title": title or f"영상 {video_id}",
            "channelId": subs_channel,
            "channelTitle": "테스트 채널",
            "publishedAt": iso(hours_ago),
            "liveBroadcastContent": live,
        },
        "statistics": {"viewCount": str(views), "likeCount": str(likes), "commentCount": "10"},
        "contentDetails": {"duration": duration},
    }


def channel_item(channel_id, *, subscribers=10000, hidden=False):
    stats = {"subscriberCount": str(subscribers), "videoCount": "100"}
    if hidden:
        stats = {"hiddenSubscriberCount": True}
    return {"id": channel_id, "snippet": {"title": "테스트 채널"}, "statistics": stats}


class TestDurationParsing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("PT10M", 600.0),
            ("PT1H2M3S", 3723.0),
            ("PT45S", 45.0),
            ("PT1H", 3600.0),
            ("P1DT2H", 93600.0),
            ("PT0S", 0.0),
            ("PT1M30.5S", 90.5),
        ],
    )
    def test_parses(self, text, expected):
        assert parse_iso8601_duration(text) == expected

    @pytest.mark.parametrize("text", [None, "", "10분", "garbage", "P"])
    def test_unparseable_is_zero(self, text):
        # 0 이면 길이 필터에서 자연히 걸러진다
        assert parse_iso8601_duration(text) == 0.0


class TestChannelReference:
    @pytest.mark.parametrize(
        ("text", "kind", "value"),
        [
            ("UCabcdefghijklmnopqrstuv", "channel_id", "UCabcdefghijklmnopqrstuv"),
            ("@노마드코더", "handle", "@노마드코더"),
            ("https://www.youtube.com/@handle", "handle", "@handle"),
            ("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv", "channel_id", "UCabcdefghijklmnopqrstuv"),
            ("https://youtube.com/c/SomeName", "username", "SomeName"),
            ("https://www.youtube.com/user/LegacyName", "username", "LegacyName"),
            ("youtube.com/@bare", "handle", "@bare"),
        ],
    )
    def test_detects_channels(self, text, kind, value):
        assert parse_channel_reference(text) == (kind, value)

    @pytest.mark.parametrize("text", ["재테크", "python tutorial", "", "   ", "https://example.com/@x"])
    def test_treats_rest_as_keyword(self, text):
        assert parse_channel_reference(text)[0] == "query"

    def test_url_with_query_string(self):
        kind, value = parse_channel_reference("https://www.youtube.com/@handle?sub_confirmation=1")
        assert (kind, value) == ("handle", "@handle")


class TestScoring:
    def test_zero_ratio_scores_zero(self):
        assert score_video(0.0, 1, 336) == 0.0

    def test_fresher_wins_at_equal_ratio(self):
        window = 336.0
        assert score_video(3.0, 2, window) > score_video(3.0, 300, window)

    def test_higher_ratio_wins_at_equal_age(self):
        assert score_video(5.0, 24, 336) > score_video(2.0, 24, 336)

    def test_freshness_penalty_is_capped(self):
        # 아무리 오래돼도 70% 감점까지만 — V/S 가 압도적이면 여전히 올라온다
        assert score_video(10.0, 10_000, 336) == pytest.approx(10.0 * 0.3)

    def test_engagement_boost_is_capped(self):
        base = score_video(2.0, 0, 336, engagement_rate=0.0)
        assert score_video(2.0, 0, 336, engagement_rate=0.5) == pytest.approx(base * 1.2)

    def test_negative_age_is_clamped(self):
        assert score_video(2.0, -50, 336) == pytest.approx(2.0)


class TestTrendVideo:
    def test_vs_ratio(self):
        assert TrendVideo("v", view_count=50_000, subscriber_count=10_000).vs_ratio == 5.0

    def test_vs_ratio_without_subscribers_is_zero(self):
        assert TrendVideo("v", view_count=50_000, subscriber_count=0).vs_ratio == 0.0

    def test_url_format(self):
        assert TrendVideo("abc123").url == "https://www.youtube.com/watch?v=abc123"
        assert watch_url("xyz") == "https://www.youtube.com/watch?v=xyz"

    def test_views_per_day(self):
        video = TrendVideo("v", view_count=4800, published_at=NOW - timedelta(hours=48))
        assert video.views_per_day == pytest.approx(2400, rel=0.05)

    def test_engagement_rate(self):
        assert TrendVideo("v", view_count=1000, like_count=50).engagement_rate == 0.05

    def test_to_dict_is_json_serialisable(self):
        video = TrendVideo("v", title="제목", view_count=100, subscriber_count=50,
                           published_at=NOW, duration_seconds=600)
        assert json.loads(json.dumps(video.to_dict(), ensure_ascii=False))["url"].endswith("v=v")


class TestClientErrors:
    def test_missing_key_is_actionable(self):
        with pytest.raises(InvalidApiKeyError, match="YOUTUBE_API_KEY"):
            YouTubeClient("")

    def test_quota_exceeded(self):
        transport = FakeTransport(
            {"search": {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}},
            status=403,
        )
        client = YouTubeClient("k", transport=transport)
        with pytest.raises(QuotaExceededError, match="할당량"):
            client.search_video_ids("x", published_after=NOW)

    def test_invalid_key(self):
        transport = FakeTransport(
            {"search": {"error": {"message": "bad key", "errors": [{"reason": "keyInvalid"}]}}},
            status=400,
        )
        with pytest.raises(InvalidApiKeyError, match="API 키"):
            YouTubeClient("k", transport=transport).search_video_ids("x", published_after=NOW)

    def test_generic_http_error(self):
        transport = FakeTransport({"videos": {"error": {"message": "boom"}}}, status=500)
        with pytest.raises(YouTubeApiError, match="HTTP 500"):
            YouTubeClient("k", transport=transport).fetch_videos(["a"])

    def test_unparseable_body(self):
        def broken(url, timeout):
            return 200, b"<html>not json</html>"

        with pytest.raises(YouTubeApiError, match="해석하지 못했습니다"):
            YouTubeClient("k", transport=broken).fetch_videos(["a"])

    def test_api_key_never_appears_in_error_text(self):
        transport = FakeTransport({"videos": {"error": {"message": "boom"}}}, status=500)
        try:
            YouTubeClient("SUPER-SECRET-KEY", transport=transport).fetch_videos(["a"])
        except YouTubeApiError as exc:
            assert "SUPER-SECRET-KEY" not in str(exc)


class TestClientCalls:
    def test_search_sends_window_and_type(self):
        transport = FakeTransport({"search": {"items": [{"id": {"videoId": "v1"}}]}})
        client = YouTubeClient("k", transport=transport)
        ids = client.search_video_ids("재테크", published_after=NOW - timedelta(days=7), max_results=10)
        params = transport.params_for("search")
        assert ids == ["v1"]
        assert params["type"] == "video"
        assert params["q"] == "재테크"
        assert params["publishedAfter"].endswith("Z")

    def test_search_paginates(self):
        transport = FakeTransport({
            "search": [
                {"items": [{"id": {"videoId": f"v{i}"}} for i in range(50)], "nextPageToken": "p2"},
                {"items": [{"id": {"videoId": f"w{i}"}} for i in range(10)]},
            ]
        })
        client = YouTubeClient("k", transport=transport)
        ids = client.search_video_ids("x", published_after=NOW, max_results=60)
        assert len(ids) == 60
        assert transport.count("search") == 2

    def test_videos_are_batched_by_fifty(self):
        transport = FakeTransport({"videos": {"items": []}})
        client = YouTubeClient("k", transport=transport)
        client.fetch_videos([f"v{i}" for i in range(120)])
        assert transport.count("videos") == 3          # 50 + 50 + 20

    def test_duplicate_ids_are_collapsed(self):
        transport = FakeTransport({"channels": {"items": []}})
        client = YouTubeClient("k", transport=transport)
        client.fetch_channels(["UC1"] * 80)
        assert transport.count("channels") == 1

    def test_quota_accounting(self):
        transport = FakeTransport({
            "search": {"items": [{"id": {"videoId": "v1"}}]},
            "videos": {"items": []},
            "channels": {"items": []},
        })
        client = YouTubeClient("k", transport=transport)
        client.search_video_ids("x", published_after=NOW, max_results=5)
        client.fetch_videos(["v1"])
        client.fetch_channels(["UC1"])
        assert client.quota_used == 102               # 100 + 1 + 1

    def test_resolve_handle_uses_cheap_endpoint(self):
        transport = FakeTransport({"channels": {"items": [{"id": "UCxyz"}]}})
        client = YouTubeClient("k", transport=transport)
        assert client.resolve_channel_id("@someone") == "UCxyz"
        assert transport.params_for("channels")["forHandle"] == "@someone"
        assert client.quota_used == 1                 # 검색(100)을 쓰지 않는다

    def test_raw_channel_id_costs_nothing(self):
        transport = FakeTransport({})
        client = YouTubeClient("k", transport=transport)
        assert client.resolve_channel_id("UCabcdefghijklmnopqrstuv") == "UCabcdefghijklmnopqrstuv"
        assert client.quota_used == 0

    def test_handle_falls_back_to_search(self):
        transport = FakeTransport({
            "channels": {"items": []},
            "search": {"items": [{"id": {"channelId": "UCfound"}}]},
        })
        client = YouTubeClient("k", transport=transport)
        assert client.resolve_channel_id("@missing") == "UCfound"

    def test_unresolvable_channel_raises(self):
        transport = FakeTransport({"channels": {"items": []}, "search": {"items": []}})
        with pytest.raises(ChannelNotFoundError):
            YouTubeClient("k", transport=transport).resolve_channel_id("@nobody")

    def test_uploads_playlist_lookup(self):
        transport = FakeTransport({
            "channels": {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]}
        })
        assert YouTubeClient("k", transport=transport).uploads_playlist_id("UC1") == "UU123"

    def test_uploads_stops_at_window_edge(self):
        transport = FakeTransport({
            "playlistItems": [{
                "items": [
                    {"contentDetails": {"videoId": "new1", "videoPublishedAt": iso(2)}},
                    {"contentDetails": {"videoId": "new2", "videoPublishedAt": iso(20)}},
                    {"contentDetails": {"videoId": "old1", "videoPublishedAt": iso(1000)}},
                ],
                "nextPageToken": "p2",
            }, {"items": []}],
        })
        client = YouTubeClient("k", transport=transport)
        ids = client.recent_upload_ids("UU1", published_after=NOW - timedelta(days=7), max_results=50)
        assert ids == ["new1", "new2"]                # 기간 밖을 만나면 더 넘기지 않는다
        assert transport.count("playlistItems") == 1


class TestBuildAndFilter:
    def test_hidden_subscriber_count_yields_zero(self):
        videos = build_candidates([video_item("v1")], {"UC" + "a" * 22: channel_item("UC" + "a" * 22, hidden=True)})
        assert videos[0].subscriber_count == 0

    def test_missing_channel_is_tolerated(self):
        videos = build_candidates([video_item("v1")], {})
        assert videos[0].subscriber_count == 0 and videos[0].video_id == "v1"

    def test_malformed_stats_default_to_zero(self):
        item = video_item("v1")
        item["statistics"] = {"viewCount": "not-a-number"}
        assert build_candidates([item], {})[0].view_count == 0

    def _candidate(self, **kwargs):
        defaults = dict(video_id="v", view_count=50_000, subscriber_count=10_000,
                        duration_seconds=600, published_at=NOW - timedelta(hours=24), like_count=1000)
        defaults.update(kwargs)
        return TrendVideo(**defaults)

    def test_filters_tiny_channels(self):
        # 구독자 10명 / 조회수 5000 이면 V/S 500 이지만 의미가 없다
        tiny = self._candidate(subscriber_count=10, view_count=5000)
        assert filter_and_rank([tiny], window_hours=336) == []

    def test_filters_hidden_subscriber_videos(self):
        assert filter_and_rank([self._candidate(subscriber_count=0)], window_hours=336) == []

    def test_filters_shorts_and_short_videos(self):
        assert filter_and_rank([self._candidate(duration_seconds=45)], window_hours=336) == []

    def test_respects_max_duration(self):
        long_video = self._candidate(duration_seconds=7200)
        assert filter_and_rank([long_video], window_hours=336, max_duration=3600) == []
        assert filter_and_rank([long_video], window_hours=336) != []

    def test_filters_low_vs_ratio(self):
        weak = self._candidate(view_count=1000, subscriber_count=100_000)   # V/S 0.01
        assert filter_and_rank([weak], window_hours=336, min_vs_ratio=1.0) == []

    def test_filters_low_views(self):
        assert filter_and_rank([self._candidate(view_count=50)], window_hours=336) == []

    def test_ranks_by_score_and_assigns_rank(self):
        hot = self._candidate(video_id="hot", view_count=100_000, subscriber_count=10_000)
        mild = self._candidate(video_id="mild", view_count=20_000, subscriber_count=10_000)
        ranked = filter_and_rank([mild, hot], window_hours=336)
        assert [v.video_id for v in ranked] == ["hot", "mild"]
        assert [v.rank for v in ranked] == [1, 2]

    def test_limit_is_applied(self):
        pool = [self._candidate(video_id=f"v{i}", view_count=20_000 + i * 1000) for i in range(10)]
        assert len(filter_and_rank(pool, window_hours=336, limit=3)) == 3


class TestFindTrending:
    def _transport(self, **overrides):
        channel = "UC" + "a" * 22
        responses = {
            "search": {"items": [{"id": {"videoId": "hot"}}, {"id": {"videoId": "mild"}}]},
            "videos": {"items": [
                video_item("hot", views=90_000, subs_channel=channel, hours_ago=6, title="떡상 영상"),
                video_item("mild", views=12_000, subs_channel=channel, hours_ago=200, title="보통 영상"),
            ]},
            "channels": {"items": [channel_item(channel, subscribers=10_000)]},
        }
        responses.update(overrides)
        return FakeTransport(responses)

    def test_keyword_search_end_to_end(self):
        transport = self._transport()
        client = YouTubeClient("k", transport=transport)
        videos, quota = find_trending("재테크", api_key="k", client=client)
        assert [v.video_id for v in videos] == ["hot", "mild"]
        assert videos[0].rank == 1
        assert videos[0].vs_ratio == 9.0
        assert videos[0].url == "https://www.youtube.com/watch?v=hot"
        assert quota == 102                            # search 100 + videos 1 + channels 1

    def test_channel_mode_avoids_expensive_search(self):
        channel = "UC" + "a" * 22
        transport = FakeTransport({
            "channels": [
                {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
                {"items": [channel_item(channel, subscribers=10_000)]},
            ],
            "playlistItems": {"items": [
                {"contentDetails": {"videoId": "hot", "videoPublishedAt": iso(5)}},
            ]},
            "videos": {"items": [video_item("hot", views=90_000, subs_channel=channel, hours_ago=5)]},
        })
        client = YouTubeClient("k", transport=transport)
        videos, quota = find_trending(f"https://www.youtube.com/channel/{channel}", api_key="k", client=client)
        assert [v.video_id for v in videos] == ["hot"]
        assert transport.count("search") == 0
        assert quota == 4                              # 검색 100 유닛을 쓰지 않는다

    def test_live_broadcasts_are_excluded(self):
        channel = "UC" + "a" * 22
        transport = self._transport(videos={"items": [
            video_item("live1", views=90_000, subs_channel=channel, hours_ago=1, live="live"),
            video_item("hot", views=90_000, subs_channel=channel, hours_ago=6),
        ]})
        client = YouTubeClient("k", transport=transport)
        videos, _ = find_trending("키워드", api_key="k", client=client)
        assert [v.video_id for v in videos] == ["hot"]

    def test_no_results_returns_empty(self):
        transport = FakeTransport({"search": {"items": []}})
        client = YouTubeClient("k", transport=transport)
        videos, quota = find_trending("없는키워드", api_key="k", client=client)
        assert videos == [] and quota == 100

    def test_force_channel_mode(self):
        # 일반 키워드를 채널로 강제하면 핸들 조회를 건너뛰고 곧장 검색으로 해석한다
        transport = FakeTransport({
            "channels": [
                {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]},
                {"items": [channel_item("UC" + "a" * 22, subscribers=10_000)]},
            ],
            "search": {"items": [{"id": {"channelId": "UCfound"}}]},
            "playlistItems": {"items": [{"contentDetails": {"videoId": "hot", "videoPublishedAt": iso(5)}}]},
            "videos": {"items": [video_item("hot", views=90_000, hours_ago=5)]},
        })
        client = YouTubeClient("k", transport=transport)
        videos, _ = find_trending("채널이름", api_key="k", as_channel=True, client=client)
        assert transport.count("playlistItems") == 1   # 채널 경로를 탔다
        assert videos

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError, match="입력"):
            find_trending("   ", api_key="k")

    def test_window_is_passed_to_search(self):
        transport = self._transport()
        client = YouTubeClient("k", transport=transport)
        find_trending("키워드", api_key="k", days=3, client=client)
        published_after = transport.params_for("search")["publishedAfter"]
        parsed = datetime.strptime(published_after, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert 2.9 < (NOW - parsed).total_seconds() / 86400 < 3.1
