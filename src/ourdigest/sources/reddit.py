"""Reddit source: pulls /r/<subreddit> JSON, no auth required."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

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
        url = f"https://www.reddit.com/r/{self.subreddit}/{self.sort}.json"
        params = {"t": self.time, "limit": str(min(limit, 100))}
        headers = {"User-Agent": "ourdigest/0.1 (by /u/ourdigest)"}
        resp = await client.get(url, params=params, headers=headers, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        children = data.get("data", {}).get("children", []) or []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[Story] = []
        for child in children:
            d: dict[str, Any] = child.get("data") or {}
            permalink = d.get("permalink") or ""
            full_url = f"https://www.reddit.com{permalink}" if permalink else d.get("url", "")
            if not full_url:
                continue
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if created < cutoff:
                continue
            out.append(
                Story(
                    source=f"r/{self.subreddit}",
                    source_type=self.source_type,
                    url=full_url,
                    title=d.get("title", "").strip(),
                    snippet=(d.get("selftext") or "")[:500],
                    author=d.get("author", ""),
                    published=created,
                    score=int(d.get("score", 0) or 0),
                    comments_url=full_url,
                )
            )
            if len(out) >= limit:
                break
        return out
