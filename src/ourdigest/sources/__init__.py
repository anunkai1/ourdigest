"""Source plugin registry. Each source lives in its own module."""
from __future__ import annotations

from typing import Any

from .base import Source
from .reddit import RedditSource
from .hackernews import HackerNewsSource
from .lemmy import LemmySource
from .arxiv import ArxivSource


_REGISTRY: dict[str, type[Source]] = {
    "reddit": RedditSource,
    "hackernews": HackerNewsSource,
    "lemmy": LemmySource,
    "arxiv": ArxivSource,
}


def build_source(source_type: str, name: str, params: dict[str, Any]) -> Source:
    cls = _REGISTRY.get(source_type)
    if cls is None:
        raise ValueError(f"unknown source type: {source_type!r}")
    return cls(name=name, **params)


__all__ = ["Source", "build_source"]
