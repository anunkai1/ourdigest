"""Reddit source: pulls /r/<subreddit> RSS feed (no auth required).

Reddit's anonymous JSON API now returns 403 for most clients.
RSS feeds are still open and provide title/link/author/date.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from io import BytesIO

import feedparser
import httpx

from .base import Source
from ..models import Story


class RedditSource(Source):
    source_type = "reddit"

    def __init__(
        self,
        name: str,
        subreddit: str,
        sort: str = "top",
        time: str = "day",
    ) -> None:
        super().__init__(name=name)
        if sort not in {"hot", "new", "top", "rising"}:
            raise ValueError(f"reddit sort must be one of hot/new/top/rising, got {sort!r}")
        if time not in {"hour", "day", "week", "month", "year", "all"}:
            raise ValueError(f"reddit time must be hour/day/week/month/year/all, got {time!r}")
        self.subreddit = subreddit
        self.sort = sort
        self.time = time

    async def fetch(
        self,
        client: httpx.AsyncClient,
        *,
        lookback_hours: int,
        limit: int,
    ) -> list[Story]:
        # Reddit RSS: https://www.reddit.com/r/<sub>/.rss?sort=top&t=day
        url = f"https://www.reddit.com/r/{self.subreddit}/.rss"
        params = {"sort": self.sort, "t": self.time}
        headers = {"User-Agent": "ourdigest/0.1 (by /u/ourdigest)"}
        resp = await client.get(
            url, params=params, headers=headers, timeout=15.0, follow_redirects=True
        )
        resp.raise_for_status()
        feed = feedparser.parse(BytesIO(resp.content))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[Story] = []
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            published = cutoff + timedelta(seconds=1)  # default: keep
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pass
            if published < cutoff:
                continue
            author = (entry.get("author") or "").strip()
            snippet = ""
            if hasattr(entry, "summary"):
                snippet = (entry.summary or "")[:500]
            out.append(
                Story(
                    source=f"r/{self.subreddit}",
                    source_type=self.source_type,
                    url=link,
                    title=title,
                    snippet=snippet,
                    author=author,
                    published=published,
                    score=0,
                    comments_url=link,
                )
            )
            if len(out) >= limit:
                break
        return out
