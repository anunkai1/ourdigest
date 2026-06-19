"""Data models shared across the pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def url_id(url: str) -> str:
    """Stable identifier for dedup, derived from URL."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Story:
    """A normalized item from any source."""

    source: str            # human source label, e.g. "r/LocalLLaMA"
    source_type: str       # "reddit" | "hackernews" | "lemmy" | "arxiv"
    url: str
    title: str
    snippet: str = ""
    author: str = ""
    published: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: int = 0
    comments_url: str = ""
    summary: str = ""      # filled by summarizer
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", url_id(self.url))

    @property
    def published_iso(self) -> str:
        return self.published.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
