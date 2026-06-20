"""Reddit source: scrapes old.reddit.com HTML (no API needed, includes scores)."""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta

import httpx

from .base import Source
from ..models import Story

# Match from one thing div to the next (or to the footer)
_THING_START_RE = re.compile(
    r'<div\s[^>]*class="[^"]*\sthing\s[^"]*"[^>]*>'
)

_ATTR_RE = re.compile(r'(data-\w+)="([^"]*)"')

_TITLE_A_RE = re.compile(
    r'<a\s[^>]*class="(?:title\s|[^"]*\stitle\s)[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL,
)


def _parse_attrs(tag: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(tag)}


class RedditSource(Source):
    source_type = "reddit"

    def __init__(self, name, subreddit, sort="top", time="day"):
        super().__init__(name=name)
        if sort not in {"hot", "new", "top", "rising"}:
            raise ValueError(f"sort must be hot/new/top/rising, got {sort!r}")
        if time not in {"hour", "day", "week", "month", "year", "all"}:
            raise ValueError(f"time must be hour/day/week/month/year/all, got {time!r}")
        self.subreddit = subreddit
        self.sort = sort
        self.time = time

    async def fetch(self, client, *, lookback_hours, limit):
        url = f"https://old.reddit.com/r/{self.subreddit}/{self.sort}/"
        params = {"sort": self.sort, "t": self.time}
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out = []

        # Find all thing div start positions
        starts = list(_THING_START_RE.finditer(html))
        for i, start_match in enumerate(starts):
            tag = start_match.group(0)
            start_pos = start_match.end()
            
            # End position: next thing div start, or end of listing area
            if i + 1 < len(starts):
                end_pos = starts[i + 1].start()
            else:
                # Last thing: search for the footer / clearleft after it
                footer = re.search(r'<div\sclass="clearleft">', html[start_pos:])
                if footer:
                    end_pos = start_pos + footer.start()
                else:
                    end_pos = len(html)
            
            block = html[start_pos:end_pos]
            attrs = _parse_attrs(tag)

            ts_str = attrs.get("data-timestamp", "")
            if not ts_str:
                continue
            try:
                ts = int(ts_str) / 1000.0
                published = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, OSError):
                continue
            if published < cutoff:
                continue

            title_match = _TITLE_A_RE.search(block)
            if not title_match:
                continue
            title = _clean_html(title_match.group(1)).strip()
            if not title:
                continue

            score = int(attrs.get("data-score", "0"))
            permalink = attrs.get("data-permalink", "")
            link_url = attrs.get("data-url", "")
            author = attrs.get("data-author", "")
            comments = attrs.get("data-comments-count", "0")
            domain = attrs.get("data-domain", "")

            if permalink:
                full_url = f"https://old.reddit.com{permalink}"
            elif link_url and link_url.startswith("http"):
                full_url = link_url
            else:
                continue

            is_self = domain.startswith("self.") if domain else bool(permalink and "/r/" in permalink)
            snippet = f"[self post, {comments} comments]" if is_self else f"[{domain}, {comments} comments]"

            out.append(Story(
                source=f"r/{self.subreddit}",
                source_type=self.source_type,
                url=full_url,
                title=title,
                snippet=snippet,
                author=author,
                published=published,
                score=score,
                comments_url=f"https://old.reddit.com{permalink}" if permalink else full_url,
            ))
            if len(out) >= limit:
                break

        return out


def _clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'").replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text

# Patch: add rate-limit delay as module-level config
import asyncio
_RATE_LIMIT_DELAY = 3.0  # seconds between Reddit requests

# Monkey-patch RedditSource.fetch to add delay
_original_fetch = RedditSource.fetch
async def _rate_limited_fetch(self, client, *, lookback_hours, limit):
    await asyncio.sleep(_RATE_LIMIT_DELAY)
    return await _original_fetch(self, client, lookback_hours=lookback_hours, limit=limit)
RedditSource.fetch = _rate_limited_fetch
