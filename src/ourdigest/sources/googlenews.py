"""Google News source: pulls Google News RSS for a search query (no auth)."""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from .base import Source
from ..models import Story


class GoogleNewsSource(Source):
    source_type = "googlenews"

    def __init__(self, name, query, hl="en-US", gl="US"):
        super().__init__(name=name)
        self.query = query
        self.hl = hl
        self.gl = gl

    async def fetch(self, client, *, lookback_hours, limit):
        url = "https://news.google.com/rss/search"
        params = {
            "q": self.query,
            "hl": self.hl,
            "gl": self.gl,
            "ceid": f"{self.gl}:{self.hl.split('-')[0]}",
        }
        resp = await client.get(url, params=params, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        # Use a generous lookback since Google News mixes old and new
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(lookback_hours, 168))
        out = []
        for entry in parsed.entries:
            published = datetime.now(timezone.utc)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pass
            elif hasattr(entry, "published"):
                try:
                    published = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
                except (TypeError, ValueError):
                    pass
            if published < cutoff:
                continue

            title = _clean(entry.get("title", ""))
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            source_name = ""
            if hasattr(entry, "source") and entry.source:
                source_name = _clean(entry.source.get("title", ""))
            if not source_name:
                source_name = "Google News"

            desc = _clean(entry.get("description", ""))
            if len(desc) > 400:
                desc = desc[:397] + "..."

            out.append(Story(
                source=source_name,
                source_type=self.source_type,
                url=link,
                title=title,
                snippet=desc,
                author=source_name,
                published=published,
                score=0,
                comments_url=link,
            ))
            if len(out) >= limit:
                break
        return out


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
