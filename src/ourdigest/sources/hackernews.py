"""HackerNews source: HN Algolia search API (no auth)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from .base import Source
from ..models import Story


class HackerNewsSource(Source):
    source_type = "hackernews"

    def __init__(
        self,
        name: str,
        query: str | None = None,
        query_tags: list[str] | None = None,
        limit: int = 30,
    ) -> None:
        super().__init__(name=name)
        self.query = query
        self.query_tags = query_tags or ["front_page"]
        self.limit = max(1, min(limit, 100))

    async def fetch(
        self,
        client: httpx.AsyncClient,
        *,
        lookback_hours: int,
        limit: int,
    ) -> list[Story]:
        if "front_page" in self.query_tags:
            url = "https://hn.algolia.com/api/v1/search?tags=front_page"
        else:
            tag_param = ",".join(t for t in self.query_tags if t != "front_page") or "story"
            url = f"https://hn.algolia.com/api/v1/search_by_date?tags={tag_param}"
            if self.query:
                url += f"&query={self.query}"

        params: dict[str, Any] = {
            "hitsPerPage": str(min(self.limit, limit, 100)),
        }
        resp = await client.get(url, params=params, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", []) or []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[Story] = []
        for h in hits:
            ts = h.get("created_at_i") or 0
            created = datetime.fromtimestamp(ts, tz=timezone.utc)
            if created < cutoff:
                continue
            story_url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
            out.append(
                Story(
                    source="Hacker News",
                    source_type=self.source_type,
                    url=story_url,
                    title=h.get("title", "").strip() or "(no title)",
                    snippet=(h.get("story_text") or "")[:500],
                    author=h.get("author", ""),
                    published=created,
                    score=int(h.get("points", 0) or 0),
                    comments_url=f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                )
            )
            if len(out) >= limit:
                break
        return out
