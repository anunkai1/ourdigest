"""RSS feed writer (one feed per topic, plus a combined 'all' feed)."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator  # type: ignore[import-untyped]

from .config import Config, TopicConfig
from .models import Story


def _story_description(s: Story) -> str:
    parts: list[str] = []
    if s.summary:
        parts.append(f"<p><em>{html.escape(s.summary)}</em></p>")
    if s.snippet:
        parts.append(f"<p>{html.escape(s.snippet)}</p>")
    meta_bits = [f"Source: {html.escape(s.source)}"]
    if s.score:
        meta_bits.append(f"Score: {s.score}")
    if s.author:
        meta_bits.append(f"By: {html.escape(s.author)}")
    parts.append(f"<p><small>{' · '.join(meta_bits)}</small></p>")
    if s.comments_url and s.comments_url != s.url:
        parts.append(
            f'<p><a href="{html.escape(s.comments_url)}">Discussion</a></p>'
        )
    return "\n".join(parts)


def _build_feed(topic: TopicConfig, stories: list[Story], *, base_url: str) -> FeedGenerator:
    fg = FeedGenerator()
    fg.id(f"{base_url}/feed/{topic.key}.xml")
    fg.title(topic.title)
    fg.description(topic.description or topic.title)
    fg.link(href=f"{base_url}/feed/{topic.key}.xml", rel="self")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))
    sorted_stories = sorted(stories, key=lambda s: s.published, reverse=True)
    for s in sorted_stories:
        fe = fg.add_entry()
        fe.id(s.id)
        fe.title(s.title)
        fe.link(href=s.url, rel="alternate")
        fe.author(name=s.author) if s.author else None
        fe.published(s.published.astimezone(timezone.utc))
        fe.description(_story_description(s))
        fe.content(_story_description(s), type="html")
        fe.category({"term": s.source, "label": s.source})
    return fg


def write_feed(out_path: Path, topic: TopicConfig, stories: list[Story], *, base_url: str) -> None:
    fg = _build_feed(topic, stories, base_url=base_url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(out_path))


def write_all_feed(out_path: Path, cfg: Config, topic_stories: dict[str, list[Story]], *, base_url: str) -> None:
    combined_title = "ourdigest — all topics"
    combined_desc = "Combined feed across all topics."
    fg = FeedGenerator()
    fg.id(f"{base_url}/feed/all.xml")
    fg.title(combined_title)
    fg.description(combined_desc)
    fg.link(href=f"{base_url}/feed/all.xml", rel="self")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))
    flat: list[tuple[TopicConfig, Story]] = []
    for topic in cfg.topics:
        for s in topic_stories.get(topic.key, []):
            flat.append((topic, s))
    flat.sort(key=lambda ts: ts[1].published, reverse=True)
    for topic, s in flat:
        fe = fg.add_entry()
        fe.id(f"{topic.key}:{s.id}")
        fe.title(f"[{topic.title}] {s.title}")
        fe.link(href=s.url, rel="alternate")
        fe.published(s.published.astimezone(timezone.utc))
        fe.description(_story_description(s))
        fe.content(_story_description(s), type="html")
        fe.category({"term": topic.key, "label": topic.title})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(out_path))
