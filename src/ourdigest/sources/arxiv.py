"""arXiv source: pulls an arXiv category RSS feed (no auth)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser  # type: ignore[import-untyped]
import httpx

from .base import Source
from ..models import Story


class ArxivSource(Source):
    source_type = "arxiv"

    def __init__(self, name: str, category: str) -> None:
        super().__init__(name=name)
        self.category = category

    async def fetch(
        self,
        client: httpx.AsyncClient,
        *,
        lookback_hours: int,
        limit: int,
    ) -> list[Story]:
        url = f"http://export.arxiv.org/rss/{self.category}"
        resp = await client.get(url, timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[Story] = []
        for entry in parsed.entries[:limit]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "published") and entry.published:
                try:
                    published = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
                except (TypeError, ValueError):
                    published = None
            if published is None:
                published = datetime.now(timezone.utc)
            if published < cutoff:
                continue
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()
            # strip CDATA-ish tags feedparser leaves
            import re
            summary = re.sub(r"<[^>]+>", " ", summary).strip()[:500]
            title = re.sub(r"<[^>]+>", " ", entry.get("title", "")).strip()
            authors = ", ".join(a.get("name", "") for a in entry.get("authors", []))
            out.append(
                Story(
                    source=f"arXiv {self.category}",
                    source_type=self.source_type,
                    url=link,
                    title=title or "(untitled)",
                    snippet=summary,
                    author=authors,
                    published=published,
                    score=0,
                    comments_url=link,
                )
            )
            if len(out) >= limit:
                break
        return out
