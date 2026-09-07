"""뉴스 수집 테스트 — 실패해도 매매를 막지 않는 것이 핵심."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests

from config.loader import AiConfig
from data_pipeline.news import fetch_news, strip_tags
from tests.conftest import FakeResponse, make_env

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=KST)

AI = AiConfig(timeout_sec=60, max_retries=2, min_confidence=0.6,
              news_max_items=3, news_lookback_hours=24)


def env_with_naver(**kw):
    return make_env(naver_client_id="id", naver_client_secret="secret", **kw)


def item(title: str, hours_ago: float, description: str = "본문 요약"):
    published = NOW - timedelta(hours=hours_ago)
    return {
        "title": title,
        "description": description,
        "pubDate": published.strftime("%a, %d %b %Y %H:%M:%S +0900"),
        "link": "https://n.news.naver.com/1",
    }


class StubSession:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": params})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_strip_tags_removes_markup_and_entities():
    assert strip_tags("<b>삼성전자</b> &quot;신고가&quot;  경신") == '삼성전자 "신고가" 경신'
    assert strip_tags("") == ""


def test_returns_empty_without_api_key():
    session = StubSession(FakeResponse({"items": [item("제목", 1)]}))
    assert fetch_news("삼성전자", make_env(), AI, now=NOW, session=session) == []
    assert session.calls == [], "키가 없으면 호출조차 하지 않는다"


def test_parses_and_strips_articles():
    session = StubSession(
        FakeResponse({"items": [item("<b>삼성전자</b> 신고가", 2, "<b>반도체</b> 업황 개선")]})
    )
    articles = fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session)

    assert len(articles) == 1
    assert articles[0]["title"] == "삼성전자 신고가"
    assert articles[0]["summary"] == "반도체 업황 개선"
    assert articles[0]["published"].startswith("2026-09-07T10:00")
    assert session.calls[0]["headers"]["X-Naver-Client-Id"] == "id"
    assert session.calls[0]["params"]["sort"] == "date"


def test_filters_articles_outside_lookback_window():
    session = StubSession(
        FakeResponse({"items": [item("오래된 기사", 30), item("최근 기사", 3)]})
    )
    articles = fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session)
    assert [a["title"] for a in articles] == ["최근 기사"]


def test_respects_max_items():
    session = StubSession(FakeResponse({"items": [item(f"기사{i}", i) for i in range(10)]}))
    articles = fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session)
    assert len(articles) == AI.news_max_items


def test_http_error_returns_empty_list():
    session = StubSession(FakeResponse(None, status_code=401, text="unauthorized"))
    assert fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session) == []


def test_network_error_does_not_propagate():
    session = StubSession(requests.ConnectionError("network down"))
    assert fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session) == []


def test_malformed_pubdate_is_skipped():
    bad = {"title": "제목", "description": "요약", "pubDate": "언젠가"}
    session = StubSession(FakeResponse({"items": [bad, item("정상 기사", 1)]}))
    articles = fetch_news("삼성전자", env_with_naver(), AI, now=NOW, session=session)
    assert [a["title"] for a in articles] == ["정상 기사"]


def test_zero_max_items_skips_call():
    ai = AiConfig(timeout_sec=60, max_retries=2, min_confidence=0.6,
                  news_max_items=0, news_lookback_hours=24)
    session = StubSession(FakeResponse({"items": [item("기사", 1)]}))
    assert fetch_news("삼성전자", env_with_naver(), ai, now=NOW, session=session) == []
    assert session.calls == []
