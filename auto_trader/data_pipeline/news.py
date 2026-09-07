"""네이버 뉴스 검색 API로 종목 뉴스 수집.

- 키가 없거나 호출이 실패하면 **빈 리스트를 반환**한다(예외를 위로 전파하지 않는다).
  뉴스는 보조 정보이므로 매매 사이클을 막아서는 안 된다.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from config.loader import AiConfig, EnvConfig
from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("news")

SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
HTTP_TIMEOUT = 8
MAX_DISPLAY = 100  # 네이버 API 1회 최대 조회 건수
TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """`<b>` 등 태그 제거 + HTML 엔티티 복원 + 공백 정리."""
    return re.sub(r"\s+", " ", html.unescape(TAG_PATTERN.sub("", text or ""))).strip()


def _parse_pubdate(raw: str) -> datetime | None:
    """RFC 2822 형식(`Mon, 07 Sep 2026 09:30:00 +0900`) → KST datetime."""
    try:
        return parsedate_to_datetime(raw).astimezone(KST)
    except (TypeError, ValueError):
        return None


def fetch_news(
    query: str,
    env: EnvConfig,
    ai: AiConfig,
    *,
    now: datetime | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """종목명으로 뉴스를 검색해 최근 기사만 돌려준다.

    Returns:
        `[{"title": ..., "published": ISO8601, "summary": ...}]` — 최신순,
        최대 `ai.news_max_items` 건. 실패 시 빈 리스트.
    """
    if not env.news_enabled:
        logger.debug("네이버 API 키가 없어 뉴스를 건너뜁니다")
        return []
    if not query or ai.news_max_items <= 0:
        return []

    headers = {
        "X-Naver-Client-Id": env.naver_client_id or "",
        "X-Naver-Client-Secret": env.naver_client_secret or "",
    }
    params = {
        "query": query,
        # 시간 필터로 걸러낼 것을 감안해 넉넉히 받아온다.
        "display": min(max(ai.news_max_items * 4, 10), MAX_DISPLAY),
        "start": 1,
        "sort": "date",  # 최신순
    }

    try:
        client = session or requests
        response = client.get(SEARCH_URL, headers=headers, params=params, timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            logger.warning("뉴스 검색 실패 (HTTP %s) — 뉴스 없이 진행합니다", response.status_code)
            return []
        items = response.json().get("items") or []
    except (requests.RequestException, ValueError) as exc:
        logger.warning("뉴스 검색 오류(%s) — 뉴스 없이 진행합니다", exc)
        return []

    cutoff = (now or datetime.now(KST)) - timedelta(hours=ai.news_lookback_hours)
    articles: list[dict[str, Any]] = []
    for item in items:
        published = _parse_pubdate(item.get("pubDate", ""))
        if published is None or published < cutoff:
            continue
        title = strip_tags(item.get("title", ""))
        if not title:
            continue
        articles.append(
            {
                "title": title,
                "published": published.isoformat(timespec="seconds"),
                "summary": strip_tags(item.get("description", "")),
            }
        )
        if len(articles) >= ai.news_max_items:
            break

    logger.debug("뉴스 %d건 수집: %s", len(articles), query)
    return articles
