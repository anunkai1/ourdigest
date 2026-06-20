"""Top-level pipeline: fetch sources → filter → dedup → summarize."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

import httpx

from .config import Config, TopicConfig
from .models import Story
from .sources import build_source
from .storage import DedupStore
from .summarizer import Summarizer

log = logging.getLogger(__name__)


def _matches(story: Story, topic: TopicConfig) -> bool:
    # Score threshold: drop anything below topic.min_score.
    if topic.min_score and story.score < topic.min_score:
        return False
    # If keywords are configured, apply them as a secondary filter.
    if topic.keywords_any or topic.keywords_all or topic.keywords_none:
        haystack = f"{story.title}\n{story.url}\n{story.snippet}".lower()
        if topic.keywords_none and any(k in haystack for k in topic.keywords_none):
            return False
        if topic.keywords_all and not all(k in haystack for k in topic.keywords_all):
            return False
        if topic.keywords_any:
            return any(k in haystack for k in topic.keywords_any)
    # No keywords and no min_score: keep everything.
    return True


async def _fetch_one_source(
    cfg: Config,
    topic: TopicConfig,
    src_cfg,
    client: httpx.AsyncClient,
) -> list[Story]:
    source = build_source(src_cfg.type, src_cfg.name, src_cfg.params)
    log.info("fetching %s [%s] for topic %s", source.name, src_cfg.type, topic.key)
    try:
        return await source.fetch(
            client,
            lookback_hours=cfg.global_.lookback_hours,
            limit=cfg.global_.max_items_per_source,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("source %s failed: %s", source.name, exc)
        return []


async def fetch_topic(
    cfg: Config,
    topic: TopicConfig,
    *,
    store: DedupStore,
    client: httpx.AsyncClient,
    summarize: bool = True,
    summarizer: Summarizer | None = None,
) -> list[Story]:
    """Return new (un-seen) stories for a topic, after dedup + filtering.

    Side effects: marks each returned story id as seen in the store.
    """
    # 1. fetch all sources for this topic (sequentially, configurable later)
    fetched: list[Story] = []
    for src_cfg in topic.sources:
        fetched.extend(await _fetch_one_source(cfg, topic, src_cfg, client))

    # 2. filter by keywords
    kept = [s for s in fetched if _matches(s, topic)]
    log.info("topic %s: %d fetched, %d after filter (min_score=%d)", topic.key, len(fetched), len(kept), topic.min_score)

    # 3. dedup against the store
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    new: list[Story] = []
    for s in kept:
        if store.is_seen(s.id, topic.key):
            continue
        new.append(s)
    log.info("topic %s: %d new after dedup", topic.key, len(new))

    # 4. summarize (best-effort)
    if summarize and summarizer and new:
        await summarizer.summarize_many(
            client, new, max_chars=cfg.global_.summarize_max_input_chars
        )

    # 5. mark seen
    store.mark_seen([s.id for s in new], topic.key, now_ms)
    return new


async def fetch_all(
    cfg: Config,
    *,
    store: DedupStore,
    summarize: bool = True,
) -> dict[str, list[Story]]:
    """Fetch + dedup + summarize for every topic."""
    summarizer: Summarizer | None = None
    if summarize and cfg.global_.summarize:
        try:
            summarizer = Summarizer(model=cfg.global_.summarize_model)
        except ValueError as exc:
            log.warning("summarizer disabled: %s", exc)

    out: dict[str, list[Story]] = defaultdict(list)
    async with httpx.AsyncClient(
        headers={"User-Agent": cfg.global_.user_agent},
        timeout=cfg.global_.http_timeout_seconds,
    ) as client:
        for topic in cfg.topics:
            stories = await fetch_topic(
                cfg,
                topic,
                store=store,
                client=client,
                summarize=summarize,
                summarizer=summarizer,
            )
            out[topic.key] = stories
    return out
